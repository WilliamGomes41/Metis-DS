"""Meaning-boundary split for Protocol v2.13 atomic objects.

Extraction splits at meaning boundaries, NOT token budgets. Token-budget
chunking (300–700 / 1000) MUST NOT define object identity. Fusion of
condition / exception / negation / qualifier into a recommendation is
FORBIDDEN unless splitting would break a single grammatical claim.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from src.object_taxonomy_v1 import propose_object_type

# Sentence boundary after ., ! or ? when the next claim starts with a capital.
# Abbreviations such as o.a. / d.w.z. are not treated as meaning boundaries.
_SENTENCE_RE = re.compile(
    r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÄËÏÖÜÀÈÂÊÎÔÛ])"
)
_ABBREV_RE = re.compile(
    r"\b(?:o\.a|d\.w\.z|bijv|ca|nr|dr|ir|mr|ds)\.$",
    re.I,
)
BOUNDING_TYPES = frozenset({"condition", "exception"})
CLAIM_TYPES = frozenset(
    {"recommendation", "condition", "exception", "definition", "explanation"}
)


def split_sentences(text: str) -> list[str]:
    blob = re.sub(r"\s+", " ", text or "").strip()
    if not blob:
        return []
    parts: list[str] = []
    start = 0
    for match in _SENTENCE_RE.finditer(blob):
        candidate = blob[start : match.start()].strip()
        if candidate and _ABBREV_RE.search(candidate):
            continue
        if candidate:
            parts.append(candidate)
            start = match.end()
    tail = blob[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def is_single_grammatical_claim(text: str) -> bool:
    return len(split_sentences(text)) <= 1


def fusion_is_forbidden(text: str) -> bool:
    """True when condition/exception and recommendation are separate sentences."""
    sentences = split_sentences(text)
    if len(sentences) <= 1:
        return False
    types = [propose_object_type(sentence) for sentence in sentences]
    has_recommendation = any(item == "recommendation" for item in types)
    has_bound = any(item in BOUNDING_TYPES for item in types)
    return has_recommendation and has_bound


def split_meaning_units(text: str, *, is_heading: bool = False) -> list[str]:
    """Split one confirmable meaning unit per grammatical claim.

    Token counts are ignored. Headings stay one structural unit.
    """
    blob = (text or "").strip()
    if not blob:
        return []
    if is_heading:
        return [blob]
    sentences = split_sentences(blob)
    return sentences or [blob]


def token_budget_must_not_define_identity(text: str) -> list[str]:
    """Explicit non-chunker: identity follows meaning units, never 300–700 / 1000."""
    return split_meaning_units(text)


def proposed_relations_for_units(units: Iterable[dict[str, Any]]) -> None:
    """Propose closed serving-law relations between adjacent split units.

    Proposals are unconfirmed. They MUST NOT bind until a human confirms them
    on the exact object version.
    """
    rows = list(units)
    last_heading: dict[str, Any] | None = None
    last_condition: dict[str, Any] | None = None
    last_recommendation: dict[str, Any] | None = None
    for row in rows:
        proposed = row.get("proposed_object_type") or propose_object_type(
            row.get("text") or "",
            is_heading=row.get("object_type") == "heading",
        )
        relations = list(row.get("relations") or [])
        if proposed == "heading" or row.get("object_type") == "heading":
            last_heading = row
            last_condition = None
            last_recommendation = None
            row["relations"] = relations
            continue
        if last_heading is not None:
            relations.append(
                {
                    "relation_type": "child",
                    "target_object_id": last_heading["object_id"],
                    "confirmed": False,
                }
            )
        if proposed == "condition":
            last_condition = row
        if proposed == "recommendation":
            if last_condition is not None:
                relations.append(
                    {
                        "relation_type": "applies_if",
                        "target_object_id": last_condition["object_id"],
                        "confirmed": False,
                    }
                )
            last_recommendation = row
        if proposed == "exception" and last_recommendation is not None:
            last_recommendation.setdefault("relations", []).append(
                {
                    "relation_type": "except_if",
                    "target_object_id": row["object_id"],
                    "confirmed": False,
                }
            )
        row["relations"] = relations
