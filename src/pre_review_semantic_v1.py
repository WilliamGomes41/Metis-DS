"""Source-bound semantic passage formation before human Review.

This module owns the optional production LLM step between source extraction and
Review object creation. It does not write canonical knowledge, review decisions,
publication state, or serving state. The model may only select exact source
spans and propose a closed object type; Metis reconstructs candidate text from
the source through ``semantic_passage_v1``.

The existing deterministic splitter remains available only as an explicit
rollback mode. Semantic-mode failures never fall back silently.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from contextvars import ContextVar
from typing import Any, Callable, Mapping
from src.bounded_model_call_v1 import ModelCallLimits, load_limits, post_json as bounded_post_json

# Per execution, including worker threads; never persisted as document authority.
_PROCESSING_REFERENCE: ContextVar[str] = ContextVar("pre_review_processing_reference", default="-")

from src.context_aware_split_v1 import split_context_aware_units
from src.llm_provider_v1 import OPENAI_RESPONSES_URL, load_llm_provider_config
from src.object_taxonomy_v1 import (
    extract_object_type,
    is_kennisplatform_chrome_text,
    is_strength_stamp,
)
from src.operations_console_v1 import ConsoleError
from src.recommendation_semantics_v1 import is_source_strength_label
from src.passage_formation_policy_v1 import (
    DETERMINISTIC_MODE,
    SEMANTIC_MODE,
    STRATEGY_DETERMINISTIC,
    STRATEGY_SEMANTIC,
    PASSAGE_FORMATION_POLICY_VERSION,
    PassageFormationDecision,
    PassageFormationPolicyError,
    deterministic_heading_decision,
    resolve_passage_formation_strategy,
)
from src.semantic_passage_v1 import (
    ALLOWED_PROPOSED_TYPES,
    SELECTION_ORIGIN_PROPOSAL,
    SEMANTIC_PASSAGE_VERSION,
    SemanticPassageError,
    attach_relation_proposals,
    semantic_coverage_units,
    semantic_source_blocks,
    semantic_units_from_proposal,
)
from src.semantic_replay_v1 import (
    EXECUTION_INFERENCE,
    EXECUTION_REPLAY,
    LOOKUP_HIT,
    LOOKUP_REJECTED,
    SEMANTIC_REPLAY_SPEC_KEY,
    build_replay_identity,
    exact_replay_lookup,
    replayed_record,
    validated_inference_record,
)
from src.source_occurrence_authority_v1 import prefer_authoritative_exact_occurrences
from src.source_reconstruction_v1 import RECONSTRUCTION_VERSION
from src.source_bound_fields_v2 import MODE as SEMANTIC_V2_MODE, evidence_schema, context_evidence_schema, CONTEXT_VERSION
from src.source_bound_fields_v3 import MODE as SEMANTIC_V3_MODE, VERSION as FIELDS_V3_VERSION
from src.source_evidence_resolution_v1 import (
    resolve_proposal_evidence, VERSION as EVIDENCE_RESOLUTION_VERSION,
    V3_VERSION as V3_EVIDENCE_RESOLUTION_VERSION,
)


PASSAGE_FORMATION_MODE_ENV = "METIS_PASSAGE_FORMATION_MODE"
DEFAULT_TIMEOUT_SECONDS = 900
MAX_INPUT_BYTES = 2_000_000
MAX_RESPONSE_BYTES = 4_000_000
LOGGER = logging.getLogger("metis.provider")
SEMANTIC_PROVIDER_ID = "openai-responses-v1"
SEMANTIC_DEVELOPER_PROMPT = (
    "Form meaning units for human review by selecting only exact source spans. "
    "Copy each selected source substring verbatim into its literal reference; "
    "never write, rewrite or paraphrase source text. Do not calculate character offsets. "
    "Every reference has block_id, literal and occurrence. Use occurrence:null for "
    "a unique exact match, otherwise the zero-based occurrence counting all exact "
    "matches including overlapping matches in that block. Never guess an occurrence. "
    "Group spans only when they form one independently understandable unit. "
    "Selections must be contiguous: across blocks include the entire remainder of the "
    "first block, every intervening block and the beginning of the last block. "
    "Do not stitch around any unselected content. A separate strength label belongs "
    "in strength_evidence; do not append it to the candidate across a gap. "
    "Keep target group, conditions, exceptions and modality with the statement "
    "they qualify. For every object return recommendation_semantics: null unless "
    "proposed_object_type is recommendation. For a recommendation, propose only "
    "closed direction/strength values and exact evidence references. Direction "
    "evidence must come from the selected recommendation text. Strength evidence "
    "may reference evidence_blocks. Treat only explicit strong/weak source wording "
    "as explicit strength; conditional/voorwaardelijk alone never means weak. "
    "Labels Sterk - voor/tegen and Zwak - voor/tegen state recommendation strength "
    "and direction, not evidence quality. Keep advice and conditions in mixed blocks. "
    "For knowledge relations return only source-bound relation proposals between "
    "objects selected in this same proposal. Use only applies_if, except_if, defines, "
    "explains, supported_by or supersedes. Identify source and target by their exact "
    "selected spans and bind relation evidence to exact evidence_blocks spans. "
    "Never infer a relation from proximity alone and never return parent/child here. "
    "Preserve source order. If no safe source-bound proposal is possible, return "
    "zero objects and a short abstain_reason."
)
SEMANTIC_V2_INSTRUCTION = (
    " Examine every supplied source block in source order. This is document-wide curation, "
    "not a sample, summary or demonstration: select all safely source-bound meaning units "
    "you can identify, including explicit recommendations. Do not stop after a few examples. "
    "Do not turn standalone labels into independent recommendations. Uncertain text remains "
    "available for human disposition; never invent missing content to increase coverage. "
    " For every object return field_evidence for all declared fields. Each field is an exact "
    "source span wholly within the selected candidate, or null with missing_reason "
    "not_stated, uncertain or not_applicable. Never invent or paraphrase field text. "
    "Preserve attribution, uncertainty, negation, conditions, exceptions, numbers and units. "
    "Field evidence is a proposal for human review, not a confirmation of truth. "
    "Return context_evidence for each object: exact evidence_blocks spans for target group, timing, "
    "condition, exception, negation, scope, list introduction, row/column header or support. "
    "Context belongs to this candidate. Use unresolved_reason for uncertain applicability or layout; "
    "never resolve geometry or missing information with general knowledge. Empty context_evidence "
    "means no separate context was identified, not that completeness has been proven."
)

SEMANTIC_V3_INSTRUCTION = (
    " Examine every selectable range in this bounded source task in source order. Perform complete curation of this task, "
    "not a sample or summary. Select all complete source-bound meaning units of the existing types: "
    "definition, explanation, condition, exception and recommendation. Examine all sections, "
    "including numbered and unnumbered recommendations. Preserve attribution, uncertainty, "
    "negation, conditions, exceptions, target group, modality, numbers and units. "
    "For each object return every field_evidence and context_evidence. All values must be exact "
    "source references or null with a closed missing reason. The recommendation_evidence_span "
    "is the entire normative core, without its list number or strength stamp. Never omit clinical "
    "qualifiers from it. Select a contiguous core; link separate strength metadata and necessary "
    "lists as context instead of stitching around source gaps. Distinguish actor_span (performer), "
    "target_group_span (patients) and scope_span (clinical situation). Do not invent a performer "
    "for an imperative: actor/subject may be not_stated. These three fields can reference exact "
    "applicable context: scope role for performer/situation, target_group role for patients. "
    "condition_span may also reference an exact applicable context entry with role condition. "
    "Other field evidence must stay within the selected core. Link every necessary heading, "
    "condition, exception, table/list, timing or abbreviation definition using context_evidence. "
    "A header alone does not realize an announced list/table: include its applicable content. "
    "Do not guess applicability from proximity or add general knowledge. Use unresolved_reason "
    "for uncertain scope, relation or layout. All references remain proposals for human review. "
    "Missing punctuation is not missing meaning. If selection_targets are supplied, select only "
    "meaning units wholly within the unselected source ranges identified by those exact literals, "
    "across all five knowledge types, not prior selections. Never stop after a few examples. "
    "formation_task.selectable_ranges is the authoritative candidate boundary, including for initial tasks. "
    "evidence_blocks are context-only; never form a new candidate from them. Source blocks may contain "
    "previous selections outside the selectable ranges: those ranges are context-only as well. "
)

SOURCE_ACCOUNTABILITY_INSTRUCTION = (
    " Return source_assessments for unselected metadata, structure or unresolved content. "
    "Each assessment covers one exact source span with a closed role and matching reason. "
    "Do not overlap candidate selections or other assessments. Split mixed blocks at exact "
    "boundaries; never classify clinical statements as metadata merely because their section "
    "is introductory or administrative. metadata means document_metadata or page_furniture; "
    "structure means navigation or document_structure; unresolved means unformed_meaning or "
    "uncertain_source_role. These are proposals for source disposition, never exclusions, "
    "human approval or proof of completeness. Omitted ranges remain explicitly unresolved. "
)


def _semantic_instruction(field_contract_v2=False, field_contract_v3=False):
    if field_contract_v3:
        return SEMANTIC_V3_INSTRUCTION + SOURCE_ACCOUNTABILITY_INSTRUCTION
    if field_contract_v2:
        return SEMANTIC_V2_INSTRUCTION + SOURCE_ACCOUNTABILITY_INSTRUCTION
    return ""


SEMANTIC_MODEL_CONFIG = {
    "api": "responses",
    "structured_output": "json_schema",
    "strict": True,
}

PostJson = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]


def _configured_passage_formation_mode(environ: Mapping[str, str]) -> str:
    return str(environ.get(PASSAGE_FORMATION_MODE_ENV, "") or "").strip() or SEMANTIC_V2_MODE


def _stamp_passage_formation(
    spec: dict[str, Any],
    decision: PassageFormationDecision,
) -> dict[str, Any]:
    """Persist the strategy decision as candidate evidence, not workflow authority."""

    for obj in spec.get("objects") or []:
        if obj.get("object_type") == "document":
            continue
        object_decision = decision
        if (
            decision.strategy == STRATEGY_SEMANTIC
            and (
                obj.get("object_type") == "heading"
                or obj.get("proposed_object_type") == "heading"
            )
        ):
            object_decision = deterministic_heading_decision()
        metadata = dict(obj.get("metadata") or {})
        metadata["passage_formation"] = object_decision.as_metadata()
        obj["metadata"] = metadata
    return spec


def _stable_json_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    limits = load_limits()
    from dataclasses import replace
    limits = replace(limits, total=timeout, connect=min(limits.connect, timeout), idle=min(limits.idle, timeout))
    return _bounded_provider_json(url, headers, payload, limits)


def _bounded_provider_json(url, headers, payload, limits, observation=None):
    call_id = uuid.uuid4().hex[:12]
    started = time.monotonic()
    LOGGER.info("METIS_PROVIDER start id=%s total=%s reference=%s", call_id, limits.total, _PROCESSING_REFERENCE.get())
    observation = observation if observation is not None else {}
    observation["call_id"] = call_id
    try:
        result = bounded_post_json(url, headers, payload, limits, observation=observation)
    except ConsoleError as exc:
        LOGGER.error("METIS_PROVIDER failure id=%s code=%s http=%s elapsed=%.2f reference=%s",
                     call_id, exc.code, observation.get("http_status", "-"), time.monotonic()-started, _PROCESSING_REFERENCE.get())
        raise
    LOGGER.info("METIS_PROVIDER success id=%s http=%s elapsed=%.2f reference=%s",
                call_id, observation.get("http_status", "-"), time.monotonic()-started, _PROCESSING_REFERENCE.get())
    return result


def _proposal_schema(field_contract_v2: bool = False, field_contract_v3: bool = False) -> dict[str, Any]:
    span = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "block_id": {"type": "string"},
            "literal": {"type": "string", "minLength": 1},
            "occurrence": {"type": ["integer", "null"], "minimum": 0},
        },
        "required": ["block_id", "literal", "occurrence"],
    }
    nullable_span = {
        "type": ["object", "null"],
        "additionalProperties": False,
        "properties": dict(span["properties"]),
        "required": list(span["required"]),
    }
    recommendation_semantics = {
        "type": ["object", "null"],
        "additionalProperties": False,
        "properties": {
            "direction": {"type": "string", "enum": ["for", "against"]},
            "direction_evidence": span,
            "strength": {
                "type": ["string", "null"],
                "enum": ["strong", "weak", None],
            },
            "strength_status": {
                "type": "string",
                "enum": ["explicit", "not_stated", "unmapped"],
            },
            "strength_evidence": nullable_span,
        },
        "required": [
            "direction",
            "direction_evidence",
            "strength",
            "strength_status",
            "strength_evidence",
        ],
    }
    relation = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source_spans": {"type": "array", "minItems": 1, "items": span},
            "relation_type": {
                "type": "string",
                "enum": [
                    "applies_if",
                    "except_if",
                    "defines",
                    "explains",
                    "supported_by",
                    "supersedes",
                ],
            },
            "target_spans": {"type": "array", "minItems": 1, "items": span},
            "evidence_spans": {"type": "array", "minItems": 1, "items": span},
        },
        "required": [
            "source_spans",
            "relation_type",
            "target_spans",
            "evidence_spans",
        ],
    }
    obj = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "spans": {"type": "array", "minItems": 1, "items": span},
            "proposed_object_type": {
                "type": "string",
                "enum": sorted(ALLOWED_PROPOSED_TYPES),
            },
            "recommendation_semantics": recommendation_semantics,
        },
        "required": [
            "spans",
            "proposed_object_type",
            "recommendation_semantics",
        ],
    }
    if field_contract_v2 or field_contract_v3:
        from src.source_bound_fields_v3 import evidence_schema as schema_v3
        obj["properties"]["field_evidence"] = schema_v3(span) if field_contract_v3 else evidence_schema(span)
        obj["required"].append("field_evidence")
        obj["properties"]["context_evidence"] = context_evidence_schema(span)
        obj["required"].append("context_evidence")
    result = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "objects": {"type": "array", "items": obj},
            "relations": {"type": "array", "items": relation},
            "abstain_reason": {"type": ["string", "null"]},
        },
        "required": ["objects", "relations", "abstain_reason"],
    }
    if field_contract_v2 or field_contract_v3:
        from src.source_accountability_v1 import assessment_schema
        result["properties"]["source_assessments"] = assessment_schema(span)
        result["required"].append("source_assessments")
    return result


def _extract_output_text(response: dict[str, Any]) -> str:
    if response.get("status") not in (None, "completed"):
        raise ConsoleError("pre_review_llm_response_not_completed")
    output = response.get("output")
    if not isinstance(output, list):
        raise ConsoleError("pre_review_llm_response_invalid")
    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise ConsoleError("pre_review_llm_refused")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    text = "".join(texts)
    if not text.strip():
        raise ConsoleError("pre_review_llm_response_empty")
    return text


def _request_payload(
    *,
    model: str,
    blocks: list[dict[str, Any]],
    evidence_blocks: list[dict[str, Any]],
    field_contract_v2: bool = False,
    field_contract_v3: bool = False,
    selection_targets=None,
    task=None,
) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "developer",
                "content": SEMANTIC_DEVELOPER_PROMPT + _semantic_instruction(field_contract_v2, field_contract_v3),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "source_blocks": blocks,
                        "evidence_blocks": evidence_blocks,
                        **({"selection_targets": selection_targets} if selection_targets is not None else {}),
                        **({"formation_task": task} if task is not None else {}),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "pre_review_semantic_passage_proposal",
                "strict": True,
                "schema": _proposal_schema(field_contract_v2, field_contract_v3),
            }
        },
    }

def _content_fragments(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fragment in fragments:
        object_type, _proposed = extract_object_type(fragment)
        if object_type != "heading":
            out.append(fragment)
    return out


def _materialised_content(**kwargs: Any) -> list[dict[str, Any]]:
    """Selection decides. The materialiser creates the only knowledge candidates."""

    from src.knowledge_materialisation_v1 import (
        materialise_knowledge_candidates,
        ordered_source_projection,
    )
    from src.semantic_passage_v1 import _project_semantic_selection

    decisions, coverage = _project_semantic_selection(**kwargs)
    candidates = materialise_knowledge_candidates(
        decisions,
        document_id=str(kwargs["document_id"]),
        fragments=kwargs["fragments"],
    )
    return ordered_source_projection(candidates, decisions, coverage, kwargs["fragments"])


def _candidate_fragments(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return source fragments the provider may select as KnowledgeCandidates.

    Strength labels stay in source coverage/evidence but are not themselves
    candidate passages.
    """

    out: list[dict[str, Any]] = []
    for fragment in _content_fragments(fragments):
        text = str(fragment.get("clean_text") or fragment.get("raw_text") or "").strip()
        if (
            is_strength_stamp(text)
            or is_source_strength_label(text)
            or is_kennisplatform_chrome_text(text)
        ):
            continue
        out.append(fragment)
    return out


def _evidence_fragments(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return source material eligible to support semantics evidence."""

    return [
        fragment
        for fragment in fragments
        if not is_kennisplatform_chrome_text(
            str(fragment.get("clean_text") or fragment.get("raw_text") or "").strip()
        )
    ]


def _heading_units(
    fragments: list[dict[str, Any]],
    *,
    document_id: str,
) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for fragment in fragments:
        object_type, _proposed = extract_object_type(fragment)
        if object_type == "heading":
            headings.append(fragment)
    return split_context_aware_units(headings, document_id=document_id) if headings else []


def _source_ordered_units(
    fragments: list[dict[str, Any]],
    *,
    headings: list[dict[str, Any]],
    content: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reinsert deterministic headings without moving them ahead of content."""

    source_position: dict[str, int] = {}
    for index, fragment in enumerate(fragments):
        ids = list(fragment.get("source_fragment_ids") or [])
        fragment_id = str(fragment.get("fragment_id") or "").strip()
        if fragment_id and fragment_id not in ids:
            ids.append(fragment_id)
        for source_id in ids:
            if source_id:
                source_position.setdefault(str(source_id), index)

    combined = headings + content

    def position(unit: dict[str, Any]) -> int:
        candidates = [
            source_position[str(source_id)]
            for source_id in unit.get("source_fragment_ids") or []
            if str(source_id) in source_position
        ]
        return min(candidates) if candidates else len(fragments)

    return [
        unit
        for _index, unit in sorted(
            enumerate(combined),
            key=lambda item: (position(item[1]), item[0]),
        )
    ]


def _extractor_contract(fragments: list[dict[str, Any]]) -> str:
    versions = sorted(
        {
            str(fragment.get("parser_version") or "").strip()
            for fragment in fragments
            if str(fragment.get("parser_version") or "").strip()
        }
    )
    return "|".join(versions) if versions else "parser-version-unspecified"


def _replay_identity(
    *,
    document_id: str,
    model: str,
    blocks: list[dict[str, Any]],
    evidence_blocks: list[dict[str, Any]],
    source_fragments: list[dict[str, Any]],
    formation_context: Mapping[str, Any] | None,
    field_contract_v2: bool = False,
    field_contract_v3: bool = False,
) -> dict[str, Any] | None:
    if not formation_context:
        return None
    snapshot_id = str(formation_context.get("snapshot_id") or "").strip()
    source_sha256 = str(formation_context.get("source_sha256") or "").strip()
    if not snapshot_id or not source_sha256:
        return None
    semantic_input = {
        "source_blocks": blocks,
        "evidence_blocks": evidence_blocks,
    }
    return build_replay_identity(
        snapshot_id=snapshot_id,
        source_sha256=source_sha256,
        document_id=document_id,
        source_blocks_hash=_stable_json_hash(semantic_input),
        extractor_version=_extractor_contract(source_fragments),
        reconstruction_version=RECONSTRUCTION_VERSION,
        formation_policy_version=PASSAGE_FORMATION_POLICY_VERSION,
        semantic_contract_version=("source-accountability-v2/bounded-formation-v1/" if field_contract_v3 else "source-accountability-v1/") + (f"recoverable-formation-v1/{FIELDS_V3_VERSION}/{CONTEXT_VERSION}/condition-context-and-timing-list-v2/recommendation-core-admission-v3/recommendation-coverage-v1/{SEMANTIC_PASSAGE_VERSION}/{V3_EVIDENCE_RESOLUTION_VERSION}" if field_contract_v3 else f"source-bound-fields-v2/{CONTEXT_VERSION}/{SEMANTIC_PASSAGE_VERSION}/{EVIDENCE_RESOLUTION_VERSION}" if field_contract_v2 else f"{SEMANTIC_PASSAGE_VERSION}/{EVIDENCE_RESOLUTION_VERSION}"),
        prompt_hash=_stable_json_hash(SEMANTIC_DEVELOPER_PROMPT + _semantic_instruction(field_contract_v2, field_contract_v3)),
        schema_hash=_stable_json_hash(_proposal_schema(field_contract_v2, field_contract_v3)),
        provider_id=SEMANTIC_PROVIDER_ID,
        model_id=model,
        model_config_hash=_stable_json_hash(SEMANTIC_MODEL_CONFIG),
    )

def validate_provider_proposal(proposal, *, field_contract_v2=False, field_contract_v3=False):
    """Pure proposal gates shared with read-only diagnostic reproduction."""
    if not isinstance(proposal, dict):
        raise ConsoleError("pre_review_llm_response_invalid")
    if str(proposal.get("abstain_reason") or "").strip():
        raise ConsoleError("pre_review_llm_abstained")
    if (field_contract_v2 or field_contract_v3) and isinstance(proposal.get("objects"), list):
        for index, row in enumerate(proposal["objects"]):
            if not isinstance(row, dict) or "context_evidence" not in row:
                error = ConsoleError("pre_review_llm_proposal_rejected", "source_bound_context_required")
                error.validation_finding = {"candidate_index": index, "field": "context_evidence",
                    "proposed_object": row, "reason_code": "source_bound_context_required"}
                raise error


def _provider_proposal(
    *,
    api_key: str,
    model: str,
    blocks: list[dict[str, Any]],
    evidence_blocks: list[dict[str, Any]],
    post_json: PostJson | None,
    field_contract_v2: bool = False,
    field_contract_v3: bool = False,
    selection_targets=None,
    task=None,
    model_limits: ModelCallLimits | None = None,
    evidence: dict[str, Any] | None = None,
    checkpoint=None,
    validator_input=None,
) -> dict[str, Any]:
    safe_key = str(api_key or "").strip()
    if not safe_key:
        raise ConsoleError("pre_review_llm_api_key_required")
    payload = _request_payload(model=model, blocks=blocks,
                               evidence_blocks=evidence_blocks,
                               field_contract_v2=field_contract_v2, field_contract_v3=field_contract_v3, selection_targets=selection_targets, task=task)
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > MAX_INPUT_BYTES:
        raise ConsoleError("pre_review_llm_input_limit_exceeded")
    request_evidence = deepcopy(payload)
    requested_at = datetime.now(timezone.utc).isoformat()
    limits = model_limits or ModelCallLimits(total=DEFAULT_TIMEOUT_SECONDS)
    started = time.monotonic()
    transport = {}
    if evidence is not None:
        evidence.update(version="semantic-provider-evidence-v1", requested_at=requested_at, request=request_evidence)
    try:
        commit = (Path(__file__).resolve().parents[1] / "config/deployed_commit.txt").read_text().strip()
    except OSError:
        commit = ""
    if evidence is not None:
        evidence["deployed_commit"] = commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None
    if checkpoint:
        checkpoint("model_request", {"provider_evidence": evidence})
    headers = {"Authorization": f"Bearer {safe_key}", "Content-Type": "application/json"}
    if post_json is None:
        response = _bounded_provider_json(OPENAI_RESPONSES_URL, headers, payload, limits, transport)
    else:
        # Injection for deterministic proposal tests / existing instrumentation.
        # Production uses the supervised native transport; custom transports must
        # honor this contract themselves. This guard still forbids late activation.
        response = post_json(OPENAI_RESPONSES_URL, headers, payload, limits.total)
    if time.monotonic() - started >= limits.total:
        raise ConsoleError("pre_review_llm_processing_timeout")
    if not isinstance(response, dict):
        raise ConsoleError("pre_review_llm_response_invalid")
    if evidence is not None:
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        evidence.update(transport=transport, response={"id": response.get("id"), "status": response.get("status"),
                        "output_text": None, "input_tokens": usage.get("input_tokens"),
                        "output_tokens": usage.get("output_tokens")})
    if checkpoint:
        checkpoint("response_received", {"provider_evidence": evidence})
    if len(json.dumps(response, ensure_ascii=False).encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ConsoleError("pre_review_llm_output_limit_exceeded")
    output_text = _extract_output_text(response)
    if evidence is not None:
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        evidence.update(transport=transport, response={"id": response.get("id"), "status": response.get("status"),
                        "output_text": output_text, "input_tokens": usage.get("input_tokens"),
                        "output_tokens": usage.get("output_tokens")})
    if checkpoint:
        checkpoint("model_response", {"provider_evidence": evidence})
    try:
        proposal = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise ConsoleError("pre_review_llm_response_invalid") from exc
    if checkpoint:
        checkpoint("proposal_parsed", {"proposal": proposal, "proposal_hash": _stable_json_hash(proposal)})
    try:
        if not field_contract_v3:
            validate_provider_proposal(proposal, field_contract_v2=field_contract_v2)
    except ConsoleError as error:
        if checkpoint:
            checkpoint("proposal_gate_rejected", {"finding": getattr(error, "validation_finding", {"reason_code": error.code})})
        raise
    if evidence is not None:
        # Never persist HTTP headers, credentials, arbitrary provider metadata or
        # reasoning. This observation travels through the existing run commit.
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        try:
            commit = (Path(__file__).resolve().parents[1] / "config/deployed_commit.txt").read_text().strip()
        except OSError:
            commit = ""
        if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
            commit = None
        evidence.update(version="semantic-provider-evidence-v1", transport=transport, requested_at=requested_at,
                        deployed_commit=commit, request=request_evidence,
                        response={"id": response.get("id"), "status": response.get("status"),
                                  "output_text": output_text,
                                  "input_tokens": usage.get("input_tokens"),
                                  "output_tokens": usage.get("output_tokens")})
    try:
        if field_contract_v3:
            from src.recoverable_formation_v1 import prepare
            resolved, formation = prepare(proposal, blocks=blocks, evidence_blocks=evidence_blocks,
                                          validator_input=validator_input)
            if evidence is not None:
                evidence["formation"] = formation
        else:
            resolved = resolve_proposal_evidence(proposal, blocks=blocks, evidence_blocks=evidence_blocks,
                                                field_contract_v3=False)
    except SemanticPassageError as exc:
        if checkpoint:
            checkpoint("validation_rejected", {"finding": exc.finding})
        raise ConsoleError("pre_review_llm_proposal_rejected", exc.code) from exc
    if checkpoint:
        checkpoint("evidence_resolved", {"resolved_proposal": resolved,
                   "resolved_proposal_hash": _stable_json_hash(resolved)})
    return resolved

def _semantic_execution_before_review(
    fragments: list[dict[str, Any]],
    *,
    document_id: str,
    api_key: str,
    model: str,
    formation_context: Mapping[str, Any] | None = None,
    post_json: PostJson | None = None,
    field_contract_v2: bool = False,
    field_contract_v3: bool = False,
    model_limits: ModelCallLimits | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    safe_key = str(api_key or "").strip()
    safe_model = str(model or "").strip()
    if not safe_model:
        if not safe_key:
            raise ConsoleError("pre_review_llm_api_key_required")
        raise ConsoleError("pre_review_llm_model_required")

    content_fragments = _content_fragments(fragments)
    candidate_fragments = _candidate_fragments(fragments)
    evidence_fragments = _evidence_fragments(fragments)
    blocks = semantic_source_blocks(candidate_fragments)
    evidence_blocks = semantic_source_blocks(evidence_fragments)
    allowed_candidate_block_ids = {
        str(block.get("block_id") or "")
        for block in blocks
        if str(block.get("block_id") or "")
    }
    semantic_input = {
        "source_blocks": blocks,
        "evidence_blocks": evidence_blocks,
    }
    content_units: list[dict[str, Any]] = []
    replay_record: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    execution = EXECUTION_INFERENCE
    replay_rejection_reason: str | None = None

    identity = _replay_identity(
        document_id=document_id,
        model=safe_model,
        blocks=blocks,
        evidence_blocks=evidence_blocks,
        source_fragments=fragments,
        field_contract_v2=field_contract_v2, field_contract_v3=field_contract_v3,
        formation_context=formation_context,
    )
    existing_replay = (
        formation_context.get("semantic_replay")
        if formation_context
        else None
    )

    if blocks and identity is not None:
        lookup = exact_replay_lookup(
            existing_replay,
            expected_identity=identity,
        )
        if lookup.status == LOOKUP_HIT and lookup.proposal is not None:
            try:
                replay_units = _materialised_content(
                    fragments=content_fragments,
                    document_id=document_id,
                    proposal=lookup.proposal,
                    evidence_fragments=evidence_fragments,
                    allowed_candidate_block_ids=allowed_candidate_block_ids,
                    field_contract_v2=field_contract_v2,
                    field_contract_v3=field_contract_v3,
                )
            except SemanticPassageError as exc:
                replay_rejection_reason = exc.code
            else:
                if replay_units:
                    proposal = lookup.proposal
                    content_units = replay_units
                    execution = EXECUTION_REPLAY
                    replay_record = replayed_record(existing_replay)
                else:
                    replay_rejection_reason = "semantic_replay_abstention_not_reusable"
        elif lookup.status == LOOKUP_REJECTED:
            replay_rejection_reason = lookup.reason or "semantic_replay_record_rejected"

    checkpoint = (formation_context or {}).get("diagnostic_checkpoint")
    validator_input = {"fragments": content_fragments, "document_id": document_id,
                       "evidence_fragments": evidence_fragments,
                       "allowed_candidate_block_ids": sorted(allowed_candidate_block_ids),
                       "field_contract_v2": field_contract_v2, "field_contract_v3": field_contract_v3}
    if checkpoint:
        from src.attempt_diagnostics_v1 import validator_identity
        checkpoint("source_reconstructed", {"validator_input": validator_input,
            "validator_input_hash": _stable_json_hash(validator_input),
            "validator_identity": validator_identity(), "semantic_identity": identity})
    if field_contract_v3 and blocks and (proposal is None or (formation_context or {}).get("resume_formation")):
        if (formation_context or {}).get("resume_formation") and proposal is None:
            raise ConsoleError("semantic_replay_policy_mismatch")
        from src.bounded_formation_v1 import execute
        limits = model_limits or ModelCallLimits(total=DEFAULT_TIMEOUT_SECONDS)
        def provider(**kwargs):
            return _provider_proposal(api_key=api_key, model=safe_model, post_json=post_json,
                field_contract_v3=True, checkpoint=None, **kwargs)
        proposal, provider_evidence = execute(blocks=blocks, evidence_blocks=evidence_blocks,
            validator_input=validator_input, provider=provider, limits=limits,
            proposal=proposal, evidence=(replay_record or {}).get("provider_evidence"), checkpoint=checkpoint)
        errors = [call["error_code"] for call in [provider_evidence, *provider_evidence.get("supplementary_calls", [])]
                  if call.get("error_code")]
        if not proposal["objects"] and errors:
            # A wholly failed new run must not replace existing valid work
            # with source remainders. Partial success is retained separately.
            raise ConsoleError(errors[0])
        content_units = _materialised_content(**validator_input, proposal=proposal)
    if blocks and proposal is None:
        provider_evidence: dict[str, Any] = {}
        proposal = _provider_proposal(
            api_key=api_key,
            model=safe_model,
            blocks=blocks,
            evidence_blocks=evidence_blocks,
            post_json=post_json,
            field_contract_v2=field_contract_v2, field_contract_v3=field_contract_v3,
            model_limits=model_limits,
            evidence=provider_evidence,
            checkpoint=checkpoint, validator_input=validator_input,
        )
        if checkpoint:
            checkpoint("proposal_received", {"provider_evidence": provider_evidence})
        try:
            content_units = _materialised_content(
                fragments=content_fragments,
                document_id=document_id,
                proposal=proposal,
                evidence_fragments=evidence_fragments,
                allowed_candidate_block_ids=allowed_candidate_block_ids,
                field_contract_v2=field_contract_v2,
                field_contract_v3=field_contract_v3,
            )
        except SemanticPassageError as exc:
            if checkpoint:
                checkpoint("validation_rejected", {"finding": exc.finding})
            LOGGER.error("METIS_VALIDATION rejected code=%s reference=%s", exc.code, _PROCESSING_REFERENCE.get())
            raise ConsoleError("pre_review_llm_proposal_rejected", exc.code) from exc
    if proposal is not None and blocks:
        provider_evidence = locals().get("provider_evidence") or deepcopy((replay_record or {}).get("provider_evidence") or {})
        if field_contract_v3:
            from src.recoverable_formation_v1 import pending_rejections
            provider_evidence["pending_rejections"] = pending_rejections(provider_evidence, proposal)
            provider_evidence["formation_incomplete"] = bool(provider_evidence["pending_rejections"])
            if checkpoint:
                checkpoint("formation_accounted", {"provider_evidence": provider_evidence})
        if execution != EXECUTION_REPLAY or (formation_context or {}).get("resume_formation"):
            execution = EXECUTION_INFERENCE
        if identity is not None and execution != EXECUTION_REPLAY:
            replay_record = validated_inference_record(
                identity=identity,
                proposal=proposal,
                replay_rejection_reason=replay_rejection_reason,
            )
            replay_record["provider_evidence"] = provider_evidence
    elif not blocks and not safe_key:
        raise ConsoleError("pre_review_llm_api_key_required")

    if not blocks and content_fragments:
        content_units = semantic_coverage_units(
            content_fragments,
            document_id=document_id,
            source_version="source-accountability-v2" if field_contract_v3 else "source-accountability-v1",
        )

    if proposal is not None:
        if field_contract_v3:
            from src.recommendation_coverage_v1 import assess, attach
            attach(content_units, assess(blocks, proposal))
        source_blocks_hash = _stable_json_hash(semantic_input)
        proposal_hash = _stable_json_hash(proposal)
        for unit in content_units:
            semantic_passage = unit.get("semantic_passage")
            if (
                isinstance(semantic_passage, dict)
                and semantic_passage.get("selection_origin") == SELECTION_ORIGIN_PROPOSAL
            ):
                semantic_passage.update(
                    {
                        "formation_mode": SEMANTIC_V3_MODE if field_contract_v3 else SEMANTIC_V2_MODE if field_contract_v2 else SEMANTIC_MODE,
                        "model": safe_model,
                        "source_blocks_hash": source_blocks_hash,
                        "proposal_hash": proposal_hash,
                    }
                )

    units = prefer_authoritative_exact_occurrences(
        _source_ordered_units(
            fragments,
            headings=_heading_units(fragments, document_id=document_id),
            content=content_units,
        )
    )
    if proposal is not None:
        attach_relation_proposals(
            units,
            raw_relations=proposal.get("relations", []),
            evidence_fragments=evidence_fragments,
            object_version="1.0",
        )
    return units, replay_record


def semantic_units_before_review(
    fragments: list[dict[str, Any]],
    *,
    document_id: str,
    api_key: str,
    model: str,
    formation_context: Mapping[str, Any] | None = None,
    post_json: PostJson | None = None,
    field_contract_v2: bool = False,
    field_contract_v3: bool = False,
    model_limits: ModelCallLimits | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic headings plus source-reconstructed semantic candidates."""

    units, _replay_record = _semantic_execution_before_review(
        fragments,
        document_id=document_id,
        api_key=api_key,
        model=model,
        formation_context=formation_context,
        post_json=post_json,
        field_contract_v2=field_contract_v2, field_contract_v3=field_contract_v3,
        model_limits=model_limits,
    )
    return units


def semantic_spec_from_fragments(
    *,
    document_id: str,
    title: str,
    family: str,
    class_: str,
    fragments: list[dict[str, Any]],
    content_kind: str,
    api_key: str,
    model: str,
    formation_context: Mapping[str, Any] | None = None,
    post_json: PostJson | None = None,
    field_contract_v2: bool = False,
    field_contract_v3: bool = False,
    model_limits: ModelCallLimits | None = None,
) -> dict[str, Any]:
    reference = str((formation_context or {}).get("processing_reference") or uuid.uuid4().hex)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", reference):
        reference = uuid.uuid4().hex
    snapshot_id = str((formation_context or {}).get("snapshot_id") or "")
    # Do not log document titles, source prose, credentials or provider messages.
    snapshot_id = snapshot_id if re.fullmatch(r"snap-[A-Za-z0-9_-]{1,100}", snapshot_id) else "-"
    checkpoint = (formation_context or {}).get("diagnostic_checkpoint")
    if checkpoint:
        checkpoint("validation_started", {"processing_reference": reference, "model": model,
                    "field_contract": "v3" if field_contract_v3 else "v2" if field_contract_v2 else "v1"})
    token = _PROCESSING_REFERENCE.set(reference)
    started = time.monotonic()
    LOGGER.info("METIS_PRE_REVIEW start reference=%s snapshot_id=%s", reference, snapshot_id)
    try:
        units, replay_record = _semantic_execution_before_review(
            fragments,
            document_id=document_id,
            api_key=api_key,
            model=model,
            formation_context=formation_context,
            post_json=post_json,
            field_contract_v2=field_contract_v2, field_contract_v3=field_contract_v3,
            model_limits=model_limits,
        )
    except ConsoleError as exc:
        reason = str(exc) if exc.code == "pre_review_llm_proposal_rejected" else ""
        reason = reason if re.fullmatch(r"(?:semantic|recommendation|source_bound)_[a-z_]{1,100}", reason) else ""
        code = exc.code if re.fullmatch(r"[a-z_]{1,120}", exc.code) else "processing_failed"
        # Transient error metadata only: failed retries leave persisted state intact.
        exc.pre_review_diagnostics = {"reference": reference, "reason_code": reason}
        LOGGER.error(
            "METIS_PRE_REVIEW blocked reference=%s snapshot_id=%s code=%s reason=%s elapsed=%.2f",
            reference, snapshot_id, code, reason or "-", time.monotonic() - started,
        )
        raise
    else:
        LOGGER.info("METIS_PRE_REVIEW prepared reference=%s snapshot_id=%s elapsed=%.2f",
                    reference, snapshot_id, time.monotonic() - started)
    finally:
        _PROCESSING_REFERENCE.reset(token)
    objects: list[dict[str, Any]] = [
        {
            "object_id": f"{document_id}-document",
            "object_type": "document",
            "text": title,
            "review_track": "technical",
        }
    ]
    objects.extend(units)
    spec = {
        "spec_version": "console-ingest-1.0",
        "document_id": document_id,
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": [family, f"class:{class_}", f"source-kind:{content_kind}"],
        "objects": objects,
    }
    if replay_record is not None:
        spec[SEMANTIC_REPLAY_SPEC_KEY] = replay_record
    return spec


def bind_pre_review_semantic_processing(
    console: Any,
    *,
    environ: Mapping[str, str] | None = None,
    post_json: PostJson | None = None,
) -> None:
    """Bind passage formation to one console instance, never process-global state.

    Normal HTML/PDF processing uses the configured semantic route. Decision-tree
    processing remains on its dedicated deterministic path. Read-only source
    re-extraction used by deterministic Review repair is explicitly suppressed,
    so opening a repair catalog cannot trigger or depend on an LLM call.
    """

    if getattr(console, "_pre_review_semantic_bound", False):
        return

    env = environ if environ is not None else os.environ
    console._model_call_limits_reader = lambda: load_limits(env)

    def active_passage_formation_mode() -> str:
        return _configured_passage_formation_mode(env)

    # Runtime-only projection for UI/status surfaces. This is not document state
    # and is deliberately the same reader used by the processing router below.
    console._passage_formation_mode_reader = active_passage_formation_mode
    original_fragments_and_spec = console._fragments_and_spec
    semantic_suppressed: ContextVar[bool] = ContextVar(
        f"metis_pre_review_semantic_suppressed_{id(console)}",
        default=False,
    )

    def configured_fragments_and_spec(
        kind: str,
        path: Any,
        *,
        data: bytes,
        document_id: str,
        source_id: str,
        title: str,
        family: str,
        class_: str,
        formation_context: Mapping[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if semantic_suppressed.get() or (kind == "pdf" and class_ == "beslisboom"):
            return original_fragments_and_spec(
                kind,
                path,
                data=data,
                document_id=document_id,
                source_id=source_id,
                title=title,
                family=family,
                class_=class_,
                formation_context=formation_context,
            )

        mode = active_passage_formation_mode()
        try:
            decision = resolve_passage_formation_strategy(
                content_kind=kind,
                deployment_mode=mode,
            )
        except PassageFormationPolicyError as exc:
            raise ConsoleError(exc.code) from exc

        if decision.strategy == STRATEGY_DETERMINISTIC:
            fragments, spec = original_fragments_and_spec(
                kind,
                path,
                data=data,
                document_id=document_id,
                source_id=source_id,
                title=title,
                family=family,
                class_=class_,
                formation_context=formation_context,
            )
            return fragments, _stamp_passage_formation(spec, decision)

        checkpoint = (formation_context or {}).get("diagnostic_checkpoint")
        if checkpoint:
            checkpoint("extraction_started", {})
        from src.docling_pdf_v1 import enabled as docling_enabled
        extraction_kwargs = ({"deadline": (formation_context or {}).get("attempt_deadline")}
                             if kind == "pdf" and docling_enabled() else {})
        retained_fragments = (formation_context or {}).get("retained_fragments")
        fragments = retained_fragments if retained_fragments is not None else console._extract(
            kind,
            path,
            document_id=document_id,
            source_id=source_id,
            **extraction_kwargs,
        )
        if checkpoint:
            checkpoint("extraction_finished", {"fragment_count": len(fragments), "extractor_versions": sorted({str(f.get("parser_version") or "not_recorded") for f in fragments})})
        provider = load_llm_provider_config(env)
        limits = (ModelCallLimits(**(formation_context or {}).get("model_call_limits"))
                  if (formation_context or {}).get("model_call_limits") else load_limits(env))
        deadline = (formation_context or {}).get("attempt_deadline")
        if deadline is not None:
            from dataclasses import replace
            from src.bounded_model_call_v1 import CLEANUP_SECONDS
            remaining = deadline - time.monotonic() - CLEANUP_SECONDS
            if remaining <= 0:
                raise ConsoleError("processing_attempt_expired")
            limits = replace(limits, total=min(limits.total, remaining),
                             connect=min(limits.connect, remaining), idle=min(limits.idle, remaining))
        spec = semantic_spec_from_fragments(
            document_id=document_id,
            title=title,
            family=family,
            class_=class_,
            fragments=fragments,
            content_kind=kind,
            api_key=provider.api_key,
            model=provider.model,
            formation_context=formation_context,
            post_json=post_json,
            field_contract_v2=(mode == SEMANTIC_V2_MODE),
            field_contract_v3=(mode == SEMANTIC_V3_MODE),
            model_limits=limits,
        )
        return fragments, _stamp_passage_formation(spec, decision)

    console._fragments_and_spec = configured_fragments_and_spec

    original_source_fragment_catalog = getattr(console, "source_fragment_catalog", None)
    if callable(original_source_fragment_catalog):
        def deterministic_source_fragment_catalog(*args: Any, **kwargs: Any) -> Any:
            token = semantic_suppressed.set(True)
            try:
                return original_source_fragment_catalog(*args, **kwargs)
            finally:
                semantic_suppressed.reset(token)

        console.source_fragment_catalog = deterministic_source_fragment_catalog

    console._pre_review_semantic_bound = True
