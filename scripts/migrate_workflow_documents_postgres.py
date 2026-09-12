#!/usr/bin/env python3
"""Explicit one-way copy of file-backed console documents into workflow PostgreSQL.

This command does not switch console callers. Run only after the workflow schema
and accounts are provisioned. Exact replays are harmless; mismatches fail closed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    args = parser.parse_args()

    store = PostgresWorkflowDocumentStore()
    store.verify_schema()
    result = store.migrate_legacy_runtime(args.runtime)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
