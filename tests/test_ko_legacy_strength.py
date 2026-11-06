"""Existing stored legacy strength uses the existing command, without modern inference.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang slop releasebewijs
"""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.review.ko_receipt_ui_v1 import read_saved_review
from src.review.review_assessment_v1 import ReviewAssessment, displayed_review_descriptor, compact_approval_arguments
from tests.semantic_fixture_support import install_fixture_history
from tests.test_d4_3_human_relation_confirmation import _console, _accounts, _ingest, _plant_proposals
from tests.test_ko_new_pages import compact_submission
from tests.test_review_command_bounded_http_v1 import physical_state


def legacy_system(tmp_path, production_console, *, stored_strength=''):
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    sid = _ingest(console, accounts)['snapshot_id']
    focal, _ = _plant_proposals(console, sid, include_explanation=False)
    if stored_strength:
        from src.integrity_kernel import stamp_canonical_hashes
        rows = console._load_objects(sid)
        current = next(row for row in rows if row['object_id'] == focal['object_id']
                       and row['object_version'] == focal['object_version'])
        current['proposed_recommendation_strength'] = stored_strength
        stamp_canonical_hashes(current)
        install_fixture_history(console, sid, rows)
    client = TestClient(console._metis_test_application)
    client.post('/login', data={'username': 'reviewer.d43', 'password': 'reviewer-secret'})
    return console, accounts, sid, focal, client


def test_known_legacy_stamp_commits_without_fabricating_modern_semantics(tmp_path, production_console):
    console, accounts, sid, focal, client = legacy_system(tmp_path, production_console, stored_strength='doen')
    page = client.get('/review', params={'document': sid, 'object': focal['object_id']})
    assert 'Sterkte van de aanbeveling: DOEN' in page.text
    assert 'Aanraden · Sterk' not in page.text
    data = {**compact_submission(page), 'recommendation_direction': 'against', 'recommendation_strength_level': 'weak'}
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    receipt = read_saved_review(console, accounts['reviewer'], sid, focal['object_id'], data['interaction_id'])
    assert receipt.object['confirmed_recommendation_strength'] == 'doen'
    assert 'confirmed_recommendation_semantics' not in receipt.object
    assert receipt.event['details']['review_interaction']['assessment'] == ReviewAssessment('yes', 'yes', 'yes').as_evidence()


def test_missing_legacy_and_modern_records_remains_blocked_despite_action_text(tmp_path, production_console):
    console, _, sid, focal, client = legacy_system(tmp_path, production_console)
    assert not any(focal.get(field) for field in ('proposed_recommendation_semantics', 'confirmed_recommendation_semantics',
                  'proposed_recommendation_strength', 'confirmed_recommendation_strength'))
    page = client.get('/review', params={'document': sid, 'object': focal['object_id']})
    assert 'data-can-approve="false"' in page.text
    before = physical_state(console, sid)
    refused = client.post('/review', data=compact_submission(page), follow_redirects=False)
    assert refused.status_code == 400
    assert physical_state(console, sid) == before


@pytest.mark.parametrize('record', [None, {}, {'version': 'invalid'}, {'strength_status': 'unmapped'}])
def test_present_invalid_modern_record_never_falls_back_to_known_legacy(record):
    obj = {'object_id': 'rec', 'object_version': '1.0', 'object_type': 'recommendation',
        'content': {'clean_text': 'Bespreek de mogelijkheden.'},
        'proposed_recommendation_semantics': record, 'proposed_recommendation_strength': 'doen'}
    descriptor = displayed_review_descriptor(obj, [obj], 'richtlijn')
    assert not descriptor.can_confirm
    assert descriptor.legacy_recommendation_strength == ''
    with pytest.raises(ConsoleError):
        compact_approval_arguments(ReviewAssessment('yes', 'yes', 'yes'), descriptor)


def test_confirmed_legacy_value_has_priority_and_does_not_generate_modern_choices():
    obj = {'object_id': 'rec', 'object_version': '1.0', 'object_type': 'recommendation',
        'content': {'clean_text': 'Bespreek de mogelijkheden.'},
        'confirmed_recommendation_strength': 'overweeg', 'proposed_recommendation_strength': 'doen'}
    descriptor = displayed_review_descriptor(obj, [obj], 'richtlijn')
    arguments = compact_approval_arguments(ReviewAssessment('yes', 'yes', 'yes'), descriptor)
    assert descriptor.direction == '' and descriptor.strength_choice == ''
    assert descriptor.legacy_recommendation_strength == 'overweeg'
    assert arguments['recommendation_strength'] == 'overweeg'
    assert 'recommendation_direction' not in arguments
    assert 'recommendation_strength_level' not in arguments


def test_valid_modern_evidence_remains_the_owner_when_a_legacy_stamp_is_also_present():
    from tests.test_recommendation_context_v3 import prepare
    _, rows, focal, fragments = prepare()
    obj = deepcopy(focal)
    obj['proposed_recommendation_strength'] = 'doen'
    rows = [obj if row['object_id'] == obj['object_id'] else row for row in rows]
    descriptor = displayed_review_descriptor(obj, rows, 'richtlijn', fragments=fragments)
    arguments = compact_approval_arguments(ReviewAssessment('yes', 'yes', 'yes'), descriptor)
    assert descriptor.legacy_recommendation_strength == ''
    assert arguments['recommendation_direction'] == 'against'
    assert arguments['recommendation_strength_level'] == 'not_stated'
    assert 'recommendation_strength' not in arguments
