"""Explicit WorkingRevision participation, with unchanged absent-policy legacy rules.

The envelope owns the policy. Objects carry its exact, hash-bound projection so
shared object gates can evaluate participation without an ambient console.
Publication verifies those projections against the envelope authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

CONTRACT = "explicit-review-v1"


def validate_policy(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"contract", "revision", "primary", "assignments"}:
        raise ValueError("invalid_review_policy")
    if value["contract"] != CONTRACT or type(value["revision"]) is not int or value["revision"] < 1:
        raise ValueError("invalid_review_policy")
    primary = value["primary"]
    if not isinstance(primary, str) or not primary or not isinstance(value["assignments"], list):
        raise ValueError("invalid_review_policy")
    seen = {primary}
    for row in value["assignments"]:
        if not isinstance(row, dict) or set(row) != {"reviewer_id", "participation"}:
            raise ValueError("invalid_review_assignment")
        actor = row["reviewer_id"]
        if not isinstance(actor, str) or not actor or actor in seen or row["participation"] not in {"optional", "required"}:
            raise ValueError("invalid_review_assignment")
        seen.add(actor)
    return deepcopy(value)


def object_policy(obj: dict[str, Any]) -> dict[str, Any] | None:
    metadata = obj.get("metadata") or {}
    if "review_policy" not in metadata:
        return None
    return validate_policy(metadata["review_policy"])


def participants(policy: dict[str, Any]) -> list[str]:
    return [policy["primary"], *(row["reviewer_id"] for row in policy["assignments"])]


def required_reviewers(policy: dict[str, Any]) -> set[str]:
    return {policy["primary"], *(row["reviewer_id"] for row in policy["assignments"] if row["participation"] == "required")}


def missing_reviewers(obj: dict[str, Any], bindings: list[dict[str, Any]]) -> set[str]:
    from src.review_duty_v1 import exact_current_approver_ids

    policy = object_policy(obj)
    return required_reviewers(policy) - set(exact_current_approver_ids(obj, bindings)) if policy else set()


def project_policy(objects: list[dict[str, Any]], policy: dict[str, Any]) -> None:
    from src.four_eyes_v1 import mark_four_eyes_on_object
    from src.integrity_kernel import stamp_canonical_hashes

    for obj in objects:
        obj.setdefault("metadata", {})["review_policy"] = deepcopy(policy)
        mark_four_eyes_on_object(obj)
        stamp_canonical_hashes(obj)
