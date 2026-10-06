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
)

_DECISION_KIND = "semantic_selection"


def _source_text(decision: dict[str, Any], blocks: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    for span in decision["spans"]:
        block = blocks.get(str(span["block_id"]))
        if block is None:
            raise ValueError("materialisation_unknown_block")
        start = span["start"]
        end = span["end"]
        text = str(block["text"])
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(text):
            raise ValueError("materialisation_span_invalid")
        parts.append(text[start:end])
    source_text = normalize_visible_prose(" ".join(parts))
    if source_text != decision.get("source_text"):
        raise ValueError("materialisation_text_mismatch")
    return source_text


def materialise_knowledge_candidates(
    decisions: Iterable[dict[str, Any]],
    *,
    document_id: str,
    fragments: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create KnowledgeCandidates from selection decisions and exact source spans."""

    blocks = {row["block_id"]: row for row in semantic_source_blocks(fragments)}
    candidates: list[dict[str, Any]] = []
    for decision in decisions:
        if not isinstance(decision, dict) or decision.get("decision_kind") != _DECISION_KIND:
            raise ValueError("materialiser_requires_selection_decision")
        if "object_id" in decision or "clean_text" in decision:
            raise ValueError("selection_decision_is_not_a_candidate")
        if decision.get("selection_origin") != SELECTION_ORIGIN_PROPOSAL:
            raise ValueError("materialiser_requires_proposal_selection")
        source_text = _source_text(decision, blocks)
        identity_material = decision.get("_identity_material") or "|".join(
            f'{span["block_id"]}:{span["start"]}:{span["end"]}' for span in decision["spans"]
        )
        identity = hashlib.sha256(str(identity_material).encode("utf-8")).hexdigest()[:16]
        candidate: dict[str, Any] = {
            "object_id": f"{document_id}-sem-{identity}",
            "object_type": DEFAULT_OBJECT_TYPE,
            "text": source_text,
            "clean_text": source_text,
            "source_fragment_ids": list(decision.get("source_fragment_ids") or []),
            "section_path": list(decision.get("section_path") or []),
            "heading": decision.get("heading"),
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
                "source_mapping": list(decision.get("source_mapping") or []),
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
