"""D5.1 ReviewDuty kernel and semantic count regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from src.review_duty_v1 import (
    FIRST_REVIEW,
    LANE_BATCH,
    LANE_CONTEXTUAL,
    LANE_STRUCTURE,
    SECOND_REVIEW,
    repair_duty_count,
    review_duties,
    review_duty_counts,
    review_duty_for,
)
from src.review_workboard_v1 import _work_item_from_counts, _work_summary


def _obj(
    object_id: str,
    object_type: str,
    *,
    status: str = "needs_review",
    gate: str = "allowed",
    section: tuple[str, ...] = ("Inhoud",),
    second_required: bool = False,
    second_status: str = "not_required",
    uncertainty: bool = False,
    relation: bool = False,
) -> dict:
    row = {
        "object_id": object_id,
        "object_version": "1.0",
        "object_type": object_type,
        "confirmed_object_type": object_type
        if object_type not in {"unclassified"}
        else None,
        "content": {"clean_text": f"Passage {object_id}."},
        "structure": {"section_path": list(section)},
        "metadata": {
            "admission": {
                "gate_result": gate,
                "section_path": list(section),
            }
        },
        "governance": {
            "validation_status": status,
            "second_review": {
                "required": second_required,
                "status": second_status,
                "reviewer": None,
                "review_date": None,
                "snapshot_hash": None,
            },
        },
        "risk": {
            "level": "normal",
            "risk_level": "standard",
            "risk_fields": [],
            "requires_second_review": second_required,
        },
        "uncertainty": {
            "has_uncertainty": uncertainty,
            "items": [],
        },
        "provenance": {
            "canonical_object_hash": f"hash-{object_id}",
        },
    }
    if relation:
        row["proposed_knowledge_relations"] = [
            {
                "version": "knowledge-relation-v1",
                "relation_id": "rel-" + "a" * 64,
                "relation_type": "supported_by",
                "target_object_id": "support-1",
                "target_object_version": "1.0",
            }
        ]
    return row


def test_review_duty_lifecycle_projects_first_second_and_closed_states() -> None:
    first = _obj("rec", "recommendation")
    second = _obj(
        "second",
        "explanation",
        status="approved",
        second_required=True,
        second_status="pending",
    )
    approved = _obj("approved", "definition", status="approved")
    revise = _obj("revise", "recommendation", status="revise")
    rejected = _obj("rejected", "recommendation", status="rejected")

    first_duty = review_duty_for(first, review_path="richtlijn")
    second_duty = review_duty_for(second, review_path="richtlijn")

    assert first_duty is not None
    assert first_duty["stage"] == FIRST_REVIEW
    assert first_duty["lane"] == LANE_CONTEXTUAL

    assert second_duty is not None
    assert second_duty["stage"] == SECOND_REVIEW
    assert second_duty["lane"] == LANE_CONTEXTUAL

    assert review_duty_for(approved, review_path="richtlijn") is None
    assert review_duty_for(revise, review_path="richtlijn") is None
    assert review_duty_for(rejected, review_path="richtlijn") is None


def test_structure_batch_and_relation_bearing_context_are_distinct_lanes() -> None:
    heading = _obj("heading", "heading")
    definition = _obj("definition", "definition")
    related_explanation = _obj("related", "explanation", relation=True)

    heading_duty = review_duty_for(heading, review_path="richtlijn")
    definition_duty = review_duty_for(definition, review_path="richtlijn")
    relation_duty = review_duty_for(
        related_explanation,
        review_path="richtlijn",
    )

    assert heading_duty is not None
    assert heading_duty["lane"] == LANE_STRUCTURE
    assert definition_duty is not None
    assert definition_duty["lane"] == LANE_BATCH
    assert relation_duty is not None
    assert relation_duty["lane"] == LANE_CONTEXTUAL


def test_review_duty_counts_do_not_mix_repair_or_correction_waiting_work() -> None:
    rows = [
        _obj("heading", "heading"),
        _obj("rec", "recommendation"),
        _obj("definition", "definition"),
        _obj(
            "second",
            "explanation",
            status="approved",
            second_required=True,
            second_status="pending",
        ),
        _obj("related", "explanation", relation=True),
        _obj("repair", "definition", gate="blocked"),
        _obj("revise", "recommendation", status="revise"),
        _obj("done", "definition", status="approved"),
    ]

    duties = review_duties(rows, review_path="richtlijn")
    counts = review_duty_counts(rows, review_path="richtlijn")

    assert len(duties) == 5
    assert counts == {
        "review_duties": 5,
        "first_review_duties": 4,
        "second_review_duties": 1,
        "structure_review_duties": 1,
        "contextual_review_duties": 3,
        "batch_review_duties": 1,
    }
    assert repair_duty_count(rows, review_path="richtlijn") == 1


def test_one_object_has_at_most_one_open_review_duty() -> None:
    obj = _obj(
        "second",
        "recommendation",
        status="approved",
        second_required=True,
        second_status="pending",
    )
    duties = review_duties([obj, obj], review_path="richtlijn")
    assert len(duties) == 1
    assert duties[0]["stage"] == SECOND_REVIEW


def test_workboard_review_count_excludes_disposition_and_repair_counts() -> None:
    base = {
        "envelope": {"snapshot_id": "snap-1"},
        "snapshot_id": "snap-1",
        "lifecycle_status": {
            "workflow_status": "processing",
            "release_status": "none",
            "serving_status": "inactive",
            "presentation_status": "in_review",
        },
        "heading_pending": 1,
        "individual_pending": 2,
        "normal_passages": 3,
        "normal_batches": 1,
        "blocked_count": 7,
        "closure_gap_ids": ["gap-1", "gap-2"],
        "closure_gap_count": 2,
        "source_passage_review_complete": False,
        "review_duties": 6,
        "first_review_duties": 5,
        "second_review_duties": 1,
        "structure_review_duties": 1,
        "contextual_review_duties": 2,
        "batch_review_duties": 3,
    }
    item = _work_item_from_counts(**base)

    assert item["remaining_review_items"] == 6
    assert item["review_duties"] == 6
    assert item["disposition_duties"] == 2
    assert item["repair_duties"] == 7
    assert _work_summary(item) == "6 inhoudelijke beoordelingen open; 6 voor jou uitvoerbaar."


def test_closure_only_work_is_not_mislabeled_as_review_duty() -> None:
    item = _work_item_from_counts(
        envelope={"snapshot_id": "snap-1"},
        snapshot_id="snap-1",
        lifecycle_status={
            "workflow_status": "processing",
            "release_status": "none",
            "serving_status": "inactive",
            "presentation_status": "in_review",
        },
        heading_pending=0,
        individual_pending=0,
        normal_passages=0,
        normal_batches=0,
        blocked_count=0,
        closure_gap_ids=["gap-1"],
        closure_gap_count=1,
        source_passage_review_complete=False,
        review_duties=0,
        first_review_duties=0,
        second_review_duties=0,
        structure_review_duties=0,
        contextual_review_duties=0,
        batch_review_duties=0,
    )

    assert item["remaining_review_items"] == 0
    assert item["review_duties"] == 0
    assert item["disposition_duties"] == 1
    assert item["next_task"] == "disposition"
    assert _work_summary(item) == "Geen inhoudelijke review open; 1 bronpassage nog afhandelen."
