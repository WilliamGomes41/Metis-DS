"""Regression proof for direct Review workboard queue navigation.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import pytest

from src.review_workboard_v1 import _workboard_card

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _item() -> dict[str, object]:
    return {
        "snapshot_id": "snap-test",
        "envelope": {
            "snapshot_id": "snap-test",
            "title": "Testdocument",
            "version": "1.0",
            "family": "zorg",
            "class": "richtlijn",
            "state": "captured_not_published",
        },
        "lifecycle_status": {
            "workflow_status": "processing",
            "release_status": "none",
            "serving_status": "inactive",
            "presentation_status": "in_review",
        },
        "meaningful_status": "in_review",
        "work_state": "review",
        "remaining_review_items": 69,
        "review_duties": 69,
        "first_review_duties": 69,
        "second_review_duties": 0,
        "structure_review_duties": 56,
        "contextual_review_duties": 6,
        "batch_review_duties": 7,
        "actionable_review_duties": 13,
        "waiting_for_reviewer_duties": 0,
        "actionable_structure_duties": 56,
        "actionable_contextual_duties": 6,
        "actionable_batch_duties": 7,
        "actionable_second_review_duties": 0,
        "heading_pending": 56,
        "individual_pending": 6,
        "normal_passages": 7,
        "normal_batches": 4,
        "blocked_count": 361,
        "closure_gap_ids": [],
        "closure_gap_count": 0,
        "source_passage_review_complete": False,
        "next_task": "structure",
        "next_title": "Koppen controleren",
        "next_description": "Controleer de indeling van het document",
        "next_href": "/source-selection?document=snap-test&task=structure",
    }


def test_one_primary_action_skips_prose_structure_and_source_work() -> None:
    html = _workboard_card(_item())
    assert html.count('data-personal-review-action') == 1
    assert 'task=contextual' in html
    assert 'data-personal-open>13<' in html
    assert '>Beginnen</a>' in html
    for old in ('data-work-queue', 'task=structure', 'task=repair', '361 technisch', '56 structuur', 'Volgende stap'):
        assert old not in html


def test_existing_next_content_lane_without_contextual_work() -> None:
    item = _item()
    item['actionable_contextual_duties'] = 0
    item['actionable_review_duties'] = 7
    html = _workboard_card(item, started=True, q='zorg & welzijn', page=2)
    assert 'task=batch' in html
    assert 'q=zorg+%26+welzijn&amp;page=2' in html
    assert '>Verder beoordelen</a>' in html
    assert html.count('data-personal-review-action') == 1


def test_closed_working_revision_offers_no_primary_review_action() -> None:
    item = _item()
    item['lifecycle_status']['workflow_status'] = 'closed'
    html = _workboard_card(item)
    assert 'data-personal-review-action' not in html
    assert 'data-personal-state="complete"' in html


def test_boom_path_keeps_its_existing_structure_review_route() -> None:
    item = _item()
    item['envelope']['class'] = 'beslisboom'
    html = _workboard_card(item)
    assert 'href="/review?document=snap-test&amp;task=structure' in html


def test_graph_override_and_independent_wait_are_preserved() -> None:
    item = _item()
    item['actionable_review_duties'] = 0
    item['review_duties'] = 0
    item['next_href'] = '/review/decision-graph?document=snap-test'
    html = _workboard_card(item)
    assert '/review/decision-graph?' in html and 'data-personal-review-action' in html
    assert 'De beslisroutes vragen jouw beoordeling.' in html
    item['work_state'] = 'waiting_for_reviewer'
    item['next_href'] = ''
    html = _workboard_card(item)
    assert 'data-personal-state="waiting"' in html
    assert 'data-personal-review-action' not in html
