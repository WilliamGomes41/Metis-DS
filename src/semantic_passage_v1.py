"""Deterministic source-bound contract for semantic passage proposals.

The provider may select exact source spans and closed proposal enums only.
Candidate prose and recommendation evidence prose are reconstructed by Metis
from immutable source blocks.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES, DEFAULT_OBJECT_TYPE, normalize_visible_prose
from src.recommendation_semantics_v1 import (
    PROPOSED_FIELD,
    RECOMMENDATION_SEMANTICS_VERSION,
    source_literal_strength,
    validate_recommendation_semantics,
)
from src.source_reconstruction_v1 import reconstruct_source_fragments, source_fragment_ids_for_text


SEMANTIC_PASSAGE_VERSION = "semantic-passage-v1.0.0"
RECOMMENDATION_SEMANTICS_EVIDENCE_VERSION = "recommendation-semantics-evidence-v1"
SELECTION_ORIGIN_PROPOSAL = "proposal_selected"
SELECTION_ORIGIN_COVERAGE = "coverage_remainder"
ALLOWED_PROPOSED_TYPES = frozenset(
    (set(CLOSED_OBJECT_TYPES) - {"heading"}) | {DEFAULT_OBJECT_TYPE}
)

_TOP_LEVEL_KEYS = frozenset({"objects", "abstain_reason"})
_OBJECT_KEYS = frozenset({"spans", "proposed_object_type", "recommendation_semantics"})
_SPAN_KEYS = frozenset({"block_id", "start", "end"})
_RECOMMENDATION_KEYS = frozenset(
    {
        "direction",
        "direction_evidence",
        "strength",
        "strength_status",
        "strength_evidence",
    }
)


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
    """Expose reconstructed source blocks that a semantic proposer may reference."""

    return [public for public, _source in _reconstructed_blocks(fragments)]


def _coverage_remainders(
    reconstructed: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    document_id: str,
    selected_ranges_by_block: dict[str, list[tuple[int, int]]],
) -> list[tuple[tuple[int, int], dict[str, Any]]]:
    out: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for public, source in reconstructed:
        block_id = str(public["block_id"])
        text = str(public["text"])
        ranges = sorted(selected_ranges_by_block.get(block_id, []))

        merged: list[tuple[int, int]] = []
        for start, end in ranges:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        cursor = 0
        gaps: list[tuple[int, int]] = []
        for start, end in merged:
            if cursor < start:
                gaps.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < len(text):
            gaps.append((cursor, len(text)))

        for start, end in gaps:
            remainder_text = normalize_visible_prose(text[start:end])
            if not remainder_text:
                continue
            fragment_ids = source_fragment_ids_for_text(source, start=start, end=end)
            identity_material = f"{block_id}:{start}:{end}:coverage"
            identity = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()[:16]
            unit = {
                "object_id": f"{document_id}-semcov-{identity}",
                "object_type": DEFAULT_OBJECT_TYPE,
                "text": remainder_text,
                "clean_text": remainder_text,
                "source_fragment_ids": fragment_ids,
                "section_path": list(public["section_path"]),
                "heading": public["heading"],
                "review_track": "clinical",
                "relations": [],
                "confirmed_relations": [],
                "semantic_passage": {
                    "version": SEMANTIC_PASSAGE_VERSION,
                    "source_bound": True,
                    "selection_origin": SELECTION_ORIGIN_COVERAGE,
                    "spans": [
                        {
                            "block_id": block_id,
                            "start": start,
                            "end": end,
                        }
                    ],
                },
            }
            out.append(((int(public["position"]), start), unit))
    return out


def _paths_related(left: list[str], right: list[str]) -> bool:
    if left == right:
        return True
    if not left or not right:
        return False
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    return long[: len(short)] == short


def _resolve_evidence_ref(
    raw_ref: Any,
    *,
    evidence_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    candidate_section_path: list[str],
    code_prefix: str,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(raw_ref, dict):
        _fail(f"{code_prefix}_missing")
    _require_only_keys(raw_ref, _SPAN_KEYS, f"{code_prefix}_contains_untrusted_fields")
    block_id = str(raw_ref.get("block_id") or "")
    if block_id not in evidence_by_id:
        _fail(f"{code_prefix}_unknown_block")
    start = raw_ref.get("start")
    end = raw_ref.get("end")
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
    ):
        _fail(f"{code_prefix}_bounds_invalid")
    public, source = evidence_by_id[block_id]
    text = str(public["text"])
    if start < 0 or end <= start or end > len(text):
        _fail(f"{code_prefix}_bounds_invalid")
    if not _paths_related(candidate_section_path, list(public["section_path"])):
        _fail(f"{code_prefix}_cross_section")
    evidence_text = normalize_visible_prose(text[start:end])
    if not evidence_text:
        _fail(f"{code_prefix}_empty")
    return evidence_text, {
        "block_id": block_id,
        "start": start,
        "end": end,
        "source_fragment_ids": source_fragment_ids_for_text(
            source,
            start=start,
            end=end,
        ),
    }


def _direction_ref_within_candidate(
    evidence: dict[str, Any],
    selected: list[dict[str, Any]],
) -> bool:
    for row in selected:
        if row["block_id"] != evidence["block_id"]:
            continue
        if evidence["start"] >= row["start"] and evidence["end"] <= row["end"]:
            return True
    return False


def _recommendation_semantics_from_proposal(
    raw_semantics: Any,
    *,
    proposed_type: str,
    selected: list[dict[str, Any]],
    evidence_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if raw_semantics is None:
        return None, None
    if proposed_type != "recommendation":
        _fail("recommendation_semantics_on_non_recommendation")
    if not isinstance(raw_semantics, dict):
        _fail("recommendation_semantics_invalid")
    _require_only_keys(
        raw_semantics,
        _RECOMMENDATION_KEYS,
        "recommendation_semantics_contains_untrusted_fields",
    )

    direction = str(raw_semantics.get("direction") or "").strip()
    if direction not in {"for", "against"}:
        _fail("recommendation_direction_invalid")

    candidate_section_path = list(selected[0]["section_path"])
    direction_text, direction_evidence = _resolve_evidence_ref(
        raw_semantics.get("direction_evidence"),
        evidence_by_id=evidence_by_id,
        candidate_section_path=candidate_section_path,
        code_prefix="recommendation_direction_evidence",
    )
    if not _direction_ref_within_candidate(direction_evidence, selected):
        _fail("recommendation_direction_evidence_outside_candidate")

    status = str(raw_semantics.get("strength_status") or "").strip()
    if status not in {"explicit", "not_stated", "unmapped"}:
        _fail("recommendation_strength_status_invalid")
    strength = raw_semantics.get("strength")
    strength_evidence: dict[str, Any] | None = None
    strength_text: str | None = None

    if status == "explicit":
        if strength not in {"strong", "weak"}:
            _fail("recommendation_strength_invalid")
        strength_text, strength_evidence = _resolve_evidence_ref(
            raw_semantics.get("strength_evidence"),
            evidence_by_id=evidence_by_id,
            candidate_section_path=candidate_section_path,
            code_prefix="recommendation_strength_evidence",
        )
        literal = source_literal_strength(strength_text)
        if literal != strength:
            _fail("recommendation_strength_literal_mismatch")
    elif status == "not_stated":
        if strength is not None or raw_semantics.get("strength_evidence") is not None:
            _fail("recommendation_strength_not_stated_invalid")
        related_evidence_text = [
            str(public.get("text") or "")
            for public, _source in evidence_by_id.values()
            if _paths_related(
                candidate_section_path,
                list(public.get("section_path") or []),
            )
        ]
        context_for_strength = " ".join(
            [str(row.get("text") or "") for row in selected]
            + list(candidate_section_path)
            + related_evidence_text
        )
        if source_literal_strength(context_for_strength) is not None:
            _fail("recommendation_strength_not_stated_conflict")
    else:
        if strength is not None:
            _fail("recommendation_strength_unmapped_invalid")
        strength_text, strength_evidence = _resolve_evidence_ref(
            raw_semantics.get("strength_evidence"),
            evidence_by_id=evidence_by_id,
            candidate_section_path=candidate_section_path,
            code_prefix="recommendation_strength_evidence",
        )
        if source_literal_strength(strength_text) is not None:
            _fail("recommendation_strength_unmapped_literal_conflict")

    semantics = {
        "version": RECOMMENDATION_SEMANTICS_VERSION,
        "direction": direction,
        "strength": strength,
        "strength_status": status,
        "direction_evidence_span": direction_text,
        "strength_evidence_span": strength_text,
        "source_label": strength_text,
        "normalization_scheme": "source_literal_v1",
    }
    if validate_recommendation_semantics(semantics, confirmed=False):
        _fail("recommendation_semantics_invalid")

    evidence = {
        "version": RECOMMENDATION_SEMANTICS_EVIDENCE_VERSION,
        "direction": direction_evidence,
        "strength": strength_evidence,
    }
    return semantics, evidence


def semantic_units_from_proposal(
    fragments: Iterable[dict[str, Any]],
    *,
    document_id: str,
    proposal: dict[str, Any],
    evidence_fragments: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Validate provider proposal and reconstruct source-bound candidate data."""

    fragments_list = list(fragments)
    evidence_list = list(evidence_fragments) if evidence_fragments is not None else fragments_list

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

    reconstructed = _reconstructed_blocks(fragments_list)
    by_id = {public["block_id"]: (public, source) for public, source in reconstructed}
    evidence_reconstructed = _reconstructed_blocks(evidence_list)
    evidence_by_id = {
        public["block_id"]: (public, source)
        for public, source in evidence_reconstructed
    }
    block_order = {
        str(public["block_id"]): index
        for index, (public, _source) in enumerate(reconstructed)
    }
    units_with_position: list[tuple[tuple[int, int], dict[str, Any]]] = []
    selected_ranges_by_block: dict[str, list[tuple[int, int]]] = {}

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
            selected_ranges_by_block.setdefault(block_id, []).append((start, end))

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

        for previous, current in zip(selected, selected[1:]):
            if previous["block_id"] == current["block_id"]:
                block_text = str(by_id[previous["block_id"]][0]["text"])
                if block_text[previous["end"]:current["start"]].strip():
                    _fail("semantic_span_hidden_gap")
                continue
            if block_order[current["block_id"]] != block_order[previous["block_id"]] + 1:
                _fail("semantic_span_hidden_gap")
            previous_text = str(by_id[previous["block_id"]][0]["text"])
            if previous["end"] != len(previous_text) or current["start"] != 0:
                _fail("semantic_span_hidden_gap")

        candidate_text = normalize_visible_prose(" ".join(row["text"] for row in selected))
        if not candidate_text:
            _fail("semantic_candidate_empty")

        fragment_ids: list[str] = []
        for row in selected:
            for fragment_id in row["source_fragment_ids"]:
                if fragment_id not in fragment_ids:
                    fragment_ids.append(fragment_id)

        semantics, semantics_evidence = _recommendation_semantics_from_proposal(
            raw_object.get("recommendation_semantics"),
            proposed_type=proposed_type,
            selected=selected,
            evidence_by_id=evidence_by_id,
        )

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
                "selection_origin": SELECTION_ORIGIN_PROPOSAL,
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
        if semantics is not None:
            unit[PROPOSED_FIELD] = semantics
            unit["recommendation_semantics_evidence"] = semantics_evidence
        units_with_position.append(((first["position"], first["start"]), unit))

    units_with_position.extend(
        _coverage_remainders(
            reconstructed,
            document_id=document_id,
            selected_ranges_by_block=selected_ranges_by_block,
        )
    )
    units_with_position.sort(key=lambda pair: pair[0])
    return [unit for _position, unit in units_with_position]
