"""The single formation route for decision trees (Protocol §5.4, strategy C).

source extraction -> source-bound model proposal -> deterministic construction
(``materialise_knowledge_candidates`` is the only candidate creator) ->
existing transform, admission, review and publication.

PDF trees and structured exports both get their proposal from the configured
model and pass through the same contract and constructor. For an export the
explicit nodes, branches, answer labels and result bundles stay authoritative
source evidence: a proposal that does not reproduce every one of them exactly,
or that adds a route, is rejected (``verify_export_preserved``). A failing
proposer fails the attempt; there is no other route to fall back to.
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
PROPOSER_PROMPT = (
    "You propose the structure of one decision tree from frozen source blocks. "
    "Select exact character spans only; never write, repair or summarise source text. "
    "quoted_text must equal the selected spans joined by single spaces. "
    "Roles: start, question, action, outcome, context. Answer labels (for example Ja/Nee) "
    "are route evidence on a connection (label_span), never units. Cite evidence_ids from "
    "evidence_items that support each connection itself. Use to=null for a target you "
    "cannot identify and add an unresolved entry instead of guessing."
)
# Appended for structured exports only, so the PDF prompt stays unchanged.
EXPORT_PROMPT = (
    " This source is a structured export: each text evidence item names its export_id, and "
    "export_edge records name the export_id of their from and to items. Propose exactly one unit "
    "per exported item, selecting its complete text. Propose exactly one connection per "
    "export_edge evidence item, citing that item alone, between the units of its from and to "
    "items; never add, drop or redirect a connection. Propose one result bundle per container "
    "item (bundle_role container) with exactly the member items of its bundle_id."
)

Proposer = Callable[[dict[str, Any]], tuple[dict[str, Any], str]]


def _error(code: str, detail: str = ""):
    from src.operations_console_v1 import ConsoleError
    return ConsoleError(code, detail) if detail else ConsoleError(code)


def request_input(frozen: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The developer prompt and source view a proposer receives; nothing else."""
    evidence_items = {key: {k: v for k, v in item.items() if k in {"kind", "text", "page", "bbox", "record"}}
                      for key, item in frozen["inventory"]["items"].items()}
    if frozen.get("kind") == "boom":
        # Request-only view: which exported item each text item is, so export_edge
        # records can be read. The recorded inventory itself is unchanged.
        for fragment in frozen["fragments"]:
            item = evidence_items.get(fragment["fragment_id"])
            if item is not None and item["kind"] == "text":
                item["record"] = {"export_id": fragment.get("boom_id"), "export_kind": fragment.get("boom_kind"),
                                  "bundle_id": fragment.get("bundle_id"), "bundle_role": fragment.get("bundle_role")}
    prompt = PROPOSER_PROMPT + (EXPORT_PROMPT if frozen.get("kind") == "boom" else "")
    return prompt, {"source_blocks": proposal_inputs(frozen["fragments"]), "evidence_items": evidence_items}


def request_proposal(frozen: dict[str, Any], *, api_key: str, model: str, limits: Any,
                     post_json: Callable | None = None) -> dict[str, Any]:
    """Bounded provider call outside any write transaction; failures never fall back."""
    from src.decision_tree_proposal_v1 import proposal_schema
    from src.llm_provider_v1 import OPENAI_RESPONSES_URL
    from src.pre_review_semantic_v1 import _bounded_provider_json, _extract_output_text
    if not str(api_key or "").strip():
        raise _error("pre_review_llm_api_key_required")
    prompt, source = request_input(frozen)
    payload = {"model": model, "input": [
        {"role": "developer", "content": prompt},
        {"role": "user", "content": json.dumps(source, ensure_ascii=False)}],
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


def verify_export_preserved(construction: dict[str, Any], data: bytes,
                            fragments: list[dict[str, Any]]) -> None:
    """Fail closed unless the construction carries the export's explicit graph exactly.

    Every non-empty exported item is one whole unit; every well-formed branch
    between them is one edge with its literal label and only its own evidence;
    no other edge exists; every exported bundle is reproduced with its members;
    no item that an exported branch leads to is proposed as an entrypoint.
    """
    from src.decision_graph_v1 import export_branches
    candidates = construction["spec"]["objects"][1:]
    object_for = {}
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
    if len(candidates) != len(object_for):
        raise DecisionTreeProposalError("decision_export_node_not_preserved")
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
        from src.operations_console_v1 import ConsoleError, docling_console_error
        if isinstance(exc, DoclingError):
            # Same conversion as every extraction route: code plus page numbers.
            raise docling_console_error(exc) from exc
        if isinstance(exc, ConsoleError):
            raise
        raise _error("invalid_boom_freeze" if kind == "boom" else "invalid_decision_pdf") from exc
    if kind == "pdf":
        from src.docling_pdf_v1 import release_conversion_capacity
        release_conversion_capacity()
    source_hash = sha256_bytes(data)
    inventory = source_evidence(path, data, kind, fragments, source_hash)
    frozen = {"kind": kind, "fragments": fragments, "inventory": inventory, "formation_context": context}
    invalid: list[str] = []
    types = None
    if proposer is None:
        raise _error("pre_review_llm_decision_tree_proposer_unbound")
    try:
        proposal, model = proposer(frozen)
        if kind == "boom":
            from src.decision_graph_v1 import export_branches
            valid = {index for index, _branch in export_branches(data, fragments)}
            invalid = [f"invalid_export_branch:{i}" for i in range(len(json.loads(data).get("branches", [])))
                       if i not in valid]
            from src.decision_tree_proposal_v1 import validate_proposal
            validate_proposal(proposal, blocks=proposal_inputs(fragments), inventory=inventory)
            types = export_types(proposal, fragments)
        construction = construct(proposal, document_id=document_id, title=title, family=family, class_=class_,
                                 content_kind=kind, fragments=fragments, inventory=inventory, model=model,
                                 proposed_types=types)
        if kind == "boom":
            verify_export_preserved(construction, data, fragments)
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
