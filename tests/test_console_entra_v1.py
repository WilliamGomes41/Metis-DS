"""Microsoft sign-in proof; native PostgreSQL execution is mandatory in CI.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import secrets
import time

import pytest
from fastapi.testclient import TestClient

from src.console_entra_v1 import EntraConfig, EntraIdentity, FLOW_COOKIE, admitted_claims, install_entra
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore, PostgresIdentityDurablePublicationConsole
from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter, check_workflow_integrity
from tests.test_workflow_chain_recovery_v1 import recovery_postgres, _install_schema  # noqa: F401

TENANT = '11111111-1111-4111-8111-111111111111'
CLIENT = '22222222-2222-4222-8222-222222222222'
ADMIN = '33333333-3333-4333-8333-333333333333'
USER = '44444444-4444-4444-8444-444444444444'
ORIGIN = 'https://testserver'


def config(bindings=None):
    return EntraConfig(TENANT, CLIENT, 'test-only-secret', ORIGIN, bindings or {})


def claims(oid=USER, roles=None):
    return dict(oid=oid, tid=TENANT, aud=CLIENT, iss=config().authority+'/v2.0',
                exp=int(time.time())+3600, name='Anne Reviewer',
                roles=roles if roles is not None else ['Metis.Reviewer'])


class FakeMicrosoft:
    """Only the external exchange is replaced. SQL, HTTP, policy and sessions are real."""
    def __init__(self):
        self.claims = claims()

    def begin(self):
        return {'auth_uri': 'https://login.microsoftonline.com/test', 'state': secrets.token_urlsafe(24), 'nonce': 'nonce', 'code_verifier': 'verifier'}

    def finish(self, flow, response):
        assert flow['state'] == response['state']
        if response.get('code') == 'bad-nonce':
            raise ValueError('nonce mismatch')
        return deepcopy(self.claims)


def console(root, cfg):
    return PostgresIdentityDurablePublicationConsole(root=root, workflow_identity_store=PostgresWorkflowIdentityStore(cfg))


def app_client(monkeypatch, state, bindings=None):
    monkeypatch.setenv('METIS_CONSOLE_AUTH', 'entra')
    monkeypatch.setenv('METIS_ENTRA_TENANT_ID', TENANT)
    monkeypatch.setenv('METIS_ENTRA_CLIENT_ID', CLIENT)
    monkeypatch.setenv('METIS_ENTRA_CLIENT_SECRET', 'test-only-secret')
    monkeypatch.setenv('METIS_ENTRA_ACCOUNT_BINDINGS_JSON', json.dumps(bindings or {}))
    app = create_console_app(state, trusted_origin=ORIGIN)
    provider = FakeMicrosoft()
    app.state.microsoft_login = provider
    client = TestClient(app, base_url=ORIGIN, headers={'Origin': ORIGIN}, raise_server_exceptions=False)
    return client, provider


def begin(client, store):
    assert client.get('/auth/microsoft', follow_redirects=False).status_code == 303
    with store._connect() as con:
        from src.workflows.workflow_identity_postgres_v1 import _token_hash
        row = con.execute('SELECT payload FROM workflow.entra_flows WHERE browser_hash=%s', (_token_hash(client.cookies[FLOW_COOKIE]),)).fetchone()
    return row['payload']['state']


def login(client, store, *, code='test-code'):
    state = begin(client, store)
    return client.get('/auth/microsoft/callback', params={'state': state, 'code': code}, follow_redirects=False)


@pytest.mark.parametrize('patch', [
    {'tid': USER}, {'aud': USER}, {'iss': 'https://evil.example'}, {'oid': 'not-an-id'},
    {'roles': []}, {'roles': ['publisher']}, {'roles': 'Metis.Publisher'},
    {'exp': 0}, {'nbf': int(time.time())+3600},
])
def test_invalid_identity_and_role_claims_fail_closed(patch):
    with pytest.raises(ConsoleError, match='entra_access_denied'):
        admitted_claims(config(), dict(claims(), **patch))


def test_activation_requires_explicit_valid_configuration_and_postgres(monkeypatch, tmp_path):
    state = OperationsConsole(root=tmp_path)
    assert install_entra(state, None) is None
    monkeypatch.setenv('METIS_CONSOLE_AUTH', 'entra')
    with pytest.raises(ValueError, match='configuration'):
        install_entra(state, None)
    monkeypatch.setenv('METIS_ENTRA_TENANT_ID', TENANT)
    monkeypatch.setenv('METIS_ENTRA_CLIENT_ID', CLIENT)
    monkeypatch.setenv('METIS_ENTRA_CLIENT_SECRET', 'test-only-secret')
    with pytest.raises(ValueError, match='requires_postgres'):
        install_entra(state, ORIGIN)


def test_http_login_migration_revocation_restart_and_no_password_bypass(recovery_postgres, tmp_path, monkeypatch):
    state = console(tmp_path, recovery_postgres)
    admin = state.create_account('admin', 'local-password', ['publisher'])
    reviewer = state.create_account('anne', 'local-password', ['reviewer'])
    old_session = state.authenticate('anne', 'local-password')['token']
    client, provider = app_client(monkeypatch, state, {ADMIN: admin['account_id'], USER: reviewer['account_id']})
    assert 'Inloggen met Microsoft' in client.get('/login').text
    assert 'type="password"' not in client.get('/login').text
    client.cookies.set('console_session', old_session)
    assert client.get('/accounts', follow_redirects=False).status_code == 303
    assert client.post('/login', data={'username': 'anne', 'password': 'local-password'}).status_code >= 400
    for name in ('authenticate', 'create_account', 'assign_roles', 'create_managed_account'):
        with pytest.raises(ConsoleError, match='entra_local_auth_disabled'):
            getattr(state, name)()
    client.cookies.clear()
    assert login(client, state.workflow_identity_store).status_code == 303
    token = client.cookies['console_session']
    assert state.session_account(token)['account_id'] == reviewer['account_id']
    assert len(state.list_accounts()) == 2
    assert 'type="password"' not in client.get('/accounts').text
    assert '/accounts/roles' not in client.get('/accounts').text
    assert client.post('/accounts/access', data={'account_id': admin['account_id'], 'blocked': 'true'}).status_code >= 400

    restarted = console(tmp_path/'restart', recovery_postgres)
    admin_client, admin_provider = app_client(monkeypatch, restarted)
    assert restarted.session_account(token)['account_id'] == reviewer['account_id']
    admin_provider.claims = claims(ADMIN, ['Metis.Publisher'])
    assert login(admin_client, restarted.workflow_identity_store).status_code == 303
    page = admin_client.get('/accounts').text
    assert 'Toegang direct blokkeren' in page and '/accounts/roles' not in page
    assert admin_client.post('/accounts/access', data={'account_id': reviewer['account_id'], 'blocked': 'true'}, follow_redirects=False).status_code == 303
    assert client.get('/accounts', follow_redirects=False).status_code == 303
    assert login(client, state.workflow_identity_store).status_code == 403
    assert admin_client.post('/accounts/access', data={'account_id': reviewer['account_id'], 'blocked': 'false'}, follow_redirects=False).status_code == 303
    with pytest.raises(ConsoleError):
        state.session_account(token)  # Unblocking cannot revive revoked sessions.
    assert login(client, state.workflow_identity_store).status_code == 303
    with state.workflow_identity_store._connect() as con:
        con.execute("UPDATE workflow.sessions SET created_at=CURRENT_TIMESTAMP - interval '8 hours 1 minute', expires_at=CURRENT_TIMESTAMP + interval '1 hour' WHERE account_id=%s", (reviewer['account_id'],))
    assert client.get('/accounts', follow_redirects=False).status_code == 303  # Eight-hour absolute max age.
    assert admin_client.post('/accounts/access', data={'account_id': admin['account_id'], 'blocked': 'true'}).status_code >= 400
    assert admin_client.post('/accounts/access', headers={'Origin': 'https://evil.example'}, data={'account_id': reviewer['account_id'], 'blocked': 'true'}).status_code == 403


def test_entra_session_slides_for_thirty_minutes_warns_and_keeps_eight_hour_cap(recovery_postgres, tmp_path, monkeypatch):
    state = console(tmp_path, recovery_postgres)
    client, _ = app_client(monkeypatch, state)
    assert login(client, state.workflow_identity_store).status_code == 303
    token = client.cookies['console_session']
    account_id = state.session_account(token)['account_id']

    # Status is observational: it must not silently extend the idle deadline.
    with state.workflow_identity_store._connect() as con:
        con.execute(
            "UPDATE workflow.sessions SET created_at=CURRENT_TIMESTAMP - interval '29 minutes', "
            "expires_at=CURRENT_TIMESTAMP + interval '1 minute' WHERE account_id=%s",
            (account_id,),
        )
    status = client.get('/session/status')
    assert status.status_code == 200
    before = status.json()
    assert 0 < before['idle_remaining_seconds'] <= 61
    assert 7 * 60 * 60 < before['absolute_remaining_seconds'] < 8 * 60 * 60

    # A real protected navigation renews idle time and the page carries the warning UI.
    page = client.get('/accounts', follow_redirects=False)
    assert page.status_code == 200
    assert 'data-session-warning' in page.text
    assert 'data-session-renew' in page.text
    renewed = client.get('/session/status').json()
    assert 29 * 60 <= renewed['idle_remaining_seconds'] <= 30 * 60
    assert renewed['remaining_seconds'] <= renewed['absolute_remaining_seconds']

    # Explicit user action may renew too; status polling itself never acts as keep-alive.
    with state.workflow_identity_store._connect() as con:
        con.execute(
            "UPDATE workflow.sessions SET expires_at=CURRENT_TIMESTAMP + interval '1 minute' "
            "WHERE account_id=%s",
            (account_id,),
        )
    passive = client.get('/session/status').json()
    assert passive['idle_remaining_seconds'] <= 61
    active = client.post('/session/renew')
    assert active.status_code == 200
    assert active.json()['idle_remaining_seconds'] >= 29 * 60

    # Idle timeout is still enforced server-side.
    with state.workflow_identity_store._connect() as con:
        con.execute(
            "UPDATE workflow.sessions SET expires_at=CURRENT_TIMESTAMP - interval '1 second' "
            "WHERE account_id=%s",
            (account_id,),
        )
    assert client.get('/accounts', follow_redirects=False).status_code == 303


def test_callback_browser_state_replay_denied_and_no_header_trust(recovery_postgres, tmp_path, monkeypatch):
    state = console(tmp_path, recovery_postgres)
    client, provider = app_client(monkeypatch, state)
    assert client.get('/accounts', headers={'X-MS-CLIENT-PRINCIPAL': 'fake'}, follow_redirects=False).status_code == 303
    nonce = begin(client, state.workflow_identity_store)
    stolen = client.get('/auth/microsoft/callback', params={'state': nonce, 'code': 'code'}, cookies={FLOW_COOKIE: 'wrong'}, follow_redirects=False)
    assert stolen.status_code == 403
    nonce = begin(client, state.workflow_identity_store)
    assert client.get('/auth/microsoft/callback', params={'state': 'wrong', 'code': 'code'}, follow_redirects=False).status_code == 403
    assert client.get('/auth/microsoft/callback', params={'state': nonce, 'code': 'code'}, follow_redirects=False).status_code == 403
    assert login(client, state.workflow_identity_store, code='bad-nonce').status_code == 403
    assert not state.list_accounts()
    provider.claims = claims(roles=[])
    assert login(client, state.workflow_identity_store).status_code == 403
    assert not state.list_accounts()
    provider.claims = claims()
    response = login(client, state.workflow_identity_store)
    assert response.status_code == 303
    assert response.headers['cache-control'] == 'no-store'
    assert 'Secure' in response.headers['set-cookie'] and 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/auth/microsoft/callback', params={'state': nonce, 'code': 'code'}, follow_redirects=False).status_code == 403


def test_explicit_binding_atomicity_and_concurrent_provisioning(recovery_postgres, tmp_path):
    state = console(tmp_path, recovery_postgres)
    a = state.create_account('anne', 'password', ['reviewer'])
    b = state.create_account('bert', 'password', ['reviewer'])
    store = state.workflow_identity_store
    with pytest.raises(ConsoleError, match='binding_required'):
        EntraIdentity(store, config({USER: a['account_id']})).prepare()
    with store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.entra_identities').fetchone()['n'] == 0
    identity = EntraIdentity(store, config({USER: a['account_id'], ADMIN: b['account_id']}))
    identity.prepare()
    identity.prepare()
    with pytest.raises(ConsoleError, match='binding_conflict'):
        EntraIdentity(store, config({ADMIN: a['account_id'], USER: b['account_id']})).prepare()
    new_oid = '55555555-5555-4555-8555-555555555555'
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(lambda _: identity.sign_in(claims(new_oid)), range(2)))
    assert result[0]['account_id'] == result[1]['account_id']
    assert len(state.list_accounts()) == 3
    # Display name/email similarities NEVER bind to an existing reviewer.
    assert result[0]['account_id'] != a['account_id']
    current = identity.sign_in(claims(new_oid, ['Metis.Publisher']))
    with pytest.raises(ConsoleError):
        identity.session_account(result[0]['token'])
    assert identity.session_account(current['token'])['roles'] == ['publisher']


def test_recovery_preserves_binding_and_block_but_never_revives_entra_sessions(recovery_postgres, tmp_path):
    store = PostgresWorkflowIdentityStore(recovery_postgres)
    identity = EntraIdentity(store, config())
    identity.prepare()
    admin = identity.sign_in(claims(ADMIN, ['Metis.Publisher']))
    user = identity.sign_in(claims())
    identity.set_blocked(actor_token=admin['token'], account_id=user['account_id'], blocked=True)
    identity.save_flow({'state': 'must-not-restore', 'code_verifier': 'must-not-export'})
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    snapshot = adapter.export_state()
    assert check_workflow_integrity(snapshot)['ok']
    assert len(snapshot['entra_identities']) == 2
    assert 'must-not-export' not in json.dumps(snapshot)
    _install_schema(recovery_postgres.dsn)
    adapter.restore_state(snapshot)
    fresh = EntraIdentity(PostgresWorkflowIdentityStore(recovery_postgres), config())
    fresh.prepare()
    assert fresh.access_rows()[user['account_id']] is True
    with pytest.raises(ConsoleError):
        fresh.sign_in(claims())
    with pytest.raises(ConsoleError):
        fresh.session_account(admin['token'])
    assert fresh.sign_in(claims(ADMIN, ['Metis.Publisher']))['account_id'] == admin['account_id']


def test_real_msal_code_exchange_binds_nonce_state_and_pkce():
    """Exercise MSAL itself; replace only Microsoft's HTTPS endpoints."""
    import jwt
    from urllib.parse import parse_qs, urlsplit
    from msal import ConfidentialClientApplication
    from src.console_entra_v1 import MicrosoftLogin

    class Response:
        status_code = 200
        headers = {}
        def __init__(self, data):
            self.text = json.dumps(data)
        def json(self):
            return json.loads(self.text)
        def raise_for_status(self):
            pass

    class MicrosoftHTTP:
        nonce = ''
        posted = None
        def get(self, url, **kwargs):
            return Response({
                'authorization_endpoint': config().authority+'/oauth2/v2.0/authorize',
                'token_endpoint': config().authority+'/oauth2/v2.0/token',
                'issuer': config().authority+'/v2.0',
            })
        def post(self, url, data=None, **kwargs):
            self.posted = data
            token_claims = dict(claims(), sub=USER, iat=int(time.time()), nonce=self.nonce)
            return Response({'token_type': 'Bearer', 'expires_in': 3600,
                             'id_token': jwt.encode(token_claims, 'test-signing-key-at-least-32-bytes-long', algorithm='HS256')})

    http = MicrosoftHTTP()
    provider = MicrosoftLogin(config())
    provider._factory = lambda: ConfidentialClientApplication(
        CLIENT, client_credential='test-only-secret', authority=config().authority,
        http_client=http, instance_discovery=False, exclude_scopes=['offline_access'],
    )
    flow = provider.begin()
    query = parse_qs(urlsplit(flow['auth_uri']).query)
    assert query['code_challenge_method'] == ['S256']
    assert 'offline_access' not in query['scope'][0]
    assert query['redirect_uri'] == [config().redirect_uri]
    http.nonce = query['nonce'][0]
    result = provider.finish(flow, {'state': flow['state'], 'code': 'code'})
    assert admitted_claims(config(), result)[0] == USER
    assert http.posted['code_verifier'] == flow['code_verifier']
    with pytest.raises(ValueError):
        provider.finish(flow, {'state': 'wrong-state', 'code': 'code'})
    http.nonce = 'wrong-nonce'
    with pytest.raises(RuntimeError):
        provider.finish(flow, {'state': flow['state'], 'code': 'code'})


def test_sql_failure_rolls_back_provisioning_and_session(recovery_postgres):
    store = PostgresWorkflowIdentityStore(recovery_postgres)
    identity = EntraIdentity(store, config())
    identity.prepare()
    with store._connect() as con:
        con.execute("CREATE FUNCTION workflow.reject_test_session() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'simulated session write failure'; END; $$")
        con.execute('CREATE TRIGGER reject_test_session BEFORE INSERT ON workflow.entra_sessions FOR EACH ROW EXECUTE FUNCTION workflow.reject_test_session()')
    with pytest.raises(Exception, match='simulated session write failure'):
        identity.sign_in(claims())
    with store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.accounts').fetchone()['n'] == 0
        assert con.execute('SELECT count(*) AS n FROM workflow.entra_identities').fetchone()['n'] == 0
        assert con.execute('SELECT count(*) AS n FROM workflow.sessions').fetchone()['n'] == 0
        con.execute('DROP TRIGGER reject_test_session ON workflow.entra_sessions')
    session = identity.sign_in(claims())
    assert identity.session_account(session['token'])['account_id'] == session['account_id']


def test_postgres_outage_cannot_fall_back_to_local_session(recovery_postgres, tmp_path, monkeypatch):
    state = console(tmp_path, recovery_postgres)
    client, _ = app_client(monkeypatch, state)
    assert login(client, state.workflow_identity_store).status_code == 303
    def unavailable():
        raise RuntimeError('database down')
    client.cookies.set(FLOW_COOKIE, 'saved-handshake')
    monkeypatch.setattr(state.workflow_identity_store, '_connect', unavailable)
    assert client.get('/accounts', follow_redirects=False).status_code == 503
    client.cookies.set(FLOW_COOKIE, 'saved-handshake')
    response = client.get('/auth/microsoft/callback', params={'state': 'state', 'code': 'SECRET-CODE'}, follow_redirects=False)
    assert response.status_code == 503
    assert 'SECRET-CODE' not in response.text and 'database down' not in response.text


def test_navigation_return_replay_and_expired_handshake(recovery_postgres, tmp_path, monkeypatch):
    from src.workflows.workflow_identity_postgres_v1 import _token_hash
    state = console(tmp_path, recovery_postgres)
    client, _ = app_client(monkeypatch, state)
    response = client.get('/review?document=example', follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'].startswith('/auth/microsoft?next=')
    for target, expected in [('/accounts', '/accounts'), ('https://evil.example', '/'), ('//evil.example', '/'), ('/\\evil.example', '/')]:
        assert client.get('/auth/microsoft', params={'next': target}, follow_redirects=False).status_code == 303
        handle = client.cookies[FLOW_COOKIE]
        with state.workflow_identity_store._connect() as con:
            flow = con.execute('SELECT payload FROM workflow.entra_flows WHERE browser_hash=%s', (_token_hash(handle),)).fetchone()['payload']
        response = client.get('/auth/microsoft/callback', params={'state': flow['state'], 'code': 'code'}, follow_redirects=False)
        assert response.status_code == 303 and response.headers['location'] == expected
        client.cookies.set(FLOW_COOKIE, handle)
        assert client.get('/auth/microsoft/callback', params={'state': flow['state'], 'code': 'code'}, follow_redirects=False).status_code == 403
        client.cookies.clear()
    nonce = begin(client, state.workflow_identity_store)
    with state.workflow_identity_store._connect() as con:
        con.execute("UPDATE workflow.entra_flows SET expires_at=CURRENT_TIMESTAMP - interval '1 second'")
    assert client.get('/auth/microsoft/callback', params={'state': nonce, 'code': 'code'}, follow_redirects=False).status_code == 403
    assert len(state.list_accounts()) == 1
