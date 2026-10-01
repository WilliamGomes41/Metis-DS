"""Source-bound decision structure owned by the existing WorkingRevision.

Extraction inventories evidence, never confirms routing. Edges are human claims
over immutable evidence; an exact graph hash and object tuple set bind review.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from src.integrity_kernel import stable_hash

CONTRACT = "source-decision-graph-v1"


def pdf_fragments(path: Path, *, document_id: str, source_id: str) -> list[dict[str, Any]]:
    from src.extract_pdf_v2 import extract
    fragments = extract(path, document_id=document_id, source_id=source_id)
    for row in fragments:
        row["boom_id"] = row["fragment_id"]
        row["boom_kind"] = "node"
    return fragments


def evidence_inventory(path: Path, fragments: list[dict[str, Any]], source_hash: str) -> dict[str, Any]:
    import fitz

    evidence = {r["fragment_id"]: {"kind": "text", "text": r["clean_text"],
                "locator": deepcopy(r["source_locator"])} for r in fragments}
    with fitz.open(path) as doc:
        for number, page in enumerate(doc, 1):
            for index, drawing in enumerate(page.get_drawings()):
                segments = []
                for item in drawing["items"]:
                    if item[0] == "l":
                        segments.append([[float(p.x), float(p.y)] for p in item[1:3]])
                if segments:
                    evidence[f"p{number}-drawing-{index}"] = {
                        "kind": "graphic", "page": number,
                        "bbox": list(drawing["rect"]), "segments": segments,
                    }
    return {"source_sha256": source_hash, "items": evidence}


def prepare_graph(path: Path, data: bytes, kind: str, fragments: list[dict[str, Any]],
                  objects: list[dict[str, Any]], source_hash: str) -> dict[str, Any]:
    """Both adapters emit proposals; missing export routes remain missing."""
    from src.integrity_kernel import stamp_canonical_hashes
    if kind == "pdf":
        inventory = evidence_inventory(path, fragments, source_hash)
    else:
        inventory = {"source_sha256": source_hash, "items": {
            f["fragment_id"]: {"kind": "text", "text": f["clean_text"], "locator": f["source_locator"]}
            for f in fragments}}
    graph = {"contract": CONTRACT, "source_sha256": source_hash, "nodes": [], "edges": [],
             "entrypoints": [], "unresolved": ["human_route_reconstruction_required"]}
    for obj in objects:
        obj.setdefault("metadata", {})["decision_graph_contract"] = CONTRACT
        stamp_canonical_hashes(obj)
        if obj["object_type"] != "document":
            graph["nodes"].append({"object_id": obj["object_id"], "object_version": obj["object_version"],
                                   "mode": "unresolved", "evidence_ids": [r["raw_object_id"] for r in obj["provenance"]["source_fragments"]]})
    if kind == "boom":
        payload = json.loads(data)
        by_source_id = {str(f["boom_id"]): f'{f["document_id"]}-{f["boom_id"]}' for f in fragments}
        for index, branch in enumerate(payload.get("branches", [])):
            if not isinstance(branch, dict):
                continue
            src, dest = by_source_id.get(branch.get("from")), by_source_id.get(branch.get("to"))
            if not src or not dest or not isinstance(branch.get("label", ""), str):
                continue
            eid = f"export-branch-{index}"
            label = branch.get("label", "")
            inventory["items"][eid] = {"kind": "export_edge", "text": label,
                                       "record": deepcopy(branch), "locator": {"json_pointer": f"/branches/{index}"}}
            graph["edges"].append({"id": eid, "from": src, "to": dest, "label": label,
                                   "kind": "answer" if label else "continue", "evidence_ids": [eid]})
    return {"decision_graph": graph, "decision_graph_evidence": inventory, "decision_graph_reviews": []}


def graph_hash(graph: dict[str, Any]) -> str:
    return stable_hash(graph)


def route_contexts(graph: dict[str, Any]) -> dict[str, str]:
    """Bind each connected route component; unrelated source context stays put."""
    nodes = {n["object_id"]: n for n in graph["nodes"]}
    adjacency = {oid: set() for oid in nodes}
    for edge in graph["edges"]:
        adjacency[edge["from"]].add(edge["to"])
        adjacency[edge["to"]].add(edge["from"])
    result = {}
    for oid in nodes:
        component, pending = set(), [oid]
        while pending:
            item = pending.pop()
            if item not in component:
                component.add(item)
                pending.extend(adjacency[item] - component)
        result[oid] = stable_hash({
            "nodes": [{k: v for k, v in nodes[i].items() if k != "object_version"} for i in sorted(component)],
            "edges": sorted((e for e in graph["edges"] if e["from"] in component), key=lambda e: e["id"]),
            "entrypoints": sorted(set(graph["entrypoints"]) & component),
        })
    return result


def graph_issues(graph: Any, objects: list[dict[str, Any]], inventory: dict[str, Any]) -> list[str]:
    """Structural checks cannot certify the human interpretation of a drawing."""
    if not isinstance(graph, dict) or set(graph) != {"contract", "source_sha256", "nodes", "edges", "entrypoints", "unresolved"}:
        return ["decision_graph_invalid"]
    if graph["contract"] != CONTRACT or graph["source_sha256"] != inventory.get("source_sha256"):
        return ["decision_graph_source_mismatch"]
    if not all(isinstance(graph[key], list) for key in ("nodes", "edges", "entrypoints", "unresolved")):
        return ["decision_graph_invalid"]
    issues = ["decision_graph_unresolved"] if graph["unresolved"] else []
    current = {o["object_id"]: o for o in objects if o.get("object_type") != "document"}
    evidence = inventory.get("items") or {}
    nodes = {}
    for n in graph["nodes"]:
        if not isinstance(n, dict) or set(n) != {"object_id", "object_version", "mode", "evidence_ids"}:
            return ["decision_graph_node_invalid"]
        oid = n["object_id"]
        if not isinstance(oid, str) or oid in nodes or oid not in current:
            return ["decision_graph_endpoint_invalid"]
        if n["object_version"] != current[oid]["object_version"]:
            issues.append("decision_graph_endpoint_stale")
        if n["mode"] not in {"single", "multiple", "continue", "terminal", "context"}:
            issues.append("decision_graph_mode_unresolved")
        ids = n["evidence_ids"]
        source_ids = {r.get("raw_object_id") for r in (current[oid].get("provenance") or {}).get("source_fragments", [])}
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in evidence or i not in source_ids for i in ids):
            issues.append("decision_graph_node_evidence_missing")
        nodes[oid] = n
    if set(nodes) != set(current):
        issues.append("decision_graph_coverage_incomplete")
    outgoing = {oid: [] for oid in nodes}
    edge_ids = set()
    for edge in graph["edges"]:
        if not isinstance(edge, dict) or set(edge) != {"id", "from", "to", "kind", "label", "evidence_ids"}:
            return ["decision_graph_edge_invalid"]
        eid = edge["id"]
        if not isinstance(eid, str) or not eid or eid in edge_ids:
            return ["decision_graph_edge_invalid"]
        edge_ids.add(eid)
        if edge["from"] not in nodes or edge["to"] not in nodes:
            return ["decision_graph_endpoint_invalid"]
        ids = edge["evidence_ids"]
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in evidence for i in ids):
            issues.append("decision_graph_edge_evidence_missing")
            continue
        if not any(evidence[i]["kind"] in {"graphic", "export_edge"} for i in ids):
            issues.append("decision_graph_graphic_evidence_missing")
        if edge["kind"] == "answer":
            if not isinstance(edge["label"], str) or not edge["label"] or not any(
                edge["label"] == evidence[i].get("text") for i in ids
            ):
                issues.append("decision_graph_label_not_literal")
        elif edge["kind"] != "continue" or edge["label"] != "":
            issues.append("decision_graph_edge_kind_invalid")
        outgoing[edge["from"]].append(edge)
    active = {oid for oid, n in nodes.items() if n["mode"] != "context"}
    for oid, n in nodes.items():
        edges = outgoing[oid]
        mode = n["mode"]
        if mode in {"single", "multiple"}:
            labels = [e["label"] for e in edges]
            if len(edges) < 2 or len(labels) != len(set(labels)) or any(e["kind"] != "answer" for e in edges):
                issues.append("decision_graph_answers_incomplete")
        elif mode == "continue" and (len(edges) != 1 or edges[0]["kind"] != "continue"):
            issues.append("decision_graph_continuation_incomplete")
        elif mode in {"terminal", "context"} and edges:
            issues.append("decision_graph_unexpected_route")
        if any(e["to"] not in active for e in edges):
            issues.append("decision_graph_route_to_context")
    entries = graph["entrypoints"]
    if not entries or any(not isinstance(i, str) or i not in active for i in entries) or len(set(entries)) != len(entries):
        issues.append("decision_graph_entrypoints_invalid")
    visited, visiting = set(), set()

    def visit(oid):
        if oid in visiting:
            issues.append("decision_graph_cycle_unresolved")
            return
        if oid in visited or oid not in nodes:
            return
        visiting.add(oid)
        for edge in outgoing[oid]:
            visit(edge["to"])
        visiting.remove(oid)
        visited.add(oid)
    for oid in entries:
        if isinstance(oid, str):
            visit(oid)
    if visited != active:
        issues.append("decision_graph_unreachable_nodes")
    return sorted(set(issues))


def review_target(graph: dict[str, Any], objects: list[dict[str, Any]], policy: dict[str, Any]) -> str:
    return stable_hash({"graph": graph_hash(graph), "policy": policy,
                       "objects": sorted((o["object_id"], o["object_version"],
                                           o["provenance"]["canonical_object_hash"])
                                          for o in objects if o.get("object_type") != "document")})


def verify_source_evidence(console: Any, envelope: dict[str, Any]) -> None:
    """Reconstruct evidence from source bytes, not from an editable client claim."""
    if "decision_graph" not in envelope:
        return
    from src.beslisboom_path_v1 import extract_boom_fragments
    path, data = console._verified_source_bytes(envelope)
    args = {"document_id": envelope["document_id"], "source_id": envelope["source_id"]}
    fragments = pdf_fragments(path, **args) if envelope["content_kind"] == "pdf" else extract_boom_fragments(data, **args)
    inventory = prepare_graph(path, data, envelope["content_kind"], fragments, [], envelope["sha256"])["decision_graph_evidence"]
    if inventory != envelope["decision_graph_evidence"]:
        raise ValueError("decision_graph_source_evidence_mismatch")


def publication_issues(envelope: dict[str, Any], objects: list[dict[str, Any]]) -> list[str]:
    if "decision_graph" not in envelope:
        return []
    graph = envelope["decision_graph"]
    issues = graph_issues(graph, objects, envelope["decision_graph_evidence"])
    if issues:
        return issues
    from src.review_policy_v1 import required_reviewers
    target = review_target(graph, objects, envelope["review_policy"])
    confirmed = {r["reviewer_id"] for r in envelope.get("decision_graph_reviews", []) if r.get("target") == target}
    if required_reviewers(envelope["review_policy"]) - confirmed:
        issues.append("decision_graph_review_incomplete")
    return issues


def release_graph(envelope: dict[str, Any], objects: list[dict[str, Any]]) -> dict[str, Any]:
    """Immutable release evidence; never a separate serving authority."""
    issues = publication_issues(envelope, objects)
    if issues:
        raise ValueError(",".join(issues))
    return deepcopy({"graph": envelope["decision_graph"], "evidence": envelope["decision_graph_evidence"],
                     "policy": envelope["review_policy"], "reviews": envelope["decision_graph_reviews"],
                     "objects": objects, "graph_hash": graph_hash(envelope["decision_graph"]),
                     "source_sha256": envelope["sha256"], "applicability": "not_evaluated"})


def read_active_graph(store: Any, source_store: Any, snapshot_id: str) -> dict[str, Any] | None:
    """Read only an entire active release, with verified immutable source bytes."""
    from src.integrity_kernel import sha256_bytes
    active = [r for r in store.active_publication_rows() if r["snapshot_id"] == snapshot_id]
    if not active:
        return None
    release = store.release_for_snapshot(snapshot_id)
    if not release or not release.get("decision_graph_release"):
        return None
    if any(r["publication"]["release_id"] != release["release_id"] for r in active):
        raise ValueError("decision_graph_release_mismatch")
    expected = {(o["object_id"], o["object_version"]) for o in release["objects"]}
    actual = {(r["knowledge_object"]["object_id"], r["knowledge_object"]["object_version"]) for r in active}
    if actual != expected:
        raise ValueError("decision_graph_release_incomplete")
    payload = deepcopy(release["decision_graph_release"])
    from src.integrity_kernel import compute_canonical_object_hash
    payload_objects = {(o["object_id"], o["object_version"], compute_canonical_object_hash(o))
                       for o in payload["objects"] if o.get("object_type") != "document"}
    active_objects = {(r["knowledge_object"]["object_id"], r["knowledge_object"]["object_version"],
                       compute_canonical_object_hash(r["knowledge_object"])) for r in active}
    if payload["source_sha256"] != release["source_sha256"] or payload_objects != active_objects:
        raise ValueError("decision_graph_release_mismatch")
    if source_store is None or sha256_bytes(source_store.load_verified(release["source_locator"])) != payload["source_sha256"]:
        raise ValueError("decision_graph_source_unavailable")
    if payload["graph_hash"] != graph_hash(payload["graph"]) or graph_issues(payload["graph"], payload["objects"], payload["evidence"]):
        raise ValueError("decision_graph_release_invalid")
    return {"release_id": release["release_id"], "release_version": release["release_version"],
            "snapshot_id": snapshot_id, **payload}
