"""Installed application authorization/storage regression in the pinned CI environment.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: metrics teller/noemer score-must-drop
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


def test_selected_shadow_view_is_authorized_and_cannot_write(console, monkeypatch):
    actor, reviewer = accounts(console)
    bind(console, provider)
    sid = receive(console, actor, reviewer, 'forecast')
    console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='forecast-read', expected_revision=console.objects_revision(sid))
    outsider = console.create_account(username='forecast.outsider', password='fixture-only', roles=('reviewer',))
    publisher = console.create_account(username='forecast.publisher', password='fixture-only', roles=('publisher',))
    async def no_dispatch(_self):
        pass
    monkeypatch.setattr(SourceProcessingDispatcher, 'start', no_dispatch)
    app = create_console_app(console)
    before = deepcopy(console._envelope(sid))
    def forbidden(*args, **kwargs):
        raise AssertionError('shadow GET attempted a durable transition')
    for name in ('_commit_prepared_store', 'execute_source_selection', 'reserve_source_selection'):
        monkeypatch.setattr(console, name, forbidden)
    with TestClient(app, base_url='https://testserver') as client:
        assert client.get('/source-selection', params={'document': sid}).status_code == 401
        for username in ('author', 'reviewer'):
            login(client, username)
            response = client.get('/source-selection', params={'document': sid})
            assert response.status_code == 200
            assert response.headers['cache-control'] == 'no-store'
            assert 'id="deadline-schaduwprognose"' in response.text
            assert 'HOLD' in response.text
            assert 'id="deadline-schaduwprognose"' not in client.get('/source-selection').text
        for account in (outsider, publisher):
            login(client, account['username'])
            response = client.get('/source-selection', params={'document': sid})
            assert response.status_code in (400, 403)
            assert 'id="deadline-schaduwprognose"' not in response.text
    assert console._envelope(sid) == before
