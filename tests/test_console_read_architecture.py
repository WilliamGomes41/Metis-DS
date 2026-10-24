"""Production read costs and ownership.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: releasebewijs
"""
from collections import Counter
from copy import deepcopy
import time
import pytest
from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_insight_v1 import _login


@pytest.mark.parametrize("evidence_records", [4000, 40000])
def test_insight_overview_never_loads_full_documents_or_objects(tmp_path, production_console, production_app, monkeypatch, evidence_records):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    env = store.get_envelope(sid)
    env.setdefault('semantic_replay', {}).setdefault('provider_evidence', {})['large_fixture'] = [
        {'index': i, 'spans': [{'start': i, 'end': i+20}], 'text': 'synthetic evidence'} for i in range(evidence_records)]
    store.write_bundle(envelope=env)
    calls = Counter()
    for name in ('get_envelope', 'list_envelopes', 'list_document_objects'):
        original = getattr(store, name)
        def counted(*args, _original=original, _name=name, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(store, name, counted)
    import src.request_diagnostics_v1 as diagnostics
    metrics = []
    original_metrics = diagnostics.note_request_metrics
    def capture(**values):
        metrics.append(values)
        return original_metrics(**values)
    monkeypatch.setattr(diagnostics, 'note_request_metrics', capture)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    metrics.clear()
    started = time.perf_counter()
    response = client.get('/inzicht/api/documents')
    print('INSIGHT_READ_COST', dict(calls), round(time.perf_counter()-started, 4))
    assert response.status_code == 200
    assert [r['snapshot_id'] for r in response.json()['documents']] == [sid]
    assert sum(calls.values()) == 0, 'Overview fetched full envelope/object payloads'
    assert 0 < metrics[-1]['db_json_bytes'] < 4096, 'Overview fetched large JSON and trimmed it after decoding'


def test_single_read_reuses_without_list_warmup(tmp_path, production_console, monkeypatch):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    calls = []
    original = store.get_envelope
    def counted(sid):
        calls.append(sid)
        return original(sid)
    monkeypatch.setattr(store, 'get_envelope', counted)
    before = deepcopy(console._envelopes)
    with console.document_read_operation():
        a = console._envelope(sid)
        b = console._envelope(sid)
        assert a == b
        changed = original(sid)
        changed['title'] = 'Independent committed title'
        from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
        PostgresConcurrentWorkflowDocumentStore(store.config).write_bundle(envelope=changed)
        assert console._envelope(sid)['title'] == a['title']
    assert len(calls) == 1, 'single reads require list warmup'
    assert console._envelopes == before, 'read refreshed shared command state'
    with console.document_read_operation():
        assert console._envelope(sid)['title'] == 'Independent committed title'


def test_checkpoint_commit_does_not_copy_unrelated_document_payloads(tmp_path, production_console, monkeypatch):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    env = console.workflow_document_store.get_envelope(sid)
    copies = []
    class UnrelatedPayload:
        def __deepcopy__(self, memo):
            copies.append(1)
            return self
    original = console._reload_store_locked
    def reload():
        original()
        console._envelopes['unrelated-document'] = {'snapshot_id': 'unrelated-document', 'evidence': UnrelatedPayload()}
    monkeypatch.setattr(console, '_reload_store_locked', reload)
    console._commit_prepared_store(envelopes={sid: env}, snapshot_id=sid)
    assert copies == [], 'Checkpoint copied payloads belonging to other documents'
    assert console.workflow_document_store.get_envelope(sid) == env


def test_all_main_pages_and_detail_apis_keep_workflow_state(tmp_path, production_console, production_app):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    reviewer = users['reviewer_a']
    console.workflow_identity_store.update_roles(reviewer['account_id'], ['researcher', 'reviewer', 'publisher'])
    client = _login(console, reviewer['username'], production_app=production_app)
    store = console.workflow_document_store
    before = (store.get_envelope(sid), store.list_document_objects(sid), console.workflow_review_store.read_bindings())
    paths = ['/', '/ingest', '/source-selection', '/review', '/publish', '/tree', '/settings', '/inzicht',
             '/inzicht/api/documents', '/inzicht/api/quality', '/telemetry/api/summary', '/raad/meldingen',
             '/inzicht/document?document=' + sid, '/review?document=' + sid + '&task=individual',
             '/publish?document=' + sid, '/source-selection?document=' + sid,
             '/inzicht/document/diagnostiek?document=' + sid,
             '/inzicht/document/passages?document=' + sid]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, (path.split('?')[0], response.status_code)
        assert 'data-console-error' not in response.text
    assert before == (store.get_envelope(sid), store.list_document_objects(sid), console.workflow_review_store.read_bindings())
    assert console._envelope.__func__.__module__ == 'src.workflows.workflow_documents_cutover_v1'
    print('PRODUCTION_MRO', [cls.__name__ for cls in type(console).__mro__])
    print('PAGE_ROUTES_OK', len(paths))


def test_compact_page_routes_do_not_fetch_full_envelopes(tmp_path, production_console, production_app, monkeypatch):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    reviewer = users['reviewer_a']
    console.workflow_identity_store.update_roles(reviewer['account_id'], ['researcher', 'reviewer', 'publisher'])
    client = _login(console, reviewer['username'], production_app=production_app)
    def forbidden(*args, **kwargs):
        raise AssertionError('Compact page fetched a full envelope')
    monkeypatch.setattr(console.workflow_document_store, 'list_envelopes', forbidden)
    monkeypatch.setattr(console.workflow_document_store, 'get_envelope', forbidden)
    for path in ['/ingest', '/tree', '/publish', '/inzicht/api/documents', '/raad/meldingen']:
        assert client.get(path).status_code == 200, path


def test_notices_revocation_and_explicit_unknown_count(tmp_path, production_console, production_app):
    from tests.production_support import restart_production
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    second = restart_production(console)
    reviewer = users['reviewer_a']
    client = _login(console, reviewer['username'], production_app=production_app)
    # A stored processing block must remain visible even with no blocked candidates.
    env = second.workflow_document_store.get_envelope(sid)
    env['processing_blocker'] = 'processing_dependency_failed'
    second.workflow_document_store.write_bundle(envelope=env)
    first = client.get('/raad/meldingen')
    assert first.status_code == 200
    row = next(r for r in first.json()['documents'] if r['snapshot_id'] == sid)
    assert row['processing_blocked'] and row['blocked'] == 0
    env['named_reviewers'] = []
    second.workflow_document_store.write_bundle(envelope=env)
    assert client.get('/raad/meldingen').json()['documents'] == []
    denied = client.get('/inzicht/document', params={'document': sid})
    assert denied.status_code >= 400 and env['title'] not in denied.text
    # Publishers can see existing publication metadata, but do not gain processing access.
    publisher = console.create_account(username='overview.publisher', password='d54-secret', roles=['publisher'])
    notices = _login(console, publisher['username'], production_app=production_app).get('/raad/meldingen').json()
    assert notices['documents'][0]['blocked'] is None


def test_overview_errors_are_not_empty_success(tmp_path, production_console, production_app, monkeypatch):
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    def failed(*args):
        raise WorkflowDocumentStoreError('workflow_document_diagnostics_read_failed')
    monkeypatch.setattr(console.workflow_document_store, 'document_diagnostic_inputs', failed)
    response = client.get('/inzicht/api/documents')
    assert response.status_code >= 400
    assert 'D5.4 fixture' not in response.text


def test_pure_read_transaction_is_repeatable_read_only_and_leaves_no_query(tmp_path, production_console):
    import pytest
    import psycopg
    from src.workflows.workflow_transaction_v1 import workflow_read_transaction
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
    independent = PostgresConcurrentWorkflowDocumentStore(store.config)
    with workflow_read_transaction(store) as con:
        pid = con.info.backend_pid
        assert con.execute('SHOW transaction_isolation').fetchone()['transaction_isolation'] == 'repeatable read'
        assert con.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
        before = store.get_envelope(sid)
        changed = independent.get_envelope(sid)
        changed['title'] = 'Committed while reading'
        independent.write_bundle(envelope=changed)
        assert store.get_envelope(sid) == before
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            con.execute('UPDATE workflow.documents SET title=title')
    with pytest.raises(psycopg.errors.QueryCanceled):
        with workflow_read_transaction(store) as con:
            canceled_pid = con.info.backend_pid
            con.execute("SET LOCAL statement_timeout='50ms'")
            con.execute('SELECT pg_sleep(10)')
    with independent._connect() as con:
        assert not con.execute('SELECT 1 FROM pg_stat_activity WHERE pid=%s AND state=%s', (canceled_pid, 'active')).fetchall()
    assert store.get_envelope(sid)['title'] == 'Committed while reading'


def test_future_sync_and_async_pages_automatically_own_read_operations(tmp_path, production_console, production_app, monkeypatch):
    import asyncio
    from fastapi.testclient import TestClient
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    app = production_app(console)
    @app.get('/test/future-read')
    def future():
        assert console._document_reads() is not None
        first = console._envelope(sid)
        return {'same_snapshot': console._envelope(sid) is first}
    @app.get('/test/future-async-read')
    async def async_future():
        assert console._document_reads() is not None
        first = await asyncio.to_thread(console._envelope, sid)
        return {'same_snapshot': await asyncio.to_thread(console._envelope, sid) is first}
    original = console.workflow_document_store.get_envelope
    calls = []
    def count(snapshot_id):
        calls.append(snapshot_id)
        return original(snapshot_id)
    monkeypatch.setattr(console.workflow_document_store, 'get_envelope', count)
    client = TestClient(app)
    for path in ['/test/future-read', '/test/future-async-read']:
        assert client.get(path).json() == {'same_snapshot': True}
    assert calls == [sid, sid]
    assert console._document_reads() is None


def test_command_inside_a_reader_loads_current_state_and_restores_read_snapshot(tmp_path, production_console):
    from tests.production_support import restart_production
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    second = restart_production(console)
    with console.document_read_operation():
        first = deepcopy(console._envelope(sid))
        changed = second.workflow_document_store.get_envelope(sid)
        changed['title'] = 'Fresh command inputs'
        second.workflow_document_store.write_bundle(envelope=changed)
        with console._atomic_snapshot_mutation(sid):
            assert console._document_reads() is None
            assert console._envelope(sid)['title'] == 'Fresh command inputs'
        assert console._envelope(sid) == first
    assert console._document_reads() is None


def test_overlapping_ingest_formation_review_and_document_reads(tmp_path, production_console, production_app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from tests.production_support import restart_production
    from tests.test_d5_4_review_interaction_evidence import HTML
    console, users, sid, oid = _system(tmp_path, production_console=production_console)
    reviewer, producer = restart_production(console), restart_production(console)
    original = console.workflow_document_store.get_envelope(sid)
    barrier = Barrier(3)
    def read():
        client = _login(console, users['researcher']['username'], production_app=production_app)
        barrier.wait(timeout=5)
        for _ in range(5):
            response = client.get('/inzicht/api/documents')
            assert response.status_code == 200
            assert sid in {row['snapshot_id'] for row in response.json()['documents']}
        return True
    def review():
        barrier.wait(timeout=5)
        return reviewer.review_object(actor_id=users['reviewer_a']['account_id'], snapshot_id=sid,
            object_id=oid, decision='approve', confirmed_object_type='definition',
            expected_revision=reviewer.objects_revision(sid))
    def ingest():
        barrier.wait(timeout=5)
        return producer.ingest(actor_id=users['researcher']['account_id'], filename='concurrent.html',
            data=HTML, content_type='text/html', ingest_kind='new', title='Concurrent ingestion',
            version='1.0', date='2026-09-25', live_url='', class_='richtlijn', family='test',
            named_reviewers=[users['reviewer_a']['account_id'], users['reviewer_b']['account_id']])
    with ThreadPoolExecutor(max_workers=3) as pool:
        reading, reviewing, forming = pool.submit(read), pool.submit(review), pool.submit(ingest)
        assert reading.result(timeout=15)
        assert reviewing.result(timeout=15)
        formed = forming.result(timeout=15)
    assert producer.snapshot_objects(formed['snapshot_id'])
    assert next(row for row in reviewer.snapshot_objects(sid) if row['object_id'] == oid)['governance']['validation_status'] == 'approved'
    assert console.workflow_document_store.get_envelope(sid)['sha256'] == original['sha256']


def test_source_overview_never_loads_full_payloads_or_offers_unchecked_commands(tmp_path, production_console, production_app, monkeypatch):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    def forbidden(*args, **kwargs):
        raise AssertionError('Source overview loaded detail')
    for name in ['get_envelope', 'list_envelopes', 'list_document_objects']:
        monkeypatch.setattr(console.workflow_document_store, name, forbidden)
    response = client.get('/source-selection')
    assert response.status_code == 200
    assert 'Aantallen kandidaten en bronpassages zijn nog niet gecontroleerd' in response.text
    assert 'action="/source-selection/start"' not in response.text
    assert 'Document openen' in response.text


def test_bounded_notices_do_not_claim_complete_when_later_documents_are_unchecked(tmp_path, production_console, production_app, monkeypatch):
    import src.insight_v1 as insight
    from tests.test_d5_4_review_interaction_evidence import HTML
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    console.receive_source(actor_id=users['researcher']['account_id'], filename='later.html', data=HTML,
        content_type='text/html', ingest_kind='new', title='Later unchecked document', version='1.0',
        date='2026-09-25', live_url='', class_='richtlijn', family='test',
        named_reviewers=[users['reviewer_a']['account_id']])
    monkeypatch.setattr(insight, 'MAX_SCAN', 1)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    notices = client.get('/raad/meldingen').json()
    assert notices['complete'] is False
    full = client.get('/inzicht/api/documents').json()
    assert full['total'] == 2
    assert any(row['processing_blocked'] for row in full['documents'])


def test_json_volume_uses_native_decoder_bytes_without_reencoding(tmp_path, production_console):
    import json
    import psycopg
    from src.console_performance_v1 import connect_postgres, performance_scope
    from psycopg.types.json import set_json_loads
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    custom_calls = []
    def custom(data):
        custom_calls.append(len(data))
        return json.loads(data)
    # Install a native decoder customization on this test connection only.
    class Driver:
        Cursor = psycopg.Cursor
        @staticmethod
        def connect(*args, **kwargs):
            con = psycopg.connect(*args, **kwargs)
            set_json_loads(custom, con)
            return con
    with performance_scope() as metrics:
        with connect_postgres(Driver, store.config.dsn) as con:
            assert con.execute("SELECT '{\"a\":1}'::json").fetchone()[0] == {'a': 1}
            assert con.execute("SELECT '{\"b\":2}'::jsonb").fetchone()[0] == {'b': 2}
        assert metrics.json_bytes == sum(custom_calls) > 0
        assert len(custom_calls) == 2
        assert 'a' not in metrics.__dict__ and 'b' not in metrics.__dict__


def test_dispatch_expiry_scan_respects_bound(tmp_path, production_console):
    from datetime import timedelta
    from src.processing_retry_v1 import now
    from src.source_processing_dispatch_v1 import pending
    from tests.test_d5_4_review_interaction_evidence import HTML
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    snapshots = []
    for index in range(3):
        receipt = console.receive_source(actor_id=users['researcher']['account_id'], filename=f'queued-{index}.html', data=HTML,
            content_type='text/html', ingest_kind='new', title=f'Queued {index}', version='1.0', date='2026-09-25',
            live_url='', class_='richtlijn', family='test', named_reviewers=[users['reviewer_a']['account_id']])
        target = receipt['snapshot_id']
        console.reserve_source_selection(actor_id=users['researcher']['account_id'], snapshot_id=target,
            command_id=f'expiry-{index}', expected_revision=console.objects_revision(target))
        env = console.workflow_document_store.get_envelope(target)
        env['processing_attempts'][-1]['expires_at'] = (now()-timedelta(seconds=1)).isoformat()
        console.workflow_document_store.write_bundle(envelope=env)
        snapshots.append(target)
    def interrupted():
        return sum(console.workflow_document_store.get_envelope(s)['processing_attempts'][-1]['state'] == 'interrupted' for s in snapshots)
    assert pending(console, limit=1) == []
    assert interrupted() == 1, 'One scan expired unbounded work while finding no pending command'
    assert pending(console, limit=1) == []
    assert interrupted() == 2, 'The bounded scan must progress past completed expiry work'
