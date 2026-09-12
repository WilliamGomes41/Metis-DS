#!/usr/bin/env python3
"""Prepare migrated workflow documents for PostgreSQL runtime authority.

Run only after db/migrations/003_workflow_document_envelope_payload.sql and after
scripts/migrate_workflow_documents_postgres.py. This command backfills the full
legacy envelope payload only when the already-migrated relational document,
reviewer and object state matches exactly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    args = parser.parse_args()
    store = PostgresWorkflowDocumentRuntimeStore()
    store.verify_cutover_schema()
    result = store.prepare_legacy_cutover(args.runtime)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
