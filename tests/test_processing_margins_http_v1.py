"""Installed app/storage proof; requires the repository's pinned test environment.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: metrics teller/noemer score-must-drop
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.source_processing_dispatch_v1 import SourceProcessingDispatcher
from tests.test_availability_repair import accounts, bind, provider, login
from tests.test_source_dispatch_hardening import console, receive  # noqa: F401
from tests.complete_workflow_support import complete_postgres as workflow_postgres  # noqa: F401


def test_installed_trace_and_diagnosis_keep_processing_authority_and_role_scope(console, monkeypatch):
    actor, reviewer = accounts(console)
    bind(console, provider)
    sid = receive(console, actor, reviewer, 'margins')
    reserved, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='margins-read', expected_revision=console.objects_revision(sid))
    publisher = console.create_account(username='publisher.margins', password='fixture-only', roles=('publisher',))
    outsider = console.create_account(username='outsider.margins', password='fixture-only', roles=('reviewer',))
    # Observe the reserved pending attempt; background execution is unrelated to
    # proving that diagnostic GETs do not perform a transition.
    async def no_dispatch(_self):
        pass
    monkeypatch.setattr(SourceProcessingDispatcher, 'start', no_dispatch)
    app = create_console_app(console)
    before = deepcopy(console._envelope(sid))
    def forbidden(*args, **kwargs):
        raise AssertionError('diagnostic GET attempted processing or a durable write')
    monkeypatch.setattr(console, '_commit_prepared_store', forbidden)
    monkeypatch.setattr(console, 'execute_source_selection', forbidden)
    monkeypatch.setattr(console, 'reserve_source_selection', forbidden)
    monkeypatch.setattr('src.processing_retry_v1.expire_running', forbidden)
    with TestClient(app, base_url='https://testserver') as client:
        assert client.get('/inzicht/document/verwerkingsspoor', params={'document':sid}).status_code == 401
        assert client.get('/inzicht/document', params={'document':sid}).status_code == 401
        for username in ('author', 'reviewer'):
            login(client, username)
            exported = client.get('/inzicht/document/verwerkingsspoor', params={'document':sid})
            assert exported.status_code == 200
            assert exported.headers['cache-control'] == 'no-store'
            data = exported.json()['processing_margins']
            assert data['attempts'][0]['attempt_id'] == reserved['attempt_id']
            assert data['attempts'][0]['stored_state'] == 'running'
            assert data['attempts'][0]['queue_wait_seconds'] is not None
            diagnosis = client.get('/inzicht/document', params={'document':sid})
            assert diagnosis.status_code == 200
            assert diagnosis.headers['cache-control'] == 'no-store'
            assert 'id="verwerkingsmarges"' in diagnosis.text
            assert 'Een oud checkpoint bewijst geen stilstand' in diagnosis.text
        login(client, publisher['username'])
        assert client.get('/inzicht/document/verwerkingsspoor', params={'document':sid}).status_code == 403
        page = client.get('/inzicht/document', params={'document':sid})
        assert page.status_code == 200
        assert 'id="verwerkingsmarges"' not in page.text
        assert reserved['attempt_id'] not in page.text
        login(client, outsider['username'])
        assert client.get('/inzicht/document/verwerkingsspoor', params={'document':sid}).status_code == 400
        assert client.get('/inzicht/document', params={'document':sid}).status_code == 400
    assert console._envelope(sid) == before
