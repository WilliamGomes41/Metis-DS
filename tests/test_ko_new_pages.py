"""New review pages submit actual answers and show only exact durable results.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang slop releasebewijs
"""
import re

import pytest
from fastapi.testclient import TestClient

from src.review.ko_receipt_ui_v1 import read_saved_review
from tests.production_support import restart_production
from tests.test_ko_receipt_ui import prepared
from tests.test_review_command_bounded_http_v1 import physical_state, bounded_post_only
from tests.test_review_command_freshness_v1 import system, participation, approve


def compact_submission(page):
    fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', page.text))
    return {**fields, 'review_action': 'approve', 'applicable': 'yes',
            'complete': 'yes', 'placed_correctly': 'yes'}


def test_compact_http_commit_standalone_bon_and_durable_answers(tmp_path, production_console, monkeypatch):
    console, sid, reviewer, obj, client, page, _ = prepared(tmp_path, production_console, monkeypatch)
    assert page.text.count('class="ko-question"') == 3
    assert not re.search(r'<form[^>]*\sdata-review-form', page.text)
    assert 'ko-review.css' in page.text
    assert not re.search(r'<input[^>]+type="radio"[^>]+checked', page.text)
    data = compact_submission(page)
    data.update(confirmed_object_type='definition', recommendation_direction='for')
    with bounded_post_only(console, sid, monkeypatch):
        saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    bon = client.get(saved.headers['location'])
    assert bon.status_code == 200
    assert 'data-review-receipt' in bon.text
    assert not re.search(r'<form[^>]*\sdata-ko-assessment-form', bon.text)
    assert 'data-ko-next-passage' in bon.text
    assert bon.text.count('data-answer="yes"') == 3
    receipt = read_saved_review(console, console._account(reviewer), sid, obj['object_id'], data['interaction_id'])
    assert receipt.object['confirmed_object_type'] == 'recommendation'
    assert receipt.object['confirmed_recommendation_semantics']['direction'] == 'against'
    answers = receipt.event['details']['review_interaction']['assessment']
    assert answers == {'version': 'review-assessment-v1', 'applicable': 'yes',
                       'complete': 'yes', 'placed_correctly': 'yes'}
    restarted = restart_production(console)
    reopened = read_saved_review(restarted, restarted._account(reviewer), sid, obj['object_id'], data['interaction_id'])
    assert reopened.event == receipt.event
    assert reopened.object == receipt.object
    stale = client.post('/review', data=data, follow_redirects=False)
    assert stale.status_code == 409
    assert 'data-review-receipt' not in stale.text
    assert 'data-ko-assessment-form' in stale.text
    assert stale.text.count(' checked') == 3


@pytest.mark.parametrize('change', [{'complete': ''}, {'complete': 'adjust'}, {'applicable': 'true'}])
def test_incomplete_or_tampered_compact_http_never_mutates(tmp_path, production_console, monkeypatch, change):
    console, sid, _, _, client, page, _ = prepared(tmp_path, production_console, monkeypatch)
    before = physical_state(console, sid)
    response = client.post('/review', data={**compact_submission(page), **change}, follow_redirects=False)
    assert response.status_code == 400
    assert 'data-ko-assessment-form' in response.text
    assert 'data-review-receipt' not in response.text
    assert physical_state(console, sid) == before


def test_later_without_answers_has_no_durable_decision_or_bon(tmp_path, production_console, monkeypatch):
    console, sid, _, _, client, page, _ = prepared(tmp_path, production_console, monkeypatch)
    before = physical_state(console, sid)
    data = {key: value for key, value in compact_submission(page).items()
            if key not in {'applicable', 'complete', 'placed_correctly'}}
    result = client.post('/review', data={**data, 'review_action': 'later'}, follow_redirects=False)
    assert result.status_code == 303, result.text
    assert 'receipt_' not in result.headers['location']
    after = physical_state(console, sid)
    assert after['objects'] == before['objects']
    assert after['bindings'] == before['bindings']


def test_second_review_keeps_exact_tuple_and_refuses_mislabelled_rejection(system, production_app):
    from src.integrity_kernel import compute_canonical_object_hash
    console, _, accounts, sid, obj = system
    participation(console, accounts, sid, 'archive', accounts['reviewer']['account_id'])
    participation(console, accounts, sid, 'add_required', accounts['reviewer']['account_id'])
    approve(console, accounts, sid, obj)
    original = next(row for row in console.snapshot_objects(sid) if row['object_id'] == obj['object_id'])
    client = TestClient(production_app(console))
    client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'})
    page = client.get('/review', params={'document': sid, 'object': obj['object_id'], 'task': 'second_review'})
    assert 'Onafhankelijke tweede review' in page.text
    assert 'value="reject"' not in page.text
    data = compact_submission(page)
    before = physical_state(console, sid)
    rejected = client.post('/review/second-review', data={**data, 'review_action': 'reject',
        'comment': 'Geen afwijzing als correctie opslaan.'}, follow_redirects=False)
    assert rejected.status_code == 400
    assert physical_state(console, sid) == before
    saved = client.post('/review/second-review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    receipt = read_saved_review(console, accounts['reviewer'], sid, obj['object_id'], data['interaction_id'])
    assert receipt is not None
    assert receipt.object['object_version'] == original['object_version']
    assert compute_canonical_object_hash(receipt.object) == compute_canonical_object_hash(original)
    assert receipt.event['details']['review_interaction']['assessment']['complete'] == 'yes'


@pytest.mark.parametrize('invalid', [dict(review_action='reject', comment=''),
    dict(review_action='unknown'), dict(complete='tampered')])
def test_early_validation_error_cannot_rebase_old_answers_onto_current_revision(tmp_path, production_console, monkeypatch, invalid):
    console, sid, _, obj, client, page, _ = prepared(tmp_path, production_console, monkeypatch)
    old = compact_submission(page)
    peer = next(row for row in console.snapshot_objects(sid)
        if row['object_id'] != obj['object_id'] and row.get('proposed_object_type') == 'recommendation')
    peer_page = client.get('/review', params={'document': sid, 'object': peer['object_id']})
    winner = client.post('/review', data=compact_submission(peer_page), follow_redirects=False)
    assert winner.status_code == 303, winner.text
    committed = physical_state(console, sid)
    refused = client.post('/review', data={**old, **invalid}, follow_redirects=False)
    assert refused.status_code == 409
    recovered = compact_submission(refused)
    assert recovered['snapshot_revision'] == old['snapshot_revision']
    assert refused.text.count(' checked') == (2 if 'complete' in invalid else 3)
    assert re.search(r'<button[^>]+value="approve"[^>]+disabled', refused.text)
    assert 'Passage opnieuw beoordelen' in refused.text
    assert client.post('/review', data=recovered, follow_redirects=False).status_code == 409
    assert physical_state(console, sid) == committed
    fresh = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert compact_submission(fresh)['snapshot_revision'] != old['snapshot_revision']
    assert not re.search(r'<input[^>]+type="radio"[^>]+checked', fresh.text)


def test_standalone_bon_avoids_global_prefetch_but_keeps_exact_authorization(tmp_path, production_console, monkeypatch):
    from src.workflows.workflow_transaction_v1 import workflow_transaction_active
    console, sid, _, _, client, page, _ = prepared(tmp_path, production_console, monkeypatch)
    data = compact_submission(page)
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303

    def no_global_prefetch():
        raise AssertionError('Standalone bon must not calculate lifecycle for all documents')

    monkeypatch.setattr(console, 'list_document_lifecycle_statuses', no_global_prefetch)
    original = console.document_release_serving_status
    canonical_reads = []

    def selected_canonical_status(snapshot_id, **kwargs):
        assert not workflow_transaction_active()
        canonical_reads.append(snapshot_id)
        return original(snapshot_id, **kwargs)

    monkeypatch.setattr(console, 'document_release_serving_status', selected_canonical_status)
    result = client.get(saved.headers['location'])
    assert result.status_code == 200
    assert result.text.count('data-answer="yes"') == 3
    assert canonical_reads == [sid]
    console.create_account(username='foreign-reviewer', password='fixture-only', roles=('reviewer',))
    client.post('/login', data={'username': 'foreign-reviewer', 'password': 'fixture-only'})

    def no_private_event_read(*args, **kwargs):
        raise AssertionError('A reviewer outside this document cannot read its event')

    monkeypatch.setattr(console.workflow_review_store, 'read_review_command_events', no_private_event_read)
    forbidden = client.get(saved.headers['location'])
    assert forbidden.status_code == 400
    assert 'data-review-receipt' not in forbidden.text
    assert canonical_reads == [sid]


@pytest.mark.parametrize('destination', ['document', 'object', 'after', 'partial_receipt', 'tree'])
def test_other_review_destinations_keep_document_status_prefetch(tmp_path, production_console, monkeypatch, destination):
    console, sid, _, obj, client, _, _ = prepared(tmp_path, production_console, monkeypatch)
    original = console.list_document_lifecycle_statuses
    calls = []

    def document_statuses():
        result = original()
        calls.append(result)
        return result

    monkeypatch.setattr(console, 'list_document_lifecycle_statuses', document_statuses)
    params = {'document': sid}
    if destination in {'object', 'after'}:
        params[destination] = obj['object_id']
    if destination == 'partial_receipt':
        params['receipt_interaction'] = 'incomplete-reference'
    response = client.get('/tree' if destination == 'tree' else '/review', params=params)
    assert response.status_code == 200
    assert calls and sid in calls[0]
