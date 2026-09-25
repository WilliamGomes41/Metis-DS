"""D5.1 read-only ReviewDuty domain projection.

A ReviewDuty is not persisted. It is derived from the current KnowledgeObject
state and existing review governance. Durable review authority remains the
exact object version/hash review binding and second-review state.

This module deliberately performs no writes and creates no task store.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, admission_of
from src.four_eyes_v1 import requires_four_eyes
from src.knowledge_relations_v1 import (
    confirmed_knowledge_relations_of,
    proposed_knowledge_relations_of,
)


FIRST_REVIEW = "first_review"
SECOND_REVIEW = "second_review"

LANE_STRUCTURE = "structure"
LANE_CONTEXTUAL = "contextual"
LANE_BATCH = "batch"

_FINAL_FIRST_REVIEW = frozenset({"approved", "rejected", "superseded"})
_BATCH_TYPES = frozenset({"definition", "explanation"})
_CONTEXTUAL_TYPES = frozenset(
    {"recommendation", "condition", "exception", "node", "outcome"}
)


def authoritative_review_type(obj: dict[str, Any]) -> str:
    confirmed = str(obj.get("confirmed_object_type") or "").strip()
    if confirmed:
        return confirmed
    stored = str(obj.get("object_type") or "").strip()
    if stored and stored != "unclassified":
        return stored
    return str(obj.get("proposed_object_type") or "").strip()


def _second_review(obj: dict[str, Any]) -> dict[str, Any]:
    governance = obj.get("governance")
    if not isinstance(governance, dict):
        return {}
    value = governance.get("second_review")
    return value if isinstance(value, dict) else {}


def second_review_open(obj: dict[str, Any]) -> bool:
    governance = obj.get("governance")
    if not isinstance(governance, dict):
        return False
    if str(governance.get("validation_status") or "") != "approved":
        return False
    second = _second_review(obj)
    if not bool(second.get("required")):
        return False
    return str(second.get("status") or "") == "pending"


def _relation_review_required(obj: dict[str, Any]) -> bool:
    return bool(
        proposed_knowledge_relations_of(obj)
        or confirmed_knowledge_relations_of(obj)
    )


def _section_path(obj: dict[str, Any]) -> tuple[str, ...]:
    admission = admission_of(obj)
    raw = admission.get("section_path")
    if not raw:
        structure = obj.get("structure")
        raw = structure.get("section_path") if isinstance(structure, dict) else []
    return tuple(str(part).strip() for part in raw or [] if str(part).strip())


def first_review_open(obj: dict[str, Any], *, review_path: str) -> bool:
    if str(obj.get("object_type") or "") == "document":
        return False
    governance = obj.get("governance")
    status = (
        str(governance.get("validation_status") or "")
        if isinstance(governance, dict)
        else ""
    )
    if status in _FINAL_FIRST_REVIEW or status == "revise":
        return False
    if review_path != "boom" and admission_of(obj).get("gate_result") == GATE_BLOCKED:
        return False
    return True


def review_duty_lane(
    obj: dict[str, Any],
    *,
    review_path: str,
    stage: str,
) -> str:
    obj_type = authoritative_review_type(obj)

    if stage == SECOND_REVIEW:
        return LANE_CONTEXTUAL

    if (review_path == "boom" and obj_type == "path") or (
        review_path != "boom" and obj_type == "heading"
    ):
        return LANE_STRUCTURE

    if (
        obj_type in _CONTEXTUAL_TYPES
        or requires_four_eyes(
            obj,
            confirmed_type=str(obj.get("confirmed_object_type") or "") or None,
        )
        or _relation_review_required(obj)
    ):
        return LANE_CONTEXTUAL

    uncertainty = obj.get("uncertainty")
    risk = obj.get("risk")
    if (
        review_path != "boom"
        and obj_type in _BATCH_TYPES
        and admission_of(obj).get("gate_result") == GATE_ALLOWED
        and _section_path(obj)
        and not (
            isinstance(uncertainty, dict)
            and bool(uncertainty.get("has_uncertainty"))
        )
        and not (
            isinstance(risk, dict)
            and (
                str(risk.get("level") or "") == "high"
                or bool(risk.get("requires_second_review"))
            )
        )
    ):
        return LANE_BATCH

    return LANE_CONTEXTUAL


def review_duty_for(
    obj: dict[str, Any],
    *,
    review_path: str,
) -> dict[str, Any] | None:
    """Project the one currently open human review duty for this object.

    One object can have at most one open duty at a time: first review takes
    precedence until approved; then an independent second review may become
    open.
    """

    if first_review_open(obj, review_path=review_path):
        stage = FIRST_REVIEW
    elif second_review_open(obj):
        stage = SECOND_REVIEW
    else:
        return None

    provenance = obj.get("provenance")
    canonical_hash = (
        str(provenance.get("canonical_object_hash") or "")
        if isinstance(provenance, dict)
        else ""
    )
    return {
        "object_id": str(obj.get("object_id") or ""),
        "object_version": str(obj.get("object_version") or ""),
        "canonical_object_hash": canonical_hash,
        "stage": stage,
        "lane": review_duty_lane(obj, review_path=review_path, stage=stage),
        "object_type": authoritative_review_type(obj),
    }


def review_duties(
    objects: Iterable[dict[str, Any]],
    *,
    review_path: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for obj in objects:
        duty = review_duty_for(obj, review_path=review_path)
        if duty is None:
            continue
        key = (
            duty["object_id"],
            duty["object_version"],
            duty["stage"],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(duty)
    return out


def review_duty_counts(
    objects: Iterable[dict[str, Any]],
    *,
    review_path: str,
) -> dict[str, int]:
    duties = review_duties(objects, review_path=review_path)
    return {
        "review_duties": len(duties),
        "first_review_duties": sum(
            duty["stage"] == FIRST_REVIEW for duty in duties
        ),
        "second_review_duties": sum(
            duty["stage"] == SECOND_REVIEW for duty in duties
        ),
        "structure_review_duties": sum(
            duty["lane"] == LANE_STRUCTURE for duty in duties
        ),
        "contextual_review_duties": sum(
            duty["lane"] == LANE_CONTEXTUAL for duty in duties
        ),
        "batch_review_duties": sum(
            duty["lane"] == LANE_BATCH for duty in duties
        ),
    }


def repair_duty_count(
    objects: Iterable[dict[str, Any]],
    *,
    review_path: str,
) -> int:
    if review_path == "boom":
        return 0
    return sum(
        str(obj.get("object_type") or "") != "document"
        and admission_of(obj).get("gate_result") == GATE_BLOCKED
        for obj in objects
    )
