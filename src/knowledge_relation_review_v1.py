"""D4.3 human confirmation policy for version-bound KnowledgeRelations.

Pure domain helpers only. This module validates the reviewer-selected semantic
relation set against the persisted D4.2 proposal/current confirmed set and
builds the D4.1 confirmed value objects for a caller-supplied final source
object version.

No persistence, UI, review binding, or serving behavior lives here.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from src.knowledge_relation_proposal_v1 import relation_endpoint_compatible
from src.knowledge_relations_v1 import (
    CONFIRMED_FIELD,
    PROPOSED_FIELD,
    SEMANTIC_RELATION_TYPES,
    STRUCTURAL_RELATION_TYPES,
    build_knowledge_relation,
    canonicalize_knowledge_relation_set,
    confirmed_knowledge_relations_of,
    proposed_knowledge_relations_of,
    validate_knowledge_relation_set,
)


RELATION_REVIEW_VERSION = "knowledge-relation-review-v1"


def semantic_relation_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("relation_type") or "").strip(),
        str(row.get("target_object_id") or "").strip(),
        str(row.get("target_object_version") or "").strip(),
    )


def relation_choice_value(row: dict[str, Any]) -> str:
    relation_type, target_id, target_version = semantic_relation_key(row)
    return f"{relation_type}:{target_id}:{target_version}"


def parse_relation_choice(value: str) -> tuple[str, str, str]:
    parts = str(value or "").split(":", 2)
    if len(parts) != 3 or not all(part.strip() for part in parts):
        raise ValueError("knowledge_relation_choice_invalid")
    relation_type, target_id, target_version = (part.strip() for part in parts)
    if relation_type not in SEMANTIC_RELATION_TYPES:
        raise ValueError("knowledge_relation_choice_invalid")
    return relation_type, target_id, target_version


def _object_type(obj: dict[str, Any]) -> str:
    return str(
        obj.get("confirmed_object_type")
        or obj.get("proposed_object_type")
        or obj.get("object_type")
        or ""
    ).strip()


def semantic_proposed_relations(obj: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        deepcopy(row)
        for row in proposed_knowledge_relations_of(obj)
        if str(row.get("relation_type") or "") in SEMANTIC_RELATION_TYPES
    ]


def semantic_confirmed_relations(obj: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        deepcopy(row)
        for row in confirmed_knowledge_relations_of(obj)
        if str(row.get("relation_type") or "") in SEMANTIC_RELATION_TYPES
    ]


def has_semantic_relation_review(obj: dict[str, Any]) -> bool:
    return bool(semantic_proposed_relations(obj) or semantic_confirmed_relations(obj))


def plan_semantic_relation_review(
    obj: dict[str, Any],
    *,
    objects: Iterable[dict[str, Any]],
    selected_choices: Iterable[str],
    source_type: str,
) -> dict[str, Any]:
    """Validate one reviewer selection against persisted relation authority.

    Proposal state takes precedence as the review basis. When no proposal is
    present, an existing confirmed semantic set is the basis so a later human
    re-review can remove one or more edges deliberately.
    """

    source_id = str(obj.get("object_id") or "").strip()
    source_version = str(obj.get("object_version") or "").strip()
    proposed = semantic_proposed_relations(obj)
    confirmed = semantic_confirmed_relations(obj)
    basis = proposed if proposed else confirmed
    basis_kind = "proposal" if proposed else "confirmed"

    if proposed:
        errors = validate_knowledge_relation_set(
            proposed_knowledge_relations_of(obj),
            source_object_id=source_id,
            source_object_version=source_version,
        )
        if errors:
            raise ValueError("knowledge_relation_source_version_stale")

    parsed: list[tuple[str, str, str]] = []
    for raw in selected_choices:
        key = parse_relation_choice(raw)
        if key in parsed:
            raise ValueError("knowledge_relation_choice_duplicate")
        parsed.append(key)

    allowed = {semantic_relation_key(row): row for row in basis}
    for key in parsed:
        if key not in allowed:
            raise ValueError("knowledge_relation_choice_not_available")

    by_id = {
        str(row.get("object_id") or ""): row
        for row in objects
        if str(row.get("object_id") or "").strip()
    }
    effective_source_type = str(source_type or _object_type(obj)).strip()
    selected_rows: list[dict[str, Any]] = []
    for key in parsed:
        relation_type, target_id, target_version = key
        target = by_id.get(target_id)
        if target is None:
            raise ValueError("knowledge_relation_target_missing")
        if str(target.get("object_version") or "").strip() != target_version:
            raise ValueError("knowledge_relation_target_stale")
        if not relation_endpoint_compatible(
            relation_type,
            source_type=effective_source_type,
            target_type=_object_type(target),
        ):
            raise ValueError("knowledge_relation_endpoint_type_invalid")
        selected_rows.append(deepcopy(allowed[key]))

    current_confirmed_keys = {
        semantic_relation_key(row)
        for row in confirmed
    }
    selected_keys = set(parsed)
    state_change_required = (
        PROPOSED_FIELD in obj
        or CONFIRMED_FIELD not in obj
        or selected_keys != current_confirmed_keys
    )

    proposal_ids = [
        str(row.get("relation_id") or "")
        for row in proposed
        if str(row.get("relation_id") or "")
    ]
    selected_proposal_ids = [
        str(allowed[key].get("relation_id") or "")
        for key in parsed
        if basis_kind == "proposal" and str(allowed[key].get("relation_id") or "")
    ]

    return {
        "version": RELATION_REVIEW_VERSION,
        "basis": basis_kind,
        "source_object_id": source_id,
        "source_object_version": source_version,
        "source_type": effective_source_type,
        "selected": [
            {
                "relation_type": relation_type,
                "target_object_id": target_id,
                "target_object_version": target_version,
            }
            for relation_type, target_id, target_version in parsed
        ],
        "proposal_relation_ids": proposal_ids,
        "selected_proposal_relation_ids": selected_proposal_ids,
        "rejected_proposal_relation_ids": [
            relation_id
            for relation_id in proposal_ids
            if relation_id not in selected_proposal_ids
        ],
        "state_change_required": state_change_required,
    }


def build_confirmed_relation_set(
    plan: dict[str, Any],
    *,
    final_source_version: str,
    structural_relations: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Build the full confirmed relation set against one final source version."""

    source_id = str(plan.get("source_object_id") or "").strip()
    source_version = str(final_source_version or "").strip()
    rows: list[dict[str, Any]] = []

    for selected in plan.get("selected") or []:
        rows.append(
            build_knowledge_relation(
                source_object_id=source_id,
                source_object_version=source_version,
                relation_type=str(selected.get("relation_type") or ""),
                target_object_id=str(selected.get("target_object_id") or ""),
                target_object_version=str(selected.get("target_object_version") or ""),
            )
        )

    for structural in structural_relations:
        relation_type = str(structural.get("relation_type") or "").strip()
        if relation_type not in STRUCTURAL_RELATION_TYPES:
            continue
        rows.append(
            build_knowledge_relation(
                source_object_id=source_id,
                source_object_version=source_version,
                relation_type=relation_type,
                target_object_id=str(structural.get("target_object_id") or ""),
                target_object_version=str(structural.get("target_object_version") or ""),
            )
        )

    return canonicalize_knowledge_relation_set(
        rows,
        source_object_id=source_id,
        source_object_version=source_version,
    )


def legacy_confirmed_mirror(
    relations: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "relation_type": str(row.get("relation_type") or ""),
            "target_object_id": str(row.get("target_object_id") or ""),
            "target_object_version": str(row.get("target_object_version") or ""),
            "confirmed": True,
        }
        for row in relations
    ]


def relation_review_evidence(
    plan: dict[str, Any],
    *,
    confirmed_relations: Iterable[dict[str, Any]],
    reviewer_id: str,
    reviewer_username: str,
    reviewed_at: str,
    source_version_after: str,
) -> dict[str, Any]:
    return {
        "version": RELATION_REVIEW_VERSION,
        "basis": str(plan.get("basis") or ""),
        "reviewer_id": str(reviewer_id or ""),
        "reviewer": str(reviewer_username or ""),
        "reviewed_at": str(reviewed_at or ""),
        "source_object_version_before": str(plan.get("source_object_version") or ""),
        "source_object_version_after": str(source_version_after or ""),
        "proposal_relation_ids": list(plan.get("proposal_relation_ids") or []),
        "selected_proposal_relation_ids": list(
            plan.get("selected_proposal_relation_ids") or []
        ),
        "rejected_proposal_relation_ids": list(
            plan.get("rejected_proposal_relation_ids") or []
        ),
        "confirmed_relation_ids": [
            str(row.get("relation_id") or "")
            for row in confirmed_relations
            if str(row.get("relation_id") or "")
        ],
    }
