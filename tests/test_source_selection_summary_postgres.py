"""#835: compact source summaries must also bound server-side JSONB reads.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import hashlib
import json
import math
import time

import psycopg
import pytest

from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_insight_v1 import _login


def test_selected_source_survives_slow_document_decode(
    tmp_path, production_console, production_app, monkeypatch
):
    from contextlib import contextmanager
    import src.workflows.workflow_transaction_v1 as transactions
    from src.request_diagnostics_v1 import _LOGGER

    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    envelope = console.workflow_document_store.get_envelope(sid)
    fragments = [{'index': i, 'text': hashlib.sha256(str(i).encode()).hexdigest() * 5}
                 for i in range(12000)]
    original_attempt = envelope['processing_attempts'][-1]
    envelope['processing_attempts'] = []
    for index in range(5):
        attempt = deepcopy(original_attempt)
        attempt.update(attempt_id=f'pa_{index:032x}', command_id=f'decode-history-{index}')
        attempt['diagnostic']['validator_input'] = fragments
        envelope['processing_attempts'].append(attempt)
    console.workflow_document_store.write_bundle(envelope=envelope)
    original_transaction = transactions.workflow_read_transaction
    original_decode = console.workflow_document_store._envelope_from_row
    events = []
    native_errors = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, payload: events.append(json.loads(payload)))

    @contextmanager
    def short_idle_window(owner):
        with original_transaction(owner) as connection:
            # Exercise the real server-side idle timeout, scaled down only in
            # this test. The application keeps its existing five-second limit.
            connection.execute("SET LOCAL idle_in_transaction_session_timeout='100ms'")
            yield connection

    def slow_decode(connection, row):
        # PostgreSQL already delivered the JSON; Python is working before the
        # next reviewer query, exactly where the connection can become idle.
        time.sleep(.3)
        try:
            return original_decode(connection, row)
        except psycopg.Error as error:
            native_errors.append({'type': type(error).__name__, 'sqlstate': error.sqlstate})
            raise

    monkeypatch.setattr(transactions, 'workflow_read_transaction', short_idle_window)
    monkeypatch.setattr(console.workflow_document_store, '_envelope_from_row', slow_decode)
    response = client.get('/source-selection', params={'document': sid})
    finished = next(event for event in events if event.get('event') == 'request_finished'
                    and event.get('request_id') == response.headers['x-metis-request-id'])
    print('SELECTED_SOURCE_IDLE_TIMEOUT', {
        'status': response.status_code,
        'native_errors': native_errors,
        'causes': [{k: value for k, value in cause.items() if k in {'type', 'sqlstate'}}
                   for cause in finished.get('error', {}).get('causes', [])],
    })
    assert response.status_code == 200
    assert 'Vorming' in response.text


def test_source_pages_stay_available_during_real_large_checkpoints(
    tmp_path, production_console, production_app, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from tests.test_console_read_architecture import _received
    from tests.production_support import restart_production
    from src.vorming.source_processing_dispatch_v1 import claim
    from src.request_diagnostics_v1 import current_request_id

    console, users, _, _ = _system(tmp_path, production_console=production_console)
    sid = _received(console, users, title='Concurrent checkpoint availability')
    attempt, _ = console.reserve_source_selection(
        actor_id=users['researcher']['account_id'], snapshot_id=sid,
        command_id='checkpoint-read-proof', expected_revision=console.objects_revision(sid))
    envelope = console.workflow_document_store.get_envelope(sid)
    fragments = [{'index': i, 'text': hashlib.sha256(str(i).encode()).hexdigest() * 5}
                 for i in range(12000)]
    history = []
    for index in range(4):
        previous = deepcopy(envelope['processing_attempts'][-1])
        previous.update(attempt_id=f'pa_{index:032x}', command_id=f'previous-{index}',
                        state='interrupted', finished_at=previous['started_at'],
                        diagnostic={'phase': 'proposal_received', 'validator_input': fragments})
        history.append(previous)
    envelope['processing_attempts'][-1]['diagnostic']['validator_input'] = fragments
    envelope['processing_attempts'] = history + envelope['processing_attempts']
    console.workflow_document_store.write_bundle(envelope=envelope)
    writer = restart_production(console)
    claimed = claim(writer, snapshot_id=sid, attempt_id=attempt['attempt_id'])
    assert claimed is not None
    checkpoint = writer._diagnostic_writer(sid, attempt['attempt_id'])
    client = _login(console, users['researcher']['username'], production_app=production_app)
    original_write = writer.workflow_document_store.write_bundle
    original_execute = psycopg.Connection.execute
    get_mutations = []
    pause = {}

    def paused_checkpoint(**kwargs):
        result = original_write(**kwargs)
        # The real checkpoint has written its new row version. Its outer
        # StoreCommand still owns the transaction and row lock during both GETs.
        pause['written'].set()
        assert pause['release'].wait(15)
        return result

    def observed_execute(connection, query, *args, **kwargs):
        if current_request_id() and isinstance(query, str):
            sql = query.lstrip().upper()
            if sql.startswith(('INSERT', 'UPDATE', 'DELETE')) and any(
                name in sql for name in ('WORKFLOW.DOCUMENTS', 'WORKFLOW.DOCUMENT_OBJECTS',
                                         'WORKFLOW.REVIEW_EVENTS', 'WORKFLOW.PUBLISH_AUTHORIZATIONS')
            ):
                get_mutations.append(sql.split()[0])
        return original_execute(connection, query, *args, **kwargs)

    monkeypatch.setattr(writer.workflow_document_store, 'write_bundle', paused_checkpoint)
    monkeypatch.setattr(psycopg.Connection, 'execute', observed_execute)
    durations = []
    with ThreadPoolExecutor(max_workers=1) as pool:
        for index in range(3):
            pause.update(written=Event(), release=Event())
            future = pool.submit(checkpoint, 'model_request', {'current_task': {'index': index + 1}})
            try:
                assert pause['written'].wait(15)
                for params, budget in [({}, 3), ({'document': sid}, 5)]:
                    started = time.perf_counter()
                    response = client.get('/source-selection', params=params)
                    elapsed = time.perf_counter() - started
                    durations.append({'detail': bool(params), 'seconds': round(elapsed, 3)})
                    assert response.status_code == 200
                    assert 'Status: bezig' in response.text
                    assert elapsed < budget
            finally:
                pause['release'].set()
            future.result(timeout=15)
    print('CONCURRENT_SOURCE_CHECKPOINT_READS', durations)
    assert not get_mutations
    stored = writer.workflow_document_store.get_envelope(sid)
    assert stored['processing_attempts'][-1]['diagnostic']['current_task']['index'] == 3
    assert stored['processing_attempts'][-1]['state'] == 'running'


def test_source_summary_does_not_reread_toasted_diagnostics(
    tmp_path, production_console, production_app, monkeypatch
):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    client = _login(console, users['researcher']['username'], production_app=production_app)
    # Five attempts carrying source/validation evidence, as in the incident.
    # Distinct deterministic text keeps the payload genuinely out-of-line.
    fragments = [
        {"index": i, "text": hashlib.sha256(str(i).encode()).hexdigest() * 4}
        for i in range(10000)
    ]
    envelope = store.get_envelope(sid)
    for attempt in envelope['processing_attempts']:
        attempt['diagnostic'] = {"phase": "proposal_received", "validator_input": fragments}
    while len(envelope['processing_attempts']) < 5:
        envelope['processing_attempts'].append(deepcopy(envelope['processing_attempts'][0]))
    store.write_bundle(envelope=envelope)
    queries = []
    original = psycopg.Connection.execute

    def observed(connection, query, *args, **kwargs):
        if isinstance(query, str) and 'SELECT d.snapshot_id,d.title' in query:
            queries.append(query)
        return original(connection, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.Connection, 'execute', observed)
    summaries = console.source_selection_documents(actor_id=users['researcher']['account_id'])
    assert [row['snapshot_id'] for row in summaries] == [sid]
    assert 'validator_input' not in json.dumps(summaries)
    assert len(queries) == 1
    assert 'envelope_payload' not in queries[0]
    assert 'processing_attempts' not in queries[0]
    with store._connect() as con:
        size = con.execute(
            'SELECT pg_column_size(envelope_payload) AS n FROM workflow.documents WHERE snapshot_id=%s', (sid,)
        ).fetchone()['n']
        plan = con.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) ' + queries[0]).fetchone()['QUERY PLAN'][0]
    blocks = plan['Plan'].get('Shared Hit Blocks', 0) + plan['Plan'].get('Shared Read Blocks', 0)
    budget = 20 + 4 * math.ceil(size / 8192)
    print('SOURCE_SUMMARY_IO', {'stored_bytes': size, 'buffer_accesses': blocks,
                               'budget': budget, 'execution_ms': plan['Execution Time']})
    assert blocks <= budget, 'Compact output repeatedly reads the full TOASTed envelope'
    with store._connect() as con:
        before = con.execute(
            'SELECT md5(envelope_payload::text) AS digest FROM workflow.documents WHERE snapshot_id=%s', (sid,)
        ).fetchone()['digest']
    started = time.perf_counter()
    response = client.get('/source-selection')
    print('SOURCE_SUMMARY_HTTP_SECONDS', round(time.perf_counter() - started, 3))
    assert response.status_code == 200 and 'Vorming' in response.text
    assert 'validator_input' not in response.text
    with store._connect() as con:
        assert con.execute(
            'SELECT md5(envelope_payload::text) AS digest FROM workflow.documents WHERE snapshot_id=%s', (sid,)
        ).fetchone()['digest'] == before


@pytest.mark.parametrize('reviewers', [None, ['not-the-assigned-reviewer']])
def test_summary_still_rejects_invalid_reviewer_authority(
    tmp_path, production_console, reviewers
):
    from src.operations_console_v1 import ConsoleError
    from psycopg.types.json import Jsonb
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    # Bypass the writer only to model corrupt durable data, not a valid command.
    with store._connect() as con:
        con.execute("UPDATE workflow.documents SET envelope_payload=jsonb_set(envelope_payload,"
                    "'{named_reviewers}',%s) WHERE snapshot_id=%s", (Jsonb(reviewers), sid))
    with pytest.raises(ConsoleError, match='workflow_document_unavailable'):
        console.source_selection_documents(actor_id=users['researcher']['account_id'])


def test_source_summary_database_failure_keeps_cause_and_request_id(
    tmp_path, production_console, production_app, monkeypatch
):
    from src.request_diagnostics_v1 import _LOGGER
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    events = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, payload: events.append(json.loads(payload)))
    original = psycopg.Connection.execute

    def blocked(connection, query, *args, **kwargs):
        if isinstance(query, str) and 'SELECT d.snapshot_id,d.title' in query:
            # A real PostgreSQL cancellation on the actual overview connection.
            original(connection, "SET LOCAL statement_timeout='20ms'")
            original(connection, "SELECT pg_sleep(1)")
        return original(connection, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.Connection, 'execute', blocked)
    response = client.get('/source-selection')
    assert response.status_code == 400
    assert 'workflow_document_unavailable' in response.text
    event = next(row for row in events if row.get('event') == 'request_finished'
                 and row.get('request_id') == response.headers['x-metis-request-id'])
    assert event['error']['code'] == 'workflow_document_unavailable'
    assert any(cause['type'] == 'QueryCanceled' and cause['sqlstate'] == '57014'
               for cause in event['error']['causes'])
    assert any('list_source_selection_summaries' in frame
               for cause in event['error']['causes'] for frame in cause.get('frames', []))


def test_summary_trigger_covers_raw_writes_and_ignores_forged_projection(
    tmp_path, production_console
):
    from psycopg.types.json import Jsonb
    from src.vorming.source_selection_v1 import comparable_observations
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    envelope = store.get_envelope(sid)
    template = envelope['processing_attempts'][-1]
    attempts = []
    for index, seconds in enumerate([10, 20, 30]):
        attempt = deepcopy(template)
        attempt.update(attempt_id=f'pa_{index:032x}', kind='ingest', state='succeeded',
                       started_at='2026-10-24T10:00:00+00:00',
                       finished_at=f'2026-10-24T10:00:{seconds:02d}+00:00')
        attempts.append(attempt)
    attempts.append({**template, 'state': 'failed', 'kind': 'resume'})
    envelope['processing_attempts'] = attempts
    envelope.setdefault('semantic_replay', {}).setdefault('provider_evidence', {})['formation_incomplete'] = False
    # Same raw table write used by old binaries/importers: no application cache writer.
    with store._connect() as con:
        con.execute('UPDATE workflow.documents SET envelope_payload=%s WHERE snapshot_id=%s',
                    (Jsonb(envelope), sid))
    summaries = console.source_selection_documents(actor_id=users['researcher']['account_id'])
    row = next(row for row in summaries if row['snapshot_id'] == sid)
    assert len(row['processing_attempts']) == 1
    assert len(json.dumps(row)) < 4096
    assert row['processing_attempts'][0]['state'] == 'failed'
    assert len(row['ingest_observations']) == 3
    assert comparable_observations([row]) == comparable_observations([envelope])
    with store._connect() as con:
        con.execute("UPDATE workflow.documents SET source_selection_summary='{}'::jsonb WHERE snapshot_id=%s", (sid,))
    assert console.source_selection_documents(actor_id=users['researcher']['account_id']) == summaries
    # A fresh interpreter has no operation-scoped Python state to reuse.
    import os
    import subprocess
    import sys
    code = '''import hashlib,json,os
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
store=PostgresWorkflowDocumentRuntimeStore(PostgresCanonicalConfig(dsn=os.environ['METIS_SUMMARY_RESTART_DSN']))
rows=store.list_source_selection_summaries()
print(hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
'''
    restarted = subprocess.run([sys.executable, '-c', code], check=True, capture_output=True,
        text=True, env={**os.environ, 'METIS_SUMMARY_RESTART_DSN': store.config.dsn})
    assert restarted.stdout.strip() == hashlib.sha256(json.dumps(summaries, sort_keys=True).encode()).hexdigest()


def test_summary_write_rolls_back_with_envelope(tmp_path, production_console):
    from src.workflows.workflow_transaction_v1 import workflow_transaction
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    before = store.get_envelope(sid)
    summaries = console.source_selection_documents(actor_id=users['researcher']['account_id'])
    changed = deepcopy(before)
    changed['processing_attempts'][-1]['state'] = 'failed'
    with pytest.raises(RuntimeError, match='injected rollback'):
        with workflow_transaction(store):
            store.write_bundle(envelope=changed)
            raise RuntimeError('injected rollback')
    assert store.get_envelope(sid) == before
    assert console.source_selection_documents(actor_id=users['researcher']['account_id']) == summaries


def test_missing_projection_requires_explicit_resumable_backfill(
    tmp_path, production_console
):
    from scripts.backfill_source_selection_summary import backfill
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    store = console.workflow_document_store
    before = store.get_envelope(sid)
    # Emulate the expand phase: an old row predates the newly added column.
    with store._connect() as con:
        con.execute('ALTER TABLE workflow.documents DISABLE TRIGGER refresh_source_selection_summary')
        con.execute('UPDATE workflow.documents SET source_selection_summary=NULL WHERE snapshot_id=%s', (sid,))
        con.execute('ALTER TABLE workflow.documents ENABLE TRIGGER refresh_source_selection_summary')
    with pytest.raises(WorkflowDocumentStoreError):
        store.list_source_selection_summaries()
    assert backfill(store) == {'applied': False, 'processed': 0, 'remaining': 1}
    with store._connect() as locked:
        locked.execute('SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE', (sid,))
        assert backfill(store, apply=True, batch_size=1) == {
            'applied': True, 'processed': 0, 'remaining': 1}
    assert backfill(store, apply=True, batch_size=1) == {'applied': True, 'processed': 1, 'remaining': 0}
    assert backfill(store, apply=True, batch_size=1) == {'applied': True, 'processed': 0, 'remaining': 0}
    assert store.get_envelope(sid) == before
    assert console.source_selection_documents(actor_id=users['researcher']['account_id'])
