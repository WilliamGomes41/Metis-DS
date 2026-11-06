"""Compact human answers share the captured proposal and existing atomic audit.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.operations_console_v1 import ConsoleError
from src.review.review_assessment_v1 import (
    ReviewAssessment, compact_approval_arguments, displayed_review_descriptor,
)
from src.review.review_interaction_v1 import build_review_interaction_evidence, new_review_interaction_id
from tests.test_ko_receipt_ui import prepared
from tests.test_review_command_bounded_http_v1 import physical_state
from tests.production_support import restart_production


def command(console, sid, reviewer, obj, data, assessment, *, compact=True):
    interaction = new_review_interaction_id()
    console.review_object(actor_id=reviewer, snapshot_id=sid, object_id=obj['object_id'],
        decision='approve', eindoordeel='goedkeuren', suitability='ja',
        expected_revision=data['snapshot_revision'], _compact_result=compact,
        _interaction_id=interaction, _review_assessment=assessment,
        confirmed_object_type='definition', recommendation_direction='for')
    return interaction


@pytest.mark.parametrize('compact', [True, False])
def test_three_answers_confirm_the_captured_proposal_and_survive_restart(
    tmp_path, production_console, monkeypatch, compact,
):
    console, sid, reviewer, obj, client, page, data = prepared(tmp_path, production_console, monkeypatch)
    answers = ReviewAssessment('yes', 'yes', 'yes')
    interaction = command(console, sid, reviewer, obj, data, answers, compact=compact)
    current = next(row for row in console.snapshot_objects(sid) if row['object_id'] == obj['object_id'])
    assert current['confirmed_object_type'] == 'recommendation'
    assert current['confirmed_recommendation_semantics']['direction'] == 'against'
    assert current['confirmed_recommendation_semantics']['strength_status'] == 'not_stated'
    events = console.workflow_review_store.read_review_command_events(
        sid, [], interaction_id=interaction, include_pending=False)
    decision = next(row for row in events if row['event_type'].endswith('_review_approve'))
    assert decision['details']['review_interaction']['assessment'] == answers.as_evidence()
    restarted = restart_production(console)
    assert restarted.workflow_review_store.read_review_command_events(
        sid, [], interaction_id=interaction, include_pending=False) == events


@pytest.mark.parametrize('answers', [ReviewAssessment(None, None, None),
    ReviewAssessment('yes', 'adjust', 'yes')])
def test_incomplete_or_adjusted_answers_never_write_an_approval(
    tmp_path, production_console, monkeypatch, answers,
):
    console, sid, reviewer, obj, client, page, data = prepared(tmp_path, production_console, monkeypatch)
    before = physical_state(console, sid)
    with pytest.raises(ConsoleError, match='review_assessment_approval_requires_yes'):
        command(console, sid, reviewer, obj, data, answers)
    assert physical_state(console, sid) == before


def test_descriptor_does_not_guess_unknown_semantics_or_accept_hidden_missing_target():
    from tests.test_recommendation_context_v3 import prepare
    _, rows, focal, fragments = prepare()
    descriptor = displayed_review_descriptor(focal, rows, 'richtlijn')
    assert descriptor.direction == 'against' and descriptor.strength_choice == 'not_stated'
    uncertain = deepcopy(focal)
    uncertain.pop('proposed_recommendation_semantics', None)
    unknown = displayed_review_descriptor(uncertain, [uncertain], 'richtlijn')
    assert not unknown.can_confirm
    with pytest.raises(ConsoleError):
        compact_approval_arguments(ReviewAssessment('yes', 'yes', 'yes'), unknown)
    from src.knowledge_relations_v1 import build_knowledge_relation
    missing = deepcopy(focal)
    missing['proposed_knowledge_relations'] = [build_knowledge_relation(
        source_object_id=missing['object_id'], source_object_version=missing['object_version'],
        relation_type='applies_if', target_object_id='not-loaded', target_object_version='1.0')]
    unresolved = displayed_review_descriptor(missing, [missing], 'richtlijn')
    assert unresolved.relations[0]['resolution'] == 'missing'
    assert not unresolved.can_confirm


def test_event_builder_keeps_legacy_evidence_unknown_and_records_explicit_answers():
    from tests.test_recommendation_context_v3 import prepare
    _, rows, focal, _ = prepare()
    args = dict(interaction_id=new_review_interaction_id(), interaction_kind='contextual',
        reviewer_account_id='reviewer', snapshot_id='snapshot', review_stage='first_review',
        focal=focal, objects=rows, review_path='richtlijn')
    legacy = build_review_interaction_evidence(**args)
    assert 'assessment' not in legacy
    assert ReviewAssessment.from_evidence(legacy.get('assessment')) is None
    answers = ReviewAssessment.from_values('yes', 'adjust', '')
    stored = build_review_interaction_evidence(**args, assessment=answers)
    assert stored['assessment']['placed_correctly'] is None
    assert ReviewAssessment.from_evidence(stored['assessment']) == answers
    assert stored['context_manifest_hash'] == legacy['context_manifest_hash']
    assert not answers.all_yes
    assert ReviewAssessment.from_evidence({'version': 'review-assessment-v1'}) is None
