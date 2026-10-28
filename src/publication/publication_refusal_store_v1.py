"""Separate append-only store for publication refusals (outside the review ledger).

Store: PostgreSQL table workflow.publication_refusals (migration 018), the only refusal
store since D6b; a console without the PostgreSQL workflow store raises
RefusalStoreUnavailable. The JSONL helpers below only read or export files written by
the retired file topology; no runtime path writes them.

Rules (B18):
- A publication_refused record MAG NIET enter the review ledger hash chain; it MOET
  only be written here. Existing ledger event hashes MOETEN NOOIT change.
- Records are NOOIT rewritten; only retention/rotation removes old records.
- The PostgreSQL refusal path is ONE transactional INSERT … ON CONFLICT (dedup_key) DO NOTHING
  on the UNIQUE dedup_key (key + 10-minute window bucket); a duplicate row MAG NIET exist. It
  MAG NIET take an advisory lock and MAG NIET run DELETE. Table retention is the explicit
  maintenance command apply_retention (scripts/publication_refusal_retention.py); it MAG
  NIET run per refusal.
- Dedup: one record per (snapshot_id, reason_codes, actor) per DEDUP_WINDOW.
- Bounded: MAX_REASON_CODES per record; the table keeps RETENTION_DAYS / MAX_ROWS. A full
  store MAG NIET permanently refuse new records.
- A corrupt legacy file record is skipped and reported (on_corrupt) on export.
- The actor is stored in clear ONLY under Lex's conditions (account_id only, least-privilege access,
  retention in docs/RETENTION_MATRIX.md) and MAG NIET be exported; the revision only as SHA-256.
This store is an observation, NOOIT a gate authority.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCHEMA = 'publication-refusal-audit-v1'
STORE_STATUS = 'temporary_file_store_pending_postgres_table'
POSTGRES_STATUS = 'postgres_table'
FILE_NAME = 'publication_refusal_audit.jsonl'
DEDUP_WINDOW = timedelta(minutes=10)
MAX_REASON_CODES = 128
RETENTION_DAYS = 400
MAX_ROWS = 200_000
RECORDS_LIMIT = 500
_LOCK = threading.Lock()



class RefusalStoreUnavailable(RuntimeError):
    """No PostgreSQL refusal store on this console."""


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
    """Export/backup read (not the write path): rotated generation first, then the active file."""
    rows: list[dict] = []
    with _LOCK:  # same process lock as rotation, so a rotation MAG NIET split this read in-process
        for part in (rotated_path(path), path):
            if part.exists():
                with part.open('r', encoding='utf-8', errors='replace') as handle:
                    rows.extend(_parse(handle, on_corrupt))
    return rows


def dedup_key(key, clock: datetime) -> str:
    """Key + fixed DEDUP_WINDOW bucket (UTC epoch); identical within a bucket, new in the next."""
    bucket = int(clock.timestamp() // DEDUP_WINDOW.total_seconds())
    return hashlib.sha256(json.dumps([key, bucket], separators=(',', ':')).encode()).hexdigest()


def _key(snapshot_id, reason_codes, actor):
    return [str(snapshot_id), list(reason_codes)[:MAX_REASON_CODES], str(actor)]


def _record(key, object_version, revision, clock, status):
    return {'schema': SCHEMA, 'store_status': status, 'event_type': 'publication_refused',
            'recorded_at': clock.isoformat(), 'snapshot_id': key[0], 'object_version': str(object_version),
            'actor': key[2], 'verdict': 'refused', 'reason_codes': key[1],
            'revision_sha256': hashlib.sha256(revision.encode()).hexdigest() if isinstance(revision, str) else None}


class PostgresRefusalStore:
    """workflow.publication_refusals (migration 018). Uses the workflow store's connection."""

    def __init__(self, workflow_store):
        self._store = workflow_store

    def append(self, *, snapshot_id, object_version, actor, reason_codes, revision, clock=None) -> str:
        clock = clock or datetime.now(timezone.utc)
        key = _key(snapshot_id, reason_codes, actor)
        dedup = dedup_key(key, clock)
        record = _record(key, object_version, revision, clock, POSTGRES_STATUS)
        with self._store._connect() as con:
            with con.transaction():
                row = con.execute(
                    'INSERT INTO workflow.publication_refusals(recorded_at, snapshot_id, object_version, actor, verdict,'
                    ' reason_codes, revision_sha256, dedup_key, schema_version)'
                    ' VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)'
                    ' ON CONFLICT (dedup_key) DO NOTHING RETURNING refusal_id',
                    (clock, key[0], record['object_version'], key[2], 'refused', json.dumps(key[1]),
                     record['revision_sha256'], dedup, SCHEMA)).fetchone()
        if row is None:
            return 'deduplicated'
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


def apply_retention(workflow_store, *, clock: datetime | None = None,
                    retention_days: int | None = None, max_rows: int | None = None) -> dict:
    """Explicit maintenance (NOOIT per refusal): age bound, then row bound, without OFFSET."""
    clock = clock or datetime.now(timezone.utc)
    days = RETENTION_DAYS if retention_days is None else int(retention_days)
    rows = MAX_ROWS if max_rows is None else int(max_rows)
    if rows <= 0 or days <= 0:
        raise ValueError('refusal_retention_bounds_must_be_positive')  # MAG NIET empty the table
    with workflow_store._connect() as con:
        with con.transaction():
            con.execute('DELETE FROM workflow.publication_refusals WHERE recorded_at < %s',
                        (clock - timedelta(days=days),))
            con.execute('DELETE FROM workflow.publication_refusals WHERE refusal_id <= '
                        '(SELECT max(refusal_id) FROM workflow.publication_refusals) - %s', (rows,))
    return {'status': 'PASS', 'retention_days': days, 'max_rows': rows}


def postgres_store(console):
    workflow = getattr(console, 'workflow_document_store', None)
    return PostgresRefusalStore(workflow) if workflow is not None and hasattr(workflow, '_connect') else None


def append(console, *, snapshot_id, object_version, actor, reason_codes, revision, on_corrupt=None) -> str:
    """PostgreSQL is the only refusal store (D6b); without it the refusal is not recorded."""
    pg = postgres_store(console)
    if pg is None:
        raise RefusalStoreUnavailable('refusal_postgres_store_required')
    return pg.append(snapshot_id=snapshot_id, object_version=object_version, actor=actor,
                     reason_codes=reason_codes, revision=revision)
