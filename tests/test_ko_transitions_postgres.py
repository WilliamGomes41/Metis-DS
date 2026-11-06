"""KO4 native transition rules at the existing durable review command.

# release-control-evidence: scope/belofte opslag toegang slop releasebewijs
"""
from copy import deepcopy

import pytest

from src.operations_console_v1 import ConsoleError
from src.review.knowledge_path_v1 import content_reviewable
from tests.test_t12_publication_readiness_authority import _console
from tests.test_review_command_bounded_http_v1 import physical_state


def test_native_approval_requires_explicit_answers_without_domain_writes(tmp_path, production_console):
    console, sid = _console(tmp_path, production_console=production_console)
    target = next(row for row in console.snapshot_objects(sid) if content_reviewable(row))
    before = deepcopy(physical_state(console, sid))
    events = console.workflow_review_store.read_events_for_snapshots([sid])
    with pytest.raises(ConsoleError) as refused:
        console.review_object(actor_id=console._envelope(sid)['named_reviewers'][0],
            snapshot_id=sid, object_id=target['object_id'], decision='approve',
            confirmed_object_type='definition', suitability='ja', eindoordeel='goedkeuren',
            type_action='dit_klopt', expected_revision=console.objects_revision(sid))
    assert refused.value.code == 'review_assessment_required'
    assert physical_state(console, sid) == before
    assert console.workflow_review_store.read_events_for_snapshots([sid]) == events


YES = {'version': 'review-assessment-v1', 'applicable': 'yes', 'complete': 'yes',
       'placed_correctly': 'yes'}


def _approval(console, sid, target, **values):
    return console.review_object(actor_id=console._envelope(sid)['named_reviewers'][0],
        snapshot_id=sid, object_id=target['object_id'], decision='approve',
        confirmed_object_type='definition', suitability='ja', eindoordeel='goedkeuren',
        type_action='dit_klopt', expected_revision=console.objects_revision(sid), **values)


@pytest.mark.parametrize('values,code', [
    ({'assessment': YES}, 'knowledge_evidence_required'),
    ({'assessment': {**YES, 'complete': 'adjust'}, 'evidence_not_applicable': True},
     'review_assessment_requires_three_yes'),
    ({'assessment': {**YES, 'applicable': 'adjust', 'complete': 'adjust', 'placed_correctly': 'adjust'},
      'evidence_not_applicable': True}, 'review_assessment_requires_three_yes'),
    ({'assessment': YES, 'evidence_not_applicable': 'false'}, 'supporting_evidence_choice_invalid'),
])
def test_approval_guards_refuse_before_any_object_binding_or_event_write(
        tmp_path, production_console, values, code):
    console, sid = _console(tmp_path, production_console=production_console)
    target = next(row for row in console.snapshot_objects(sid) if content_reviewable(row))
    before = deepcopy(physical_state(console, sid))
    events = console.workflow_review_store.read_events_for_snapshots([sid])
    with pytest.raises(ConsoleError) as refused:
        _approval(console, sid, target, **values)
    assert refused.value.code == code
    assert physical_state(console, sid) == before
    assert console.workflow_review_store.read_events_for_snapshots([sid]) == events


def test_explicit_not_applicable_is_bound_to_the_saved_tuple_and_recorded_in_audit(
        tmp_path, production_console):
    from src.publication.publish_authorization_v1 import still_matches
    from src.review.ko_transitions_v1 import recorded_not_applicable
    console, sid = _console(tmp_path, production_console=production_console)
    target = next(row for row in console.snapshot_objects(sid) if content_reviewable(row))
    _approval(console, sid, target, assessment=YES, evidence_not_applicable=True)
    saved = next(row for row in console.snapshot_objects(sid) if row['object_id'] == target['object_id'])
    bindings = console.object_review_bindings(sid)
    own = [row for row in bindings if row['object_id'] == target['object_id']]
    assert len(own) == 1 and still_matches(own[0], saved)
    assert own[0]['assessment'] == YES
    assert recorded_not_applicable(saved, own)
    changed = deepcopy(saved)
    changed['content']['clean_text'] += ' Veranderd.'
    assert not recorded_not_applicable(changed, own)
    events = console.workflow_review_store.read_events_for_snapshots([sid])
    event = next(row for row in events if row['event_type'].endswith('_review_approve'))
    assert event['details']['supporting_evidence'] == own[0]['supporting_evidence']
    before = deepcopy(physical_state(console, sid))
    _approval(console, sid, target, assessment=YES, evidence_not_applicable=True)
    assert physical_state(console, sid) == before
    assert console.workflow_review_store.read_events_for_snapshots([sid]) == events


@pytest.mark.parametrize('change_support', [False, True])
def test_real_support_repair_targets_final_versions_and_allows_approval_without_na(
        tmp_path, production_console, production_app, change_support):
    from tests.test_deterministic_review_repair_v1 import REPAIR_SUPPORT_RELATION
    from src.knowledge_relations_v1 import confirmed_knowledge_relations_of
    from src.review.knowledge_relation_review_v1 import relation_choice_value
    from tests.semantic_fixture_support import bind_fixture_selections
    console = production_console(root=tmp_path, source_store=tmp_path / 'sources',
        runtime=tmp_path / 'runtime', processing_binder=bind_fixture_selections)
    author = console.create_account(username='author', password='fixture-only', roles=('researcher',))
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
    texts = ['Oedeem is een ophoping van vocht.', 'Een observatie is een systematische waarneming.']
    bind_fixture_selections(console, [(text, 'definition') for text in texts])
    receipt = console.ingest(actor_id=author['account_id'], filename='definitions.html',
        data=('<h1>Begrippen</h1>' + ''.join('<p>' + text + '</p>' for text in texts)).encode(),
        content_type='text/html', ingest_kind='new', title='Begrippen', version='1.0',
        date='2026-11-06', live_url='', class_='richtlijn', family='test',
        named_reviewers=[reviewer['account_id']])
    sid = receipt['snapshot_id']
    objects = [row for row in console.snapshot_objects(sid) if content_reviewable(row)]
    support, claim = objects[:2]
    console.submit_review_resolution(actor_id=reviewer['account_id'], snapshot_id=sid,
        object_id=support['object_id'], expected_revision=console.objects_revision(sid),
        suitability='alleen_onderbouwing', comment='Deze passage onderbouwt deze claim.',
        repair_kind=REPAIR_SUPPORT_RELATION, claim_object_id=claim['object_id'])
    current = {row['object_id']: row for row in console.snapshot_objects(sid)}
    claim_now, support_now = current[claim['object_id']], current[support['object_id']]
    relations = confirmed_knowledge_relations_of(claim_now)
    supporting = next(row for row in relations if row['relation_type'] == 'supported_by')
    assert supporting['target_object_version'] == support_now['object_version']
    assert all((row.get('governance') or {}).get('validation_status') != 'revise'
               for row in console.snapshot_objects(sid))
    if change_support:
        console.confirm_object_type(actor_id=reviewer['account_id'], snapshot_id=sid,
            object_id=support['object_id'], confirmed_object_type='explanation',
            expected_revision=console.objects_revision(sid))
    before = deepcopy(physical_state(console, sid))
    def approve():
        return console.review_object(actor_id=reviewer['account_id'], snapshot_id=sid,
            object_id=claim['object_id'], decision='approve', confirmed_object_type='definition',
            suitability='ja', eindoordeel='goedkeuren', assessment=YES,
            relation_choices=[relation_choice_value(row) for row in relations
                              if row['relation_type'] in {'supported_by', 'explains'}],
            relation_review_ack=True, expected_revision=console.objects_revision(sid))
    if change_support:
        with pytest.raises(ConsoleError) as refused:
            approve()
        assert refused.value.code in {'knowledge_relation_target_stale', 'knowledge_relation_target_version_mismatch'}
        assert physical_state(console, sid) == before
    else:
        approve()
        binding = next(row for row in console.object_review_bindings(sid)
                       if row['object_id'] == claim['object_id'] and row.get('valid'))
        assert binding['supporting_evidence']['applicability'] == 'linked'
