"""Exact identity verification for the Step 9 data migration wrapper.

# release-control-evidence: opslag
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
"""
from __future__ import annotations

import pytest

from scripts.migrate_workflow_cutover_postgres import _verify_identity_snapshot


TOKEN = "raw-token-never-written-to-output"
ACCOUNT = {
    "account_id": "account-1",
    "username": "anne",
    "display_name": "Anne",
    "roles": ["researcher"],
    "password_salt": "salt",
    "password_hash": "hash",
    "created_at": "2026-09-12T10:00:00Z",
}
SESSION = {
    "account_id": "account-1",
    "created_at": "2026-09-12T10:01:00Z",
    "expires_at": "2026-09-12T18:01:00Z",
}


class Rows:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict]:
        return self.rows


class Connection:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _query: str) -> Rows:
        return Rows(self.rows)


class Store:
    def __init__(self, *, account: dict, sessions: list[dict]) -> None:
        self.account = account
        self.sessions = sessions

    def list_accounts(self) -> list[dict]:
        return [dict(self.account)]

    def _connect(self) -> Connection:
        return Connection(self.sessions)


def _store() -> Store:
    import hashlib

    return Store(
        account={**ACCOUNT, "created_at": "2026-09-12T10:00:00+00:00"},
        sessions=[
            {
                "token_hash": hashlib.sha256(TOKEN.encode("utf-8")).hexdigest(),
                "account_id": "account-1",
                "created_at": "2026-09-12T10:01:00+00:00",
                "expires_at": "2026-09-12T18:01:00+00:00",
            }
        ],
    )


def test_identity_verification_compares_accounts_and_hashed_sessions_exactly() -> None:
    result = _verify_identity_snapshot(  # type: ignore[arg-type]
        _store(), {"account-1": ACCOUNT}, {TOKEN: SESSION}
    )
    assert result == {"accounts": 1, "sessions": 1, "skipped_sessions": 0}
    assert TOKEN not in str(result)


def test_identity_verification_fails_closed_on_database_difference() -> None:
    store = _store()
    store.account["display_name"] = "Different"
    with pytest.raises(RuntimeError, match="workflow_identity_migration_conflict"):
        _verify_identity_snapshot(  # type: ignore[arg-type]
            store, {"account-1": ACCOUNT}, {TOKEN: SESSION}
        )


def test_identity_verification_skips_legacy_session_without_expiry() -> None:
    result = _verify_identity_snapshot(  # type: ignore[arg-type]
        Store(account={**ACCOUNT, "created_at": "2026-09-12T10:00:00+00:00"}, sessions=[]),
        {"account-1": ACCOUNT},
        {TOKEN: {"account_id": "account-1", "created_at": "2026-09-12T10:01:00Z"}},
    )
    assert result == {"accounts": 1, "sessions": 0, "skipped_sessions": 1}
