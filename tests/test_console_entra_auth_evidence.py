"""Every fail-closed answer of the Entra boundary leaves explainable evidence.

Incident 2026-10-19: a scanner caused three /auth/microsoft 503s whose cause was
swallowed before diagnostics could record it, and dotfile probes started
Entra authentication flows.
"""
# release-control-evidence: scope/belofte every Entra 503/403/404/429 carries a safe, recorded cause
# release-control-evidence: toegang dotfile probes never reach session or Entra; real routes still require sign-in
# release-control-evidence: beschikbaarheid parallel scans start no flows; flow starts are capped with Retry-After
# release-control-evidence: slop no message text, state or code reaches the diagnostic records
# release-control-evidence: releasebewijs tests only; no live deployment or production log evidence
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.console_entra_routes_v1 import (
    DEFAULT_FLOW_STARTS_PER_MINUTE, _denied_path, flow_starts_per_minute, install_entra_routes,
)
from src.operations_console_app import _page, create_console_app
from src.operations_console_v1 import ConsoleError
from src.request_diagnostics_v1 import RequestDiagnostics, _LOGGER
from tests.test_console_duty_first_home import _console


@pytest.fixture
def events(monkeypatch):
    monkeypatch.delenv('APPLICATIONINSIGHTS_CONNECTION_STRING', raising=False)
    records = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: records.append(json.loads(msg)))
    return records


class _BrokenLogin:
    def begin(self):
        raise RuntimeError('SECRET-DETAIL from provider')


def _client(monkeypatch, identity, *, login=None):
    monkeypatch.setattr('src.console_entra_routes_v1.MicrosoftLogin', lambda config: login)
    app = FastAPI()

    @app.get('/settings')
    def settings():
        return {'ok': True}

    install_entra_routes(app, None, identity, render_page=lambda body: body)
    app.add_middleware(RequestDiagnostics)
    return TestClient(app, base_url='https://testserver')


def _finished(events):
    return [r for r in events if r['event'] == 'request_finished']


def test_begin_failure_stays_503_and_records_cause_without_text(monkeypatch, events):
    client = _client(monkeypatch, SimpleNamespace(config=None), login=_BrokenLogin())
    response = client.get('/auth/microsoft', follow_redirects=False)
    assert response.status_code == 503
    [finished] = _finished(events)
    assert finished['status'] == 503
    error = finished['error']
    assert error['type'] == 'RuntimeError' and error['handled'] is True
    assert any(':begin:' in frame for frame in error['frames'])
    assert 'SECRET-DETAIL' not in json.dumps(events)


def test_callback_denial_records_console_error_code(monkeypatch, events):
    def consume_flow(handle):
        raise ConsoleError('entra_flow_missing')
    client = _client(monkeypatch, SimpleNamespace(config=None, consume_flow=consume_flow))
    response = client.get('/auth/microsoft/callback', params={'state': 's', 'code': 'SECRET-CODE'},
                          follow_redirects=False)
    assert response.status_code == 403
    [finished] = _finished(events)
    assert finished['error']['code'] == 'entra_flow_missing'
    assert 'SECRET-CODE' not in json.dumps(events)


@pytest.mark.parametrize('params', [
    {'code': 'SECRET-CODE'}, {'state': 'other', 'code': 'SECRET-CODE'},
    [('state', 'flow-state'), ('state', 'flow-state'), ('code', 'SECRET-CODE')],
])
def test_callback_state_rejection_records_its_cause(monkeypatch, events, params):
    identity = SimpleNamespace(config=None, consume_flow=lambda handle: {'state': 'flow-state'})
    login = SimpleNamespace(finish=lambda flow, supplied: pytest.fail('state must fail before code exchange'))
    client = _client(monkeypatch, identity, login=login)
    response = client.get('/auth/microsoft/callback', params=params, follow_redirects=False)
    assert response.status_code == 403
    [finished] = _finished(events)
    assert finished['error'] == {'type': 'ConsoleError', 'code': 'entra_state_mismatch', 'handled': True}
    assert 'SECRET-CODE' not in json.dumps(events) and 'flow-state' not in json.dumps(events)


_PROBES = ['/.env', '/.git/config', '/.aws/credentials', '/.kube/config',
           '/%2eenv', '/.ENV', '/.Git/HEAD', '/app/.env', '/api/.env.local', '/static%2f.ssh/id_rsa']


@pytest.mark.parametrize('path', _PROBES)
def test_secret_dotfile_probe_is_404_before_session_or_entra(monkeypatch, events, path):
    def renew_session(token):
        raise AssertionError('a dotfile probe must not reach session renewal')
    login = SimpleNamespace(begin=lambda: pytest.fail('a dotfile probe must not start Entra'))
    client = _client(monkeypatch, SimpleNamespace(config=None, renew_session=renew_session), login=login)
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 404
    assert 'location' not in response.headers
    [finished] = _finished(events)
    assert finished['error']['code'] == 'route_denied'


def test_denial_matches_raw_unnormalised_segments_only():
    # Raw clients may send dot segments unresolved; httpx would normalise them away.
    assert _denied_path('/x/../.ENV') and _denied_path('/a/b/.git')
    for path in ('/', '/.well-known/oauth-protected-resource', '/environment', '/review/envelope',
                 '/brand/metis.svg', '/docs/report.env'):
        assert not _denied_path(path), path


def test_parallel_scan_starts_no_session_or_entra_work(monkeypatch, events):
    calls = []
    lock = threading.Lock()
    def renew_session(token):
        with lock:
            calls.append('renew')
        raise ConsoleError('workflow_session_required')
    def begin():
        with lock:
            calls.append('begin')
        return {'auth_uri': 'https://login.microsoftonline.com/x', 'state': 's'}
    client = _client(monkeypatch, SimpleNamespace(config=None, renew_session=renew_session, save_flow=lambda f: 'h'),
                     login=SimpleNamespace(begin=begin))
    probes = [_PROBES[i % len(_PROBES)] for i in range(42)]
    with client, ThreadPoolExecutor(max_workers=42) as pool:
        statuses = list(pool.map(lambda p: client.get(p).status_code, probes))  # follows redirects
    assert statuses == [404] * 42
    assert calls == []
    finished = _finished(events)
    assert len(finished) == 42 and all(r['error']['code'] == 'route_denied' for r in finished)


def test_save_flow_failure_is_explainable_503(monkeypatch, events):
    def save_flow(flow):
        raise OSError('SECRET-DSN identity store down')
    login = SimpleNamespace(begin=lambda: {'auth_uri': 'https://login.microsoftonline.com/x', 'state': 's'})
    client = _client(monkeypatch, SimpleNamespace(config=None, save_flow=save_flow), login=login)
    response = client.get('/auth/microsoft', follow_redirects=False)
    assert response.status_code == 503
    assert 'location' not in response.headers
    [finished] = _finished(events)
    assert finished['error']['type'] == 'OSError' and finished['error']['handled'] is True
    assert any(':begin:' in frame for frame in finished['error']['frames'])
    assert 'SECRET-DSN' not in json.dumps(events)


@pytest.mark.parametrize('target,kept', [
    ('/review?doc=1', '/review?doc=1'), ('https://evil.example/', '/'), ('//evil.example', '/'),
    ('/\\evil.example', '/'), ('/auth/microsoft', '/'), ('/logout', '/'), ('javascript:alert(1)', '/'),
])
def test_begin_redirects_only_to_entra_and_keeps_internal_return(monkeypatch, events, target, kept):
    auth_uri = 'https://login.microsoftonline.com/tenant/oauth2/v2.0/authorize?state=SECRET-STATE'
    saved = []
    def save_flow(flow):
        saved.append(flow)
        return 'handle'
    login = SimpleNamespace(begin=lambda: {'auth_uri': auth_uri, 'state': 'SECRET-STATE'})
    client = _client(monkeypatch, SimpleNamespace(config=None, save_flow=save_flow), login=login)
    response = client.get('/auth/microsoft', params={'next': target}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == auth_uri
    assert saved[0]['metis_return_to'] == kept
    assert 'SECRET-STATE' not in json.dumps(events)


def test_protected_routes_still_redirect_to_sign_in(monkeypatch, events):
    def renew_session(token):
        raise ConsoleError('workflow_session_required')
    client = _client(monkeypatch, SimpleNamespace(config=None, renew_session=renew_session))
    for path in ('/settings', '/.well-known/unknown', '/environment'):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'].startswith('/auth/microsoft?next=')


@pytest.mark.parametrize('path', ['/settings', '/review', '/accounts'])
def test_registered_metis_routes_still_require_sign_in(tmp_path, monkeypatch, path):
    def renew_session(token):
        raise ConsoleError('workflow_session_required')
    monkeypatch.setattr('src.console_entra_routes_v1.MicrosoftLogin', lambda config: None)
    app = create_console_app(_console(tmp_path))
    install_entra_routes(app, None, SimpleNamespace(config=None, renew_session=renew_session), render_page=_page)
    response = TestClient(app, base_url='https://testserver').get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/auth/microsoft?next=' + path.replace('/', '%2F')


def test_parallel_flow_start_burst_is_capped_with_retry_after(monkeypatch, events):
    monkeypatch.setenv('METIS_AUTH_FLOW_STARTS_PER_MINUTE', '30')
    started = []
    lock = threading.Lock()
    def begin():
        with lock:
            started.append(1)
        return {'auth_uri': 'https://login.microsoftonline.com/x', 'state': 's'}
    def renew_session(token):
        raise ConsoleError('workflow_session_required')
    def consume_flow(handle):
        raise ConsoleError('entra_flow_missing')
    identity = SimpleNamespace(config=None, save_flow=lambda flow: 'h', renew_session=renew_session,
                               consume_flow=consume_flow)
    client = _client(monkeypatch, identity, login=SimpleNamespace(begin=begin))
    with client, ThreadPoolExecutor(max_workers=42) as pool:
        responses = list(pool.map(lambda _: client.get('/auth/microsoft', follow_redirects=False), range(42)))
        # Navigation and the callback stay outside the flow-start ceiling.
        assert client.get('/settings', follow_redirects=False).status_code == 303
        assert client.get('/auth/microsoft/callback', params={'state': 's'},
                          follow_redirects=False).status_code == 403
    statuses = sorted(r.status_code for r in responses)
    assert statuses == [303] * 30 + [429] * 12
    assert len(started) == 30
    for response in responses:
        if response.status_code == 429:
            assert 1 <= int(response.headers['retry-after']) <= 60
            assert response.headers['cache-control'] == 'no-store'
            assert 'location' not in response.headers
    denied = [r for r in _finished(events) if r['status'] == 429]
    assert len(denied) == 12 and all(r['error']['code'] == 'rate_limit_exceeded' for r in denied)


@pytest.mark.parametrize('raw,expected', [
    (None, DEFAULT_FLOW_STARTS_PER_MINUTE), ('300', 300), ('0', DEFAULT_FLOW_STARTS_PER_MINUTE),
    ('-5', DEFAULT_FLOW_STARTS_PER_MINUTE), ('veel', DEFAULT_FLOW_STARTS_PER_MINUTE),
])
def test_flow_start_ceiling_configuration_falls_back_safely(raw, expected):
    environ = {} if raw is None else {'METIS_AUTH_FLOW_STARTS_PER_MINUTE': raw}
    assert flow_starts_per_minute(environ) == expected


@pytest.mark.parametrize('code,status', [('workflow_identity_unavailable', 503), ('workflow_session_required', 401)])
def test_explicit_session_renewal_records_its_cause(monkeypatch, events, code, status):
    def renew_session(token):
        raise ConsoleError(code)
    client = _client(monkeypatch, SimpleNamespace(config=None, renew_session=renew_session))
    assert client.post('/session/renew').status_code == status
    [finished] = _finished(events)
    assert finished['error'] == {'type': 'ConsoleError', 'code': code, 'handled': True}


def test_retry_after_never_points_inside_the_window():
    from src.product_security_v1 import SlidingWindowRateLimiter
    ticks = [0.0]
    limiter = SlidingWindowRateLimiter(now=lambda: ticks[0])
    assert limiter.allow('k', 1) == (True, 0)
    ticks[0] = 0.9
    allowed, retry_after = limiter.allow('k', 1)
    assert not allowed and retry_after == 60
    ticks[0] = 0.9 + retry_after
    assert limiter.allow('k', 1)[0]
