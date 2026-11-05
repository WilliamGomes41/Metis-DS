#!/usr/bin/env python3
"""Issue #974: collect candidate evidence for an aborted save, never infer its outcome.

Maps the pseudonymous telemetry ``doc_ref`` to its document and lists the review
events recorded in the window after the aborted request started. Only counts,
event types, timestamps and hashed object references are printed; never
document ids, object ids, actors, comments or event details.

Copy the reviewed script to /tmp in App Service SSH and use the app's interpreter:

    METIS_DIAGNOSTIC_APP_ROOT=/app python /tmp/check_review_save_outcome.py \
        --doc-ref d_0123456789abcdef --start 2026-11-04T09:12:03Z --seconds 60

Interpretation: these are candidate events, not request-correlated outcomes.
Events may belong to another save, or have been timestamped before a delayed
commit. No event in the window does not prove rollback. The outcome remains
not_determined until the exact command/interaction and stored decision agree.
The script only observes. It never repeats, repairs or deletes a decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(os.environ.get("METIS_DIAGNOSTIC_APP_ROOT", Path(__file__).resolve().parents[1])).resolve()
sys.path[:0] = [str(ROOT / ".python_packages"), str(ROOT)]

LIMIT_SECONDS = 60
MAX_WINDOW_SECONDS = 600
MAX_EVENTS = 1000


def _object_ref(object_id: str) -> str:
    return "o_" + hashlib.sha256(object_id.encode("utf-8")).hexdigest()[:12]


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp needs a timezone, e.g. 2026-11-04T09:12:03Z")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--doc-ref", required=True, help="telemetry doc_ref, d_ + 16 hex")
    parser.add_argument("--start", required=True, type=_parse_time, help="request_started time (UTC)")
    parser.add_argument("--seconds", type=int, default=60, help="window after start (default 60, max 600)")
    args = parser.parse_args()
    if not (len(args.doc_ref) == 18 and args.doc_ref.startswith("d_")
            and all(c in "0123456789abcdef" for c in args.doc_ref[2:])):
        parser.error("--doc-ref must look like d_0123456789abcdef")
    if not 1 <= args.seconds <= MAX_WINDOW_SECONDS:
        parser.error(f"--seconds must be between 1 and {MAX_WINDOW_SECONDS}")

    def stop(*_args):
        print(json.dumps({"status": "timeout", "limit_seconds": LIMIT_SECONDS}), flush=True)
        raise SystemExit(1)

    signal.signal(signal.SIGALRM, stop)
    signal.alarm(LIMIT_SECONDS)

    from src.azure_postgres_credential_v1 import CachedAzurePostgresCredential
    from src.telemetry.hub import doc_ref
    from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore

    store = PostgresWorkflowReviewStore(credential=CachedAzurePostgresCredential())
    # Ledger events carry second precision: floor only the lower bound, so the
    # starting second is included and the requested end is kept.
    end = args.start + timedelta(seconds=args.seconds)
    args.start = args.start.replace(microsecond=0)
    with store._connect() as con:
        con.execute("SET TRANSACTION READ ONLY")
        con.execute("SET LOCAL statement_timeout = '10s'")
        ids = [row["snapshot_id"] for row in con.execute("SELECT snapshot_id FROM workflow.documents")]
        matches = [sid for sid in ids if doc_ref(sid) == args.doc_ref]
        if len(matches) != 1:
            print(json.dumps({"status": "document_not_resolved", "doc_ref": args.doc_ref,
                              "matches": len(matches)}))
            return 1
        rows = con.execute(
            "SELECT object_id, event_type, occurred_at FROM workflow.review_events "
            "WHERE snapshot_id=%s AND occurred_at >= %s AND occurred_at < %s "
            "ORDER BY occurred_at, event_id LIMIT %s",
            (matches[0], args.start, end, MAX_EVENTS + 1),
        ).fetchall()
    truncated = len(rows) > MAX_EVENTS
    events = [{"occurred_at": row["occurred_at"].isoformat(), "event_type": row["event_type"],
               "object_ref": _object_ref(str(row["object_id"]))} for row in rows[:MAX_EVENTS]]
    print(json.dumps({
        "status": "ok", "doc_ref": args.doc_ref,
        "window": {"start": args.start.isoformat(), "end": end.isoformat()},
        "save_outcome": "not_determined",
        "review_events_in_window": None if truncated else len(events),
        "events_truncated": truncated,
        "reported_events": len(events),
        "events": events,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
