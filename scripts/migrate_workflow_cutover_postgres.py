#!/usr/bin/env python3
"""Run the existing idempotent workflow data migrations in dependency order.

Run this inside the production App Service so both its managed identity and the
existing /home/data runtime are available.  Planning is the default; --execute
requires an exact runtime-path confirmation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore
from src.workflow_identity_postgres_v1 import (
    PostgresWorkflowIdentityStore,
    migratable_legacy_sessions,
)
from src.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflow_review_postgres_v1 import PostgresWorkflowReviewStore

# Reuse the exact migration helpers rather than introducing a second migration engine.
from scripts.migrate_workflow_identity_postgres import _read_map
from scripts.migrate_workflow_remaining_postgres import (
    _migrate_audits,
    _migrate_class_history,
    _migrate_secret,
)


def _instant(value: object) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _verify_identity_snapshot(
    store: PostgresWorkflowIdentityStore,
    accounts: dict[str, dict],
    sessions: dict[str, dict],
) -> dict[str, int]:
    valid_sessions = migratable_legacy_sessions(accounts, sessions)
    expected_accounts = sorted([
        {
            "account_id": str(row["account_id"]),
            "username": str(row["username"]),
            "display_name": str(row["display_name"]),
            "roles": list(row["roles"]),
            "password_salt": str(row["password_salt"]),
            "password_hash": str(row["password_hash"]),
            "created_at": _instant(row["created_at"]),
        }
        for row in accounts.values()
    ], key=lambda row: row["account_id"])
    actual_accounts = sorted(
        ({**row, "created_at": _instant(row["created_at"]) } for row in store.list_accounts()),
        key=lambda row: row["account_id"],
    )
    if actual_accounts != expected_accounts:
        raise RuntimeError("workflow_identity_migration_conflict")

    expected_sessions = sorted([
        {
            "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
            "account_id": str(row["account_id"]),
            "created_at": _instant(row["created_at"]),
            "expires_at": _instant(row["expires_at"]),
        }
        for token, row in valid_sessions.items()
    ], key=lambda row: row["token_hash"])
    try:
        with store._connect() as connection:
            rows = connection.execute(
                "SELECT token_hash,account_id,created_at,expires_at,revoked_at "
                "FROM workflow.sessions ORDER BY token_hash"
            ).fetchall()
    except Exception as exc:
        raise RuntimeError("workflow_identity_session_verification_failed") from exc
    actual_sessions = {
        str(row["token_hash"]): {
            "token_hash": str(row["token_hash"]),
            "account_id": str(row["account_id"]),
            "created_at": _instant(row["created_at"]),
            "expires_at": _instant(row["expires_at"]),
            "revoked": row.get("revoked_at") is not None,
        }
        for row in rows
    }
    revoked_legacy = 0
    for expected in expected_sessions:
        actual = actual_sessions.get(expected["token_hash"])
        if actual is None:
            raise RuntimeError("workflow_identity_session_migration_conflict")
        actual_identity = {key: actual[key] for key in expected}
        if actual_identity != expected:
            raise RuntimeError("workflow_identity_session_migration_conflict")
        revoked_legacy += int(actual["revoked"])
    return {
        "accounts": len(expected_accounts),
        "sessions": len(expected_sessions),
        "skipped_sessions": len(sessions) - len(valid_sessions),
        "active_legacy_sessions": len(expected_sessions) - revoked_legacy,
        "revoked_legacy_sessions": revoked_legacy,
        "additional_sessions": len(actual_sessions) - len(expected_sessions),
    }


def execute(runtime: Path) -> dict[str, object]:
    identity = PostgresWorkflowIdentityStore()
    identity.verify_schema()
    accounts = _read_map(runtime / "accounts.json")
    sessions = _read_map(runtime / "sessions.json")
    identity_migrated = identity.migrate_legacy_if_empty(accounts, sessions)
    identity_verified = _verify_identity_snapshot(identity, accounts, sessions)

    documents = PostgresWorkflowDocumentStore()
    documents.verify_schema()
    topic_identity_result = documents.backfill_topic_identity()
    document_result = documents.migrate_legacy_runtime(runtime)

    document_runtime = PostgresWorkflowDocumentRuntimeStore()
    document_runtime.verify_cutover_schema()
    prepared_result = document_runtime.prepare_legacy_cutover(runtime)

    review = PostgresWorkflowReviewStore()
    review.verify_review_schema()
    review_result = review.migrate_legacy_runtime(runtime)

    remaining = PostgresWorkflowRemainingStore()
    remaining.verify_remaining_schema()
    remaining_result = {
        "audits": _migrate_audits(runtime, remaining),
        "audit_secrets": _migrate_secret(runtime, remaining),
        "class_history_records": _migrate_class_history(runtime, document_runtime),
    }
    return {
        "status": "PASS",
        "identity": {
            "migrated": identity_migrated,
            **identity_verified,
            "exact": True,
        },
        "topic_identity": topic_identity_result,
        "documents": document_result,
        "document_cutover": prepared_result,
        "review": review_result,
        "remaining": remaining_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-runtime")
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    if not runtime.is_dir():
        print(json.dumps({"status": "BLOCKED", "error": "runtime_directory_missing"}, indent=2))
        return 2
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "PLANNED",
                    "mutation": "none",
                    "runtime": str(runtime),
                    "order": ["identity", "documents", "document_cutover", "review", "remaining"],
                    "execute_confirmation": str(runtime),
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    if args.confirm_runtime != str(runtime):
        print(json.dumps({"status": "BLOCKED", "error": "runtime_confirmation_mismatch"}, indent=2))
        return 2
    try:
        result = execute(runtime)
    except Exception as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "error": type(exc).__name__, "detail": str(exc)[:500]},
                sort_keys=True,
                indent=2,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
