"""Source-range accountability for recommendation sections, not recall truth.

Derived from existing source blocks/proposals. Open items remain in the passage
register; this is not another durable authority or an automatic exclusion.
"""
from __future__ import annotations

import re
from copy import deepcopy

VERSION = "recommendation-coverage-v1"
KEY = "recommendation_coverage"
_NUMBER = re.compile(r"(?<!\w)\d{1,3}[.)]\s+(?=[A-ZÀ-Ý])")
_NORMATIVE = re.compile(
    r"^(?:Breng|Overweeg|Gebruik|Stel|Zet|Pas|Evalueer|Consulteer|Wees|Controleer|"
    r"Bespreek|Verwijs|Start|Stop|Vermijd|Houd|Neem|Bied|Adviseer|Beoordeel|Monitor|"
    r"Meet|Geef|Vraag|Onderzoek|Leg|Voorkom|Mobiliseer|Wij bevelen|Het wordt aanbevolen)\b"
)
_STAMP = re.compile(r"\b(?:Sterk|Zwak)\s*[–—-]\s*(?:voor|tegen)\b\.?", re.I)


def inventory(blocks):
    result = []
    active_scope = None
    active_path = None
    for block in blocks:
        path = list(block.get("section_path") or [])
        if not any(re.fullmatch(r"(?:\d+(?:\.\d+)*[.)]?\s*)?(?:aanbevelingen|recommendations)\s*:?", p.strip(), re.I) for p in path):
            continue
        text = block["text"]
        if path != active_path:
            active_scope = None
            active_path = path
        scope_label = text.rstrip().endswith(":") and len(text) < 240 and not _NORMATIVE.search(text.lstrip())
        if scope_label:
            active_scope = {"block_id": block["block_id"], "start": 0, "end": len(text), "text": text}
        numbers = [m for m in _NUMBER.finditer(text)
                   if not re.search(r"\b(?:Tabel|Table|Bijlage|Figuur)\s*$", text[:m.start()], re.I)]
        starts = [m.end() for m in numbers]
        if not starts and _NORMATIVE.search(text.lstrip()):
            starts = [len(text) - len(text.lstrip())]
        if not starts and not scope_label:
            # A descriptive list/body breaks the adjacency of a possible
            # scope label. Do not carry it into unrelated later advice.
            active_scope = None
        for index, start in enumerate(starts):
            end = numbers[index + 1].start() if numbers and index + 1 < len(numbers) else len(text)
            stamp = _STAMP.search(text, start, end)
            if stamp:
                end = stamp.start()
            while end > start and text[end-1].isspace():
                end -= 1
            if end > start:
                result.append({"span": {"block_id": block["block_id"], "start": start, "end": end},
                               "text": text[start:end], "section_path": path,
                               "scope_cue": deepcopy(active_scope)})
    return result


def assess(blocks, proposal):
    rows = inventory(blocks)
    selected = [(index, span) for index, obj in enumerate(proposal.get("objects") or [])
                if obj.get("proposed_object_type") == "recommendation" for span in obj.get("spans") or []]
    for row in rows:
        ref = row["span"]
        owners = sorted({index for index, span in selected if span["block_id"] == ref["block_id"]
                         and span["start"] <= ref["start"] and span["end"] >= ref["end"]})
        contextual = any(s.get("span") and not s.get("unresolved_reason")
            and s["span"]["block_id"] == ref["block_id"] and s["span"]["start"] <= ref["start"]
            and s["span"]["end"] >= ref["end"] for obj in proposal.get("objects") or []
            for s in obj.get("context_evidence") or [])
        row.update(status="selected" if owners else "used_as_context" if contextual else "open", proposal_indices=owners)
    return {"version": VERSION, "detection_completeness": "not_proven", "entries": rows}


def supplementary_blocks(blocks, report):
    open_ids = {r["span"]["block_id"] for r in report["entries"] if r["status"] == "open"}
    return [b for b in blocks if b["block_id"] in open_ids]


def merge_proposals(primary, supplement):
    """Deduplicate identical source selections; reject conflicting overlap.

    Do not merge index-based relations across two provider responses. Each
    relation already refers to source spans, but supplement relations may point
    to an object absent from its own response and are validated after merging.
    """
    from src.operations_console_v1 import ConsoleError
    result = deepcopy(primary)
    objects = result["objects"]
    for obj in supplement["objects"]:
        signature = obj["spans"]
        match = next((existing for existing in objects if existing["spans"] == signature), None)
        if match is not None:
            if match != obj:
                raise ConsoleError("pre_review_llm_proposal_rejected", "semantic_supplement_conflict")
            continue
        for existing in objects:
            if any(a["block_id"] == b["block_id"] and max(a["start"], b["start"]) < min(a["end"], b["end"])
                   for a in signature for b in existing["spans"]):
                raise ConsoleError("pre_review_llm_proposal_rejected", "semantic_supplement_overlap")
        objects.append(deepcopy(obj))
    for relation in supplement.get("relations") or []:
        if relation not in result["relations"]:
            result["relations"].append(deepcopy(relation))
    return result


def attach(units, report):
    """Attach each open range to its existing coverage-remainder owner(s)."""
    for unit in units:
        semantic = unit.get("semantic_passage") or {}
        entries = []
        for row in report["entries"]:
            ref = row["span"]
            if any(s["block_id"] == ref["block_id"]
                   and max(s["start"], ref["start"]) < min(s["end"], ref["end"])
                   for s in semantic.get("spans") or []):
                entries.append(deepcopy(row))
        if entries:
            unit[KEY] = {"version": VERSION, "detection_completeness": "not_proven", "entries": entries}
