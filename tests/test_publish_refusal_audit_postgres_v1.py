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

import src.publication_refusal_store_v1 as store
import src.publish_refusal_audit_v1 as audit
from src.request_diagnostics_v1 import _LOGGER
from src.review_ledger import read_events, verify_ledger
from tests.test_vsa_publish_document_v1 import (  # noqa: F401 - fixture import
    MemoryCanonicalStore, MemorySourceStore, _ready_console, workflow_postgres,
)

pytestmark = [pytest.mark.release_control_opslag, pytest.mark.release_control_releasebewijs]


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv('METIS_AUDIT_HMAC_KEY', 'pg-audit-key')
    monkeypatch.setattr(audit, '_FAILURE_COUNT', [0])


def _blocked(tmp_path, config):
    console, accounts, receipt = _ready_console(tmp_path, config, MemoryCanonicalStore(), MemorySourceStore())
    real = console.consider_publish

    def blocked(**kwargs):
        return {**real(**kwargs), 'publish_allowed': False, 'blockers': ['fixture_forced_refusal']}
    console.consider_publish = blocked
    return console, str(receipt['snapshot_id']), accounts['publisher']['account_id']


def _chain(console):
    return [(e['event_type'], e['event_hash'], e.get('previous_event_hash')) for e in read_events(console._ledger_path)]


def test_postgres_refusal_outside_ledger_chain_and_deduplicated(tmp_path, workflow_postgres):
    console, sid, actor = _blocked(tmp_path, workflow_postgres)
    before = _chain(console)
    results = [console.publish(actor_id=actor, snapshot_id=sid) for _ in range(3)]
    assert all(r['status'] == 'BLOCKED' and r['blockers'] == ['fixture_forced_refusal'] for r in results)
    assert _chain(console) == before
    assert verify_ledger(console._ledger_path) == []
    [record] = store.read_records(store.store_path(console))
    assert record['actor'] == actor and record['snapshot_id'] == sid
    assert len(record['revision_sha256']) == 64  # m2. token MAG NIET be stored verbatim


def test_postgres_store_failure_keeps_verdict_and_emits_diagnostic(tmp_path, workflow_postgres, monkeypatch):
    warnings = []
    monkeypatch.setattr(_LOGGER, 'warning', lambda fmt, msg: warnings.append(json.loads(msg)))

    def failing(*args, **kwargs):
        raise OSError('private failure')
    monkeypatch.setattr(store, 'append_refusal', failing)
    console, sid, actor = _blocked(tmp_path, workflow_postgres)
    before = _chain(console)
    result = console.publish(actor_id=actor, snapshot_id=sid)
    assert result['status'] == 'BLOCKED' and result['blockers'] == ['fixture_forced_refusal']
    assert _chain(console) == before
    assert [w['stage'] for w in warnings if w.get('event') == 'publication_refusal_audit_failed'] == ['durable_store']
