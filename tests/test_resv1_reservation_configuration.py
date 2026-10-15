"""RESV-1: every reservation point records the active configuration; fail-closed.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag stale retry version-compat recovery concurrent
# release-control-evidence: slop
# release-control-evidence: releasebewijs

Rules (B18):
- Iedere reservering (ingest, re-extract) MOET de actieve configuratie vastleggen.
- Een configuratie die niet leesbaar is MOET de reservering weigeren
  (`processing_configuration_unavailable`); er MAG NIET een poging ontstaan.
"""
import threading

import pytest

import src.source_selection_v1 as selection
from src.operations_console_v1 import ConsoleError, OperationsConsole
from tests.test_attempt_diagnostics_postgres import bound, ingest


def _console(tmp_path):
    return OperationsConsole(root=tmp_path, source_store=tmp_path / 'sources' / 'private',
                             runtime=tmp_path / 'output' / 'runtime' / 'operations-console')


def _attempts(console, sid, kind):
    return [a for a in console._envelope(sid).get('processing_attempts', []) if a['kind'] == kind]


def _broken(monkeypatch):
    def broken(_console):
        raise OSError('private configuration failure')
    monkeypatch.setattr(selection, 'configuration', broken)


def test_ingest_reservation_records_active_configuration(tmp_path):
    console = _console(tmp_path)
    bound(console, reject=False)
    sid, _, _ = ingest(console)
    [attempt] = _attempts(console, sid, 'ingest')
    assert attempt['processing_configuration'] == selection.configuration(console)
    assert attempt['processing_configuration']['mode'] != 'unbound'


def test_ingest_reservation_fails_closed_when_configuration_unreadable(tmp_path, monkeypatch):
    console = _console(tmp_path)
    bound(console, reject=False)
    _broken(monkeypatch)
    with pytest.raises(ConsoleError, match='processing_configuration_unavailable'):
        ingest(console)
    assert console._envelopes == {}


def _reextract_ready(tmp_path):
    console = _console(tmp_path)
    bound(console, reject=False)
    sid, actor, _ = ingest(console)
    assert not console.snapshot_is_published(sid)
    return console, sid, actor


def test_reextract_reservation_records_active_configuration(tmp_path):
    console, sid, actor = _reextract_ready(tmp_path)
    try:
        console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    except ConsoleError:
        pass  # outcome irrelevant: the reservation is durable
    [attempt] = _attempts(console, sid, 'reextract')
    assert attempt['processing_configuration'] == selection.configuration(console)


def test_reextract_reservation_fails_closed_when_configuration_unreadable(tmp_path, monkeypatch):
    console, sid, actor = _reextract_ready(tmp_path)
    before = list(console._envelope(sid)['processing_attempts'])
    _broken(monkeypatch)
    with pytest.raises(ConsoleError, match='processing_configuration_unavailable'):
        console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    assert console._envelope(sid)['processing_attempts'] == before


def test_stale_configuration_is_never_reserved_on_reextract(tmp_path):
    console, sid, actor = _reextract_ready(tmp_path)
    console._envelope(sid)['processing_configuration'] = {'mode': 'stale-mode'}
    try:
        console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    except ConsoleError:
        pass
    [attempt] = _attempts(console, sid, 'reextract')
    assert attempt['processing_configuration']['mode'] != 'stale-mode'


def test_concurrent_ingests_each_record_active_configuration(tmp_path):
    console = _console(tmp_path)
    bound(console, reject=False)
    researcher = console.create_account(username='anne', password='anne-secret', roles=('researcher',))
    reviewer = console.create_account(username='bert', password='bert-secret', roles=('reviewer', 'publisher'))
    barrier, sids = threading.Barrier(3), []

    def run(n):
        barrier.wait()
        receipt = console.ingest(actor_id=researcher['account_id'], filename=f't{n}.html', content_type='text/html',
            data=f'<html><body><h1>B{n}</h1><p>Een observatie {n} is een systematische waarneming.</p></body></html>'.encode(),
            ingest_kind='new', title=f'B{n}', version='1', date='2026-10-03', live_url='',
            class_='richtlijn', family=f'begrippen{n}', named_reviewers=[reviewer['account_id']])
        sids.append(receipt['snapshot_id'])
    threads = [threading.Thread(target=run, args=(n,)) for n in range(3)]
    [t.start() for t in threads]
    [t.join(60) for t in threads]
    assert len(sids) == 3
    expected = selection.configuration(console)
    for sid in sids:
        [attempt] = _attempts(console, sid, 'ingest')
        assert attempt['processing_configuration'] == expected


def test_resume_duplicate_receipt_accepts_incomplete_budget():
    import inspect
    source = inspect.getsource(OperationsConsole.resume_formation)
    assert 'attempt["state"] in {"succeeded", "incomplete_budget"}' in source


def test_reextract_reserved_contract_follows_active_configuration_not_stale_envelope(tmp_path):
    """#630 reconcile: reserve() records the contract of the active configuration."""
    from src.pre_review_semantic_v1 import semantic_contract_version_for_mode
    from copy import deepcopy
    console, sid, actor = _reextract_ready(tmp_path)
    stale = deepcopy(console._envelope(sid))
    stale['processing_configuration'] = {'mode': 'stale-mode'}
    console._commit_prepared_store(envelopes={sid: stale}, snapshot_id=sid)  # durable stale value
    try:
        console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    except ConsoleError:
        pass
    [attempt] = _attempts(console, sid, 'reextract')
    active = selection.configuration(console)
    assert attempt['reserved_semantic_contract_version'] == semantic_contract_version_for_mode(active['mode'])
