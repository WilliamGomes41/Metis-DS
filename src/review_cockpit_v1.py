"""Protocol v2.30 Phase 3 review-cockpit helpers (Block B).

Ordinary-language reviewer flow. Internal parent ids MAY remain in the
kernel. MUST NOT invent serving types. Passage register is Phase 4.
"""
from __future__ import annotations

import re
from typing import Any
from src.source_label_hint_v1 import source_label_hint

from src.admission_gate_v1 import admission_of, ordinary_review_queue, serving_type_for_admission_type
from src.heading_parent_list_v1 import (
    heading_visible_text,
    parent_choice_list,
    parent_proposal_may_bind,
    parse_outline_number,
)
from src.semantic_passage_v1 import (
    SELECTION_ORIGIN_COVERAGE,
    SELECTION_ORIGIN_PROPOSAL,
)

_BIND_OUTLINE_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?(?:\s+|$)")


def _normalize_heading_bind_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _heading_bind_title(text: str) -> str:
    return _BIND_OUTLINE_RE.sub("", _normalize_heading_bind_text(text)).strip()


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
    "recommendation": "Metis stelt voor deze passage als aanbeveling te beoordelen. Controleer dit aan de hand van de bron.",
    "definition": "Metis stelt voor deze passage als definitie te beoordelen. Controleer dit aan de hand van de bron.",
    "condition": "Metis stelt voor deze passage als voorwaarde te beoordelen. Controleer dit aan de hand van de bron.",
    "exception": "Metis stelt voor deze passage als uitzondering te beoordelen. Controleer dit aan de hand van de bron.",
    "explanation": "Metis stelt voor deze passage als toelichting te beoordelen. Controleer dit aan de hand van de bron.",
    "factual_finding": "Metis stelt voor deze passage als feitelijke constatering te beoordelen. Controleer dit aan de hand van de bron.",
    "heading": "Metis stelt voor deze passage als kop in de documentstructuur te beoordelen. Controleer de plaatsing aan de hand van de bron.",
    "path": "Deze passage is ingedeeld als pad: structuur voor een route of resultaatbundel. Controleer dit aan de hand van de bron.",
    "node": "Deze passage is ingedeeld als knoop. Controleer of dit een vraag, beslispunt, vertakkingskeuze of scorelijstitem is.",
    "outcome": "Deze passage is ingedeeld als uitkomst. Controleer of dit het afsluitende advies is en bij welke voorwaarden het hoort.",
}


def proposed_type_of(obj: dict[str, Any]) -> str:
    admission = admission_of(obj)
    return str(
        admission.get("proposed_type")
        or obj.get("proposed_object_type")
        or ""
    ).strip()


def semantic_passage_of(obj: dict[str, Any]) -> dict[str, Any]:
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    passage = metadata.get("semantic_passage")
    return passage if isinstance(passage, dict) else {}


def semantic_selection_origin(obj: dict[str, Any]) -> str:
    origin = str(semantic_passage_of(obj).get("selection_origin") or "").strip()
    if origin in {SELECTION_ORIGIN_PROPOSAL, SELECTION_ORIGIN_COVERAGE}:
        return origin
    return ""


def why_selected(obj: dict[str, Any], *, content_kind: str = "") -> str:
    proposed = proposed_type_of(obj)
    bundle = (obj.get("metadata") or {}).get("result_bundle") or {}
    if proposed in {"path", "node", "outcome"}:
        if bundle.get("role") == "container":
            return (
                "Deze opsomming is automatisch gegroepeerd als resultaatbundel (type Pad). "
                "Beoordeel hier de samenhang; beoordeel ieder onderdeel afzonderlijk op inhoud."
            )
        if bundle.get("role") == "member":
            return (
                "Dit onderdeel is automatisch afgesplitst uit een resultaatbundel (type Uitkomst). "
                "Controleer het advies en de voorwaarden van de bundel aan de hand van de bron."
            )
        if content_kind == "pdf" and proposed == "node":
            return (
                "Dit PDF-fragment heeft standaard het type Knoop gekregen bij het inlezen. "
                "Dit is geen inhoudelijke classificatie. Bepaal het juiste type aan de hand van de bron."
            )
    hint = source_label_hint(obj)
    if hint:
        return hint["guidance"]
    if semantic_selection_origin(obj) == SELECTION_ORIGIN_COVERAGE:
        return (
            "Deze brontekst is nog niet inhoudelijk beoordeeld. "
            "Bepaal aan de hand van de bron wat ermee moet gebeuren."
        )
    if proposed in WHY_SELECTED:
        return WHY_SELECTED[proposed]
    return "Metis stelt voor deze passage te beoordelen. Controleer dit aan de hand van de bron."


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
    semantic = semantic_passage_of(obj)
    origin = semantic_selection_origin(obj)
    selection_text = (
        str(content.get("raw_text") or content.get("clean_text") or "").strip()
        if origin
        else ""
    )
    spans = [
        dict(span)
        for span in (semantic.get("spans") or [])
        if isinstance(span, dict)
    ]
    return {
        "ancestor_headings": ancestors,
        "current_heading": heading,
        "previous_paragraph": previous,
        "source_text_exact": marked,
        "next_paragraph": nxt,
        "semantic_selection_origin": origin,
        "semantic_selection_text": selection_text,
        "semantic_spans": spans,
    }


def resolve_found_under_parent(obj: dict[str, Any], objects: list[dict[str, Any]]) -> str:
    path = found_under_path(obj)
    if not path:
        return ""
    last = _normalize_heading_bind_text(path.split(" › ")[-1])
    if not last:
        return ""
    last_title = _heading_bind_title(last)
    last_outline = parse_outline_number(last)
    matches: list[dict[str, Any]] = []
    for row in parent_choice_list(objects):
        text = heading_visible_text(row)
        if not text:
            continue
        if last_title:
            if _heading_bind_title(text) == last_title:
                matches.append(row)
        elif text == last:
            matches.append(row)
    chosen: dict[str, Any] | None = None
    if len(matches) == 1:
        chosen = matches[0]
    elif last_outline is not None:
        outlined = [
            row
            for row in matches
            if parse_outline_number(heading_visible_text(row)) == last_outline
        ]
        if len(outlined) == 1:
            chosen = outlined[0]
    if chosen is None:
        return ""
    if not parent_proposal_may_bind(obj, chosen, objects):
        return ""
    return str(chosen.get("object_id") or "")


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
    bindings=None,
    fragments=None,
) -> str:
    queue = ordinary_review_queue(objects, review_path=review_path, bindings=bindings, fragments=fragments)
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


def knowledge_review_projection(obj, objects):
    """One lossless projection of the durable revision for both review passes."""
    from copy import deepcopy
    from src.admission_gate_v1 import admission_of
    from src.context_scan_v1 import required_context
    from src.source_context_review_v1 import links_of, context_issues
    admission = admission_of(obj)
    realization = admission.get('context_realization') or {}
    essential = []
    for row in required_context(admission.get('context_scan') or {}):
        proof = next((item for item in realization.get('realized') or []
                      if item.get('text') == row['text'] and item.get('role') == row['role']), None)
        if proof and proof.get('realization') == 'inline':
            continue  # Already visible in the full, lossless core passage.
        essential.append({**row, 'status': 'bound' if proof else 'unresolved'})
    from src.source_bound_fields_v2 import CONTEXT_KEY, context_matches_target
    record = (obj.get('metadata') or {}).get(CONTEXT_KEY) or {}
    for entry in record.get('entries') or []:
        if entry.get('role') != 'support':
            essential.append({'role': entry.get('role'), 'text': entry.get('text'),
                              'status': 'stale' if not context_matches_target(obj) else
                                        'unresolved' if entry.get('unresolved_reason') else 'bound'})
    stale = context_issues(objects).get(str(obj.get('object_id') or ''), [])
    for link in links_of(obj):
        present = next((row for row in essential if row.get('text') == link.get('text')), None)
        if present:
            present['source_object_id'] = link.get('source_object_id')
            if stale:
                present['status'] = 'stale'
            continue
        essential.append({'role': link.get('role'), 'text': link.get('text'),
                          'status': 'stale' if stale else 'bound',
                          'source_object_id': link.get('source_object_id')})
    for row in realization.get('unresolved') or []:
        if not any(e['text'] == row['text'] for e in essential):
            essential.append({**deepcopy(row), 'status': 'unresolved'})
    merge = admission.get('expand_merge') or {}
    proposal = str(merge.get('merged_text') or '')
    text = str((obj.get('content') or {}).get('clean_text') or '')
    return {'object_id': obj.get('object_id'), 'object_version': obj.get('object_version'),
            'object_type': obj.get('confirmed_object_type') or obj.get('proposed_object_type') or obj.get('object_type'),
            'canonical_hash': (obj.get('provenance') or {}).get('canonical_object_hash'),
            'text': text, 'essential_context': essential,
            'proposal': proposal if proposal and proposal != text else '',
            'unresolved_reasons': list(dict.fromkeys(list(admission.get('reason_codes') or []) + stale)),
            'source_hash': (obj.get('source') or {}).get('source_checksum'),
            'semantic_completeness': 'not_proven'}
