"""Shared workflow identity regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.durable_publication_console_v1 import DurablePublicationConsole
from src.operations_console_v1 import ConsoleError
from src.workflow_identity_postgres_v1 import (
    PostgresIdentityDurablePublicationConsole,
    _token_hash,
)


class SharedIdentityStore:
    """Small shared test double for the PostgreSQL identity contract."""

    def __init__(self) -> None:
        self.accounts: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.verify_calls = 0
        self.migration_calls = 0

    def verify_schema(self) -> None:
        self.verify_calls += 1

    def migrate_legacy_if_empty(self, accounts: dict, sessions: dict) -> bool:
        self.migration_calls += 1
        if self.accounts:
            return False
        self.accounts = deepcopy(accounts)
        for token, session in sessions.items():
            self.sessions[_token_hash(token)] = deepcopy(session)
        return bool(accounts)

    def list_accounts(self) -> list[dict]:
        return [deepcopy(row) for row in self.accounts.values()]

    def account_by_id(self, account_id: str) -> dict | None:
        row = self.accounts.get(account_id)
        return deepcopy(row) if row else None

    def account_by_username(self, username: str) -> dict | None:
        row = next((row for row in self.accounts.values() if row["username"] == username), None)
        return deepcopy(row) if row else None

    def create_account(self, record: dict) -> None:
        if any(row["username"] == record["username"] for row in self.accounts.values()):
            from src.workflow_identity_postgres_v1 import WorkflowIdentityStoreError

            raise WorkflowIdentityStoreError("username_already_exists")
        self.accounts[record["account_id"]] = deepcopy(record)

    def update_roles(self, account_id: str, roles: list[str]) -> dict | None:
        row = self.accounts.get(account_id)
        if row is None:
            return None
        row["roles"] = list(roles)
        return deepcopy(row)

    def create_session(self, session: dict) -> None:
        self.sessions[_token_hash(session["token"])] = deepcopy(session)

    def session_account(self, token: str) -> dict | None:
        session = self.sessions.get(_token_hash(token))
        if not session or session.get("revoked"):
            return None
        return self.account_by_id(session["account_id"])

    def revoke_session(self, token: str) -> None:
        session = self.sessions.get(_token_hash(token))
        if session:
            session["revoked"] = True


def _console(tmp_path: Path, shared: SharedIdentityStore, name: str) -> PostgresIdentityDurablePublicationConsole:
    return PostgresIdentityDurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / name,
        workflow_identity_store=shared,  # type: ignore[arg-type]
    )


def test_session_created_on_one_instance_is_valid_on_another(tmp_path: Path) -> None:
    shared = SharedIdentityStore()
    first = _console(tmp_path, shared, "runtime-a")
    second = _console(tmp_path, shared, "runtime-b")

    account = first.create_account("anne", "correct-horse", ["researcher", "reviewer"])
    session = first.authenticate("anne", "correct-horse")

    assert second.session_account(session["token"]) == {
        "account_id": account["account_id"],
        "username": "anne",
        "display_name": "anne",
        "roles": ["researcher", "reviewer"],
    }


def test_logout_on_one_instance_revokes_session_for_all_instances(tmp_path: Path) -> None:
    shared = SharedIdentityStore()
    first = _console(tmp_path, shared, "runtime-a")
    second = _console(tmp_path, shared, "runtime-b")
    first.create_account("anne", "correct-horse", ["researcher"])
    session = first.authenticate("anne", "correct-horse")

    second.logout(session["token"])

    with pytest.raises(ConsoleError, match="not_authenticated"):
        first.session_account(session["token"])


def test_role_change_is_visible_across_instances(tmp_path: Path) -> None:
    shared = SharedIdentityStore()
    first = _console(tmp_path, shared, "runtime-a")
    second = _console(tmp_path, shared, "runtime-b")
    publisher = first.create_account("pub", "secret-pass", ["publisher"])
    reviewer = first.create_account("reviewer", "secret-pass", ["reviewer"])

    first.assign_roles(actor_id=publisher["account_id"], account_id=reviewer["account_id"], roles=["researcher", "reviewer"])

    assert second._account(reviewer["account_id"])["roles"] == ["researcher", "reviewer"]


def test_legacy_file_identity_is_imported_only_when_shared_store_is_empty(tmp_path: Path) -> None:
    runtime = tmp_path / "legacy-runtime"
    legacy = DurablePublicationConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=runtime)
    legacy.create_account("anne", "correct-horse", ["researcher"])
    session = legacy.authenticate("anne", "correct-horse")

    shared = SharedIdentityStore()
    migrated = PostgresIdentityDurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=runtime,
        workflow_identity_store=shared,  # type: ignore[arg-type]
    )
    assert migrated.session_account(session["token"])["username"] == "anne"

    # A stale local file must not replay after PostgreSQL has become authority.
    legacy.create_account("stale-local", "correct-horse", ["researcher"])
    PostgresIdentityDurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=runtime,
        workflow_identity_store=shared,  # type: ignore[arg-type]
    )
    assert shared.account_by_username("stale-local") is None


def test_session_tokens_are_one_way_hashed_for_shared_storage() -> None:
    token = "raw-session-token"
    digest = _token_hash(token)

    assert digest != token
    assert len(digest) == 64
    assert digest == _token_hash(token)
