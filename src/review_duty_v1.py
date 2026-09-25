"""D5.1 read-only ReviewDuty domain projection.

A ReviewDuty is not persisted. It is derived from the current KnowledgeObject
state and existing review governance. Durable review authority remains the
exact object version/hash review binding and second-review state.

This module deliberately performs no writes and creates no task store.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, admission_of
from src.four_eyes_v1 import requires_four_eyes, reviewer_is_agent
from src.knowledge_relations_v1 import (
    confirmed_knowledge_relations_of,
    proposed_knowledge_relations_of,
)


FIRST_REVIEW = "first_review"
SECOND_REVIEW = "second_review"

LANE_STRUCTURE = "structure"
LANE_CONTEXTUAL = "contextual"
LANE_BATCH = "batch"

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


def exact_current_approver_ids(
    obj: dict[str, Any],
    bindings: Iterable[dict[str, Any]],
) -> tuple[str, ...]:
    """Unique human approvers whose binding still matches this exact tuple."""

    object_id = str(obj.get("object_id") or "")
    object_version = str(obj.get("object_version") or "")
    confirmed_type = str(obj.get("confirmed_object_type") or "")
    provenance = obj.get("provenance")
    canonical_hash = (
        str(provenance.get("canonical_object_hash") or "")
        if isinstance(provenance, dict)
        else ""
    )
    seen: set[str] = set()
    out: list[str] = []
    for row in bindings:
        if not row.get("valid") or str(row.get("decision") or "") != "approve":
            continue
        if reviewer_is_agent(row):
            continue
        reviewer_id = str(row.get("reviewer_id") or row.get("reviewer_account_id") or "")
        if not reviewer_id or reviewer_id in seen:
            continue
        if str(row.get("object_id") or "") != object_id:
            continue
        if str(row.get("object_version") or "") != object_version:
            continue
        if str(row.get("canonical_object_hash") or "") != canonical_hash:
            continue
        if str(row.get("confirmed_object_type") or "") != confirmed_type:
            continue
        seen.add(reviewer_id)
        out.append(reviewer_id)
    return tuple(out)


def _terminal_without_open_review(obj: dict[str, Any]) -> bool:
    governance = obj.get("governance")
    status = (
        str(governance.get("validation_status") or "")
        if isinstance(governance, dict)
        else ""
    )
    return status in {"rejected", "superseded", "revise"}


def review_stage(
    obj: dict[str, Any],
    *,
    review_path: str,
    bindings: Iterable[dict[str, Any]] | None = None,
) -> str | None:
    """Return the open review stage from current tuple approvals.

    Bindings are the durable approval authority. Governance remains useful
    metadata, but a stale/pending second-review flag cannot reopen a tuple that
    already has two independent current human approvals.
    """

    if str(obj.get("object_type") or "") == "document":
        return None
    if _terminal_without_open_review(obj):
        return None
    obj_type = authoritative_review_type(obj)
    gate = str(admission_of(obj).get("gate_result") or "")
    confirmed = str(obj.get("confirmed_object_type") or "").strip()
    # Headings are structural and have no Admission. A human-confirmed type
    # without a gate is also reviewable: the reviewer already classified it.
    # An explicit non-allowed gate stays out, including after confirmation.
    if (
        review_path != "boom"
        and obj_type != "heading"
        and gate != GATE_ALLOWED
        and not (confirmed and not gate)
    ):
        return None

    if bindings is None:
        governance = obj.get("governance")
        status = (
            str(governance.get("validation_status") or "")
            if isinstance(governance, dict)
            else ""
        )
        if status not in {"approved"}:
            return FIRST_REVIEW
        second = governance.get("second_review") if isinstance(governance, dict) else {}
        if (
            isinstance(second, dict)
            and bool(second.get("required"))
            and str(second.get("status") or "") == "pending"
        ):
            return SECOND_REVIEW
        return None

    approvers = exact_current_approver_ids(obj, bindings)
    four_eyes = requires_four_eyes(
        obj,
        confirmed_type=str(obj.get("confirmed_object_type") or "") or None,
    )
    if not approvers:
        return FIRST_REVIEW
    if four_eyes and len(approvers) == 1:
        return SECOND_REVIEW
    return None




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


def first_review_open(
    obj: dict[str, Any],
    *,
    review_path: str,
    bindings: Iterable[dict[str, Any]] | None = None,
) -> bool:
    return review_stage(
        obj,
        review_path=review_path,
        bindings=bindings,
    ) == FIRST_REVIEW


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
    bindings: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Project the one currently open human review duty for this object.

    One object can have at most one open duty at a time: first review takes
    precedence until approved; then an independent second review may become
    open.
    """

    stage = review_stage(
        obj,
        review_path=review_path,
        bindings=bindings,
    )
    if stage is None:
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
    bindings: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for obj in objects:
        duty = review_duty_for(
            obj,
            review_path=review_path,
            bindings=bindings,
        )
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
    bindings: Iterable[dict[str, Any]] | None = None,
) -> dict[str, int]:
    duties = review_duties(
        objects,
        review_path=review_path,
        bindings=bindings,
    )
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


def reviewer_route_for(
    obj: dict[str, Any],
    *,
    review_path: str,
    reviewer_id: str,
    bindings: Iterable[dict[str, Any]] = (),
) -> dict[str, Any] | None:
    """Actor-specific actionability over one current ReviewDuty."""

    duty = review_duty_for(
        obj,
        review_path=review_path,
        bindings=bindings,
    )
    if duty is None:
        return None

    approvers = exact_current_approver_ids(obj, bindings)
    already_approved = reviewer_id in set(approvers)
    stage = str(duty["stage"])
    actionable = not already_approved
    canonical_task = (
        "second_review"
        if stage == SECOND_REVIEW
        else str(duty["lane"])
    )
    return {
        **duty,
        "canonical_task": canonical_task,
        "actionable": actionable,
        "waiting_for_other_reviewer": stage == SECOND_REVIEW and not actionable,
        "current_approver_ids": list(approvers),
    }


def reviewer_route_counts(
    objects: Iterable[dict[str, Any]],
    *,
    review_path: str,
    reviewer_id: str,
    bindings: Iterable[dict[str, Any]] = (),
) -> dict[str, int]:
    routes = [
        route
        for obj in objects
        if (
            route := reviewer_route_for(
                obj,
                review_path=review_path,
                reviewer_id=reviewer_id,
                bindings=bindings,
            )
        ) is not None
    ]
    return {
        "actionable_review_duties": sum(bool(row["actionable"]) for row in routes),
        "waiting_for_reviewer_duties": sum(
            bool(row["waiting_for_other_reviewer"]) for row in routes
        ),
        "actionable_structure_duties": sum(
            bool(row["actionable"]) and row["canonical_task"] == "structure"
            for row in routes
        ),
        "actionable_contextual_duties": sum(
            bool(row["actionable"]) and row["canonical_task"] == "contextual"
            for row in routes
        ),
        "actionable_batch_duties": sum(
            bool(row["actionable"]) and row["canonical_task"] == "batch"
            for row in routes
        ),
        "actionable_second_review_duties": sum(
            bool(row["actionable"]) and row["canonical_task"] == "second_review"
            for row in routes
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
