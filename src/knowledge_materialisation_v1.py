"""Deterministic materialisation of a SemanticSelectionDecision.

This is the only creator of a semantic KnowledgeCandidate. Selection code
returns decisions. It does not assign object identity or canonical text.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from typing import Any, Iterable

from src.object_taxonomy_v1 import DEFAULT_OBJECT_TYPE, normalize_visible_prose
from src.semantic_passage_v1 import (
    SemanticPassageError,
    SELECTION_ORIGIN_PROPOSAL,
    SEMANTIC_PASSAGE_VERSION,
    semantic_source_blocks,
    _reconstructed_blocks,
)

_DECISION_KIND = "semantic_selection"
_source_reconstruction: ContextVar[dict | None] = ContextVar("source_reconstruction", default=None)


@contextmanager
def source_reconstruction_scope():
    """Reuse one identical source only during a synchronous read calculation.

    This stores derived blocks, never validation results. Each candidate still
    passes all source checks. A snapshot comparison detects even in-place input
    changes; nested calls and exceptions restore the caller's scope.
    """
    token = _source_reconstruction.set({})
    try:
        yield
    finally:
        _source_reconstruction.reset(token)


def _read_source_blocks(fragments):
    scope = _source_reconstruction.get()
    if scope is None:
        return _selection_blocks(fragments)
    if "fragments" not in scope or fragments != scope["fragments"]:
        blocks = _selection_blocks(fragments)
        scope.update(fragments=deepcopy(fragments), blocks=blocks)
    return scope["blocks"]


class MaterialisationError(SemanticPassageError):
    """Processing failure, never an Admission decision."""


def _selection_blocks(fragments):
    from src.object_taxonomy_v1 import extract_object_type
    return {
        public["block_id"]: (public, source)
        for public, source in _reconstructed_blocks(
            row for row in fragments if extract_object_type(row)[0] != "heading"
        )
    }


def resolve_source_selection(
    spans: Any, *, fragments: Iterable[dict[str, Any]], source_blocks=None
) -> dict[str, Any]:
    """Rebuild text and provenance from authoritative extracted source only."""
    from src.knowledge_path_v1 import spans_are_exact
    from src.source_reconstruction_v1 import source_fragment_ids_for_text
    from src.source_layout_v1 import mapped_raw_spans

    if not spans_are_exact(spans) or any(not isinstance(span["block_id"], str) for span in spans):
        raise MaterialisationError("materialisation_span_invalid")
    fragments = list(fragments)
    raw_by_id = {row.get("fragment_id"): row for row in fragments}
    try:
        blocks = source_blocks if source_blocks is not None else _read_source_blocks(fragments)
    except (ValueError, KeyError, TypeError) as exc:
        raise MaterialisationError("materialisation_source_mapping_invalid") from exc
    parts, fragment_ids, mapping = [], [], []
    first = None
    previous_rank = None
    seen = set()
    for span in spans:
        if span["block_id"] not in blocks:
            raise MaterialisationError("materialisation_unknown_block")
        public, source = blocks[span["block_id"]]
        start, end = span["start"], span["end"]
        if end > len(public["text"]):
            raise MaterialisationError("materialisation_span_invalid")
        rank = (public["position"], start, end)
        if previous_rank is not None and (
            rank <= previous_rank
            or (rank[0] == previous_rank[0] and start < previous_rank[2])
        ):
            raise MaterialisationError("materialisation_span_order_invalid")
        previous_rank = rank
        first = first or public
        cursor = start
        for raw_span in source.get("_raw_source_mapping", []):
            lo, hi = max(start, raw_span["start"]), min(end, raw_span["end"])
            if lo >= hi:
                continue
            if lo != cursor:
                raise MaterialisationError("materialisation_source_mapping_invalid")
            cursor = hi
        if cursor != end:
            raise MaterialisationError("materialisation_source_mapping_invalid")
        parts.append(public["text"][start:end])
        for fragment_id in source_fragment_ids_for_text(source, start=start, end=end):
            if fragment_id not in seen:
                seen.add(fragment_id)
                fragment_ids.append(fragment_id)
        mapping.extend(mapped_raw_spans(source, start=start, end=end))
    text = normalize_visible_prose(" ".join(parts))
    if not text:
        raise MaterialisationError("materialisation_text_empty")
    if not fragment_ids or any(
        not isinstance(value, str) or not value.strip() or value.upper() == "UNKNOWN"
        or value not in raw_by_id for value in fragment_ids
    ):
        raise MaterialisationError("materialisation_source_fragments_invalid")
    raw_mapping = [row for row in mapping if row.get("kind") != "join_separator"]
    if not raw_mapping or set(row.get("fragment_id") for row in raw_mapping) != set(fragment_ids):
        raise MaterialisationError("materialisation_source_mapping_invalid")
    for row in raw_mapping:
        raw = raw_by_id.get(row.get("fragment_id"))
        if (raw is None or type(row.get("raw_start")) is not int
                or type(row.get("raw_end")) is not int
                or not 0 <= row["raw_start"] < row["raw_end"] <= len(str(raw.get("raw_text") or ""))):
            raise MaterialisationError("materialisation_source_mapping_invalid")
    return {
        "source_text": text,
        "source_fragment_ids": fragment_ids,
        "source_mapping": mapping,
        "section_path": list(first["section_path"]),
        "heading": first["heading"],
    }


def _candidate_identity(document_id: str, spans: list[dict[str, Any]]) -> str:
    """Preserve the pre-T7 identity of the same ordered source selection.

    A selector-supplied identity field is not an input.
    """

    # Pre-T7 compatibility: document_id is the prefix, not a hash input.
    material = "|".join(
        f'{span["block_id"]}:{span["start"]}:{span["end"]}' for span in spans
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def materialise_knowledge_candidates(
    decisions: Iterable[dict[str, Any]],
    *,
    document_id: str,
    fragments: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create KnowledgeCandidates from selection decisions and exact source spans."""

    fragments = list(fragments)
    try:
        source_blocks = _selection_blocks(fragments)
    except (ValueError, KeyError, TypeError) as exc:
        raise MaterialisationError("materialisation_source_mapping_invalid") from exc
    candidates: list[dict[str, Any]] = []
    for index, decision in enumerate(decisions):
        try:
            if not isinstance(decision, dict) or decision.get("decision_kind") != _DECISION_KIND:
                raise MaterialisationError("materialiser_requires_selection_decision")
            if "object_id" in decision or "clean_text" in decision:
                raise MaterialisationError("selection_decision_is_not_a_candidate")
            if decision.get("selection_origin") != SELECTION_ORIGIN_PROPOSAL:
                raise MaterialisationError("materialiser_requires_proposal_selection")
            resolved = resolve_source_selection(decision.get("spans"), fragments=fragments, source_blocks=source_blocks)
            source_text = resolved["source_text"]
            if source_text != decision.get("source_text"):
                raise MaterialisationError("materialisation_text_mismatch")
            identity = _candidate_identity(document_id, decision["spans"])
            candidate: dict[str, Any] = {
                "object_id": f"{document_id}-sem-{identity}",
                "object_type": DEFAULT_OBJECT_TYPE,
                "text": source_text,
                "clean_text": source_text,
                "source_fragment_ids": resolved["source_fragment_ids"],
                "section_path": resolved["section_path"],
                "heading": resolved["heading"],
                "review_track": "clinical",
                "relations": [],
                "confirmed_relations": [],
                "semantic_passage": {
                    "version": SEMANTIC_PASSAGE_VERSION,
                    "source_bound": True,
                    "selection_origin": SELECTION_ORIGIN_PROPOSAL,
                    "spans": [
                        {"block_id": span["block_id"], "start": span["start"], "end": span["end"]}
                        for span in decision["spans"]
                    ],
                    "source_mapping": resolved["source_mapping"],
                },
            }
            if decision.get("emit_proposed_type"):
                candidate["proposed_object_type"] = decision.get("proposed_object_type")
            from src.source_bound_fields_v2 import CONTEXT_KEY, KEY
            if decision.get(CONTEXT_KEY):
                candidate[CONTEXT_KEY] = decision[CONTEXT_KEY]
            elif decision.get("context"):
                candidate[CONTEXT_KEY] = decision["context"]
            if KEY in decision:
                candidate[KEY] = decision[KEY]
            from src.recommendation_semantics_v1 import PROPOSED_FIELD
            if PROPOSED_FIELD in decision:
                candidate[PROPOSED_FIELD] = decision[PROPOSED_FIELD]
            if "recommendation_semantics_evidence" in decision:
                candidate["recommendation_semantics_evidence"] = decision["recommendation_semantics_evidence"]
            candidates.append(candidate)
        except MaterialisationError as exc:
            exc.finding["candidate_index"] = index
            raise
    return candidates



def validate_materialised_candidate(
    obj: dict[str, Any], *, fragments, source_blocks=None
) -> dict[str, Any]:
    """Validate raw or canonical candidates against authoritative source.

    Origin, admission, type and identity are not accepted as source proof.
    """
    fragments = list(fragments)
    metadata = obj.get("metadata") or {}
    semantic = obj.get("semantic_passage") or metadata.get("semantic_passage") or {}
    resolved = resolve_source_selection(
        semantic.get("spans"), fragments=fragments, source_blocks=source_blocks
    )
    content = obj.get("content")
    text = (content.get("clean_text") if isinstance(content, dict)
            else obj.get("clean_text", obj.get("text")))
    if not isinstance(text, str) or normalize_visible_prose(text) != resolved["source_text"]:
        raise MaterialisationError("materialisation_text_mismatch")
    expected_mapping = resolved["source_mapping"]
    from src.semantic_passage_v1 import LEGACY_SEMANTIC_PASSAGE_VERSION
    if semantic.get("version") == LEGACY_SEMANTIC_PASSAGE_VERSION:
        expected_mapping = [row for row in expected_mapping if row.get("kind") != "join_separator"]
    if semantic.get("source_mapping") != expected_mapping:
        raise MaterialisationError("materialisation_source_mapping_invalid")
    if isinstance(content, dict):
        refs = (obj.get("provenance") or {}).get("source_fragments")
        if not isinstance(refs, list) or any(not isinstance(row, dict) for row in refs):
            raise MaterialisationError("materialisation_source_fragments_invalid")
        ids = [row.get("raw_object_id") for row in refs]
        raw_by_id = {row.get("fragment_id"): row for row in fragments}
        for ref in refs:
            raw = raw_by_id.get(ref.get("raw_object_id"))
            if (raw is None
                    or not ref.get("raw_content_hash")
                    or str(ref.get("raw_content_hash")).upper() == "UNKNOWN"
                    or ref.get("raw_content_hash") != raw.get("fragment_hash")
                    or ref.get("source_locator") != raw.get("source_locator")
                    or ref.get("page") != raw.get("source_page")
                    or ref.get("bbox") != raw.get("bbox")
                    or ref.get("coordinate_status") != (
                        "available" if raw.get("bbox") is not None else "not_applicable")):
                raise MaterialisationError("materialisation_source_fragments_invalid")
    else:
        ids = obj.get("source_fragment_ids")
    if ids != resolved["source_fragment_ids"]:
        raise MaterialisationError("materialisation_source_fragments_invalid")
    return resolved

def ordered_source_projection(
    candidates: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    fragments: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Place materialised candidates and coverage rows back in source order.

    Coverage stays a source record. Only the materialised rows are knowledge
    candidates. Position does not grant either kind the other's authority.
    """

    if len(candidates) != len(decisions):
        raise MaterialisationError("materialisation_count_mismatch")
    block_order = {
        str(block["block_id"]): index
        for index, block in enumerate(semantic_source_blocks(fragments))
    }

    def rank(spans: Any) -> tuple[int, int]:
        if not isinstance(spans, list) or not spans or not isinstance(spans[0], dict):
            return (10**9, 0)
        span = spans[0]
        return (
            block_order.get(str(span.get("block_id") or ""), 10**9),
            int(span.get("start") or 0),
        )

    ranked: list[tuple[tuple[int, int], int, dict[str, Any]]] = []
    for index, (decision, candidate) in enumerate(zip(decisions, candidates)):
        ranked.append((rank(decision.get("spans")), index, candidate))
    offset = len(ranked)
    for index, row in enumerate(coverage):
        semantic = row.get("semantic_passage") if isinstance(row.get("semantic_passage"), dict) else {}
        ranked.append((rank(semantic.get("spans")), offset + index, row))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [row for _rank, _index, row in ranked]
