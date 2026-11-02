"""D1: native Entra signin is independent of a protected review decision.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from src.console_entra_v1 import EntraIdentity
from src.operations_console_v1 import ConsoleError
from src.workflows.account_retirement_v1 import retire_account
from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from src.workflows.workflow_transaction_v1 import workflow_transaction_active
from tests.test_console_entra_v1 import config, claims, ADMIN, USER
from tests.test_t9_review_knowledge_authority import _console, _approve


def test_entra_signin_finishes_while_review_is_protected_then_retirement_denies_next_command(
    tmp_path, production_console, monkeypatch,
):
    console, reviewer, sid, focal = _console(tmp_path, production_console=production_console)
    uploader = console._envelope(sid)['uploader_account_id']
    store = PostgresWorkflowIdentityStore(console.workflow_identity_store.config)
    identity = EntraIdentity(store, config({ADMIN: uploader, USER: reviewer['account_id']}))
    identity.prepare()
    entered, release = Event(), Event()
    original = console.workflow_document_store.apply_review_changes

    def paused(*args, **kwargs):
        assert workflow_transaction_active()
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)
    monkeypatch.setattr(console.workflow_document_store, 'apply_review_changes', paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        review = pool.submit(_approve, console, reviewer, sid, focal)
        assert entered.wait(10)
        login = pool.submit(identity.sign_in, claims(USER, ['Metis.Reviewer']))
        try:
            assert login.result(timeout=1)['account_id'] == reviewer['account_id']
        finally:
            release.set()
        review.result(timeout=15)
    assert next(o for o in console.snapshot_objects(sid) if o['object_id'] == focal['object_id'])[
        'governance']['validation_status'] == 'approved'
    publisher = console.create_account(username='retirement-owner', password='fixture-only', roles=('publisher',))
    with store._connect() as con:
        retire_account(con, account_id=reviewer['account_id'], actor_id=publisher['account_id'],
                       reason='Synthetic D1 next-command check', apply=True)
    before = console.workflow_review_store.read_events()
    with pytest.raises(ConsoleError, match='not_authenticated'):
        _approve(console, reviewer, sid, focal)
    assert console.workflow_review_store.read_events() == before
