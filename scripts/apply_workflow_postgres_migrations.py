#!/usr/bin/env python3
"""Plan, apply, or verify Metis workflow migrations 002-006 with Entra auth."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.workflows.workflow_postgres_migration_v1 import (
    WorkflowMigrationError,
    apply_migrations,
    connect_entra,
    migration_digest,
    migration_paths,
    observe_schema,
)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "verify"))
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", help="Entra database administrator/user; required for apply/verify")
    parser.add_argument("--confirm-target", help="Exact HOST/DATABASE; required for apply")
    parser.add_argument("--confirm-digest", help="Digest printed by plan; required for apply")
    args = parser.parse_args()
    paths = migration_paths(ROOT)
    digest = migration_digest(paths)
    plan = {
        "status": "PLANNED",
        "mutation": "none",
        "target": f"{args.host}/{args.database}",
        "migrations": [path.name for path in paths],
        "digest": digest,
    }
    if args.command == "plan":
        print(json.dumps(plan, sort_keys=True, indent=2))
        return 0
    if not args.user:
        print(json.dumps({"status": "BLOCKED", "error": "database_user_required"}, indent=2))
        return 2
    try:
        connection = connect_entra(host=args.host, database=args.database, user=args.user)
        with connection:
            if args.command == "verify":
                result = observe_schema(connection)
                result["mutation"] = "none"
            else:
                if args.confirm_target != plan["target"]:
                    raise WorkflowMigrationError("workflow_migration_target_confirmation_mismatch")
                if not args.confirm_digest:
                    raise WorkflowMigrationError("workflow_migration_digest_confirmation_required")
                result = apply_migrations(connection, paths=paths, expected_digest=args.confirm_digest)
    except WorkflowMigrationError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True, indent=2))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
