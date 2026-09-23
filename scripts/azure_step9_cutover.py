#!/usr/bin/env python3
"""Read-only Azure preflight and explicit one-phase workflow activation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.azure_step9_cutover_v1 import AzureCli, Step9Error, activate_phase, observe_production
from src.workflows.workflow_postgres_migration_v1 import (
    WorkflowMigrationError,
    connect_entra,
    migration_digest,
    migration_paths,
    observe_schema,
)

def _target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--webapp", required=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight", help="Read Azure state; never mutate")
    _target(preflight)
    activate = sub.add_parser("activate", help="Enable exactly one prepared workflow phase")
    _target(activate)
    activate.add_argument("--phase", required=True, choices=("identity", "documents", "review", "remaining"))
    activate.add_argument(
        "--confirm",
        required=True,
        help="Exact subscription/resource-group/webapp/phase confirmation",
    )
    activate.add_argument(
        "--database-user",
        required=True,
        help="Existing Entra database user for read-only schema verification",
    )
    activate.add_argument(
        "--confirm-data-migrated",
        required=True,
        help="Exact HOST/DATABASE confirmation that data migration completed",
    )
    args = parser.parse_args()
    cli = AzureCli()
    try:
        if args.command == "preflight":
            result = observe_production(
                cli,
                subscription_id=args.subscription_id,
                resource_group=args.resource_group,
                webapp=args.webapp,
            )
        else:
            observed = observe_production(
                cli,
                subscription_id=args.subscription_id,
                resource_group=args.resource_group,
                webapp=args.webapp,
            )
            if observed["status"] != "PASS":
                raise Step9Error("azure_preflight_blocked")
            selected = observed["selection"]
            database_target = f"{selected['postgres_host']}/{selected['postgres_database']}"
            if args.confirm_data_migrated != database_target:
                raise Step9Error("workflow_data_migration_confirmation_mismatch")
            try:
                connection = connect_entra(
                    host=selected["postgres_host"],
                    database=selected["postgres_database"],
                    user=args.database_user,
                )
                with connection:
                    schema = observe_schema(connection)
            except WorkflowMigrationError as exc:
                raise Step9Error(str(exc)) from exc
            if schema["status"] != "PASS":
                raise Step9Error("workflow_schema_verification_failed")
            result = activate_phase(
                cli,
                subscription_id=args.subscription_id,
                resource_group=args.resource_group,
                webapp=args.webapp,
                phase_name=args.phase,
                confirmation=args.confirm,
            )
            result["schema_verification"] = {
                "status": schema["status"],
                "database": schema["database"],
                "migration_digest": migration_digest(migration_paths(ROOT)),
            }
    except Step9Error as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True, indent=2))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
