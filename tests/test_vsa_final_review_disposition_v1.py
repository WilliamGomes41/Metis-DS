"""VSA Slice 2: one explicit derived final-review disposition policy.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from typing import Any

from src.publication_readiness_v1 import publication_review_readiness
from src.review_disposition_v1 import definitive_review_disposition


def _object(register_status: str, review_status: str = "needs_review") -> dict[str, Any]:
    return {
        "object_id": f"{register_status}-{review_status}",
        "object_type": "explanation",
        "metadata": {"passage_register": {"status": register_status}},
        "governance": {"validation_status": review_status},
    }


def test_selected_candidate_approved_is_final() -> None:
    disposition = definitive_review_disposition(_object("selected_as_candidate", "approved"))
    assert disposition["state"] == "final"
    assert disposition["final"] is True
    assert disposition["valid"] is True
    assert disposition["outcome"] == "approved"


def test_selected_candidate_rejected_is_final() -> None:
    disposition = definitive_review_disposition(_object("selected_as_candidate", "rejected"))
    assert disposition["state"] == "final"
    assert disposition["final"] is True
    assert disposition["outcome"] == "rejected"


def test_selected_candidate_needs_review_or_revise_stays_open() -> None:
    for review_status in ("needs_review", "revise", ""):
        disposition = definitive_review_disposition(_object("selected_as_candidate", review_status))
        assert disposition["state"] == "open"
        assert disposition["final"] is False
        assert disposition["valid"] is True
        assert disposition["outcome"] == "candidate_review_open"


def test_terminal_non_candidate_dispositions_are_final() -> None:
    for register_status in (
        "used_as_context",
        "linked_as_support",
        "excluded_with_reason",
    ):
        disposition = definitive_review_disposition(_object(register_status, "needs_review"))
        assert disposition["state"] == "final"
        assert disposition["final"] is True
        assert disposition["valid"] is True
        assert disposition["outcome"] == register_status


def test_not_yet_assessed_is_always_open() -> None:
    for review_status in ("needs_review", "approved", "rejected"):
        disposition = definitive_review_disposition(_object("not_yet_assessed", review_status))
        assert disposition["state"] == "open"
        assert disposition["final"] is False
        assert disposition["valid"] is True
        assert disposition["outcome"] == "not_yet_assessed"


def test_unknown_register_status_fails_closed() -> None:
    disposition = definitive_review_disposition(_object("invented", "approved"))
    assert disposition["state"] == "open"
    assert disposition["final"] is False
    assert disposition["valid"] is False
    assert disposition["outcome"] == "invalid_register_status"


def test_document_is_not_a_curator_disposition() -> None:
    obj = _object("selected_as_candidate", "approved")
    obj["object_type"] = "document"
    disposition = definitive_review_disposition(obj)
    assert disposition["state"] == "not_applicable"
    assert disposition["final"] is False
    assert disposition["valid"] is True


def test_slice_one_reuses_final_disposition_for_candidate_readiness() -> None:
    objects = [
        _object("selected_as_candidate", "approved"),
        _object("selected_as_candidate", "needs_review"),
        _object("excluded_with_reason", "needs_review"),
    ]
    readiness = publication_review_readiness(objects)
    assert readiness["review_required_object_count"] == 2
    assert readiness["unresolved_review_object_count"] == 1
    assert readiness["review_complete"] is False
