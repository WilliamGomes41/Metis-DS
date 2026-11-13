"""Independent KO4 state/event/post-state oracle at the pure policy boundary.

# release-control-evidence: scope/belofte slop releasebewijs
"""
import pytest

from src.operations_console_v1 import ConsoleError
from src.review import ko_transitions_v1 as policy


STATES = ('Kandidaat', 'Context open', 'Bewijs open', 'Samengesteld', 'In review',
          'Tweede review', 'Goedgekeurd', 'Gepubliceerd', 'Vervangen', 'Ingetrokken', 'Afgewezen')
EVENTS = ('approve', 'approve_second', 'reject', 'later', 'confirm_type', 'correct',
          'link_support', 'confirm_relations', 'supersede_merge')
OPEN = {'Kandidaat', 'Context open', 'Bewijs open', 'Samengesteld', 'In review'}
YES = {'version': 'review-assessment-v1', 'applicable': 'yes', 'complete': 'yes',
       'placed_correctly': 'yes'}


def expected_targets(state, event):
    if state in {'Gepubliceerd', 'Vervangen', 'Ingetrokken'}:
        return set()
    if event == 'approve':
        return {'Goedgekeurd', 'Tweede review'} if state in {'Bewijs open', 'Samengesteld', 'In review'} else set()
    if event == 'approve_second':
        return {'Goedgekeurd', 'Tweede review'} if state == 'Tweede review' else set()
    if event == 'reject':
        # #1064 (William, 13 november 2026): the independent second reviewer may reject too.
        return set() if state in {'Goedgekeurd', 'Afgewezen'} else {'Afgewezen'}
    if event == 'later':
        if state in {'Goedgekeurd', 'Tweede review', 'Afgewezen'}:
            return set()
        return OPEN
    if event == 'supersede_merge':
        return {'Vervangen'}
    return OPEN


@pytest.mark.parametrize('state', STATES)
@pytest.mark.parametrize('event', EVENTS)
@pytest.mark.parametrize('after', STATES)
def test_every_state_event_and_prepared_result_against_independent_oracle(monkeypatch, state, event, after):
    current = {'object_id': 'claim', 'object_version': '1', 'object_type': 'recommendation', 'phase': 'before'}
    prepared = {**current, 'object_version': '2', 'phase': 'after'}
    monkeypatch.setattr(policy, 'derive_ko_state',
        lambda obj, **kwargs: {'state': state if obj['phase'] == 'before' else after})
    allowed = expected_targets(state, event)
    call = lambda: policy.apply_ko_event(current=current, prepared=prepared, event=event,
        review_path='richtlijn', assessment=YES, evidence_not_applicable=True)
    if after in allowed:
        call()
    else:
        with pytest.raises(ConsoleError) as refused:
            call()
        assert refused.value.code == ('ko_transition_refused' if not allowed else 'ko_transition_result_invalid')


def test_matrix_covers_the_public_state_and_event_alphabets():
    assert set(STATES) == set(policy.KO_STATES)
    assert set(EVENTS) == set(policy.EVENTS)


@pytest.mark.parametrize('before_type,after_type', [('path', 'path'), ('path', 'node'),
                                                  ('node', 'node'), ('node', 'path')])
def test_current_and_prepared_classification_share_one_central_rule(monkeypatch, before_type, after_type):
    current = {'object_id': 'claim', 'object_type': before_type, 'phase': 'before'}
    prepared = {'object_id': 'claim', 'object_type': after_type, 'phase': 'after'}
    monkeypatch.setattr(policy, 'derive_ko_state',
        lambda obj, **kwargs: {'state': 'Bewijs open' if obj['phase'] == 'before' else 'Goedgekeurd'})
    facts = {'assessment': YES, 'evidence_not_applicable': True} if after_type == 'node' else {}
    result = policy.apply_ko_event(current=current, prepared=prepared, event='approve', review_path='boom', **facts)
    assert bool(result) is (after_type == 'node')
    if after_type == 'node':
        assert result['assessment'] == YES
        assert result['supporting_evidence']['applicability'] == 'not_applicable'


@pytest.mark.parametrize('state', ['Kandidaat', 'Gepubliceerd', 'Vervangen', 'Ingetrokken'])
def test_leaving_ko_for_structure_retains_the_current_state_guard(monkeypatch, state):
    current = {'object_id': 'claim', 'object_type': 'node'}
    prepared = {'object_id': 'claim', 'object_type': 'path'}
    monkeypatch.setattr(policy, 'derive_ko_state', lambda *args, **kwargs: {'state': state})
    if state == 'Kandidaat':
        assert policy.apply_ko_event(current=current, prepared=prepared, event='approve', review_path='boom') == {}
    else:
        with pytest.raises(ConsoleError) as refused:
            policy.apply_ko_event(current=current, prepared=prepared, event='approve', review_path='boom')
        assert refused.value.code == 'ko_transition_refused'
