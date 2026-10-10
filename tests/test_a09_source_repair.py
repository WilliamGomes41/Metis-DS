"""A09 actual HTTP -> durable repair -> independently reconstructed readback.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale restart rollback
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.deterministic_review_repair_v1 import install_deterministic_review_repair_routes
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.review_closure_v1 import ReviewClosureConsole
from src.knowledge_materialisation_v1 import validate_materialised_candidate
from src.source_bound_fields_v3 import validate_object_fields
from tests.test_recommendation_context_v3 import response_for

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'a09-local-fixture'


def setup_repair(tmp_path, *, text='Gebruik geen zalf. Bespreek de opties.', core='Gebruik geen zalf.', heading=None, factory=None, secondary=None):
    def fresh():
        return factory() if factory else ReviewClosureConsole(root=ROOT, source_store=tmp_path/'sources', runtime=tmp_path/'runtime')
    console = fresh()
    author = console.create_account(username='author', password=PASSWORD, roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password=PASSWORD, roles=('reviewer',))
    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload['input'][1]['content'])
        proposal = ({'objects': [], 'relations': [], 'abstain_reason': 'uncertain'} if data.get('selection_targets')
                    else response_for(payload, core, heading=heading))
        if secondary and not data.get('selection_targets'):
            proposal['objects'].extend(response_for(payload, secondary)['objects'])
        if text.count(core) > 1:
            # Synthetic producer explicitly selects the first occurrence. Repair
            # will select the second by position, never by a text search.
            def occurrence(value):
                if isinstance(value, dict):
                    if 'literal' in value and value.get('block_id'):
                        value['occurrence'] = 0
                    for child in value.values():
                        occurrence(child)
                elif isinstance(value, list):
                    for child in value:
                        occurrence(child)
            occurrence(proposal)
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(proposal)}]}]}
    bind_pre_review_semantic_processing(console, environ={'METIS_PASSAGE_FORMATION_MODE':'semantic-source-bound-v3',
        'METIS_LLM_API_KEY':'fixture', 'METIS_LLM_MODEL':'fixture'}, post_json=provider)
    data = ('<html><body>' + (f'<h2>{heading}</h2>' if heading else '') + f'<p>{text}</p></body></html>').encode()
    sid = console.ingest(actor_id=author['account_id'], filename='fixture.html', data=data, content_type='text/html',
        ingest_kind='new', title='A09 fixture', version='1.0', date='2026-10-10', live_url='', class_='richtlijn',
        family='fixture', named_reviewers=[reviewer['account_id']])['snapshot_id']
    obj = next(o for o in console.snapshot_objects(sid) if o['content']['clean_text'] == core)
    return console, sid, obj, reviewer, fresh


def client(console):
    app = create_console_app(console)
    install_deterministic_review_repair_routes(app, console)
    c = TestClient(app, base_url='https://testserver', raise_server_exceptions=False)
    c.post('/login', data={'username':'reviewer', 'password':PASSWORD})
    return c


def repair(console, sid, obj, units, *, revision=None):
    with client(console) as c:
        return c.post('/review/resolve', data={'snapshot_id':sid, 'object_id':obj['object_id'],
            'snapshot_revision':revision or console.objects_revision(sid), 'suitability':'mist_context',
            'comment':'Selecteer exacte bronzinnen.', 'repair_kind':'source_units',
            'source_unit_ids':[u['unit_id'] for u in units]}, follow_redirects=False)


@pytest.mark.parametrize('count', [1, 2])
def test_http_source_selection_has_complete_revision_after_restart(tmp_path, count):
    console, sid, obj, reviewer, fresh = setup_repair(tmp_path)
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    old = deepcopy(console._load_objects(sid, remember=False))
    response = repair(console, sid, obj, units[:count])
    assert response.status_code == 303
    live = fresh()._current_object(sid, obj['object_id'])
    fragments = fresh().review_source_fragments(sid)
    validate_materialised_candidate(live, fragments=fragments)
    validate_object_fields(live, fragments)
    assert live['metadata']['admission']['gate_result'] == ('allowed' if count == 1 else 'blocked')
    assert 'source_bound_fields_stale' not in live['metadata']['admission']['reason_codes']
    history = fresh()._load_objects(sid, remember=False)
    for prior in old:
        stored = next(o for o in history if (o['object_id'], o['object_version']) == (prior['object_id'], prior['object_version']))
        assert stored['content'] == prior['content']
        assert stored['provenance']['canonical_object_hash'] == prior['provenance']['canonical_object_hash']


@pytest.fixture(params=['file', 'postgres'])
def repair_setup(request, tmp_path):
    """Same HTTP probes on file compatibility and production PostgreSQL mixins."""
    factory = None
    if request.param == 'postgres':
        from tests.decision_graph_native_support import native_state
        state, _canonical, _source = native_state(tmp_path)
        counter = iter(range(100))
        factory = lambda: state(f'a09-{next(counter)}')
    return lambda **kwargs: setup_repair(tmp_path, factory=factory, **kwargs)


def assert_complete(console, sid, oid):
    from src.integrity_kernel import compute_canonical_object_hash
    from src.source_bound_fields_v2 import validated_context
    obj = console._current_object(sid, oid)
    fragments = console.review_source_fragments(sid)
    validate_materialised_candidate(obj, fragments=fragments)
    validate_object_fields(obj, fragments)
    validated_context(obj, fragments, obj['source']['source_checksum'])
    assert obj['provenance']['canonical_object_hash'] == compute_canonical_object_hash(obj)
    assert 'source_bound_fields_stale' not in obj['metadata']['admission']['reason_codes']
    assert obj['metadata']['revision_lineage']['previous_object_version'] == obj['provenance']['previous_object_version']
    return obj


def test_expand_shorten_context_restart_and_stale_replay(repair_setup):
    console, sid, obj, reviewer, fresh = repair_setup(heading='Bij een natte plek:')
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    assert repair(console, sid, obj, units[:1]).status_code == 303
    same = assert_complete(fresh(), sid, obj['object_id'])
    assert same['metadata']['admission']['gate_result'] == 'allowed'
    assert same['metadata']['source_bound_context']['target_object_version_at_binding'] == same['object_version']
    assert same['metadata']['source_bound_context']['entries'][0]['text'] == 'Bij een natte plek:'
    stale = console.objects_revision(sid)
    assert repair(console, sid, same, units).status_code == 303
    expanded = assert_complete(fresh(), sid, obj['object_id'])
    assert expanded['metadata']['admission']['gate_result'] == 'blocked'
    assert expanded['metadata']['source_bound_context']['entries'][0]['unresolved_reason'] == 'relation_uncertain'
    before = deepcopy(fresh()._load_objects(sid, remember=False))
    conflict = repair(fresh(), sid, expanded, units, revision=stale)
    assert conflict.status_code == 400
    assert 'tussentijds gewijzigd' in conflict.text
    assert fresh()._load_objects(sid, remember=False) == before
    assert repair(fresh(), sid, expanded, units[:1]).status_code == 303
    shortened = assert_complete(fresh(), sid, obj['object_id'])
    assert shortened['content']['clean_text'] == 'Gebruik geen zalf.'
    # Returning to old text does not resurrect historical semantic authority.
    assert shortened['metadata']['admission']['gate_result'] == 'blocked'


def test_repeated_text_selects_second_position_without_inheriting_meaning(repair_setup):
    console, sid, obj, reviewer, fresh = repair_setup(text='Gebruik geen zalf. Gebruik geen zalf.')
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    assert len(units) == 2
    assert repair(console, sid, obj, units[1:]).status_code == 303
    live = assert_complete(fresh(), sid, obj['object_id'])
    span = live['metadata']['semantic_passage']['spans'][0]
    assert span['start'] == len('Gebruik geen zalf. ')
    assert span['start'] != obj['metadata']['semantic_passage']['spans'][0]['start']
    assert live['metadata']['admission']['gate_result'] == 'blocked'
    assert all(e['span'] is None and e['missing_reason'] == 'uncertain'
               for e in live['metadata']['source_bound_fields']['evidence'].values())


def test_old_approval_is_retained_and_invalidated(repair_setup):
    from src.review_ledger import read_events
    console, sid, obj, reviewer, fresh = repair_setup()
    console.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=obj['object_id'],
        decision='approve', confirmed_object_type='recommendation', recommendation_direction='against',
        recommendation_strength_level='not_stated', comment='Bron gecontroleerd.')
    bindings = deepcopy(console.object_review_bindings(sid))
    assert any(b['valid'] for b in bindings)
    events = read_events(console._ledger_path)
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    assert repair(console, sid, obj, units).status_code == 303
    restarted = fresh()
    assert not any(b['valid'] for b in restarted.object_review_bindings(sid))
    assert len(restarted.object_review_bindings(sid)) == len(bindings)
    assert read_events(restarted._ledger_path)[:len(events)] == events
    assert_complete(restarted, sid, obj['object_id'])


def test_overlapping_http_corrections_have_one_winner(repair_setup):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from src.review_ledger import read_events
    console, sid, obj, reviewer, fresh = repair_setup()
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    revision = console.objects_revision(sid)
    states = [fresh(), fresh()]
    barrier = Barrier(2)
    def send(index):
        with client(states[index]) as c:
            barrier.wait(timeout=10)
            return c.post('/review/resolve', data={'snapshot_id':sid, 'object_id':obj['object_id'],
                'snapshot_revision':revision, 'suitability':'mist_context', 'comment':'Concurrente selectie.',
                'repair_kind':'source_units', 'source_unit_ids':[u['unit_id'] for u in units[:index+1]]},
                follow_redirects=False).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(send, [0, 1]))
    assert sorted(outcomes) == [303, 400]
    restarted = fresh()
    assert_complete(restarted, sid, obj['object_id'])
    corrections = [e for e in read_events(restarted._ledger_path) if e['event_type']=='quality_object_corrected']
    assert len(corrections) == 1


def test_failed_http_commit_rolls_back_objects_bindings_and_audit(repair_setup, monkeypatch):
    from src.review_ledger import read_events
    console, sid, obj, reviewer, fresh = repair_setup()
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    before_objects = deepcopy(console._load_objects(sid, remember=False))
    before_bindings = deepcopy(console.object_review_bindings(sid))
    before_envelope = deepcopy(console._envelope(sid))
    before_events = read_events(console._ledger_path)
    if hasattr(console, 'workflow_review_store'):
        # Native deferred trigger: fail at outer COMMIT after writes/audit were attempted.
        store = console.workflow_review_store
        with store._connect() as con:
            con.execute("""CREATE FUNCTION workflow.a09_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.event_type = 'quality_object_corrected' THEN
              RAISE EXCEPTION 'a09_injected_commit_failure'; END IF; RETURN NEW; END $$""")
            con.execute("""CREATE CONSTRAINT TRIGGER a09_fail_commit AFTER INSERT ON workflow.review_events
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.a09_fail_commit()""")
    else:
        commit = console._commit_prepared_store
        def fail(**kwargs):
            commit(**kwargs)
            if kwargs.get('ledger_fn'):
                raise RuntimeError('a09_injected_commit_failure')
        monkeypatch.setattr(console, '_commit_prepared_store', fail)
    try:
        response = repair(console, sid, obj, units)
        assert response.status_code >= 400
    finally:
        if hasattr(console, 'workflow_review_store'):
            with console.workflow_review_store._connect() as con:
                con.execute('DROP TRIGGER a09_fail_commit ON workflow.review_events')
                con.execute('DROP FUNCTION workflow.a09_fail_commit()')
    restarted = fresh()
    assert restarted._load_objects(sid, remember=False) == before_objects
    assert restarted.object_review_bindings(sid) == before_bindings
    assert restarted._envelope(sid) == before_envelope
    assert read_events(restarted._ledger_path) == before_events


def test_direct_kernel_rejects_partial_materialisation_before_storage(repair_setup):
    from src.operations_console_v1 import OperationsConsole, ConsoleError
    from src.review_ledger import read_events
    console, sid, obj, reviewer, fresh = repair_setup()
    console.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=obj['object_id'],
                         decision='revise', comment='Correctie nodig.')
    before = deepcopy(console._load_objects(sid, remember=False))
    events = read_events(console._ledger_path)
    patch = {'reason':'Expliciete correctie', 'operations':[{'op':'set', 'path':'content.clean_text',
                              'value':'Gebruik geen zalf. Bespreek de opties.'}]}
    with pytest.raises(ConsoleError, match='materialisation_text_mismatch'):
        OperationsConsole.correct_object(console, actor_id=reviewer['account_id'], snapshot_id=sid,
            object_id=obj['object_id'], patch=patch, expected_revision=console.objects_revision(sid))
    assert fresh()._load_objects(sid, remember=False) == before
    assert read_events(fresh()._ledger_path) == events


def test_new_process_restart_reconstructs_committed_revision(repair_setup):
    import os
    import subprocess
    import sys
    console, sid, obj, reviewer, fresh = repair_setup()
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    assert repair(console, sid, obj, units).status_code == 303
    native = hasattr(console, 'workflow_review_store')
    code = r'''
import json, sys
from pathlib import Path
from src.review_closure_v1 import ReviewClosureConsole
from tests.test_a09_source_repair import assert_complete
root, sources, runtime, sid, oid, native = sys.argv[1:]
kwargs = dict(root=Path(root), source_store=Path(sources), runtime=Path(runtime))
if native == '1':
    import os
    from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig, PostgresCanonicalPublicationStore
    from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
    from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
    from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
    from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
    from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowDurablePublicationConsole
    from src.workflows.workflow_transaction_v1 import bind_workflow_stores
    config = PostgresCanonicalConfig(dsn=os.environ['METIS_TEST_POSTGRES_DSN'])
    identity = CutoverPostgresWorkflowIdentityStore(config)
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    remaining = PostgresWorkflowRemainingStore(config)
    bind_workflow_stores(identity, documents, reviews, remaining)
    console = FastBadgePostgresCompleteWorkflowDurablePublicationConsole(**kwargs,
        canonical_publication_store=PostgresCanonicalPublicationStore(config),
        workflow_identity_store=identity, workflow_document_store=documents,
        workflow_review_store=reviews, workflow_remaining_store=remaining)
else:
    console = ReviewClosureConsole(**kwargs)
print(json.dumps(assert_complete(console, sid, oid)))
'''
    runtime = console.runtime.parent/'process-restart' if native else console.runtime
    result = subprocess.run([sys.executable, '-c', code, str(console.root), str(console.source_store), str(runtime),
                             sid, obj['object_id'], '1' if native else '0'], cwd=ROOT,
                            capture_output=True, text=True, timeout=30, env=os.environ.copy())
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == assert_complete(fresh(), sid, obj['object_id'])


def test_source_identity_rechecked_at_actual_commit(repair_setup, monkeypatch):
    from src.operations_console_v1 import OperationsConsole, ConsoleError
    from src.source_bound_fields_v2 import rebind_revision_evidence
    from src.review_ledger import read_events
    console, sid, obj, reviewer, fresh = repair_setup()
    # The supported direct kernel entrance has preparation outside the lock.
    console.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=obj['object_id'],
                         decision='revise', comment='Correctie nodig.')
    before = deepcopy(console._load_objects(sid, remember=False))
    before_events = read_events(console._ledger_path)
    def corrupt_source(previous, revised, *, fragments):
        rebind_revision_evidence(previous, revised, fragments=fragments)
        path = Path(console._envelope(sid)['binary_path'])
        path.write_bytes(b'changed source bytes')
        if console.immutable_source_store is not None:
            locator = console._envelope(sid)['immutable_storage_locator']
            console.immutable_source_store.blobs[locator] = b'changed source bytes'
    monkeypatch.setattr('src.source_bound_fields_v2.rebind_revision_evidence', corrupt_source)
    with pytest.raises(ConsoleError, match='freeze_bytes_missing|immutable_source_recovery_failed'):
        OperationsConsole.correct_object(console, actor_id=reviewer['account_id'], snapshot_id=sid,
            object_id=obj['object_id'], expected_revision=console.objects_revision(sid),
            patch={'reason':'Zelfde selectie', 'operations':[{'op':'set','path':'content.clean_text','value':obj['content']['clean_text']}]})
    assert fresh()._load_objects(sid, remember=False) == before
    assert read_events(fresh()._ledger_path) == before_events



def test_authorization_revoked_during_preparation_cannot_commit(repair_setup, monkeypatch):
    from src.operations_console_v1 import OperationsConsole, ConsoleError
    from src.source_bound_fields_v2 import rebind_revision_evidence
    from src.review_ledger import read_events
    console, sid, obj, reviewer, fresh = repair_setup()
    publisher = console.create_account(username='publisher', password=PASSWORD, roles=('publisher',))
    console.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=obj['object_id'],
                         decision='revise', comment='Correctie nodig.')
    before = deepcopy(console._load_objects(sid, remember=False))
    before_events = read_events(console._ledger_path)
    def revoke(previous, revised, *, fragments):
        rebind_revision_evidence(previous, revised, fragments=fragments)
        fresh().assign_roles(actor_id=publisher['account_id'], account_id=reviewer['account_id'], roles=[])
    monkeypatch.setattr('src.source_bound_fields_v2.rebind_revision_evidence', revoke)
    with pytest.raises(ConsoleError, match='correction_role_required'):
        OperationsConsole.correct_object(console, actor_id=reviewer['account_id'], snapshot_id=sid,
            object_id=obj['object_id'], expected_revision=console.objects_revision(sid),
            patch={'reason':'Zelfde selectie', 'operations':[{'op':'set','path':'content.clean_text','value':obj['content']['clean_text']}]})
    assert fresh()._load_objects(sid, remember=False) == before
    assert read_events(fresh()._ledger_path) == before_events



@pytest.mark.parametrize('later_primary', [False, True])
def test_http_merge_reconstructs_shared_block_in_source_order(repair_setup, later_primary):
    console, sid, obj, reviewer, fresh = repair_setup(secondary='Bespreek de opties.')
    other = next(o for o in console.snapshot_objects(sid) if o['content']['clean_text']=='Bespreek de opties.')
    primary, absorbed = (other, obj) if later_primary else (obj, other)
    with client(console) as c:
        response = c.post('/review/resolve', data={'snapshot_id':sid, 'object_id':primary['object_id'],
            'snapshot_revision':console.objects_revision(sid), 'suitability':'samenvoegen',
            'comment':'Samenvoegen in bronvolgorde.', 'repair_kind':'merge_objects',
            'merge_object_ids':[absorbed['object_id']]}, follow_redirects=False)
    assert response.status_code == 303
    restarted = fresh()
    live = assert_complete(restarted, sid, primary['object_id'])
    assert live['content']['clean_text'] == 'Gebruik geen zalf. Bespreek de opties.'
    assert live['metadata']['admission']['gate_result'] == 'blocked'
    assert restarted._current_object(sid, absorbed['object_id'])['governance']['validation_status'] == 'superseded'



@pytest.mark.parametrize('entrance', ['kernel', 'closure'])
def test_direct_correction_cannot_save_inconsistent_raw_text(repair_setup, entrance):
    from src.operations_console_v1 import OperationsConsole, ConsoleError
    console, sid, obj, reviewer, fresh = repair_setup()
    console.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=obj['object_id'],
                         decision='revise', comment='Correctie nodig.')
    before = deepcopy(console._load_objects(sid, remember=False))
    kwargs = dict(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=obj['object_id'],
                  expected_revision=console.objects_revision(sid),
                  patch={'reason':'Raw text correction', 'operations':[{'op':'set','path':'content.raw_text','value':'Invented text'}]})
    with pytest.raises(ConsoleError, match='materialisation_raw_text_mismatch'):
        if entrance == 'kernel':
            OperationsConsole.correct_object(console, **kwargs)
        else:
            console.correct_object(**kwargs)
    assert fresh()._load_objects(sid, remember=False) == before


def test_nonadjacent_units_do_not_silently_include_the_gap(repair_setup):
    console, sid, obj, reviewer, fresh = repair_setup(text='Gebruik geen zalf. Bespreek de opties. Controleer de huid.')
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    before = deepcopy(console._load_objects(sid, remember=False))
    response = repair(console, sid, obj, [units[0], units[2]])
    assert response.status_code == 400
    assert 'repair_source_units_must_be_contiguous' in response.text
    assert fresh()._load_objects(sid, remember=False) == before
