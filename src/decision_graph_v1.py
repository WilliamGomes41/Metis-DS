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


def pdf_fragments(path: Path, *, document_id: str, source_id: str, construct_units: bool = True, deadline=None, use_docling=None) -> list[dict[str, Any]]:
    from src.extract_pdf_v2 import extract
    from src.docling_pdf_v1 import enabled, extract as extract_docling
    selected = enabled() if use_docling is None else use_docling
    fragments = (extract_docling(path, document_id=document_id, source_id=source_id, deadline=deadline)
                 if selected else extract(path, document_id=document_id, source_id=source_id))
    extraction_record = getattr(fragments, "extraction_record", None)
    for row in fragments:
        row["boom_id"] = row["fragment_id"]
        row["boom_kind"] = "node"
    if construct_units:
        from src.decision_unit_construction_v1 import add_layout, source_lines
        add_layout(path, fragments)
        fragments = source_lines(fragments)
    from src.decision_bundles_v1 import split_bundles
    output = split_bundles(fragments)
    if extraction_record is not None:
        from src.docling_contract_v1 import ExtractedFragments
        output = ExtractedFragments(output, extraction_record)
    return output


def evidence_inventory(path: Path, fragments: list[dict[str, Any]], source_hash: str) -> dict[str, Any]:
    import fitz
    from src.decision_bundles_v1 import bundle_evidence

    evidence = {r["fragment_id"]: {"kind": "text", "text": r["clean_text"],
                "locator": deepcopy(r["source_locator"]), **bundle_evidence(r)} for r in fragments}
    with fitz.open(path) as doc:
        for number, page in enumerate(doc, 1):
            for index, drawing in enumerate(page.get_drawings()):
                segments = []
                curves = []
                for item in drawing["items"]:
                    if item[0] == "l":
                        segments.append([[float(p.x), float(p.y)] for p in item[1:3]])
                    elif item[0] == "c":
                        curves.append([[float(p.x), float(p.y)] for p in item[1:5]])
                if segments or curves:
                    evidence[f"p{number}-drawing-{index}"] = {
                        "kind": "graphic", "page": number,
                        "bbox": list(drawing["rect"]), "segments": segments,
                        **({"curves": curves} if curves else {}),
                    }
    return {"source_sha256": source_hash, "items": evidence}


def prepare_graph(path: Path, data: bytes, kind: str, fragments: list[dict[str, Any]],
                  objects: list[dict[str, Any]], source_hash: str) -> dict[str, Any]:
    """Both adapters emit proposals; missing export routes remain missing."""
    from src.integrity_kernel import stamp_canonical_hashes
    from src.decision_bundles_v1 import bundle_evidence, stamp_bundles
    if kind == "pdf":
        inventory = evidence_inventory(path, fragments, source_hash)
    else:
        inventory = {"source_sha256": source_hash, "items": {
            f["fragment_id"]: {"kind": "text", "text": f["clean_text"], "locator": f["source_locator"], **bundle_evidence(f)}
            for f in fragments}}
    graph = {"contract": CONTRACT, "source_sha256": source_hash, "nodes": [], "edges": [],
             "entrypoints": [], "unresolved": ["human_route_reconstruction_required"]}
    stamp_bundles(fragments, objects)
    for obj in objects:
        obj.setdefault("metadata", {})["decision_graph_contract"] = CONTRACT
        stamp_canonical_hashes(obj)
        if obj["object_type"] != "document":
            from src.decision_unit_construction_v1 import KEY, branch_label
            graph["nodes"].append({"object_id": obj["object_id"], "object_version": obj["object_version"],
                                   "mode": "context" if (obj.get("metadata") or {}).get(KEY) and branch_label(obj["content"]["clean_text"]) else "unresolved",
                                   "evidence_ids": [r["raw_object_id"] for r in obj["provenance"]["source_fragments"]]})
    if kind == "boom":
        payload = json.loads(data)
        by_source_id = {str(f["boom_id"]): f'{f["document_id"]}-{f["boom_id"]}' for f in fragments}
        for index, branch in enumerate(payload.get("branches", [])):
            if not isinstance(branch, dict):
                graph["unresolved"].append(f"invalid_export_branch:{index}")
                continue
            src, dest = by_source_id.get(branch.get("from")), by_source_id.get(branch.get("to"))
            if not src or not dest or not isinstance(branch.get("label", ""), str):
                graph["unresolved"].append(f"invalid_export_branch:{index}")
                continue
            eid = f"export-branch-{index}"
            label = branch.get("label", "")
            inventory["items"][eid] = {"kind": "export_edge", "text": label,
                                       "record": deepcopy(branch), "locator": {"json_pointer": f"/branches/{index}"}}
            graph["edges"].append({"id": eid, "from": src, "to": dest, "label": label,
                                   "kind": "answer" if label else "continue", "evidence_ids": [eid]})
    proposals = []
    if kind == "pdf":
        from src.pdf_route_proposals_v1 import propose_routes
        proposals = propose_routes(fragments, objects, inventory)
        from src.decision_unit_construction_v1 import KEY
        constructed = any((o.get("metadata") or {}).get(KEY) for o in objects)
        graph["edges"] = [{k: v for k, v in proposal.items() if k != "uncertainties"} for proposal in proposals
                          if not constructed or set(proposal["uncertainties"]) <= {"human_route_confirmation_required"}]
    from src.decision_unit_construction_v1 import apply_gate
    from src.passage_register_v1 import apply_passage_register
    apply_gate(objects, source_hash=source_hash, graph=graph, inventory=inventory)
    objects[:] = apply_passage_register(objects)
    for obj in objects:
        stamp_canonical_hashes(obj)
    from src.decision_unit_construction_v1 import KEY, CONTRACT as UNIT_CONTRACT
    return {"decision_graph": graph, "decision_graph_evidence": inventory, "decision_graph_reviews": [],
            "decision_graph_proposals": proposals,
            **({"decision_unit_contract": UNIT_CONTRACT} if any((o.get("metadata") or {}).get(KEY) for o in objects) else {})}


def graph_hash(graph: dict[str, Any]) -> str:
    return stable_hash(graph)


def route_contexts(graph: dict[str, Any], objects: list[dict[str, Any]] | None = None) -> dict[str, str]:
    """Bind each connected route component; unrelated source context stays put."""
    nodes = {n["object_id"]: n for n in graph["nodes"]}
    adjacency = {oid: set() for oid in nodes}
    for edge in graph["edges"]:
        adjacency[edge["from"]].add(edge["to"])
        adjacency[edge["to"]].add(edge["from"])
    for obj in objects or []:
        bundle = (obj.get("metadata") or {}).get("result_bundle")
        if bundle and bundle["role"] == "member" and obj["object_id"] in adjacency and bundle["object_id"] in adjacency:
            adjacency[obj["object_id"]].add(bundle["object_id"])
            adjacency[bundle["object_id"]].add(obj["object_id"])
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
    if any((o.get("source") or {}).get("source_checksum") != graph["source_sha256"] for o in current.values()):
        return ["decision_graph_source_mismatch"]
    if len({str((o.get("source") or {}).get("version")) for o in current.values()}) > 1:
        return ["decision_graph_source_mismatch"]
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
        from src.decision_unit_construction_v1 import KEY, unit_issues
        if (current[oid].get("metadata") or {}).get(KEY):
            construction_issues = unit_issues(current[oid])
            issues.extend(code for code in construction_issues if n["mode"] != "context"
                          or code not in {"decision_branch_label_not_node", "decision_unit_incomplete"})
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
    from src.decision_bundles_v1 import bundle_issues
    issues.extend(bundle_issues(nodes, current, evidence))
    return sorted(set(issues))


def review_target(graph: dict[str, Any], objects: list[dict[str, Any]], policy: dict[str, Any]) -> str:
    return stable_hash({"graph": graph_hash(graph), "policy": policy.get("review_basis", policy),
                       "objects": sorted((o["object_id"], o["object_version"],
                                           o["provenance"]["canonical_object_hash"])
                                          for o in objects if o.get("object_type") != "document")})


def verify_source_evidence(
    console: Any,
    envelope: dict[str, Any],
    *,
    fragments: list[dict[str, Any]] | None = None,
) -> None:
    """Reconstruct evidence from source bytes, reusing an authoritative fragment read."""
    if "decision_graph" not in envelope:
        return
    from src.beslisboom_path_v1 import extract_boom_fragments
    path, data = console._verified_source_bytes(envelope)
    args = {"document_id": envelope["document_id"], "source_id": envelope["source_id"]}
    if fragments is None:
        fragments = console._read_source_fragments(envelope, path)
    from src.decision_bundles_v1 import split_bundles
    fragments = split_bundles(list(fragments))
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
    from src.review_policy_v1 import required_reviewers, archived_required
    target = review_target(graph, objects, envelope["review_policy"])
    confirmed = {r["reviewer_id"] for r in envelope.get("decision_graph_reviews", []) if r.get("target") == target}
    if (required_reviewers(envelope["review_policy"]) - confirmed) or archived_required(envelope["review_policy"]):
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
    from src.integrity_kernel import compute_canonical_object_hash, validate_hashes
    # Context labels are immutable graph evidence, not independently approved
    # knowledge objects. Verify the exact graph review before excluding them.
    if any(validate_hashes(o) for o in payload["objects"]) or payload["graph_hash"] != graph_hash(payload["graph"]) or publication_issues(
        {"decision_graph": payload["graph"], "decision_graph_evidence": payload["evidence"],
         "review_policy": payload["policy"], "decision_graph_reviews": payload["reviews"]},
        payload["objects"],
    ):
        raise ValueError("decision_graph_release_invalid")
    from src.decision_unit_construction_v1 import label_usage
    payload_objects = {(o["object_id"], o["object_version"], compute_canonical_object_hash(o))
                       for o in payload["objects"] if o.get("object_type") != "document"
                       and not label_usage(o, payload["graph"])}
    active_objects = {(r["knowledge_object"]["object_id"], r["knowledge_object"]["object_version"],
                       compute_canonical_object_hash(r["knowledge_object"])) for r in active}
    if payload["source_sha256"] != release["source_sha256"] or payload_objects != active_objects:
        raise ValueError("decision_graph_release_mismatch")
    if source_store is None or sha256_bytes(source_store.load_verified(release["source_locator"])) != payload["source_sha256"]:
        raise ValueError("decision_graph_source_unavailable")
    return {"release_id": release["release_id"], "release_version": release["release_version"],
            "snapshot_id": snapshot_id, **payload}


def ordered_paths(graph: dict[str, Any], objects: list[dict[str, Any]], inventory: dict[str, Any],
                  outcome_id: str, *, max_paths: int = 1024, max_steps: int = 16384) -> dict[str, Any]:
    """Pure ordered alternatives referencing shared nodes, never a conjunction.

    This projection verifies source/structure/revision, not human route correctness.
    An unresolved graph (including PDF proposals) yields no asserted paths.
    """
    if not isinstance(graph, dict) or len(graph.get('nodes') or []) > 512:
        return {'paths': [], 'issues': ['decision_graph_projection_limit'], 'nodes': {}}
    issues = graph_issues(graph, objects, inventory)
    if issues:
        return {'paths': [], 'issues': issues, 'nodes': {}}
    by_id = {o['object_id']: o for o in objects}
    target = by_id.get(outcome_id)
    if target is None:
        return {'paths': [], 'issues': ['decision_graph_endpoint_invalid'], 'nodes': {}}
    bundle = (target.get('metadata') or {}).get('result_bundle') or {}
    route_target = bundle.get('object_id') if bundle.get('role') == 'member' else outcome_id
    nodes = {n['object_id']: n for n in graph['nodes']}
    if nodes.get(route_target, {}).get('mode') != 'terminal':
        return {'paths': [], 'issues': ['decision_graph_not_outcome'], 'nodes': nodes}
    outgoing = {oid: [] for oid in nodes}
    for edge in graph['edges']:
        outgoing[edge['from']].append(edge)
    pending = [(entry, []) for entry in reversed(graph['entrypoints'])]
    paths, work = [], 0
    while pending:
        oid, steps = pending.pop()
        work += 1
        if work > max_steps:
            return {'paths': [], 'issues': ['decision_graph_projection_limit'], 'nodes': nodes}
        if oid == route_target:
            paths.append({'entrypoint': steps[0]['object_id'] if steps else oid,
                          'steps': steps, 'outcome_id': outcome_id, 'route_outcome_id': route_target})
            if len(paths) > max_paths:
                return {'paths': [], 'issues': ['decision_graph_projection_limit'], 'nodes': nodes}
        else:
            for edge in reversed(outgoing[oid]):
                pending.append((edge['to'], steps + [{'object_id': oid, 'object_version': nodes[oid]['object_version'],
                    'mode': nodes[oid]['mode'], 'edge_id': edge['id'], 'label': edge['label'],
                    'next_object_id': edge['to']}]))
    return {'paths': paths, 'issues': [] if paths else ['decision_graph_outcome_unreachable'],
            'nodes': nodes, 'graph_hash': graph_hash(graph), 'source_sha256': graph['source_sha256']}
