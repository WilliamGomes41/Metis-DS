"""C3 (Sherlock 02:55 on #639): admission switch and read-only rollback pre-check.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag retry interrupt concurrent recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs

Rules (B18):
- METIS_PROCESSING_ADMISSION=closed MOET every new reservation in processing_retry_v1.reserve()
  refuse with processing_admission_closed; no attempt MAG NIET be added.
- The ingest reservation MOET be refused with the same code; no envelope and no attempt MAG NIET be stored.
- A value other than unset, empty or 'open' MOET count as closed (fail-closed).
- A repeated command_id MOET return its existing attempt (no new work).
- scripts/processing_rollback_precheck.py is read-only and MOET exit non-zero while any attempt is
  'running' or 'incomplete_budget'; it exits 0 only when there are none.
"""
import json

import pytest

from src.operations_console_v1 import ConsoleError, PRE_REVIEW_BLOCKED
from src.processing_retry_v1 import now, reserve
from tests.test_resv1_reservation_configuration import _console
from tests.test_attempt_diagnostics_postgres import bound, ingest
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401

ENV = 'METIS_PROCESSING_ADMISSION'


def _envelope():
    return {'sha256': 'a' * 64, 'version': '1.0', 'publication_eligibility': PRE_REVIEW_BLOCKED}


@pytest.mark.parametrize('value', ['closed', 'CLOSED', 'gesloten', 'x'])
def test_reserve_refused_when_admission_closed(monkeypatch, value):
    monkeypatch.setenv(ENV, value)
    envelope = _envelope()
    with pytest.raises(ConsoleError, match='^processing_admission_closed$'):
        reserve(envelope, command_id='c', actor_id='a', revision='r', clock=now())
    assert envelope.get('processing_attempts', []) == []


@pytest.mark.parametrize('value', [None, '', 'open', 'OPEN'])
def test_reserve_allowed_when_admission_open(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(ENV, raising=False)
    else:
        monkeypatch.setenv(ENV, value)
    attempt, fresh = reserve(_envelope(), command_id='c', actor_id='a', revision='r', clock=now())
    assert fresh and attempt['state'] == 'running'


def test_repeated_command_returns_existing_attempt_when_closed(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    envelope = _envelope()
    first, _ = reserve(envelope, command_id='c', actor_id='a', revision='r', clock=now())
    monkeypatch.setenv(ENV, 'closed')
    again, fresh = reserve(envelope, command_id='c', actor_id='a', revision='r', clock=now())
    assert (again['attempt_id'], fresh) == (first['attempt_id'], False)
    assert len(envelope['processing_attempts']) == 1


def test_ingest_reservation_refused_when_admission_closed(tmp_path, monkeypatch):
    console = _console(tmp_path)
    bound(console, reject=False)
    monkeypatch.setenv(ENV, 'closed')
    with pytest.raises(ConsoleError, match='^processing_admission_closed$'):
        ingest(console)
    restarted = _console(tmp_path)
    assert restarted._envelopes == {} and console._envelopes == {}


# --- read-only pre-check script ---

def _store(tmp_path, envelopes):
    path = tmp_path / 'envelopes.json'
    path.write_text(json.dumps(envelopes), encoding='utf-8')
    return path


def _with_states(*states):
    return {f's{n}': {'processing_attempts': [{'attempt_id': f'pa_{n}', 'state': state}]}
            for n, state in enumerate(states)}


@pytest.mark.parametrize('states,code', [
    ((), 0),
    (('succeeded', 'failed', 'interrupted'), 0),
    (('succeeded', 'running'), 2),
    (('incomplete_budget',), 2),
    (('running', 'incomplete_budget'), 2),
])
def test_precheck_exit_code(tmp_path, capsys, states, code):
    from scripts.processing_rollback_precheck import main
    path = _store(tmp_path, _with_states(*states))
    before = path.read_bytes()
    assert main(['--envelopes-file', str(path)]) == code
    report = json.loads(capsys.readouterr().out)
    assert report['counts'] == {'running': states.count('running'),
                                'incomplete_budget': states.count('incomplete_budget')}
    assert path.read_bytes() == before, 'the pre-check MAG NIET write'


def test_precheck_unreadable_store_exits_non_zero(tmp_path):
    from scripts.processing_rollback_precheck import main
    path = tmp_path / 'envelopes.json'
    path.write_text('{not json', encoding='utf-8')
    assert main(['--envelopes-file', str(path)]) != 0


def test_precheck_postgres_uses_read_only_transaction():
    from scripts.processing_rollback_precheck import scan_postgres
    executed = []

    class Rows:
        def fetchall(self):
            return [{'snapshot_id': 's0', 'envelope_payload': {'processing_attempts': [{'attempt_id': 'pa', 'state': 'running'}]}}]

    class Connection:
        def execute(self, sql, *_):
            executed.append(' '.join(sql.split()))
            return Rows()

        def rollback(self):
            executed.append('ROLLBACK')
    report = scan_postgres(Connection())
    assert executed[0] == 'BEGIN READ ONLY' and executed[-1] == 'ROLLBACK'
    assert not any(word in sql.upper() for sql in executed for word in ('INSERT', 'UPDATE', 'DELETE'))
    assert report['counts'] == {'running': 1, 'incomplete_budget': 0}


# --- Sherlock FAIL on 91c16c3, point 1: the pre-check connection MOET be read-only (connection.read_only=True) ---

def test_precheck_sets_connection_read_only_before_any_statement():
    from scripts.processing_rollback_precheck import scan_postgres
    seen = []

    class Rows:
        def fetchall(self):
            return []

    class Connection:
        read_only = False

        def execute(self, sql, *_):
            seen.append((self.read_only, ' '.join(sql.split())))
            return Rows()

        def rollback(self):
            seen.append((self.read_only, 'ROLLBACK'))
    connection = Connection()
    scan_postgres(connection)
    assert connection.read_only is True
    assert seen and all(flag is True for flag, _ in seen), seen


def test_precheck_postgres_connection_refuses_insert(workflow_postgres):
    import psycopg
    from scripts.processing_rollback_precheck import scan_postgres
    with psycopg.connect(workflow_postgres.dsn, row_factory=psycopg.rows.dict_row) as connection:
        report = scan_postgres(connection)
        assert report['status'] == 'clean'
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            connection.execute("INSERT INTO workflow.documents (snapshot_id) VALUES ('precheck-write-probe')")
        connection.rollback()
    with psycopg.connect(workflow_postgres.dsn) as check:
        assert check.execute("SELECT count(*) FROM workflow.documents WHERE snapshot_id='precheck-write-probe'").fetchone()[0] == 0
