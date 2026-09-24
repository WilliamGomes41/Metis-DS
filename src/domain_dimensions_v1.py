"""Read-only domain projections for Review.

Review currently consumes several durable authorities whose meanings are
orthogonal. This module names those meanings without creating a new source of
truth:

- source structure;
- knowledge-candidate status;
- knowledge relations;
- human review decision/evidence;
- processing issues.

The functions in this module are pure projections. They MUST NOT persist
state, reinterpret publication authority, or turn review batching into a
semantic relation.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.admission_gate_v1 import GATE_BLOCKED, admission_of, is_inhoudelijk_candidate
from src.object_taxonomy_v1 import DEFAULT_OBJECT_TYPE, section_role_for_path
from src.passage_register_v1 import passage_register_of
from src.serving_relations_v1 import confirmed_relations, proposed_relations


_HUMAN_REVIEW_STATUSES = frozenset({"approved", "rejected", "revise"})


def _section_path(obj: dict[str, Any]) -> list[str]:
    structure = obj.get("structure") if isinstance(obj.get("structure"), dict) else {}
    path = [
        str(part).strip()
        for part in (structure.get("section_path") or [])
        if str(part).strip()
    ]
    if path:
        return path
    admission = admission_of(obj)
    return [
        str(part).strip()
        for part in (admission.get("section_path") or [])
        if str(part).strip()
    ]


def source_structure_dimension(obj: dict[str, Any]) -> dict[str, Any]:
    """Project source structure without assigning knowledge value."""

    object_type = str(obj.get("object_type") or "")
    proposed_type = str(obj.get("proposed_object_type") or "")
    if object_type == "document":
        kind = "document"
    elif object_type == "heading" or proposed_type == "heading":
        kind = "heading"
    else:
        kind = "passage"

    section_path = _section_path(obj)
    admission = admission_of(obj)
    section_role = str(admission.get("section_role") or "").strip()
    if not section_role:
        section_role = section_role_for_path(section_path)

    return {
        "kind": kind,
        "section_path": section_path,
        "section_role": section_role,
    }


def knowledge_candidate_dimension(obj: dict[str, Any]) -> dict[str, Any]:
    """Project candidate meaning independently from processing success."""

    stored_type = str(obj.get("object_type") or "")
    return {
        "is_candidate": bool(is_inhoudelijk_candidate(obj)),
        "proposed_type": str(
            obj.get("proposed_object_type")
            or admission_of(obj).get("proposed_type")
            or ""
        ),
        "confirmed_type": str(obj.get("confirmed_object_type") or ""),
        "stored_type": (
            stored_type
            if stored_type not in {"", DEFAULT_OBJECT_TYPE, "document", "heading"}
            else ""
        ),
    }


def knowledge_relations_dimension(obj: dict[str, Any]) -> dict[str, Any]:
    """Project relation edges; review batching is deliberately absent."""

    return {
        "proposed": [dict(row) for row in proposed_relations(obj)],
        "confirmed": [dict(row) for row in confirmed_relations(obj)],
    }


def review_decision_dimension(obj: dict[str, Any]) -> dict[str, Any]:
    """Project only evidence that a human review decision has actually occurred.

    Extract-created passage-register rows such as not_yet_assessed are coverage
    state, not curator decisions. A terminal/revise governance state is also
    review evidence for older records whose register source was not stamped as
    review.
    """

    register = passage_register_of(obj)
    register_source = str(register.get("source") or "")
    validation_status = str(
        (obj.get("governance") or {}).get("validation_status") or ""
    )
    has_human_decision = (
        register_source == "review" or validation_status in _HUMAN_REVIEW_STATUSES
    )

    return {
        "has_human_decision": has_human_decision,
        "validation_status": validation_status if has_human_decision else "",
        "passage_disposition": (
            str(register.get("status") or "") if register_source == "review" else ""
        ),
        "suitability": (
            str(register.get("suitability") or "") if register_source == "review" else ""
        ),
    }


def processing_issue_dimension(obj: dict[str, Any]) -> dict[str, Any]:
    """Project machine/pipeline blocking separately from human review."""

    admission = admission_of(obj)
    gate_result = str(admission.get("gate_result") or "")
    blocked = gate_result == GATE_BLOCKED
    return {
        "has_issue": blocked,
        "gate_result": gate_result,
        "reason_codes": (
            [
                str(code)
                for code in (admission.get("reason_codes") or [])
                if str(code).strip()
            ]
            if blocked
            else []
        ),
    }


def project_review_domain_dimensions(obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the five orthogonal Review dimensions for one current object."""

    return {
        "source_structure": source_structure_dimension(obj),
        "knowledge_candidate": knowledge_candidate_dimension(obj),
        "knowledge_relations": knowledge_relations_dimension(obj),
        "review_decision": review_decision_dimension(obj),
        "processing_issue": processing_issue_dimension(obj),
    }


def processing_issue_objects(objects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return objects blocked by the existing admission/processing authority."""

    return [
        obj
        for obj in objects
        if processing_issue_dimension(obj)["has_issue"]
    ]
