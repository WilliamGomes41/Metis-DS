"""Literal context commands across HTTP, durable objects and closure.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.review_closure_v1 import ReviewClosureConsole
from src.review_ledger import read_events
from src.source_context_review_v1 import context_issues, projection, EVENT, LINKS_KEY
from src.processing_diagnostics_v1 import passage_export_rows
from src.publication_readiness_v1 import source_passage_closure
from src.processing_evidence_export_v1 import processing_evidence_tables
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing, PASSAGE_FORMATION_MODE_ENV, SEMANTIC_MODE
from tests.test_workflow_chain_recovery_v1 import recovery_postgres  # noqa: F401


def _bind_semantic_fixture(state):
    # A provider double is only a plumbing fixture, never model acceptance.
    def provider_fixture(url, headers, payload, timeout):
        blocks = json.loads(payload['input'][1]['content'])['source_blocks']
        block = next(row for row in blocks if 'systematische waarneming' in row['text'])
        proposal = {'objects': [{'spans': [{'block_id': block['block_id'], 'start': 0, 'end': len(block['text'])}],
                                'proposed_object_type': 'definition', 'recommendation_semantics': None}],
                    'relations': [], 'abstain_reason': None}
        return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(proposal)}]}]}
    bind_pre_review_semantic_processing(state,
        environ={PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE, 'METIS_LLM_API_KEY': 'fixture', 'METIS_LLM_MODEL': 'fixture'},
        post_json=provider_fixture)


def _system(tmp_path, console=None):
    state = console or ReviewClosureConsole(root=tmp_path, source_store=tmp_path / 'sources', runtime=tmp_path / 'runtime')
    researcher = state.create_account(username='anne', password='anne-secret', roles=('researcher',))
    reviewer = state.create_account(username='bert', password='bert-secret', roles=('reviewer',))
    _bind_semantic_fixture(state)
    receipt = state.ingest(actor_id=researcher['account_id'], filename='labels.html', content_type='text/html',
        data=b'<html><body><h1>Zorg</h1><h2>1 Ondersteuning</h2><p>DOEN</p><p>De verpleegkundige bespreekt passende ondersteuning met de client.</p><p>Een observatie is een systematische waarneming van gedrag.</p></body></html>',
        ingest_kind='new', title='Zorg', version='1.0', date='2026-09-11', live_url='',
        class_='richtlijn', family='zorg', named_reviewers=[reviewer['account_id']])
    sid = receipt['snapshot_id']
    current = state.snapshot_objects(sid)
    source = next(row for row in current if (row.get('content') or {}).get('clean_text') == 'DOEN')
    target = next(row for row in current if 'systematische waarneming' in str((row.get('content') or {}).get('clean_text')))
    command = dict(actor_id=reviewer['account_id'], snapshot_id=sid, source_object_id=source['object_id'],
                   role='label', target_object_ids=[target['object_id']], reason='Het bronlabel hoort bij deze passage.',
                   command_id='context-test-1', expected_revision=state.objects_revision(sid))
    return state, researcher, reviewer, source, target, command


def test_context_retains_exact_source_restarts_and_invalidates_changed_text(tmp_path):
    state, _, _, source, target, command = _system(tmp_path)
    before = deepcopy(state.snapshot_objects(command['snapshot_id']))
    result = state.confirm_source_context(**command)
    assert result['role'] == 'label'
    rows = state.snapshot_objects(command['snapshot_id'])
    label = next(row for row in rows if row['object_id'] == source['object_id'])
    linked = next(row for row in rows if row['object_id'] == target['object_id'])
    assert label['content'] == source['content']
    assert linked['content'] == target['content']
    assert linked['governance']['validation_status'] == 'needs_review'
    assert not context_issues(rows)
    assert projection(label, rows)['target_object_ids'] == [target['object_id']]
    export = next(row for row in passage_export_rows(rows) if row['object_id'] == target['object_id'])
    assert export['source_context_review']['links'][0]['text'] == 'DOEN'
    tables, _ = processing_evidence_tables(snapshot_id=command['snapshot_id'], revision=state.objects_revision(command['snapshot_id']),
        envelope=state._envelope(command['snapshot_id']), objects=rows)
    context_export = next(row for row in tables['context_evidence']
                          if row['object_id'] == target['object_id'] and row.get('source_context_review'))
    assert context_export['source_context_review'] == export['source_context_review']
    assert not linked.get('confirmed_recommendation_strength')
    restarted = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / 'sources', runtime=tmp_path / 'runtime')
    assert restarted.snapshot_objects(command['snapshot_id']) == rows
    assert restarted.confirm_source_context(**command)['idempotent'] is True
    assert len([event for event in read_events(state._ledger_path) if event['event_type'] == EVENT]) == 1
    old_versions = state._load_objects(command['snapshot_id'], remember=False)
    assert all(row in old_versions for row in before)
    modified = deepcopy(rows)
    changed_target = next(row for row in modified if row['object_id'] == target['object_id'])
    changed_target['content']['clean_text'] += ' Andere betekenis.'
    assert target['object_id'] in context_issues(modified)
    assert target['object_id'] in source_passage_closure(modified)['unresolved_source_passage_ids']


def test_context_failure_stale_id_reuse_and_published_work_do_not_mutate(tmp_path, monkeypatch):
    state, researcher, _, source, _, command = _system(tmp_path)
    sid = command['snapshot_id']
    before = deepcopy(state.snapshot_objects(sid))
    events = read_events(state._ledger_path)
    with pytest.raises(ConsoleError):
        state.confirm_source_context(**{**command, 'actor_id': researcher['account_id']})
    with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
        state.confirm_source_context(**{**command, 'expected_revision': 'stale'})
    original = state._commit_prepared_store
    monkeypatch.setattr(state, '_commit_prepared_store', lambda **kwargs: (_ for _ in ()).throw(RuntimeError('forced commit failure')))
    with pytest.raises(RuntimeError):
        state.confirm_source_context(**command)
    monkeypatch.setattr(state, '_commit_prepared_store', original)
    assert state.snapshot_objects(sid) == before
    assert read_events(state._ledger_path) == events
    state.confirm_source_context(**command)
    with pytest.raises(ConsoleError, match='source_context_command_conflict'):
        state.confirm_source_context(**{**command, 'reason': 'Andere command met hetzelfde ID.'})
    monkeypatch.setattr(state, 'snapshot_is_published', lambda sid: True)
    with pytest.raises(ConsoleError, match='published_working_revision_immutable'):
        state.confirm_source_context(**command)


def test_context_http_projection_and_command(tmp_path):
    state, _, reviewer, source, target, command = _system(tmp_path)
    client = TestClient(create_console_app(state))
    assert client.post('/login', data={'username': reviewer['username'], 'password': 'bert-secret'}, follow_redirects=False).status_code == 303
    before = client.get('/review', params={'document': command['snapshot_id'], 'object': source['object_id']})
    assert 'Bronrol en contextkoppeling' in before.text
    result = client.post('/review/source-context', data={'snapshot_id': command['snapshot_id'],
        'source_object_id': source['object_id'], 'role': 'label', 'target_object_ids': [target['object_id']],
        'reason': command['reason'], 'command_id': command['command_id'], 'snapshot_revision': command['expected_revision'],
        'source_checked': '1'}, follow_redirects=False)
    assert result.status_code == 303, result.text
    after = client.get('/review', params={'document': command['snapshot_id'], 'object': target['object_id']})
    assert 'Bevestigde broncontext' in after.text
    assert 'DOEN' in after.text
    assert 'Dit bevestigt geen aanbevelingssterkte' in after.text
    label_page = client.get('/review', params={'document': command['snapshot_id'], 'object': source['object_id']})
    assert 'data-source-role-card' in label_page.text


def test_replacing_context_reopens_approval_and_preserves_unmodified_review_type(tmp_path):
    state, _, reviewer, source, target, command = _system(tmp_path)
    sid = command['snapshot_id']
    state.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=target['object_id'],
                        decision='approve', confirmed_object_type='definition', relation_review_ack=True)
    assert any(row.get('valid') for row in state.object_review_bindings(sid) if row['object_id'] == target['object_id'])
    command['expected_revision'] = state.objects_revision(sid)
    state.confirm_source_context(**command)
    assert not any(row.get('valid') for row in state.object_review_bindings(sid) if row['object_id'] == target['object_id'])
    state.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=target['object_id'],
                        decision='approve', confirmed_object_type='definition', relation_review_ack=True)
    assert not context_issues(state.snapshot_objects(sid))
    state.confirm_source_context(**{**command, 'command_id': 'context-test-2', 'expected_revision': state.objects_revision(sid),
                                   'role': 'excluded', 'target_object_ids': [], 'reason': 'Het label hoort niet bij deze passage.'})
    linked = next(row for row in state.snapshot_objects(sid) if row['object_id'] == target['object_id'])
    assert LINKS_KEY not in linked['metadata']
    assert linked['confirmed_object_type'] == 'definition'
    assert linked['governance']['validation_status'] == 'needs_review'


def test_native_context_commit_failure_restart_csv_mcp_and_stale_worker(recovery_postgres, tmp_path):
    import psycopg
    from tests.test_lifecycle_withdrawal_recovery_v1 import _console
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore
    from src.metis_mcp_queries_v1 import McpQueries

    source_store = FakeBlobStore()
    root = tmp_path / 'native'
    root.mkdir()
    state = _console(root, recovery_postgres, source_store)
    state, _, reviewer, source, target, command = _system(root, state)
    sid = command['snapshot_id']
    before = deepcopy(state.snapshot_objects(sid))
    with psycopg.connect(recovery_postgres.dsn) as connection:
        connection.execute("""CREATE FUNCTION workflow.fail_context_commit_test() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'context_commit_failure'; END; $$""")
        connection.execute("""CREATE CONSTRAINT TRIGGER fail_context_commit_test
            AFTER INSERT ON workflow.document_objects DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION workflow.fail_context_commit_test()""")
    try:
        with pytest.raises(Exception, match='context_commit_failure'):
            state.confirm_source_context(**command)
        assert state.snapshot_objects(sid) == before
        assert not [e for e in read_events(state._ledger_path) if e['event_type'] == EVENT]
    finally:
        with psycopg.connect(recovery_postgres.dsn) as connection:
            connection.execute('DROP TRIGGER fail_context_commit_test ON workflow.document_objects')
            connection.execute('DROP FUNCTION workflow.fail_context_commit_test()')
    other_root = tmp_path / 'second-worker'
    other_root.mkdir()
    other = _console(other_root, recovery_postgres, source_store)
    state.confirm_source_context(**command)
    committed = deepcopy(state.snapshot_objects(sid))
    with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
        other.confirm_source_context(**{**command, 'command_id': 'stale-worker'})
    assert state.snapshot_objects(sid) == committed
    fresh_root = tmp_path / 'restart'
    fresh_root.mkdir()
    fresh = _console(fresh_root, recovery_postgres, source_store)
    assert fresh.snapshot_objects(sid) == committed
    assert fresh.confirm_source_context(**command)['idempotent'] is True
    export = passage_export_rows(fresh.snapshot_objects(sid))
    assert next(r for r in export if r['object_id'] == target['object_id'])['source_context_review']['links'][0]['text'] == 'DOEN'
    mcp = McpQueries(fresh, 'https://testserver')
    payload = mcp.read(reviewer, 'get_passages', {'snapshot_id': sid, 'object_id': target['object_id']})
    assert 'DOEN' in json.dumps(payload)


def _close_context_review(state, reviewer, sid, target_id):
    from src.passage_register_v1 import definitive_review_disposition
    from src.operations_console_v1 import review_lane
    state.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=target_id,
                        decision='approve', confirmed_object_type='definition', relation_review_ack=True)
    for obj in state.snapshot_objects(sid):
        if obj['object_id'] == target_id or obj.get('object_type') == 'document' or review_lane(obj) == 'fast':
            continue
        if not definitive_review_disposition(obj)['final']:
            state.review_object(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=obj['object_id'],
                                decision='reject', suitability='ja', eindoordeel='afwijzen',
                                comment='Testfixture: geen zelfstandig kennisobject.')


def test_native_context_publication_successor_withdrawal_and_restart(recovery_postgres, tmp_path):
    from tests.test_lifecycle_withdrawal_recovery_v1 import _console, _api, _documents
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore
    from tests.test_api_access_lifecycle_v1 import _provision
    from src.api_access_v1 import PostgresApiAccessStore
    from src.retrieval.retrieval_projection_v2 import build_projection

    blobs = FakeBlobStore()
    root = tmp_path / 'full-chain'
    root.mkdir()
    state = _console(root, recovery_postgres, blobs)
    state, researcher, reviewer, source, target, command = _system(root, state)
    publisher = state.create_account(username='carla', password='carla-secret', roles=('publisher',))
    sid = command['snapshot_id']
    state.confirm_source_context(**command)
    restart_root = tmp_path / 'review-restart'
    restart_root.mkdir()
    state = _console(restart_root, recovery_postgres, blobs)
    _bind_semantic_fixture(state)
    _close_context_review(state, reviewer, sid, target['object_id'])
    client = TestClient(create_console_app(state))
    assert client.post('/login', data={'username': 'carla', 'password': 'carla-secret'}, follow_redirects=False).status_code == 303
    assert client.post('/publish', data={'snapshot_id': sid, 'publish_confirmed': 'yes'}, follow_redirects=False).status_code == 303
    r1 = state.canonical_publication_store.release_for_snapshot(sid)
    assert r1 is not None
    old_objects = deepcopy(state.snapshot_objects(sid))
    canonical = deepcopy(state.canonical_publication_store.active_publication_rows())
    records, blocked = build_projection(canonical)
    assert not blocked, blocked
    record = next(row for row in records if row['metadata']['object_id'] == target['object_id'])
    assert 'Bronlabel: DOEN' in record['retrieval_text']
    assert record['metadata'][LINKS_KEY][0]['text'] == 'DOEN'
    with pytest.raises(ConsoleError, match='published_working_revision_immutable'):
        state.confirm_source_context(**command)
    state.migrate_legacy_revise_to_review()
    assert state.snapshot_objects(sid) == old_objects

    # A new source version gets fresh objects and no inherited label decision.
    data = b'<html><body><h1>Zorg</h1><h2>1 Ondersteuning</h2><p>DOEN</p><p>Een observatie is een systematische waarneming van gedrag. Nieuwe versie.</p></body></html>'
    v2 = state.ingest(actor_id=researcher['account_id'], filename='labels-v2.html', content_type='text/html',
        data=data, ingest_kind='new_version', replaces_snapshot_id=sid, title='Zorg', version='2.0', date='2026-09-12',
        live_url='', class_='richtlijn', family='zorg', named_reviewers=[reviewer['account_id']])
    sid2 = v2['snapshot_id']
    assert state._envelope(sid2)['logical_document_id'] == r1['logical_document_id']
    rows = state.snapshot_objects(sid2)
    assert not any(row.get('metadata', {}).get(LINKS_KEY) for row in rows)
    assert state.canonical_publication_store.active_publication_rows() == canonical
    label2 = next(row for row in rows if row.get('content', {}).get('clean_text') == 'DOEN')
    target2 = next(row for row in rows if 'systematische waarneming' in row.get('content', {}).get('clean_text', ''))
    state.confirm_source_context(**{**command, 'snapshot_id': sid2, 'source_object_id': label2['object_id'],
        'target_object_ids': [target2['object_id']], 'command_id': 'v2-label', 'expected_revision': state.objects_revision(sid2)})
    _close_context_review(state, reviewer, sid2, target2['object_id'])
    assert client.post('/publish', data={'snapshot_id': sid2, 'publish_confirmed': 'yes'}, follow_redirects=False).status_code == 303
    r2 = state.canonical_publication_store.release_for_snapshot(sid2)
    assert state.snapshot_objects(sid) == old_objects
    assert state.document_release_serving_status(sid)['serving_status'] == 'inactive'
    assert state.document_release_serving_status(sid2)['serving_status'] == 'active'
    assert {row['publication']['release_id'] for row in state.canonical_publication_store.active_publication_rows()} == {r2['release_id']}

    consumer = _provision(PostgresApiAccessStore(recovery_postgres), name='Context',
        tenant_docs=(target['document_id'], target2['document_id']), app_docs=(target['document_id'], target2['document_id']))
    api = _api(tmp_path / 'product-api', recovery_postgres, blobs)
    assert _documents(api, consumer) == (200, [target2['document_id']])
    response = api.get('/v1/knowledge/' + target2['object_id'], headers={'Authorization': f'Bearer {consumer.credential}'})
    assert response.status_code == 200, response.text
    assert 'Bronlabel: DOEN' in response.json()['content']
    result = state.withdraw_document(actor_id=publisher['account_id'], snapshot_id=sid2,
        expected_release_id=r2['release_id'], reason='Expliciete intrekking in lifecycleproef.')
    assert result['status'] == 'PASS'
    fresh_root = tmp_path / 'withdrawal-restart'
    fresh_root.mkdir()
    fresh = _console(fresh_root, recovery_postgres, blobs)
    assert not fresh.canonical_publication_store.active_publication_rows()
    assert fresh.snapshot_objects(sid) == old_objects
    assert fresh.canonical_publication_store.release_for_snapshot(sid2)['release_status'] == 'withdrawn'
    assert _documents(_api(tmp_path / 'api-restarted', recovery_postgres, blobs), consumer) == (200, [])


def test_native_context_and_publication_serialize_before_authority_read(recovery_postgres, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event
    from tests.test_lifecycle_withdrawal_recovery_v1 import _console
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore

    blobs = FakeBlobStore()
    root = tmp_path / 'context-worker'
    root.mkdir()
    state, _, reviewer, _, target, command = _system(root, _console(root, recovery_postgres, blobs))
    publisher = state.create_account(username='carla', password='carla-secret', roles=('publisher',))
    sid = command['snapshot_id']
    _close_context_review(state, reviewer, sid, target['object_id'])
    command['expected_revision'] = state.objects_revision(sid)
    peer_root = tmp_path / 'publisher-worker'
    peer_root.mkdir()
    peer = _console(peer_root, recovery_postgres, blobs)
    committed, proceed = Event(), Event()
    original = state._commit_prepared_store

    def hold_context(**kwargs):
        result = original(**kwargs)
        committed.set()
        assert proceed.wait(15), 'Context test barrier timed out'
        return result

    with monkeypatch.context() as patch, ThreadPoolExecutor(max_workers=2) as executor:
        patch.setattr(state, '_commit_prepared_store', hold_context)
        context = executor.submit(state.confirm_source_context, **command)
        assert committed.wait(15)
        publication = executor.submit(peer.publish, actor_id=publisher['account_id'], snapshot_id=sid)
        try:
            with pytest.raises(TimeoutError):
                publication.result(timeout=0.25)
        finally:
            proceed.set()
        context.result(timeout=15)
        assert publication.result(timeout=15)['status'] == 'BLOCKED'
    assert not state.canonical_publication_store.active_publication_rows()
    _close_context_review(state, reviewer, sid, target['object_id'])
    command2 = {**command, 'command_id': 'context-after-publication', 'expected_revision': state.objects_revision(sid)}
    publishing, finish = Event(), Event()
    original_publish = peer._publish_locked

    def hold_publication(**kwargs):
        publishing.set()
        assert finish.wait(15), 'Publication test barrier timed out'
        return original_publish(**kwargs)

    with monkeypatch.context() as patch, ThreadPoolExecutor(max_workers=2) as executor:
        patch.setattr(peer, '_publish_locked', hold_publication)
        publication = executor.submit(peer.publish, actor_id=publisher['account_id'], snapshot_id=sid)
        assert publishing.wait(15)
        context = executor.submit(state.confirm_source_context, **command2)
        try:
            with pytest.raises(TimeoutError):
                context.result(timeout=0.25)
        finally:
            finish.set()
        assert publication.result(timeout=15)['status'] == 'PASS'
        with pytest.raises(ConsoleError, match='published_working_revision_immutable'):
            context.result(timeout=15)
    assert state.canonical_publication_store.release_for_snapshot(sid) is not None
