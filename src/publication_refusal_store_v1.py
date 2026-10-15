"""Separate append-only store for publication refusals (outside the review ledger).

Live store: PostgreSQL table workflow.publication_refusals (migration 018). The JSONL file
store is TIJDELIJK and for the single-worker file topology only: it MAG NIET go live. The
gate is the topology (assert_supported_topology PASS, one worker, no METIS_* store in
postgres mode), NOOIT an environment marker such as WEBSITE_SITE_NAME; any other topology
without the PostgreSQL workflow store raises RefusalStoreUnavailable.

Rules (B18):
- A publication_refused record MAG NIET enter the review ledger hash chain; it MOET
  only be written here. Existing ledger event hashes MOETEN NOOIT change.
- Records are NOOIT rewritten; only retention/rotation removes old records.
- The PostgreSQL refusal path is ONE transactional INSERT (dedup inside that statement): it
  MAG NIET take an advisory lock and MAG NIET run DELETE. Table retention is the explicit
  maintenance command apply_retention (scripts/publication_refusal_retention.py); it MAG
  NIET run per refusal.
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
_POSTGRES_MODE_KEYS = ('METIS_CANONICAL_STORE', 'METIS_WORKFLOW_STORE', 'METIS_WORKFLOW_DOCUMENT_STORE',
                       'METIS_WORKFLOW_REVIEW_STORE', 'METIS_WORKFLOW_REMAINING_STORE')


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
                row = con.execute(
                    'INSERT INTO workflow.publication_refusals(recorded_at, snapshot_id, object_version, actor, verdict,'
                    ' reason_codes, revision_sha256, dedup_key, schema_version)'
                    ' SELECT %s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s WHERE NOT EXISTS ('
                    'SELECT 1 FROM workflow.publication_refusals WHERE dedup_key=%s AND recorded_at > %s)'
                    ' RETURNING refusal_id',
                    (clock, key[0], record['object_version'], key[2], 'refused', json.dumps(key[1]),
                     record['revision_sha256'], dedup, SCHEMA, dedup, clock - DEDUP_WINDOW)).fetchone()
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
    with workflow_store._connect() as con:
        with con.transaction():
            con.execute('DELETE FROM workflow.publication_refusals WHERE recorded_at < %s',
                        (clock - timedelta(days=days),))
            con.execute('DELETE FROM workflow.publication_refusals WHERE refusal_id <= '
                        '(SELECT max(refusal_id) FROM workflow.publication_refusals) - %s', (rows,))
    return {'status': 'PASS', 'retention_days': days, 'max_rows': rows}


def file_store_allowed(environ=None) -> bool:
    """Topology gate for the TIJDELIJK file store (single-worker file topology only)."""
    from src.topology_bound_v1 import TopologyBoundError, assert_supported_topology
    env = os.environ if environ is None else environ
    try:
        topology = assert_supported_topology(env)
    except TopologyBoundError:
        return False
    if topology['workers'] != 1 or topology['instances'] != 1:
        return False
    return not any(str(env.get(name, '') or '').strip().lower() == 'postgres' for name in _POSTGRES_MODE_KEYS)


def postgres_store(console):
    workflow = getattr(console, 'workflow_document_store', None)
    return PostgresRefusalStore(workflow) if workflow is not None and hasattr(workflow, '_connect') else None


def append(console, *, snapshot_id, object_version, actor, reason_codes, revision, on_corrupt=None) -> str:
    """Topology dispatch: PostgreSQL table when present; file only in the single-worker file topology (MAG NIET go live)."""
    pg = postgres_store(console)
    if pg is not None:
        return pg.append(snapshot_id=snapshot_id, object_version=object_version, actor=actor,
                         reason_codes=reason_codes, revision=revision)
    if not file_store_allowed():
        raise RefusalStoreUnavailable('refusal_file_store_not_allowed_live')
    return append_refusal(store_path(console), snapshot_id=snapshot_id, object_version=object_version, actor=actor,
                          reason_codes=reason_codes, revision=revision, on_corrupt=on_corrupt)
