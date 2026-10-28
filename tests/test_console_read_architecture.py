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
    for path in ['/ingest', '/tree', '/publish', '/review', '/review/repair', '/inzicht/routevergelijking', '/inzicht/api/documents', '/raad/meldingen']:
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
    assert notices['documents'][0]['reasons'] == []
    env.pop('processing_blocker')
    second.workflow_document_store.write_bundle(envelope=env)
    assert _login(console, publisher['username'], production_app=production_app).get('/raad/meldingen').json()['documents'] == []


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
    import src.settings.insight_v1 as insight
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
    assert not any(row['processing_blocked'] for row in full['documents'])


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
    from src.vorming.processing_retry_v1 import now
    from src.vorming.source_processing_dispatch_v1 import pending
    from tests.test_d5_4_review_interaction_evidence import HTML
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    snapshots = []
    for index in range(51):
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
    assert interrupted() == 50, 'One scan must retain a bounded expiry discovery batch'
    assert pending(console, limit=1) == []
    assert interrupted() == 51, 'The bounded scan must progress past completed expiry work'

# PR #834 repair probes: first executed unchanged on 56488c0.
def _received(console, users, title='Unstarted'):
    from tests.test_d5_4_review_interaction_evidence import HTML
    return console.receive_source(actor_id=users['researcher']['account_id'], filename='queued.html', data=HTML,
        content_type='text/html', ingest_kind='new', title=title, version='1.0', date='2026-09-25',
        live_url='', class_='richtlijn', family='test', named_reviewers=[users['reviewer_a']['account_id']])['snapshot_id']


def test_slow_telemetry_outside_read_transaction(tmp_path, production_console, production_app, monkeypatch):
    import src.settings.insight_v1 as insight
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    original = insight._telemetry_by_document
    def slow(since):
        time.sleep(6)
        return original(since)
    monkeypatch.setattr(insight, '_telemetry_by_document', slow)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    assert client.get('/inzicht/api/documents').status_code == 200
    assert client.get('/raad/meldingen').status_code == 200


def test_telemetry_has_no_open_read_transaction(tmp_path, production_console, production_app, monkeypatch):
    import src.settings.insight_v1 as insight
    from src.workflows.workflow_transaction_v1 import workflow_transaction_active
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    observed = []
    def telemetry(since):
        observed.append(workflow_transaction_active())
        return {}, False
    monkeypatch.setattr(insight, '_telemetry_by_document', telemetry)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    assert client.get('/inzicht/api/documents').status_code == 200
    assert client.get('/raad/meldingen').status_code == 200
    assert observed == [False, False]


@pytest.mark.parametrize('running', [False, True])
def test_new_and_running_documents_are_not_processing_blocks(tmp_path, production_console, production_app, running):
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    sid = _received(console, users)
    if running:
        console.reserve_source_selection(actor_id=users['researcher']['account_id'], snapshot_id=sid,
            command_id='repair-running', expected_revision=console.objects_revision(sid))
        env = console.workflow_document_store.get_envelope(sid)
        env['processing_blocker'] = 'pre_review_llm_processing_in_progress'
        console.workflow_document_store.write_bundle(envelope=env)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    row = next(r for r in client.get('/inzicht/api/documents').json()['documents'] if r['snapshot_id'] == sid)
    assert row['processing_blocked'] is False
    assert sid not in {r['snapshot_id'] for r in client.get('/raad/meldingen').json()['documents']}


def test_publisher_missing_processing_access_is_not_a_notice(tmp_path, production_console, production_app):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    publisher = console.create_account(username='repair.publisher', password='d54-secret', roles=['publisher'])
    client = _login(console, publisher['username'], production_app=production_app)
    assert client.get('/raad/meldingen').json()['documents'] == []
    env = console.workflow_document_store.get_envelope(sid)
    env['processing_blocker'] = 'processing_dependency_failed'
    console.workflow_document_store.write_bundle(envelope=env)
    row = client.get('/raad/meldingen').json()['documents'][0]
    assert row['processing_blocked'] and row['blocked'] is None and row['reasons'] == []
    assert row['retry_allowed'] is False and row['code'] is None


def test_notices_second_diagnostic_batch_failure_is_explicit_partial(tmp_path, production_console, production_app, monkeypatch, caplog):
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    summary = store.list_document_summaries()[0]
    processing = store.document_processing_inputs([sid])[sid]
    diagnostic = store.document_diagnostic_inputs([sid])[sid]
    documents = [{**summary, 'snapshot_id': f'batch-{i}', 'processing_blocker': 'processing_dependency_failed' if i == 0 else None} for i in range(51)]
    monkeypatch.setattr(store, 'list_document_summaries', lambda **kw: documents)
    monkeypatch.setattr(store, 'document_processing_inputs', lambda ids: {s: {**processing, 'snapshot_id': s} for s in ids})
    monkeypatch.setattr(console, 'published_snapshot_ids', lambda ids: set())
    calls = []
    def diagnostics(ids):
        calls.append(len(ids))
        if len(calls) == 2:
            raise WorkflowDocumentStoreError('workflow_document_diagnostics_read_failed')
        return {s: diagnostic for s in ids}
    monkeypatch.setattr(store, 'document_diagnostic_inputs', diagnostics)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    response = client.get('/raad/meldingen')
    assert response.status_code == 200
    result = response.json()
    assert result['complete'] is False and result['next_offset'] == 50
    assert [r['snapshot_id'] for r in result['documents']] == ['batch-0']
    assert calls == [50, 1]
    assert 'document_diagnostic_batch_unavailable' in caplog.text


def test_source_overview_refreshes_running_document(tmp_path, production_console, production_app):
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    sid = _received(console, users)
    console.reserve_source_selection(actor_id=users['researcher']['account_id'], snapshot_id=sid,
        command_id='overview-running', expected_revision=console.objects_revision(sid))
    response = _login(console, users['researcher']['username'], production_app=production_app).get('/source-selection')
    assert response.status_code == 200
    assert 'window.location.reload()' in response.text
    assert 'Deze pagina ververst elke 5 seconden zolang de verwerking loopt.' in response.text
    assert 'action="/source-selection/start"' not in response.text


def test_pending_finds_task_after_expired_document_in_same_round(tmp_path, production_console):
    from datetime import timedelta
    from src.vorming.processing_retry_v1 import now
    from src.vorming.source_processing_dispatch_v1 import pending
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    ids = []
    for index in range(2):
        sid = _received(console, users, f'Queued {index}')
        console.reserve_source_selection(actor_id=users['researcher']['account_id'], snapshot_id=sid,
            command_id=f'repair-{index}', expected_revision=console.objects_revision(sid))
        ids.append(sid)
    env = console.workflow_document_store.get_envelope(ids[0])
    env['processing_attempts'][-1]['expires_at'] = (now()-timedelta(seconds=1)).isoformat()
    console.workflow_document_store.write_bundle(envelope=env)
    found = pending(console, limit=1)
    assert [s for s, attempt in found] == [ids[1]]


def test_quality_source_and_ledger_io_outside_read_transaction(tmp_path, production_console, monkeypatch):
    import src.settings.quality_metrics_app_v1 as quality
    from src.workflows.workflow_transaction_v1 import workflow_transaction_active
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    original = console.review_source_fragments
    observed = []
    def source(*args, **kwargs):
        observed.append(workflow_transaction_active())
        return original(*args, **kwargs)
    monkeypatch.setattr(console, 'review_source_fragments', source)
    objects = console.snapshot_objects
    def captured_objects(*args, **kwargs):
        observed.append(workflow_transaction_active())
        return objects(*args, **kwargs)
    monkeypatch.setattr(console, 'snapshot_objects', captured_objects)
    ledger = quality.read_events
    def events(*args):
        observed.append(workflow_transaction_active())
        return ledger(*args)
    monkeypatch.setattr(quality, 'read_events', events)
    assert quality.capture(console, users['researcher'])['documents']
    assert observed and not any(observed)


def test_notices_budget_returns_cursor_without_open_transaction(tmp_path, production_console, production_app, monkeypatch, caplog):
    import src.settings.insight_v1 as insight
    from src.workflows.workflow_transaction_v1 import workflow_transaction_active
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    monkeypatch.setattr(insight, 'NOTICE_TIME_BUDGET_SECONDS', 0)
    calls = []
    monkeypatch.setattr(console.workflow_document_store, 'document_diagnostic_inputs', lambda ids: calls.append(ids))
    response = _login(console, users['researcher']['username'], production_app=production_app).get('/raad/meldingen')
    assert response.status_code == 200
    assert response.json() == {'documents': [], 'complete': False, 'next_offset': 0}
    assert not calls and 'document_diagnostic_budget_exhausted' in caplog.text
    assert not workflow_transaction_active()


def test_notices_statement_timeout_preserves_previous_batch(tmp_path, production_console, production_app, monkeypatch, caplog):
    import src.settings.insight_v1 as insight
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    later = _received(console, users)
    # utc_now stores seconds; make batch ordering independent of random ID ties.
    from datetime import datetime, timedelta
    later_env = store.get_envelope(later)
    later_env['acquired_at'] = (datetime.fromisoformat(store.get_envelope(sid)['acquired_at']) + timedelta(seconds=1)).isoformat()
    store.write_bundle(envelope=later_env)
    env = store.get_envelope(sid)
    env['processing_blocker'] = 'processing_dependency_failed'
    store.write_bundle(envelope=env)
    monkeypatch.setattr(insight, 'DIAGNOSTIC_BATCH_SIZE', 1)
    original = store.document_diagnostic_inputs
    calls = []
    def diagnostic(ids):
        calls.append(ids)
        if len(calls) == 2:
            try:
                with store._connect() as con:
                    con.execute("SET LOCAL statement_timeout='20ms'")
                    con.execute('SELECT pg_sleep(1)')
            except Exception as exc:
                raise WorkflowDocumentStoreError('workflow_document_diagnostics_read_failed') from exc
        return original(ids)
    monkeypatch.setattr(store, 'document_diagnostic_inputs', diagnostic)
    response = _login(console, users['researcher']['username'], production_app=production_app).get('/raad/meldingen')
    assert response.status_code == 200
    body = response.json()
    assert body['complete'] is False and body['next_offset'] == 1
    assert [r['snapshot_id'] for r in body['documents']] == [sid]
    assert 'document_diagnostic_batch_unavailable' in caplog.text
    # The failed transaction closed; the independent next request can read again.
    monkeypatch.setattr(store, 'document_diagnostic_inputs', original)
    again = _login(console, users['researcher']['username'], production_app=production_app).get('/raad/meldingen?offset=1')
    assert again.status_code == 200 and again.json()['complete'] is True


@pytest.mark.parametrize('state', ['failed', 'expired'])
def test_failed_or_expired_latest_attempt_is_a_stored_block(tmp_path, production_console, production_app, state):
    from datetime import timedelta
    from src.vorming.processing_retry_v1 import now
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    sid = _received(console, users)
    console.reserve_source_selection(actor_id=users['researcher']['account_id'], snapshot_id=sid,
        command_id='failure-notice', expected_revision=console.objects_revision(sid))
    env = console.workflow_document_store.get_envelope(sid)
    env.pop('processing_blocker', None)
    if state == 'failed':
        env['processing_attempts'][-1].update(state='failed', finished_at=now().isoformat(), error_code='processing_dependency_failed')
    else:
        env['processing_attempts'][-1]['expires_at'] = (now()-timedelta(seconds=1)).isoformat()
    console.workflow_document_store.write_bundle(envelope=env)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    assert next(r for r in client.get('/raad/meldingen').json()['documents'] if r['snapshot_id'] == sid)['processing_blocked']


@pytest.mark.parametrize('path', ['/review', '/review/repair', '/inzicht/routevergelijking'])
def test_cleanup_compact_gets_do_not_read_full_envelopes(tmp_path, production_console, production_app, monkeypatch, path):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    def forbidden(*args, **kwargs):
        raise AssertionError('GET fetched full envelope data')
    monkeypatch.setattr(console.workflow_document_store, 'get_envelope', forbidden)
    monkeypatch.setattr(console.workflow_document_store, 'list_envelopes', forbidden)
    response = client.get(path)
    assert response.status_code == 200
    assert 'comparison_unavailable' not in response.text


def test_console_gets_never_take_command_write_lock(tmp_path, production_console, production_app, monkeypatch):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    console.workflow_identity_store.update_roles(users['researcher']['account_id'], ['researcher','reviewer','publisher'])
    client = _login(console, users['researcher']['username'], production_app=production_app)
    lock_calls = []
    def forbidden():
        lock_calls.append(True)
        raise AssertionError('GET took the command write lock')
    monkeypatch.setattr(console, '_store_write_lock', forbidden)
    for path in ['/', '/ingest', '/source-selection', '/publish', '/review', '/review/repair', '/tree', '/settings',
                 '/inzicht', '/inzicht/routevergelijking', '/inzicht/api/documents', '/raad/meldingen',
                 '/inzicht/api/quality', '/inzicht/document?document='+sid, '/review?document='+sid,
                 '/source-selection?document='+sid, '/publish?document='+sid]:
        assert client.get(path).status_code == 200, path
        assert not lock_calls, path


def test_class_change_reads_only_its_selected_snapshot(tmp_path, production_console, production_app, monkeypatch):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    def forbidden(*args, **kwargs):
        raise AssertionError('Class change listed every envelope')
    monkeypatch.setattr(console, 'list_envelopes', forbidden)
    calls = []
    monkeypatch.setattr(console, 'promote_class', lambda **kw: calls.append(kw))
    response = client.post('/tree/promote', data={'snapshot_id':sid,'new_class':'protocol','confirm':'yes'}, follow_redirects=False)
    assert response.status_code == 303
    assert calls and calls[0]['snapshot_id'] == sid
    missing = client.post('/tree/promote', data={'snapshot_id':'snap-missing','new_class':'protocol','confirm':'yes'}, follow_redirects=False)
    assert missing.status_code == 400 and 'unknown_snapshot' in missing.text
    assert len(calls) == 1


def test_slow_canonical_status_is_outside_workflow_transaction(tmp_path, production_console, production_app, monkeypatch):
    from src.workflows.workflow_transaction_v1 import workflow_transaction_active
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    original = console.published_snapshot_ids
    observed = []
    def slow(ids):
        observed.append(workflow_transaction_active())
        time.sleep(6)
        return original(ids)
    monkeypatch.setattr(console, 'published_snapshot_ids', slow)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    assert client.get('/inzicht/api/documents').status_code == 200
    assert client.get('/raad/meldingen').status_code == 200
    assert observed == [False, False]


@pytest.mark.parametrize('path', ['/inzicht/api/documents', '/raad/meldingen'])
def test_deleted_document_between_summary_and_capture_is_partial(tmp_path, production_console, production_app, monkeypatch, path):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    monkeypatch.setattr(console.workflow_document_store, 'document_processing_inputs', lambda ids: {})
    client = _login(console, users['researcher']['username'], production_app=production_app)
    response = client.get(path)
    assert response.status_code == 200
    body = response.json()
    assert body['documents'] == []
    if path == '/raad/meldingen':
        assert body['complete'] is False
    else:
        assert body['metadata_partial'] is True and body['total'] is None


def test_review_overview_does_not_decode_unrelated_envelope_replay(tmp_path, production_console, production_app, monkeypatch):
    import src.request_diagnostics_v1 as diagnostics
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    env = store.get_envelope(sid)
    env.setdefault('semantic_replay', {}).setdefault('provider_evidence', {})['large_fixture'] = [
        {'index': i, 'text': 'synthetic review replay payload', 'spans':[{'start':i,'end':i+20}]} for i in range(4000)]
    store.write_bundle(envelope=env)
    metrics = []
    original = diagnostics.note_request_metrics
    def capture(**kw):
        metrics.append(kw)
        return original(**kw)
    monkeypatch.setattr(diagnostics, 'note_request_metrics', capture)
    client = _login(console, users['reviewer_a']['username'], production_app=production_app)
    response = client.get('/review')
    assert response.status_code == 200
    print('REVIEW_COMPACT_JSON_BYTES', metrics[-1]['db_json_bytes'])
    assert 0 < metrics[-1]['db_json_bytes'] < 65536


def test_installed_review_and_publish_gets_have_single_explicit_owner(tmp_path, production_console, production_app):
    import inspect
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    app = production_app(console)
    for path, owner in [('/review', 'src.review.review_workboard_v1'), ('/publish', 'src.publication.publish_readiness_ui_v1')]:
        routes = [r for r in app.routes if getattr(r, 'path', '') == path and 'GET' in (getattr(r, 'methods', None) or ())]
        assert len(routes) == 1
        assert inspect.unwrap(routes[0].endpoint).__module__ == owner


def test_native_review_targeted_inputs_preserve_full_domain_result(tmp_path, production_console):
    from src.review.review_workboard_v1 import review_work_item
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    account = users['reviewer_a']
    full = review_work_item(console, account=account, envelope=console.workflow_document_store.get_envelope(sid))
    with console.document_read_operation():
        compact = console.review_workboard_summaries(account['account_id'])[sid]['work_item']
    assert full is not None and compact is not None
    assert {k:v for k,v in compact.items() if k != 'envelope'} == {k:v for k,v in full.items() if k != 'envelope'}
    assert 'semantic_replay' not in compact['envelope']
    assert 'processing_attempts' not in compact['envelope']
