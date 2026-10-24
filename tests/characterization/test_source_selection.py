"""Stored progress overview, including refresh without selecting a detail."""
import html
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from .support import console_at, command, ACTOR


@pytest.mark.parametrize('dispatch_state', ['pending', 'claimed'])
def test_source_overview_running_golden(tmp_path, production_console, golden, dispatch_state):
    from src.source_selection_ui_v1 import install
    console = console_at(tmp_path, production_console=production_console)
    receipt = console.receive_source(**command())
    sid = receipt['snapshot_id']
    console.reserve_source_selection(actor_id=ACTOR, snapshot_id=sid, command_id='golden-running',
                                     expected_revision=console.objects_revision(sid))
    env = console.workflow_document_store.get_envelope(sid)
    env['processing_attempts'][-1]['dispatch']['state'] = dispatch_state
    console.workflow_document_store.write_bundle(envelope=env)
    app = FastAPI()
    install(app, console, lambda request: console._account(ACTOR), lambda body: body, lambda *_: '', html.escape)
    response = TestClient(app).get('/source-selection')
    assert response.status_code == 200
    assert 'window.location.reload()' in response.text
    assert 'action="/source-selection/start"' not in response.text
    golden('source_selection', dispatch_state, {'html': response.text})
