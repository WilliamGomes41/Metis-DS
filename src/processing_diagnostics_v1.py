"""Read-only diagnostics for admission-blocked Review candidates.

D2a explains the current processing surface without creating a new authority.
It groups existing admission reason codes for operational diagnosis while
preserving each raw code exactly as stored.

Important boundaries:
- a processing issue is not a human Review decision;
- a processing issue is not a candidate-quality score;
- a diagnostic family is not a root-cause claim;
- this module performs no writes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from src.admission_gate_v1 import admission_of
from src.domain_dimensions_v1 import processing_issue_objects
from src.object_taxonomy_v1 import section_role_for_path


SOURCE_BINDING = "source_binding"
UNIT_COMPLETENESS = "unit_completeness"
SEMANTIC_CONTRACT = "semantic_contract"
DEPENDENCY_RESOLUTION = "dependency_resolution"
PROCESSING_COMPLETENESS = "processing_completeness"
UNCLASSIFIED = "unclassified"

PROCESSING_ISSUE_FAMILIES = (
    SOURCE_BINDING,
    UNIT_COMPLETENESS,
    SEMANTIC_CONTRACT,
    DEPENDENCY_RESOLUTION,
    PROCESSING_COMPLETENESS,
    UNCLASSIFIED,
)

_REASON_FAMILY = {
    "locator_invalid": SOURCE_BINDING,
    "span_not_in_source": SOURCE_BINDING,
    "source_fidelity_failure": SOURCE_BINDING,
    "subject_missing": UNIT_COMPLETENESS,
    "predicate_missing": UNIT_COMPLETENESS,
    "incomplete_sentence": UNIT_COMPLETENESS,
    "no_independent_claim": UNIT_COMPLETENESS,
    "type_evidence_missing": SEMANTIC_CONTRACT,
    "type_contract_incomplete": SEMANTIC_CONTRACT,
    "recommendation_evidence_missing": SEMANTIC_CONTRACT,
    "condition_target_missing": SEMANTIC_CONTRACT,
    "exception_target_missing": SEMANTIC_CONTRACT,
    "supported_object_missing": SEMANTIC_CONTRACT,
    "comparison_target_missing": DEPENDENCY_RESOLUTION,
    "abbreviation_unresolved": DEPENDENCY_RESOLUTION,
    "unresolved_reference": DEPENDENCY_RESOLUTION,
    "context_necessary_unresolved": DEPENDENCY_RESOLUTION,
    "context_scan_not_done": PROCESSING_COMPLETENESS,
    "context_unnecessary_unrecorded": PROCESSING_COMPLETENESS,
}


def processing_issue_family(reason_code: str) -> str:
    """Return the diagnostic family without changing the raw reason code."""

    code = str(reason_code or "").strip()
    return _REASON_FAMILY.get(code, UNCLASSIFIED)


def _metadata(obj: dict[str, Any], key: str) -> dict[str, Any]:
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    value = metadata.get(key)
    return value if isinstance(value, dict) else {}


def _proposed_type(obj: dict[str, Any]) -> str:
    admission = admission_of(obj)
    return str(
        admission.get("proposed_type")
        or obj.get("proposed_object_type")
        or "unknown"
    ).strip() or "unknown"


def _section_path(obj: dict[str, Any]) -> list[str]:
    admission = admission_of(obj)
    raw_path = (
        admission.get("section_path")
        or (obj.get("structure") or {}).get("section_path")
        or []
    )
    return [
        str(part).strip()
        for part in raw_path
        if str(part).strip()
    ]


def _section_role(obj: dict[str, Any]) -> str:
    admission = admission_of(obj)
    role = str(admission.get("section_role") or "").strip()
    if role:
        return role
    path = _section_path(obj)
    return section_role_for_path(path) if path else "unknown"


def _formation_strategy(obj: dict[str, Any]) -> str:
    value = str(_metadata(obj, "passage_formation").get("strategy") or "").strip()
    return value or "unknown"


def _formation_reason(obj: dict[str, Any]) -> str:
    value = str(_metadata(obj, "passage_formation").get("reason") or "").strip()
    return value or "unknown"


def _candidate_text(obj: dict[str, Any]) -> str:
    admission = admission_of(obj)
    text = str(admission.get("candidate_text") or "").strip()
    if text:
        return text
    content = obj.get("content") if isinstance(obj.get("content"), dict) else {}
    return str(content.get("clean_text") or obj.get("text") or "").strip()


def _selection_origin(obj: dict[str, Any]) -> str:
    semantic = _metadata(obj, "semantic_passage")
    origin = str(semantic.get("selection_origin") or "").strip()
    if origin:
        return origin
    strategy = _formation_strategy(obj)
    if strategy == "deterministic":
        return "not_applicable"
    return "unknown"


def _increment(counter: Counter[str], key: str) -> None:
    counter[str(key or "unknown").strip() or "unknown"] += 1


def processing_diagnostic_rows(
    objects: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return one read-only diagnostic row per admission-blocked candidate.

    This is evidence for diagnosis only. It deliberately preserves raw
    admission reason codes and does not nominate a root cause or repair.
    """

    rows: list[dict[str, Any]] = []
    for index, obj in enumerate(processing_issue_objects(objects)):
        admission = admission_of(obj)
        reason_codes = [
            str(code).strip()
            for code in (admission.get("reason_codes") or [])
            if str(code).strip()
        ]
        families: list[str] = []
        for code in reason_codes:
            family = processing_issue_family(code)
            if family not in families:
                families.append(family)

        rows.append(
            {
                "object_id": str(obj.get("object_id") or f"blocked-{index}"),
                "object_version": str(obj.get("object_version") or ""),
                "candidate_text": _candidate_text(obj),
                "reason_codes": reason_codes,
                "families": families,
                "proposed_type": _proposed_type(obj),
                "section_role": _section_role(obj),
                "section_path": _section_path(obj),
                "formation_strategy": _formation_strategy(obj),
                "formation_reason": _formation_reason(obj),
                "selection_origin": _selection_origin(obj),
            }
        )
    return rows


def processing_diagnostics(
    objects: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize current admission-blocked candidates without mutating them.

    Candidate counts and issue-occurrence counts are deliberately distinct.
    A candidate may contribute multiple reason codes and multiple families.
    """

    blocked = list(processing_issue_objects(objects))
    by_reason: Counter[str] = Counter()
    by_reason_candidates: dict[str, set[str]] = defaultdict(set)
    by_family_occurrences: Counter[str] = Counter()
    by_family_candidates: dict[str, set[str]] = defaultdict(set)
    by_proposed_type: Counter[str] = Counter()
    by_section_role: Counter[str] = Counter()
    by_formation_strategy: Counter[str] = Counter()
    by_selection_origin: Counter[str] = Counter()
    unknown_reason_codes: set[str] = set()
    blocked_without_reason_ids: list[str] = []

    for index, obj in enumerate(blocked):
        object_id = str(obj.get("object_id") or f"blocked-{index}")
        admission = admission_of(obj)
        raw_reasons = [
            str(code).strip()
            for code in (admission.get("reason_codes") or [])
            if str(code).strip()
        ]

        _increment(by_proposed_type, _proposed_type(obj))
        _increment(by_section_role, _section_role(obj))
        _increment(by_formation_strategy, _formation_strategy(obj))
        _increment(by_selection_origin, _selection_origin(obj))

        if not raw_reasons:
            blocked_without_reason_ids.append(object_id)
            by_family_candidates[UNCLASSIFIED].add(object_id)
            continue

        for code in raw_reasons:
            family = processing_issue_family(code)
            by_reason[code] += 1
            by_reason_candidates[code].add(object_id)
            by_family_occurrences[family] += 1
            by_family_candidates[family].add(object_id)
            if family == UNCLASSIFIED:
                unknown_reason_codes.add(code)

    family_rows: dict[str, dict[str, int]] = {}
    for family in PROCESSING_ISSUE_FAMILIES:
        candidate_count = len(by_family_candidates.get(family, set()))
        issue_occurrence_count = int(by_family_occurrences.get(family, 0))
        if candidate_count or issue_occurrence_count:
            family_rows[family] = {
                "candidate_count": candidate_count,
                "issue_occurrence_count": issue_occurrence_count,
            }

    reason_rows = {
        code: {
            "candidate_count": len(by_reason_candidates[code]),
            "issue_occurrence_count": int(count),
        }
        for code, count in sorted(
            by_reason.items(),
            key=lambda item: (-item[1], item[0]),
        )
    }

    return {
        "blocked_candidate_count": len(blocked),
        "issue_occurrence_count": sum(by_reason.values()),
        "blocked_without_reason_count": len(blocked_without_reason_ids),
        "blocked_without_reason_ids": blocked_without_reason_ids,
        "unknown_reason_codes": sorted(unknown_reason_codes),
        "by_family": family_rows,
        "by_reason_code": reason_rows,
        "by_proposed_type": dict(sorted(by_proposed_type.items())),
        "by_section_role": dict(sorted(by_section_role.items())),
        "by_formation_strategy": dict(sorted(by_formation_strategy.items())),
        "by_selection_origin": dict(sorted(by_selection_origin.items())),
    }
