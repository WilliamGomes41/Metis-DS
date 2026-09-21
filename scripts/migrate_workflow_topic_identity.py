#!/usr/bin/env python3
"""Plan or execute the additive workflow Topic-identity backfill.

Schema migration 010 must already be applied. The backfill only inserts Topic
rows and populates workflow.documents.topic_id; source bytes, envelope payload,
objects, review evidence and publication state are not rewritten.
"""
from __future__ import annotations

import argparse
import json

from src.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore


def execute() -> dict[str, object]:
    store = PostgresWorkflowDocumentStore()
    store.verify_schema()
    result = store.backfill_topic_identity()
    return {"status": "PASS", **result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "PLANNED",
                    "mutation": "insert workflow.topics + populate workflow.documents.topic_id",
                    "execute_flag": "--execute",
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    try:
        result = execute()
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
