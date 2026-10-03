"""Literal decision units before review; no durable state or generated source text.

Layout supplies grouping evidence, never routing authority. Unknown constructions
remain source passages in the existing repair lane and decision evidence inventory.
"""
from __future__ import annotations

from copy import deepcopy
from bisect import bisect_left, bisect_right
from collections import defaultdict
import re
from src.integrity_kernel import stable_hash

CONTRACT = "decision-unit-construction-v1"
KEY = "decision_unit_construction"
LABELS = frozenset({"ja", "nee", "yes", "no"})
TRAILING = re.compile(r"\b(?:een|de|het|van|in|op|over|voor|met|naar|en|of|zich|als|indien|wanneer)\s*$", re.I)
ACTION = re.compile(r"^(?:[•*\-]\s*)?(?:bespreek|adviseer|verwijs|start|stop|maak|neem|plan|controleer|bepaal|overweeg|signaleer|vraag|bied|geef|informeer|ondersteun|geen actie)\b", re.I)
QUESTION = re.compile(r"^(?:is|zijn|heeft|hebben|kan|kunnen|mag|mogen|moet|moeten|hoe|wat|waar|welke|wie|waarom|wanneer|uit)\b", re.I)
INSTRUCTION = re.compile(r"\b(?:signaleren|bespreken|identificeren|vaststellen|verwijzen|ondersteunen|evalueren|controleren)\s*$", re.I)


def branch_label(text: str) -> bool:
    return text.strip().casefold() in LABELS


def add_layout(path, fragments):
    """Retain enclosure and typography evidence without modifying source identity."""
    import fitz
    by_page = defaultdict(list)
    for fragment in fragments:
        by_page[fragment.get("source_page")].append(fragment)
    with fitz.open(path) as doc:
        for number, page in enumerate(doc, 1):
            enclosures = []
            for drawing in page.get_drawings():
                # Only an explicit closed rectangle, not the bounding box of a line.
                for item in drawing["items"]:
                    if item[0] == "re":
                        enclosures.append(list(item[1]))
            blocks = {tuple(b["bbox"]): b for b in page.get_text("dict")["blocks"] if b["type"] == 0}
            for f in by_page[number]:
                box = f.get("bbox")
                if not box:
                    continue
                containers = [r for r in enclosures if r[0] <= box[0] and r[1] <= box[1]
                              and r[2] >= box[2] and r[3] >= box[3]]
                containers.sort(key=lambda r: (r[2]-r[0])*(r[3]-r[1]))
                block = blocks.get(tuple(box), {})
                styles = sorted({(s["font"], round(s["size"], 2)) for line in block.get("lines", [])
                                 for s in line.get("spans", []) if s["text"].strip()})
                f["_decision_layout"] = {"container": containers[0] if containers else None,
                                          "styles": styles}
                f["_decision_lines"] = [{"text": "".join(s["text"] for s in line["spans"]),
                                          "bbox": list(line["bbox"]),
                                          "styles": sorted({(s["font"], round(s["size"], 2)) for s in line["spans"] if s["text"].strip()})}
                                         for line in block.get("lines", [])]


def source_lines(fragments):
    """Undo PDF blocks that contain parallel boxes; retain exact parent spans."""
    from src.extract_pdf_v2 import clean_text, page_bbox_locator
    from src.decision_bundles_v1 import BULLET
    output = []
    for f in fragments:
        lines = f.get("_decision_lines", [])
        if len(lines) < 2 or len(list(BULLET.finditer(f["clean_text"]))) >= 2:
            output.append(f)
            continue
        cursor = 0
        for index, line in enumerate(lines):
            raw = line["text"].strip()
            if not raw:
                continue
            start = f["raw_text"].find(raw, cursor)
            if start < 0:
                raise ValueError("decision_unit_parent_span_invalid")
            end = start + len(raw)
            cursor = end
            child = deepcopy(f)
            child["fragment_id"] = child["boom_id"] = f'{f["fragment_id"]}-line-{index+1}'
            child["raw_text"], child["clean_text"] = raw, clean_text(raw)
            child["bbox"] = line["bbox"]
            child["source_locator"] = page_bbox_locator(f["source_page"], line["bbox"])
            child["_decision_layout"]["styles"] = line["styles"]
            child["_decision_parent"] = {"fragment_id": f["fragment_id"], "raw_start": start, "raw_end": end,
                                         "raw_span_text": raw, "raw_content_hash": stable_hash(f["raw_text"]),
                                         "locator": deepcopy(f["source_locator"])}
            child.pop("_decision_lines", None)
            child["fragment_hash"] = stable_hash({k:v for k,v in child.items() if k != "fragment_hash"})
            output.append(child)
    return output


def _complete(text):
    blob = re.sub(r"\s+", " ", text).strip()
    if not blob or TRAILING.search(blob.rstrip("?!.:* ")):
        return False
    if re.search(r"\?[*]*$", blob):
        return bool(QUESTION.search(blob))
    return bool(re.search(r"[!.][*]*$", blob) or ACTION.search(blob)
                or (INSTRUCTION.search(blob) and " " in blob))


def _continues(left, right):
    a, b = left["clean_text"].strip(), right["clean_text"].strip()
    if branch_label(a) or branch_label(b) or _complete(a):
        return False
    if re.search(r"[?!.][*]*$", a) or ACTION.search(b):
        return False
    if not b or not b[0].islower():
        return False
    # A dangling grammatical link plus independently verified visual signals.
    return bool(TRAILING.search(a) or re.match(r"^(?:is|zijn|heeft|hebben|kan|kunnen|uit|ervaar)\b", a, re.I)
                or left.get("_decision_layout", {}).get("container"))


def _compatible(left, right):
    if left.get("source_page") != right.get("source_page") or left.get("bundle_role") or right.get("bundle_role"):
        return False
    a, b = left.get("bbox"), right.get("bbox")
    if not a or not b:
        return False
    la, lb = left.get("_decision_layout", {}), right.get("_decision_layout", {})
    if la.get("container") != lb.get("container"):
        return False
    if not la.get("styles") or la.get("styles") != lb.get("styles"):
        return False
    height = min(a[3]-a[1], b[3]-b[1])
    if height <= 0:
        return False
    # Scale relative to the actual line height; spacing alone never merges.
    aligned = abs(a[0]-b[0]) <= height * .6 or abs((a[0]+a[2])-(b[0]+b[2])) <= height
    return aligned and -.1*height <= b[1]-a[3] <= height*.9 and _continues(left, right)


def groups(fragments):
    """Unique predecessor/successor only; ambiguity is never broken by order."""
    rows = sorted(fragments, key=lambda f: (f.get("source_page") or 0,
                   (f.get("bbox") or [0, 0])[1], (f.get("bbox") or [0])[0], f["fragment_id"]))
    followers, predecessors = {}, {}
    pages = defaultdict(list)
    for row in rows:
        if row.get("bbox"):
            pages[row.get("source_page")].append(row)
    tops = {page: [r["bbox"][1] for r in page_rows] for page, page_rows in pages.items()}
    for left in rows:
        box = left.get("bbox")
        if not box:
            continue
        height = box[3]-box[1]
        page = left.get("source_page")
        candidates = pages[page][bisect_left(tops[page], box[3]-.1*height):
                                 bisect_right(tops[page], box[3]+.9*height)]
        for right in candidates:
            if left is not right and _compatible(left, right):
                followers.setdefault(left["fragment_id"], []).append(right)
                predecessors.setdefault(right["fragment_id"], []).append(left)
    links = {fid: choices[0] for fid, choices in followers.items()
             if len(choices) == 1 and len(predecessors[choices[0]["fragment_id"]]) == 1}
    consumed, result = set(), []
    for f in rows:
        if f["fragment_id"] in consumed:
            continue
        unit, current = [f], f
        consumed.add(f["fragment_id"])
        while current["fragment_id"] in links:
            following = links[current["fragment_id"]]
            if following["fragment_id"] in consumed:
                break
            unit.append(following)
            consumed.add(following["fragment_id"])
            current = following
        result.append(unit)
    return result


def record(unit):
    text = "\n".join(f["clean_text"] for f in unit)
    role = "branch_label" if branch_label(text) else "question" if re.search(r"\?[*]*$", text.strip()) else "action" if ACTION.search(text.strip()) or INSTRUCTION.search(text.strip()) else "unresolved"
    reasons = []
    if role == "branch_label":
        reasons.append("decision_branch_label_not_node")
    elif not _complete(text):
        reasons.append("decision_unit_incomplete")
    spans = [{"fragment_id": f["fragment_id"], "start": 0, "end": len(f["clean_text"]),
              "fragment_text_hash": stable_hash(f["clean_text"]),
              "source_fragment_hash": f.get("fragment_hash"),
              "text_sha256": stable_hash(f["clean_text"]), "locator": deepcopy(f["source_locator"]),
              **({"parent": deepcopy(f["_decision_parent"])} if f.get("_decision_parent") else {})} for f in unit]
    return {"contract": CONTRACT, "spans": spans, "separator": "\n", "literal_hash": stable_hash(text),
            "role": role, "reason_codes": reasons,
            "grouping_evidence": [{"fragment_id": f["fragment_id"],
                                   "layout": deepcopy(f.get("_decision_layout", {}))} for f in unit]}


def reconstruct(evidence, fragments):
    if not isinstance(evidence, dict) or evidence.get("contract") != CONTRACT or evidence.get("separator") != "\n":
        raise ValueError("decision_unit_evidence_invalid")
    by_id = fragments if isinstance(fragments, dict) else {f["fragment_id"]: f for f in fragments}
    spans = evidence.get("spans")
    if not isinstance(spans, list) or not spans:
        raise ValueError("decision_unit_evidence_invalid")
    used, pieces = set(), []
    for s in spans:
        f = by_id.get(s.get("fragment_id")) if isinstance(s, dict) else None
        if not f or s["fragment_id"] in used:
            raise ValueError("decision_unit_source_fidelity_failure")
        start, end = s.get("start"), s.get("end")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(f["clean_text"]):
            raise ValueError("decision_unit_source_fidelity_failure")
        piece = f["clean_text"][start:end]
        if s.get("fragment_text_hash") != stable_hash(f["clean_text"]):
            raise ValueError("decision_unit_source_fidelity_failure")
        if s.get("source_fragment_hash") != f.get("fragment_hash"):
            raise ValueError("decision_unit_source_fidelity_failure")
        if s.get("locator") != f["source_locator"] or s.get("text_sha256") != stable_hash(piece):
            raise ValueError("decision_unit_source_fidelity_failure")
        if s.get("parent") != f.get("_decision_parent"):
            raise ValueError("decision_unit_source_fidelity_failure")
        if s.get("parent"):
            parent = s["parent"]
            if parent["raw_span_text"] != f["raw_text"] or parent["raw_end"]-parent["raw_start"] != len(f["raw_text"]):
                raise ValueError("decision_unit_source_fidelity_failure")
        used.add(s["fragment_id"])
        pieces.append(piece)
    text = "\n".join(pieces)
    if stable_hash(text) != evidence.get("literal_hash"):
        raise ValueError("decision_unit_source_fidelity_failure")
    return text


def construction_spec(spec, fragments):
    """Replace block proposals with literal units, keeping original raw fragments."""
    output = deepcopy(spec)
    by_id = {f["fragment_id"]: f for f in fragments}
    original = {item["source_fragment_ids"][0]: item for item in spec["objects"] if item.get("source_fragment_ids")}
    items = [deepcopy(item) for item in spec["objects"] if item["object_type"] == "document"]
    for unit in groups(fragments):
        item = deepcopy(original[unit[0]["fragment_id"]])
        evidence = record(unit)
        text = reconstruct(evidence, by_id)
        if len(unit) > 1:
            item["object_id"] = f'{spec["document_id"]}-unit-{stable_hash(evidence["spans"])[:20]}'
        item.update(text=text, clean_text=text, source_fragment_ids=[f["fragment_id"] for f in unit])
        item["metadata"] = {KEY: evidence}
        if evidence["role"] == "branch_label":
            item.pop("proposed_object_type", None)
        item["risk_fields"] = sorted({v for f in unit for v in f.get("risk_fields", [])})
        items.append(item)
    output["objects"] = items
    return output


def unit_issues(obj):
    evidence = (obj.get("metadata") or {}).get(KEY)
    if not evidence:
        return []  # Legacy snapshots and explicit freezes keep their contract.
    if not isinstance(evidence, dict) or evidence.get("contract") != CONTRACT or not isinstance(evidence.get("spans"), list) or not evidence["spans"]:
        return ["decision_unit_evidence_invalid"]
    text = str((obj.get("content") or {}).get("clean_text") or "")
    issues = []
    if stable_hash(text) != evidence.get("literal_hash"):
        issues.append("decision_unit_source_fidelity_failure")
    if branch_label(text):
        issues.append("decision_branch_label_not_node")
    elif not _complete(text) and not (obj.get("metadata") or {}).get("result_bundle"):
        issues.append("decision_unit_incomplete")
    source_ids = [r["raw_object_id"] for r in obj.get("provenance", {}).get("source_fragments", [])]
    if source_ids != [s.get("fragment_id") for s in evidence.get("spans", [])]:
        issues.append("decision_unit_source_fidelity_failure")
    for ref, span in zip(obj.get("provenance", {}).get("source_fragments", []), evidence["spans"]):
        if ref.get("source_locator") != span.get("locator") or ref.get("raw_content_hash") != span.get("source_fragment_hash"):
            issues.append("decision_unit_source_fidelity_failure")
    return sorted(set(issues))


def rebuild_for_revision(original, revised, fragments):
    """Rebuild only an explicit literal selection from verified immutable input.

    Whole-fragment merges retain the v1 newline representation. A single
    fragment may be narrowed to one unique literal substring. No fuzzy match,
    metadata patch or stale construction proof is accepted.
    """
    by_id = {f["fragment_id"]: f for f in fragments}
    reconstruct(original["metadata"][KEY], by_id)
    if "decision_unit_source_fidelity_failure" in unit_issues(original):
        raise ValueError("decision_unit_source_fidelity_failure")
    unit = []
    for ref in revised.get("provenance", {}).get("source_fragments", []):
        fragment = by_id.get(ref.get("raw_object_id"))
        if (not fragment or ref.get("raw_content_hash") != fragment.get("fragment_hash")
                or ref.get("source_locator") != fragment["source_locator"]
                or fragment in unit):
            raise ValueError("decision_unit_source_fidelity_failure")
        unit.append(fragment)
    if not unit:
        raise ValueError("decision_unit_source_fidelity_failure")
    original_ids = [s["fragment_id"] for s in original["metadata"][KEY]["spans"]]
    selected_ids = {f["fragment_id"] for f in unit}
    # Source units are ordered by catalog position, but their verified internal
    # layout order must survive extension (PDF insertion may differ from layout).
    extraction_position = {f["fragment_id"]: index for index, f in enumerate(fragments)}
    blocks = [[fid for fid in original_ids if fid in selected_ids]]
    remaining = selected_ids - set(original_ids)
    blocks.extend([f["fragment_id"] for f in group if f["fragment_id"] in remaining]
                  for group in groups(fragments))
    blocks = sorted((block for block in blocks if block),
                    key=lambda block: min(extraction_position[fid] for fid in block))
    ordered_ids = [fid for block in blocks for fid in block]
    source_position = {fid: index for index, fid in enumerate(ordered_ids)}
    unit.sort(key=lambda f: source_position[f["fragment_id"]])
    revised["provenance"]["source_fragments"].sort(key=lambda ref: source_position[ref["raw_object_id"]])
    text = str(revised.get("content", {}).get("clean_text") or "")
    evidence = record(unit)
    literal = reconstruct(evidence, by_id)
    if len(unit) == 1:
        if not text or literal.find(text) < 0 or literal.find(text) != literal.rfind(text):
            raise ValueError("decision_unit_source_fidelity_failure")
        start = literal.index(text)
        span = evidence["spans"][0]
        span.update(start=start, end=start+len(text), text_sha256=stable_hash(text))
        evidence["literal_hash"] = stable_hash(text)
        literal = reconstruct(evidence, by_id)
    elif re.sub(r"\s+", " ", text).strip() != re.sub(r"\s+", " ", literal).strip():
        raise ValueError("decision_unit_source_fidelity_failure")
    # Recompute interpretation hints from the realized text, not old grouping.
    hints = record([{**unit[0], "clean_text": literal}])
    evidence.update(role=hints["role"], reason_codes=hints["reason_codes"])
    revised["content"].update(clean_text=literal, raw_text=literal)
    revised.setdefault("metadata", {})[KEY] = evidence
    return revised


def finalized_source_refs(obj, selected_refs):
    """Preserve kernel construction order after verifying the same selection."""
    if not (obj.get("metadata") or {}).get(KEY):
        return deepcopy(selected_refs)
    current = obj.get("provenance", {}).get("source_fragments") or []
    def bindings(refs):
        return {ref["raw_object_id"]: (ref.get("raw_content_hash"), ref.get("source_locator"))
                for ref in refs}
    if (len(selected_refs) != len(current)
            or len(bindings(selected_refs)) != len(selected_refs)
            or bindings(selected_refs) != bindings(current)
            or {"decision_unit_source_fidelity_failure", "decision_unit_evidence_invalid"}.intersection(unit_issues(obj))):
        raise ValueError("decision_unit_source_fidelity_failure")
    return deepcopy(current)


def apply_gate(objects, *, source_hash, graph=None, inventory=None):
    """Derived admission for versioned PDF units only, persisted by existing callers."""
    graph_reasons = []
    if graph is not None:
        from src.decision_graph_v1 import graph_issues
        graph_reasons = graph_issues(graph, objects, inventory)
    for obj in objects:
        evidence = (obj.get("metadata") or {}).get(KEY)
        if not evidence:
            continue
        reasons = unit_issues(obj)
        if (obj.get("source") or {}).get("source_checksum") != source_hash:
            reasons.append("decision_unit_source_fidelity_failure")
        if graph_reasons:
            reasons.append("decision_unit_graph_unresolved")
        elif graph is None and "decision_unit_graph_unresolved" in (obj.get("metadata") or {}).get("admission", {}).get("reason_codes", []):
            reasons.append("decision_unit_graph_unresolved")
        obj.setdefault("metadata", {})["admission"] = {
            "admission_version": CONTRACT, "gate_result": "blocked" if reasons else "allowed",
            "reason_codes": sorted(set(reasons)), "candidate_text": obj["content"]["clean_text"],
            "document_version": obj["source"]["version"], "source_hash": source_hash}
        if graph is not None and not graph_reasons and label_usage(obj, graph):
            obj["metadata"]["admission"]["source_usage"] = "edge_label"
    return objects


def label_usage(obj, graph):
    """A graph context passage used literally by a branch, never a node approval."""
    if not (obj.get("metadata") or {}).get(KEY):
        return False
    if not branch_label(obj.get("content", {}).get("clean_text", "")):
        return False
    if set(unit_issues(obj)) != {"decision_branch_label_not_node"}:
        return False
    node = next((n for n in graph["nodes"] if n["object_id"] == obj["object_id"]), {})
    source_ids = {r["raw_object_id"] for r in obj.get("provenance", {}).get("source_fragments", [])}
    return node.get("mode") == "context" and any(
        e["kind"] == "answer" and e["label"] == obj["content"]["clean_text"]
        and source_ids.intersection(e["evidence_ids"]) for e in graph["edges"])
