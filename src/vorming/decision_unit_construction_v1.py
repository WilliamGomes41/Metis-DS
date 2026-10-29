"""Historical decision-unit evidence: readers and validators only, no formation.

Snapshots formed before ``decision-tree-source-bound-v1`` carry this contract.
Their evidence is reconstructed and validated here; new candidates come only
from ``knowledge_materialisation_v1`` via ``decision_tree_route_v1``.
"""
from __future__ import annotations

from copy import deepcopy
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


def _complete(text):
    blob = re.sub(r"\s+", " ", text).strip()
    if not blob or TRAILING.search(blob.rstrip("?!.:* ")):
        return False
    if re.search(r"\?[*]*$", blob):
        return bool(QUESTION.search(blob))
    return bool(re.search(r"[!.][*]*$", blob) or ACTION.search(blob)
                or (INSTRUCTION.search(blob) and " " in blob))


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


def unit_issues(obj):
    from src.review.review_card_facts_v1 import ReviewObjectFacts
    if isinstance(obj, ReviewObjectFacts):
        return list(obj.proof['unit_issues'])
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


def finalized_source_refs(obj, selected_refs, fragments=None):
    """Preserve kernel construction order after verifying the same selection."""
    if not (obj.get("metadata") or {}).get(KEY):
        return deepcopy(selected_refs)
    try:
        reconstruct(obj["metadata"][KEY], fragments or [])
    except ValueError as exc:
        raise ValueError("decision_unit_source_fidelity_failure") from exc
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


def _formed_by_route(obj) -> bool:
    from src.vorming.decision_tree_construction_v1 import FORMATION_MODE
    semantic = (obj.get("metadata") or {}).get("semantic_passage") or {}
    return semantic.get("formation_mode") == FORMATION_MODE


def apply_gate(objects, *, source_hash, graph=None, inventory=None):
    """Derived admission for decision-tree units, persisted by existing callers.

    Historical units keep their literal-unit checks; units of the current route
    were already verified by the materialiser and transform.
    """
    from src.vorming.decision_tree_construction_v1 import CONTRACT as ROUTE_CONTRACT
    graph_reasons = []
    if graph is not None:
        from src.vorming.decision_graph_v1 import graph_issues
        graph_reasons = graph_issues(graph, objects, inventory)
    for obj in objects:
        evidence = (obj.get("metadata") or {}).get(KEY)
        current = _formed_by_route(obj)
        if not evidence and not current:
            continue
        reasons = unit_issues(obj) if evidence else []
        if (obj.get("source") or {}).get("source_checksum") != source_hash:
            reasons.append("decision_unit_source_fidelity_failure")
        if graph_reasons:
            reasons.append("decision_unit_graph_unresolved")
        elif graph is None and "decision_unit_graph_unresolved" in (obj.get("metadata") or {}).get("admission", {}).get("reason_codes", []):
            reasons.append("decision_unit_graph_unresolved")
        obj.setdefault("metadata", {})["admission"] = {
            "admission_version": ROUTE_CONTRACT if current else CONTRACT,
            "gate_result": "blocked" if reasons else "allowed",
            "reason_codes": sorted(set(reasons)), "candidate_text": obj["content"]["clean_text"],
            "document_version": obj["source"]["version"], "source_hash": source_hash}
        if evidence and graph is not None and not graph_reasons and label_usage(obj, graph):
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
