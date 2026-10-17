"""Unified telemetry: one hub, correlated events, safe errors, analysis and the page.

# release-control-evidence: scope/belofte
# release-control-evidence: metrics
# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import logging
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.request_diagnostics_v1 import RequestDiagnostics, _CURRENT, _LOGGER, doc_ref
from src.telemetry import analysis
from src.telemetry.errors import exception_evidence
from src.telemetry.hub import HUB, JsonlSink, TelemetryHub
from src.telemetry.logging_bridge import HUB_HANDLER, install_logging_bridge


@pytest.fixture
def events(monkeypatch):
    monkeypatch.delenv('APPLICATIONINSIGHTS_CONNECTION_STRING', raising=False)
    records = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: records.append(json.loads(msg)))
    return records


@pytest.fixture
def hub(monkeypatch):
    fresh = TelemetryHub()
    for module in ('src.telemetry.hub', 'src.telemetry.logging_bridge', 'src.telemetry.routes'):
        monkeypatch.setattr(f'{module}.HUB', fresh)
    return fresh


def test_exception_evidence_keeps_type_code_and_repo_frames_never_the_message():
    try:
        raise ConsoleError('snapshot_object_write_conflict', 'secret clinical text')
    except ConsoleError as exc:
        evidence = exception_evidence(exc)
    assert evidence['type'] == 'ConsoleError' and evidence['code'] == 'snapshot_object_write_conflict'
    assert 'secret' not in json.dumps(evidence)
    assert all(frame.startswith('src/') for frame in evidence['frames'])
    try:
        raise KeyError('patient name')
    except KeyError as exc:
        first = exception_evidence(exc)
    try:
        raise KeyError('another name')
    except KeyError as exc:
        second = exception_evidence(exc)
    assert first['fingerprint'] == second['fingerprint'] and 'patient' not in json.dumps(first)


def test_hub_redacts_bounds_and_never_raises(tmp_path):
    hub = TelemetryHub()
    hub.configure(tmp_path)
    hub.record({'event': 'log_record', 'kind': 'log', 'message': 'password=hunter2 for x@example.org\nnext'})
    hub.record({'event': 'phase_started', 'phase': 'db_execute'})  # transient: not stored
    hub.record({'event': 'weird', 'value': object(), 'nested': {'a' * 300: 1, 'ok': [1, 2]}})
    stored = list(hub.events())
    assert [event['event'] for event in stored] == ['log_record', 'weird']
    text = json.dumps(stored)
    assert 'hunter2' not in text and 'x@example.org' not in text and '\n' not in stored[0]['message']
    assert stored[1].get('value') is None
    assert all(event['pid'] and event['commit'] for event in stored)


def test_sink_prunes_by_retention(tmp_path, monkeypatch):
    import os
    old = tmp_path / 'events-19990101-1-aaaaaaaa.jsonl'
    old.write_text('{}\n')
    os.utime(old, (1, 1))
    sink = JsonlSink(tmp_path)
    sink.write('{"event":"x"}')
    sink.prune(force=True)
    assert not old.exists() and sink.files()



def test_prune_keeps_other_workers_current_files_and_unusable_storage_falls_back(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from src.telemetry import hub as hub_module
    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    other = tmp_path / f'events-{today}-99999-bbbbbbbb.jsonl'
    rotated = tmp_path / f'events-{today}-99999-bbbbbbbb-1.jsonl'
    other.write_text('{}\n')
    rotated.write_text('{}\n')
    monkeypatch.setattr(hub_module, 'TOTAL_MAX_BYTES', 0)
    sink = JsonlSink(tmp_path)
    sink.write('{"event":"x"}')
    sink.prune(force=True)
    assert other.exists() and not rotated.exists()
    blocked = tmp_path / 'not-a-directory'
    blocked.write_text('')
    fresh = TelemetryHub()
    assert fresh.configure(blocked / 'telemetry') is False and fresh.directory is None
    fresh.record({'event': 'still_recorded'})
    assert [e['event'] for e in fresh.events()] == ['still_recorded']


def test_serve_console_uses_the_same_observability_composition(tmp_path, monkeypatch):
    import argparse
    import uvicorn
    from src import cli
    served = {}
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kwargs: served.setdefault('app', app))
    monkeypatch.setattr('src.telemetry.install.install_telemetry', lambda directory: served.setdefault('dir', directory))
    cli.cmd_serve_console(argparse.Namespace(source_store=tmp_path / 'sources', runtime=tmp_path / 'runtime',
                                             host='127.0.0.1', port=0))
    assert any(m.cls is RequestDiagnostics for m in served['app'].user_middleware)
    assert served['dir'] == tmp_path / 'runtime' / 'telemetry'


def _app():
    app = FastAPI()

    @app.post('/review/approve')
    def approve():
        raise ValueError('private value')

    @app.get('/conflict')
    def conflict():
        raise ConsoleError('snapshot_object_write_conflict')

    @app.exception_handler(ConsoleError)
    async def handled(_request, exc):
        from fastapi.responses import PlainTextResponse
        from src.request_diagnostics_v1 import note_handled_error
        note_handled_error(exc.code)
        return PlainTextResponse('nope', status_code=409)

    @app.get('/session/status')
    def status():
        return {'ok': True}

    app.add_middleware(RequestDiagnostics)
    return app


def test_write_routes_errors_and_correlation_are_captured(events):
    trace = '0af7651916cd43dd8448eb211c80319c'
    sid = 'snap-8e5d062cf95bfe2f-6a00cd1d'
    with TestClient(_app(), raise_server_exceptions=False) as client:
        failed = client.post('/review/approve', headers={'traceparent': f'00-{trace}-b7ad6b7169203331-01'})
        handled = client.get('/conflict', params={'document': sid})
        polled = client.get('/session/status')
    # The 500 body comes from the server-error layer outside diagnostics; the event still carries the id.
    assert failed.status_code == 500 and handled.headers['x-metis-trace-id']
    assert polled.status_code == 200 and 'x-metis-request-id' not in polled.headers
    finished = [e for e in events if e['event'] == 'request_finished']
    by_route = {e['route']: e for e in finished}
    crash = by_route['/review/approve']
    assert crash['outcome'] == 'exception' and crash['error']['type'] == 'ValueError'
    assert crash['error']['fingerprint'] and crash['trace_id'] == trace
    conflict = by_route['/conflict']
    assert conflict['status'] == 409 and conflict['error'] == {
        'type': 'ConsoleError', 'code': 'snapshot_object_write_conflict', 'handled': True}
    assert conflict['doc_ref'] == doc_ref(sid)
    serialized = json.dumps(events)
    assert 'private value' not in serialized and sid not in serialized
    assert not any(e.get('route') == '/session/status' for e in events)


def test_store_lock_wait_and_hold_are_phases(tmp_path, events):
    from src.operations_console_v1 import OperationsConsole
    console = OperationsConsole(root=tmp_path, runtime=tmp_path / 'runtime')
    app = FastAPI()

    @app.post('/lock')
    def lock():
        with console._store_write_lock():
            with console._store_write_lock():
                time.sleep(0.01)
        return {'ok': True}

    app.add_middleware(RequestDiagnostics)
    with TestClient(app) as client:
        assert client.post('/lock').status_code == 200
    phases = [e for e in events if e['event'] == 'request_finished'][-1]['phases']
    assert phases['store_lock_wait']['calls'] == 1
    assert phases['store_lock_hold']['calls'] == 1 and phases['store_lock_hold']['inclusive_ms'] >= 10
    assert phases['store_lock_hold']['exclusive_ms'] == 0


def test_logging_bridge_forwards_diagnostics_and_warnings_with_request_id(hub, monkeypatch):
    install_logging_bridge()
    from src.request_diagnostics_v1 import RequestEvidence
    evidence = RequestEvidence('a' * 32, '/review', lambda payload: None, trace_id='b' * 32)
    token = _CURRENT.set(evidence)
    try:
        logging.getLogger('metis.test').warning('store_command_remirror_failed snapshot_ids=%s', 'x')
        _LOGGER.handle(logging.LogRecord('metis.console.diagnostics', logging.INFO, '', 0, 'metis_diagnostic %s',
                                         (json.dumps({'event': 'processing_checkpoint', 'phase': 'reserved'}),), None))
    finally:
        _CURRENT.reset(token)
    stored = list(hub.events())
    warning = next(e for e in stored if e.get('kind') == 'log')
    assert warning['request_id'] == 'a' * 32 and warning['trace_id'] == 'b' * 32
    assert warning['message'].startswith('store_command_remirror_failed')
    assert any(e.get('event') == 'processing_checkpoint' and e['kind'] == 'processing' for e in stored)
    assert HUB_HANDLER in logging.getLogger().handlers



def test_diagnostic_identifiers_become_doc_ref_and_never_reach_the_hub(hub):
    install_logging_bridge()
    sid = 'snap-0123456789abcdef-01234567'
    payload = {'event': 'publication_boundary', 'snapshot_id': sid, 'release_id': 'rel-1', 'actor_hmac': 'f' * 64,
               'items': [{'object_id': 'obj-secret', 'object_version': '1', 'content_hash': 'a' * 64}]}
    _LOGGER.handle(logging.LogRecord('metis.console.diagnostics', logging.INFO, '', 0, 'metis_diagnostic %s',
                                     (json.dumps(payload),), None))
    logging.getLogger('metis.test').warning('retry failed for %s', sid)
    stored = json.dumps(list(hub.events()))
    event = next(e for e in hub.events() if e.get('event') == 'publication_boundary')
    assert event['doc_ref'] == doc_ref(sid) and event['items'][0]['content_hash'] == 'a' * 64
    for secret in (sid, 'rel-1', 'f' * 64, 'obj-secret'):
        assert secret not in stored
    assert f'retry failed for {doc_ref(sid)}' in stored


def test_logged_exception_keeps_fingerprint_after_structured_logging_redaction(hub):
    from src.structured_logging_v1 import install_structured_logging
    install_logging_bridge()
    install_structured_logging()
    assert logging.getLogger().handlers[0] is HUB_HANDLER
    try:
        raise KeyError('patient secret')
    except KeyError:
        logging.getLogger('metis.test').exception('background job failed')
    event = next(e for e in hub.events() if e.get('kind') == 'log' and e['message'] == 'background job failed')
    assert event['error']['type'] == 'KeyError' and event['error']['fingerprint']
    assert 'patient secret' not in json.dumps(event)



def test_unmatched_paths_get_a_fixed_label_and_inbound_trace_reaches_the_span(events):
    with TestClient(_app(), raise_server_exceptions=False) as client:
        assert client.get('/missing/Jane-Doe/diagnosis').status_code == 404
    started = next(e for e in events if e['event'] == 'request_started')
    assert started['route'] == '<unmatched>' and 'Jane' not in json.dumps(events)
    from opentelemetry.sdk.trace import TracerProvider
    from src.request_diagnostics_v1 import AzureTelemetry
    telemetry = AzureTelemetry.__new__(AzureTelemetry)
    telemetry.tracer = TracerProvider().get_tracer('test')
    trace = '0af7651916cd43dd8448eb211c80319c'
    with telemetry.request('/review', traceparent=f'00-{trace}-b7ad6b7169203331-01') as span:
        assert format(span.get_span_context().trace_id, '032x') == trace


def test_standalone_errors_follow_the_window_and_request_filters():
    now = time.time()
    rows = _history(now)
    rows.append({'ts': _event(now - 3500, 'x', 'x')['ts'], 'kind': 'log', 'event': 'log_record',
                 'level': 'ERROR', 'logger': 'old', 'message': 'before_window'})
    rows.append({'ts': _event(now - 60, 'x', 'x')['ts'], 'kind': 'log', 'event': 'log_record',
                 'level': 'ERROR', 'logger': 'tree', 'message': 'other_route', 'request_id': 'running'})
    labels = lambda summary: {g['label'] for g in summary['errors']}
    window = analysis.summarize(rows, now=now, since=now - 600)
    assert 'Log ERROR: before_window' not in labels(window) and 'Log ERROR: other_route' in labels(window)
    filtered = analysis.summarize(rows, filters={'route': '/review'}, now=now, since=now - 600)
    assert 'Log ERROR: other_route' not in labels(filtered)
    tree = analysis.summarize(rows, filters={'route': '/tree'}, now=now, since=now - 600)
    assert sum(row['requests'] for row in tree['commits']) == 1


def _event(t, name, rid, **fields):
    from datetime import datetime, timezone
    ts = datetime.fromtimestamp(t, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    return {'ts': ts, 'event': name, 'request_id': rid, 'kind': 'request', **fields}


def _history(now):
    rows = []
    for i in range(40):
        t = now - 3000 + i * 60
        commit = 'old' if i < 20 else 'new'
        slow = commit == 'new'
        rows.append(_event(t, 'request_started', f'r{i}', route='/review', commit=commit))
        rows.append(_event(t + 0.1, 'request_finished', f'r{i}', route='/review', commit=commit, status=200,
                           outcome='completed', elapsed_ms=400.0 if slow else 100.0,
                           phases={'db_execute': {'calls': 30 if slow else 3, 'inclusive_ms': 300 if slow else 30,
                                                  'exclusive_ms': 300 if slow else 30}},
                           db={'db_queries': 30 if slow else 3}))
    for i in range(4):
        t = now - 600 + i
        rows.append(_event(t, 'request_started', f'e{i}', route='/review', method='POST', commit='new'))
        rows.append(_event(t + 0.2, 'request_finished', f'e{i}', route='/review', method='POST', commit='new',
                           status=None, outcome='exception', elapsed_ms=20.0,
                           error={'type': 'KeyError', 'fingerprint': 'abc123abc123', 'frames': ['src/x.py:f:1']}))
    rows.append(_event(now - 300, 'request_started', 'aborted', route='/publish', commit='new'))
    rows.append(_event(now - 290, 'request_running', 'aborted', route='/publish', phase='store_transaction'))
    rows.append(_event(now - 5, 'request_started', 'running', route='/tree', commit='new'))
    return rows


def test_analysis_finds_aborts_groups_regressions_and_correlations():
    now = time.time()
    summary = analysis.summarize(_history(now), now=now, since=now - 3600)
    kpis = summary['kpis']
    assert kpis['aborted'] == 1 and kpis['running'] == 1 and kpis['errors'] == 5
    groups = {g['key']: g for g in summary['errors']}
    assert groups['abc123abc123']['count'] == 4 and groups['abc123abc123']['guidance']['where'] == 'src/x.py:f:1'
    assert 'aborted:/publish' in groups and groups['aborted:/publish']['guidance']['category'] == 'crash'
    new = next(c for c in summary['commits'] if c['commit'] == 'new')
    assert new['delta_p95_ratio'] >= 1.5
    assert any(row['value'] == 'db_queries' for row in summary['correlations'])
    titles = [item['title'] for item in summary['insights']]
    assert titles[0].startswith('1 verzoek(en) afgebroken') and any('Trager na deploy' in t for t in titles)
    only_errors = analysis.summarize(_history(now), filters={'error': 'abc123abc123'}, now=now, since=now - 3600)
    assert only_errors['kpis']['requests'] == 4
    detail = analysis.request_detail(_history(now), 'aborted', now=now)
    assert detail['request']['state'] == 'aborted' and detail['request']['last_phase'] == 'store_transaction'


def test_page_and_api_require_login_and_render(hub):
    from src.operations_console_app import create_console_app
    from src.operations_console_v1 import OperationsConsole
    import tempfile
    from pathlib import Path
    root = Path(tempfile.mkdtemp())
    console = OperationsConsole(root=root, runtime=root / 'runtime')
    console.create_account(username='beheer', password='fixture-only', roles=('reviewer',))
    app = create_console_app(console)
    app.add_middleware(RequestDiagnostics)
    with TestClient(app, base_url='https://testserver') as client:
        assert client.get('/telemetry/api/summary').status_code == 401
        assert client.get('/telemetry', follow_redirects=False).status_code == 401
        client.post('/login', data={'username': 'beheer', 'password': 'fixture-only'}, follow_redirects=False)
        alias = client.get('/telemetry', follow_redirects=False)
        assert alias.status_code == 303 and alias.headers['location'] == '/inzicht?tab=systeem'
        page = client.get('/inzicht?tab=systeem')
        assert page.status_code == 200 and 'id="tm-insights"' in page.text and 'data-initial-tab="systeem"' in page.text
        summary = client.get('/telemetry/api/summary', params={'window': '1h', 'q': 'snap-8e5d062cf95bfe2f-6a00cd1d'})
        body = summary.json()
        assert summary.status_code == 200 and summary.headers['cache-control'] == 'no-store'
        assert body['filters']['q'] == doc_ref('snap-8e5d062cf95bfe2f-6a00cd1d')
        assert {'kpis', 'series', 'routes', 'phases', 'errors', 'commits', 'correlations', 'insights', 'requests'} <= set(body)
        assert client.get('/telemetry/api/request/' + 'f' * 32).status_code == 404
        assert client.get('/telemetry/api/request/not-an-id').status_code == 404
        export = client.get('/telemetry/api/export', params={'window': '1h'})
        assert export.status_code == 200 and export.headers['content-type'].startswith('application/x-ndjson')


def test_install_is_idempotent_and_enables_crash_stacks(tmp_path, monkeypatch):
    import faulthandler
    from src.telemetry import install
    monkeypatch.setattr(install, '_INSTALLED', {})
    fresh = TelemetryHub()
    monkeypatch.setattr(install, 'HUB', fresh)
    monkeypatch.setattr('src.telemetry.hub.HUB', fresh)
    install.install_telemetry(tmp_path)
    install.install_telemetry(tmp_path)
    assert faulthandler.is_enabled()
    starts = [e for e in fresh.events() if e.get('event') == 'process_started']
    assert len(starts) == 1 and fresh.directory == tmp_path
    assert sum(handler is HUB_HANDLER for handler in logging.getLogger().handlers) == 1


def test_json_log_lines_carry_request_and_trace_id_without_a_filter():
    from src.request_diagnostics_v1 import RequestEvidence
    from src.structured_logging_v1 import JsonLogFormatter
    record = logging.LogRecord('metis.any', logging.WARNING, '', 0, 'late handler line', (), None)
    token = _CURRENT.set(RequestEvidence('c' * 32, '/review', lambda payload: None, trace_id='d' * 32))
    try:
        row = json.loads(JsonLogFormatter().format(record))
    finally:
        _CURRENT.reset(token)
    assert row['request_id'] == 'c' * 32 and row['trace_id'] == 'd' * 32
    assert 'request_id' not in json.loads(JsonLogFormatter().format(record))


def test_every_http_middleware_is_excluded_from_error_frames():
    import re
    from pathlib import Path
    from src.telemetry.errors import MIDDLEWARE_FUNCTIONS
    names = set()
    for path in Path('src').rglob('*.py'):
        names.update(re.findall(r'@app\.middleware\("http"\)\s*\n\s*async def (\w+)', path.read_text(encoding='utf-8')))
    assert names and names <= MIDDLEWARE_FUNCTIONS, names - MIDDLEWARE_FUNCTIONS


def test_concurrent_store_lock_wait_is_measured_and_stale_request_is_aborted(tmp_path, events):
    """opslag: a concurrent writer waits on the store lock and the wait is visible;
    a request whose heartbeats went stale is reported as aborted, not as running."""
    import threading
    from src.operations_console_v1 import OperationsConsole
    console = OperationsConsole(root=tmp_path, runtime=tmp_path / 'runtime')
    holding, release = threading.Event(), threading.Event()

    def holder():
        with console._store_write_lock():
            holding.set()
            release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    holding.wait(5)
    app = FastAPI()

    @app.post('/write')
    def write():
        with console._store_write_lock():
            return {'ok': True}

    app.add_middleware(RequestDiagnostics)
    with TestClient(app) as client:
        timer = threading.Timer(0.15, release.set)
        timer.start()
        assert client.post('/write').status_code == 200
    thread.join(5)
    wait = [e for e in events if e['event'] == 'request_finished'][-1]['phases']['store_lock_wait']
    assert wait['calls'] == 1 and wait['inclusive_ms'] >= 100
    now = time.time()
    stale = [_event(now - 120, 'request_started', 'stale', route='/review', commit='c'),
             _event(now - 100, 'request_running', 'stale', route='/review', phase='store_lock_wait')]
    detail = analysis.request_detail(stale, 'stale', now=now)
    assert detail['request']['state'] == 'aborted' and detail['request']['last_phase'] == 'store_lock_wait'
