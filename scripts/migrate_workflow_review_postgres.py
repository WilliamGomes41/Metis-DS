#!/usr/bin/env python3
"""Migrate review ledger and publish authorizations to PostgreSQL.

Run only after workflow documents/accounts are migrated and after applying
004_workflow_review_authority.sql. This command is explicit and idempotent;
startup never copies local review state automatically.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.workflow_review_postgres_v1 import PostgresWorkflowReviewStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    args = parser.parse_args()
    store = PostgresWorkflowReviewStore()
    store.verify_review_schema()
    result = store.migrate_legacy_runtime(args.runtime)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
