"""Audit-domain acceptance evidence for the decision-tree formation route.

The active route (``decision_tree_route_v1``) is measured on frozen sources
against an independent human reference. Nothing here writes KnowledgeObjects,
review bindings, workflow state or publication records (Protocol §10). Human
graph review stays the only confirmation of an interpretation.
"""
from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.integrity_kernel import sha256_bytes, stable_hash

VERSION = "decision-tree-route-acceptance-v1"
ROUTE = "decision-tree-source-bound-v1"
FABRICATED_CONTENT_MAX = 0  # Protocol §10: zero tolerance, not a tunable threshold.
THRESHOLD_KEYS = ("unit_recall_min", "unit_precision_min", "edge_recall_min", "edge_precision_min",
                  "condition_recall_min", "correction_actions_max_per_reference_unit")


def _manifest(source_id: str, title: str, digest: str) -> dict[str, Any]:
    return {"canonical_source": {
        "source_id": source_id, "title": title, "publisher": "V&VN",
        "source_url": f"urn:vvn:freeze:{digest}", "source_type": "pdf", "source_level": 1,
        "canonicality": "canonical", "source_checksum": digest, "checksum_algorithm": "sha256",
        "integrity_status": "verified", "publication_date": "experiment", "version": "experiment"}}


def frozen_input(path: Path, *, document_id: str, source_id: str) -> dict[str, Any]:
    """The route's own source representation and reconstructable evidence."""
    from src.decision_graph_v1 import source_evidence
    from src.decision_tree_route_v1 import source_fragments
    data = Path(path).read_bytes()
    digest = sha256_bytes(data)
    fragments = list(source_fragments("pdf", Path(path), data, document_id=document_id, source_id=source_id,
                                      use_docling=False))
    return {"path": Path(path), "data": data, "source_sha256": digest, "document_id": document_id,
            "source_id": source_id, "fragments": fragments,
            "inventory": source_evidence(Path(path), data, "pdf", fragments, digest)}


def route_output(frozen: dict[str, Any], proposal: Any, *, model: str,
                 title: str = "Beslisboom") -> dict[str, Any]:
    """Proposal -> sole materialiser -> existing transform and graph validation (no writes)."""
    from src.decision_graph_v1 import graph_issues
    from src.decision_tree_construction_v1 import bind_graph, construct
    from src.operations_console_v1 import transform_generic
    fragments = deepcopy(frozen["fragments"])
    construction = construct(proposal, document_id=frozen["document_id"], title=title, family="experiment",
                             class_="beslisboom", content_kind="pdf", fragments=fragments,
                             inventory=frozen["inventory"], model=model)
    objects = transform_generic(construction["spec"], _manifest(frozen["source_id"], title, frozen["source_sha256"]),
                                fragments)
    from src.decision_bundles_v1 import stamp_bundles
    from src.integrity_kernel import stamp_canonical_hashes
    stamp_bundles(fragments, objects)
    for obj in objects:
        stamp_canonical_hashes(obj)
    graph = bind_graph(construction, objects, frozen["source_sha256"])
    return {"route": ROUTE, "objects": objects, "graph": graph, "construction": construction,
            "context_bindings": construction["context_bindings"],
            "issues": graph_issues(graph, objects, frozen["inventory"])}


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def _score(expected: set, actual: set) -> dict[str, Any]:
    matched = len(expected & actual)
    return {"reference": len(expected), "output": len(actual), "matched": matched,
            "omissions": len(expected - actual), "additions": len(actual - expected),
            "recall": matched / len(expected) if expected else None,
            "precision": matched / len(actual) if actual else None}


def compare_to_reference(arm: dict[str, Any], reference: dict[str, Any],
                         fragments: list[dict[str, Any]]) -> dict[str, Any]:
    """Literal-text comparison against an independent human reference."""
    text = {o["object_id"]: _norm(o["content"]["clean_text"]) for o in arm["objects"]
            if o.get("object_type") != "document"}
    context = {n["object_id"] for n in arm["graph"]["nodes"] if n["mode"] == "context"}
    units = {t for oid, t in text.items() if oid not in context}
    edges = {(text[e["from"]], text[e["to"]], _norm(e["label"])) for e in arm["graph"]["edges"]}
    conditions = {(text[b["context"]], text[t]) for b in arm["context_bindings"] for t in b["applies_to"]}
    source = " ".join(_norm(f["clean_text"]) for f in fragments)
    fabricated = sum(1 for t in text.values() if not all(part in source for part in t.split(" ")))
    ref_units = {_norm(u["text"]) for u in reference["units"]}
    ref_edges = {(_norm(e["from"]), _norm(e["to"]), _norm(e.get("label"))) for e in reference["connections"]}
    ref_conditions = {(_norm(c["context"]), _norm(c["applies_to"])) for c in reference.get("conditions", [])}
    scores = {"units": _score(ref_units, units), "edges": _score(ref_edges, edges),
              "conditions": _score(ref_conditions, conditions)}
    return {"route": arm["route"], **scores, "fabricated_content": fabricated,
            "correction_actions": sum(s["omissions"] + s["additions"] for s in scores.values()),
            "blocking_issues": list(arm["issues"]), "output_hash": stable_hash(
                {"objects": sorted(text.values()), "edges": sorted(edges), "conditions": sorted(conditions)})}


def decide(criteria: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Pre-registered decision. Missing thresholds or references block; never 'accepted'."""
    thresholds = criteria.get("thresholds") or {}
    missing = [k for k in THRESHOLD_KEYS if not isinstance(thresholds.get(k), (int, float))
               or isinstance(thresholds.get(k), bool)]
    if missing:
        return {"decision": "BLOCKED", "reason": "thresholds_unspecified", "missing": missing}
    if not cases or any(not c.get("reference_independent") for c in cases):
        return {"decision": "BLOCKED", "reason": "independent_reference_missing"}
    failures = []
    for case in cases:
        result = case["result"]
        per_unit = result["correction_actions"] / max(result["units"]["reference"], 1)
        checks = {
            "fabricated_content": result["fabricated_content"] <= FABRICATED_CONTENT_MAX,
            "unit_recall": (result["units"]["recall"] or 0) >= thresholds["unit_recall_min"],
            "unit_precision": (result["units"]["precision"] or 0) >= thresholds["unit_precision_min"],
            "edge_recall": (result["edges"]["recall"] or 0) >= thresholds["edge_recall_min"],
            "edge_precision": (result["edges"]["precision"] or 0) >= thresholds["edge_precision_min"],
            "condition_recall": result["conditions"]["recall"] is None
            or result["conditions"]["recall"] >= thresholds["condition_recall_min"],
            "correction_work": per_unit <= thresholds["correction_actions_max_per_reference_unit"],
        }
        failures.extend({"source_sha256": case["source_sha256"], "check": k} for k, ok in checks.items() if not ok)
    return ({"decision": "ITERATE", "failures": failures} if failures else
            {"decision": "ACCEPTANCE_CRITERIA_MET",
             "note": "Inhoudelijke acceptatie van de route op dit corpus; menselijke graafreview blijft per document vereist."})


def legacy_route_inventory(envelopes: list[dict[str, Any]]) -> dict[str, Any]:
    """Read-only: decision trees formed under the retired structural route.

    Their evidence stays readable; re-forming or correcting their units fails
    closed and needs an explicit successor revision. Attempts reserved before
    the cutover are listed so an operator can see them; nothing is changed.
    """
    rows = []
    for envelope in envelopes:
        if envelope.get("class") != "beslisboom" or envelope.get("decision_tree_formation"):
            continue
        attempts = envelope.get("processing_attempts") or []
        rows.append({
            "snapshot_id": envelope.get("snapshot_id"),
            "content_kind": envelope.get("content_kind"),
            "recorded_route": envelope.get("decision_unit_contract")
            or ("structural-graph-without-unit-contract" if "decision_graph" in envelope else None),
            "recorded_processing_mode": (envelope.get("processing_configuration") or {}).get("mode"),
            "running_attempts": [a.get("attempt_id") for a in attempts if a.get("state") == "running"],
            "publication_eligibility": envelope.get("publication_eligibility"),
            "graph_reviews": len(envelope.get("decision_graph_reviews") or []),
        })
    return {"version": VERSION, "legacy_snapshots": rows,
            "attempts_reserved_before_cutover": [r["snapshot_id"] for r in rows if r["running_attempts"]]}
