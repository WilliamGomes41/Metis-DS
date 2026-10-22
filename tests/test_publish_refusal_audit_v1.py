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
import src.publication_refusal_store_v1 as store
from src.request_diagnostics_v1 import _LOGGER
from tests.test_durable_publication_console_v1 import MemoryCanonicalStore, _ready_console
from tests.test_recoverable_formation_v1 import system


@pytest.fixture(autouse=True)
def audit_key(monkeypatch):
    monkeypatch.setenv('METIS_AUDIT_HMAC_KEY', 'test-audit-key')
    monkeypatch.setattr(audit, '_FAILURE_COUNT', [0])
    monkeypatch.setattr(audit, '_SUPPRESSED_COUNT', [0], raising=False)


@pytest.fixture
def events(monkeypatch):
    rows = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: rows.append(json.loads(msg)))
    return rows


def _refusals(rows):
    return [r for r in rows if r.get('event') == 'publication_refused']


def _blocked_base(tmp_path, *, production_console):
    console, sid, actor, reviewer, *_ = system(tmp_path,
        production_console=lambda **options: production_console(isolated=True, **options))
    return console, sid, reviewer


def _forced_block(console):
    real = console.consider_publish

    def blocked(**kwargs):
        verdict = real(**kwargs)
        return {**verdict, 'publish_allowed': False, 'blockers': ['fixture_forced_refusal']}
    console.consider_publish = blocked


def _durable_blocked(tmp_path, *, production_console):
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console, isolated=True)
    _forced_block(console)
    return console, receipt['snapshot_id'], accounts['publisher']['account_id']


def test_refusal_emits_one_bounded_audit_event(tmp_path, events, build):
    console, sid, actor = build(tmp_path)
    result = console.publish(actor_id=actor, snapshot_id=sid)
    assert result['status'] == 'BLOCKED'
    [event] = _refusals(events)
    assert event['snapshot_id'] == sid
    assert event['actor_hmac'] == hmac.new(b'test-audit-key', actor.encode(), hashlib.sha256).hexdigest()
    assert actor not in json.dumps(event) and 'test-audit-key' not in json.dumps(events)
    from src.review_ledger import read_events
    assert [e for e in read_events(console._ledger_path) if e['event_type'] == 'publication_refused'] == []
    [durable] = store.postgres_store(console).records_for(sid)
    assert durable['actor'] == actor and durable['snapshot_id'] == sid
    assert durable['reason_codes'] == event['reason_codes']
    assert event['reason_codes'] == [c if audit._CODE.fullmatch(c) else 'unrecognized_reason' for c in result['blockers']]
    assert event['verdict'] == 'refused'
    assert event['revision_sha256'] is None or len(event['revision_sha256']) == 64


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


def test_allowed_publication_emits_no_refusal_and_publishes_identically(tmp_path, events, monkeypatch, *, production_console):
    console, accounts, receipt = _ready_console(tmp_path, production_console=production_console, isolated=True)
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=receipt['snapshot_id'])
    assert result['status'] == 'PASS'
    assert _refusals(events) == []


def test_audit_failure_never_changes_the_verdict(tmp_path, events, monkeypatch, *, production_console):
    def broken(*args, **kwargs):
        raise OSError('private logging failure')
    monkeypatch.setattr(_LOGGER, 'info', broken)
    console, sid, actor = _blocked_base(tmp_path, production_console=production_console)
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


def test_concurrent_refusals_each_emit_one_event_and_identical_verdicts(tmp_path, events, *, production_console):
    from concurrent.futures import ThreadPoolExecutor
    console, sid, actor = _blocked_base(tmp_path, production_console=production_console)
    with ThreadPoolExecutor(4) as pool:
        verdicts = list(pool.map(lambda _: console.publish(actor_id=actor, snapshot_id=sid), range(4)))
    assert all(v == verdicts[0] for v in verdicts) and verdicts[0]['status'] == 'BLOCKED'
    assert len(_refusals(events)) == 4


def test_verdict_identical_when_durable_audit_write_raises(tmp_path, events, monkeypatch, build):
    import src.review_ledger as ledger
    reference, sid_r, actor_r = build(tmp_path / 'ref')
    expected = reference.publish(actor_id=actor_r, snapshot_id=sid_r)
    original = ledger.append_event

    def failing(path, **kwargs):
        if kwargs.get('event_type') == 'publication_refused':
            raise OSError('private audit store failure')
        return original(path, **kwargs)

    def failing_store(*args, **kwargs):
        raise OSError('private audit store failure')
    monkeypatch.setattr(ledger, 'append_event', failing)
    monkeypatch.setattr(store.PostgresRefusalStore, 'append', failing_store)
    console, sid, actor = build(tmp_path / 'broken')
    verdict = console.publish(actor_id=actor, snapshot_id=sid)
    normalise = lambda v, s: json.loads(json.dumps(v).replace(s, 'SID'))
    assert normalise(verdict, sid) == normalise(expected, sid_r)


def test_without_hmac_key_actor_is_not_logged(tmp_path, events, monkeypatch, *, production_console):
    monkeypatch.delenv('METIS_AUDIT_HMAC_KEY')
    console, sid, actor = _blocked_base(tmp_path, production_console=production_console)
    console.publish(actor_id=actor, snapshot_id=sid)
    [event] = _refusals(events)
    assert event['actor_hmac'] is None and actor not in json.dumps(event)


# --- #629 F1: separate append-only store, outside the review ledger hash chain ---

def test_refusal_never_enters_the_review_ledger_hash_chain(tmp_path, events, build):
    from src.review_ledger import read_events, verify_ledger
    console, sid, actor = build(tmp_path)
    before = [(e['event_type'], e['event_hash'], e.get('previous_event_hash')) for e in read_events(console._ledger_path)]
    assert console.publish(actor_id=actor, snapshot_id=sid)['status'] == 'BLOCKED'
    after = [(e['event_type'], e['event_hash'], e.get('previous_event_hash')) for e in read_events(console._ledger_path)]
    assert after == before, 'REFUSAL_IN_LEDGER_CHAIN'
    assert verify_ledger(console._ledger_path) == []
    [record] = store.postgres_store(console).records_for(sid)
    assert record['event_type'] == 'publication_refused' and record['actor'] == actor


def test_refusal_store_dedups_per_document_reason_actor_within_window(tmp_path, events, *, production_console):
    console, sid, actor = _blocked_base(tmp_path, production_console=production_console)
    for _ in range(3):
        assert console.publish(actor_id=actor, snapshot_id=sid)['status'] == 'BLOCKED'
    assert len(store.postgres_store(console).records_for(sid)) == 1
    assert len(_refusals(events)) == 3  # logs are not deduplicated


# --- #629 F2: bounded publication_refusal_audit_failed diagnostic, no silent except-pass ---

@pytest.fixture
def warnings_(monkeypatch):
    rows = []
    monkeypatch.setattr(_LOGGER, 'warning', lambda fmt, msg: rows.append(json.loads(msg)))
    return rows


def _failures(rows):
    return [r for r in rows if r.get('event') == 'publication_refusal_audit_failed']


def test_store_failure_emits_bounded_audit_failed_diagnostic(tmp_path, events, warnings_, monkeypatch, build):
    def failing_store(*args, **kwargs):
        raise OSError('private /secret/path failure hunter2')
    monkeypatch.setattr(store.PostgresRefusalStore, 'append', failing_store)
    console, sid, actor = build(tmp_path)
    assert console.publish(actor_id=actor, snapshot_id=sid)['status'] == 'BLOCKED'
    [failure] = _failures(warnings_)
    assert failure['stage'] == 'durable_store' and failure['error_class'] == 'OSError'
    assert failure['snapshot_id'] == sid
    text = json.dumps(warnings_)
    assert 'hunter2' not in text and '/secret/path' not in text and actor not in text
    assert set(failure) <= {'event', 'stage', 'error_class', 'outcome', 'snapshot_id', 'request_id', 'authority'}


def test_log_failure_emits_audit_failed_diagnostic(tmp_path, warnings_, monkeypatch, *, production_console):
    def broken(*args, **kwargs):
        raise OSError('private logging failure')
    monkeypatch.setattr(_LOGGER, 'info', broken)
    console, sid, actor = _blocked_base(tmp_path, production_console=production_console)
    assert console.publish(actor_id=actor, snapshot_id=sid)['status'] == 'BLOCKED'
    assert [f['stage'] for f in _failures(warnings_)] == ['log']


def test_audit_failed_diagnostic_is_bounded_per_process(warnings_, monkeypatch):
    monkeypatch.setattr(audit, '_FAILURE_COUNT', [0])
    monkeypatch.setattr(audit, '_SUPPRESSED_COUNT', [0])
    for _ in range(audit.MAX_FAILURE_DIAGNOSTICS + 50):
        audit._audit_failed('durable_store', error=OSError('x'), snapshot_id='s')
    assert len(_failures(warnings_)) == audit.MAX_FAILURE_DIAGNOSTICS
    # After the cap: exactly ONE suppression event with a counter; MAG NIET go silent.
    [suppressed] = [w for w in warnings_ if w.get('event') == 'publication_refusal_audit_failed_suppressed']
    assert suppressed['cap'] == audit.MAX_FAILURE_DIAGNOSTICS and suppressed['suppressed_count'] == 1
    assert audit.suppressed_failure_count() == 50


def test_hostile_error_class_and_snapshot_are_bounded(warnings_, monkeypatch):
    monkeypatch.setattr(audit, '_FAILURE_COUNT', [0])
    Hostile = type('Hostile Error <script>', (Exception,), {})
    audit._audit_failed('durable_store', error=Hostile(), snapshot_id='bad id with spaces' * 20)
    [failure] = _failures(warnings_)
    assert failure['error_class'] == 'unrecognized_error' and failure['snapshot_id'] is None


def test_no_silent_except_pass_in_refusal_audit():
    import inspect
    source = inspect.getsource(audit)
    assert 'except Exception:\n        pass' not in source and 'except Exception:\n            pass' not in source

def test_file_store_never_goes_live(tmp_path, monkeypatch):
    # Live topology (postgres mode) without a PostgreSQL refusal store: the file store MAG NIET be used.
    monkeypatch.setenv('WEBSITE_SITE_NAME', 'metis-prod')
    monkeypatch.setenv('METIS_WORKFLOW_DOCUMENT_STORE', 'postgres')
    from types import SimpleNamespace
    console = SimpleNamespace(_ledger_path=tmp_path/'ledger.jsonl', _envelope=lambda sid: {'version': '1'})
    sid, actor = 'fixture-snapshot', 'fixture-actor'
    with pytest.raises(store.RefusalStoreUnavailable):
        store.append(console, snapshot_id=sid, object_version='1', actor=actor, reason_codes=['r'], revision=None)
    assert not store.store_path(console).exists()


# --- Sherlock re-audit #636 F2: file store blocked by topology, not by WEBSITE_SITE_NAME ---

@pytest.mark.parametrize('env', [
    {'METIS_WORKFLOW_DOCUMENT_STORE': 'postgres'},
    {'METIS_WORKFLOW_STORE': 'postgres'},
    {'CONSOLE_GUNICORN_WORKERS': '2'},
    {'CONSOLE_INSTANCE_COUNT': '2'},
])
def test_file_store_blocked_by_topology_without_website_site_name(tmp_path, monkeypatch, env):
    monkeypatch.delenv('WEBSITE_SITE_NAME', raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    from types import SimpleNamespace
    console = SimpleNamespace(_ledger_path=tmp_path/'ledger.jsonl', _envelope=lambda sid: {'version': '1'})
    sid, actor = 'fixture-snapshot', 'fixture-actor'
    with pytest.raises(store.RefusalStoreUnavailable):
        store.append(console, snapshot_id=sid, object_version='1', actor=actor, reason_codes=['r'], revision=None)
    assert not store.store_path(console).exists()


# --- Sherlock re-audit #636 F3: the refusal path is one transactional INSERT; retention is maintenance ---

class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeCon:
    def __init__(self, row=(1,)):
        self.sql, self._row = [], row

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def transaction(self):
        return self

    def execute(self, sql, params=None):
        self.sql.append(' '.join(sql.split()).upper())
        return _FakeResult(self._row)


class _FakeWorkflow:
    def __init__(self, con):
        self.con = con

    def _connect(self):
        return self.con


def test_postgres_refusal_path_is_a_single_insert_without_lock_or_delete():
    con = _FakeCon()
    pg = store.PostgresRefusalStore(_FakeWorkflow(con))
    assert pg.append(snapshot_id='s', object_version='1', actor='a', reason_codes=['r'], revision=None) == 'recorded'
    assert len(con.sql) == 1 and con.sql[0].startswith('INSERT INTO WORKFLOW.PUBLICATION_REFUSALS')
    joined = ' '.join(con.sql)
    assert 'ADVISORY' not in joined and 'DELETE' not in joined and 'OFFSET' not in joined


def test_postgres_refusal_dedup_returns_deduplicated_when_insert_skips():
    con = _FakeCon(row=None)
    pg = store.PostgresRefusalStore(_FakeWorkflow(con))
    assert pg.append(snapshot_id='s', object_version='1', actor='a', reason_codes=['r'], revision=None) == 'deduplicated'


def test_retention_is_an_explicit_maintenance_command_without_offset():
    con = _FakeCon(row=(0,))
    result = store.apply_retention(_FakeWorkflow(con))
    assert result['status'] == 'PASS'
    assert con.sql and all(s.startswith(('DELETE', 'SELECT')) for s in con.sql)
    assert 'OFFSET' not in ' '.join(con.sql) and 'ADVISORY' not in ' '.join(con.sql)


def test_retention_script_runs_apply_retention(monkeypatch, capsys):
    import scripts.publication_refusal_retention as script
    con = _FakeCon(row=(0,))
    monkeypatch.setattr(script, '_workflow_store', lambda: _FakeWorkflow(con))
    assert script.main(['--max-rows', '10', '--retention-days', '30']) == 0
    assert '"status": "PASS"' in capsys.readouterr().out and len(con.sql) == 2


# --- Metis F1-4: a duplicate row is NOT acceptable: unique dedup key + ON CONFLICT DO NOTHING ---

def test_migration_018_has_unique_dedup_key():
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[1] / 'db' / 'migrations' / '018_publication_refusal_audit.sql').read_text()
    assert 'UNIQUE (dedup_key)' in sql


def test_postgres_refusal_insert_uses_on_conflict_do_nothing_without_lock():
    con = _FakeCon()
    store.PostgresRefusalStore(_FakeWorkflow(con)).append(snapshot_id='s', object_version='1', actor='a',
                                                          reason_codes=['r'], revision=None)
    [sql] = con.sql
    assert 'ON CONFLICT (DEDUP_KEY) DO NOTHING' in sql and 'ADVISORY' not in sql and 'NOT EXISTS' not in sql


def test_dedup_key_is_stable_within_a_window_and_changes_across_windows():
    from datetime import datetime, timezone
    t0 = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc)
    k = lambda t, actor='a': store.dedup_key(['s', ['r'], actor], t)
    assert k(t0) == k(t0 + store.DEDUP_WINDOW / 2)
    assert k(t0) != k(t0 + store.DEDUP_WINDOW) and k(t0) != k(t0, actor='b')


@pytest.mark.parametrize('bad', ['0', '-1'])
def test_retention_script_refuses_non_positive_max_rows(monkeypatch, bad):
    # Sherlock 02:10 F3: --max-rows <= 0 MAG NIET run (it would empty the table).
    import scripts.publication_refusal_retention as script
    con = _FakeCon(row=(0,))
    monkeypatch.setattr(script, '_workflow_store', lambda: _FakeWorkflow(con))
    with pytest.raises(SystemExit) as exit_info:
        script.main(['--max-rows', bad])
    assert exit_info.value.code == 2 and con.sql == []


def test_apply_retention_refuses_non_positive_max_rows():
    con = _FakeCon(row=(0,))
    with pytest.raises(ValueError):
        store.apply_retention(_FakeWorkflow(con), max_rows=0)
    assert con.sql == []


# --- Sherlock #636 P2: a failing durable write MOET emit publication_refusal_audit_failed (NOOIT silent) ---

def test_durable_store_failure_emits_audit_failed_diagnostic(tmp_path, monkeypatch, *, production_console):
    warnings = []
    monkeypatch.setattr(_LOGGER, 'warning', lambda fmt, msg: warnings.append(json.loads(msg)))

    def failing(*args, **kwargs):
        raise OSError('disk gone password=hunter2')
    monkeypatch.setattr(store, 'append', failing)
    console, sid, actor = _blocked_base(tmp_path, production_console=production_console)
    audit._append_durable(console, actor_id=actor, snapshot_id=sid, reason_codes=['r'], revision=None)
    failed = [w for w in warnings if w.get('event') == 'publication_refusal_audit_failed']
    assert [(w['stage'], w['error_class']) for w in failed] == [('durable_store', 'OSError')]
    assert 'hunter2' not in json.dumps(warnings)


@pytest.mark.parametrize('env', [{}, {'METIS_WORKFLOW_STORE': 'postgres'}, {'METIS_CANONICAL_STORE': 'postgres'}])
def test_console_without_postgres_refusal_store_is_fail_closed_and_reported(tmp_path, monkeypatch, env):
    # Sherlock thread (partial PostgreSQL routing), D6b: without the PostgreSQL store there is no
    # file fallback in any configuration; the refusal verdict MOET stand and the lost audit write
    # MOET be reported, NOOIT silent.
    warnings = []
    monkeypatch.setattr(_LOGGER, 'warning', lambda fmt, msg: warnings.append(json.loads(msg)))
    monkeypatch.delenv('WEBSITE_SITE_NAME', raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    from types import SimpleNamespace
    console = SimpleNamespace(_ledger_path=tmp_path/'ledger.jsonl', _envelope=lambda sid: {'version': '1'})
    sid, actor = 'fixture-snapshot', 'fixture-actor'
    assert store.postgres_store(console) is None
    audit._append_durable(console, actor_id=actor, snapshot_id=sid, reason_codes=['r'], revision=None)
    assert [(w['stage'], w['error_class']) for w in warnings if w.get('event') == 'publication_refusal_audit_failed'] \
        == [('durable_store', 'RefusalStoreUnavailable')]
    assert not store.store_path(console).exists()


# --- Sherlock #637 P2s ---

def test_diagnostic_cap_is_atomic_under_concurrency(warnings_, monkeypatch):
    import threading
    import time

    class SlowCounter(list):  # widens the check-then-increment window deterministically
        def __getitem__(self, index):
            value = list.__getitem__(self, index)
            time.sleep(0.002)
            return value
    monkeypatch.setattr(audit, '_FAILURE_COUNT', SlowCounter([audit.MAX_FAILURE_DIAGNOSTICS - 1]))
    monkeypatch.setattr(audit, '_SUPPRESSED_COUNT', [0])
    barrier = threading.Barrier(16)

    def burst():
        barrier.wait()
        for _ in range(20):
            audit._audit_failed('durable_store', error=OSError('x'), snapshot_id='s')
    threads = [threading.Thread(target=burst) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(_failures(warnings_)) == 1  # one slot left: exactly one diagnostic
    assert len([w for w in warnings_ if w.get('event') == 'publication_refusal_audit_failed_suppressed']) == 1
    assert audit.suppressed_failure_count() == 16 * 20 - 1


def test_real_handler_write_failure_is_detected_and_reported_out_of_band(tmp_path, monkeypatch, *, production_console):
    import io
    import logging

    class BrokenStream(io.StringIO):
        def write(self, text):
            raise OSError('sink full')
    fallback = io.StringIO()
    monkeypatch.setattr(audit, '_FALLBACK_STREAM', fallback, raising=False)
    monkeypatch.setattr(logging, 'raiseExceptions', False)
    handler = logging.StreamHandler(BrokenStream())
    saved = (list(_LOGGER.handlers), _LOGGER.level, _LOGGER.propagate)
    _LOGGER.handlers, _LOGGER.propagate = [handler], False
    _LOGGER.setLevel(logging.INFO)  # as installed by request_diagnostics_v1
    try:
        console, sid, actor = _blocked_base(tmp_path, production_console=production_console)
        assert console.publish(actor_id=actor, snapshot_id=sid)['status'] == 'BLOCKED'
    finally:
        _LOGGER.handlers, _LOGGER.propagate = saved[0], saved[2]
        _LOGGER.setLevel(saved[1])
    rows = [json.loads(line) for line in fallback.getvalue().splitlines() if line.strip()]
    assert any(r.get('event') == 'publication_refusal_audit_failed' and r.get('stage') == 'log'
               and r.get('outcome') == 'handler_write_failed' for r in rows), rows


@pytest.fixture(params=[_blocked_base, _durable_blocked], ids=['partial-formation', 'ready-durable'])
def build(request, production_console):
    return lambda root: request.param(root, production_console=production_console)


def _file_blocked_base(tmp_path):
    from src.review_closure_v1 import ReviewClosureConsole
    console, sid, actor, reviewer, *_ = system(tmp_path,
        make_console=lambda: ReviewClosureConsole(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime'),
        production_console=None)  # partial formation: gate MOET refuse
    return console, sid, reviewer
