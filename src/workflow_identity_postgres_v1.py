"""PostgreSQL-backed accounts and sessions for the Metis operations console.

This module migrates only identity/session state. Document, review and publication
workflow state remain on the existing console runtime until their own migration.
Activation is opt-in through ``METIS_WORKFLOW_STORE=postgres`` so code can land
before the Azure runtime is switched over.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Any, Iterable

from azure.identity import DefaultAzureCredential

from src.azure_authoritative_publication_console_v1 import AzureAuthoritativePublicationConsole
from src.canonical_publication_postgres_v1 import AZURE_POSTGRES_SCOPE, PostgresCanonicalConfig
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.operations_console_v1 import (
    ALLOWED_ROLES,
    DEFAULT_SESSION_TTL_SECONDS,
    ConsoleError,
    _hash_password,
    _is_forbidden_identity,
    utc_after,
    utc_now,
)

REQUIRED_WORKFLOW_IDENTITY_TABLES = frozenset({"accounts", "sessions"})


class WorkflowIdentityStoreError(RuntimeError):
    """Fail-closed shared workflow identity error."""


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PostgresWorkflowIdentityStore:
    """Shared transactional authority for console accounts and sessions."""

    def __init__(
        self,
        config: PostgresCanonicalConfig | None = None,
        *,
        credential: Any | None = None,
    ) -> None:
        self.config = config or PostgresCanonicalConfig.from_environ()
        self.config.validate()
        self._credential = credential

    def _connect(self) -> Any:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - deployment dependency guard
            raise WorkflowIdentityStoreError("psycopg_unavailable") from exc
        try:
            if self.config.dsn:
                return psycopg.connect(self.config.dsn, row_factory=dict_row, connect_timeout=10)
            credential = self._credential or DefaultAzureCredential()
            token = credential.get_token(AZURE_POSTGRES_SCOPE).token
            return psycopg.connect(
                host=self.config.host,
                dbname=self.config.database,
                user=self.config.user,
                password=token,
                sslmode="require",
                connect_timeout=10,
                row_factory=dict_row,
            )
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_postgres_unavailable") from exc

    def verify_schema(self) -> None:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='workflow'"
                ).fetchall()
        except WorkflowIdentityStoreError:
            raise
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_postgres_schema_check_failed") from exc
        present = {str(row["tablename"]) for row in rows}
        missing = sorted(REQUIRED_WORKFLOW_IDENTITY_TABLES - present)
        if missing:
            raise WorkflowIdentityStoreError("workflow_postgres_schema_missing:" + ",".join(missing))

    @staticmethod
    def _account(row: Any) -> dict[str, Any]:
        return {
            "account_id": str(row["account_id"]),
            "username": str(row["username"]),
            "display_name": str(row["display_name"]),
            "roles": list(row["roles"] or []),
            "password_salt": str(row["password_salt"]),
            "password_hash": str(row["password_hash"]),
            "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        }

    def list_accounts(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT account_id,username,display_name,roles,password_salt,password_hash,created_at "
                    "FROM workflow.accounts ORDER BY created_at,account_id"
                ).fetchall()
            return [self._account(row) for row in rows]
        except WorkflowIdentityStoreError:
            raise
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_accounts_read_failed") from exc

    def account_by_id(self, account_id: str) -> dict[str, Any] | None:
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT account_id,username,display_name,roles,password_salt,password_hash,created_at "
                    "FROM workflow.accounts WHERE account_id=%s",
                    (account_id,),
                ).fetchone()
            return self._account(row) if row else None
        except WorkflowIdentityStoreError:
            raise
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_account_read_failed") from exc

    def account_by_username(self, username: str) -> dict[str, Any] | None:
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT account_id,username,display_name,roles,password_salt,password_hash,created_at "
                    "FROM workflow.accounts WHERE username=%s",
                    (username,),
                ).fetchone()
            return self._account(row) if row else None
        except WorkflowIdentityStoreError:
            raise
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_account_read_failed") from exc

    def create_account(self, record: dict[str, Any]) -> None:
        try:
            with self._connect() as con:
                con.execute(
                    "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (
                        record["account_id"],
                        record["username"],
                        record["display_name"],
                        list(record["roles"]),
                        record["password_salt"],
                        record["password_hash"],
                        record["created_at"],
                    ),
                )
        except Exception as exc:
            if self.account_by_username(str(record["username"])) is not None:
                raise WorkflowIdentityStoreError("username_already_exists") from exc
            raise WorkflowIdentityStoreError("workflow_account_write_failed") from exc

    def update_roles(self, account_id: str, roles: list[str]) -> dict[str, Any] | None:
        try:
            with self._connect() as con:
                row = con.execute(
                    "UPDATE workflow.accounts SET roles=%s WHERE account_id=%s "
                    "RETURNING account_id,username,display_name,roles,password_salt,password_hash,created_at",
                    (roles, account_id),
                ).fetchone()
            return self._account(row) if row else None
        except WorkflowIdentityStoreError:
            raise
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_account_write_failed") from exc

    def create_session(self, session: dict[str, Any]) -> None:
        try:
            with self._connect() as con:
                con.execute(
                    "INSERT INTO workflow.sessions(token_hash,account_id,created_at,expires_at,revoked_at) "
                    "VALUES(%s,%s,%s,%s,NULL)",
                    (
                        _token_hash(str(session["token"])),
                        session["account_id"],
                        session["created_at"],
                        session["expires_at"],
                    ),
                )
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_session_write_failed") from exc

    def session_account(self, token: str) -> dict[str, Any] | None:
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT a.account_id,a.username,a.display_name,a.roles,a.password_salt,a.password_hash,a.created_at "
                    "FROM workflow.sessions s JOIN workflow.accounts a ON a.account_id=s.account_id "
                    "WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>CURRENT_TIMESTAMP",
                    (_token_hash(token),),
                ).fetchone()
            return self._account(row) if row else None
        except WorkflowIdentityStoreError:
            raise
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_session_read_failed") from exc

    def revoke_session(self, token: str) -> None:
        try:
            with self._connect() as con:
                con.execute(
                    "UPDATE workflow.sessions SET revoked_at=CURRENT_TIMESTAMP "
                    "WHERE token_hash=%s AND revoked_at IS NULL",
                    (_token_hash(token),),
                )
        except WorkflowIdentityStoreError:
            raise
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_session_write_failed") from exc

    def migrate_legacy_if_empty(
        self,
        accounts: dict[str, dict[str, Any]],
        sessions: dict[str, dict[str, Any]],
    ) -> bool:
        """Import the file-backed identity snapshot once, only into an empty store.

        Once any PostgreSQL account exists, local files are stale compatibility
        artifacts and MUST NOT be replayed into the shared authority.
        """
        try:
            with self._connect() as con:
                with con.transaction():
                    count = con.execute("SELECT COUNT(*) AS n FROM workflow.accounts").fetchone()
                    if int(count["n"]) != 0:
                        return False
                    for record in accounts.values():
                        con.execute(
                            "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
                            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                            (
                                record["account_id"], record["username"], record["display_name"],
                                list(record["roles"]), record["password_salt"], record["password_hash"], record["created_at"],
                            ),
                        )
                    known_accounts = set(accounts)
                    for token, session in sessions.items():
                        if session.get("account_id") not in known_accounts:
                            continue
                        con.execute(
                            "INSERT INTO workflow.sessions(token_hash,account_id,created_at,expires_at,revoked_at) "
                            "VALUES(%s,%s,%s,%s,NULL) ON CONFLICT(token_hash) DO NOTHING",
                            (_token_hash(token), session["account_id"], session["created_at"], session["expires_at"]),
                        )
            return bool(accounts)
        except WorkflowIdentityStoreError:
            raise
        except Exception as exc:
            raise WorkflowIdentityStoreError("workflow_identity_legacy_migration_failed") from exc


class _PostgresIdentityMixin:
    workflow_identity_store: PostgresWorkflowIdentityStore

    def __init__(self, *args: Any, workflow_identity_store: PostgresWorkflowIdentityStore, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.workflow_identity_store = workflow_identity_store
        self.workflow_identity_store.verify_schema()
        self.workflow_identity_store.migrate_legacy_if_empty(self._accounts, self._sessions)

    @staticmethod
    def _public_account(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "account_id": record["account_id"],
            "username": record["username"],
            "display_name": record["display_name"],
            "roles": list(record["roles"]),
        }

    def _account(self, account_id: str) -> dict[str, Any]:
        try:
            account = self.workflow_identity_store.account_by_id(account_id)
        except WorkflowIdentityStoreError as exc:
            raise ConsoleError("workflow_identity_unavailable", str(exc)) from exc
        if account is None:
            raise ConsoleError("unknown_account")
        return account

    def create_account(
        self,
        username: str,
        password: str,
        roles: Iterable[str],
        display_name: str | None = None,
    ) -> dict[str, Any]:
        username = username.strip()
        display = (display_name or username).strip()
        if not username or not password:
            raise ConsoleError("account_fields_required")
        if _is_forbidden_identity(username) or _is_forbidden_identity(display):
            raise ConsoleError("forbidden_reviewer_identity")
        role_set = sorted(set(roles))
        if any(role not in ALLOWED_ROLES for role in role_set):
            raise ConsoleError("unknown_role")
        salt, digest = _hash_password(password)
        record = {
            "account_id": f"acc-{uuid.uuid4().hex[:12]}",
            "username": username,
            "display_name": display,
            "roles": role_set,
            "password_salt": salt,
            "password_hash": digest,
            "created_at": utc_now(),
        }
        try:
            self.workflow_identity_store.create_account(record)
        except WorkflowIdentityStoreError as exc:
            if str(exc) == "username_already_exists":
                raise ConsoleError("username_already_exists") from exc
            raise ConsoleError("workflow_identity_unavailable", str(exc)) from exc
        return self._public_account(record)

    def assign_roles(self, *, actor_id: str, account_id: str, roles: Iterable[str]) -> dict[str, Any]:
        self._require_role(actor_id, "publisher")
        role_set = sorted(set(roles))
        if any(role not in ALLOWED_ROLES for role in role_set):
            raise ConsoleError("unknown_role")
        try:
            account = self.workflow_identity_store.update_roles(account_id, role_set)
        except WorkflowIdentityStoreError as exc:
            raise ConsoleError("workflow_identity_unavailable", str(exc)) from exc
        if account is None:
            raise ConsoleError("unknown_account")
        return self._public_account(account)

    def list_reviewer_accounts(self) -> list[dict[str, Any]]:
        try:
            accounts = self.workflow_identity_store.list_accounts()
        except WorkflowIdentityStoreError as exc:
            raise ConsoleError("workflow_identity_unavailable", str(exc)) from exc
        return [self._public_account(row) for row in accounts if "reviewer" in row["roles"]]

    def _resolve_named_reviewers(self, named_reviewers: list[str], uploader_id: str) -> list[str]:
        if not named_reviewers:
            raise ConsoleError("named_reviewers_required")
        try:
            accounts = self.workflow_identity_store.list_accounts()
        except WorkflowIdentityStoreError as exc:
            raise ConsoleError("workflow_identity_unavailable", str(exc)) from exc
        by_id = {row["account_id"]: row for row in accounts}
        resolved: list[str] = []
        for raw in named_reviewers:
            value = str(raw).strip()
            if _is_forbidden_identity(value):
                raise ConsoleError("forbidden_reviewer_identity")
            account = by_id.get(value) or next(
                (row for row in accounts if row["username"] == value or row["display_name"] == value),
                None,
            )
            if account is None:
                raise ConsoleError("unknown_reviewer")
            if _is_forbidden_identity(account["username"]) or _is_forbidden_identity(account["display_name"]):
                raise ConsoleError("forbidden_reviewer_identity")
            if "reviewer" not in account["roles"]:
                raise ConsoleError("named_reviewer_must_have_reviewer_role")
            resolved.append(account["account_id"])
        unique = list(dict.fromkeys(resolved))
        if not [account_id for account_id in unique if account_id != uploader_id]:
            raise ConsoleError("uploader_cannot_be_sole_required_reviewer")
        return unique

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        try:
            record = self.workflow_identity_store.account_by_username(username)
        except WorkflowIdentityStoreError as exc:
            raise ConsoleError("workflow_identity_unavailable", str(exc)) from exc
        if not record:
            raise ConsoleError("invalid_credentials")
        _, digest = _hash_password(password, record["password_salt"])
        if not secrets.compare_digest(digest, record["password_hash"]):
            raise ConsoleError("invalid_credentials")
        session = {
            "token": secrets.token_hex(32),
            "account_id": record["account_id"],
            "username": record["username"],
            "roles": list(record["roles"]),
            "created_at": utc_now(),
            "expires_at": utc_after(DEFAULT_SESSION_TTL_SECONDS),
        }
        try:
            self.workflow_identity_store.create_session(session)
        except WorkflowIdentityStoreError as exc:
            raise ConsoleError("workflow_identity_unavailable", str(exc)) from exc
        return dict(session)

    def session_account(self, token: str | None) -> dict[str, Any]:
        if not token:
            raise ConsoleError("not_authenticated")
        try:
            account = self.workflow_identity_store.session_account(token)
        except WorkflowIdentityStoreError as exc:
            raise ConsoleError("workflow_identity_unavailable", str(exc)) from exc
        if account is None:
            raise ConsoleError("not_authenticated")
        return self._public_account(account)

    def logout(self, token: str | None) -> None:
        if not token:
            return
        try:
            self.workflow_identity_store.revoke_session(token)
        except WorkflowIdentityStoreError as exc:
            raise ConsoleError("workflow_identity_unavailable", str(exc)) from exc


class PostgresIdentityDurablePublicationConsole(_PostgresIdentityMixin, DurablePublicationConsole):
    pass


class PostgresIdentityAzureAuthoritativePublicationConsole(
    _PostgresIdentityMixin,
    AzureAuthoritativePublicationConsole,
):
    pass
