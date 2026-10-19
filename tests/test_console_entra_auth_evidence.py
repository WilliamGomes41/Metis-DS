"""Every fail-closed answer of the Entra boundary leaves explainable evidence.

Incident 2026-10-19: a scanner caused three /auth/microsoft 503s whose cause was
swallowed before diagnostics could record it, and dotfile probes started
Entra authentication flows.
"""
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.console_entra_routes_v1 import install_entra_routes
from src.operations_console_v1 import ConsoleError
from src.request_diagnostics_v1 import RequestDiagnostics, _LOGGER


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


@pytest.mark.parametrize('path', ['/.env', '/.git/config', '/.aws/credentials', '/.kube/config'])
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


def test_protected_routes_still_redirect_to_sign_in(monkeypatch, events):
    def renew_session(token):
        raise ConsoleError('workflow_session_required')
    client = _client(monkeypatch, SimpleNamespace(config=None, renew_session=renew_session))
    for path in ('/settings', '/.well-known/unknown', '/environment'):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'].startswith('/auth/microsoft?next=')
