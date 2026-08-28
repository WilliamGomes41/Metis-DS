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
        and is_closed_confirmed_type(confirmed_object_type)
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
    hash_now = (obj.get("provenance") or {}).get("canonical_object_hash")
    return (
        binding.get("object_id") == obj.get("object_id")
        and binding.get("object_version") == obj.get("object_version")
        and binding.get("canonical_object_hash") == hash_now
        and binding.get("confirmed_object_type") == obj.get("confirmed_object_type")
        and is_closed_confirmed_type(binding.get("confirmed_object_type"))
    )


def invalidate_for_object(bindings: list[dict[str, Any]], object_id: str) -> list[dict[str, Any]]:
    out = []
    for row in bindings:
        item = dict(row)
        if item.get("object_id") == object_id:
            item["valid"] = False
        out.append(item)
    return out
