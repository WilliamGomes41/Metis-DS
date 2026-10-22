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
    import os
    stale = tmp_path / f'events-{today}-88888-cccccccc.jsonl'
    stale.write_text('{}\n')
    os.utime(stale, (time.time() - 3600, time.time() - 3600))
    sink.prune(force=True)
    assert other.exists() and not stale.exists()
    sink._path.unlink()  # another worker pruned this worker's quiet file
    sink.write('{"event":"y"}')
    assert sink._path.exists() and sink._path.read_text() == '{"event":"y"}\n'
    vanished = tmp_path / f'events-{today}-99999-bbbbbbbb-2.jsonl'
    monkeypatch.setattr(sink, 'files', lambda: [vanished, *JsonlSink.files(sink)])
    sink.prune(force=True)  # another worker already removed it: no error
    blocked = tmp_path / 'not-a-directory'
    blocked.write_text('')
    fresh = TelemetryHub()
    assert fresh.configure(blocked / 'telemetry') is False and fresh.directory is None
    fresh.record({'event': 'still_recorded'})
    assert [e['event'] for e in fresh.events()] == ['still_recorded']
    failing = TelemetryHub()
    assert failing.configure(tmp_path / 'runtime-store')
    monkeypatch.setattr(failing._sink, 'write', lambda line: (_ for _ in ()).throw(OSError('disk full')))
    failing.record({'event': 'after_disk_full'})
    assert failing.directory is None and [e['event'] for e in failing.events()] == ['after_disk_full']


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


def test_store_lock_wait_and_hold_are_phases(tmp_path, events, *, production_console, production_app):
    from src.operations_console_v1 import OperationsConsole
    console = production_console(processing_binder=lambda console: None, root=tmp_path, runtime=tmp_path / 'runtime')
    app = production_app(console)

    @app.post('/lock')
    def lock():
        with console._store_write_lock():
            with console._store_write_lock():
                time.sleep(0.01)
        return {'ok': True}

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



def test_server_logger_warnings_reach_the_hub_once(hub, monkeypatch):
    server = logging.getLogger('uvicorn.error')
    own = logging.NullHandler()
    monkeypatch.setattr(server, 'handlers', [own])
    monkeypatch.setattr(server, 'propagate', False)
    # Other suites (a real server, dictConfig) may leave this logger disabled or above WARNING.
    monkeypatch.setattr(server, 'disabled', False)
    monkeypatch.setattr(server, 'level', logging.INFO)
    monkeypatch.setattr(server, '_cache', {})
    monkeypatch.setattr(logging.root.manager, 'disable', 0)
    install_logging_bridge()
    install_logging_bridge()
    assert server.handlers == [HUB_HANDLER, own]
    server.warning('worker_timeout pid=%s', 7)
    assert [e['message'] for e in hub.events() if e.get('kind') == 'log'] == ['worker_timeout pid=7']


def test_quality_trend_uses_only_comparable_reports():
    from src.insight_v1 import quality_projection

    def report(as_of, filters, version='v1'):
        return {'as_of': as_of, 'filters': filters, 'definition_version': version, 'open_passages': 1,
                'cohort_size': 1, 'routes': {}}
    current = {**report('2026-10-03', {'route': 'semantic'}), 'publication_duration_seconds': {}, 'burden': {},
               'documents': [], 'definitions': {}, 'limitations': [], 'readiness_duration': {'reason': ''},
               'clinical_errors': {'reason': ''}}
    history = [{'calculation_id': 'a', 'report': report('2026-10-01', {'route': 'semantic'})},
               {'calculation_id': 'b', 'report': report('2026-10-02', {'route': 'deterministic'})},
               {'calculation_id': 'c', 'report': report('2026-10-02', {'route': 'semantic'}, 'v2')},
               {'calculation_id': 'd', 'report': current}]
    view = {'record': {'calculation_id': 'd'}, 'report': current, 'history': history}
    assert [row['calculation_id'] for row in quality_projection(view)['trend']] == ['a', 'd']



def test_form_backed_document_commands_carry_doc_ref(events):
    from fastapi import Form
    app = FastAPI()

    @app.post('/publish')
    def publish(snapshot_id: str = Form(...)):
        return {'ok': snapshot_id.startswith('snap-')}

    app.add_middleware(RequestDiagnostics)
    sid = 'snap-8e5d062cf95bfe2f-6a00cd1d'
    with TestClient(app) as client:
        assert client.post('/publish', data={'snapshot_id': sid}).json() == {'ok': True}
    finished = next(e for e in events if e['event'] == 'request_finished')
    assert finished['doc_ref'] == doc_ref(sid) and sid not in json.dumps(events)



def test_analysis_holds_only_the_newest_events_in_memory(hub, monkeypatch):
    from src.telemetry import hub as hub_module
    monkeypatch.setattr(hub_module, 'MAX_ANALYZED_EVENTS', 3)
    for i in range(5):
        hub.record({'event': f'e{i}', 'ts': f'2026-10-17T10:00:0{i}.000Z'})
    events, truncated = hub_module.recent_events(0)
    assert [e['event'] for e in events] == ['e2', 'e3', 'e4'] and truncated
    from src.insight_v1 import _telemetry_by_document
    calls = []
    monkeypatch.setattr(hub_module, 'recent_events', lambda since: calls.append(since) or ([], True))
    assert _telemetry_by_document(5.0) == ({}, True) and calls == [5.0]  # same bound, partiality surfaced



def test_hub_keeps_every_node_of_a_bounded_phase_tree():
    from src.request_diagnostics_v1 import MAX_TREE_NODES, PHASES
    from src.telemetry import hub as hub_module
    assert hub_module.MAX_KEYS >= max(MAX_TREE_NODES, len(PHASES))
    fresh = TelemetryHub()
    tree = {f'review_render/db_execute/{i}': {'calls': 1} for i in range(MAX_TREE_NODES)}
    stored = fresh.record({'event': 'request_finished', 'phase_tree': tree})
    assert len(stored['phase_tree']) == MAX_TREE_NODES



def test_install_keeps_booting_when_faulthandler_cannot_use_stderr(hub, monkeypatch):
    import faulthandler
    from src.telemetry import install
    monkeypatch.setattr(install, '_INSTALLED', {})
    monkeypatch.setattr(faulthandler, 'is_enabled', lambda: False)
    monkeypatch.setattr(faulthandler, 'enable', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sys.stderr is None')))
    monkeypatch.setattr(install, '_install_exception_hooks', lambda: None)
    monkeypatch.setattr(install.atexit, 'register', lambda fn: None)
    install.install_telemetry(None)
    assert any(e['event'] == 'telemetry_crash_stacks_unavailable' for e in hub.events())



def test_event_survives_a_prune_between_check_and_append(tmp_path):
    sink = JsonlSink(tmp_path)
    sink.write('{"event":"first"}')
    real = sink._handle

    class PrunedDuringWrite:
        def __getattr__(self, name):
            return getattr(real, name)

        def write(self, text):
            sink._path.unlink()  # another worker prunes right before this append
            return real.write(text)
    sink._handle = PrunedDuringWrite()
    sink.write('{"event":"second"}')
    assert sink._path.read_text() == '{"event":"second"}\n'



def test_cut_lists_report_omissions_and_latency_counts_only_completed_responses():
    fresh = TelemetryHub()
    stored = fresh.record({'event': 'publication_boundary', 'omitted_item_count': 0,
                           'items': [{'content_hash': 'a' * 64}] * 40, 'blockers': ['x'] * 35})
    assert len(stored['items']) == 32 and stored['omitted_item_count'] == 8 and stored['blockers_omitted'] == 3
    now = time.time()
    rows = [_event(now - 100, 'request_started', 'ok1', route='/review'),
            _event(now - 99.9, 'request_finished', 'ok1', route='/review', status=200, outcome='completed', elapsed_ms=100.0),
            _event(now - 400, 'request_started', 'dead', route='/review'),
            _event(now - 100, 'request_running', 'dead', route='/review'),
            _event(now - 50, 'request_started', 'boom', route='/review'),
            _event(now - 40, 'request_finished', 'boom', route='/review', status=None, outcome='exception', elapsed_ms=10000.0)]
    kpis = analysis.summarize(rows, now=now, since=now - 600)['kpis']
    assert kpis['p95_ms'] == 100.0 and kpis['aborted'] == 1



def test_counts_and_truncation_refer_to_the_requested_window(hub, monkeypatch):
    from src.telemetry import hub as hub_module
    now = time.time()
    stamp = lambda t: _event(t, 'x', 'x')['ts']
    for i in range(4):  # lookback hour, before the window
        hub.record({'event': f'old{i}', 'ts': stamp(now - 3000 + i)})
    for i in range(2):  # inside a 15-minute window
        hub.record({'event': f'new{i}', 'ts': stamp(now - 60 + i)})
    monkeypatch.setattr(hub_module, 'MAX_ANALYZED_EVENTS', 3)
    events, truncated = hub_module.recent_events(now - 3600 - 900, window_start=now - 900)
    assert len(events) == 3 and truncated is False  # only lookback events were left out
    monkeypatch.setattr(hub_module, 'MAX_ANALYZED_EVENTS', 1)  # now a window event is dropped too
    assert hub_module.recent_events(now - 3600 - 900, window_start=now - 900)[1] is True
    summary = analysis.summarize(list(hub.events()), now=now, since=now - 900)
    assert summary['telemetry']['events'] == 2



def test_rotations_within_one_second_keep_every_file(tmp_path, monkeypatch):
    from src.telemetry import hub as hub_module
    monkeypatch.setattr(hub_module, 'FILE_MAX_BYTES', 10)
    monkeypatch.setattr(hub_module.time, 'time', lambda: 1792270000.0)  # same second for every rotation
    sink = JsonlSink(tmp_path)
    for i in range(3):
        sink.write('{"event":"burst-%d"}' % i)
    rotated = [p for p in sink.files() if len(p.stem.split('-')) == 5]
    assert len(rotated) == 3


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
    assert 'aborted:/publish' in groups and groups['aborted:/publish']['guidance']['category'] == 'missing_completion'
    new = next(c for c in summary['commits'] if c['commit'] == 'new')
    assert new['delta_p95_ratio'] >= 1.5
    assert any(row['value'] == 'db_queries' for row in summary['correlations'])
    titles = [item['title'] for item in summary['insights']]
    assert any(t == 'Bij 1 verzoek(en) ontbreekt de afronding' for t in titles) and any('Trager na deploy' in t for t in titles)
    only_errors = analysis.summarize(_history(now), filters={'error': 'abc123abc123'}, now=now, since=now - 3600)
    assert only_errors['kpis']['requests'] == 4
    detail = analysis.request_detail(_history(now), 'aborted', now=now)
    assert detail['request']['state'] == 'aborted' and detail['request']['last_phase'] == 'store_transaction'


def test_page_and_api_require_login_and_render(hub, *, production_app, production_console):
    from src.operations_console_v1 import OperationsConsole
    import tempfile
    from pathlib import Path
    root = Path(tempfile.mkdtemp())
    console = production_console(processing_binder=lambda console: None, root=root, runtime=root / 'runtime')
    console.create_account(username='beheer', password='fixture-only', roles=('reviewer',))
    app = production_app(console)
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


def test_concurrent_store_lock_wait_is_measured_and_stale_request_is_aborted(tmp_path, events, *, production_console, production_app):
    """opslag: a concurrent writer waits on the store lock and the wait is visible;
    a request whose heartbeats went stale is reported as aborted, not as running."""
    import threading
    from src.operations_console_v1 import OperationsConsole
    console = production_console(processing_binder=lambda console: None, root=tmp_path, runtime=tmp_path / 'runtime')
    holding, release = threading.Event(), threading.Event()

    def holder():
        with console._store_write_lock():
            holding.set()
            release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    app = production_app(console)

    @app.post('/write')
    def write():
        # Start the hold interval only once the request reaches the writer;
        # client/middleware startup can otherwise outlast the entire interval.
        timer = threading.Timer(0.15, release.set)
        timer.start()
        try:
            with console._store_write_lock():
                return {'ok': True}
        finally:
            timer.cancel()
            timer.join(5)

    try:
        assert holding.wait(5)
        with TestClient(app) as client:
            assert client.post('/write').status_code == 200
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    wait = [e for e in events if e['event'] == 'request_finished'][-1]['phases']['store_lock_wait']
    assert wait['calls'] == 1 and wait['inclusive_ms'] >= 100
    now = time.time()
    stale = [_event(now - 120, 'request_started', 'stale', route='/review', commit='c'),
             _event(now - 100, 'request_running', 'stale', route='/review', phase='store_lock_wait')]
    detail = analysis.request_detail(stale, 'stale', now=now)
    assert detail['request']['state'] == 'aborted' and detail['request']['last_phase'] == 'store_lock_wait'
