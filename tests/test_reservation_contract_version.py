"""Semantic contract version recorded at reservation for every attempt.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag version-compat retry interrupt stale concurrent
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from datetime import timedelta

import pytest

from src.operations_console_v1 import ConsoleError, PRE_REVIEW_BLOCKED
from src.processing_retry_v1 import expire_running, finish, now, reserve


def _envelope(mode):
    envelope = {'sha256': 'a' * 64, 'version': '1.0', 'publication_eligibility': PRE_REVIEW_BLOCKED}
    if mode is not None:
        envelope['processing_configuration'] = {'mode': mode, 'model': 'fixture', 'docling': False}
    return envelope


def _expected(v2=False, v3=False):
    from src.pre_review_semantic_v1 import semantic_contract_version
    return semantic_contract_version(field_contract_v2=v2, field_contract_v3=v3)


@pytest.mark.parametrize('mode,flags', [
    ('semantic-source-bound-v3', dict(v3=True)),
    ('semantic-source-bound-v2', dict(v2=True)),
    ('semantic-source-bound-v1', dict()),
])
def test_semantic_modes_record_contract_at_reservation(mode, flags):
    envelope = _envelope(mode)
    attempt, _ = reserve(envelope, command_id='c', actor_id='a', revision='r', clock=now())
    assert attempt['reserved_semantic_contract_version'] == _expected(**flags)


@pytest.mark.parametrize('mode', ['deterministic-v1', 'unbound', None])
def test_non_semantic_or_missing_configuration_records_none(mode):
    attempt, _ = reserve(_envelope(mode), command_id='c', actor_id='a', revision='r', clock=now())
    assert attempt['reserved_semantic_contract_version'] is None


def test_failed_and_interrupted_attempts_keep_reserved_contract():
    envelope = _envelope('semantic-source-bound-v3')
    first, _ = reserve(envelope, command_id='c1', actor_id='a', revision='r', clock=now())
    finish(envelope, first['attempt_id'], state='failed', error=ConsoleError('pre_review_llm_connection_failed'))
    second, _ = reserve(envelope, command_id='c2', actor_id='a', revision='r', clock=now())
    expire_running(envelope, now() + timedelta(days=1))
    states = [(a['state'], a['reserved_semantic_contract_version']) for a in envelope['processing_attempts']]
    assert states == [('failed', _expected(v3=True)), ('interrupted', _expected(v3=True))]


def test_reservation_only_reads_configuration():
    envelope = _envelope('semantic-source-bound-v3')
    before = dict(envelope['processing_configuration'])
    reserve(envelope, command_id='c', actor_id='a', revision='r', clock=now())
    assert envelope['processing_configuration'] == before


def test_resume_reservation_equals_contract_of_the_stored_replay(tmp_path, *, production_console):
    from tests.test_recoverable_formation_v1 import system
    state, sid, actor, *_ = system(tmp_path, production_console=production_console)
    produced = state._envelope(sid)['semantic_replay']['identity']['components']['semantic_contract_version']
    assert produced == _expected(v3=True)  # helper output identical to pre_review_semantic_v1:585
    try:
        state.resume_formation(actor_id=actor, snapshot_id=sid, command_id='resume-1',
                               expected_revision=state.objects_revision(sid))
    except ConsoleError:
        pass  # outcome irrelevant: the reservation is durable either way
    resume = next(a for a in state._envelope(sid)['processing_attempts'] if a['kind'] == 'resume')
    assert resume['reserved_semantic_contract_version'] == produced


# --- RESV-2: legacy retry path refreshes configuration before reserving -----

@pytest.fixture
def blocked(tmp_path, *, production_console):
    from tests.test_attempt_diagnostics_postgres import bound, ingest
    console = production_console(processing_binder=lambda console: None, root=tmp_path, source_store=tmp_path / 'sources' / 'private',
                                runtime=tmp_path / 'output' / 'runtime' / 'operations-console')
    bound(console)  # provider rejects: ingest leaves an empty, blocked document
    sid, actor, _ = ingest(console)
    assert console.snapshot_objects(sid) == []
    return console, sid, actor


def test_retry_refreshes_configuration_before_reserving(blocked, monkeypatch):
    from src.pre_review_semantic_v1 import semantic_contract_version_for_mode, SEMANTIC_MODE
    console, sid, actor = blocked
    try:
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id='retry-1')
    except ConsoleError:
        pass  # outcome irrelevant: the reservation is durable
    envelope = console._envelope(sid)
    attempt = next(a for a in envelope['processing_attempts'] if a['command_id'] == 'retry-1')
    assert envelope['processing_configuration']['mode'] == SEMANTIC_MODE
    assert attempt['reserved_semantic_contract_version'] == semantic_contract_version_for_mode(SEMANTIC_MODE)


def test_retry_fails_closed_when_configuration_refresh_fails(blocked, monkeypatch):
    import src.source_selection_v1 as selection
    console, sid, actor = blocked
    before = list(console._envelope(sid)['processing_attempts'])

    def broken(_console):
        raise OSError('private configuration failure')
    monkeypatch.setattr(selection, 'configuration', broken)
    with pytest.raises(ConsoleError, match='processing_configuration_unavailable'):
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id='retry-2')
    assert console._envelope(sid)['processing_attempts'] == before


def test_retry_replaces_stale_stored_configuration(blocked):
    from src.pre_review_semantic_v1 import semantic_contract_version_for_mode, SEMANTIC_MODE
    console, sid, actor = blocked
    envelope = console._envelope(sid)
    envelope['processing_configuration'] = {'mode': 'stale-mode'}
    console.workflow_document_store.write_bundle(envelope=envelope, objects=None)
    assert console._envelope(sid)['processing_configuration'] == {'mode': 'stale-mode'}  # live state
    try:
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id='retry-stale')
    except ConsoleError:
        pass
    after = console._envelope(sid)
    attempt = next(a for a in after['processing_attempts'] if a['command_id'] == 'retry-stale')
    assert after['processing_configuration']['mode'] == SEMANTIC_MODE
    assert attempt['reserved_semantic_contract_version'] == semantic_contract_version_for_mode(SEMANTIC_MODE)


def test_concurrent_retries_all_reserve_the_refreshed_contract(blocked):
    import threading
    from src.pre_review_semantic_v1 import semantic_contract_version_for_mode, SEMANTIC_MODE
    console, sid, actor = blocked
    barrier = threading.Barrier(4)

    def run(n):
        barrier.wait()
        try:
            console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id=f'retry-c{n}')
        except ConsoleError:
            pass
    threads = [threading.Thread(target=run, args=(n,)) for n in range(4)]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    attempts = [a for a in console._envelope(sid)['processing_attempts'] if a['command_id'].startswith('retry-c')]
    assert attempts
    assert {a['reserved_semantic_contract_version'] for a in attempts} == {semantic_contract_version_for_mode(SEMANTIC_MODE)}
    assert sum(a['state'] == 'running' for a in attempts) == 0


# --- RESV-1 F3: mid-flight deploy changes the configuration after reservation ---

def test_retry_fails_with_configuration_changed_after_mid_flight_deploy(blocked, monkeypatch):
    # Reservation reads configuration A; a deploy switches to B before execution.
    # The retry attempt MOET pin A and MOET stop with processing_configuration_changed;
    # work under B MAG NIET start.
    import src.source_selection_v1 as selection
    console, sid, actor = blocked
    real = selection.configuration
    calls = {'n': 0}

    def deploy_after_reservation(target):
        calls['n'] += 1
        current = real(target)
        return current if calls['n'] == 1 else {**current, 'mode': 'deployed-mid-flight'}
    monkeypatch.setattr(selection, 'configuration', deploy_after_reservation)
    # Codex P2 / C6 (#639): exact counters per stage; none MAG NIET run before the fence refuses.
    from tests.test_resv1_reservation_configuration import exact_counters
    counts = exact_counters(console)
    with pytest.raises(ConsoleError, match='processing_configuration_changed'):
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id='retry-deploy')
    assert counts() == {'extract': 0, 'prepare': 0, 'provider': 0}, 'PROVIDER_WORK_STARTED_BEFORE_FENCE'
    attempt = next(a for a in console._envelope(sid)['processing_attempts'] if a['command_id'] == 'retry-deploy')
    assert attempt['processing_configuration']['mode'] != 'deployed-mid-flight', 'RETRY_ATTEMPT_NOT_PINNED'
    assert attempt['state'] == 'failed' and attempt['error_code'] == 'processing_configuration_changed'


def test_duplicate_retry_command_keeps_its_pinned_configuration(blocked, monkeypatch):
    # A repeated command returns the existing attempt; its configuration MAG NIET be overwritten.
    import src.source_selection_v1 as selection
    console, sid, actor = blocked
    try:
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id='retry-dup')
    except ConsoleError:
        pass
    pinned = deepcopy_attempt(console, sid, 'retry-dup')['processing_configuration']
    assert pinned and pinned == selection.configuration(console), 'RETRY_ATTEMPT_NOT_PINNED'
    real = selection.configuration
    monkeypatch.setattr(selection, 'configuration', lambda c: {**real(c), 'mode': 'later-deploy'})
    try:
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id='retry-dup')
    except ConsoleError:
        pass
    assert deepcopy_attempt(console, sid, 'retry-dup')['processing_configuration'] == pinned


def test_retry_pin_is_a_copy_not_a_shared_reference(blocked):
    console, sid, actor = blocked
    try:
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id='retry-copy')
    except ConsoleError:
        pass
    envelope = console._envelope(sid)
    attempt = next(a for a in envelope['processing_attempts'] if a['command_id'] == 'retry-copy')
    assert attempt['processing_configuration'] == envelope['processing_configuration']
    assert attempt['processing_configuration'] is not envelope['processing_configuration']


def test_retry_without_configuration_fails_closed_without_attempt(blocked, monkeypatch):
    # Legacy/empty configuration: MOET fail closed (processing_configuration_unavailable), NOOIT KeyError.
    import src.source_selection_v1 as selection
    console, sid, actor = blocked
    before = list(console._envelope(sid)['processing_attempts'])
    monkeypatch.setattr(selection, 'configuration', lambda c: None)
    with pytest.raises(ConsoleError, match='processing_configuration_unavailable'):
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id='retry-legacy')
    assert console._envelope(sid)['processing_attempts'] == before


def deepcopy_attempt(console, sid, command_id):
    from copy import deepcopy
    return deepcopy(next(a for a in console._envelope(sid)['processing_attempts'] if a['command_id'] == command_id))
