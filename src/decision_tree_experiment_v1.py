"""Audit-domain experiment: structural baseline versus source-bound proposal route.

Both arms run on the same frozen source bytes and the same extraction. Nothing
here writes KnowledgeObjects, review bindings, workflow state or publication
records; outputs are comparison evidence only (Protocol §10). The best outcome
``decide`` can return is ``READY FOR IMPLEMENTATION``; it never activates a route.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from src.integrity_kernel import sha256_bytes, stable_hash

VERSION = "decision-tree-route-experiment-v1"
ROUTES = ("structural-baseline", "semantic-proposal-candidate")
PROPOSER_VERSION = "decision-tree-proposer-v1"
FABRICATED_CONTENT_MAX = 0  # Protocol §10: zero tolerance, not a tunable threshold.
THRESHOLD_KEYS = ("unit_recall_min", "unit_precision_min", "edge_recall_min", "edge_precision_min",
                  "condition_recall_min", "correction_actions_max_ratio_to_baseline")
PROPOSER_PROMPT = (
    "You propose the structure of one decision tree from frozen source blocks. "
    "Select exact character spans only; never write, repair or summarise source text. "
    "quoted_text must equal the selected spans joined by single spaces. "
    "Roles: start, question, action, outcome, context. Answer labels (for example Ja/Nee) "
    "are route evidence on a connection (label_span), never units. Cite evidence_ids from "
    "evidence_items that support each connection itself. Use to=null for a target you "
    "cannot identify and add an unresolved entry instead of guessing."
)


class ExperimentError(ValueError):
    pass


def _manifest(source_id: str, title: str, digest: str) -> dict[str, Any]:
    return {"canonical_source": {
        "source_id": source_id, "title": title, "publisher": "V&VN",
        "source_url": f"urn:vvn:freeze:{digest}", "source_type": "pdf", "source_level": 1,
        "canonicality": "canonical", "source_checksum": digest, "checksum_algorithm": "sha256",
        "integrity_status": "verified", "publication_date": "experiment", "version": "experiment"}}


def frozen_input(path: Path, *, document_id: str, source_id: str) -> dict[str, Any]:
    """One extraction shared by both arms; evidence inventory is reconstructable."""
    from src.decision_graph_v1 import evidence_inventory, pdf_fragments
    data = Path(path).read_bytes()
    digest = sha256_bytes(data)
    fragments = list(pdf_fragments(Path(path), document_id=document_id, source_id=source_id, use_docling=False))
    return {"path": Path(path), "data": data, "source_sha256": digest, "document_id": document_id,
            "source_id": source_id, "fragments": fragments,
            "inventory": evidence_inventory(Path(path), fragments, digest)}


def baseline_arm(frozen: dict[str, Any], *, title: str = "Beslisboom") -> dict[str, Any]:
    """Current structural route, read-only: unit construction plus geometric proposals."""
    from src.beslisboom_path_v1 import boom_spec_from_fragments
    from src.decision_graph_v1 import graph_issues, prepare_graph
    from src.decision_unit_construction_v1 import construction_spec
    from src.operations_console_v1 import transform_generic
    fragments = deepcopy(frozen["fragments"])
    spec = construction_spec(boom_spec_from_fragments(document_id=frozen["document_id"], title=title,
                             family="experiment", class_="beslisboom", fragments=fragments), fragments)
    objects = transform_generic(spec, _manifest(frozen["source_id"], title, frozen["source_sha256"]), fragments)
    prepared = prepare_graph(frozen["path"], frozen["data"], "pdf", fragments, objects, frozen["source_sha256"])
    graph = prepared["decision_graph"]
    return {"route": ROUTES[0], "objects": objects, "graph": graph, "context_bindings": [],
            "issues": graph_issues(graph, objects, prepared["decision_graph_evidence"])}


def candidate_arm(frozen: dict[str, Any], proposal: Any, *, model: str,
                  title: str = "Beslisboom") -> dict[str, Any]:
    """Proposal -> sole materialiser -> existing transform and graph validation."""
    from src.decision_graph_v1 import graph_issues
    from src.decision_tree_construction_v1 import bind_graph, construct
    from src.operations_console_v1 import transform_generic
    fragments = deepcopy(frozen["fragments"])
    construction = construct(proposal, document_id=frozen["document_id"], title=title, family="experiment",
                             class_="beslisboom", content_kind="pdf", fragments=fragments,
                             inventory=frozen["inventory"], model=model)
    objects = transform_generic(construction["spec"], _manifest(frozen["source_id"], title, frozen["source_sha256"]),
                                fragments)
    # Source-derived bundle evidence, exactly as the existing graph preparation stamps it.
    from src.decision_bundles_v1 import stamp_bundles
    from src.integrity_kernel import stamp_canonical_hashes
    stamp_bundles(fragments, objects)
    for obj in objects:
        stamp_canonical_hashes(obj)
    graph = bind_graph(construction, objects, frozen["source_sha256"])
    return {"route": ROUTES[1], "objects": objects, "graph": graph, "construction": construction,
            "context_bindings": construction["context_bindings"],
            "issues": graph_issues(graph, objects, frozen["inventory"])}


def request_proposal(frozen: dict[str, Any], *, api_key: str, model: str, limits: Any,
                     post_json: Callable | None = None) -> dict[str, Any]:
    """Bounded provider call outside any write transaction; failures never fall back."""
    from src.decision_tree_construction_v1 import proposal_inputs
    from src.decision_tree_proposal_v1 import proposal_schema
    from src.llm_provider_v1 import OPENAI_RESPONSES_URL
    from src.operations_console_v1 import ConsoleError
    from src.pre_review_semantic_v1 import _bounded_provider_json, _extract_output_text
    if not str(api_key or "").strip():
        raise ConsoleError("pre_review_llm_api_key_required")
    evidence_items = {key: {k: v for k, v in item.items() if k in {"kind", "text", "page", "bbox", "record"}}
                      for key, item in frozen["inventory"]["items"].items()}
    payload = {"model": model, "input": [
        {"role": "developer", "content": PROPOSER_PROMPT},
        {"role": "user", "content": json.dumps({"source_blocks": proposal_inputs(frozen["fragments"]),
                                                "evidence_items": evidence_items}, ensure_ascii=False)}],
        "text": {"format": {"type": "json_schema", "name": "decision_tree_proposal", "strict": True,
                            "schema": proposal_schema()}}}
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    response = (_bounded_provider_json(OPENAI_RESPONSES_URL, headers, payload, limits) if post_json is None
                else post_json(OPENAI_RESPONSES_URL, headers, payload, limits.total))
    if not isinstance(response, dict):
        raise ConsoleError("pre_review_llm_response_invalid")
    try:
        return json.loads(_extract_output_text(response))
    except json.JSONDecodeError as exc:
        raise ConsoleError("pre_review_llm_response_invalid") from exc


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
        base, cand = case["results"][ROUTES[0]], case["results"][ROUTES[1]]
        checks = {
            "fabricated_content": cand["fabricated_content"] <= FABRICATED_CONTENT_MAX,
            "unit_recall": (cand["units"]["recall"] or 0) >= thresholds["unit_recall_min"],
            "unit_precision": (cand["units"]["precision"] or 0) >= thresholds["unit_precision_min"],
            "edge_recall": (cand["edges"]["recall"] or 0) >= thresholds["edge_recall_min"],
            "edge_precision": (cand["edges"]["precision"] or 0) >= thresholds["edge_precision_min"],
            "condition_recall": cand["conditions"]["recall"] is None
            or cand["conditions"]["recall"] >= thresholds["condition_recall_min"],
            "correction_work": cand["correction_actions"]
            <= thresholds["correction_actions_max_ratio_to_baseline"] * max(base["correction_actions"], 1),
        }
        failures.extend({"source_sha256": case["source_sha256"], "check": k} for k, ok in checks.items() if not ok)
    return ({"decision": "ITERATE", "failures": failures} if failures else
            {"decision": "READY FOR IMPLEMENTATION",
             "note": "Geen activering: omschakeling vereist protocolwijziging (§15) en een afzonderlijke PR."})


def legacy_route_inventory(envelopes: list[dict[str, Any]]) -> dict[str, Any]:
    """Read-only decommission precondition: which PDF trees still depend on the old route.

    The structural route is implied by class and kind, not by the recorded
    prose ``processing_configuration``; the durable marker is the envelope's
    ``decision_unit_contract``. Nothing is changed or re-routed here.
    """
    rows = []
    for envelope in envelopes:
        if envelope.get("content_kind") != "pdf" or envelope.get("class") != "beslisboom":
            continue
        attempts = envelope.get("processing_attempts") or []
        rows.append({
            "snapshot_id": envelope.get("snapshot_id"),
            "recorded_route": envelope.get("decision_unit_contract")
            or ("structural-graph-without-unit-contract" if "decision_graph" in envelope else None),
            "recorded_processing_mode": (envelope.get("processing_configuration") or {}).get("mode"),
            "running_attempts": [a.get("attempt_id") for a in attempts if a.get("state") == "running"],
            "retryable_blocked": envelope.get("publication_eligibility") == "pre_review_blocked",
            "publication_eligibility": envelope.get("publication_eligibility"),
            "graph_reviews": len(envelope.get("decision_graph_reviews") or []),
        })
    return {"version": VERSION, "snapshots": rows,
            "decommission_blockers": [r["snapshot_id"] for r in rows
                                      if r["running_attempts"] or r["retryable_blocked"]]}
