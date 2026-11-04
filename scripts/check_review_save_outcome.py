#!/usr/bin/env python3
"""Issue #974: was an aborted Review save committed? Read-only, bounded, no content.

Maps the pseudonymous telemetry ``doc_ref`` to its document and lists the review
events recorded in the window after the aborted request started. Only counts,
event types, timestamps and hashed object references are printed; never
document ids, object ids, actors, comments or event details.

Run in App Service SSH (same vendored packages and credentials as the app):

    python /home/site/wwwroot/scripts/check_review_save_outcome.py \
        --doc-ref d_0123456789abcdef --start 2026-11-04T09:12:03Z --seconds 60

Interpretation: an event matching the reviewer's action between request_started
and the worker's last line means the save was committed before the worker
stopped, so the user saw an error for a stored decision. No event in that window
means the transaction rolled back. Other saves on the same document may also
fall in the window; compare times before concluding.
The script only observes. It never repeats, repairs or deletes a decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / ".python_packages"), str(ROOT)]

LIMIT_SECONDS = 60
MAX_WINDOW_SECONDS = 600


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
    end = args.start + timedelta(seconds=args.seconds)
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
            "ORDER BY occurred_at, event_id",
            (matches[0], args.start, end),
        ).fetchall()
    events = [{"occurred_at": row["occurred_at"].isoformat(), "event_type": row["event_type"],
               "object_ref": _object_ref(str(row["object_id"]))} for row in rows]
    print(json.dumps({
        "status": "ok", "doc_ref": args.doc_ref,
        "window": {"start": args.start.isoformat(), "end": end.isoformat()},
        # Other saves on the same document can fall inside the window; compare
        # timestamps and event types with the aborted request before concluding.
        "review_events_in_window": len(events),
        "events": events,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
