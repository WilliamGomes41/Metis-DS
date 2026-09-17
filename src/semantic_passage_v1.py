"""Deterministic source-bound contract for semantic passage proposals.

This module is provider-neutral. It accepts only references to exact spans in
Metis-reconstructed source blocks and reconstructs candidate text itself.
Model-authored candidate prose is therefore outside the accepted contract.

It is not wired into production passage formation yet.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES, DEFAULT_OBJECT_TYPE, normalize_visible_prose
from src.source_reconstruction_v1 import reconstruct_source_fragments, source_fragment_ids_for_text


SEMANTIC_PASSAGE_VERSION = "semantic-passage-v1.0.0"
ALLOWED_PROPOSED_TYPES = frozenset(
    (set(CLOSED_OBJECT_TYPES) - {"heading"}) | {DEFAULT_OBJECT_TYPE}
)

_TOP_LEVEL_KEYS = frozenset({"objects", "abstain_reason"})
_OBJECT_KEYS = frozenset({"spans", "proposed_object_type"})
_SPAN_KEYS = frozenset({"block_id", "start", "end"})


class SemanticPassageError(ValueError):
    """Fail-closed proposal validation error with one stable reason code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise SemanticPassageError(code)


def _require_only_keys(row: dict[str, Any], allowed: frozenset[str], code: str) -> None:
    if set(row) - allowed:
        _fail(code)


def _source_fragment_ids(fragment: dict[str, Any]) -> list[str]:
    ids = [str(value) for value in fragment.get("source_fragment_ids") or [] if value]
    fragment_id = str(fragment.get("fragment_id") or "")
    if fragment_id and fragment_id not in ids:
        ids.append(fragment_id)
    return ids


def _block_id(fragment: dict[str, Any], text: str) -> str:
    material = "\x1f".join(_source_fragment_ids(fragment)) + "\x1e" + text
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return f"semblock-{digest}"


def _reconstructed_blocks(
    fragments: Iterable[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    blocks: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for position, fragment in enumerate(reconstruct_source_fragments(fragments)):
        text = normalize_visible_prose(
            str(fragment.get("clean_text") or fragment.get("raw_text") or "")
        )
        if not text:
            continue
        public = {
            "block_id": _block_id(fragment, text),
            "position": position,
            "text": text,
            "source_fragment_ids": _source_fragment_ids(fragment),
            "section_path": [
                str(value)
                for value in fragment.get("section_path") or []
                if str(value).strip()
            ],
            "heading": str(fragment.get("heading") or "").strip() or None,
        }
        blocks.append((public, fragment))
    return blocks


def semantic_source_blocks(fragments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose reconstructed source blocks that a semantic proposer may select."""

    return [public for public, _source in _reconstructed_blocks(fragments)]


def semantic_units_from_proposal(
    fragments: Iterable[dict[str, Any]],
    *,
    document_id: str,
    proposal: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate a proposal and reconstruct meaning units from source only.

    The proposal contract is intentionally closed. A proposer can select spans
    and propose a type; it cannot supply candidate text or other canonical
    knowledge fields. Source order, candidate text and provenance are all
    derived deterministically by Metis.
    """

    if not isinstance(proposal, dict):
        _fail("semantic_proposal_invalid")
    _require_only_keys(proposal, _TOP_LEVEL_KEYS, "semantic_proposal_contains_untrusted_fields")

    raw_objects = proposal.get("objects", [])
    abstain_reason = str(proposal.get("abstain_reason") or "").strip()
    if not isinstance(raw_objects, list):
        _fail("semantic_objects_invalid")
    if abstain_reason:
        if raw_objects:
            _fail("semantic_abstain_with_objects")
        return []
    if not raw_objects:
        _fail("semantic_empty_proposal")

    reconstructed = _reconstructed_blocks(fragments)
    by_id = {public["block_id"]: (public, source) for public, source in reconstructed}
    units_with_position: list[tuple[tuple[int, int], dict[str, Any]]] = []

    for raw_object in raw_objects:
        if not isinstance(raw_object, dict):
            _fail("semantic_object_invalid")
        _require_only_keys(raw_object, _OBJECT_KEYS, "semantic_object_contains_untrusted_fields")

        proposed_type = str(
            raw_object.get("proposed_object_type") or DEFAULT_OBJECT_TYPE
        ).strip()
        if proposed_type not in ALLOWED_PROPOSED_TYPES:
            _fail("semantic_object_type_invalid")

        raw_spans = raw_object.get("spans")
        if not isinstance(raw_spans, list) or not raw_spans:
            _fail("semantic_object_spans_required")

        selected: list[dict[str, Any]] = []
        seen_ranges: set[tuple[str, int, int]] = set()
        for raw_span in raw_spans:
            if not isinstance(raw_span, dict):
                _fail("semantic_span_invalid")
            _require_only_keys(raw_span, _SPAN_KEYS, "semantic_span_contains_untrusted_fields")

            block_id = str(raw_span.get("block_id") or "")
            if block_id not in by_id:
                _fail("semantic_span_unknown_block")

            start = raw_span.get("start")
            end = raw_span.get("end")
            if (
                isinstance(start, bool)
                or isinstance(end, bool)
                or not isinstance(start, int)
                or not isinstance(end, int)
            ):
                _fail("semantic_span_bounds_invalid")

            public, source = by_id[block_id]
            text = str(public["text"])
            if start < 0 or end <= start or end > len(text):
                _fail("semantic_span_bounds_invalid")

            range_key = (block_id, start, end)
            if range_key in seen_ranges:
                _fail("semantic_span_duplicate")
            seen_ranges.add(range_key)

            selected_text = text[start:end]
            if not selected_text.strip():
                _fail("semantic_span_empty")
            selected.append(
                {
                    "block_id": block_id,
                    "position": int(public["position"]),
                    "start": start,
                    "end": end,
                    "text": selected_text,
                    "section_path": list(public["section_path"]),
                    "heading": public["heading"],
                    "source_fragment_ids": source_fragment_ids_for_text(
                        source,
                        start=start,
                        end=end,
                    ),
                }
            )

        selected.sort(key=lambda row: (row["position"], row["start"], row["end"]))
        section_paths = {tuple(row["section_path"]) for row in selected}
        if len(section_paths) != 1:
            _fail("semantic_cross_section_merge")

        previous_end_by_block: dict[str, int] = {}
        for row in selected:
            previous_end = previous_end_by_block.get(row["block_id"])
            if previous_end is not None and row["start"] < previous_end:
                _fail("semantic_span_overlap")
            previous_end_by_block[row["block_id"]] = row["end"]

        candidate_text = normalize_visible_prose(" ".join(row["text"] for row in selected))
        if not candidate_text:
            _fail("semantic_candidate_empty")

        fragment_ids: list[str] = []
        for row in selected:
            for fragment_id in row["source_fragment_ids"]:
                if fragment_id not in fragment_ids:
                    fragment_ids.append(fragment_id)

        identity_material = "|".join(
            f'{row["block_id"]}:{row["start"]}:{row["end"]}' for row in selected
        )
        identity = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()[:16]
        first = selected[0]
        unit: dict[str, Any] = {
            "object_id": f"{document_id}-sem-{identity}",
            "object_type": DEFAULT_OBJECT_TYPE,
            "text": candidate_text,
            "clean_text": candidate_text,
            "source_fragment_ids": fragment_ids,
            "section_path": list(first["section_path"]),
            "heading": first["heading"],
            "review_track": "clinical",
            "relations": [],
            "confirmed_relations": [],
            "semantic_passage": {
                "version": SEMANTIC_PASSAGE_VERSION,
                "source_bound": True,
                "spans": [
                    {
                        "block_id": row["block_id"],
                        "start": row["start"],
                        "end": row["end"],
                    }
                    for row in selected
                ],
            },
        }
        if proposed_type != DEFAULT_OBJECT_TYPE:
            unit["proposed_object_type"] = proposed_type
        units_with_position.append(((first["position"], first["start"]), unit))

    units_with_position.sort(key=lambda pair: pair[0])
    return [unit for _position, unit in units_with_position]
