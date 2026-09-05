"""Protocol v2.30 Phase 4 passage register.

Closed statuses only. MUST NOT silently drop passages. MUST NOT become a
Phase-1 admission prerequisite. Phase 3 suitability maps onto register
outcomes. Operators MUST NOT invent serving types.
"""
from __future__ import annotations

from typing import Any

from src.admission_gate_v1 import (
    GATE_ALLOWED,
    GATE_BLOCKED,
    admission_of,
    is_boom_object,
    is_inhoudelijk_candidate,
)
from src.review_cockpit_v1 import SUITABILITY_VALUES


PASSAGE_REGISTER_STATUSES = (
    "selected_as_candidate",
    "used_as_context",
    "linked_as_support",
    "excluded_with_reason",
    "not_yet_assessed",
)

SUITABILITY_TO_REGISTER = {
    "ja": "selected_as_candidate",
    "mist_context": "used_as_context",
    "samenvoegen": "used_as_context",
    "alleen_onderbouwing": "linked_as_support",
    "geen_kenniseenheid": "excluded_with_reason",
}

UNKNOWN_REGISTER_STATUS = "unknown_passage_register_status"


def passage_register_of(obj: dict[str, Any]) -> dict[str, Any]:
    md = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    row = md.get("passage_register")
    return row if isinstance(row, dict) else {}


def register_status_from_suitability(suitability: str) -> str:
    status = SUITABILITY_TO_REGISTER.get((suitability or "").strip())
    if not status:
        raise ValueError(UNKNOWN_REGISTER_STATUS)
    return status


def _require_status(status: str) -> str:
    token = (status or "").strip()
    if token not in PASSAGE_REGISTER_STATUSES:
        raise ValueError(UNKNOWN_REGISTER_STATUS)
    return token


def passage_register_record(
    *,
    status: str,
    reason_codes: list[str] | None = None,
    suitability: str = "",
    source: str = "extract",
    linked_object_id: str = "",
    section_path: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": _require_status(status),
        "reason_codes": [str(code) for code in (reason_codes or []) if str(code).strip()],
        "suitability": (suitability or "").strip(),
        "source": (source or "extract").strip() or "extract",
        "linked_object_id": (linked_object_id or "").strip(),
        "section_path": [str(part).strip() for part in (section_path or []) if str(part).strip()],
    }


def _text_of(obj: dict[str, Any]) -> str:
    content = obj.get("content") if isinstance(obj.get("content"), dict) else {}
    return str(content.get("clean_text") or obj.get("candidate_text") or "").strip()


def section_path_of(obj: dict[str, Any]) -> list[str]:
    structure = obj.get("structure") if isinstance(obj.get("structure"), dict) else {}
    path = [str(part).strip() for part in (structure.get("section_path") or []) if str(part).strip()]
    if path:
        return path
    admission = admission_of(obj)
    return [str(part).strip() for part in (admission.get("section_path") or []) if str(part).strip()]


def _is_heading(obj: dict[str, Any]) -> bool:
    return obj.get("object_type") == "heading" or obj.get("proposed_object_type") == "heading"


def _context_heading_texts(objects: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for obj in objects:
        admission = admission_of(obj)
        scan = admission.get("context_scan") if isinstance(admission.get("context_scan"), dict) else {}
        heading = str(scan.get("current_heading") or admission.get("current_heading") or "").strip()
        if heading:
            found.add(heading)
        for item in scan.get("ancestor_headings") or admission.get("ancestor_headings") or []:
            blob = str(item).strip()
            if blob:
                found.add(blob)
    return found


def _initial_status(obj: dict[str, Any], *, context_headings: set[str]) -> tuple[str, list[str]]:
    existing = passage_register_of(obj)
    if existing.get("source") == "review" and existing.get("status") in PASSAGE_REGISTER_STATUSES:
        return str(existing["status"]), list(existing.get("reason_codes") or [])
    admission = admission_of(obj)
    gate = admission.get("gate_result")
    reasons = [str(code) for code in (admission.get("reason_codes") or []) if str(code).strip()]
    if gate == GATE_BLOCKED:
        return "excluded_with_reason", reasons
    if is_boom_object(obj):
        return "selected_as_candidate", []
    if is_inhoudelijk_candidate(obj) and gate == GATE_ALLOWED:
        expand = admission.get("expand_merge") if isinstance(admission.get("expand_merge"), dict) else {}
        proposed = str(obj.get("proposed_object_type") or admission.get("proposed_type") or "")
        if proposed == "explanation" or (proposed == "exception" and expand.get("performed")):
            return "linked_as_support", []
        return "selected_as_candidate", []
    if _is_heading(obj):
        text = _text_of(obj)
        if text and any(text == heading or text in heading or heading in text for heading in context_headings):
            return "used_as_context", []
        return "not_yet_assessed", []
    return "not_yet_assessed", []


def apply_passage_register(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stamp a closed register status on every non-document passage."""
    for obj in objects:
        if obj.get("object_type") == "document":
            continue
        existing = passage_register_of(obj)
        if existing.get("status"):
            _require_status(str(existing.get("status") or ""))
    context_headings = _context_heading_texts(objects)
    out: list[dict[str, Any]] = []
    for obj in objects:
        row = obj
        if obj.get("object_type") != "document":
            existing = passage_register_of(obj)
            if existing.get("source") == "review" and existing.get("status") in PASSAGE_REGISTER_STATUSES:
                status = str(existing["status"])
                reasons = list(existing.get("reason_codes") or [])
                source = "review"
                suitability = str(existing.get("suitability") or "")
            else:
                status, reasons = _initial_status(obj, context_headings=context_headings)
                source = "extract"
                suitability = ""
            row = dict(obj)
            metadata = dict(row.get("metadata") or {})
            metadata["passage_register"] = passage_register_record(
                status=status,
                reason_codes=reasons,
                suitability=suitability,
                source=source,
                linked_object_id=str(existing.get("linked_object_id") or ""),
                section_path=section_path_of(row),
            )
            row["metadata"] = metadata
        out.append(row)
    return out


def apply_register_from_review(
    obj: dict[str, Any],
    *,
    suitability: str = "",
) -> dict[str, Any]:
    token = (suitability or "").strip()
    if token not in SUITABILITY_VALUES:
        return obj
    status = register_status_from_suitability(token)
    existing = passage_register_of(obj)
    reasons = list(existing.get("reason_codes") or [])
    if status == "excluded_with_reason":
        admission = admission_of(obj)
        reasons = reasons or [str(code) for code in (admission.get("reason_codes") or []) if str(code).strip()]
        if "geen_kenniseenheid" not in reasons:
            reasons.append("geen_kenniseenheid")
    row = dict(obj)
    metadata = dict(row.get("metadata") or {})
    metadata["passage_register"] = passage_register_record(
        status=status,
        reason_codes=reasons,
        suitability=token,
        source="review",
        linked_object_id=str(existing.get("linked_object_id") or ""),
        section_path=section_path_of(row),
    )
    row["metadata"] = metadata
    return row
