"""Single content-review predicate for knowledge candidates.

Derived from the row. This module does not write lifecycle, kind, or review
authority onto the object: those fields sit inside the canonical hash.

Content review requires a semantic selection, exact source spans, and an
allowed admission gate. Deterministic prose, headings, source records, and
coverage remainders are not knowledge candidates.
"""
from __future__ import annotations

from typing import Any

from src.semantic_passage_v1 import SELECTION_ORIGIN_COVERAGE, SELECTION_ORIGIN_PROPOSAL

GATE_ALLOWED = "allowed"
GATE_BLOCKED = "blocked"
_UNKNOWN_SPAN = {"", "UNKNOWN"}


def _metadata(obj: dict[str, Any]) -> dict[str, Any]:
    metadata = obj.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _semantic(obj: dict[str, Any]) -> dict[str, Any] | None:
    semantic = _metadata(obj).get("semantic_passage")
    return semantic if isinstance(semantic, dict) else None


def _origin(obj: dict[str, Any]) -> str:
    semantic = _semantic(obj)
    if semantic is None:
        return ""
    return str(semantic.get("selection_origin") or "").strip()


def _gate(obj: dict[str, Any]) -> str:
    admission = _metadata(obj).get("admission")
    if not isinstance(admission, dict):
        return ""
    return str(admission.get("gate_result") or "").strip()


def _spans(obj: dict[str, Any]) -> list[Any] | None:
    semantic = _semantic(obj)
    if semantic is None or "spans" not in semantic:
        return None
    spans = semantic.get("spans")
    return spans if isinstance(spans, list) else []


def is_structural_projection(obj: dict[str, Any]) -> bool:
    """Structure only while the stored row is still a heading or unclassified.

    A stored or confirmed knowledge type wins. Otherwise a stale proposed
    heading would keep a reclassified recommendation out of content review.
    """

    stored = str(obj.get("object_type") or "").strip()
    proposed = str(obj.get("proposed_object_type") or "").strip()
    confirmed = str(obj.get("confirmed_object_type") or "").strip()
    if confirmed not in {"", "heading"} or stored not in {"", "heading", "unclassified"}:
        return False
    if stored == "heading" or confirmed == "heading" or proposed == "heading":
        return True
    semantic = _semantic(obj)
    if semantic is None:
        return False
    if semantic.get("structural") is True:
        return True
    return _origin(obj) == "not_applicable"


def _exact_bound(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def spans_are_exact(spans: Any) -> bool:
    """Exact source spans: non-empty block id and real integer bounds.

    A string, a bool, a negative start, an empty range, or an unknown
    source-span id is not exact. This reader does not reconstruct the span.
    """

    if not isinstance(spans, list) or not spans:
        return False
    for span in spans:
        if not isinstance(span, dict):
            return False
        if not str(span.get("block_id") or "").strip():
            return False
        start = span.get("start")
        end = span.get("end")
        if not _exact_bound(start) or not _exact_bound(end):
            return False
        if start < 0 or end <= start:
            return False
        if "source_span_id" in span and str(span.get("source_span_id") or "").strip() in _UNKNOWN_SPAN:
            return False
    return True


def has_exact_source_spans(obj: dict[str, Any]) -> bool:
    spans = _spans(obj)
    if spans is None:
        return False
    return spans_are_exact(spans)


def _lineage_claimed(obj: dict[str, Any]) -> bool:
    return _spans(obj) is not None


def content_reviewable(obj: dict[str, Any]) -> bool:
    """Content review is only an admitted semantic candidate with exact spans.

    A deterministic row, a heading, a source record, or a coverage remainder
    is not a knowledge candidate. Boom construction does not use this predicate.
    """

    if str(obj.get("object_type") or "").strip() == "document":
        return False
    if is_structural_projection(obj):
        return False
    from src.source_accountability_v1 import is_source_record
    if is_source_record(obj):
        return False
    if _origin(obj) != SELECTION_ORIGIN_PROPOSAL:
        return False
    return _gate(obj) == GATE_ALLOWED and has_exact_source_spans(obj)


def candidate_lifecycle(obj: dict[str, Any]) -> str:
    """Derived lifecycle. Never written back onto the canonical object."""

    if is_structural_projection(obj):
        return "structure"
    from src.source_accountability_v1 import is_source_record
    if is_source_record(obj) or _origin(obj) == SELECTION_ORIGIN_COVERAGE:
        return "source"
    if _origin(obj) == SELECTION_ORIGIN_PROPOSAL and not has_exact_source_spans(obj):
        return "materialisation_failed"
    if _gate(obj) == GATE_BLOCKED:
        return "blocked"
    if content_reviewable(obj):
        return "admitted"
    return str((obj.get("governance") or {}).get("validation_status") or "")


def knowledge_publication_blockers(obj: dict[str, Any]) -> list[str]:
    """Blockers that stop a binding from authorizing knowledge publication.

    Publication uses the same candidate boundary as content review. A stored
    approval stays historical evidence and is not rewritten.
    """

    blockers: list[str] = []
    if is_structural_projection(obj):
        blockers.append("structural_projection_not_knowledge")
    if _lineage_claimed(obj) and not has_exact_source_spans(obj):
        blockers.append("source_lineage_incomplete")
    if _gate(obj) == GATE_BLOCKED:
        blockers.append("admission_blocked")
    if not content_reviewable(obj) and not blockers:
        blockers.append("not_knowledge_candidate")
    return blockers
