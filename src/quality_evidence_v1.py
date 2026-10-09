"""Non-authoritative processing/review evidence for passive quality measurements.

Evidence lives in the existing envelope/ledger transaction, never in canonical
object metadata: adding measurements must not invalidate a review hash.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.integrity_kernel import compute_canonical_object_hash, stable_hash

VERSION = "quality-evidence-v1"
RUNS = "quality_processing_runs"


def instant() -> str:
    return datetime.now(timezone.utc).isoformat()


def route_of(obj: dict[str, Any]) -> dict[str, Any]:
    metadata = obj.get("metadata") or {}
    formation = metadata.get("passage_formation") or {}
    semantic = metadata.get("semantic_passage") or {}
    strategy = formation.get("strategy", "unknown")
    if strategy not in {"semantic", "deterministic"}:
        strategy = "unknown"
    origin = semantic.get("selection_origin")
    if origin == "coverage_remainder":
        route = "remainder"
    elif strategy == "semantic" and origin == "proposal_selected":
        route = "semantic"
    elif strategy == "deterministic":
        route = "deterministic"
    else:
        route = "unknown"
    return {"route": route, "strategy": strategy, "selection_origin": origin or (
        "deterministic" if strategy == "deterministic" else "unknown"
    ), "policy_version": formation.get("policy_version"), "model": semantic.get("model")}


def content_fingerprint(obj: dict[str, Any]) -> dict[str, Any]:
    """Compare source text/type without treating confirmation stamps as edits.

    Complex semantics are deliberately unknown until their normalized evidence
    is sufficient; a missing comparison must never produce a success score.
    """
    kind = obj.get("confirmed_object_type") or obj.get("object_type")
    if kind in {None, "unclassified"}:
        kind = obj.get("proposed_object_type")
    relation_rows = obj.get("confirmed_knowledge_relations")
    if relation_rows is None:
        relation_rows = obj.get("proposed_knowledge_relations")
    relations = sorted((str(r.get("relation_type")), str(r.get("target_object_id")),
                        str(r.get("target_object_version"))) for r in relation_rows or []
                       if r.get("relation_type") not in {"parent", "child"})
    semantics = obj.get("confirmed_recommendation_semantics")
    if semantics is None:
        semantics = obj.get("proposed_recommendation_semantics")
    legacy = bool(((obj.get("relations") or obj.get("confirmed_relations")) and relation_rows is None)
                  or obj.get("proposed_recommendation_strength") or obj.get("confirmed_recommendation_strength"))
    return {"text": stable_hash((obj.get("content") or {}).get("clean_text", "")),
            "type": kind, "relations": stable_hash(relations),
            "semantics": stable_hash(semantics),
            "complex_semantics": legacy}



def record_processing(envelope: dict[str, Any], objects: list[dict[str, Any]], *,
                      fragments: list[dict[str, Any]], replay: dict[str, Any] | None,
                      started_at: str, outcome: str = "succeeded", reason: str = "") -> None:
    """Append to a prepared envelope; its existing commit owns durability."""
    if outcome == "succeeded" and fragments and envelope.get("snapshot_id") and envelope.get("document_id"):
        from src.source_representation_v1 import prepare, PREPARED
        envelope[PREPARED] = prepare(envelope, fragments, correction_revision=envelope.get("source_correction_revision"))
    run = {"version": VERSION, "run_id": "qp_" + uuid4().hex,
           "source_hash": envelope.get("sha256"), "started_at": started_at,
           "finished_at": instant(), "outcome": outcome, "reason": reason,
           "extractor_versions": sorted({str(f["parser_version"]) for f in fragments if f.get("parser_version")}),
           "semantic_identity": deepcopy((replay or {}).get("identity")),
           "execution": (replay or {}).get("semantic_execution"), "candidates": []}
    extraction = getattr(fragments, "extraction_record", None)
    if extraction is not None:
        # Prepared metadata only. Complete model output and bindings become
        # durable in the SAME existing atomic envelope/object commit.
        run["document_extraction"] = deepcopy(extraction)
        from src.integrity_kernel import stable_hash
        retained = run["document_extraction"]
        retained["prepared_fragments"] = deepcopy(list(fragments))
        retained["prepared_fragments_hash"] = stable_hash(retained["prepared_fragments"])
        retained.pop("record_hash", None)
        retained["record_hash"] = stable_hash(retained)
    for obj in objects:
        if obj.get("object_type") == "document":
            continue
        run["candidates"].append({
            "object_id": obj["object_id"], "object_version": obj["object_version"],
            "canonical_hash": compute_canonical_object_hash(obj),
            "fingerprint": content_fingerprint(obj), "origin": route_of(obj),
            "structural": content_fingerprint(obj)["type"] in {"heading", "path"},
        })
    envelope[RUNS] = [*deepcopy(envelope.get(RUNS) or []), run]
    run["source_fragments"] = [{key: deepcopy(fragment[key]) for key in (
        "fragment_id", "fragment_hash", "raw_text", "clean_text", "section_path", "heading", "source_page", "bbox", "source_locator", "source_text_view", "source_layout_findings")
        if key in fragment} for fragment in fragments]


def review_evidence(envelope: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    runs = envelope.get(RUNS) or []
    run = runs[-1] if runs else {}
    candidate = next((r for r in run.get("candidates", []) if r["object_id"] == before.get("object_id")), None)
    evidence = {"version": VERSION, "run_id": run.get("run_id"),
                "before_version": before.get("object_version"),
                "after_version": after.get("object_version"),
                "after_hash": compute_canonical_object_hash(after),
                "origin": deepcopy(candidate["origin"]) if candidate else {"route": "unknown"},
                "structural": bool(candidate and candidate.get("structural")),
                "changed_fields": [], "unchanged_proposal": None}
    if candidate:
        baseline, final = candidate["fingerprint"], content_fingerprint(after)
        evidence["changed_fields"] = [k for k in ("text", "type", "relations", "semantics") if baseline.get(k) != final.get(k)]
        if evidence["changed_fields"] or before.get("object_version") != candidate["object_version"]:
            evidence["unchanged_proposal"] = False
        elif not baseline.get("complex_semantics") and not final.get("complex_semantics"):
            evidence["unchanged_proposal"] = True
    return evidence
