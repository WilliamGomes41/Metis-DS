"""Derived curator finality from existing passage and review state.

This policy introduces no new persisted status. It normalizes the current
passage-register disposition plus governance review status into one fail-closed
answer that other vertical slices can reuse.
"""
from __future__ import annotations

from typing import Any

from src.passage_register_v1 import PASSAGE_REGISTER_STATUSES, passage_register_of

FINAL_CANDIDATE_REVIEW_STATUSES = frozenset({"approved", "rejected"})
FINAL_NON_CANDIDATE_DISPOSITIONS = frozenset(
    {"used_as_context", "linked_as_support", "excluded_with_reason"}
)


def definitive_review_disposition(obj: dict[str, Any]) -> dict[str, Any]:
    """Classify one current non-document object as open or curatorially final.

    Unknown or contradictory state fails closed. ``selected_as_candidate`` only
    becomes final after an existing terminal governance review outcome.
    ``not_yet_assessed`` is always open.
    """
    if obj.get("object_type") == "document":
        return {
            "state": "not_applicable",
            "final": False,
            "valid": True,
            "outcome": "document",
            "register_status": "",
            "review_status": "",
        }

    register_status = str(passage_register_of(obj).get("status") or "")
    review_status = str((obj.get("governance") or {}).get("validation_status") or "")

    if register_status not in PASSAGE_REGISTER_STATUSES:
        return {
            "state": "open",
            "final": False,
            "valid": False,
            "outcome": "invalid_register_status",
            "register_status": register_status,
            "review_status": review_status,
        }

    if register_status == "not_yet_assessed":
        return {
            "state": "open",
            "final": False,
            "valid": True,
            "outcome": "not_yet_assessed",
            "register_status": register_status,
            "review_status": review_status,
        }

    if register_status in FINAL_NON_CANDIDATE_DISPOSITIONS:
        return {
            "state": "final",
            "final": True,
            "valid": True,
            "outcome": register_status,
            "register_status": register_status,
            "review_status": review_status,
        }

    if register_status == "selected_as_candidate":
        if review_status in FINAL_CANDIDATE_REVIEW_STATUSES:
            return {
                "state": "final",
                "final": True,
                "valid": True,
                "outcome": review_status,
                "register_status": register_status,
                "review_status": review_status,
            }
        return {
            "state": "open",
            "final": False,
            "valid": True,
            "outcome": "candidate_review_open",
            "register_status": register_status,
            "review_status": review_status,
        }

    return {
        "state": "open",
        "final": False,
        "valid": False,
        "outcome": "invalid_disposition_state",
        "register_status": register_status,
        "review_status": review_status,
    }
