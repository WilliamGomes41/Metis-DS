#!/usr/bin/env python3
"""Read-only rollback pre-check for attempt states (C3, #639).

Exit codes: 0 = no attempt is 'running' or 'incomplete_budget'; 2 = at least one is;
1 = the store is unreadable (fail-closed). The script MAG NIET write: PostgreSQL runs in an
read-only session (connection.read_only=True) and every transaction is rolled back; the file store is only read.

Run it only after METIS_PROCESSING_ADMISSION=closed is active (see
docs/change-contracts/a3-incomplete-budget-rollback.md).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

BLOCKING_STATES = ("running", "incomplete_budget")


def scan_envelopes(envelopes: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    counts = {state: 0 for state in BLOCKING_STATES}
    findings = []
    for snapshot_id, envelope in envelopes:
        if isinstance(envelope, str):
            envelope = json.loads(envelope)
        if not isinstance(envelope, dict):
            raise ValueError("envelope_payload_invalid")
        for attempt in envelope.get("processing_attempts") or []:
            state = attempt.get("state")
            if state in counts:
                counts[state] += 1
                findings.append({"snapshot_id": snapshot_id, "attempt_id": attempt.get("attempt_id"), "state": state})
    return {"precheck": "processing_rollback", "status": "clean" if not findings else "blocked",
            "counts": counts, "findings": findings}


def scan_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("envelopes_file_invalid")
    return scan_envelopes(data.items())


def scan_postgres(connection: Any) -> dict[str, Any]:
    # The session MOET be read-only before the first statement; a write MOET fail in PostgreSQL itself.
    connection.read_only = True
    try:
        rows = connection.execute(
            "SELECT snapshot_id, envelope_payload FROM workflow.documents ORDER BY snapshot_id").fetchall()
        return scan_envelopes((str(row["snapshot_id"]), row["envelope_payload"]) for row in rows)
    finally:
        connection.rollback()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--envelopes-file", type=Path, help="file backend: runtime envelopes.json")
    group.add_argument("--postgres", action="store_true", help="PostgreSQL backend via the workflow document store connection")
    args = parser.parse_args(argv)
    try:
        if args.envelopes_file is not None:
            report = scan_file(args.envelopes_file)
        else:
            # workflow.documents belongs to the workflow document store; NOOIT the canonical connection.
            from src.workflows.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore
            with PostgresWorkflowDocumentStore()._connect() as connection:
                report = scan_postgres(connection)
    except Exception as exc:
        print(json.dumps({"precheck": "processing_rollback", "status": "error", "error": type(exc).__name__}))
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "clean" else 2


if __name__ == "__main__":
    sys.exit(main())
