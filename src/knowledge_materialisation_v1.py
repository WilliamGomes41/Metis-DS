"""Deterministic materialisation of a SemanticSelectionDecision.

This is the only creator of a semantic KnowledgeCandidate. Selection code
returns decisions. It does not assign object identity or canonical text.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

from src.object_taxonomy_v1 import DEFAULT_OBJECT_TYPE, normalize_visible_prose
from src.semantic_passage_v1 import (
    SELECTION_ORIGIN_PROPOSAL,
    SEMANTIC_PASSAGE_VERSION,
    semantic_source_blocks,
    _reconstructed_blocks,
)

_DECISION_KIND = "semantic_selection"



def resolve_source_selection(
    spans: Any, *, fragments: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Rebuild text and provenance from authoritative extracted source only."""
    from src.knowledge_path_v1 import spans_are_exact
    from src.object_taxonomy_v1 import extract_object_type
    from src.source_reconstruction_v1 import source_fragment_ids_for_text
    from src.source_layout_v1 import mapped_raw_spans

    if not spans_are_exact(spans):
        raise ValueError("materialisation_span_invalid")
    blocks = {
        public["block_id"]: (public, source)
        for public, source in _reconstructed_blocks(
            row for row in fragments if extract_object_type(row)[0] != "heading"
        )
    }
    parts, fragment_ids, mapping = [], [], []
    first = None
    previous_rank = None
    seen = set()
    for span in spans:
        if span["block_id"] not in blocks:
            raise ValueError("materialisation_unknown_block")
        public, source = blocks[span["block_id"]]
        start, end = span["start"], span["end"]
        if end > len(public["text"]):
            raise ValueError("materialisation_span_invalid")
        rank = (public["position"], start, end)
        if previous_rank is not None and (
            rank <= previous_rank
            or (rank[0] == previous_rank[0] and start < previous_rank[2])
        ):
            raise ValueError("materialisation_span_order_invalid")
        previous_rank = rank
        first = first or public
        parts.append(public["text"][start:end])
        for fragment_id in source_fragment_ids_for_text(source, start=start, end=end):
            if fragment_id not in seen:
                seen.add(fragment_id)
                fragment_ids.append(fragment_id)
        mapping.extend(mapped_raw_spans(source, start=start, end=end))
    text = normalize_visible_prose(" ".join(parts))
    if not text:
        raise ValueError("materialisation_text_empty")
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
    candidates: list[dict[str, Any]] = []
    for decision in decisions:
        if not isinstance(decision, dict) or decision.get("decision_kind") != _DECISION_KIND:
            raise ValueError("materialiser_requires_selection_decision")
        if "object_id" in decision or "clean_text" in decision:
            raise ValueError("selection_decision_is_not_a_candidate")
        if decision.get("selection_origin") != SELECTION_ORIGIN_PROPOSAL:
            raise ValueError("materialiser_requires_proposal_selection")
        resolved = resolve_source_selection(decision.get("spans"), fragments=fragments)
        source_text = resolved["source_text"]
        if source_text != decision.get("source_text"):
            raise ValueError("materialisation_text_mismatch")
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
    return candidates


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
        raise ValueError("materialisation_count_mismatch")
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
