#!/usr/bin/env python3
"""Plan or apply historical account retirement using authorized database access."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.operations_console_v1 import ConsoleError
from src.workflows.account_retirement_v1 import retire_account
from src.workflows.workflow_postgres_migration_v1 import connect_entra


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply"))
    for field in ("host", "database", "user", "account-id", "actor-id", "reason"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--confirm-target", help="Exact HOST/DATABASE/ACCOUNT_ID; apply only")
    args = parser.parse_args()
    target = f"{args.host}/{args.database}/{args.account_id}"
    if args.command == "apply" and args.confirm_target != target:
        print(json.dumps({"status": "BLOCKED", "error": "account_retirement_confirmation_required", "target": target}))
        return 2
    try:
        with connect_entra(host=args.host, database=args.database, user=args.user) as con:
            if args.command == "plan":
                con.execute("SET TRANSACTION READ ONLY")
            con.execute("SET LOCAL lock_timeout='5s'")
            con.execute("SET LOCAL statement_timeout='60s'")
            result = retire_account(con, account_id=args.account_id, actor_id=args.actor_id,
                                    reason=args.reason, apply=args.command == "apply")
        print(json.dumps(dict(result, target=target), indent=2, sort_keys=True))
        return 0
    except ConsoleError as exc:
        error = exc.code
    except Exception:
        # No raw database exception: it can contain credentials or row contents.
        error = "account_retirement_unavailable_check_schema_and_database_access"
    print(json.dumps({"status": "BLOCKED", "error": error}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
