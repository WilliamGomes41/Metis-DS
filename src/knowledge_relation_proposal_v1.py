"""D4.2 source-bound KnowledgeRelation proposal policy.

This module validates proposal/admission semantics around the D4.1
KnowledgeRelation value object. It does not confirm relations, mutate review
state, or serve relation semantics.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.knowledge_relations_v1 import (
    PROPOSED_FIELD,
    SEMANTIC_RELATION_TYPES,
    knowledge_relation_errors,
    proposed_knowledge_relations_of,
    validate_knowledge_relation_set,
)


RELATION_EVIDENCE_VERSION = "knowledge-relation-evidence-v1"
PROPOSABLE_RELATION_TYPES = frozenset(SEMANTIC_RELATION_TYPES)
SUBSTANTIVE_TYPES = frozenset(
    {"definition", "explanation", "condition", "exception", "recommendation"}
)

_TARGET_TYPE_RULES: dict[str, frozenset[str]] = {
    "applies_if": frozenset({"condition"}),
    "except_if": frozenset({"exception"}),
    "defines": frozenset({"definition"}),
    "explains": frozenset({"explanation"}),
    "supported_by": SUBSTANTIVE_TYPES,
    "supersedes": SUBSTANTIVE_TYPES,
}


def relation_endpoint_compatible(
    relation_type: str,
    *,
    source_type: str,
    target_type: str,
) -> bool:
    """Return whether one semantic relation is compatible with endpoint roles.

    D4.2 intentionally validates semantic role, not editorial proximity.
    Structural parent/child relations stay outside this proposal slice.
    """

    relation = str(relation_type or "").strip()
    source = str(source_type or "").strip()
    target = str(target_type or "").strip()
    if relation not in PROPOSABLE_RELATION_TYPES:
        return False
    if source not in SUBSTANTIVE_TYPES:
        return False
    allowed_targets = _TARGET_TYPE_RULES.get(relation)
    if not allowed_targets or target not in allowed_targets:
        return False
    if relation == "supersedes" and source != target:
        return False
    return True


def _span_is_source_bound(span: Any) -> bool:
    if not isinstance(span, dict):
        return False
    if set(span) != {"block_id", "start", "end", "source_fragment_ids"}:
        return False
    block_id = str(span.get("block_id") or "").strip()
    start = span.get("start")
    end = span.get("end")
    fragment_ids = span.get("source_fragment_ids")
    return (
        bool(block_id)
        and isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and not isinstance(end, bool)
        and start >= 0
        and end > start
        and isinstance(fragment_ids, list)
        and bool(fragment_ids)
        and all(str(value or "").strip() for value in fragment_ids)
    )


def _evidence_row_is_source_bound(
    evidence: Any,
    *,
    relation: dict[str, Any],
) -> bool:
    if not isinstance(evidence, dict):
        return False
    required = {
        "relation_id",
        "relation_type",
        "target_object_id",
        "target_object_version",
        "source_spans",
        "target_spans",
        "evidence_spans",
    }
    if set(evidence) != required:
        return False
    if str(evidence.get("relation_id") or "") != str(relation.get("relation_id") or ""):
        return False
    if str(evidence.get("relation_type") or "") != str(relation.get("relation_type") or ""):
        return False
    if str(evidence.get("target_object_id") or "") != str(relation.get("target_object_id") or ""):
        return False
    if str(evidence.get("target_object_version") or "") != str(
        relation.get("target_object_version") or ""
    ):
        return False
    for field in ("source_spans", "target_spans", "evidence_spans"):
        spans = evidence.get(field)
        if not isinstance(spans, list) or not spans:
            return False
        if not all(_span_is_source_bound(span) for span in spans):
            return False
    return True


def relation_evidence_map(obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    raw = metadata.get("knowledge_relation_evidence")
    if not isinstance(raw, dict):
        return {}
    if raw.get("version") != RELATION_EVIDENCE_VERSION:
        return {}
    rows = raw.get("relations")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        relation_id = str(row.get("relation_id") or "").strip()
        if relation_id and relation_id not in out:
            out[relation_id] = row
    return out


def relation_proposal_admission_codes(
    obj: dict[str, Any],
    *,
    objects: Iterable[dict[str, Any]],
) -> list[str]:
    """Return fail-closed Admission codes for D4.2 new-format proposals."""

    if PROPOSED_FIELD not in obj:
        return []

    relations = proposed_knowledge_relations_of(obj)
    source_id = str(obj.get("object_id") or "")
    source_version = str(obj.get("object_version") or "")
    errors = validate_knowledge_relation_set(
        relations,
        source_object_id=source_id,
        source_object_version=source_version,
    )
    object_errors = knowledge_relation_errors(obj)

    codes: list[str] = []
    if errors or object_errors:
        codes.append("relation_proposal_invalid")
        joined = "|".join(errors + object_errors)
        if "knowledge_relation_type_invalid" in joined:
            codes.append("relation_type_invalid")
        if "knowledge_relation_target_object_version_missing" in joined:
            codes.append("relation_target_version_missing")
        if "knowledge_relation_self_relation" in joined:
            codes.append("relation_self_reference")
        if "legacy_authority_conflict" in joined:
            codes.append("relation_legacy_mirror_conflict")

    by_id = {
        str(row.get("object_id") or ""): row
        for row in objects
        if str(row.get("object_id") or "")
    }
    evidence_by_id = relation_evidence_map(obj)
    source_type = str(
        obj.get("proposed_object_type")
        or obj.get("confirmed_object_type")
        or obj.get("object_type")
        or ""
    )

    for relation in relations:
        relation_id = str(relation.get("relation_id") or "")
        target_id = str(relation.get("target_object_id") or "")
        target_version = str(relation.get("target_object_version") or "")
        target = by_id.get(target_id)
        if target is None:
            codes.append("relation_target_missing")
            continue
        live_target_version = str(target.get("object_version") or "")
        if not target_version:
            codes.append("relation_target_version_missing")
        elif live_target_version != target_version:
            codes.append("relation_target_version_mismatch")

        target_type = str(
            target.get("proposed_object_type")
            or target.get("confirmed_object_type")
            or target.get("object_type")
            or ""
        )
        if not relation_endpoint_compatible(
            str(relation.get("relation_type") or ""),
            source_type=source_type,
            target_type=target_type,
        ):
            codes.append("relation_endpoint_type_invalid")

        evidence = evidence_by_id.get(relation_id)
        if evidence is None:
            codes.append("relation_evidence_missing")
        elif not _evidence_row_is_source_bound(evidence, relation=relation):
            codes.append("relation_evidence_not_source_bound")

    unique: list[str] = []
    for code in codes:
        if code not in unique:
            unique.append(code)
    return unique
