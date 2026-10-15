"""Semantic contract version recorded at reservation for every attempt.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag version-compat retry interrupt
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


def test_resume_reservation_equals_contract_of_the_stored_replay(tmp_path):
    from tests.test_recoverable_formation_v1 import system
    state, sid, actor, *_ = system(tmp_path)
    produced = state._envelope(sid)['semantic_replay']['identity']['components']['semantic_contract_version']
    assert produced == _expected(v3=True)  # helper output identical to pre_review_semantic_v1:585
    try:
        state.resume_formation(actor_id=actor, snapshot_id=sid, command_id='resume-1',
                               expected_revision=state.objects_revision(sid))
    except ConsoleError:
        pass  # outcome irrelevant: the reservation is durable either way
    resume = next(a for a in state._envelope(sid)['processing_attempts'] if a['kind'] == 'resume')
    assert resume['reserved_semantic_contract_version'] == produced
