#!/usr/bin/env python3
"""Plan, apply, or verify registered Metis workflow migrations with Entra auth."""
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
    observe_runtime_privileges,
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
    parser.add_argument("--runtime-role", help="verify: also check the runtime identity's grants (e.g. vvn-metis-console)")
    parser.add_argument('--strict-runtime-privileges', action='store_true',
                        help='verify: also reject UPDATE on publication_refusals and unsafe workflow role authority; not a full ACL audit')
    parser.add_argument('--lock-timeout-ms', type=int, default=5000,
                        help='apply: positive per-statement lock wait limit in milliseconds (default: 5000)')
    parser.add_argument("--view-check", action="store_true", help="verify: the view check is enabled, so require view_checks grants")
    parser.add_argument("--compact-cards", action="store_true",
                        help="verify: CONSOLE_REVIEW_CARD_READS=compact, so require the migration 027 tables")
    parser.add_argument("--test-document-deletion", action="store_true",
                        help="verify: test document removal is enabled, so require its DELETE grants")
    args = parser.parse_args()
    if args.strict_runtime_privileges and (args.command != 'verify' or not args.runtime_role):
        parser.error('--strict-runtime-privileges requires verify and --runtime-role')
    if not 0 < args.lock_timeout_ms <= 2147483647:
        parser.error('--lock-timeout-ms must be between 1 and 2147483647')
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
                if args.runtime_role:
                    privileges = observe_runtime_privileges(connection, args.runtime_role, view_check=args.view_check,
                                                            compact_cards=args.compact_cards,
                                                            test_document_deletion=args.test_document_deletion,
                                                            strict=args.strict_runtime_privileges)
                    result["runtime_privileges"] = privileges
                    if privileges["status"] != "PASS":
                        result["status"] = "BLOCKED"
                result["mutation"] = "none"
            else:
                if args.confirm_target != plan["target"]:
                    raise WorkflowMigrationError("workflow_migration_target_confirmation_mismatch")
                if not args.confirm_digest:
                    raise WorkflowMigrationError("workflow_migration_digest_confirmation_required")
                result = apply_migrations(connection, paths=paths, expected_digest=args.confirm_digest,
                                          lock_timeout_ms=args.lock_timeout_ms)
    except WorkflowMigrationError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True, indent=2))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
