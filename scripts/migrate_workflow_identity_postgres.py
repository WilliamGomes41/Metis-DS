#!/usr/bin/env python3
"""Explicit one-way migration of local accounts/sessions into workflow PostgreSQL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore


def _read_map(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or any(not isinstance(value, dict) for value in raw.values()):
        raise ValueError(f"invalid_legacy_identity_map:{path.name}")
    return {str(key): dict(value) for key, value in raw.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    args = parser.parse_args()

    accounts = _read_map(args.runtime / "accounts.json")
    sessions = _read_map(args.runtime / "sessions.json")
    store = PostgresWorkflowIdentityStore()
    store.verify_schema()
    migrated = store.migrate_legacy_if_empty(accounts, sessions)
    result = {
        "migrated": migrated,
        "accounts": len(accounts),
        "sessions": len(sessions),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
