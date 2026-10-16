#!/usr/bin/env python3
"""Explicit retention for workflow.publication_refusals (#636 F3, Sherlock re-audit).

Maintenance command; it MAG NIET run per refusal. Deletes rows older than --retention-days
and keeps at most --max-rows rows. Uses the PostgreSQL workflow configuration from the
environment (same as the console).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import publication_refusal_store_v1 as store  # noqa: E402


def _workflow_store():
    from src.workflows.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore
    return PostgresWorkflowDocumentStore()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retention-days', type=int, default=store.RETENTION_DAYS)
    parser.add_argument('--max-rows', type=int, default=store.MAX_ROWS)
    args = parser.parse_args(argv)
    if args.max_rows <= 0 or args.retention_days <= 0:
        parser.error('--max-rows and --retention-days MOETEN be > 0')  # exit 2, nothing deleted
    result = store.apply_retention(_workflow_store(), retention_days=args.retention_days, max_rows=args.max_rows)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
