"""Historical identity remains readable, but cannot regain access.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from src.console_entra_v1 import EntraIdentity
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.workflows.account_retirement_v1 import retire_account
from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from tests.test_console_entra_v1 import config, claims, console, ADMIN, USER
from tests.test_workflow_chain_recovery_v1 import recovery_postgres, _install_schema, _seed_workflow  # noqa: F401


def test_retirement_cutover_restart_and_recovery(recovery_postgres, tmp_path):
    _seed_workflow(recovery_postgres)
    state = console(tmp_path, recovery_postgres)
    store = state.workflow_identity_store
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    before = adapter.export_state()
    with store._connect() as con:
        planned = retire_account(con, account_id='acc-reviewer', actor_id='acc-uploader', reason='Historical test account')
    assert planned['status'] == 'PLANNED' and planned['mutation'] == 'none'
    assert store.account_by_id('acc-reviewer')['retirement'] is None
    with pytest.raises(ConsoleError, match='entra_legacy_binding_required'):
        EntraIdentity(store, config({ADMIN: 'acc-uploader'})).prepare()
    with store._connect() as con:
        result = retire_account(con, account_id='acc-reviewer', actor_id='acc-uploader', reason='Historical test account', apply=True)
    assert result['status'] == 'RETIRED'
    with store._connect() as con:
        repeat = retire_account(con, account_id='acc-reviewer', actor_id='acc-uploader', reason='Retry', apply=True)
    assert repeat['retirement'] == result['retirement'] and repeat['mutation'] == 'none'
    assert 'acc-reviewer' not in [a['account_id'] for a in state.list_reviewer_accounts()]
    with pytest.raises(ConsoleError, match='unknown_reviewer'):
        state._resolve_named_reviewers(['acc-reviewer'], 'acc-uploader')
    after = adapter.export_state()
    for table in before['workflow_tables']:
        if table != 'accounts':
            assert after['workflow_tables'][table] == before['workflow_tables'][table]
    assert after['tables'] == before['tables']
    fresh = console(tmp_path / 'restart', recovery_postgres)
    assert any(a.get('retirement') for a in fresh.list_accounts())
    identity = EntraIdentity(store, config({ADMIN: 'acc-uploader'}))
    identity.prepare()
    admin = identity.sign_in(claims(ADMIN, ['Metis.Publisher']))
    assert admin['account_id'] == 'acc-uploader'
    # Even an explicitly mapped retired identity must not acquire Entra access.
    identity = EntraIdentity(store, config({USER: 'acc-reviewer'}))
    identity.prepare()
    with pytest.raises(ConsoleError, match='entra_access_denied'):
        identity.sign_in(claims(USER))
    snapshot = adapter.export_state()
    _install_schema(recovery_postgres.dsn)
    adapter.restore_state(snapshot)
    restored = adapter.export_state()
    assert restored['workflow_tables']['accounts'] == snapshot['workflow_tables']['accounts']
    fresh = EntraIdentity(PostgresWorkflowIdentityStore(recovery_postgres), config())
    fresh.prepare()
    with pytest.raises(ConsoleError):
        fresh.sign_in(claims(USER))


def test_password_sessions_ui_and_database_bypass(recovery_postgres, tmp_path):
    state = console(tmp_path, recovery_postgres)
    actor = state.create_account('owner', 'owner-password', ['publisher'])
    target = state.create_account('historical', 'old-password', ['reviewer'])
    token = state.authenticate('historical', 'old-password')['token']
    admin_token = state.authenticate('owner', 'owner-password')['token']
    store = state.workflow_identity_store
    with store._connect() as con:
        retire_account(con, account_id=target['account_id'], actor_id=actor['account_id'], reason='Test complete', apply=True)
    with pytest.raises(ConsoleError, match='invalid_credentials'):
        state.authenticate('historical', 'old-password')
    with pytest.raises(ConsoleError, match='not_authenticated'):
        state.session_account(token)
    client = TestClient(create_console_app(state))
    # The existing application cookie name is console_session.
    client.cookies.set('console_session', admin_token)
    response = client.get('/accounts')
    assert 'Historisch account' in response.text
    with store._connect() as con:
        con.execute("UPDATE workflow.accounts SET password_hash='attempted-reset' WHERE account_id=%s", (target['account_id'],))
    assert store.account_by_id(target['account_id'])['password_hash'] == ''
    for sql in [
        'UPDATE workflow.accounts SET retirement=NULL WHERE account_id=%s',
        "INSERT INTO workflow.sessions(token_hash,account_id,created_at,expires_at) VALUES('bypass',%s,now(),now()+interval '1 hour')",
        'UPDATE workflow.sessions SET revoked_at=NULL WHERE account_id=%s',
    ]:
        with pytest.raises(Exception, match='account_retir'):
            with store._connect() as con:
                con.execute(sql, (target['account_id'],))
    assert store.update_roles(target['account_id'], ['publisher']) is None


def test_invalid_actor_and_failed_transaction_leave_account_active(recovery_postgres, tmp_path):
    state = console(tmp_path, recovery_postgres)
    actor = state.create_account('owner', 'password', ['publisher'])
    target = state.create_account('reviewer', 'password', ['reviewer'])
    store = state.workflow_identity_store
    for actor_id in [target['account_id'], 'missing']:
        with pytest.raises(ConsoleError):
            with store._connect() as con:
                retire_account(con, account_id=target['account_id'], actor_id=actor_id, reason='test', apply=True)
    with pytest.raises(RuntimeError, match='rollback'):
        with store._connect() as con:
            retire_account(con, account_id=target['account_id'], actor_id=actor['account_id'], reason='test', apply=True)
            raise RuntimeError('rollback')
    assert state.authenticate('reviewer', 'password')['token']


def test_session_creation_waits_for_concurrent_retirement(recovery_postgres, tmp_path):
    state = console(tmp_path, recovery_postgres)
    actor = state.create_account('owner', 'password', ['publisher'])
    target = state.create_account('reviewer', 'password', ['reviewer'])
    store = state.workflow_identity_store
    started = Event()
    def insert_session():
        started.set()
        with store._connect() as other:
            other.execute("SET lock_timeout='5s'")
            other.execute("INSERT INTO workflow.sessions(token_hash,account_id,created_at,expires_at) VALUES('race',%s,now(),now()+interval '1 hour')", (target['account_id'],))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with store._connect() as con:
            retire_account(con, account_id=target['account_id'], actor_id=actor['account_id'], reason='test', apply=True)
            future = pool.submit(insert_session)
            assert started.wait(2)
        with pytest.raises(Exception, match='account_retired'):
            future.result(timeout=10)


def test_operator_apply_requires_exact_confirmation_before_connection(monkeypatch, capsys):
    from scripts import retire_workflow_account as command
    def forbidden(**kwargs):
        pytest.fail('must not connect before target confirmation')
    monkeypatch.setattr(command, 'connect_entra', forbidden)
    monkeypatch.setattr('sys.argv', ['retire_workflow_account', 'apply', '--host', 'host',
        '--database', 'db', '--user', 'admin', '--account-id', 'historical',
        '--actor-id', 'publisher', '--reason', 'test'])
    assert command.main() == 2
    assert 'account_retirement_confirmation_required' in capsys.readouterr().out


def test_historical_account_presentation_and_console_denial(tmp_path):
    # UI/console proof only; the tests above cover real database enforcement.
    from tests.test_workflow_identity_postgres_v1 import SharedIdentityStore, _console
    shared = SharedIdentityStore()
    state = _console(tmp_path, shared, 'ui')
    owner = state.create_account('owner', 'password', ['publisher'])
    historical = state.create_account('historical', 'password', ['reviewer'])
    old_token = state.authenticate('historical', 'password')['token']
    owner_token = state.authenticate('owner', 'password')['token']
    shared.accounts[historical['account_id']]['retirement'] = {
        'actor': owner['account_id'], 'reason': 'Test completed', 'at': '2026-09-30T12:00:00Z'}
    for action in [lambda: state.authenticate('historical', 'password'),
                   lambda: state.session_account(old_token),
                   lambda: state._require_role(historical['account_id'], 'reviewer')]:
        with pytest.raises(ConsoleError):
            action()
    assert state.list_reviewer_accounts() == []
    client = TestClient(create_console_app(state))
    client.cookies.set('console_session', owner_token)
    response = client.get('/accounts')
    assert response.status_code == 200
    assert 'Historisch account — aanmelden uitgeschakeld' in response.text
    assert 'Test completed' not in response.text
