"""Compact outcome reviews retain the existing strength and no-action rules.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang slop releasebewijs
"""
import json
import re
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.integrity_kernel import compute_canonical_object_hash
from src.review.ko_receipt_ui_v1 import read_saved_review
from src.review.review_assessment_v1 import ReviewAssessment, compact_approval_arguments, displayed_review_descriptor
from tests.semantic_fixture_support import install_fixture_history
from tests.test_explicit_review_policy import policy
from tests.test_ko_new_pages import compact_submission
from tests.test_review_command_bounded_http_v1 import physical_state
from tests.test_v225_beslisboom_path import _console, _accounts, _ingest_boom, _confirm_applies_if, _boom_freeze_bytes


def outcome_system(tmp_path, production_console, *, required=False, no_action=False):
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    source = json.loads(_boom_freeze_bytes())
    if no_action:
        source['outcomes'][0]['text'] = 'Geen actie nodig.'
    options = dict(named_reviewers=[], review_policy=policy(accounts, 'required')) if required else {}
    sid = _ingest_boom(console, accounts, data=json.dumps(source).encode(), **options)['snapshot_id']
    obj = next(row for row in console.snapshot_objects(sid) if row.get('proposed_object_type') == 'outcome')
    _confirm_applies_if(console, accounts, sid, obj)
    if required:
        from tests.test_decision_graph_chain import command
        graph = deepcopy(console._envelope(sid)['decision_graph'])
        current = {row['object_id']: row for row in console.snapshot_objects(sid)}
        for node in graph['nodes']:
            node['object_version'] = current[node['object_id']]['object_version']
            node['mode'] = 'terminal' if node['object_id'] == obj['object_id'] else 'context'
        graph.update(entrypoints=[obj['object_id']], edges=[], unresolved=[])
        console.update_decision_graph(**command(console, accounts, sid, 'prepare-outcome-graph', graph=graph))
    client = TestClient(console._metis_test_application)
    return console, accounts, sid, obj, client


def open_outcome(client, sid, obj, username='reviewer.bert', password='bert-secret'):
    assert client.post('/login', data={'username': username, 'password': password}, follow_redirects=False).status_code == 303
    page = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert page.status_code == 200
    return page


def test_known_outcome_strength_is_visible_saved_and_unchanged_by_second_review(tmp_path, production_console):
    console, accounts, sid, obj, client = outcome_system(tmp_path, production_console, required=True)
    page = open_outcome(client, sid, obj, 'researcher.anne', 'anne-secret')
    assert 'Sterkte van de aanbeveling: DOEN' in page.text
    assert 'data-can-approve="true"' in page.text
    first = compact_submission(page)
    saved = client.post('/review', data=first, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    receipt = read_saved_review(console, accounts['researcher'], sid, obj['object_id'], first['interaction_id'])
    assert receipt.object['confirmed_recommendation_strength'] == 'doen'
    first_bon = client.get(saved.headers['location'])
    assert '<span class="ko-status ko-status-neutral">Tweede review</span>' in first_bon.text
    assert receipt.event['details']['review_interaction']['assessment'] == ReviewAssessment('yes', 'yes', 'yes').as_evidence()
    version, digest = receipt.object['object_version'], compute_canonical_object_hash(receipt.object)
    second_page = open_outcome(client, sid, obj)
    assert 'Onafhankelijke tweede review' in second_page.text
    assert 'Sterkte van de aanbeveling: DOEN' in second_page.text
    second = compact_submission(second_page)
    saved_second = client.post('/review/second-review', data=second, follow_redirects=False)
    assert saved_second.status_code == 303, saved_second.text
    confirmed = read_saved_review(console, accounts['reviewer'], sid, obj['object_id'], second['interaction_id'])
    assert confirmed.object['object_version'] == version
    assert compute_canonical_object_hash(confirmed.object) == digest
    assert confirmed.object['confirmed_recommendation_strength'] == 'doen'


@pytest.mark.parametrize('unknown', [None, 'unknown'])
def test_unknown_outcome_strength_is_not_inferred_from_action_words(tmp_path, production_console, unknown):
    console, _, sid, obj, client = outcome_system(tmp_path, production_console)
    rows = console.snapshot_objects(sid)
    focal = next(row for row in rows if row['object_id'] == obj['object_id'])
    assert 'Verwijs' in focal['content']['clean_text']
    focal.pop('confirmed_recommendation_strength', None)
    focal.pop('proposed_recommendation_strength', None)
    if unknown:
        focal['proposed_recommendation_strength'] = unknown
    install_fixture_history(console, sid, rows)
    page = open_outcome(client, sid, obj)
    assert 'data-can-approve="false"' in page.text
    assert re.search(r'<button[^>]+value="approve"[^>]+disabled', page.text)
    assert 'Sterkte van de aanbeveling: DOEN' not in page.text
    before = physical_state(console, sid)
    refused = client.post('/review', data=compact_submission(page), follow_redirects=False)
    assert refused.status_code == 400
    assert physical_state(console, sid) == before


def test_no_action_outcome_keeps_existing_exemption_without_a_fabricated_stamp(tmp_path, production_console):
    console, _, sid, obj, client = outcome_system(tmp_path, production_console, no_action=True)
    rows = console.snapshot_objects(sid)
    focal = next(row for row in rows if row['object_id'] == obj['object_id'])
    focal.pop('proposed_recommendation_strength', None)
    focal.pop('confirmed_recommendation_strength', None)
    install_fixture_history(console, sid, rows)
    descriptor = displayed_review_descriptor(focal, rows, 'boom')
    assert descriptor.outcome_no_action
    assert descriptor.outcome_strength == ''
    assert 'recommendation_strength' not in compact_approval_arguments(ReviewAssessment('yes', 'yes', 'yes'), descriptor)
    page = open_outcome(client, sid, obj)
    assert 'Bronuitkomst: geen actie nodig.' in page.text
    assert 'data-can-approve="true"' in page.text
    saved = client.post('/review', data=compact_submission(page), follow_redirects=False)
    assert saved.status_code == 303, saved.text
    current = next(row for row in console.snapshot_objects(sid) if row['object_id'] == obj['object_id'])
    assert current['confirmed_recommendation_strength'] == 'niet_doen'
    assert current.get('no_action') or current['metadata'].get('no_action')


def test_confirmed_outcome_strength_takes_precedence_over_the_proposal():
    focal = {'object_id': 'outcome', 'object_version': '1.0', 'object_type': 'outcome',
        'content': {'clean_text': 'Verwijs naar de valpoli.'},
        'confirmed_recommendation_strength': 'overweeg', 'proposed_recommendation_strength': 'doen'}
    descriptor = displayed_review_descriptor(focal, [focal], 'boom')
    assert descriptor.can_confirm
    assert descriptor.outcome_strength == 'overweeg'
    assert compact_approval_arguments(ReviewAssessment('yes', 'yes', 'yes'), descriptor)['recommendation_strength'] == 'overweeg'
