"""Closed serving-law relations for Protocol v2.13.

Serving-law names win over schema v1.2 historical names. Unconfirmed
relations MUST NOT bind. Operators MUST NOT invent relation types.
"""
from __future__ import annotations

from typing import Any, Iterable

CLOSED_RELATION_TYPES = (
    "applies_if",
    "except_if",
    "defines",
    "explains",
    "supported_by",
    "supersedes",
    "parent",
    "child",
)
CLOSED_RELATION_SET = frozenset(CLOSED_RELATION_TYPES)
ADVICE_BOUND_RELATIONS = frozenset({"applies_if", "except_if"})
HISTORICAL_TO_SERVING = {
    "conditioned_by": "applies_if",
    "exception_to": "except_if",
    "supports": "supported_by",
    "child_of": "child",
    "superseded_by": "supersedes",
}
HISTORICAL_NON_SERVING_TYPES = frozenset(
    {
        "decision",
        "action",
        "score_rule",
        "table",
        "background",
        "patient_information",
        "document",
        "section",
        "out_of_scope",
        "supersession",
    }
)


def serving_relation_type(name: str | None) -> str | None:
    if not name:
        return None
    if name in CLOSED_RELATION_SET:
        return name
    mapped = HISTORICAL_TO_SERVING.get(name)
    if mapped in CLOSED_RELATION_SET:
        return mapped
    return None


def is_closed_relation_type(name: str | None) -> bool:
    return serving_relation_type(name) in CLOSED_RELATION_SET


def normalize_relation(row: dict[str, Any]) -> dict[str, Any] | None:
    served = serving_relation_type(row.get("relation_type"))
    target = str(row.get("target_object_id") or "").strip()
    if not served or not target:
        return None
    out = {
        "relation_type": served,
        "target_object_id": target,
        "confirmed": bool(row.get("confirmed")),
    }
    if row.get("target_object_version"):
        out["target_object_version"] = row["target_object_version"]
    return out


def proposed_relations(obj: dict[str, Any]) -> list[dict[str, Any]]:
    rows = obj.get("relations") or []
    out = []
    for row in rows:
        item = normalize_relation(row)
        if item:
            out.append(item)
    return out


def confirmed_relations(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only confirmed serving-law relations. Unconfirmed MUST NOT bind."""
    explicit = obj.get("confirmed_relations")
    if explicit is None and "metadata" in obj:
        explicit = (obj.get("metadata") or {}).get("confirmed_relations")
    source = explicit if explicit is not None else []
    out: list[dict[str, Any]] = []
    for row in source:
        item = normalize_relation(row)
        if item:
            item["confirmed"] = True
            out.append(item)
    if out:
        return out
    # A relation marked confirmed:true on the proposed list may bind.
    for row in proposed_relations(obj):
        raw = next(
            (
                item
                for item in (obj.get("relations") or [])
                if item.get("target_object_id") == row["target_object_id"]
                and serving_relation_type(item.get("relation_type")) == row["relation_type"]
            ),
            {},
        )
        if raw.get("confirmed") is True:
            row["confirmed"] = True
            out.append(row)
    return out


def binding_relations(obj: dict[str, Any]) -> list[dict[str, Any]]:
    return confirmed_relations(obj)


def relation_targets(obj: dict[str, Any], relation_type: str) -> list[str]:
    served = serving_relation_type(relation_type)
    return [
        row["target_object_id"]
        for row in binding_relations(obj)
        if row["relation_type"] == served
    ]


def applies_if_targets(obj: dict[str, Any]) -> list[str]:
    return relation_targets(obj, "applies_if")


def except_if_targets(obj: dict[str, Any]) -> list[str]:
    return relation_targets(obj, "except_if")


def confirm_relation_set(
    proposed: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in proposed:
        item = normalize_relation(row)
        if item is None:
            raise ValueError("unknown_relation_type")
        item["confirmed"] = True
        out.append(item)
    return out


def historical_type_must_not_serve(object_type: str | None) -> bool:
    return object_type in HISTORICAL_NON_SERVING_TYPES
