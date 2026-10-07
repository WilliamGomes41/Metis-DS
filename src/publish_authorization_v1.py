"""Publish authorization is the object tuple, not an envelope tick.

Minimum binding:
object_id + object_version + canonical_object_hash + confirmed_object_type
+ reviewer + decision

A changed hash, version or confirmed type MUST invalidate a prior authorization.
publish() remains G2-BLOCKED until a real immutable locator exists.
"""
from __future__ import annotations

from typing import Any

from src.object_taxonomy_v1 import is_closed_confirmed_type
from src.beslisboom_path_v1 import is_closed_boom_type


def tuple_record(
    *,
    object_id: str,
    object_version: str,
    canonical_object_hash: str,
    confirmed_object_type: str | None,
    reviewer: str,
    reviewer_id: str,
    decision: str,
) -> dict[str, Any]:
    valid = bool(
        object_id
        and object_version
        and canonical_object_hash
        and (is_closed_confirmed_type(confirmed_object_type) or is_closed_boom_type(confirmed_object_type))
        and reviewer
        and reviewer_id
        and decision
    )
    return {
        "object_id": object_id,
        "object_version": object_version,
        "canonical_object_hash": canonical_object_hash,
        "confirmed_object_type": confirmed_object_type,
        "reviewer": reviewer,
        "reviewer_id": reviewer_id,
        "decision": decision,
        "valid": valid,
    }


def still_matches(binding: dict[str, Any], obj: dict[str, Any]) -> bool:
    if not binding.get("valid"):
        return False
    from src.integrity_kernel import exact_review_snapshot_hash
    hash_now = exact_review_snapshot_hash(obj)
    return (
        binding.get("object_id") == obj.get("object_id")
        and binding.get("object_version") == obj.get("object_version")
        and binding.get("canonical_object_hash") == hash_now
        and binding.get("confirmed_object_type") == obj.get("confirmed_object_type")
        and (is_closed_confirmed_type(binding.get("confirmed_object_type")) or is_closed_boom_type(binding.get("confirmed_object_type")))
    )


def invalidate_for_object(bindings: list[dict[str, Any]], object_id: str) -> list[dict[str, Any]]:
    out = []
    for row in bindings:
        item = dict(row)
        if item.get("object_id") == object_id:
            item["valid"] = False
        out.append(item)
    return out


def record_authorization(bindings: list[dict[str, Any]], binding: dict[str, Any]) -> list[dict[str, Any]]:
    """One current authorization per exact approval tuple; events retain history.

    Only an authorized, successful review command calls this operation. A fresh
    command may renew the validity of an identical withdrawn authorization.
    Merely reassigning a reviewer never calls it. Distinct reviewed tuples stay
    in the existing store, and the command records every decision in the ledger.
    """
    fields = ("object_id", "object_version", "canonical_object_hash", "reviewer_id", "decision")
    key = tuple(binding.get(field) for field in fields)
    rows = [dict(row) for row in bindings]
    for row in rows:
        if tuple(row.get(field) for field in fields) == key:
            if row.get("confirmed_object_type") != binding.get("confirmed_object_type"):
                raise ValueError("review_binding_tuple_conflict")
            row["valid"] = bool(binding.get("valid"))
            return rows
    rows.append(dict(binding))
    return rows
