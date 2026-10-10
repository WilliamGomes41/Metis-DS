"""Source-bound proposals for atomic knowledge objects.

A source passage is evidence, not an object identity. This pure calculation
proposes boundaries within supplied text; it neither rebuilds source passages
nor confirms meaning, types, relations or review. Token budgets never define
boundaries. Ambiguous grammatical dependencies remain intact for admission
and human review rather than being severed by punctuation alone.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from src.object_taxonomy_v1 import (
    has_standalone_recommendation_start,
    is_continuation_fragment,
    normalize_visible_prose,
    propose_object_type,
)
from src.serving_relations_v1 import serving_relation_type

# Punctuation is only a candidate boundary. Include closing/opening quotes,
# but keep lowercase grammatical hangers and numeric/list starts intact.
_SENTENCE_RE = re.compile(
    r'''(?<=[.!?])["'”’»\)\]]*(?P<gap>\s+)(?=["'“‘«\(\[]*(?P<next>[^\W\d_]))'''
)
_ABBREV_RE = re.compile(
    r"\b(?:o\.a|d\.w\.z|bijv|ca|nr|dr|ir|mr|ds)\.$", re.I,
)
BOUNDING_TYPES = frozenset({"condition", "exception"})
CLAIM_TYPES = frozenset(
    {"recommendation", "condition", "exception", "definition", "explanation"}
)


@dataclass(frozen=True)
class MeaningUnitSpan:
    """Disposable proposal; offsets address the exact supplied text."""

    start: int
    end: int
    text: str


def _span(text: str, start: int, end: int) -> MeaningUnitSpan:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return MeaningUnitSpan(start, end, normalize_visible_prose(text[start:end]))


def _sentence_spans(text: str) -> list[MeaningUnitSpan]:
    parts: list[MeaningUnitSpan] = []
    start = 0
    for match in _SENTENCE_RE.finditer(text):
        if not match.group("next").isupper():
            continue
        candidate = _span(text, start, match.start("gap"))
        terminal = candidate.text.rstrip('\"\'”’»)]')
        if not candidate.text or _ABBREV_RE.search(terminal):
            continue
        parts.append(candidate)
        start = match.end("gap")
    tail = _span(text, start, len(text))
    if tail.text:
        parts.append(tail)
    return parts


def split_sentences(text: str) -> list[str]:
    """Detect sentence candidates, without asserting grammatical atomicity."""
    return [span.text for span in _sentence_spans(text or "")]


def has_at_most_one_detected_sentence(text: str) -> bool:
    """Nonempty sentence-count heuristic, never an admission/review proof."""
    sentences = split_sentences(text)
    return len(sentences) == 1


def is_single_grammatical_claim(text: str) -> bool:
    """Legacy heuristic API; True does not prove one grammatical claim.

    Also reject evident independent semicolon clauses. Admission and review
    remain responsible for dependencies and ambiguous multi-claim prose.
    """
    return has_at_most_one_detected_sentence(text) and len(split_meaning_units(text)) == 1


def fusion_is_forbidden(text: str) -> bool:
    """Detect separate recommendation/bound proposals, not all semantic fusion.

    Negation and qualifiers within a claim are retained verbatim. This helper
    is diagnostic, not the authority for admission or publication.
    """
    types = [propose_object_type(unit) for unit in split_meaning_units(text)]
    return "recommendation" in types and any(item in BOUNDING_TYPES for item in types)


def _independent_advice_clauses(text: str, sentence: MeaningUnitSpan) -> list[MeaningUnitSpan]:
    cuts = [match.end() for match in re.finditer(";", text[sentence.start:sentence.end])]
    if not cuts:
        return [sentence]
    boundaries = [sentence.start, *(sentence.start + cut for cut in cuts), sentence.end]
    clauses = [_span(text, left, right) for left, right in zip(boundaries, boundaries[1:])]
    # Do not split a condition, exception or incomplete/unknown clause away
    # from the action it limits. Only explicit independent advice starts qualify.
    if all(
        has_standalone_recommendation_start(clause.text)
        and propose_object_type(clause.text) == "recommendation"
        for clause in clauses
    ):
        return clauses
    return [sentence]


def split_meaning_unit_spans(text: str, *, is_heading: bool = False) -> list[MeaningUnitSpan]:
    """Propose units while preserving offsets into the unnormalised input.

    Headings remain structural units. Evident continuation fragments stay with
    the preceding sentence; integrated conditions/exceptions are not removed.
    This is a bounded heuristic, not semantic parsing or source reconstruction.
    """
    blob = text or ""
    if not blob.strip():
        return []
    if is_heading:
        return [_span(blob, 0, len(blob))]
    merged: list[MeaningUnitSpan] = []
    for sentence in _sentence_spans(blob):
        for unit in _independent_advice_clauses(blob, sentence):
            if merged and is_continuation_fragment(unit.text):
                merged[-1] = _span(blob, merged[-1].start, unit.end)
            else:
                merged.append(unit)
    return merged


def split_meaning_units(text: str, *, is_heading: bool = False) -> list[str]:
    """Compatibility text view of source-bound unit proposals."""
    if is_heading:
        return [(text or "").strip()] if (text or "").strip() else []
    return [span.text for span in split_meaning_unit_spans(text, is_heading=is_heading)]


def token_budget_must_not_define_identity(text: str) -> list[str]:
    """Explicit non-chunker: never use a 300–700 / 1000 token identity window."""
    return split_meaning_units(text)


def _same_section(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return [normalize_visible_prose(str(x)) for x in left.get("section_path") or []] == [
        normalize_visible_prose(str(x)) for x in right.get("section_path") or []
    ]


def _append_proposal(source: dict[str, Any], kind: str, target: dict[str, Any]) -> None:
    if source["object_id"] == target["object_id"]:
        return
    relations = source["relations"]
    if any(
        serving_relation_type(rel.get("relation_type")) == kind
        and rel.get("target_object_id") == target["object_id"]
        for rel in relations
    ):
        return
    relations.append({"relation_type": kind, "target_object_id": target["object_id"], "confirmed": False})


def relation_proposals_for_units(units: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return copied units with idempotent, unconfirmed relation proposals.

    Adjacency within the same section is only a proposal signal. A condition
    is not inherited by later recommendations; an exception cannot jump over
    intervening content. Existing confirmations/versions are never changed.
    Canonical version-bound relations and confirmation stay with their owners.
    """
    rows = deepcopy(list(units))
    last_heading: dict[str, Any] | None = None
    previous: dict[str, Any] | None = None
    previous_type: str | None = None
    for row in rows:
        proposed = row.get("proposed_object_type") or propose_object_type(
            row.get("text") or "", is_heading=row.get("object_type") == "heading",
        )
        row["relations"] = list(row.get("relations") or [])
        if proposed == "heading" or row.get("object_type") == "heading":
            last_heading = row
            previous = None
            previous_type = None
            continue
        if last_heading is not None and _same_section(last_heading, row):
            _append_proposal(row, "child", last_heading)
        if previous is not None and _same_section(previous, row):
            if proposed == "recommendation" and previous_type == "condition":
                _append_proposal(row, "applies_if", previous)
            if proposed == "exception" and previous_type == "recommendation":
                _append_proposal(previous, "except_if", row)
        previous, previous_type = row, proposed
    return rows


def proposed_relations_for_units(units: Iterable[dict[str, Any]]) -> None:
    """Legacy in-place adapter; computation itself never mutates input units."""
    rows = list(units)
    proposals = relation_proposals_for_units(rows)
    for row, proposal in zip(rows, proposals):
        row["relations"] = proposal["relations"]
