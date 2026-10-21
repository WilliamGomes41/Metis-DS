"""Operator-only retirement of an existing PostgreSQL account.

Database access is the administrative authorization boundary; actor_id records
which active Metis publisher owns the operation, not proof of their login.
"""
from __future__ import annotations

from datetime import datetime, timezone

from psycopg.types.json import Jsonb

from src.operations_console_v1 import ConsoleError


def retire_account(connection, *, account_id: str, actor_id: str, reason: str, apply: bool = False) -> dict:
    """Plan by default; caller commits the single apply transaction."""
    reason = reason.strip()
    if not reason or len(reason) > 1000:
        raise ConsoleError("account_retirement_reason_required")
    if account_id == actor_id:
        raise ConsoleError("account_retirement_self_denied")
    if apply:
        connection.execute("SELECT pg_advisory_xact_lock(734821095)")
    # Explicit column read: never silently proceed without migration 015.
    rows = connection.execute(
        "SELECT account_id,display_name,roles,retirement FROM workflow.accounts "
        "WHERE account_id=ANY(%s) ORDER BY account_id" + (" FOR UPDATE" if apply else ""),
        ([account_id, actor_id],),
    ).fetchall()
    accounts = {row["account_id"]: row for row in rows}
    actor, target = accounts.get(actor_id), accounts.get(account_id)
    if not actor or actor["retirement"] is not None or "publisher" not in actor["roles"]:
        raise ConsoleError("account_retirement_publisher_required")
    if not target:
        raise ConsoleError("unknown_account")
    evidence = target["retirement"]
    if apply and evidence is None:
        evidence = {"at": datetime.now(timezone.utc).isoformat(), "actor": actor_id, "reason": reason}
        # Database triggers erase credentials and revoke sessions atomically.
        connection.execute("UPDATE workflow.accounts SET retirement=%s WHERE account_id=%s",
                           (Jsonb(evidence), account_id))
    return {
        "status": "RETIRED" if evidence is not None else "PLANNED",
        "mutation": "retirement" if apply and target["retirement"] is None else "none",
        "account_id": account_id,
        "display_name": target["display_name"],
        "retirement": evidence,
        "reason": evidence["reason"] if evidence else reason,
        "history": "preserved",
    }
