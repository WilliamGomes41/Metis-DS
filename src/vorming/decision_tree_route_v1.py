"""Shared extraction, export validation and graph finalization for decision trees."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from src.vorming.decision_tree_construction_v1 import bind_graph, proposal_inputs
from src.vorming.decision_tree_proposal_v1 import DecisionTreeProposalError
from src.integrity_kernel import stamp_canonical_hashes

POLICY_VERSION = "decision-tree-formation-policy-v1.0.0"
SPEC_KEY = "_decision_tree_formation"
ENVELOPE_KEY = "decision_tree_formation"


def has_recorded_route(envelope):
    return bool(envelope.get(ENVELOPE_KEY) or envelope.get('tree_source_route'))


def _error(code: str, detail: str = ""):
    from src.operations_console_v1 import ConsoleError
    return ConsoleError(code, detail) if detail else ConsoleError(code)


def export_types(proposal: dict[str, Any], fragments: list[dict[str, Any]]) -> dict[str, str]:
    """The export's explicit item kind is the literal type evidence of its unit."""
    by_block = {block["block_id"]: block["source_fragment_ids"] for block in proposal_inputs(fragments)}
    kinds = {f["fragment_id"]: str(f.get("boom_kind") or "node") for f in fragments}
    types = {}
    for unit in proposal["units"]:
        ids = {fid for span in unit["spans"] for fid in by_block[span["block_id"]]}
        if len(ids) == 1:
            types[unit["ref"]] = kinds[ids.pop()]
    return types


_EXPORT_MEMBER_MODES = frozenset({"context"})
_EXPORT_KIND_MODES = {"outcome": frozenset({"terminal", "unresolved"}),
                      "path": frozenset({"continue", "unresolved"}),
                      "node": frozenset({"single", "multiple", "continue", "unresolved"})}


def verify_export_preserved(construction: dict[str, Any], data: bytes,
                            fragments: list[dict[str, Any]]) -> None:
    """Fail closed unless the construction carries the export's explicit graph exactly.

    Every non-empty exported item is one whole unit; every well-formed branch
    between them is one edge with its literal label and only its own evidence;
    no other edge exists; every exported bundle is reproduced with its members;
    no item that an exported branch leads to is proposed as an entrypoint;
    no node takes a role its exported kind rules out.
    """
    from src.vorming.decision_graph_v1 import export_branches
    candidates = construction["spec"]["objects"][1:]
    object_for, allowed_modes = {}, {}
    for fragment in fragments:
        text = " ".join(str(fragment.get("clean_text") or "").split())
        if not text:
            continue
        matches = [c["object_id"] for c in candidates
                   if c["source_fragment_ids"] == [fragment["fragment_id"]] and c["clean_text"] == text]
        if len(matches) != 1:
            raise DecisionTreeProposalError("decision_export_node_not_preserved",
                                            fragment_id=fragment["fragment_id"])
        object_for[str(fragment.get("boom_id"))] = matches[0]
        allowed_modes[matches[0]] = (_EXPORT_MEMBER_MODES if fragment.get("bundle_role") == "member"
                                     else _EXPORT_KIND_MODES.get(str(fragment.get("boom_kind") or "node"),
                                                                 _EXPORT_KIND_MODES["node"]))
    if len(candidates) != len(object_for):
        raise DecisionTreeProposalError("decision_export_node_not_preserved")
    # The export states item kinds, not answer semantics: a role may stay open
    # for review but never contradict the exported kind.
    if any(node["mode"] not in allowed_modes[node["object_id"]] for node in construction["graph_plan"]["nodes"]):
        raise DecisionTreeProposalError("decision_export_role_not_preserved")
    expected = sorted(
        (object_for[branch["from"]], object_for[branch["to"]],
         "answer" if branch.get("label") else "continue", branch.get("label") or "",
         (f"export-branch-{index}",))
        for index, branch in export_branches(data, fragments)
        if branch["from"] in object_for and branch["to"] in object_for)
    actual = sorted((e["from"], e["to"], e["kind"], e["label"], tuple(e["evidence_ids"]))
                    for e in construction["graph_plan"]["edges"])
    if actual != expected or construction["relation_findings"]:
        raise DecisionTreeProposalError("decision_export_route_not_preserved")
    if {to for _from, to, *_rest in expected} & set(construction["graph_plan"]["entrypoints"]):
        raise DecisionTreeProposalError("decision_export_route_not_preserved")
    # The export states no context binding; one would be invented, unreviewed structure.
    if construction["context_bindings"]:
        raise DecisionTreeProposalError("decision_export_context_not_preserved")
    bundles = sorted(
        (object_for[str(f["boom_id"])],
         tuple(sorted(object_for[str(m["boom_id"])] for m in fragments
                      if m.get("bundle_role") == "member" and m.get("bundle_id") == f["fragment_id"])))
        for f in fragments if f.get("bundle_role") == "container")
    proposed = sorted((b["container"], tuple(sorted(b["members"]))) for b in construction["result_bundles"])
    if proposed != bundles or construction["result_bundle_issues"]:
        raise DecisionTreeProposalError("decision_export_bundle_not_preserved")


def _export_enrichment(construction: dict[str, Any], fragments: list[dict[str, Any]], document_id: str) -> None:
    """Carry export-stated proposals onto materialised candidates (never text/identity/mapping)."""
    by_fragment = {f["fragment_id"]: f for f in fragments}
    object_for_boom = {}
    candidates = construction["spec"]["objects"][1:]
    for candidate in candidates:
        for fid in candidate["source_fragment_ids"]:
            object_for_boom[str(by_fragment[fid].get("boom_id"))] = candidate["object_id"]
    for candidate in candidates:
        fragment = by_fragment[candidate["source_fragment_ids"][0]]
        relations = []
        for target in fragment.get("applies_if") or []:
            if str(target) in object_for_boom:
                relations.append({"relation_type": "applies_if", "target_object_id": object_for_boom[str(target)]})
            else:
                construction["graph_plan"]["unresolved"].append(f"applies_if_target_unknown:{candidate['object_id']}")
        candidate["relations"] = relations
        candidate["scorelist"] = bool(fragment.get("scorelist"))
        candidate["risk_fields"] = list(fragment.get("risk_fields") or [])
        if fragment.get("proposed_recommendation_strength"):
            candidate["proposed_recommendation_strength"] = fragment["proposed_recommendation_strength"]


def source_fragments(kind: str, path: Path, data: bytes, *, document_id: str, source_id: str,
                     deadline: float | None = None, use_docling: bool | None = None) -> list[dict[str, Any]]:
    """The recorded source representation for this route (also used for re-reads)."""
    if kind == "pdf":
        from src.vorming.decision_graph_v1 import pdf_fragments
        return pdf_fragments(path, document_id=document_id, source_id=source_id, deadline=deadline,
                             use_docling=use_docling)
    if kind == "boom":
        from src.review.beslisboom_path_v1 import extract_boom_fragments
        from src.vorming.decision_bundles_v1 import split_bundles
        return split_bundles(extract_boom_fragments(data, document_id=document_id, source_id=source_id))
    raise _error("decision_tree_source_kind_unsupported")


def finalize(record: dict[str, Any], objects: list[dict[str, Any]], fragments: list[dict[str, Any]],
             source_hash: str, *, actor: str, with_graph: bool) -> dict[str, Any]:
    """Record the route; with a review policy also bind the reviewable graph.

    Without a review policy no graph review exists, so no graph is stored and
    no graph-based admission is derived (unchanged from the export behaviour).
    """
    from src.vorming.decision_bundles_v1 import stamp_bundles
    from src.vorming.decision_unit_construction_v1 import apply_gate
    from src.vorming.passage_register_v1 import apply_passage_register
    construction = record["construction"]
    fields = {ENVELOPE_KEY: {**record["formation"], "actor": actor},
              "decision_tree_construction": {k: deepcopy(construction[k]) for k in (
                  "proposal_hash", "references", "context_bindings", "result_bundles", "result_bundle_issues",
                  "relation_findings", "unassigned_fragment_ids")}}
    if not with_graph:
        return fields
    stamp_bundles(fragments, objects)
    for obj in objects:
        obj.setdefault("metadata", {})["decision_graph_contract"] = "source-decision-graph-v1"
        stamp_canonical_hashes(obj)
    graph = bind_graph(construction, objects, source_hash)
    apply_gate(objects, source_hash=source_hash, graph=graph, inventory=record["inventory"])
    objects[:] = apply_passage_register(objects)
    for obj in objects:
        stamp_canonical_hashes(obj)
    return {"decision_graph": graph, "decision_graph_evidence": deepcopy(record["inventory"]),
            "decision_graph_reviews": [], **fields}
