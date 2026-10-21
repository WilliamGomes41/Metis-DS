"""Native persistence, fencing and installed HTTP authorization for #807.
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg
import pytest

from src.view_check import COOKIE, ViewCheckConfig, ViewChecks, context
from src.view_check_store import ViewCheckConflict, ViewCheckStore


def store_for(config):
    return ViewCheckStore(lambda: psycopg.connect(config.dsn))


def test_registration_deduplicates_survives_restart_and_fences_late_workers(complete_postgres):
    store = store_for(complete_postgres)
    store.verify()
    row = store.register('reviewer', 'snapshot', 'key', {'revision': 'one'})
    assert store.register('reviewer', 'snapshot', 'other-key', {'revision': 'one'})['id'] == row['id']
    with pytest.raises(ViewCheckConflict):
        store.register('reviewer', 'other-document', 'key', {'revision': 'one'})
    job, token = store.claim()
    assert store.claim() is None
    assert store.capability(token)['id'] == row['id']
    # Separate store/connection is the restart boundary, not a Python cache.
    restarted = store_for(complete_postgres)
    assert restarted.get(row['id'])['state'] == 'running'
    with psycopg.connect(complete_postgres.dsn) as con:
        con.execute("UPDATE workflow.view_checks SET lease_until=CURRENT_TIMESTAMP-INTERVAL '1 second'")
    retried, new_token = restarted.claim()
    assert retried['attempt'] == 2 and restarted.capability(token) is None
    assert not restarted.finish(row['id'], job['attempt'], token, {'reason': 'obsolete'})
    assert restarted.finish(row['id'], retried['attempt'], new_token, {'checks': [], 'reason': 'completed'})
    assert restarted.get(row['id'])['result']['reason'] == 'completed'
    assert restarted.register('reviewer', 'snapshot', 'other-key', {'revision': 'one'})['id'] == row['id']
    assert restarted.capability(new_token) is None
    assert len(restarted.get(row['id'])['events']) == 5


def test_concurrent_registration_has_one_active_task_and_cancel_revokes_capability(complete_postgres):
    from concurrent.futures import ThreadPoolExecutor
    store = store_for(complete_postgres)
    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(lambda key: store.register('a', 'd', key, {'revision': 'v'}), ['one', 'two']))
    assert rows[0]['id'] == rows[1]['id']
    job, token = store.claim()
    assert not store.cancel(job['id'], 'outsider')
    assert store.cancel(job['id'], 'a')
    assert store.capability(token) is None
    assert not store.finish(job['id'], job['attempt'], token, {})
    assert store.get(job['id'])['state'] == 'cancelled'


class PrivateTestEvidence:
    """Test transport replacement for private Blob bytes; no application routes."""
    def __init__(self, root):
        self.root = Path(root)

    def put(self, key, data):
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key):
        return (self.root / key).read_bytes()


def configure(app, state, config, directory, origin='https://testserver', module=None, browser=None):
    connect = getattr(state.workflow_document_store, '_metis_workflow_original_connect', state.workflow_document_store._connect)
    service = ViewChecks(state, ViewCheckStore(connect),
                         ViewCheckConfig(origin, module or str(Path(__file__).resolve().parent), browser or sys.executable),
                         PrivateTestEvidence(directory))
    app.state.view_checks = service
    return service


def test_http_scope_origin_revision_and_revocation_leave_domain_state_unchanged(production_console, production_app, complete_postgres, tmp_path):
    from tests.test_availability_repair import accounts, bind, provider, login, upload, start
    state = production_console(processing_binder=lambda state: None)
    author, reviewer = accounts(state)
    outsider = state.create_account(username='outsider', password='fixture-only', roles=('reviewer',))
    bind(state, provider)
    app = production_app(state)
    client = TestClient(app, base_url='https://testserver')
    login(client)
    response = upload(client, reviewer)
    document = response.headers['location'].split('document=')[1].split('&')[0]
    # Receipt is sufficient: no selection or model work is needed for registration.
    service = configure(app, state, complete_postgres, tmp_path / 'evidence')
    reviewer_client = TestClient(app, base_url='https://testserver')
    login(reviewer_client, 'reviewer')
    before = deepcopy(state._envelope(document)), state.objects_revision(document)
    data = {'document': document, 'request_key': uuid4().hex, 'expected_revision': before[1]}
    assert reviewer_client.post('/inzicht/document/weergavecontrole', data=data, follow_redirects=False).status_code == 403
    response = reviewer_client.post('/inzicht/document/weergavecontrole', data=data, headers={'Origin':'https://testserver'}, follow_redirects=False)
    assert response.status_code == 303
    row = service.store.history(document)[0]
    assert reviewer_client.get('/inzicht/weergavecontrole/'+row['id']).json()['state'] == 'queued'
    page = reviewer_client.get('/inzicht/document?document='+document)
    assert 'Controleer weergave' in page.text and 'In wachtrij' in page.text
    job, token = service.store.claim()
    scoped = TestClient(app, base_url='https://testserver', cookies={COOKIE:token})
    assert scoped.post('/logout').status_code == 403
    assert scoped.get('/source-selection?document=wrong').status_code == 403
    assert scoped.get('/tree').status_code == 403
    assert scoped.get('/inzicht/document/passages?document='+document).status_code == 200
    other = TestClient(app, base_url='https://testserver')
    login(other, 'outsider')
    assert other.get('/inzicht/weergavecontrole/'+row['id']).status_code == 403
    assert before == (state._envelope(document), state.objects_revision(document))
    # Current roles, not a copied human session, decide the next worker read.
    original = state._account
    def revoked(identifier, **kwargs):
        account = deepcopy(original(identifier, **kwargs))
        if identifier == reviewer:
            account['retirement'] = {'at': 'now'}
        return account
    state._account = revoked
    assert scoped.get('/inzicht/document/passages?document='+document).status_code == 403
