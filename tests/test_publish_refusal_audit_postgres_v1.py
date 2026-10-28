"""#629 F3: publication refusal audit in the PostgreSQL workflow topology.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable authority concurrent
# release-control-evidence: releasebewijs

Runs only with METIS_TEST_POSTGRES_DSN (CI postgres:16 service). Rules (B18):
the refusal MAG NIET enter the review ledger hash chain; the verdict MAG NIET change;
a store failure MOET emit publication_refusal_audit_failed.
"""
from __future__ import annotations

import json

import pytest

import src.publication.publication_refusal_store_v1 as store
import src.publication.publish_refusal_audit_v1 as audit
from src.request_diagnostics_v1 import _LOGGER
from src.review.review_ledger import read_events, verify_ledger
from tests.test_vsa_publish_document_v1 import (  # noqa: F401 - fixture import
    canonical_store, MemorySourceStore, _ready_console, workflow_postgres,
)

pytestmark = [pytest.mark.release_control_opslag, pytest.mark.release_control_releasebewijs]


@pytest.fixture()
def refusal_postgres(workflow_postgres):  # noqa: F811 - adds migration 018 to the shared schema
    import psycopg
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[1] / 'db' / 'migrations' / '018_publication_refusal_audit.sql').read_text()
    with psycopg.connect(workflow_postgres.dsn, autocommit=True) as con:
        con.execute(sql)  # whole file: 018 has a DO $$ block (Sherlock 02:10 F1)
    return workflow_postgres


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv('METIS_AUDIT_HMAC_KEY', 'pg-audit-key')
    monkeypatch.setattr(audit, '_FAILURE_COUNT', [0])


def _blocked(tmp_path, config):
    console, accounts, receipt = _ready_console(tmp_path, config, canonical_store(config), MemorySourceStore())
    real = console.consider_publish

    def blocked(**kwargs):
        return {**real(**kwargs), 'publish_allowed': False, 'blockers': ['fixture_forced_refusal']}
    console.consider_publish = blocked
    return console, str(receipt['snapshot_id']), accounts['publisher']['account_id']


def _chain(console):
    return [(e['event_type'], e['event_hash'], e.get('previous_event_hash')) for e in read_events(console._ledger_path)]


def test_postgres_refusal_outside_ledger_chain_and_deduplicated(tmp_path, refusal_postgres):
    console, sid, actor = _blocked(tmp_path, refusal_postgres)
    before = _chain(console)
    results = [console.publish(actor_id=actor, snapshot_id=sid) for _ in range(3)]
    assert all(r['status'] == 'BLOCKED' and r['blockers'] == ['fixture_forced_refusal'] for r in results)
    assert _chain(console) == before
    assert verify_ledger(console._ledger_path) == []
    [record] = store.postgres_store(console).records_for(sid)  # table, deduplicated to one
    assert record['actor'] == actor and record['snapshot_id'] == sid
    assert record['store_status'] == store.POSTGRES_STATUS
    assert not store.store_path(console).exists()  # file store MAG NIET be used with PostgreSQL
    assert len(record['revision_sha256']) == 64  # m2. token MAG NIET be stored verbatim


def test_postgres_store_failure_keeps_verdict_and_emits_diagnostic(tmp_path, refusal_postgres, monkeypatch):
    warnings = []
    monkeypatch.setattr(_LOGGER, 'warning', lambda fmt, msg: warnings.append(json.loads(msg)))

    def failing(*args, **kwargs):
        raise OSError('private failure')
    monkeypatch.setattr(store.PostgresRefusalStore, 'append', failing)
    console, sid, actor = _blocked(tmp_path, refusal_postgres)
    before = _chain(console)
    result = console.publish(actor_id=actor, snapshot_id=sid)
    assert result['status'] == 'BLOCKED' and result['blockers'] == ['fixture_forced_refusal']
    assert _chain(console) == before
    assert [w['stage'] for w in warnings if w.get('event') == 'publication_refusal_audit_failed'] == ['durable_store']


def test_postgres_refusal_path_never_deletes_and_retention_is_maintenance(tmp_path, refusal_postgres):
    # Sherlock re-audit #636 F3: refusals only INSERT; apply_retention is the explicit maintenance command.
    console, sid, actor = _blocked(tmp_path, refusal_postgres)
    pg = store.postgres_store(console)
    outcomes = [pg.append(snapshot_id=sid, object_version='1', actor=f'a{n}', reason_codes=['r'], revision=None) for n in range(6)]
    assert outcomes == ['recorded'] * 6
    assert len(pg.records_for(sid)) == 6  # the refusal path MAG NIET delete
    assert pg.append(snapshot_id=sid, object_version='1', actor='a0', reason_codes=['r'], revision=None) == 'deduplicated'
    assert store.apply_retention(console.workflow_document_store, max_rows=3)['status'] == 'PASS'
    rows = pg.records_for(sid)
    assert [r['actor'] for r in rows] == ['a5', 'a4', 'a3']


def test_postgres_concurrent_identical_refusals_leave_one_row(tmp_path, refusal_postgres):
    # Metis F1-4: two concurrent identical refusals MOETEN leave exactly 1 row (UNIQUE + ON CONFLICT).
    import threading
    from datetime import datetime, timezone
    console, sid, actor = _blocked(tmp_path, refusal_postgres)
    pg = store.postgres_store(console)
    clock = datetime.now(timezone.utc)
    barrier, outcomes = threading.Barrier(2), []

    def refuse():
        barrier.wait()
        outcomes.append(pg.append(snapshot_id=sid, object_version='1', actor=actor, reason_codes=['r'],
                                  revision=None, clock=clock))
    threads = [threading.Thread(target=refuse) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ['deduplicated', 'recorded']
    assert len(pg.records_for(sid)) == 1
