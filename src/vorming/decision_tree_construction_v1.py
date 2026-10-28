"""Deterministic decision-tree construction from a validated proposal.

``materialise_knowledge_candidates`` remains the only candidate creator: it owns
candidate text, identity and source mapping. This module only translates the
proposal's temporary references to those materialised objects and plans the
graph, context bindings and result bundles. It never fills in missing text,
connections or labels; anything it cannot bind stays explicitly unresolved.

No durable state is written here. The existing WorkingRevision commit path
remains the only writer once a route is admitted (Protocol §5.4).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.vorming.decision_tree_proposal_v1 import (
    CONTRACT as PROPOSAL_CONTRACT,
    DecisionTreeProposalError,
    relation_findings,
    validate_proposal,
)
from src.integrity_kernel import stable_hash

CONTRACT = "decision-tree-construction-v1"
FORMATION_MODE = "decision-tree-source-bound-v1"
HUMAN_CONFIRMATION = "human_route_confirmation_required"
_MODES = {"start": "continue", "action": "continue", "outcome": "terminal", "context": "context"}
# Closed decision-tree taxonomy; a proposal, confirmed only by human review.
PROPOSED_TYPES = {"start": "path", "question": "node", "action": "node", "outcome": "outcome"}


def proposal_inputs(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Source blocks a proposer may cite: exactly the materialiser's own view."""
    from src.vorming.knowledge_materialisation_v1 import selection_source_blocks
    return selection_source_blocks(fragments)


def construct(proposal: Any, *, document_id: str, title: str, family: str, class_: str,
              content_kind: str, fragments: list[dict[str, Any]],
              inventory: dict[str, Any], model: str,
              proposed_types: dict[str, str] | None = None) -> dict[str, Any]:
    """Return a spec plus a graph plan; raise on any proposal or materialisation failure."""
    from src.vorming.knowledge_materialisation_v1 import (
        materialise_knowledge_candidates,
        resolve_source_selection,
    )
    from src.vorming.semantic_passage_v1 import SELECTION_ORIGIN_PROPOSAL

    if not str(model or "").strip():
        raise DecisionTreeProposalError("decision_construction_model_required")
    fragments = list(fragments)
    blocks = proposal_inputs(fragments)
    validate_proposal(proposal, blocks=blocks, inventory=inventory)
    units = proposal["units"]
    decisions = []
    for unit in units:
        decision = {"decision_kind": "semantic_selection", "selection_origin": SELECTION_ORIGIN_PROPOSAL,
                    "spans": deepcopy(unit["spans"]), "source_text": unit["quoted_text"]}
        proposed = (proposed_types or {}).get(unit["ref"], PROPOSED_TYPES.get(unit["role"]))
        if proposed:
            decision.update(emit_proposed_type=True, proposed_object_type=proposed)
        decisions.append(decision)
    candidates = materialise_knowledge_candidates(decisions, document_id=document_id, fragments=fragments)
    provenance = {"formation_mode": FORMATION_MODE, "model": str(model),
                  "source_blocks_hash": stable_hash(blocks), "proposal_hash": stable_hash(proposal)}
    for candidate in candidates:
        # Formation provenance only, as on the prose route; text/identity/mapping untouched.
        candidate["semantic_passage"].update(provenance)
    object_for = {unit["ref"]: candidate["object_id"] for unit, candidate in zip(units, candidates)}
    if len(set(object_for.values())) != len(object_for):
        raise DecisionTreeProposalError("decision_construction_duplicate_unit")
    by_fragment = {f["fragment_id"]: f for f in fragments}
    endpoint_fragments = {unit["ref"]: [by_fragment[fid] for fid in candidate["source_fragment_ids"]]
                          for unit, candidate in zip(units, candidates)}

    unresolved_codes = {(row["subject"], row["code"]) for row in proposal["unresolved"]}
    role_unresolved = {subject for subject, code in unresolved_codes if code == "role_ambiguous"}
    # A connection the proposer itself marks uncertain never becomes an edge.
    doubted = {subject for subject, _code in unresolved_codes}
    connections = {row["ref"]: row for row in proposal["connections"]}
    unresolved = [HUMAN_CONFIRMATION]
    for subject, code in sorted(unresolved_codes, key=lambda item: (str(item[0]), item[1])):
        row = connections.get(subject)
        target = (f"{object_for[row['from']]}->{object_for.get(row['to'], 'unknown')}" if row
                  else object_for.get(subject, "proposal"))
        unresolved.append(f"{code}:{target}")
    nodes = []
    for unit, candidate in zip(units, candidates):
        mode = unit["selection"] if unit["role"] == "question" else _MODES[unit["role"]]
        nodes.append({"object_id": candidate["object_id"],
                      "mode": "unresolved" if unit["ref"] in role_unresolved else mode,
                      "evidence_ids": list(candidate["source_fragment_ids"])})
    edges, findings, used_labels = [], [], set()
    for row in proposal["connections"]:
        label_text, label_ids = None, []
        if row["label_span"] is not None:
            label = resolve_source_selection([row["label_span"]], fragments=fragments)
            label_text, label_ids = label["source_text"], label["source_fragment_ids"]
            used_labels.update(label_ids)
        elif row["kind"] == "answer":
            # Literal label of the cited explicit export relation (validated present).
            items = inventory.get("items") or {}
            label_text = next(str(items[i]["record"].get("label") or "") for i in row["evidence_ids"]
                              if items[i].get("kind") == "export_edge")
        codes = relation_findings(row, endpoint_fragments=endpoint_fragments, label_fragment_ids=label_ids,
                                  label_text=label_text, inventory=inventory,
                                  fragments_by_id=by_fragment)
        source, target = object_for[row["from"]], object_for.get(row["to"]) if row["to"] else None
        if row["ref"] in doubted:
            continue
        if codes:
            findings.append({"connection": row["ref"], "from": source, "to": target, "codes": codes})
            unresolved.extend(f"{code}:{source}->{target or 'unknown'}" for code in codes)
            continue
        edge = {"from": source, "to": target, "kind": "answer" if row["kind"] == "answer" else "continue",
                "label": label_text or "", "evidence_ids": sorted(row["evidence_ids"])}
        edge = {"id": "dtp-" + stable_hash(edge)[:20], **edge}
        if any(e["id"] == edge["id"] for e in edges):
            unresolved.append(f"route_duplicate:{source}->{target}")
            continue
        edges.append(edge)

    bundles, bundle_issues = [], []
    for row in proposal["result_bundles"]:
        container = endpoint_fragments[row["container"]]
        members = [endpoint_fragments[m] for m in row["members"]]
        container_ids = {f["fragment_id"] for f in container if f.get("bundle_role") == "container"}
        ok = len(container_ids) == 1 and all(
            m and all(f.get("bundle_role") == "member" and f.get("bundle_id") in container_ids for f in m)
            for m in members)
        record = {"container": object_for[row["container"]], "members": [object_for[m] for m in row["members"]]}
        (bundles if ok else bundle_issues).append(record)
        if not ok:
            unresolved.append(f"result_bundle_unverified:{record['container']}")
    used = {fid for c in candidates for fid in c["source_fragment_ids"]} | used_labels
    spec = {"spec_version": "console-ingest-1.0", "document_id": document_id, "object_version": "1.0",
            "target_group": [], "care_setting": [],
            "topic": [family, f"class:{class_}", f"source-kind:{content_kind}"],
            "objects": [{"object_id": f"{document_id}-document", "object_type": "document",
                         "text": title, "review_track": "technical"}, *candidates]}
    return {
        "contract": CONTRACT,
        "proposal_contract": PROPOSAL_CONTRACT,
        "proposal_hash": stable_hash(proposal),
        "spec": spec,
        # Temporary references are proposal-local evidence, never object identity.
        "references": object_for,
        "graph_plan": {"nodes": nodes, "edges": edges,
                       "entrypoints": [object_for[u["ref"]] for u in units if u["entry"]],
                       "unresolved": list(dict.fromkeys(unresolved))},
        "context_bindings": [{"context": object_for[row["context"]],
                              "applies_to": [object_for[t] for t in row["applies_to"]]}
                             for row in proposal["context_bindings"]],
        "result_bundles": bundles,
        "result_bundle_issues": bundle_issues,
        "relation_findings": findings,
        "unassigned_fragment_ids": [f["fragment_id"] for f in fragments if f["fragment_id"] not in used],
    }


def bind_graph(construction: dict[str, Any], objects: list[dict[str, Any]], source_hash: str) -> dict[str, Any]:
    """Bind the plan to the exact transformed object versions (existing graph contract)."""
    from src.vorming.decision_graph_v1 import CONTRACT as GRAPH_CONTRACT
    versions = {o["object_id"]: o["object_version"] for o in objects if o.get("object_type") != "document"}
    plan = construction["graph_plan"]
    if {n["object_id"] for n in plan["nodes"]} != set(versions):
        raise DecisionTreeProposalError("decision_construction_object_set_mismatch")
    return {"contract": GRAPH_CONTRACT, "source_sha256": source_hash,
            "nodes": [{"object_id": n["object_id"], "object_version": versions[n["object_id"]],
                       "mode": n["mode"], "evidence_ids": list(n["evidence_ids"])} for n in plan["nodes"]],
            "edges": deepcopy(plan["edges"]), "entrypoints": list(plan["entrypoints"]),
            "unresolved": list(plan["unresolved"])}
