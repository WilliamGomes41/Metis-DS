"""Explicit WorkingRevision participation, with unchanged absent-policy legacy rules.

The envelope owns the policy. Objects carry its exact projection in immutable
v1 metadata or mutable v2 governance so shared gates need no ambient console.
Publication verifies those projections against the envelope authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

CONTRACT = "explicit-review-v1"
MANAGED_CONTRACT = "managed-review-v2"


def validate_policy(value: dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict) and value.get("contract") == MANAGED_CONTRACT:
        return validate_managed_policy(value)
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
    managed = (obj.get("governance") or {}).get("review_policy")
    if managed is not None:
        if managed.get("contract") != MANAGED_CONTRACT:
            raise ValueError("invalid_managed_review_policy")
        return validate_managed_policy(managed)
    metadata = obj.get("metadata") or {}
    if "review_policy" not in metadata:
        return None
    return validate_policy(metadata["review_policy"])


def participants(policy: dict[str, Any]) -> list[str]:
    return [policy["primary"], *(row["reviewer_id"] for row in policy["assignments"] if row.get("status", "active") == "active")]


def required_reviewers(policy: dict[str, Any]) -> set[str]:
    return {policy["primary"], *(row["reviewer_id"] for row in policy["assignments"] if row["participation"] == "required")}


def missing_reviewers(obj: dict[str, Any], bindings: list[dict[str, Any]]) -> set[str]:
    from src.review_duty_v1 import exact_current_approver_ids

    policy = object_policy(obj)
    return (required_reviewers(policy) - set(exact_current_approver_ids(obj, bindings))) | archived_required(policy) if policy else set()


def project_policy(objects: list[dict[str, Any]], policy: dict[str, Any]) -> None:
    from src.four_eyes_v1 import mark_four_eyes_on_object
    from src.integrity_kernel import stamp_canonical_hashes

    for obj in objects:
        if policy.get("contract") == MANAGED_CONTRACT:
            obj.setdefault("governance", {})["review_policy"] = deepcopy(policy)
        else:
            obj.setdefault("metadata", {})["review_policy"] = deepcopy(policy)
        mark_four_eyes_on_object(obj)
        stamp_canonical_hashes(obj)


def archived_required(policy: dict[str, Any]) -> set[str]:
    return {r["reviewer_id"] for r in policy["assignments"]
            if r.get("status") == "archived" and r["participation"] == "required"}


def validate_managed_policy(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {"contract", "revision", "primary", "assignments", "review_basis", "minimum_required"}:
        raise ValueError("invalid_managed_review_policy")
    base = {k: deepcopy(value[k]) for k in ("revision", "primary", "assignments")}
    base["contract"] = CONTRACT
    for row in base["assignments"]:
        if row.get("status") not in {"active", "archived"}:
            raise ValueError("invalid_review_assignment_status")
        row.pop("status")
    validate_policy(base)
    basis = value["review_basis"]
    if basis is not None:
        if not isinstance(basis, dict) or basis.get("contract") != CONTRACT:
            raise ValueError("invalid_review_basis")
        validate_policy(basis)
    if type(value["minimum_required"]) is not int or value["minimum_required"] < 1:
        raise ValueError("invalid_review_requirement_floor")
    if len(required_reviewers(value)) < value["minimum_required"]:
        raise ValueError("review_requirement_floor_missing")
    return deepcopy(value)
