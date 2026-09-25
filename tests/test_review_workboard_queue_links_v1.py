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
        "actionable_review_duties": 69,
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
        "next_href": "/review?document=snap-test&task=structure",
    }


def test_non_empty_workboard_queues_are_independent_links() -> None:
    html = _workboard_card(_item())

    assert html.count('class="review-work-queue-link"') == 4
    assert (
        'data-work-queue="structure" href="/review?document=snap-test&amp;task=structure">56 structuur</a>'
        in html
    )
    assert (
        'data-work-queue="contextual" href="/review?document=snap-test&amp;task=contextual">6 in samenhang</a>'
        in html
    )
    assert (
        'data-work-queue="batch" href="/review?document=snap-test&amp;task=batch">7 vergelijkbaar</a>'
        in html
    )
    assert (
        'data-work-queue="repair" href="/review?document=snap-test&amp;task=repair">361 technisch herstel</a>'
        in html
    )
    assert "Volgende stap" in html
    assert '>Ga verder</a>' in html


def test_empty_queue_is_not_rendered_as_a_link() -> None:
    item = _item()
    item["actionable_contextual_duties"] = 0

    html = _workboard_card(item)

    assert 'data-work-queue="contextual"' not in html
    assert "0 in samenhang" not in html
    assert html.count('class="review-work-queue-link"') == 3


def test_closed_working_revision_offers_no_review_queue_links() -> None:
    item = _item()
    lifecycle = dict(item["lifecycle_status"])
    lifecycle["workflow_status"] = "closed"
    item["lifecycle_status"] = lifecycle

    html = _workboard_card(item)

    assert 'class="review-work-queue-link"' not in html
