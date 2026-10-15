"""Separate append-only store for publication refusals (outside the review ledger).

Live store: PostgreSQL table workflow.publication_refusals (migration 018). The JSONL file
store is TIJDELIJK and for local/test topologies only: it MAG NIET go live (Azure,
WEBSITE_SITE_NAME set, without the PostgreSQL workflow store raises RefusalStoreUnavailable).

Rules (B18):
- A publication_refused record MAG NIET enter the review ledger hash chain; it MOET
  only be written here. Existing ledger event hashes MOETEN NOOIT change.
- Records are NOOIT rewritten; only retention/rotation removes old records.
- Dedup: one record per (snapshot_id, reason_codes, actor) per DEDUP_WINDOW.
- Bounded: MAX_REASON_CODES per record; the file rotates at MAX_FILE_BYTES (one rotated
  generation kept) and the table keeps RETENTION_DAYS / MAX_ROWS. A full store MAG NIET
  permanently refuse new records.
- No full-file reads on the write path: dedup reads at most TAIL_BYTES.
- A corrupt record is skipped and reported (on_corrupt) and NOOIT blocks later writes.
- The actor is stored in clear (as review and publish events); the revision only as SHA-256.
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
POSTGRES_STATUS = 'postgres_table'
FILE_NAME = 'publication_refusal_audit.jsonl'
DEDUP_WINDOW = timedelta(minutes=10)
MAX_REASON_CODES = 128
MAX_FILE_BYTES = 4 * 1024 * 1024
TAIL_BYTES = 256 * 1024
RETENTION_DAYS = 400
MAX_ROWS = 200_000
RECORDS_LIMIT = 500
_LOCK = threading.Lock()
_ADVISORY_KEY = 7_629_001


class RefusalStoreUnavailable(RuntimeError):
    """No allowed refusal store in this topology (file store MAG NIET go live)."""


def store_path(console) -> Path:
    return Path(console._ledger_path).parent / FILE_NAME


def rotated_path(path: Path) -> Path:
    return path.with_name(path.name + '.1')


def _parse(lines, on_corrupt=None):
    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('not an object')
            datetime.fromisoformat(row['recorded_at'])
        except Exception as error:  # skipped and reported, NOOIT blocking
            if on_corrupt is not None:
                on_corrupt(type(error).__name__)
            continue
        rows.append(row)
    return rows


def read_records(path: Path, on_corrupt=None) -> list[dict]:
    """Export/backup read (not the write path)."""
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8', errors='replace') as handle:
        return _parse(handle, on_corrupt)


def _key(snapshot_id, reason_codes, actor):
    return [str(snapshot_id), list(reason_codes)[:MAX_REASON_CODES], str(actor)]


def _record(key, object_version, revision, clock, status):
    return {'schema': SCHEMA, 'store_status': status, 'event_type': 'publication_refused',
            'recorded_at': clock.isoformat(), 'snapshot_id': key[0], 'object_version': str(object_version),
            'actor': key[2], 'verdict': 'refused', 'reason_codes': key[1],
            'revision_sha256': hashlib.sha256(revision.encode()).hexdigest() if isinstance(revision, str) else None}


def append_refusal(path: Path, *, snapshot_id: str, object_version: str, actor: str,
                   reason_codes: list[str], revision, clock: datetime | None = None, on_corrupt=None) -> str:
    """File store (TIJDELIJK, local only). Returns 'recorded' or 'deduplicated'."""
    clock = clock or datetime.now(timezone.utc)
    key = _key(snapshot_id, reason_codes, actor)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, path.open('a+', encoding='utf-8', errors='replace') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(0, size - TAIL_BYTES)
            handle.seek(start)
            lines = handle.read(TAIL_BYTES).splitlines()
            if start and lines:
                lines = lines[1:]  # first line may be partial
            for row in _parse(lines, on_corrupt):
                try:
                    recent = clock - datetime.fromisoformat(row['recorded_at']) < DEDUP_WINDOW
                except Exception:
                    recent = False
                if recent and [row.get('snapshot_id'), row.get('reason_codes'), row.get('actor')] == key:
                    return 'deduplicated'
            line = json.dumps(_record(key, object_version, revision, clock, STORE_STATUS),
                              sort_keys=True, separators=(',', ':')) + '\n'
            if size >= MAX_FILE_BYTES:
                os.replace(path, rotated_path(path))  # rotation; one generation kept
                with path.open('a', encoding='utf-8') as fresh:
                    fresh.write(line)
                    fresh.flush()
                    os.fsync(fresh.fileno())
                return 'recorded'
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
            return 'recorded'
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class PostgresRefusalStore:
    """workflow.publication_refusals (migration 018). Uses the workflow store's connection."""

    def __init__(self, workflow_store):
        self._store = workflow_store

    def append(self, *, snapshot_id, object_version, actor, reason_codes, revision, clock=None) -> str:
        clock = clock or datetime.now(timezone.utc)
        key = _key(snapshot_id, reason_codes, actor)
        dedup = hashlib.sha256(json.dumps(key, separators=(',', ':')).encode()).hexdigest()
        record = _record(key, object_version, revision, clock, POSTGRES_STATUS)
        with self._store._connect() as con:
            with con.transaction():
                con.execute('SELECT pg_advisory_xact_lock(%s)', (_ADVISORY_KEY,))
                if con.execute('SELECT 1 FROM workflow.publication_refusals WHERE dedup_key=%s AND recorded_at > %s LIMIT 1',
                               (dedup, clock - DEDUP_WINDOW)).fetchone():
                    return 'deduplicated'
                con.execute(
                    'INSERT INTO workflow.publication_refusals(recorded_at, snapshot_id, object_version, actor, verdict,'
                    ' reason_codes, revision_sha256, dedup_key, schema_version) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)',
                    (clock, key[0], record['object_version'], key[2], 'refused', json.dumps(key[1]),
                     record['revision_sha256'], dedup, SCHEMA))
                # Retention: age and row bound; NOOIT a permanent refusal.
                con.execute('DELETE FROM workflow.publication_refusals WHERE recorded_at < %s',
                            (clock - timedelta(days=RETENTION_DAYS),))
                con.execute('DELETE FROM workflow.publication_refusals WHERE refusal_id <= '
                            '(SELECT refusal_id FROM workflow.publication_refusals ORDER BY refusal_id DESC OFFSET %s LIMIT 1)',
                            (MAX_ROWS,))
        return 'recorded'

    def records_for(self, snapshot_id, limit=RECORDS_LIMIT) -> list[dict]:
        with self._store._connect() as con:
            rows = con.execute(
                'SELECT recorded_at, snapshot_id, object_version, actor, verdict, reason_codes, revision_sha256, schema_version'
                ' FROM workflow.publication_refusals WHERE snapshot_id=%s ORDER BY refusal_id DESC LIMIT %s',
                (str(snapshot_id), int(limit))).fetchall()
        return [{'schema': r['schema_version'], 'store_status': POSTGRES_STATUS, 'event_type': 'publication_refused',
                 'recorded_at': r['recorded_at'].isoformat(), 'snapshot_id': r['snapshot_id'],
                 'object_version': r['object_version'], 'actor': r['actor'], 'verdict': r['verdict'],
                 'reason_codes': r['reason_codes'], 'revision_sha256': r['revision_sha256']} for r in rows]


def postgres_store(console):
    workflow = getattr(console, 'workflow_document_store', None)
    return PostgresRefusalStore(workflow) if workflow is not None and hasattr(workflow, '_connect') else None


def append(console, *, snapshot_id, object_version, actor, reason_codes, revision, on_corrupt=None) -> str:
    """Topology dispatch: PostgreSQL table when present; file only off-Azure (MAG NIET go live)."""
    pg = postgres_store(console)
    if pg is not None:
        return pg.append(snapshot_id=snapshot_id, object_version=object_version, actor=actor,
                         reason_codes=reason_codes, revision=revision)
    if os.environ.get('WEBSITE_SITE_NAME', '').strip():
        raise RefusalStoreUnavailable('refusal_file_store_not_allowed_live')
    return append_refusal(store_path(console), snapshot_id=snapshot_id, object_version=object_version, actor=actor,
                          reason_codes=reason_codes, revision=revision, on_corrupt=on_corrupt)
