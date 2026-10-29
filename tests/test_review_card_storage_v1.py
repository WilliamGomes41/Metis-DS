"""Native freshness, rollback and restart of non-authoritative Review inputs.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale durable recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import sys
from threading import Event, current_thread

import pytest

from src.review.revision_workflow import revise_object
from src.workflows import review_card_inputs_postgres_v1 as cards
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text
from tests.test_d5_4_review_interaction_evidence import _system


@pytest.fixture
def prepared(tmp_path, production_console):
    console, users, sid, oid = _system(tmp_path, production_console=production_console)
    cards.prepare_review_cards(console.workflow_document_store, sid)
    return console, users, sid, oid


def capture(console, sid):
    with console.workflow_document_store._connect() as con:
        return cards.capture_review_cards(console.workflow_document_store, con, [sid])[sid]


@pytest.mark.parametrize('damage', ['canonical','position','replace','truncate','missing','corrupt','foreign','contract','source_ref','identity_move'])
def test_sql_mutations_never_leave_stale_or_fictitiously_empty_current_cards(prepared, damage):
    console, users, sid, oid = prepared
    store = console.workflow_document_store
    assert 'unavailable' not in capture(console, sid)
    assert console._envelope(sid).get('processing_storage') != 'task-v1'
    with store._connect() as con:
        if damage == 'canonical':
            con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{content,clean_text}',"
                        "'\"different canonical text\"'::jsonb) WHERE snapshot_id=%s AND object_id=%s",(sid,oid))
        elif damage == 'position':
            con.execute('UPDATE workflow.document_objects SET position=position+100 WHERE snapshot_id=%s AND object_id=%s',(sid,oid))
        elif damage == 'replace':
            row = con.execute('DELETE FROM workflow.document_objects WHERE snapshot_id=%s AND object_id=%s '
                              'RETURNING object_version,payload,position',(sid,oid)).fetchone()
            con.execute('INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,position) '
                        'VALUES(%s,%s,%s,%s::jsonb,%s)',(sid,oid,row['object_version'],_json_text(row['payload']),row['position']))
        elif damage == 'truncate':
            con.execute('TRUNCATE workflow.document_objects')
        elif damage == 'missing':
            con.execute('DELETE FROM workflow.review_object_facts WHERE snapshot_id=%s AND object_id=%s',(sid,oid))
        elif damage == 'corrupt':
            con.execute("UPDATE workflow.review_object_facts SET record=jsonb_set(record,'{proof,lineage}','false'::jsonb) "
                        'WHERE snapshot_id=%s AND object_id=%s',(sid,oid))
        elif damage == 'foreign':
            con.execute('UPDATE workflow.review_object_facts f SET(record,record_hash)=(SELECT record,record_hash '
                        'FROM workflow.review_object_facts d WHERE d.snapshot_id=f.snapshot_id '
                        'AND d.object_id<>f.object_id AND d.current_version=f.current_version LIMIT 1) '
                        'WHERE snapshot_id=%s AND object_id=%s',(sid,oid))
            copied = con.execute("SELECT record,record_hash=encode(sha256(convert_to(record::text,'UTF8')),'hex') AS intact "
                                 'FROM workflow.review_object_facts WHERE snapshot_id=%s AND object_id=%s',(sid,oid)).fetchone()
            assert copied['record'] and copied['intact']
            assert copied['record']['fields']['object_id'] != oid
        elif damage == 'contract':
            con.execute("UPDATE workflow.review_object_facts SET record=jsonb_set(record,'{contract}','\"old-contract\"'::jsonb),"
                        "record_hash=encode(sha256(convert_to(jsonb_set(record,'{contract}','\"old-contract\"'::jsonb)::text,'UTF8')),'hex') "
                        'WHERE snapshot_id=%s AND object_id=%s',(sid,oid))
        elif damage == 'source_ref':
            con.execute('UPDATE workflow.documents SET review_source_ref=%s::jsonb WHERE snapshot_id=%s',(_json_text({'wrong':True}),sid))
        elif damage == 'identity_move':
            con.execute('UPDATE workflow.document_objects SET object_id=object_id||%s WHERE snapshot_id=%s AND object_id=%s',('-moved',sid,oid))
    assert 'unavailable' in capture(console, sid)


def test_governance_only_sql_is_live_without_source_preparation(prepared, monkeypatch):
    console, users, sid, oid = prepared
    before = next(o for o in capture(console,sid)['objects'] if o['object_id']==oid)
    def forbidden(*args, **kwargs):
        pytest.fail('Governance-only SQL rebuilt intrinsic source facts')
    monkeypatch.setattr(cards,'prepare_source_proof',forbidden)
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{governance,validation_status}',"
                    "'\"rejected\"'::jsonb) WHERE snapshot_id=%s AND object_id=%s",(sid,oid))
    current = capture(console,sid)
    assert 'unavailable' not in current
    after = next(o for o in current['objects'] if o['object_id']==oid)
    assert after['governance']['validation_status']=='rejected'
    assert after.exact_hash == before.exact_hash and after.proof == before.proof


def test_physical_document_metadata_keeps_existing_column_authority(prepared):
    console, users, sid, oid = prepared
    store = console.workflow_document_store
    with store._connect() as con:
        con.execute("UPDATE workflow.documents SET title='Current title',state='withdrawn',"
                    "publication_eligibility='pre_review_blocked' WHERE snapshot_id=%s", (sid,))
    current = capture(console, sid)
    assert 'unavailable' not in current
    assert current['envelope']['title'] == 'Current title'
    assert current['envelope']['state'] == 'withdrawn'
    assert current['envelope']['publication_eligibility'] == 'pre_review_blocked'
    assert console.list_document_lifecycle_statuses([sid], card_inputs={sid:current}) == console.list_document_lifecycle_statuses([sid])


@pytest.mark.parametrize('field', ['fragments_hash', 'version', 'extractor_contract'])
def test_changed_extraction_header_invalidates_card_capture(prepared, field):
    console, users, sid, oid = prepared
    store = console.workflow_document_store
    envelope = store.get_envelope(sid)
    envelope['prepared_source_extraction'][field] = 'corrupt-current-header'
    with store._connect() as con:
        con.execute('UPDATE workflow.documents SET envelope_payload=%s::jsonb WHERE snapshot_id=%s',
                    (_json_text(envelope), sid))
    assert console.review_source_fragments(sid) is None
    assert 'unavailable' in capture(console, sid)


def successor(console,sid,oid,*,score=None):
    store = console.workflow_document_store
    histories = store.list_document_objects(sid)
    before = next(o for o in console.snapshot_objects(sid) if o['object_id']==oid)
    proposed = deepcopy(before)
    if score is None:
        proposed['structure']['section_path'] = ['Explicit placement']
    else:
        proposed['logic'] = {**(proposed.get('logic') or {}), 'score_points':score}
    revised = revise_object(before,proposed,snapshot_id=sid,actor='fixture reviewer',reason='explicit reviewed revision')
    store.write_bundle(envelope=console._envelope(sid),objects=[*histories,revised],expected_revision=store.objects_revision(sid))
    return before,revised


def test_historical_governance_cannot_replace_the_current_revision(prepared):
    console, users, sid, oid = prepared
    before,revised = successor(console,sid,oid)
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{governance,validation_status}',"
                    "'\"rejected\"'::jsonb) WHERE snapshot_id=%s AND object_id=%s AND object_version=%s",
                    (sid,oid,before['object_version']))
    row = capture(console,sid)
    assert 'unavailable' not in row
    current = next(o for o in row['objects'] if o['object_id']==oid)
    assert current['object_version'] == revised['object_version']
    assert current['governance'] == revised['governance']


def test_numeric_jsonb_equality_does_not_hide_canonical_hash_change(prepared):
    console, users, sid, oid = prepared
    _,revised = successor(console,sid,oid,score=1)
    assert 'unavailable' not in capture(console,sid)
    with console.workflow_document_store._connect() as con:
        assert con.execute("SELECT '1'::jsonb='1.0'::jsonb AS same").fetchone()['same']
        con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{logic,score_points}','1.0'::jsonb) "
                    'WHERE snapshot_id=%s AND object_id=%s AND object_version=%s',(sid,oid,revised['object_version']))
    assert 'unavailable' in capture(console,sid)


def test_rollback_restores_authority_and_fact_capture_together(prepared):
    console, users, sid, oid = prepared
    store = console.workflow_document_store
    with store._connect() as con:
        before = con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s',(sid,)).fetchone()
    original = next(o for o in capture(console,sid)['objects'] if o['object_id']==oid)
    with pytest.raises(RuntimeError,match='abort-proof'):
        with store._connect() as con:
            con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{governance,validation_status}',"
                        "'\"rejected\"'::jsonb) WHERE snapshot_id=%s AND object_id=%s",(sid,oid))
            raise RuntimeError('abort-proof')
    with store._connect() as con:
        assert con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s',(sid,)).fetchone()==before
    actual = next(o for o in capture(console,sid)['objects'] if o['object_id']==oid)
    assert actual['governance'] == original['governance'] and actual.exact_hash==original.exact_hash


def test_preparation_cas_cannot_overwrite_a_concurrent_review(prepared,monkeypatch):
    console, users, sid, oid = prepared
    ready, resume = Event(), Event()
    original = cards._prepare
    def paused(*args,**kwargs):
        result = original(*args,**kwargs)
        if current_thread().name.startswith('card-preparation-proof'):
            ready.set()
            assert resume.wait(20)
        return result
    monkeypatch.setattr(cards,'_prepare',paused)
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='card-preparation-proof') as pool:
        pending = pool.submit(cards.prepare_review_cards,console.workflow_document_store,sid)
        assert ready.wait(20)
        try:
            console.review_object(actor_id=users['reviewer_a']['account_id'],snapshot_id=sid,
                                  object_id=oid,decision='approve',confirmed_object_type='definition')
        finally:
            resume.set()
        with pytest.raises(WorkflowDocumentStoreError,match='preparation_conflict'):
            pending.result(timeout=20)
    row = capture(console,sid)
    assert 'unavailable' not in row
    assert next(o for o in row['objects'] if o['object_id']==oid)['governance']['validation_status']=='approved'


def test_new_process_reads_the_same_current_facts(prepared):
    console, users, sid, oid = prepared
    expected = capture(console,sid)
    script = '''
import json,os
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflows.review_card_inputs_postgres_v1 import capture_review_cards
store=PostgresWorkflowDocumentRuntimeStore(PostgresCanonicalConfig(dsn=os.environ['CARD_PROOF_DSN']))
with store._connect() as con:
 row=capture_review_cards(store,con,[os.environ['CARD_PROOF_SID']])[os.environ['CARD_PROOF_SID']]
 print(json.dumps(sorted((o['object_id'],o['object_version'],o.exact_hash) for o in row['objects'])))
'''
    env={**os.environ,'CARD_PROOF_DSN':console.workflow_document_store.config.dsn,'CARD_PROOF_SID':sid}
    process=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=30,check=True)
    assert json.loads(process.stdout)==sorted([o['object_id'],o['object_version'],o.exact_hash] for o in expected['objects'])


def test_runtime_base_writer_uses_the_same_atomic_fact_owner(prepared):
    from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
    console,users,sid,oid=prepared
    runtime=PostgresWorkflowDocumentRuntimeStore(console.workflow_document_store.config)
    before=capture(console,sid)
    runtime.write_bundle(envelope=runtime.get_envelope(sid),objects=runtime.list_document_objects(sid),
                         expected_revision=runtime.objects_revision(sid))
    after=capture(console,sid)
    assert 'unavailable' not in after
    assert [(o['object_id'],o.exact_hash) for o in after['objects']]==[(o['object_id'],o.exact_hash) for o in before['objects']]


def test_explicit_legacy_preparation_builds_views_from_retained_source_without_original(tmp_path,production_console,monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(cards,'prepare_activation',lambda *a,**k:None)
        console,users,sid,oid=_system(tmp_path,production_console=production_console)
    store=console.workflow_document_store
    assert 'unavailable' in capture(console,sid)
    with store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.source_read_roots').fetchone()['n']==0
    console._source_cache_path(console._envelope(sid)).unlink()
    result=cards.prepare_review_cards(store,sid)
    assert result['objects']>0 and 'unavailable' not in capture(console,sid)
    env={**os.environ,'METIS_CANONICAL_DB_DSN':store.config.dsn}
    child=subprocess.run([sys.executable,'scripts/prepare_review_cards.py','--snapshot',sid,'--check'],
                         env=env,capture_output=True,text=True,timeout=30,check=True)
    assert json.loads(child.stdout)['status']=='current'


@pytest.mark.parametrize('relation_only', [False, True])
def test_revoked_assignment_during_capture_hides_even_unavailable_cards(prepared, relation_only):
    from src.review.review_workboard_v1 import review_workboard_items
    console, users, sid, oid = prepared
    account = users['reviewer_a']
    console.review_card_read_mode = 'compact'
    summaries = console.review_workboard_summaries(account['account_id'], metadata_only=True)
    assert sid in summaries
    envelope = console.workflow_document_store.get_envelope(sid)
    envelope['named_reviewers'].remove(account['account_id'])
    with console.workflow_document_store._connect() as con:
        con.execute('DELETE FROM workflow.document_reviewers WHERE snapshot_id=%s AND account_id=%s',
                    (sid, account['account_id']))
        if not relation_only:
            con.execute('UPDATE workflow.documents SET envelope_payload=%s::jsonb WHERE snapshot_id=%s',
                        (_json_text(envelope), sid))
        con.execute('UPDATE workflow.review_fact_state SET initialized=false WHERE snapshot_id=%s', (sid,))
    console._enrich_review_workboard_summaries(account['account_id'], summaries)
    assert review_workboard_items(console, account=account, summaries=summaries) == []


def test_reader_rollback_restarts_on_unchanged_authority(prepared):
    from tests.production_support import production_application
    console, users, sid, oid = prepared
    store = console.workflow_document_store
    actor = users['reviewer_a']['account_id']
    console.review_card_read_mode = 'compact'
    compact = console.review_workboard_summaries(actor, sid)[sid]['work_item']
    before = store.list_document_objects(sid)
    bindings = console.object_review_bindings(sid)
    with store._connect() as con:
        state = con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s', (sid,)).fetchone()
    restarted = production_application(console.root, store.config,
        processing_binder=console._metis_test_processing_binder,
        immutable_source_store=console.immutable_source_store,
        runtime=console.runtime, source_store=console.source_store,
        environment={'CONSOLE_REVIEW_CARD_READS':'legacy'}).state.operations_kernel
    assert restarted.review_card_read_mode == 'legacy'
    legacy = restarted.review_workboard_summaries(actor, sid)[sid]['work_item']
    legacy['envelope'] = compact['envelope']
    assert legacy == compact
    assert restarted.workflow_document_store.list_document_objects(sid) == before
    assert restarted.object_review_bindings(sid) == bindings
    with store._connect() as con:
        assert con.execute('SELECT * FROM workflow.review_fact_state WHERE snapshot_id=%s', (sid,)).fetchone() == state
