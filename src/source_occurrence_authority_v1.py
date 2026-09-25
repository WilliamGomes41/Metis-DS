"""Exact source-occurrence authority for passage formation.

Repeated source prose is one candidate, not extra knowledge. This module keeps
all exact occurrences as provenance while choosing the most authoritative
occurrence as the principal candidate location. It performs no fuzzy or
semantic deduplication.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from src.object_taxonomy_v1 import normalize_visible_prose, section_role_for_path


SOURCE_OCCURRENCE_AUTHORITY_VERSION = "source-occurrence-authority-v1.0.0"
REASON_AUTHORITATIVE_SECTION = "authoritative_section_preferred"
REASON_SAME_AUTHORITY = "same_authority_exact_duplicate"

_ROLE_RANK = {
    "structural": 0,
    "summary": 1,
    "context": 2,
    "support": 3,
    "primary": 4,
}


def _text_key(unit: dict[str, Any]) -> str:
    return normalize_visible_prose(
        str(unit.get("clean_text") or unit.get("text") or "")
    )


def _section_role(unit: dict[str, Any]) -> str:
    return section_role_for_path(unit.get("section_path") or [])


def _source_ids(unit: dict[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(
            str(value)
            for value in (unit.get("source_fragment_ids") or [])
            if str(value).strip()
        )
    )


def _occurrence(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_fragment_ids": _source_ids(unit),
        "section_role": _section_role(unit),
        "section_path": [
            str(value)
            for value in (unit.get("section_path") or [])
            if str(value).strip()
        ],
    }


def _rank(unit: dict[str, Any]) -> tuple[int, int]:
    """Prefer authoritative section role, then the most direct exact occurrence."""

    return (
        _ROLE_RANK.get(_section_role(unit), _ROLE_RANK["primary"]),
        -len(_source_ids(unit)),
    )


def _proposal_rank(unit: dict[str, Any]) -> int:
    semantic = unit.get("semantic_passage")
    if not isinstance(semantic, dict):
        return 0
    return 1 if semantic.get("selection_origin") == "proposal_selected" else 0


def _apply_candidate_semantics(
    principal: dict[str, Any],
    donor: dict[str, Any],
) -> dict[str, Any]:
    """Keep candidate semantics independent from source-location authority."""

    if donor is principal:
        return principal
    row = deepcopy(principal)
    for key in (
        "semantic_passage",
        "proposed_object_type",
        "proposed_recommendation_strength",
        "proposed_recommendation_semantics",
        "recommendation_semantics_evidence",
    ):
        if key in donor:
            row[key] = deepcopy(donor[key])
    return row


def _with_authority_metadata(
    principal: dict[str, Any],
    *,
    alternates: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    row = deepcopy(principal)
    metadata = dict(row.get("metadata") or {})
    metadata["source_occurrence_authority"] = {
        "version": SOURCE_OCCURRENCE_AUTHORITY_VERSION,
        "principal_section_role": _section_role(principal),
        "reason": reason,
        "alternate_occurrences": deepcopy(alternates),
    }
    row["metadata"] = metadata
    return row


def prefer_authoritative_exact_occurrences(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate exact visible prose and retain authoritative provenance.

    Groups are keyed only by normalized exact visible text. The selected
    principal occurrence determines object identity, section path and heading.
    Principal source_fragment_ids remain principal-only so existing source
    reconstruction and Review UI never treat duplicate occurrences as one
    composite passage. Within the same section role, a source occurrence carried
    by fewer source fragments wins over an equivalent reconstructed occurrence.
    Alternate exact occurrences are preserved separately in
    source_occurrence_authority metadata. Output order follows the selected
    principal occurrence, not the first duplicate encountered.
    """

    groups: dict[str, dict[str, Any]] = {}
    passthrough: list[tuple[int, dict[str, Any]]] = []

    for position, original in enumerate(rows):
        unit = deepcopy(original)
        key = _text_key(unit)
        if not key:
            passthrough.append((position, unit))
            continue

        current = groups.get(key)
        if current is None:
            groups[key] = {
                "principal": unit,
                "principal_position": position,
                "semantic_donor": unit,
                "occurrences": [_occurrence(unit)],
            }
            continue

        current["occurrences"].append(_occurrence(unit))
        principal = current["principal"]
        if _rank(unit) > _rank(principal):
            current["principal"] = unit
            current["principal_position"] = position
        if _proposal_rank(unit) > _proposal_rank(current["semantic_donor"]):
            current["semantic_donor"] = unit

    out: list[tuple[int, dict[str, Any]]] = list(passthrough)
    for group in groups.values():
        principal = _apply_candidate_semantics(
            group["principal"],
            group["semantic_donor"],
        )
        occurrences = list(group["occurrences"])
        principal_occurrence = _occurrence(principal)

        remaining = occurrences.copy()
        try:
            remaining.remove(principal_occurrence)
        except ValueError:
            remaining = [
                occurrence
                for occurrence in remaining
                if occurrence != principal_occurrence
            ]

        if remaining:
            reason = (
                REASON_AUTHORITATIVE_SECTION
                if any(
                    occurrence["section_role"]
                    != principal_occurrence["section_role"]
                    for occurrence in remaining
                )
                else REASON_SAME_AUTHORITY
            )
            principal = _with_authority_metadata(
                principal,
                alternates=remaining,
                reason=reason,
            )

        out.append((int(group["principal_position"]), principal))

    out.sort(key=lambda item: item[0])
    return [row for _position, row in out]
