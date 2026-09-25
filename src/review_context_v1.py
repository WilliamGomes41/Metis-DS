"""D5.2 relation-aware, read-only ReviewContext projection.

ReviewContext is presentation context around one current D5.1 ReviewDuty.
It is not review authority, does not mutate KnowledgeObjects, and does not
create a task, graph, relation, audit record, or lifecycle state.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from src.admission_gate_v1 import GATE_ALLOWED, admission_of
from src.knowledge_relation_proposal_v1 import relation_evidence_map
from src.knowledge_relations_v1 import (
    SEMANTIC_RELATION_TYPES,
    confirmed_knowledge_relations_of,
    proposed_knowledge_relations_of,
)
from src.review_duty_v1 import (
    FIRST_REVIEW,
    review_duty_for,
)


AUTHORITY_CONFIRMED = "confirmed"
AUTHORITY_PROPOSED = "proposed"

DIRECTION_OUTGOING = "outgoing"
DIRECTION_INCOMING = "incoming"

RESOLUTION_CURRENT = "current"
RESOLUTION_VERSION_MISMATCH = "version_mismatch"
RESOLUTION_MISSING = "missing"


def _semantic_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("relation_type") or "").strip(),
        str(row.get("target_object_id") or "").strip(),
        str(row.get("target_object_version") or "").strip(),
    )


def _semantic_relations(
    obj: dict[str, Any],
    *,
    include_proposed: bool,
) -> list[tuple[str, dict[str, Any]]]:
    confirmed = [
        deepcopy(row)
        for row in confirmed_knowledge_relations_of(obj)
        if str(row.get("relation_type") or "") in SEMANTIC_RELATION_TYPES
    ]
    out: list[tuple[str, dict[str, Any]]] = [
        (AUTHORITY_CONFIRMED, row)
        for row in confirmed
    ]

    if not include_proposed:
        return out
    if admission_of(obj).get("gate_result") != GATE_ALLOWED:
        return out

    confirmed_keys = {_semantic_key(row) for row in confirmed}
    for row in proposed_knowledge_relations_of(obj):
        if str(row.get("relation_type") or "") not in SEMANTIC_RELATION_TYPES:
            continue
        if _semantic_key(row) in confirmed_keys:
            continue
        out.append((AUTHORITY_PROPOSED, deepcopy(row)))
    return out


def _current_by_id(
    objects: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(obj.get("object_id") or ""): obj
        for obj in objects
        if str(obj.get("object_id") or "").strip()
    }


def _endpoint_projection(
    *,
    object_id: str,
    expected_version: str,
    current_by_id: dict[str, dict[str, Any]],
    review_path: str,
) -> dict[str, Any]:
    current = current_by_id.get(object_id)
    if current is None:
        return {
            "object_id": object_id,
            "expected_version": expected_version,
            "current_version": "",
            "resolution": RESOLUTION_MISSING,
            "object_type": "",
            "text": "",
            "review_duty": None,
        }

    current_version = str(current.get("object_version") or "")
    resolution = (
        RESOLUTION_CURRENT
        if current_version == expected_version
        else RESOLUTION_VERSION_MISMATCH
    )
    return {
        "object_id": object_id,
        "expected_version": expected_version,
        "current_version": current_version,
        "resolution": resolution,
        "object_type": str(
            current.get("confirmed_object_type")
            or current.get("proposed_object_type")
            or current.get("object_type")
            or ""
        ),
        "text": str((current.get("content") or {}).get("clean_text") or ""),
        "review_duty": review_duty_for(current, review_path=review_path),
    }


def _evidence_for(
    source: dict[str, Any],
    relation: dict[str, Any],
    *,
    authority: str,
) -> dict[str, Any] | None:
    evidence = relation_evidence_map(source)
    relation_id = str(relation.get("relation_id") or "")
    if authority == AUTHORITY_PROPOSED:
        row = evidence.get(relation_id)
        return deepcopy(row) if isinstance(row, dict) else None

    # Confirmed relation ids are rebuilt after human review because the source
    # version changes. Reuse source-bound proposal evidence by semantic edge.
    key = _semantic_key(relation)
    for row in evidence.values():
        if not isinstance(row, dict):
            continue
        row_key = (
            str(row.get("relation_type") or "").strip(),
            str(row.get("target_object_id") or "").strip(),
            str(row.get("target_object_version") or "").strip(),
        )
        if row_key == key:
            return deepcopy(row)
    return None


def _outgoing_links(
    focal: dict[str, Any],
    *,
    current_by_id: dict[str, dict[str, Any]],
    review_path: str,
    include_proposed: bool,
) -> list[dict[str, Any]]:
    source_id = str(focal.get("object_id") or "")
    source_version = str(focal.get("object_version") or "")
    out: list[dict[str, Any]] = []
    for authority, relation in _semantic_relations(
        focal,
        include_proposed=include_proposed,
    ):
        target_id = str(relation.get("target_object_id") or "")
        target_version = str(relation.get("target_object_version") or "")
        out.append(
            {
                "relation_id": str(relation.get("relation_id") or ""),
                "relation_type": str(relation.get("relation_type") or ""),
                "authority": authority,
                "direction": DIRECTION_OUTGOING,
                "source": _endpoint_projection(
                    object_id=source_id,
                    expected_version=source_version,
                    current_by_id=current_by_id,
                    review_path=review_path,
                ),
                "target": _endpoint_projection(
                    object_id=target_id,
                    expected_version=target_version,
                    current_by_id=current_by_id,
                    review_path=review_path,
                ),
                "evidence": _evidence_for(
                    focal,
                    relation,
                    authority=authority,
                ),
            }
        )
    return out


def _incoming_links(
    focal: dict[str, Any],
    *,
    objects: Iterable[dict[str, Any]],
    current_by_id: dict[str, dict[str, Any]],
    review_path: str,
    include_proposed: bool,
) -> list[dict[str, Any]]:
    focal_id = str(focal.get("object_id") or "")
    focal_version = str(focal.get("object_version") or "")
    out: list[dict[str, Any]] = []
    for source in objects:
        source_id = str(source.get("object_id") or "")
        if not source_id or source_id == focal_id:
            continue
        source_version = str(source.get("object_version") or "")
        for authority, relation in _semantic_relations(
            source,
            include_proposed=include_proposed,
        ):
            if str(relation.get("target_object_id") or "") != focal_id:
                continue
            target_version = str(relation.get("target_object_version") or "")
            # Preserve stale incoming relations as explicit context issues too.
            if not target_version:
                continue
            out.append(
                {
                    "relation_id": str(relation.get("relation_id") or ""),
                    "relation_type": str(relation.get("relation_type") or ""),
                    "authority": authority,
                    "direction": DIRECTION_INCOMING,
                    "source": _endpoint_projection(
                        object_id=source_id,
                        expected_version=source_version,
                        current_by_id=current_by_id,
                        review_path=review_path,
                    ),
                    "target": _endpoint_projection(
                        object_id=focal_id,
                        expected_version=target_version,
                        current_by_id=current_by_id,
                        review_path=review_path,
                    ),
                    "evidence": _evidence_for(
                        source,
                        relation,
                        authority=authority,
                    ),
                    "focal_current_version": focal_version,
                }
            )
    return out


def _link_sort_key(link: dict[str, Any]) -> tuple[str, str, str, str, str]:
    related = (
        link["target"]
        if link.get("direction") == DIRECTION_OUTGOING
        else link["source"]
    )
    return (
        str(link.get("authority") or ""),
        str(link.get("direction") or ""),
        str(link.get("relation_type") or ""),
        str(related.get("object_id") or ""),
        str(related.get("expected_version") or ""),
    )


def review_context(
    focal: dict[str, Any],
    *,
    objects: Iterable[dict[str, Any]],
    review_path: str,
    stage: str | None = None,
) -> dict[str, Any]:
    """Project one-hop semantic context around a current focal ReviewDuty."""

    rows = list(objects)
    current_by_id = _current_by_id(rows)
    focal_id = str(focal.get("object_id") or "")
    focal_version = str(focal.get("object_version") or "")
    duty = review_duty_for(focal, review_path=review_path)
    effective_stage = str(stage or (duty or {}).get("stage") or FIRST_REVIEW)
    include_proposed = effective_stage == FIRST_REVIEW

    links = [
        *_outgoing_links(
            focal,
            current_by_id=current_by_id,
            review_path=review_path,
            include_proposed=include_proposed,
        ),
        *_incoming_links(
            focal,
            objects=rows,
            current_by_id=current_by_id,
            review_path=review_path,
            include_proposed=include_proposed,
        ),
    ]
    links.sort(key=_link_sort_key)

    issues: list[dict[str, Any]] = []
    for link in links:
        related = (
            link["target"]
            if link["direction"] == DIRECTION_OUTGOING
            else link["source"]
        )
        if related["resolution"] != RESOLUTION_CURRENT:
            issues.append(
                {
                    "relation_id": link["relation_id"],
                    "relation_type": link["relation_type"],
                    "direction": link["direction"],
                    "authority": link["authority"],
                    "related_object_id": related["object_id"],
                    "expected_version": related["expected_version"],
                    "current_version": related["current_version"],
                    "resolution": related["resolution"],
                }
            )

    return {
        "focal": {
            "object_id": focal_id,
            "object_version": focal_version,
            "review_duty": duty,
        },
        "stage": effective_stage,
        "links": links,
        "issues": issues,
    }
