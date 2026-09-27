"""Opt-in Entra sign-in at the existing console identity boundary.

Microsoft proves identity and grants app roles. PostgreSQL owns the stable Metis
account binding and the emergency deny flag. No email linking, Graph privileges,
local fallback or refresh-token storage. See docs/ENTRA_SIGN_IN.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import secrets
import time
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from src.operations_console_v1 import ConsoleError
from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore, _token_hash

ROLE_MAP = {"Metis.Researcher": "researcher", "Metis.Reviewer": "reviewer", "Metis.Publisher": "publisher"}
FLOW_COOKIE = "__Host-metis_oidc"
SESSION_SECONDS = 300


def _uuid(value: Any) -> str:
    return str(UUID(str(value)))


@dataclass(frozen=True)
class EntraConfig:
    tenant_id: str
    client_id: str
    client_secret: str = field(repr=False)
    origin: str = ""
    bindings: dict[str, str] = field(default_factory=dict)

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def redirect_uri(self) -> str:
        return self.origin + "/auth/microsoft/callback"

    @classmethod
    def from_environ(cls, origin: str | None) -> EntraConfig | None:
        mode = os.getenv("METIS_CONSOLE_AUTH", "local").strip().lower()
        if mode == "local":
            return None
        if mode != "entra":
            raise ValueError("console_auth_mode_invalid")
        try:
            parsed = urlsplit(origin or "")
            if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
                    or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
                raise ValueError()
            bindings = json.loads(os.getenv("METIS_ENTRA_ACCOUNT_BINDINGS_JSON", "{}"))
            if not isinstance(bindings, dict) or any(not isinstance(v, str) or not v for v in bindings.values()):
                raise ValueError()
            raw_count = len(bindings)
            bindings = {_uuid(k): v for k, v in bindings.items()}
            if len(bindings) != raw_count or len(set(bindings.values())) != len(bindings):
                raise ValueError()
            secret = os.environ["METIS_ENTRA_CLIENT_SECRET"].strip()
            if not secret:
                raise ValueError()
            return cls(_uuid(os.environ["METIS_ENTRA_TENANT_ID"]), _uuid(os.environ["METIS_ENTRA_CLIENT_ID"]),
                       secret, f"https://{parsed.netloc.lower()}", bindings)
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError("entra_configuration_invalid") from exc


class MicrosoftLogin:
    """Authorization code + PKCE/state/nonce validation delegated to MSAL."""

    def __init__(self, config: EntraConfig):
        from msal import ConfidentialClientApplication
        self.config = config
        # Per-handshake clients: no shared mutable user token cache; no offline scope.
        self._factory = lambda: ConfidentialClientApplication(
            config.client_id, client_credential=config.client_secret,
            authority=config.authority, exclude_scopes=["offline_access"], timeout=10,
        )

    def begin(self) -> dict[str, Any]:
        return self._factory().initiate_auth_code_flow(
            scopes=[], redirect_uri=self.config.redirect_uri, response_mode="query",
        )

    def finish(self, flow: dict, response: dict) -> dict:
        result = self._factory().acquire_token_by_auth_code_flow(flow, response)
        claims = result.get("id_token_claims")
        if not isinstance(claims, dict):
            raise ConsoleError("entra_access_denied")
        return claims


def admitted_claims(config: EntraConfig, claims: dict) -> tuple[str, list[str], str, int]:
    """Additional app policy AFTER MSAL's protocol validation, never raw JWT input."""
    try:
        oid = _uuid(claims["oid"])
        if (_uuid(claims["tid"]) != config.tenant_id or claims["aud"] != config.client_id
                or claims["iss"] != config.authority + "/v2.0"):
            raise ValueError()
        exp = int(claims["exp"])
        if exp <= time.time() or int(claims.get("nbf", 0)) > time.time() + 30:
            raise ValueError()
        raw_roles = claims.get("roles", [])
        if not isinstance(raw_roles, list) or any(not isinstance(r, str) for r in raw_roles):
            raise ValueError()
        roles = sorted({ROLE_MAP[r] for r in raw_roles if r in ROLE_MAP})
        if not roles:
            raise ValueError()
        name = str(claims.get("name") or "Microsoft-gebruiker").strip()[:200]
        return oid, roles, name or "Microsoft-gebruiker", exp
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ConsoleError("entra_access_denied") from exc


class EntraIdentity:
    def __init__(self, store: PostgresWorkflowIdentityStore, config: EntraConfig):
        self.store, self.config = store, config

    @staticmethod
    def _lock(con):
        # Serializes rare identity mutations, not document/review work or requests.
        con.execute("SELECT pg_advisory_xact_lock(734821095)")

    def prepare(self):
        """Idempotent explicit binding. Fail atomically if any legacy identity is unbound."""
        with self.store._connect() as con:
            self._lock(con)
            for table in ("entra_identities", "entra_sessions", "entra_flows"):
                con.execute(f"SELECT 1 FROM workflow.{table} LIMIT 0")
            for oid, aid in self.config.bindings.items():
                row = con.execute("SELECT tenant_id,object_id FROM workflow.entra_identities WHERE account_id=%s", (aid,)).fetchone()
                if row:
                    if str(row["tenant_id"]) != self.config.tenant_id or str(row["object_id"]) != oid:
                        raise ConsoleError("entra_binding_conflict")
                    continue
                con.execute(
                    "INSERT INTO workflow.entra_identities(tenant_id,object_id,account_id,evidence) VALUES(%s,%s,%s,%s)",
                    (self.config.tenant_id, oid, aid, Jsonb([self._event("legacy_bound", "configuration")]))
                )
            unbound = con.execute(
                "SELECT 1 FROM workflow.accounts a LEFT JOIN workflow.entra_identities e ON e.account_id=a.account_id "
                "WHERE e.account_id IS NULL OR e.tenant_id<>%s LIMIT 1", (self.config.tenant_id,)
            ).fetchone()
            if unbound:
                raise ConsoleError("entra_legacy_binding_required")
            # A configured cutover must never revive old local sessions on rollback.
            con.execute("UPDATE workflow.sessions s SET revoked_at=CURRENT_TIMESTAMP WHERE revoked_at IS NULL "
                        "AND NOT EXISTS (SELECT 1 FROM workflow.entra_sessions e WHERE e.token_hash=s.token_hash)")

    @staticmethod
    def _event(action: str, actor: str) -> dict:
        return {"action": action, "actor": actor, "at": datetime.now(timezone.utc).isoformat()}

    def save_flow(self, flow: dict) -> str:
        handle = secrets.token_urlsafe(32)
        with self.store._connect() as con:
            self._lock(con)
            con.execute("DELETE FROM workflow.entra_flows WHERE expires_at<=CURRENT_TIMESTAMP")
            if con.execute("SELECT count(*) AS n FROM workflow.entra_flows").fetchone()["n"] >= 1000:
                raise ConsoleError("entra_temporarily_unavailable")
            con.execute("INSERT INTO workflow.entra_flows VALUES(%s,%s,CURRENT_TIMESTAMP + interval '10 minutes')",
                        (_token_hash(handle), Jsonb(flow)))
        return handle

    def consume_flow(self, handle: str | None) -> dict:
        if not handle or len(handle) > 100:
            raise ConsoleError("entra_access_denied")
        with self.store._connect() as con:
            row = con.execute("DELETE FROM workflow.entra_flows WHERE browser_hash=%s RETURNING payload,expires_at",
                              (_token_hash(handle),)).fetchone()
        if not row or row["expires_at"] <= datetime.now(timezone.utc):
            raise ConsoleError("entra_access_denied")
        return row["payload"]

    def sign_in(self, claims: dict) -> dict:
        oid, roles, name, exp = admitted_claims(self.config, claims)
        token = secrets.token_hex(32)
        with self.store._connect() as con:
            self._lock(con)
            row = con.execute("SELECT account_id,blocked FROM workflow.entra_identities WHERE tenant_id=%s AND object_id=%s",
                              (self.config.tenant_id, oid)).fetchone()
            if row and row["blocked"]:
                raise ConsoleError("entra_access_denied")
            if row:
                aid = row["account_id"]
                # Role changes invalidate older sessions before publishing current rights.
                old = con.execute("SELECT roles FROM workflow.accounts WHERE account_id=%s", (aid,)).fetchone()
                if sorted(old["roles"]) != roles:
                    event = dict(self._event("roles_observed", "Microsoft Entra"), before=old["roles"], after=roles)
                    con.execute("UPDATE workflow.entra_identities SET evidence=evidence || %s WHERE account_id=%s", (Jsonb([event]), aid))
                    con.execute("UPDATE workflow.sessions SET revoked_at=CURRENT_TIMESTAMP WHERE account_id=%s AND revoked_at IS NULL", (aid,))
                con.execute("UPDATE workflow.accounts SET roles=%s WHERE account_id=%s", (roles, aid))
            else:
                aid = "acc-" + uuid4().hex[:12]
                con.execute("INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) VALUES(%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
                            (aid, f"entra:{self.config.tenant_id}:{oid}", name, roles, "", ""))
                con.execute("INSERT INTO workflow.entra_identities(tenant_id,object_id,account_id,evidence) VALUES(%s,%s,%s,%s)",
                            (self.config.tenant_id, oid, aid, Jsonb([self._event("provisioned", aid)])))
            con.execute("DELETE FROM workflow.sessions WHERE token_hash IN "
                        "(SELECT s.token_hash FROM workflow.sessions s JOIN workflow.entra_sessions es USING(token_hash) "
                        "WHERE s.expires_at<=CURRENT_TIMESTAMP)")
            con.execute("INSERT INTO workflow.sessions(token_hash,account_id,created_at,expires_at) "
                        "VALUES(%s,%s,CURRENT_TIMESTAMP,LEAST(CURRENT_TIMESTAMP + interval '5 minutes',to_timestamp(%s)))",
                        (_token_hash(token), aid, exp))
            con.execute("INSERT INTO workflow.entra_sessions VALUES(%s,%s,%s)", (_token_hash(token), self.config.tenant_id, oid))
        return {"token": token, "account_id": aid}

    def session_account(self, token: str | None) -> dict:
        if not token:
            raise ConsoleError("not_authenticated")
        try:
            with self.store._connect() as con:
                row = con.execute(
                    "SELECT a.* FROM workflow.sessions s JOIN workflow.entra_sessions es USING(token_hash) "
                    "JOIN workflow.entra_identities e ON e.tenant_id=es.tenant_id AND e.object_id=es.object_id "
                    "JOIN workflow.accounts a ON a.account_id=e.account_id AND a.account_id=s.account_id "
                    "WHERE s.token_hash=%s AND es.tenant_id=%s AND NOT e.blocked AND s.revoked_at IS NULL "
                    "AND s.expires_at>CURRENT_TIMESTAMP AND s.created_at>CURRENT_TIMESTAMP - interval '5 minutes'",
                    (_token_hash(token), self.config.tenant_id),
                ).fetchone()
        except Exception as exc:
            raise ConsoleError("workflow_identity_unavailable") from exc
        if not row:
            raise ConsoleError("not_authenticated")
        return {k: row[k] for k in ("account_id", "username", "display_name", "roles")}

    def access_rows(self) -> dict[str, bool]:
        with self.store._connect() as con:
            rows = con.execute("SELECT account_id,blocked FROM workflow.entra_identities WHERE tenant_id=%s", (self.config.tenant_id,)).fetchall()
        return {r["account_id"]: r["blocked"] for r in rows}

    def set_blocked(self, *, actor_token: str, account_id: str, blocked: bool):
        with self.store._connect() as con:
            self._lock(con)
            # Recheck actor session and role INSIDE the same mutation transaction.
            actor = con.execute(
                "SELECT a.account_id FROM workflow.accounts a JOIN workflow.sessions s USING(account_id) "
                "JOIN workflow.entra_sessions es USING(token_hash) "
                "JOIN workflow.entra_identities e ON e.account_id=a.account_id AND e.tenant_id=es.tenant_id AND e.object_id=es.object_id "
                "WHERE s.token_hash=%s AND e.tenant_id=%s AND NOT e.blocked AND 'publisher'=ANY(a.roles) "
                "AND s.revoked_at IS NULL AND s.expires_at>CURRENT_TIMESTAMP "
                "AND s.created_at>CURRENT_TIMESTAMP - interval '5 minutes'",
                (_token_hash(actor_token), self.config.tenant_id),
            ).fetchone()
            if not actor or actor["account_id"] == account_id:
                raise ConsoleError("entra_access_denied")
            if not con.execute("SELECT 1 FROM workflow.entra_identities WHERE account_id=%s AND tenant_id=%s", (account_id, self.config.tenant_id)).fetchone():
                raise ConsoleError("unknown_account")
            event = self._event("blocked" if blocked else "unblocked", actor["account_id"])
            row = con.execute("UPDATE workflow.entra_identities SET blocked=%s,evidence=evidence || %s "
                              "WHERE account_id=%s AND tenant_id=%s AND blocked<>%s RETURNING account_id",
                              (blocked, Jsonb([event]), account_id, self.config.tenant_id, blocked)).fetchone()
            if row:
                con.execute("UPDATE workflow.sessions SET revoked_at=CURRENT_TIMESTAMP WHERE account_id=%s AND revoked_at IS NULL", (account_id,))


def install_entra(console, origin: str | None):
    config = EntraConfig.from_environ(origin)
    if config is None:
        return None
    store = getattr(console, "workflow_identity_store", None)
    if not isinstance(store, PostgresWorkflowIdentityStore):
        raise ValueError("entra_requires_postgres_identity")
    identity = EntraIdentity(store, config)
    identity.prepare()
    # Every installed console route uses this same boundary, not only the base UI.
    console.session_account = identity.session_account

    def forbidden(*args, **kwargs):
        raise ConsoleError("entra_local_auth_disabled")

    console.authenticate = forbidden
    console.create_account = forbidden
    console.create_managed_account = forbidden
    console.assign_roles = forbidden
    return identity
