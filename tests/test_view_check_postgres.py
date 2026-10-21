"""Native persistence, fencing and installed HTTP authorization for #807.
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
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
    job_before_denial = service.store.get(row['id'])
    for method, path, kwargs in (
        ('get', '/inzicht/weergavecontrole/'+row['id'], {}),
        ('get', '/inzicht/weergavecontrole/'+row['id']+'/bewijs', {}),
        ('post', '/inzicht/weergavecontrole/'+row['id']+'/annuleren', {'headers': {'Origin':'https://testserver'}}),
        ('post', '/inzicht/document/weergavecontrole', {'data': {**data, 'request_key': uuid4().hex},
                                                     'headers': {'Origin':'https://testserver'}}),
    ):
        denied = getattr(other, method)(path, **kwargs)
        assert denied.status_code == 403
        assert denied.json() == {'error': 'view_check_access_denied'}
    assert service.store.get(row['id']) == job_before_denial
    assert len(service.store.history(document)) == 1
    assert before == (state._envelope(document), state.objects_revision(document))
    # Current roles, not a copied human session, decide the next worker read.
    state.assign_roles(actor_id=author, account_id=reviewer, roles=('researcher',))
    assert scoped.get('/inzicht/document/passages?document='+document).status_code == 403
    assert reviewer_client.get('/inzicht/weergavecontrole/'+row['id']).status_code == 403
    assert reviewer_client.get('/inzicht/weergavecontrole/'+row['id']+'/bewijs').status_code == 403
    assert service.store.get(row['id']) == job_before_denial
    state.assign_roles(actor_id=author, account_id=reviewer, roles=('reviewer',))
    assert scoped.get('/inzicht/document/passages?document='+document).status_code == 200
    # Missing, corrupted and expired evidence remain distinct from authorization.
    assert reviewer_client.get('/inzicht/weergavecontrole/'+row['id']+'/bewijs').status_code == 404
    image = b'\x89PNG\r\n\x1a\nfixture'
    key = f"{row['id']}/1/{sha256(image).hexdigest()}.png"
    manifest = {'key': key, 'sha256': sha256(image).hexdigest(),
                'expires_at': (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    service.store.finish(row['id'], job['attempt'], token, {'evidence': [manifest]})
    evidence_url = '/inzicht/weergavecontrole/'+row['id']+'/bewijs'
    assert reviewer_client.get(evidence_url).status_code == 503
    service.evidence.put(key, b'corrupt')
    assert reviewer_client.get(evidence_url).status_code == 503
    service.evidence.put(key, image)
    evidence = reviewer_client.get(evidence_url)
    assert evidence.status_code == 200 and evidence.content == image
    assert evidence.headers['cache-control'] == 'no-store'
    original_get = service.evidence.get
    def revoke_during_download(key):
        state.assign_roles(actor_id=author, account_id=reviewer, roles=('researcher',))
        return original_get(key)
    service.evidence.get = revoke_during_download
    assert reviewer_client.get(evidence_url).status_code == 403
    service.evidence.get = original_get
    state.assign_roles(actor_id=author, account_id=reviewer, roles=('reviewer',))
    manifest['expires_at'] = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    from psycopg.types.json import Jsonb
    with psycopg.connect(complete_postgres.dsn) as con:
        con.execute('UPDATE workflow.view_checks SET result=%s WHERE id=%s', (Jsonb({'evidence': [manifest]}), row['id']))
    assert reviewer_client.get(evidence_url).status_code == 410
    assert before == (state._envelope(document), state.objects_revision(document))
    # Cancellation returns to the job's stored historical reference, not a query override.
    pinned = {**context(state, reviewer, document), 'attempt_id': 'historical-reference'}
    pending = service.store.register(reviewer, document, uuid4().hex, pinned)
    cancelled = reviewer_client.post('/inzicht/weergavecontrole/'+pending['id']+'/annuleren',
                                    headers={'Origin': 'https://testserver'}, follow_redirects=False)
    assert cancelled.status_code == 303
    assert 'attempt=historical-reference' in cancelled.headers['location']
    assert cancelled.headers['location'].endswith('#weergavecontrole')
    assert service.store.get(pending['id'])['state'] == 'cancelled'


@pytest.mark.parametrize('unsupported', ['unknown_attempt', 'decision_graph'])
def test_panel_does_not_offer_an_unsupported_scenario(unsupported, production_console, production_app, complete_postgres, tmp_path, monkeypatch):
    from src.view_check import panel
    from tests.test_availability_repair import accounts, bind, provider, login, upload
    state = production_console(processing_binder=lambda state: None)
    _, reviewer = accounts(state)
    bind(state, provider)
    app = production_app(state)
    client = TestClient(app, base_url='https://testserver')
    login(client)
    document = upload(client, reviewer).headers['location'].split('document=')[1].split('&')[0]
    service = configure(app, state, complete_postgres, tmp_path / 'evidence')
    pinned = context(state, reviewer, document)
    old = service.store.register(reviewer, document, uuid4().hex, pinned)
    attempt = 'unknown-attempt' if unsupported == 'unknown_attempt' else ''
    if unsupported == 'decision_graph':
        envelope = state._envelope
        monkeypatch.setattr(state, '_envelope', lambda sid: {**envelope(sid), 'decision_graph': {}})
    html = panel(app, state, state._account(reviewer), document, attempt)
    assert 'Controleer weergave</button>' not in html
    assert 'niet beschikbaar' in html
    assert old['id'] in html  # Existing investigations remain accessible.


def test_second_expired_lease_is_terminal_and_does_not_block_next_job(complete_postgres):
    store = store_for(complete_postgres)
    first = store.register('reviewer', 'one', 'one', {})
    second = store.register('reviewer', 'two', 'two', {})
    tokens = []
    for attempt in (1, 2):
        job, token = store.claim()
        tokens.append(token)
        assert job['id'] == first['id'] and job['attempt'] == attempt
        with psycopg.connect(complete_postgres.dsn) as con:
            con.execute("UPDATE workflow.view_checks SET lease_until=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE id=%s", (job['id'],))
    next_job, _ = store.claim()
    assert next_job['id'] == second['id']
    assert store.get(first['id'])['state'] == 'failed'
    assert store.get(first['id'])['result']['reason'] == 'worker_interrupted'
    for attempt, token in enumerate(tokens, 1):
        assert store.capability(token) is None
        assert not store.finish(first['id'], attempt, token, {'checks': []})


@pytest.mark.parametrize('interruption', ['none', 'browser_revocation', 'upload_revocation', 'cancel', 'storage_failure'])
def test_worker_activation_rechecks_authority_and_preserves_document(interruption, production_console, production_app, complete_postgres, tmp_path, monkeypatch):
    import base64
    import json
    from types import SimpleNamespace
    from src.view_check import CHECK_IDS
    from tests.test_availability_repair import accounts, bind, provider, login, upload
    state = production_console(processing_binder=lambda state: None)
    author, reviewer = accounts(state)
    bind(state, provider)
    app = production_app(state)
    client = TestClient(app, base_url='https://testserver')
    login(client)
    document = upload(client, reviewer).headers['location'].split('document=')[1].split('&')[0]
    service = configure(app, state, complete_postgres, tmp_path / 'evidence')
    pinned = {**context(state, reviewer, document), 'origin': service.config.origin}
    row = service.store.register(reviewer, document, uuid4().hex, pinned)
    before = deepcopy(state._envelope(document)), state.objects_revision(document)
    monkeypatch.setenv('METIS_LLM_API_KEY', 'must-stay-in-parent')

    def revoke():
        state.assign_roles(actor_id=author, account_id=reviewer, roles=('researcher',))

    def browser(*args, **kwargs):
        # Only the process transport is doubled; PG claims, auth and activation run.
        assert 'METIS_LLM_API_KEY' not in kwargs['env']
        assert set(kwargs['env']) <= {'PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT', 'METIS_PLAYWRIGHT_MODULE', 'METIS_BROWSER_EXECUTABLE'}
        if interruption == 'browser_revocation':
            revoke()
        if interruption == 'cancel':
            service.store.cancel(row['id'], reviewer)
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            'checks': [{'id': key, 'verdict': 'pass', 'expected': 1, 'observed': 1} for key in CHECK_IDS],
            'screenshot': base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()}))

    original_put = service.evidence.put
    def put(key, data):
        if interruption == 'storage_failure':
            raise OSError('private storage details must not be retained')
        original_put(key, data)
        if interruption == 'upload_revocation':
            revoke()
    monkeypatch.setattr('src.view_check.subprocess.run', browser)
    monkeypatch.setattr(service.evidence, 'put', put)
    service.execute_one()
    result = service.store.get(row['id'])
    assert before == (state._envelope(document), state.objects_revision(document))
    if interruption == 'none':
        assert result['state'] == 'completed' and len(result['result']['evidence']) == 1
    elif interruption == 'cancel':
        assert result['state'] == 'cancelled' and result['result'] is None
    else:
        assert result['state'] == 'failed'
        assert result['result']['reason'] == 'investigation_unavailable'
        assert result['result']['evidence'] == []
        assert all(check['verdict'] == 'not_established' for check in result['result']['checks'])
        assert 'private storage details' not in json.dumps(result['result'])
