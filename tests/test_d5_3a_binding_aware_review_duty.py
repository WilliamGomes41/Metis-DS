"""D5.3A binding-aware ReviewDuty and ReviewerRoute regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from src.review_duty_v1 import (
    FIRST_REVIEW,
    SECOND_REVIEW,
    exact_current_approver_ids,
    review_duty_for,
    review_duty_counts,
    reviewer_route_counts,
    reviewer_route_for,
)


def _obj(
    object_id: str = "rec-1",
    *,
    version: str = "1.0",
    status: str = "approved",
    four_eyes: bool = True,
) -> dict:
    return {
        "object_id": object_id,
        "object_version": version,
        "object_type": "recommendation",
        "confirmed_object_type": "recommendation",
        "content": {"clean_text": "Doe dit."},
        "metadata": {
            "admission": {
                "gate_result": "allowed",
                "section_path": ["Advies"],
            }
        },
        "governance": {
            "validation_status": status,
            "second_review": {
                "required": four_eyes,
                "status": "pending" if four_eyes else "not_required",
                "reviewer": None,
                "review_date": None,
                "snapshot_hash": None,
            },
        },
        "risk": {
            "level": "high" if four_eyes else "standard",
            "risk_level": "high" if four_eyes else "standard",
            "requires_second_review": four_eyes,
            "risk_fields": ["contraindication"] if four_eyes else [],
        },
        "uncertainty": {"has_uncertainty": False, "items": []},
        "provenance": {
            "canonical_object_hash": "a" * 64,
        },
    }


def _binding(
    obj: dict,
    reviewer_id: str,
    *,
    version: str | None = None,
    canonical_hash: str | None = None,
    confirmed_type: str | None = None,
    valid: bool = True,
    decision: str = "approve",
) -> dict:
    return {
        "object_id": obj["object_id"],
        "object_version": version or obj["object_version"],
        "canonical_object_hash": canonical_hash
        or obj["provenance"]["canonical_object_hash"],
        "confirmed_object_type": confirmed_type
        or obj["confirmed_object_type"],
        "reviewer": reviewer_id,
        "reviewer_id": reviewer_id,
        "decision": decision,
        "valid": valid,
    }


def test_no_current_approval_projects_first_review_even_if_governance_says_approved() -> None:
    obj = _obj()
    duty = review_duty_for(obj, review_path="richtlijn", bindings=[])

    assert duty is not None
    assert duty["stage"] == FIRST_REVIEW


def test_one_exact_current_approver_projects_second_review() -> None:
    obj = _obj()
    bindings = [_binding(obj, "reviewer-a")]

    duty = review_duty_for(obj, review_path="richtlijn", bindings=bindings)

    assert duty is not None
    assert duty["stage"] == SECOND_REVIEW
    assert exact_current_approver_ids(obj, bindings) == ("reviewer-a",)


def test_two_unique_exact_current_approvers_close_four_eyes_despite_pending_mirror() -> None:
    obj = _obj()
    bindings = [
        _binding(obj, "reviewer-a"),
        _binding(obj, "reviewer-b"),
    ]

    assert obj["governance"]["second_review"]["status"] == "pending"
    assert review_duty_for(obj, review_path="richtlijn", bindings=bindings) is None
    assert review_duty_counts(
        [obj],
        review_path="richtlijn",
        bindings=bindings,
    )["review_duties"] == 0


def test_duplicate_binding_from_same_reviewer_counts_once() -> None:
    obj = _obj()
    bindings = [
        _binding(obj, "reviewer-a"),
        _binding(obj, "reviewer-a"),
    ]

    assert exact_current_approver_ids(obj, bindings) == ("reviewer-a",)
    duty = review_duty_for(obj, review_path="richtlijn", bindings=bindings)
    assert duty is not None
    assert duty["stage"] == SECOND_REVIEW


def test_stale_version_hash_type_invalid_and_reject_bindings_do_not_count() -> None:
    obj = _obj()
    bindings = [
        _binding(obj, "old-version", version="0.9"),
        _binding(obj, "old-hash", canonical_hash="b" * 64),
        _binding(obj, "old-type", confirmed_type="explanation"),
        _binding(obj, "invalid", valid=False),
        _binding(obj, "reject", decision="reject"),
    ]

    assert exact_current_approver_ids(obj, bindings) == ()
    duty = review_duty_for(obj, review_path="richtlijn", bindings=bindings)
    assert duty is not None
    assert duty["stage"] == FIRST_REVIEW


def test_first_reviewer_waits_while_other_named_reviewer_can_act_on_second_review() -> None:
    obj = _obj()
    bindings = [_binding(obj, "reviewer-a")]

    first = reviewer_route_for(
        obj,
        review_path="richtlijn",
        reviewer_id="reviewer-a",
        bindings=bindings,
    )
    second = reviewer_route_for(
        obj,
        review_path="richtlijn",
        reviewer_id="reviewer-b",
        bindings=bindings,
    )

    assert first is not None
    assert first["canonical_task"] == "second_review"
    assert first["actionable"] is False
    assert first["waiting_for_other_reviewer"] is True

    assert second is not None
    assert second["canonical_task"] == "second_review"
    assert second["actionable"] is True
    assert second["waiting_for_other_reviewer"] is False


def test_reviewer_route_counts_separate_actionable_from_waiting() -> None:
    first_review = _obj("first", status="needs_review", four_eyes=False)
    second_review = _obj("second")
    bindings = [_binding(second_review, "reviewer-a")]

    counts_a = reviewer_route_counts(
        [first_review, second_review],
        review_path="richtlijn",
        reviewer_id="reviewer-a",
        bindings=bindings,
    )
    counts_b = reviewer_route_counts(
        [first_review, second_review],
        review_path="richtlijn",
        reviewer_id="reviewer-b",
        bindings=bindings,
    )

    assert counts_a["actionable_review_duties"] == 1
    assert counts_a["waiting_for_reviewer_duties"] == 1
    assert counts_a["actionable_second_review_duties"] == 0

    assert counts_b["actionable_review_duties"] == 2
    assert counts_b["waiting_for_reviewer_duties"] == 0
    assert counts_b["actionable_second_review_duties"] == 1


def test_non_four_eyes_object_closes_after_one_exact_current_approval() -> None:
    obj = _obj(four_eyes=False)
    bindings = [_binding(obj, "reviewer-a")]

    assert review_duty_for(obj, review_path="richtlijn", bindings=bindings) is None


def test_governance_only_fallback_remains_for_non_cutover_d52_callers() -> None:
    obj = _obj()
    duty = review_duty_for(obj, review_path="richtlijn")

    assert duty is not None
    assert duty["stage"] == SECOND_REVIEW
