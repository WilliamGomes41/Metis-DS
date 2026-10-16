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
    assert [e for e in read_events(console._ledger_path) if e['event_type'] == 'publication_refused'] == []
    [durable] = store.read_records(store.store_path(console))
    assert durable['actor'] == actor and durable['snapshot_id'] == sid
    assert durable['reason_codes'] == event['reason_codes']
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

    def failing_store(*args, **kwargs):
        raise OSError('private audit store failure')
    monkeypatch.setattr(ledger, 'append_event', failing)
    monkeypatch.setattr(store, 'append_refusal', failing_store)
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


# --- #629 F1: separate append-only store, outside the review ledger hash chain ---

@pytest.mark.parametrize('build', [_blocked_base, _durable_blocked], ids=['file', 'durable'])
def test_refusal_never_enters_the_review_ledger_hash_chain(tmp_path, events, build):
    from src.review_ledger import read_events, verify_ledger
    console, sid, actor = build(tmp_path)
    before = [(e['event_type'], e['event_hash'], e.get('previous_event_hash')) for e in read_events(console._ledger_path)]
    assert console.publish(actor_id=actor, snapshot_id=sid)['status'] == 'BLOCKED'
    after = [(e['event_type'], e['event_hash'], e.get('previous_event_hash')) for e in read_events(console._ledger_path)]
    assert after == before, 'REFUSAL_IN_LEDGER_CHAIN'
    assert verify_ledger(console._ledger_path) == []
    [record] = store.read_records(store.store_path(console))
    assert record['event_type'] == 'publication_refused' and record['actor'] == actor


def test_refusal_store_dedups_per_document_reason_actor_within_window(tmp_path, events):
    console, sid, actor = _blocked_base(tmp_path)
    for _ in range(3):
        assert console.publish(actor_id=actor, snapshot_id=sid)['status'] == 'BLOCKED'
    assert len(store.read_records(store.store_path(console))) == 1
    assert len(_refusals(events)) == 3  # logs are not deduplicated


def test_refusal_store_dedup_window_and_key(tmp_path):
    from datetime import datetime, timezone
    path = tmp_path / store.FILE_NAME
    t0 = datetime(2026, 10, 15, tzinfo=timezone.utc)
    args = dict(snapshot_id='s', object_version='1', reason_codes=['r'], revision='rev')
    assert store.append_refusal(path, actor='a', clock=t0, **args) == 'recorded'
    assert store.append_refusal(path, actor='a', clock=t0 + store.DEDUP_WINDOW / 2, **args) == 'deduplicated'
    assert store.append_refusal(path, actor='b', clock=t0, **args) == 'recorded'
    assert store.append_refusal(path, actor='a', clock=t0, **{**args, 'reason_codes': ['q']}) == 'recorded'
    assert store.append_refusal(path, actor='a', clock=t0 + store.DEDUP_WINDOW, **args) == 'recorded'
    rows = store.read_records(path)
    assert len(rows) == 4 and all(len(r['revision_sha256']) == 64 and 'rev' != r['revision_sha256'] for r in rows)


def test_refusal_store_rotates_instead_of_refusing_at_capacity(tmp_path, monkeypatch):
    # Metis: rotation/retention, NOOIT a permanent refusal at the cap.
    from datetime import datetime, timezone
    monkeypatch.setattr(store, 'MAX_FILE_BYTES', 600)
    path = tmp_path / store.FILE_NAME
    t0 = datetime(2026, 10, 15, tzinfo=timezone.utc)
    outcomes = [store.append_refusal(path, snapshot_id='s', object_version='1', actor=f'a{n}', reason_codes=['r'] * 500,
                                     revision=None, clock=t0) for n in range(6)]
    assert outcomes == ['recorded'] * 6
    assert store.rotated_path(path).exists()
    assert path.stat().st_size < 600 + 2000
    assert all(len(r['reason_codes']) == store.MAX_REASON_CODES for r in store.read_records(path))


def test_dedup_reads_only_the_tail_not_the_full_file(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    path = tmp_path / store.FILE_NAME
    t0 = datetime(2026, 10, 15, tzinfo=timezone.utc)
    path.write_text('{"padding":"' + 'x' * (store.TAIL_BYTES * 3) + '"}\n')
    reads = []
    real_open = type(path).open

    def spy(self, *a, **k):
        handle = real_open(self, *a, **k)
        real_read = handle.read
        handle.read = lambda n=-1: (reads.append(n), real_read(n))[1]
        return handle
    monkeypatch.setattr(type(path), 'open', spy)
    assert store.append_refusal(path, snapshot_id='s', object_version='1', actor='a', reason_codes=['r'], revision=None, clock=t0) == 'recorded'
    assert reads and all(0 <= n <= store.TAIL_BYTES for n in reads), reads


def test_corrupt_record_is_skipped_reported_and_never_blocks_writes(tmp_path):
    from datetime import datetime, timezone
    path = tmp_path / store.FILE_NAME
    t0 = datetime(2026, 10, 15, tzinfo=timezone.utc)
    store.append_refusal(path, snapshot_id='s', object_version='1', actor='a', reason_codes=['r'], revision=None, clock=t0)
    with path.open('a') as handle:
        handle.write('{not json\n{"recorded_at":"garbage","snapshot_id":"s","reason_codes":["r"],"actor":"b"}\n')
    assert store.append_refusal(path, snapshot_id='s', object_version='1', actor='b', reason_codes=['r'], revision=None, clock=t0) == 'recorded'
    corrupt = []
    rows = store.read_records(path, on_corrupt=corrupt.append)
    assert [r['actor'] for r in rows] == ['a', 'b'] and len(corrupt) == 2


def test_file_store_never_goes_live(tmp_path, monkeypatch):
    # Live topology (postgres mode) without a PostgreSQL refusal store: the file store MAG NIET be used.
    monkeypatch.setenv('WEBSITE_SITE_NAME', 'metis-prod')
    monkeypatch.setenv('METIS_WORKFLOW_DOCUMENT_STORE', 'postgres')
    console, sid, actor = _blocked_base(tmp_path)
    with pytest.raises(store.RefusalStoreUnavailable):
        store.append(console, snapshot_id=sid, object_version='1', actor=actor, reason_codes=['r'], revision=None)
    assert not store.store_path(console).exists()

def test_file_store_is_visibly_marked_temporary(tmp_path):
    # TIJDELIJK until William's GO on a PostgreSQL table: every record MOET carry the marker.
    path = tmp_path / store.FILE_NAME
    store.append_refusal(path, snapshot_id='s', object_version='1', actor='a', reason_codes=['r'], revision=None)
    [row] = store.read_records(path)
    assert store.STORE_STATUS == 'temporary_file_store_pending_postgres_table'
    assert row['store_status'] == store.STORE_STATUS
    assert 'TIJDELIJK' in store.__doc__


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
    console, sid, actor = _blocked_base(tmp_path)
    with pytest.raises(store.RefusalStoreUnavailable):
        store.append(console, snapshot_id=sid, object_version='1', actor=actor, reason_codes=['r'], revision=None)
    assert not store.store_path(console).exists()


def test_file_store_allowed_in_single_worker_file_topology(tmp_path, monkeypatch):
    for name in ('WEBSITE_SITE_NAME', 'METIS_WORKFLOW_DOCUMENT_STORE', 'METIS_WORKFLOW_STORE',
                 'CONSOLE_GUNICORN_WORKERS', 'WEB_CONCURRENCY', 'GUNICORN_WORKERS', 'CONSOLE_INSTANCE_COUNT'):
        monkeypatch.delenv(name, raising=False)
    console, sid, actor = _blocked_base(tmp_path)
    assert store.append(console, snapshot_id=sid, object_version='1', actor=actor, reason_codes=['r'], revision=None) == 'recorded'


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
