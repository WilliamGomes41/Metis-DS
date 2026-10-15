"""Publish-gate refusal audit event: observation only, verdicts identical.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable authority stale concurrent
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import hashlib
import hmac
import json
from copy import deepcopy

import pytest

import src.publish_refusal_audit_v1 as audit
from src.request_diagnostics_v1 import _LOGGER
from tests.test_durable_publication_console_v1 import MemoryCanonicalStore, _ready_console
from tests.test_recoverable_formation_v1 import system


@pytest.fixture(autouse=True)
def audit_key(monkeypatch):
    monkeypatch.setenv('METIS_AUDIT_HMAC_KEY', 'test-audit-key')


@pytest.fixture
def events(monkeypatch):
    rows = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: rows.append(json.loads(msg)))
    return rows


def _refusals(rows):
    return [r for r in rows if r.get('event') == 'publication_refused']


def _blocked_base(tmp_path):
    console, sid, actor, reviewer, *_ = system(tmp_path)  # partial formation: gate MOET refuse
    return console, sid, reviewer


def _forced_block(console):
    real = console.consider_publish

    def blocked(**kwargs):
        verdict = real(**kwargs)
        return {**verdict, 'publish_allowed': False, 'blockers': ['fixture_forced_refusal']}
    console.consider_publish = blocked


def _durable_blocked(tmp_path):
    authority = MemoryCanonicalStore()
    console, accounts, receipt = _ready_console(tmp_path, authority)
    _forced_block(console)
    return console, receipt['snapshot_id'], accounts['publisher']['account_id']


@pytest.mark.parametrize('build', [_blocked_base, _durable_blocked], ids=['file', 'durable'])
def test_refusal_emits_one_bounded_audit_event(tmp_path, events, build):
    console, sid, actor = build(tmp_path)
    result = console.publish(actor_id=actor, snapshot_id=sid)
    assert result['status'] == 'BLOCKED'
    [event] = _refusals(events)
    assert event['snapshot_id'] == sid
    assert event['actor_hmac'] == hmac.new(b'test-audit-key', actor.encode(), hashlib.sha256).hexdigest()
    assert actor not in json.dumps(event) and 'test-audit-key' not in json.dumps(events)
    from src.review_ledger import read_events
    [durable] = [e for e in read_events(console._ledger_path) if e['event_type'] == 'publication_refused']
    assert durable['actor'] == actor and durable['object_id'] == sid
    assert durable['details']['reason_codes'] == event['reason_codes']
    assert event['reason_codes'] == [c if audit._CODE.fullmatch(c) else 'unrecognized_reason' for c in result['blockers']]
    assert event['verdict'] == 'refused'
    assert event['revision_sha256'] is None or len(event['revision_sha256']) == 64


@pytest.mark.parametrize('build', [_blocked_base, _durable_blocked], ids=['file', 'durable'])
def test_refusal_verdict_is_identical_with_and_without_audit(tmp_path, events, monkeypatch, build):
    with_audit, sid_a, actor_a = build(tmp_path / 'a')
    verdict_a = with_audit.publish(actor_id=actor_a, snapshot_id=sid_a)
    envelope_a = deepcopy(with_audit._envelope(sid_a))
    monkeypatch.setattr(audit, 'record_publish_refusal', lambda *args, **kwargs: None)
    without, sid_b, actor_b = build(tmp_path / 'b')
    verdict_b = without.publish(actor_id=actor_b, snapshot_id=sid_b)
    envelope_b = deepcopy(without._envelope(sid_b))
    normalise = lambda v, sid: json.loads(json.dumps(v).replace(sid, 'SID'))
    assert normalise(verdict_a, sid_a) == normalise(verdict_b, sid_b)
    assert envelope_a['state'] == envelope_b['state']
    assert envelope_a.get('publication_eligibility') == envelope_b.get('publication_eligibility')


def test_allowed_publication_emits_no_refusal_and_publishes_identically(tmp_path, events, monkeypatch):
    authority = MemoryCanonicalStore()
    console, accounts, receipt = _ready_console(tmp_path, authority)
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=receipt['snapshot_id'])
    assert result['status'] == 'PASS'
    assert _refusals(events) == []


def test_audit_failure_never_changes_the_verdict(tmp_path, events, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError('private logging failure')
    monkeypatch.setattr(_LOGGER, 'info', broken)
    console, sid, actor = _blocked_base(tmp_path)
    assert console.publish(actor_id=actor, snapshot_id=sid)['status'] == 'BLOCKED'


def test_hostile_reason_codes_are_bounded(events):
    audit.record_publish_refusal(None, actor_id='a', snapshot_id='snap-x',
        verdict={'publish_allowed': False, 'blockers': ['ok_code', 'Private Text!', 7] + ['x'] * 500})
    [event] = _refusals(events)
    assert event['reason_codes'][:3] == ['ok_code', 'unrecognized_reason', 'unrecognized_reason']
    assert len(event['reason_codes']) == audit.MAX_REASON_CODES
    assert 'Private' not in json.dumps(event)
    audit.record_publish_refusal(None, actor_id='a', snapshot_id='snap-x', verdict={'publish_allowed': True})
    assert len(_refusals(events)) == 1  # allowed verdicts MOETEN NOOIT a refusal event produce


def test_concurrent_refusals_each_emit_one_event_and_identical_verdicts(tmp_path, events):
    from concurrent.futures import ThreadPoolExecutor
    console, sid, actor = _blocked_base(tmp_path)
    with ThreadPoolExecutor(4) as pool:
        verdicts = list(pool.map(lambda _: console.publish(actor_id=actor, snapshot_id=sid), range(4)))
    assert all(v == verdicts[0] for v in verdicts) and verdicts[0]['status'] == 'BLOCKED'
    assert len(_refusals(events)) == 4


@pytest.mark.parametrize('build', [_blocked_base, _durable_blocked], ids=['file', 'durable'])
def test_verdict_identical_when_durable_audit_write_raises(tmp_path, events, monkeypatch, build):
    import src.review_ledger as ledger
    reference, sid_r, actor_r = build(tmp_path / 'ref')
    expected = reference.publish(actor_id=actor_r, snapshot_id=sid_r)
    original = ledger.append_event

    def failing(path, **kwargs):
        if kwargs.get('event_type') == 'publication_refused':
            raise OSError('private audit store failure')
        return original(path, **kwargs)
    monkeypatch.setattr(ledger, 'append_event', failing)
    console, sid, actor = build(tmp_path / 'broken')
    verdict = console.publish(actor_id=actor, snapshot_id=sid)
    normalise = lambda v, s: json.loads(json.dumps(v).replace(s, 'SID'))
    assert normalise(verdict, sid) == normalise(expected, sid_r)


def test_without_hmac_key_actor_is_not_logged(tmp_path, events, monkeypatch):
    monkeypatch.delenv('METIS_AUDIT_HMAC_KEY')
    console, sid, actor = _blocked_base(tmp_path)
    console.publish(actor_id=actor, snapshot_id=sid)
    [event] = _refusals(events)
    assert event['actor_hmac'] is None and actor not in json.dumps(event)
