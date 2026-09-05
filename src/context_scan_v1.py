"""Phase 2 deep context scan for richtlijn inhoudelijke candidates.

Window: candidate paragraph + previous paragraph + next paragraph +
current heading + ancestor headings. Necessary context → include OR
link OR block. MUST NOT claim context is unnecessary without recording
the checked signals.
"""
from __future__ import annotations

import re
from typing import Any

from src.admission_gate_v1 import (
    _KNOWN_ABBREVS,
    _scan_abbreviations,
    _scan_comparisons,
    _scan_conditions,
    _scan_exceptions,
    _scan_references,
)


CHECKED_CONTEXT_SIGNALS = (
    "candidate_paragraph",
    "previous_paragraph",
    "next_paragraph",
    "current_heading",
    "ancestor_headings",
    "references",
    "abbreviations",
    "comparisons",
    "conditions",
    "exceptions",
)

DISPOSITION_INCLUDE = "include"
DISPOSITION_LINK = "link"
DISPOSITION_BLOCK = "block"

_ABBREV_DEF_RE = re.compile(
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\s\-&']{1,80}?)\s+\("
    r"([A-Za-z]{0,3}[A-Z][A-Za-z&]{1,10})\)"
)
_ABBREV_REVERSE_DEF_RE = re.compile(
    r"\b([A-Za-z]{0,3}[A-Z][A-Za-z&]{1,10})\s+\(([^)]{3,80})\)"
)
_ADVICE_CUE_RE = re.compile(
    r"\b(?:adviseert?|aanbeveelt?|overweeg(?:t)?)\b",
    re.I,
)
_EXCEPTION_CUE_RE = re.compile(
    r"\b(?:tenzij|behalve|uitgezonderd|uitzondering)\b",
    re.I,
)
_CONDITION_CUE_RE = re.compile(
    r"\b(?:wanneer|indien|mits|bij een|voorwaarde)\b",
    re.I,
)


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        blob = _clean(item)
        if blob and blob not in out:
            out.append(blob)
    return out


def headings_from_section_path(section_path: Any) -> tuple[str, list[str]]:
    parts = [_clean(part) for part in (section_path or []) if _clean(part)]
    if not parts:
        return "", []
    return parts[-1], parts[:-1]


def local_abbreviation_map(*texts: str) -> dict[str, str]:
    found: dict[str, str] = dict(_KNOWN_ABBREVS)
    blob = " ".join(_clean(text) for text in texts if text)
    for match in _ABBREV_DEF_RE.finditer(blob):
        expansion, token = match.group(1).strip(), match.group(2).strip()
        if token:
            found[token] = expansion
    for match in _ABBREV_REVERSE_DEF_RE.finditer(blob):
        token, expansion = match.group(1).strip(), match.group(2).strip()
        if token and expansion:
            found.setdefault(token, expansion)
    return found


def _detect_abbreviations(*texts: str) -> tuple[list[str], list[str]]:
    detected: list[str] = []
    resolved: list[str] = []
    catalog = local_abbreviation_map(*texts)
    for text in texts:
        found, _ = _scan_abbreviations(text)
        for token in found:
            if token not in detected:
                detected.append(token)
    for token in detected:
        if token in catalog and token not in resolved:
            resolved.append(token)
    return detected, resolved


def _window_text(parts: list[str]) -> str:
    return " ".join(part for part in parts if part)


def propose_expand_merge(
    *,
    candidate_paragraph: str,
    previous_paragraph: str = "",
    next_paragraph: str = "",
) -> dict[str, Any]:
    candidate = _clean(candidate_paragraph)
    previous = _clean(previous_paragraph)
    nxt = _clean(next_paragraph)
    if candidate and nxt and _ADVICE_CUE_RE.search(candidate) and _EXCEPTION_CUE_RE.search(nxt):
        merged = f"{candidate} {nxt}".strip()
        return {
            "performed": True,
            "merged_text": merged,
            "parts": [candidate, nxt],
            "kind": "recommendation_exception",
        }
    if candidate and previous and _ADVICE_CUE_RE.search(candidate) and _CONDITION_CUE_RE.search(previous):
        merged = f"{previous} {candidate}".strip()
        return {
            "performed": True,
            "merged_text": merged,
            "parts": [previous, candidate],
            "kind": "condition_recommendation",
        }
    return {"performed": False, "merged_text": "", "parts": [], "kind": ""}


def necessary_context_disposition(
    *,
    previous_paragraph: str,
    next_paragraph: str,
    current_heading: str,
    ancestor_headings: list[str],
    expand_merge: dict[str, Any],
    conditions: list[str],
    exceptions: list[str],
    related_candidates: list[str],
) -> str:
    has_neighbor_constraint = bool(
        _CONDITION_CUE_RE.search(previous_paragraph or "")
        or _EXCEPTION_CUE_RE.search(next_paragraph or "")
        or _EXCEPTION_CUE_RE.search(previous_paragraph or "")
        or conditions
        or exceptions
    )
    if not has_neighbor_constraint:
        # Window itself is included so a later claim of "unnecessary"
        # still has recorded signals.
        return DISPOSITION_INCLUDE
    if expand_merge.get("performed") or conditions or exceptions:
        if related_candidates and not expand_merge.get("performed"):
            return DISPOSITION_LINK
        return DISPOSITION_INCLUDE
    if current_heading or ancestor_headings:
        return DISPOSITION_INCLUDE
    return DISPOSITION_BLOCK


def scan_deep_context(
    *,
    candidate_paragraph: str = "",
    previous_paragraph: str = "",
    next_paragraph: str = "",
    current_heading: str = "",
    ancestor_headings: list[str] | None = None,
    section_path: list[str] | None = None,
    related_candidates: list[str] | None = None,
) -> dict[str, Any]:
    """Scan the Phase-2 deep window and record every checked signal."""
    candidate = _clean(candidate_paragraph)
    previous = _clean(previous_paragraph)
    nxt = _clean(next_paragraph)
    heading = _clean(current_heading)
    ancestors = [_clean(item) for item in (ancestor_headings or []) if _clean(item)]
    path = [_clean(item) for item in (section_path or []) if _clean(item)]
    if not heading and path:
        heading, derived = headings_from_section_path(path)
        if not ancestors:
            ancestors = derived
    if heading and heading in ancestors:
        ancestors = [item for item in ancestors if item != heading]
    related = list(related_candidates or [])

    window = _window_text([*ancestors, heading, previous, candidate, nxt])
    refs = _unique(_scan_references(candidate))
    conditions = _unique(
        _scan_conditions(candidate) + _scan_conditions(previous) + _scan_conditions(nxt)
    )
    exceptions = _unique(
        _scan_exceptions(candidate) + _scan_exceptions(previous) + _scan_exceptions(nxt)
    )
    markers, targets = _scan_comparisons(candidate)
    if markers and not targets:
        _, window_targets = _scan_comparisons(window)
        targets = window_targets
    detected, _ = _detect_abbreviations(candidate)
    catalog = local_abbreviation_map(previous, candidate, nxt, heading, *ancestors)
    resolved = [token for token in detected if token in catalog]
    expand = propose_expand_merge(
        candidate_paragraph=candidate,
        previous_paragraph=previous,
        next_paragraph=nxt,
    )
    disposition = necessary_context_disposition(
        previous_paragraph=previous,
        next_paragraph=nxt,
        current_heading=heading,
        ancestor_headings=ancestors,
        expand_merge=expand,
        conditions=conditions,
        exceptions=exceptions,
        related_candidates=related,
    )
    return {
        "context_scan_done": True,
        "candidate_paragraph": candidate,
        "previous_paragraph": previous,
        "next_paragraph": nxt,
        "current_heading": heading,
        "ancestor_headings": ancestors,
        "section_path": path or ([*ancestors, heading] if heading else ancestors),
        "checked_signals": list(CHECKED_CONTEXT_SIGNALS),
        "necessary_context_disposition": disposition,
        "expand_merge": expand,
        "references_detected": refs,
        "references_resolved": [],
        "abbreviations_detected": detected,
        "abbreviations_resolved": resolved,
        "comparison_markers": _unique(markers),
        "comparison_targets": _unique(targets),
        "conditions_detected": conditions,
        "exceptions_detected": exceptions,
        "related_candidates": related,
        "reason_codes": [] if disposition != DISPOSITION_BLOCK else ["context_necessary_unresolved"],
    }


def apply_scan_to_candidate(candidate: dict[str, Any], scan: dict[str, Any]) -> dict[str, Any]:
    """Copy deep-scan fields onto a Phase-1 candidate record."""
    row = dict(candidate)
    row["context_scan"] = scan
    row["context_scan_done"] = True
    row["checked_signals"] = list(scan.get("checked_signals") or [])
    if scan.get("previous_paragraph"):
        row["context_before"] = scan["previous_paragraph"]
    if scan.get("next_paragraph"):
        row["context_after"] = scan["next_paragraph"]
    if scan.get("section_path") and not row.get("section_path"):
        row["section_path"] = list(scan["section_path"])
    # Candidate-scoped detections are source of truth. Neighbor-only
    # markers MUST NOT leak onto this candidate.
    row["references_detected"] = list(
        scan.get("references_detected") or row.get("references_detected") or []
    )
    row["abbreviations_detected"] = list(
        scan.get("abbreviations_detected") or row.get("abbreviations_detected") or []
    )
    row["comparison_markers"] = list(
        scan.get("comparison_markers") or row.get("comparison_markers") or []
    )
    row["abbreviations_resolved"] = _unique(
        list(row.get("abbreviations_resolved") or []) + list(scan.get("abbreviations_resolved") or [])
    )
    row["comparison_targets"] = _unique(
        list(row.get("comparison_targets") or []) + list(scan.get("comparison_targets") or [])
    )
    for key in ("conditions_detected", "exceptions_detected", "related_candidates"):
        incoming = list(scan.get(key) or [])
        existing = list(row.get(key) or [])
        row[key] = _unique(existing + incoming)
    if scan.get("expand_merge"):
        row["expand_merge"] = scan["expand_merge"]
    return row
