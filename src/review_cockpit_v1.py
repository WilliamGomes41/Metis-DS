"""Protocol v2.30 Phase 3 review-cockpit helpers (Block B).

Ordinary-language reviewer flow. Internal parent ids MAY remain in the
kernel. MUST NOT invent serving types. Passage register is Phase 4.
"""
from __future__ import annotations

from typing import Any

from src.admission_gate_v1 import admission_of, ordinary_review_queue, serving_type_for_admission_type
from src.heading_parent_list_v1 import heading_visible_text, parent_choice_list


SUITABILITY_VALUES = (
    "ja",
    "mist_context",
    "samenvoegen",
    "alleen_onderbouwing",
    "geen_kenniseenheid",
)
EINDOORDEEL_VALUES = (
    "goedkeuren",
    "goedkeuren_na_correctie",
    "afwijzen",
    "later_beoordelen",
)
EINDOORDEEL_TO_DECISION = {
    "goedkeuren": "approve",
    "goedkeuren_na_correctie": "revise",
    "afwijzen": "reject",
    "later_beoordelen": "later",
}
WHY_SELECTED = {
    "recommendation": "Geselecteerd omdat dit een volledige aanbeveling is.",
    "definition": "Geselecteerd omdat dit een definitie is.",
    "condition": "Geselecteerd omdat dit een voorwaarde is.",
    "exception": "Geselecteerd omdat dit een uitzondering is.",
    "explanation": "Geselecteerd omdat dit een toelichting is.",
    "factual_finding": "Geselecteerd omdat dit een feitelijke constatering is.",
    "heading": "Geselecteerd als kop in de documentstructuur.",
    "path": "Geselecteerd omdat dit een pad is.",
    "node": "Geselecteerd omdat dit een knoop is.",
    "outcome": "Geselecteerd omdat dit een uitkomst is.",
}


def proposed_type_of(obj: dict[str, Any]) -> str:
    admission = admission_of(obj)
    return str(
        admission.get("proposed_type")
        or obj.get("proposed_object_type")
        or ""
    ).strip()


def why_selected(obj: dict[str, Any]) -> str:
    proposed = proposed_type_of(obj)
    if proposed in WHY_SELECTED:
        return WHY_SELECTED[proposed]
    return "Geselecteerd omdat dit een bruikbare passage is."


def confirmable_proposed_type(obj: dict[str, Any]) -> str:
    proposed = proposed_type_of(obj)
    if not proposed:
        return ""
    if proposed == "heading":
        return "heading"
    return serving_type_for_admission_type(proposed)


def found_under_path(obj: dict[str, Any]) -> str:
    admission = admission_of(obj)
    scan = admission.get("context_scan") if isinstance(admission.get("context_scan"), dict) else {}
    path = [str(part).strip() for part in (admission.get("section_path") or []) if str(part).strip()]
    if not path:
        path = [
            str(part).strip()
            for part in ((obj.get("structure") or {}).get("section_path") or [])
            if str(part).strip()
        ]
    if not path:
        ancestors = [
            str(item).strip()
            for item in (scan.get("ancestor_headings") or admission.get("ancestor_headings") or [])
            if str(item).strip()
        ]
        heading = str(scan.get("current_heading") or admission.get("current_heading") or "").strip()
        path = [*ancestors, heading] if heading else ancestors
    seen: list[str] = []
    for part in path:
        if part and part not in seen:
            seen.append(part)
    return " › ".join(seen)


def broncontext_parts(obj: dict[str, Any]) -> dict[str, Any]:
    admission = admission_of(obj)
    scan = admission.get("context_scan") if isinstance(admission.get("context_scan"), dict) else {}
    ancestors = [
        str(item).strip()
        for item in (scan.get("ancestor_headings") or admission.get("ancestor_headings") or [])
        if str(item).strip()
    ]
    heading = str(scan.get("current_heading") or admission.get("current_heading") or "").strip()
    if not heading:
        path = found_under_path(obj)
        if path:
            heading = path.split(" › ")[-1]
    previous = str(
        scan.get("previous_paragraph")
        or admission.get("previous_paragraph")
        or admission.get("context_before")
        or ""
    ).strip()
    nxt = str(
        scan.get("next_paragraph")
        or admission.get("next_paragraph")
        or admission.get("context_after")
        or ""
    ).strip()
    content = obj.get("content") or {}
    fallback = str(content.get("clean_text") or content.get("raw_text") or "").strip()
    marked = str(
        admission.get("source_text_exact")
        or obj.get("source_text_exact")
        or fallback
        or ""
    ).strip()
    return {
        "ancestor_headings": ancestors,
        "current_heading": heading,
        "previous_paragraph": previous,
        "source_text_exact": marked,
        "next_paragraph": nxt,
    }


def resolve_found_under_parent(obj: dict[str, Any], objects: list[dict[str, Any]]) -> str:
    path = found_under_path(obj)
    if not path:
        return ""
    last = path.split(" › ")[-1].strip()
    for row in parent_choice_list(objects):
        text = heading_visible_text(row)
        if text == last or last in text or text in last:
            return str(row.get("object_id") or "")
    return ""


def map_eindoordeel(eindoordeel: str, decision: str = "") -> str:
    mapped = EINDOORDEEL_TO_DECISION.get((eindoordeel or "").strip(), "")
    if mapped:
        return mapped
    return (decision or "").strip()


def next_ordinary_object_id(
    objects: list[dict[str, Any]],
    current_id: str,
    *,
    review_path: str | None = None,
) -> str:
    queue = ordinary_review_queue(objects, review_path=review_path)
    ids = [str(obj.get("object_id") or "") for obj in queue if obj.get("object_id")]
    if current_id in ids:
        index = ids.index(current_id)
        if index + 1 < len(ids):
            return ids[index + 1]
    return ""


def review_passage_requested(
    *,
    suitability: str = "",
    eindoordeel: str = "",
    type_action: str = "",
    documentpositie_action: str = "",
    found_under: str = "",
    parent_choice: str = "",
) -> bool:
    """True only when the reviewer actually sent Phase-3 cockpit fields."""
    return any(
        (value or "").strip()
        for value in (
            suitability,
            eindoordeel,
            type_action,
            documentpositie_action,
            found_under,
            parent_choice,
        )
    )


def merge_heading_parent_relations(
    existing: list[dict[str, Any]] | None,
    parent_id: str,
) -> list[dict[str, Any]]:
    """Keep confirmed semantic relations; replace only parent/child structure."""
    kept = [
        dict(row)
        for row in (existing or [])
        if row.get("relation_type") not in {"parent", "child"}
    ]
    parent = (parent_id or "").strip()
    if parent:
        kept.append({"relation_type": "child", "target_object_id": parent})
    return kept


def review_passage_record(
    *,
    suitability: str = "",
    eindoordeel: str = "",
    type_action: str = "",
    documentpositie_action: str = "",
    found_under: str = "",
    parent_object_id: str = "",
) -> dict[str, Any]:
    return {
        "suitability": (suitability or "").strip(),
        "eindoordeel": (eindoordeel or "").strip(),
        "type_action": (type_action or "").strip(),
        "documentpositie_action": (documentpositie_action or "").strip(),
        "found_under": (found_under or "").strip(),
        "documentpositie": {
            "path": (found_under or "").strip(),
            "parent_object_id": (parent_object_id or "").strip(),
        },
    }
