"""Separate append-only store for publication refusals (outside the review ledger).

TIJDELIJK: this JSONL file store is temporary until William's GO on a PostgreSQL table
(no migration in this PR). Every record carries store_status = STORE_STATUS.

Rules (B18):
- A publication_refused record MAG NIET enter the review ledger hash chain; it MOET
  only be written here. Existing ledger event hashes MOETEN NOOIT change.
- The store is append-only: records are NOOIT rewritten or removed by this module.
- Dedup: one record per (snapshot_id, reason_codes, actor) per DEDUP_WINDOW.
- Bounded: at most MAX_RECORDS records per store and MAX_REASON_CODES codes per
  record; at capacity the write is refused with 'capacity_reached' (no eviction).
- The actor is stored in clear (same as review and publish events); the revision
  only as SHA-256 digest.
This store is an observation, NOOIT a gate authority.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = 'publication-refusal-audit-v1'
STORE_STATUS = 'temporary_file_store_pending_postgres_table'
FILE_NAME = 'publication_refusal_audit.jsonl'
DEDUP_WINDOW = timedelta(minutes=10)
MAX_RECORDS = 5000
MAX_REASON_CODES = 128
_LOCK = threading.Lock()


def store_path(console) -> Path:
    return Path(console._ledger_path).parent / FILE_NAME


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_refusal(path: Path, *, snapshot_id: str, object_version: str, actor: str,
                   reason_codes: list[str], revision, clock: datetime | None = None) -> str:
    """Return 'recorded', 'deduplicated' or 'capacity_reached'. Raises on I/O failure."""
    clock = clock or datetime.now(timezone.utc)
    codes = list(reason_codes)[:MAX_REASON_CODES]
    key = [str(snapshot_id), codes, str(actor)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, path.open('a+', encoding='utf-8') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows = [json.loads(line) for line in handle if line.strip()]
            for row in rows:
                if ([row.get('snapshot_id'), row.get('reason_codes'), row.get('actor')] == key
                        and clock - datetime.fromisoformat(row['recorded_at']) < DEDUP_WINDOW):
                    return 'deduplicated'
            if len(rows) >= MAX_RECORDS:
                return 'capacity_reached'
            record = {'schema': SCHEMA, 'store_status': STORE_STATUS, 'event_type': 'publication_refused', 'recorded_at': clock.isoformat(),
                      'snapshot_id': key[0], 'object_version': str(object_version), 'actor': key[2],
                      'verdict': 'refused', 'reason_codes': codes,
                      'revision_sha256': hashlib.sha256(revision.encode()).hexdigest() if isinstance(revision, str) else None}
            handle.seek(0, os.SEEK_END)
            handle.write(json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
            return 'recorded'
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
