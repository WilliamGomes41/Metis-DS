"""#614: explain missing boundaries without inventing a root cause.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json

from src.section_incident_v1 import build_incident

ATTEMPT = 'a' * 32
REQUEST = 'b' * 32
NOW = '2026-10-14T04:00:00.000Z'


def browser(**fields):
    return dict(schema='metis.section-probe.v1', attempt_id=ATTEMPT,
                route='/source-selection', started_at=NOW, finished_at=NOW,
                navigation='loaded', navigation_started=True, status=200, response_request_id=REQUEST,
                response_complete=True, final_location='target',
                assertion='section-visible-v1', usability='passed', **fields)


def event(name, **fields):
    return dict(event=name, request_id=REQUEST, attempt_id=ATTEMPT,
                route='/source-selection', timestamp=NOW, elapsed_ms=10,
                version='c'*40, instance='local', pid=12, **fields)


def test_http_success_is_not_browser_usability():
    probe = browser(); probe['usability'] = 'failed'
    result = build_incident(probe, [event('request_started'),
        event('request_finished', status=200, outcome='completed')])
    assert result['assessment']['code'] == 'browser_assertion_failed'
    assert result['domain_completion'] == 'not_assessed'
    assert result['application']['response_completed'] is True
    assert result['browser']['usability'] == 'failed'


def test_gateway_response_and_late_application_success_are_both_preserved():
    probe = browser(); probe.update(status=502, response_request_id=None, usability='not_checked')
    result = build_incident(probe, [event('request_started'),
        event('request_finished', status=200, outcome='completed')])
    assert result['assessment']['code'] == 'browser_http_failure'
    assert result['application']['status'] == 200
    assert result['browser']['status'] == 502
    assert result['correlation'] == 'client_attempt_untrusted'
    assert result['assessment']['cause'] == 'unknown'


def test_unavailable_application_is_unknown_not_absent():
    probe = browser(); probe.update(status=None, response_request_id=None,
        navigation='network_error', usability='not_checked', response_complete=False)
    result = build_incident(probe, [])
    assert result['assessment']['code'] == 'browser_navigation_failed'
    assert 'application_events_missing' in result['missing_evidence']
    assert result['application']['started'] is None
    assert result['assessment']['cause'] == 'unknown'


def test_missing_export_and_wrong_request_do_not_join_by_time():
    wrong = event('request_finished', status=200, outcome='completed')
    wrong.update(request_id='d'*32, attempt_id='e'*32)
    result = build_incident(browser(), [wrong])
    assert result['application']['started'] is None
    assert result['correlation'] == 'none'
    assert 'application_events_missing' in result['missing_evidence']


def test_duplicate_attempts_are_ambiguous_without_response_identity():
    probe = browser(); probe['response_request_id'] = None
    other = event('request_started'); other['request_id'] = 'd'*32
    result = build_incident(probe, [event('request_started'), other])
    assert result['correlation'] == 'ambiguous'
    assert result['application']['started'] is None


def test_export_is_redacted_bounded_and_records_omissions():
    raw = event('request_running', phase='db_fetch', secret='never-export')
    raw['phases'] = {'secret-sql': {'calls': 5}, 'db_fetch': {'calls': 2, 'inclusive_ms': 1}}
    probe = browser(); probe['cookie'] = 'never-export'
    result = build_incident(probe, [raw]*1200, [{'event':'startup_failed',
        'timestamp':NOW, 'message':'never-export'}])
    encoded = json.dumps(result)
    assert 'never-export' not in encoded and 'secret-sql' not in encoded
    assert len(encoded) < 600_000
    assert result['omitted_application_events'] == 200
    assert 'application_events_truncated' in result['missing_evidence']
    assert result['platform']['correlation'] == 'time_window_only'


def test_access_rejection_and_application_exception_are_not_success():
    probe = browser(); probe.update(status=403, usability='not_checked')
    result = build_incident(probe, [event('request_started'),
        event('request_finished', status=403, outcome='completed')])
    assert result['assessment']['code'] == 'access_not_granted'
    probe.update(status=500)
    result = build_incident(probe, [event('request_started'),
        event('request_finished', status=None, outcome='exception')])
    assert result['application']['outcome'] == 'exception'
    assert result['assessment']['cause'] == 'unknown'


def test_partial_progress_does_not_imply_request_termination():
    probe = browser(); probe.update(status=None, response_request_id=None,
        navigation='timeout', response_complete=False, usability='not_checked')
    result = build_incident(probe, [event('request_started'),
        event('request_running', phase='db_fetch')])
    assert result['application']['started'] is True
    assert result['application']['response_completed'] is None
    assert 'application_terminal_event_missing' in result['missing_evidence']
    assert result['application']['events'][-1]['phase'] == 'db_fetch'


def test_response_identity_prevents_fallback_to_other_attempt_request():
    wrong = event('request_finished', status=200, outcome='completed')
    wrong['request_id'] = 'd'*32
    result = build_incident(browser(), [wrong])
    assert result['correlation'] == 'none'


def test_inconsistent_browser_evidence_is_not_accepted_as_success():
    probe = browser(); probe['response_complete'] = False
    result = build_incident(probe, [])
    assert result['assessment']['code'] != 'section_visible'
    assert 'browser_usability_evidence_inconsistent' in result['contradictions']


def test_cli_exports_only_sanitized_evidence_and_refuses_overwrite(tmp_path):
    import subprocess
    import sys
    raw = browser(); raw['cookie'] = 'private-cookie'
    inp = tmp_path / 'input.json'; inp.write_text(json.dumps(raw))
    output = tmp_path / 'incident'
    cmd = [sys.executable, 'scripts/export_section_incident.py', '--browser', str(inp), '--output', str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'private-cookie' not in (output / 'incident.json').read_text()
    assert 'unknown' in (output / 'summary.txt').read_text()
    again = subprocess.run(cmd, capture_output=True, text=True)
    assert again.returncode == 2
    assert str(inp) not in again.stderr


def test_real_authenticated_browser_route_exports_correlated_evidence(review_client, tmp_path, monkeypatch):
    """Real Chromium -> HTTP -> Metis route -> offline export, local storage fixture."""
    import os
    import socket
    import subprocess
    import threading
    import time
    import pytest
    import uvicorn
    from src.request_diagnostics_v1 import RequestDiagnostics, _LOGGER
    if not os.environ.get('METIS_BROWSER_EXECUTABLE') or not os.environ.get('METIS_PLAYWRIGHT_MODULE'):
        pytest.skip('Configure Playwright and Chromium for the authenticated browser proof')
    console, client, sid = review_client
    rows = []
    monkeypatch.delenv('APPLICATIONINSIGHTS_CONNECTION_STRING', raising=False)
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: rows.append(json.loads(msg)))
    before = json.dumps(console.snapshot_objects(sid), sort_keys=True)
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    # Production already owns diagnostics; double wrapping emits two request IDs.
    server = uvicorn.Server(uvicorn.Config(client.app, log_level='critical', access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    state = tmp_path / 'session.json'
    state.write_text(json.dumps({'cookies':[{'name':cookie.name, 'value':cookie.value,
        'domain':'127.0.0.1', 'path':'/', 'expires':-1, 'httpOnly':True, 'secure':False,
        'sameSite':'Lax'} for cookie in client.cookies.jar], 'origins':[]}))
    state.chmod(0o600)
    thread.start()
    try:
        deadline = time.monotonic()+5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        out = tmp_path / 'probe.json'
        env = dict(os.environ, METIS_PROBE_URL=f'http://127.0.0.1:{port}/source-selection?document={sid}',
                   METIS_PROBE_STORAGE_STATE=str(state), METIS_PROBE_TIMEOUT_MS='10000')
        result = subprocess.run(['node', 'scripts/probe_section.cjs', str(out)],
                                env=env, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        incident = build_incident(json.loads(out.read_text()), rows)
        assert incident['assessment']['code'] == 'section_visible'
        assert incident['correlation'] == 'response_request_id'
        assert incident['application']['started'] is True
        assert incident['application']['response_completed'] is True
        assert sid not in json.dumps(incident)
        assert before == json.dumps(console.snapshot_objects(sid), sort_keys=True)
    finally:
        server.should_exit = True; thread.join(5); sock.close()


from tests.test_review_render_source_reuse import review_client


def test_terminal_state_uses_request_elapsed_order_not_export_row_order():
    rows = [event('request_finished', status=200, outcome='completed'), event('request_started')]
    rows[0]['elapsed_ms'] = 50; rows[1]['elapsed_ms'] = 0
    result = build_incident(browser(), rows)
    assert result['application']['last_observed_boundary'] == 'request_finished'
    assert result['application']['events'][0]['event'] == 'request_started'


def test_malformed_event_fields_do_not_leak_or_crash():
    raw = event('request_running'); raw.update(event=['secret'], elapsed_ms=10**1000)
    result = build_incident(browser(), [raw], [{'event':['secret']}])
    assert 'unrecognized_application_events' in result['missing_evidence']
    assert 'secret' not in json.dumps(result)


def test_export_reads_projected_kql_rows_and_console_lines(tmp_path):
    from scripts.export_section_incident import read
    path = tmp_path / 'events.json'
    raw = event('request_started')
    path.write_text(json.dumps([{'d':raw}]))
    assert read(path, events=True)[0] == [raw]
    path.write_text('metis_diagnostic ' + json.dumps(raw) + '\n')
    assert read(path, events=True)[0] == [raw]


def test_incident_retains_bounded_readiness_observation_without_private_payload():
    probe = browser()
    probe['usability'] = 'not_established'
    probe['assertion'] = 'task-ready-v2'
    probe['diagnosis'] = {'step':'page_usability', 'expected':'document_inventory_loaded',
        'observed':'pending', 'elapsed_ms':20000, 'cookies':'secret',
        'request':{'route':'/inzicht/api/documents', 'state':'pending', 'reference':'a'*32,
                   'headers':{'authorization':'secret'}}}
    result = build_incident(probe, [])
    assert result['browser']['diagnosis']['request']['reference'] == 'a'*32
    assert result['browser']['usability'] == 'not_established'
    assert 'secret' not in str(result)
