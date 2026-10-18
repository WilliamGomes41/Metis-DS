"""The single formation route for decision trees (Protocol §5.4, strategy C).

source extraction -> source-bound proposal -> deterministic construction
(``materialise_knowledge_candidates`` is the only candidate creator) ->
existing transform, admission, review and publication.

PDF trees get their proposal from the configured model; JSON exports get a
deterministic proposal from their explicit records. Both pass through the same
contract and constructor. A failing proposer fails the attempt; there is no
other route to fall back to.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from src.decision_tree_construction_v1 import (
    CONTRACT as CONSTRUCTION_CONTRACT,
    FORMATION_MODE as ROUTE,
    bind_graph,
    construct,
    proposal_inputs,
)
from src.decision_tree_proposal_v1 import CONTRACT as PROPOSAL_CONTRACT, DecisionTreeProposalError
from src.integrity_kernel import sha256_bytes, stamp_canonical_hashes

POLICY_VERSION = "decision-tree-formation-policy-v1.0.0"
SPEC_KEY = "_decision_tree_formation"
ENVELOPE_KEY = "decision_tree_formation"
EXPORT_MODEL = "deterministic-export-v1"
PROPOSER_PROMPT = (
    "You propose the structure of one decision tree from frozen source blocks. "
    "Select exact character spans only; never write, repair or summarise source text. "
    "quoted_text must equal the selected spans joined by single spaces. "
    "Roles: start, question, action, outcome, context. Answer labels (for example Ja/Nee) "
    "are route evidence on a connection (label_span), never units. Cite evidence_ids from "
    "evidence_items that support each connection itself. Use to=null for a target you "
    "cannot identify and add an unresolved entry instead of guessing."
)

Proposer = Callable[[dict[str, Any]], tuple[dict[str, Any], str]]


def _error(code: str, detail: str = ""):
    from src.operations_console_v1 import ConsoleError
    return ConsoleError(code, detail) if detail else ConsoleError(code)


def request_proposal(frozen: dict[str, Any], *, api_key: str, model: str, limits: Any,
                     post_json: Callable | None = None) -> dict[str, Any]:
    """Bounded provider call outside any write transaction; failures never fall back."""
    from src.decision_tree_proposal_v1 import proposal_schema
    from src.llm_provider_v1 import OPENAI_RESPONSES_URL
    from src.pre_review_semantic_v1 import _bounded_provider_json, _extract_output_text
    if not str(api_key or "").strip():
        raise _error("pre_review_llm_api_key_required")
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
        raise _error("pre_review_llm_response_invalid")
    try:
        return json.loads(_extract_output_text(response))
    except json.JSONDecodeError as exc:
        raise _error("pre_review_llm_response_invalid") from exc


def export_proposal(data: bytes, fragments: list[dict[str, Any]],
                    inventory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    """Deterministic proposal from an explicit export: one unit per exported item.

    Modes stay for the reviewer (``role_ambiguous``): the export states kinds and
    branches, not answer semantics. Returns proposal, proposed types, unresolved.
    """
    from src.decision_graph_v1 import export_branches
    blocks = proposal_inputs(fragments)
    by_fragment: dict[str, list[dict[str, Any]]] = {}
    for block in blocks:
        for fid in block["source_fragment_ids"]:
            by_fragment.setdefault(fid, []).append(block)
    units, types, refs = [], {}, {}
    for index, fragment in enumerate(fragments):
        text = " ".join(str(fragment.get("clean_text") or "").split())
        candidates = by_fragment.get(fragment["fragment_id"], [])
        if not text:
            continue
        if len(candidates) != 1 or candidates[0]["text"].count(text) != 1:
            raise DecisionTreeProposalError("decision_export_fragment_unselectable",
                                            fragment_id=fragment["fragment_id"])
        block = candidates[0]
        start = block["text"].index(text)
        ref = f"u{index + 1}"
        member = fragment.get("bundle_role") == "member"
        units.append({"ref": ref, "role": "context" if member else "outcome" if fragment.get("boom_kind") == "outcome"
                      else "start" if fragment.get("boom_kind") == "path" else "action",
                      "selection": None, "entry": False, "quoted_text": text,
                      "spans": [{"block_id": block["block_id"], "start": start, "end": start + len(text)}]})
        types[ref] = str(fragment.get("boom_kind") or "node")
        refs[str(fragment.get("boom_id"))] = ref
    valid = dict(export_branches(data, fragments))
    connections = [{"ref": f"c{index}", "from": refs[branch["from"]], "to": refs[branch["to"]],
                    "kind": "answer" if branch.get("label") else "continue", "label_span": None,
                    "evidence_ids": [f"export-branch-{index}"]}
                   for index, branch in valid.items() if branch["from"] in refs and branch["to"] in refs]
    bundles = []
    for fragment in fragments:
        if fragment.get("bundle_role") == "container":
            members = [refs[str(f["boom_id"])] for f in fragments
                       if f.get("bundle_role") == "member" and f.get("bundle_id") == fragment["fragment_id"]]
            bundles.append({"ref": f"b{len(bundles) + 1}", "container": refs[str(fragment["boom_id"])],
                            "members": members})
    payload_branches = json.loads(data).get("branches", [])
    invalid = [f"invalid_export_branch:{i}" for i in range(len(payload_branches)) if i not in valid]
    proposal = {"contract": PROPOSAL_CONTRACT, "units": units, "connections": connections,
                "context_bindings": [], "result_bundles": bundles,
                "unresolved": [{"ref": f"r{i + 1}", "subject": unit["ref"], "code": "role_ambiguous"}
                               for i, unit in enumerate(u for u in units if u["role"] != "context")]}
    return proposal, types, invalid


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
        from src.decision_graph_v1 import pdf_fragments
        return pdf_fragments(path, document_id=document_id, source_id=source_id, deadline=deadline,
                             use_docling=use_docling)
    if kind == "boom":
        from src.beslisboom_path_v1 import extract_boom_fragments
        from src.decision_bundles_v1 import split_bundles
        return split_bundles(extract_boom_fragments(data, document_id=document_id, source_id=source_id))
    raise _error("decision_tree_source_kind_unsupported")


def prepare(kind: str, path: Path, *, data: bytes, document_id: str, source_id: str, title: str,
            family: str, class_: str, formation_context: dict[str, Any] | None,
            proposer: Proposer | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract, propose and construct; raises on any failure (attempt records it)."""
    from src.decision_graph_v1 import source_evidence
    context = formation_context or {}
    retained = context.get("retained_fragments")
    try:
        fragments = (list(retained) if retained is not None else
                     source_fragments(kind, path, data, document_id=document_id, source_id=source_id,
                                      deadline=context.get("attempt_deadline")))
    except Exception as exc:
        from src.docling_contract_v1 import DoclingError
        from src.operations_console_v1 import ConsoleError
        if isinstance(exc, (DoclingError, ConsoleError)):
            raise
        raise _error("invalid_boom_freeze" if kind == "boom" else "invalid_decision_pdf") from exc
    if kind == "pdf":
        from src.docling_pdf_v1 import release_conversion_capacity
        release_conversion_capacity()
    source_hash = sha256_bytes(data)
    inventory = source_evidence(path, data, kind, fragments, source_hash)
    frozen = {"fragments": fragments, "inventory": inventory, "formation_context": context}
    invalid: list[str] = []
    types = None
    try:
        if kind == "boom":
            proposal, types, invalid = export_proposal(data, fragments, inventory)
            model = EXPORT_MODEL
        else:
            if proposer is None:
                raise _error("pre_review_llm_decision_tree_proposer_unbound")
            proposal, model = proposer(frozen)
        construction = construct(proposal, document_id=document_id, title=title, family=family, class_=class_,
                                 content_kind=kind, fragments=fragments, inventory=inventory, model=model,
                                 proposed_types=types)
    except DecisionTreeProposalError as exc:
        raise _error("pre_review_llm_proposal_rejected", exc.code) from exc
    except Exception as exc:  # materialisation failures keep their stable code
        from src.knowledge_materialisation_v1 import MaterialisationError
        if isinstance(exc, MaterialisationError):
            raise _error("pre_review_llm_proposal_rejected", exc.code) from exc
        raise
    construction["graph_plan"]["unresolved"].extend(invalid)
    if kind == "boom":
        _export_enrichment(construction, fragments, document_id)
    spec = construction.pop("spec")
    spec[SPEC_KEY] = {"construction": construction, "inventory": inventory,
                      "formation": {"route": ROUTE, "policy_version": POLICY_VERSION,
                                    "proposal_contract": PROPOSAL_CONTRACT,
                                    "construction_contract": CONSTRUCTION_CONTRACT, "model": model,
                                    "proposal_hash": construction["proposal_hash"],
                                    "reason": "only_admitted_route_for_decision_trees"}}
    return fragments, spec


def finalize(record: dict[str, Any], objects: list[dict[str, Any]], fragments: list[dict[str, Any]],
             source_hash: str, *, actor: str, with_graph: bool) -> dict[str, Any]:
    """Record the route; with a review policy also bind the reviewable graph.

    Without a review policy no graph review exists, so no graph is stored and
    no graph-based admission is derived (unchanged from the export behaviour).
    """
    from src.decision_bundles_v1 import stamp_bundles
    from src.decision_unit_construction_v1 import apply_gate
    from src.passage_register_v1 import apply_passage_register
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


def llm_proposer(env, *, post_json=None) -> Proposer:
    """Model proposer bound to deployment configuration; honours the attempt deadline."""
    def propose(frozen: dict[str, Any]) -> tuple[dict[str, Any], str]:
        import time
        from dataclasses import replace
        from src.bounded_model_call_v1 import CLEANUP_SECONDS, ModelCallLimits, load_limits
        from src.llm_provider_v1 import load_llm_provider_config
        context = frozen["formation_context"]
        provider = load_llm_provider_config(env)
        if not provider.model:
            raise _error("pre_review_llm_model_required")
        limits = (ModelCallLimits(**context["model_call_limits"]) if context.get("model_call_limits")
                  else load_limits(env))
        deadline = context.get("attempt_deadline")
        if deadline is not None:
            remaining = deadline - time.monotonic() - CLEANUP_SECONDS
            if remaining <= 0:
                raise _error("processing_attempt_expired")
            limits = replace(limits, total=min(limits.total, remaining),
                             connect=min(limits.connect, remaining), idle=min(limits.idle, remaining))
        return request_proposal(frozen, api_key=provider.api_key, model=provider.model,
                                limits=limits, post_json=post_json), provider.model
    return propose
