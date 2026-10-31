"""Native MET-41 proof/activation tests; no activation from diagnostic hashes.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from threading import Event

import psycopg
import pytest

from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_formation_task_store_postgres import validator_data, checkpoint_context


@pytest.fixture(params=[False, True], ids=['local-source','azure-source'])
def pending_proof(tmp_path, production_console, request):
    def factory(**kwargs):
        return production_console(azure=request.param, **kwargs)
    console, users, sid, _ = _system(tmp_path, production_console=factory)
    envelope = console._envelope(sid)
    data = validator_data(envelope)
    # The fixture is semantic v1. Preserve its original validator contract.
    data['field_contract_v3'] = False
    writer = checkpoint_context(console, envelope, data)
    from src.vorming.prepared_source_views_v1 import prepare
    from src.vorming.source_preparation_context_v1 import stored_extraction
    writer.retain_source_views(prepare(stored_extraction(envelope)).payload)
    replay = deepcopy(envelope['semantic_replay'])
    writer.final_validation(replay['proposal'])
    writer.seal_formation(replay)
    envelope = console.workflow_document_store.get_envelope(sid)
    ref = envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref']
    return console, users, writer, envelope, ref


def test_complete_proof_is_sealed_before_activation_and_pin_is_atomic(pending_proof):
    console, _, writer, envelope, ref = pending_proof
    store = writer.store
    sid = envelope['snapshot_id']
    proof = store.read_formation_evidence(ref, envelope=envelope)
    assert next(value for role, _, value in proof['members'] if role == 'replay') == envelope['semantic_replay']
    with store.documents._connect() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['formation_evidence_id'] is None
    objects = console.snapshot_objects(sid)
    store.documents.write_bundle(envelope=envelope, objects=objects, expected_revision=console.objects_revision(sid), formation_activation_ref=envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref'])
    with store.documents._connect() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['formation_evidence_id'] == ref['proof_id']
    assert store.read_formation_evidence(ref, envelope=envelope) == proof


def test_missing_member_with_recomputed_manifest_is_rejected(pending_proof):
    _, _, writer, envelope, _ = pending_proof
    prepared = writer.store.prepare_formation_evidence(envelope,
        context_id=writer.input_reference['context_id'], attempt_id=writer.attempt_id)
    header = json.loads(prepared.header_text)
    members = prepared.members[1:]
    header['manifest'] = [[a,b,c] for a,b,c,_ in members]
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_preparation_changed'):
        writer.store.publish_formation_evidence(envelope, replace(prepared,
            header_text=json.dumps(header, ensure_ascii=False, sort_keys=True, separators=(',',':')), members=members))


def test_sql_member_root_mutation_and_incomplete_commit_are_refused(pending_proof):
    _, _, writer, envelope, ref = pending_proof
    for statement, params in [
        ('UPDATE workflow.formation_evidence_members SET payload_text=payload_text WHERE proof_id=%s', (ref['proof_id'],)),
        ('DELETE FROM workflow.formation_evidence_members WHERE proof_id=%s', (ref['proof_id'],)),
        ('DELETE FROM workflow.formation_evidence_roots WHERE proof_id=%s', (ref['proof_id'],)),
        ('TRUNCATE workflow.formation_evidence_members', ())]:
        with pytest.raises(psycopg.Error, match='formation_evidence_immutable'):
            with writer.store.documents._connect() as con:
                con.execute(statement, params)
    with pytest.raises(psycopg.Error, match='formation_evidence_membership_incomplete'):
        with writer.store.documents._connect() as con:
            con.execute("INSERT INTO workflow.formation_evidence_roots SELECT 'unfinished',snapshot_id,context_id,extraction_hash,header,false "
                        'FROM workflow.formation_evidence_roots WHERE proof_id=%s', (ref['proof_id'],))


def test_changed_proposal_or_current_result_capture_cannot_activate(pending_proof):
    console, _, writer, envelope, ref = pending_proof
    objects = console.snapshot_objects(envelope['snapshot_id'])
    revision = console.objects_revision(envelope['snapshot_id'])
    changed = deepcopy(envelope)
    changed['semantic_replay']['provider_evidence']['extra_unknown_finding'] = True
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_replay_changed'):
        writer.store.documents.write_bundle(envelope=changed, objects=objects, expected_revision=revision, formation_activation_ref=envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref'])
    with writer.store.documents._connect() as con:
        con.execute("UPDATE workflow.formation_contexts SET final_validation=NULL WHERE context_id=%s", (writer.input_reference['context_id'],))
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_finalized_capture_required'):
        writer.store.documents.write_bundle(envelope=envelope, objects=objects, expected_revision=revision, formation_activation_ref=envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref'])
    with writer.store.documents._connect() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (envelope['snapshot_id'],)).fetchone()['formation_evidence_id'] is None
    assert writer.store.read_formation_evidence(ref, envelope=envelope)


def test_real_failure_after_pin_rolls_back_pin_and_objects(pending_proof, monkeypatch):
    console, _, writer, envelope, _ = pending_proof
    store = writer.store.documents
    sid = envelope['snapshot_id']
    before = console.snapshot_objects(sid)
    def failure(con, *args, **kwargs):
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['formation_evidence_id'] is not None
        con.execute('SELECT 1/0')
    monkeypatch.setattr(store, '_write_objects_locked', failure)
    with pytest.raises(WorkflowDocumentStoreError, match='workflow_document_bundle_write_failed'):
        store.write_bundle(envelope=envelope, objects=before, expected_revision=console.objects_revision(sid), formation_activation_ref=envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref'])
    with store._connect() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['formation_evidence_id'] is None
    assert console.snapshot_objects(sid) == before


def test_proof_survives_independent_process_and_cascade_is_allowed(pending_proof, tmp_path):
    _, _, writer, envelope, ref = pending_proof
    handoff = tmp_path/'proof.json'
    handoff.write_text(json.dumps({'envelope':envelope,'reference':ref}))
    code = '''
import json,sys
from pathlib import Path
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
data=json.loads(Path(sys.argv[2]).read_text())
store=FormationTaskStore(PostgresWorkflowDocumentStore(PostgresCanonicalConfig(dsn=sys.argv[1])))
proof=store.read_formation_evidence(data['reference'],envelope=data['envelope'])
print(json.dumps(proof['header']['capture']['replay_ref']))
'''
    child=subprocess.run([sys.executable,'-c',code,writer.store.documents.config.dsn,str(handoff)],
                         capture_output=True,text=True,timeout=20)
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout)['kind'] == 'semantic_replay'
    writer.store.documents.delete_document(envelope['snapshot_id'])
    with writer.store.documents._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.formation_evidence_roots').fetchone()['n'] == 0


def test_actual_reextract_producer_seals_and_activates_without_manual_proof_calls(tmp_path, production_console, monkeypatch):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    from scripts.migrate_processing_attempts import migrate
    migrate(console.workflow_document_store, sid, apply=True)
    console.reextract_unpublished(actor_id=users['researcher']['account_id'], snapshot_id=sid)
    store = FormationTaskStore(console.workflow_document_store)
    envelope = store.documents.get_envelope(sid)
    diagnostic = envelope['processing_attempts'][-1]['diagnostic']
    assert diagnostic['final_validation']['version'] == 3
    ref = diagnostic['formation_evidence_ref']
    with store.documents._connect() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['formation_evidence_id'] == ref['proof_id']
    proof = store.read_formation_evidence(ref, envelope=envelope)
    assert next(v for role, _, v in proof['members'] if role == 'replay') == envelope['semantic_replay']
    target = next(row for row in console.snapshot_objects(sid) if row.get('object_type') not in {'document','heading'})
    console.review_object(actor_id=users['reviewer_a']['account_id'], snapshot_id=sid,
        object_id=target['object_id'], decision='approve', confirmed_object_type='definition',
        expected_revision=console.objects_revision(sid))
    with store.documents._connect() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s',
                           (sid,)).fetchone()['formation_evidence_id'] == ref['proof_id']


@pytest.mark.parametrize('mutation', ['revision','gate','input','remove_input','storage'])
def test_pinned_activation_rejects_changed_or_downgraded_receipt(pending_proof, mutation):
    console, _, writer, envelope, _ = pending_proof
    store = writer.store.documents
    sid = envelope['snapshot_id']
    objects, revision = console.snapshot_objects(sid), console.objects_revision(sid)
    store.write_bundle(envelope=envelope, objects=objects, expected_revision=revision, formation_activation_ref=envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref'])
    changed = deepcopy(envelope)
    latest = changed['processing_attempts'][-1]
    diagnostic = latest['diagnostic']
    if mutation == 'revision': latest['expected_revision'] = 'stale'
    elif mutation == 'gate': diagnostic['final_validation']['validator_identity'] = {}
    elif mutation == 'input': diagnostic['validator_input_ref']['artifact_id'] = 'wrong'
    elif mutation == 'remove_input': diagnostic.pop('validator_input_ref')
    else: changed.pop('processing_storage')
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_'):
        store.write_bundle(envelope=changed, objects=objects, expected_revision=revision)


def test_metadata_write_cannot_detach_or_change_pinned_producer_evidence(pending_proof):
    console, _, writer, envelope, _ = pending_proof
    store = writer.store.documents
    sid = envelope['snapshot_id']
    store.write_bundle(envelope=envelope, objects=console.snapshot_objects(sid), expected_revision=console.objects_revision(sid), formation_activation_ref=envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref'])
    for field in ('semantic_replay', 'prepared_source_extraction'):
        changed = deepcopy(envelope)
        if field == 'semantic_replay':
            changed[field]['provider_evidence'] = {}
        else:
            changed.pop(field)
        with pytest.raises(WorkflowDocumentStoreError, match='workflow_document_bundle_write_failed'):
            store.write_bundle(envelope=changed)
    with pytest.raises(psycopg.Error, match='formation_evidence_pin_required'):
        with store._connect() as con:
            con.execute('UPDATE workflow.documents SET formation_evidence_id=NULL WHERE snapshot_id=%s', (sid,))


def test_new_activation_cannot_overwrite_metadata_that_changed_after_preparation(pending_proof):
    console, _, writer, envelope, _ = pending_proof
    store = writer.store.documents
    sid = envelope['snapshot_id']
    fresh = deepcopy(envelope)
    fresh['title'] = 'Winning metadata'
    store.write_bundle(envelope=fresh)
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_activation_changed'):
        store.write_bundle(envelope=envelope, objects=console.snapshot_objects(sid), expected_revision=console.objects_revision(sid), formation_activation_ref=envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref'])
    assert store.get_envelope(sid)['title'] == 'Winning metadata'


@pytest.mark.parametrize('mutation', ['expired','revoked','claim'])
def test_new_pin_rechecks_live_attempt_and_actor(pending_proof, mutation):
    console, _, writer, envelope, _ = pending_proof
    attempt = envelope['processing_attempts'][-1]
    with writer.store.documents._connect() as con:
        if mutation == 'expired':
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{expires_at}',"
                "to_jsonb((CURRENT_TIMESTAMP-interval '1 second')::text)) WHERE attempt_id=%s", (attempt['attempt_id'],))
        elif mutation == 'revoked':
            con.execute("UPDATE workflow.accounts SET roles=ARRAY['publisher']::text[] WHERE account_id=%s", (attempt['actor_id'],))
        else:
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch}',"
                "'{\"state\":\"claimed\",\"token\":\"new-owner\"}'::jsonb) WHERE attempt_id=%s", (attempt['attempt_id'],))
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_'):
        writer.store.documents.write_bundle(envelope=envelope, objects=console.snapshot_objects(envelope['snapshot_id']),
            expected_revision=console.objects_revision(envelope['snapshot_id']), formation_activation_ref=envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref'])
    with writer.store.documents._connect() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s',
                           (envelope['snapshot_id'],)).fetchone()['formation_evidence_id'] is None


def test_attempt_expiring_during_native_account_lock_wait_cannot_pin(pending_proof, monkeypatch):
    import src.vorming.processing_retry_v1 as retry_clock
    console, _, writer, envelope, _ = pending_proof
    store = writer.store.documents
    attempt = envelope['processing_attempts'][-1]
    sid = envelope['snapshot_id']
    objects, revision = console.snapshot_objects(sid), console.objects_revision(sid)
    clock = [datetime.now(timezone.utc)]
    monkeypatch.setattr(retry_clock, 'now', lambda: clock[0])
    original = store._connect
    connected, worker_pid = Event(), []
    @contextmanager
    def observed_connect():
        with original() as con:
            worker_pid.append(con.info.backend_pid)
            connected.set()
            yield con
    with original() as locker:
        locker.execute('SELECT account_id FROM workflow.accounts WHERE account_id=%s FOR UPDATE', (attempt['actor_id'],))
        monkeypatch.setattr(store, '_connect', observed_connect)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(store.write_bundle, envelope=envelope, objects=objects, expected_revision=revision, formation_activation_ref=envelope['processing_attempts'][-1]['diagnostic']['formation_evidence_ref'])
            try:
                assert connected.wait(5)
                deadline = time.monotonic()+10
                while time.monotonic()<deadline:
                    row = locker.execute('SELECT pg_blocking_pids(%s) AS blockers', (worker_pid[0],)).fetchone()
                    if locker.info.backend_pid in row['blockers']:
                        break
                    time.sleep(.01)
                else:
                    pytest.fail('Activation never waited on the native account lock')
                # Native blocking is real; the deadline clock is controlled so
                # this proof does not depend on CI scheduling or wall sleeps.
                clock[0] = datetime.fromisoformat(attempt['expires_at'])+timedelta(seconds=1)
            finally:
                locker.commit()
            with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_activation_not_authorized'):
                future.result(timeout=10)
    with original() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['formation_evidence_id'] is None


@pytest.mark.parametrize('route', ['bounded','pure_replay'])
def test_final_replay_and_accounting_cannot_jointly_omit_a_recorded_failure(tmp_path, production_console, monkeypatch, route):
    from src.operations_console_v1 import ConsoleError
    from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.vorming.source_bound_fields_v3 import MODE
    from tests.test_recommendation_context_v3 import response_for
    from src.workflows.workflow_documents_postgres_v1 import _json_text
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    actor = users['researcher']['account_id']
    sid = console.receive_source(actor_id=actor,filename='proof.html',content_type='text/html',
        data=b'<html><body><h1>Een</h1><p>Gebruik geen zalf.</p><h1>Twee</h1><p>Controleer dagelijks de huid.</p></body></html>',
        ingest_kind='new',title='Complete proof',version='1',date='2026-10-31',live_url='',class_='richtlijn',family='test',
        named_reviewers=[users['reviewer_a']['account_id']])['snapshot_id']
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    def provider(_url,_headers,payload,_timeout):
        text = json.loads(payload['input'][1]['content'])['source_blocks'][0]['text']
        if 'Controleer' in text:
            raise ConsoleError('pre_review_llm_response_timeout')
        proposal = response_for(payload,text)
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal)}]}]}
    bind_pre_review_semantic_processing(console,environ={'METIS_PASSAGE_FORMATION_MODE':MODE,
        'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'test'},post_json=provider)
    attempt,_ = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='proof-failure',
        expected_revision=console.objects_revision(sid))
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    store = FormationTaskStore(console.workflow_document_store)
    if route == 'pure_replay':
        console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    envelope = store.documents.get_envelope(sid)
    attempt = envelope['processing_attempts'][-1]
    if route == 'pure_replay':
        assert envelope['semantic_replay']['semantic_execution'] == 'replay'
        with store.documents._connect() as con:
            assert con.execute("SELECT count(*) AS n FROM workflow.processing_checkpoints WHERE attempt_id=%s "
                "AND phase='formation_call_basis'", (attempt['attempt_id'],)).fetchone()['n'] == 0
    diagnostic = envelope['processing_attempts'][-1]['diagnostic']
    replay = deepcopy(envelope['semantic_replay'])
    assert replay['provider_evidence']['pending_rejections']
    evidence = replay['provider_evidence']
    for call in [evidence, *evidence.get('supplementary_calls',[])]:
        call.pop('error_code', None)
        call.pop('failure_reason', None)
    evidence.update(pending_rejections=[],formation_incomplete=False)
    if route == 'pure_replay':
        # Caller-supplied prior data must not replace the actual owner record.
        envelope['semantic_replay'] = replay
    ref = store.retain_processing_archive(store.prepare_processing_archive(envelope,kind='semantic_replay',
        record_key='forged-final',observed_revision=console.objects_revision(sid),payload=replay))
    with store.documents._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{diagnostic,formation_finalized_ref}',%s::jsonb) "
            'WHERE attempt_id=%s', (_json_text(ref), attempt['attempt_id']))
        con.execute("UPDATE workflow.processing_checkpoints SET payload=jsonb_set(payload,'{provider_evidence}',%s::jsonb) "
            "WHERE attempt_id=%s AND phase='formation_accounted'", (_json_text(evidence),attempt['attempt_id']))
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_call_membership_changed'):
        store.prepare_formation_evidence(envelope, context_id=diagnostic['validator_input_ref']['context_id'],
            attempt_id=attempt['attempt_id'])


def test_curation_keeps_active_proof_when_producer_context_and_authority_change(pending_proof):
    console, _, writer, envelope, ref = pending_proof
    store = writer.store.documents
    sid = envelope['snapshot_id']
    objects, revision = console.snapshot_objects(sid), console.objects_revision(sid)
    store.write_bundle(envelope=envelope, objects=objects, expected_revision=revision, formation_activation_ref=ref)
    attempt = envelope['processing_attempts'][-1]
    with store._connect() as con:
        con.execute('UPDATE workflow.formation_contexts SET final_validation=NULL WHERE context_id=%s',
                    (writer.input_reference['context_id'],))
        con.execute("UPDATE workflow.accounts SET roles=ARRAY['publisher']::text[] WHERE account_id=%s", (attempt['actor_id'],))
    # Curation retains original producer evidence; it is not a new activation
    # and must not depend on the mutable context's latest validation receipt.
    current = store.get_envelope(sid)
    current['title'] = 'Curation while another attempt is prepared'
    store.write_bundle(envelope=current, objects=objects, expected_revision=revision)
    assert store.get_envelope(sid)['title'] == current['title']
    with store._connect() as con:
        assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()['formation_evidence_id'] == ref['proof_id']
    # Explicit producer activation still must recheck the current owner state.
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_'):
        store.write_bundle(envelope=current, objects=objects, expected_revision=revision, formation_activation_ref=ref)


def test_unpinned_new_proof_requires_explicit_activation_operation(pending_proof):
    console, _, writer, envelope, ref = pending_proof
    store = writer.store.documents
    sid = envelope['snapshot_id']
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_activation_operation_required'):
        store.write_bundle(envelope=envelope, objects=console.snapshot_objects(sid), expected_revision=console.objects_revision(sid))
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_activation_objects_required'):
        store.write_bundle(envelope=envelope, formation_activation_ref=ref)
    from src.operations_console_v1 import ConsoleError
    with pytest.raises(ConsoleError, match='formation_evidence_activation_objects_required'):
        console._commit_prepared_store(snapshot_id=sid, formation_activation_ref=ref)


@pytest.mark.parametrize('mutation', ['expired','revoked','claim'])
def test_same_pin_explicit_producer_retry_requires_live_authorization(pending_proof, mutation):
    console, _, writer, envelope, ref = pending_proof
    store = writer.store.documents
    sid = envelope['snapshot_id']
    objects, revision = console.snapshot_objects(sid), console.objects_revision(sid)
    store.write_bundle(envelope=envelope, objects=objects, expected_revision=revision, formation_activation_ref=ref)
    attempt = envelope['processing_attempts'][-1]
    with store._connect() as con:
        if mutation == 'expired':
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{expires_at}',to_jsonb((CURRENT_TIMESTAMP-interval '1 second')::text)) WHERE attempt_id=%s", (attempt['attempt_id'],))
        elif mutation == 'revoked':
            con.execute("UPDATE workflow.accounts SET roles=ARRAY['publisher']::text[] WHERE account_id=%s", (attempt['actor_id'],))
        else:
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch}','{\"state\":\"claimed\",\"token\":\"new-owner\"}'::jsonb) WHERE attempt_id=%s", (attempt['attempt_id'],))
    current = store.get_envelope(sid)
    # Normal curation retains the historical pin regardless of producer rights.
    store.write_bundle(envelope=current, objects=objects, expected_revision=revision)
    with pytest.raises(WorkflowDocumentStoreError, match='formation_evidence_'):
        store.write_bundle(envelope=current, objects=objects, expected_revision=revision, formation_activation_ref=ref)
    assert console.snapshot_objects(sid) == objects


@pytest.mark.parametrize('azure', [False, True], ids=['local-source','azure-source'])
def test_new_source_context_is_staged_and_switches_only_with_activation(tmp_path, production_console, monkeypatch, azure):
    from src.operations_console_v1 import ConsoleError
    from src.vorming.formation_checkpoint_v1 import TaskCheckpointWriter
    import src.vorming.extract_html_v1 as extractor
    from scripts.migrate_processing_attempts import migrate
    def factory(**kwargs):
        return production_console(azure=azure, **kwargs)
    console, users, sid, _ = _system(tmp_path, production_console=factory)
    actor = users['researcher']['account_id']
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    migrate(console.workflow_document_store, sid, apply=True)
    console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    store = console.workflow_document_store
    def active():
        with store._connect() as con:
            return con.execute('SELECT formation_evidence_id,review_source_ref,'
                "envelope_payload#>>'{prepared_source_extraction,record_hash}' AS extraction "
                'FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()
    before = active()
    original = TaskCheckpointWriter.seal_formation
    captured = []
    monkeypatch.setattr(extractor, 'PARSER_VERSION', extractor.PARSER_VERSION+'-source-transition-test')
    def interrupted(writer, replay):
        assert active() == before
        assert writer.staged_extraction['record_hash'] != before['extraction']
        assert writer.review_source_reference != before['review_source_ref']
        # An independent new worker reuses the staged immutable extraction.
        attempt = writer.store.documents.get_envelope(sid)['processing_attempts'][-1]
        restarted = TaskCheckpointWriter(console, sid, attempt)
        assert restarted.staged_extraction == writer.staged_extraction
        captured.append(writer.staged_extraction['record_hash'])
        raise ConsoleError('pre_review_llm_response_timeout')
    monkeypatch.setattr(TaskCheckpointWriter, 'seal_formation', interrupted)
    with pytest.raises(ConsoleError, match='pre_review_llm_response_timeout'):
        console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    assert captured and active() == before
    # Existing Review still reads the complete original source after failure.
    assert console.review_source_fragments(sid) is not None
    monkeypatch.setattr(TaskCheckpointWriter, 'seal_formation', original)
    console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    after = active()
    assert after['formation_evidence_id'] != before['formation_evidence_id']
    assert after['review_source_ref'] != before['review_source_ref']
    assert after['extraction'] == captured[-1]
    with store._connect() as con:
        header = con.execute('SELECT header FROM workflow.formation_evidence_roots WHERE proof_id=%s',
                             (after['formation_evidence_id'],)).fetchone()['header']
    assert header['capture']['source_ref'] == after['review_source_ref']
    assert header['capture']['active_source_ref'] == before['review_source_ref']
    # SQL and independent preparation cannot detach this active source basis.
    with pytest.raises(psycopg.Error, match='formation_evidence_active_binding_changed'):
        with store._connect() as con:
            con.execute('UPDATE workflow.documents SET review_source_ref=%s::jsonb WHERE snapshot_id=%s',
                        (json.dumps(before['review_source_ref']), sid))
    assert console.prepare_review_source_views(actor_id=actor,snapshot_id=sid,
        expected_revision=console.objects_revision(sid)) == after['review_source_ref']


@pytest.mark.parametrize('corruption', [None,'missing_member','missing_section'])
def test_existing_workflow_backup_restores_complete_proof_or_rolls_back(pending_proof, corruption):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore, PostgresCanonicalConfig
    from src.publication.publication_chain_recovery_v1 import PublicationChainRecoveryError
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from src.workflows.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore
    from tests.postgres_support import database
    from tests.test_workflow_chain_recovery_v1 import _install_schema
    console, _, writer, envelope, ref = pending_proof
    store = writer.store.documents
    sid = envelope['snapshot_id']
    store.write_bundle(envelope=envelope, objects=console.snapshot_objects(sid),
        expected_revision=console.objects_revision(sid), formation_activation_ref=ref)
    source = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(store.config))
    state = source.export_state()
    assert state['formation_recovery']['tables']['formation_evidence_members']
    if corruption == 'missing_member':
        state['formation_recovery']['tables']['formation_evidence_members'].pop()
    elif corruption == 'missing_section':
        state.pop('formation_recovery')
    with database(store.config.dsn) as target_db:
        _install_schema(target_db.dsn)
        config = PostgresCanonicalConfig(dsn=target_db.dsn)
        target = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config))
        if corruption:
            with pytest.raises(PublicationChainRecoveryError):
                target.restore_state(state)
            target.assert_empty()
            return
        # Physical insertion order is not logical identity. Include multiple
        # members sharing (proof_id,role) to exercise the complete compound key.
        reordered = deepcopy(state)
        for rows in reordered['formation_recovery']['tables'].values():
            rows.reverse()
        target.restore_state(reordered)
        restored = target.export_state()
        assert restored['formation_recovery'] == state['formation_recovery']
        fresh = FormationTaskStore(PostgresWorkflowDocumentStore(config))
        assert fresh.read_formation_evidence(ref, envelope=envelope) == writer.store.read_formation_evidence(ref, envelope=envelope)
        with fresh.documents._connect() as con:
            assert con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s',
                               (sid,)).fetchone()['formation_evidence_id'] == ref['proof_id']


def test_resume_before_validator_input_keeps_staged_extraction_and_active_review(tmp_path, production_console, monkeypatch):
    from src.operations_console_v1 import ConsoleError
    from src.vorming.formation_checkpoint_v1 import TaskCheckpointWriter
    from src.vorming.source_preparation_context_v1 import build_formation_context
    from src.vorming.processing_retry_v1 import reserve, now
    import src.vorming.extract_html_v1 as extractor
    from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.vorming.source_bound_fields_v3 import MODE
    from tests.test_recommendation_context_v3 import response_for
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    actor = users['researcher']['account_id']
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    def provider(_url,_headers,payload,_timeout):
        text = json.loads(payload['input'][1]['content'])['source_blocks'][0]['text']
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text',
            'text':json.dumps(response_for(payload,text))}]}]}
    def bind(kernel):
        bind_pre_review_semantic_processing(kernel, environ={'METIS_PASSAGE_FORMATION_MODE':MODE,
            'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'test'}, post_json=provider)
    bind(console)
    sid = console.receive_source(actor_id=actor,filename='staged.html',content_type='text/html',
        data=b'<html><body><h1>Advies</h1><p>Gebruik geen zalf.</p></body></html>',ingest_kind='new',
        title='Staged resume',version='1',date='2026-10-31',live_url='',class_='richtlijn',family='test',
        named_reviewers=[users['reviewer_a']['account_id']])['snapshot_id']
    first,_ = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='first',
        expected_revision=console.objects_revision(sid))
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=first)
    before = console._envelope(sid)
    original = TaskCheckpointWriter.stage_extraction
    staged = []
    monkeypatch.setattr(extractor, 'PARSER_VERSION', extractor.PARSER_VERSION+'-resume-stage-test')
    def interrupted(writer, record):
        result = original(writer,record)
        if result:
            staged.append(record)
            raise ConsoleError('pre_review_llm_response_timeout')
        return result
    monkeypatch.setattr(TaskCheckpointWriter, 'stage_extraction', interrupted)
    with pytest.raises(ConsoleError, match='pre_review_llm_response_timeout'):
        console.reextract_unpublished(actor_id=actor,snapshot_id=sid)
    monkeypatch.setattr(TaskCheckpointWriter, 'stage_extraction', original)
    current = console._envelope(sid)
    assert current['prepared_source_extraction'] == before['prepared_source_extraction']
    assert 'validator_input_ref' not in current['processing_attempts'][-1]['diagnostic']
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from tests.test_workflow_chain_recovery_v1 import _install_schema
    from tests.production_support import production_application
    config = console.workflow_document_store.config
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config))
    backup = adapter.export_state()
    _install_schema(config.dsn)  # The fixture owns this disposable database.
    adapter.restore_state(backup)
    console = production_application(tmp_path, config, processing_binder=bind,
        source_store=tmp_path/'sources'/'private', runtime=tmp_path/'runtime'/'console').state.operations_kernel
    with console._reprocessing_transaction(sid):
        current = console._envelope(sid)
        # Use the actual reservation operation; it must carry the staged input
        # with the previous source refs into a newly persisted attempt.
        current['processing_configuration'] = current['processing_attempts'][-1]['processing_configuration']
        attempt,_ = reserve(current,command_id='resume-staged',actor_id=actor,
            revision=console.objects_revision(sid),clock=now(),kind='resume')
        attempt['processing_configuration'] = current['processing_configuration']
        console._commit_prepared_store(envelopes={sid:current},snapshot_id=sid)
    context = build_formation_context(console,envelope=console._envelope(sid),actor_id=actor,
        expected_revision=console.objects_revision(sid),attempt=attempt,deadline=time.monotonic()+60)
    assert context['retained_fragments'] == staged[-1]['fragments']
    # The retained record's contract differs from active A: using A here would
    # raise source_extraction_contract_mismatch and lose recovery context.
    assert context['diagnostic_checkpoint'].staged_extraction == staged[-1]
    assert console.review_source_fragments(sid) is not None
    console._execute_source_attempt(actor_id=actor, snapshot_id=sid, attempt=attempt,
                                    deadline=time.monotonic()+60)
    with console.workflow_document_store._connect() as con:
        active = con.execute('SELECT d.review_source_ref,r.extraction_hash FROM workflow.documents d '
            'JOIN workflow.formation_evidence_roots r ON r.proof_id=d.formation_evidence_id '
            'WHERE d.snapshot_id=%s', (sid,)).fetchone()
    assert active['extraction_hash'] == staged[-1]['record_hash']
    assert active['review_source_ref']['extraction_hash'] == staged[-1]['record_hash']
