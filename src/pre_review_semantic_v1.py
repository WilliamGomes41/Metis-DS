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
import os
from contextvars import ContextVar
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.atomic_split_v1 import proposed_relations_for_units
from src.context_aware_split_v1 import split_context_aware_units
from src.llm_provider_v1 import OPENAI_RESPONSES_URL, load_llm_provider_config
from src.object_taxonomy_v1 import extract_object_type
from src.operations_console_v1 import ConsoleError
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


PASSAGE_FORMATION_MODE_ENV = "METIS_PASSAGE_FORMATION_MODE"
DEFAULT_TIMEOUT_SECONDS = 60
SEMANTIC_PROVIDER_ID = "openai-responses-v1"
SEMANTIC_DEVELOPER_PROMPT = (
    "Form meaning units for human review by selecting only exact source spans. "
    "Do not write, rewrite or paraphrase candidate knowledge text. "
    "Group spans only when they form one independently understandable unit. "
    "Keep target group, conditions, exceptions and modality with the statement "
    "they qualify. Preserve source order. If no safe source-bound proposal is "
    "possible, return zero objects and a short abstain_reason."
)
SEMANTIC_MODEL_CONFIG = {
    "api": "responses",
    "structured_output": "json_schema",
    "strict": True,
}

PostJson = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]


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
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ConsoleError("pre_review_llm_provider_unavailable") from exc
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConsoleError("pre_review_llm_response_invalid") from exc
    if not isinstance(decoded, dict):
        raise ConsoleError("pre_review_llm_response_invalid")
    return decoded


def _proposal_schema() -> dict[str, Any]:
    span = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "block_id": {"type": "string"},
            "start": {"type": "integer", "minimum": 0},
            "end": {"type": "integer", "minimum": 1},
        },
        "required": ["block_id", "start", "end"],
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
        },
        "required": ["spans", "proposed_object_type"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "objects": {"type": "array", "items": obj},
            "abstain_reason": {"type": ["string", "null"]},
        },
        "required": ["objects", "abstain_reason"],
    }


def _extract_output_text(response: dict[str, Any]) -> str:
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
    text = "".join(texts).strip()
    if not text:
        raise ConsoleError("pre_review_llm_response_empty")
    return text


def _request_payload(*, model: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "developer",
                "content": SEMANTIC_DEVELOPER_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps({"source_blocks": blocks}, ensure_ascii=False),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "pre_review_semantic_passage_proposal",
                "strict": True,
                "schema": _proposal_schema(),
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
    content_fragments: list[dict[str, Any]],
    formation_context: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not formation_context:
        return None
    snapshot_id = str(formation_context.get("snapshot_id") or "").strip()
    source_sha256 = str(formation_context.get("source_sha256") or "").strip()
    if not snapshot_id or not source_sha256:
        return None
    return build_replay_identity(
        snapshot_id=snapshot_id,
        source_sha256=source_sha256,
        document_id=document_id,
        source_blocks_hash=_stable_json_hash(blocks),
        extractor_version=_extractor_contract(content_fragments),
        reconstruction_version=RECONSTRUCTION_VERSION,
        formation_policy_version=PASSAGE_FORMATION_POLICY_VERSION,
        semantic_contract_version=SEMANTIC_PASSAGE_VERSION,
        prompt_hash=_stable_json_hash(SEMANTIC_DEVELOPER_PROMPT),
        schema_hash=_stable_json_hash(_proposal_schema()),
        provider_id=SEMANTIC_PROVIDER_ID,
        model_id=model,
        model_config_hash=_stable_json_hash(SEMANTIC_MODEL_CONFIG),
    )


def _provider_proposal(
    *,
    api_key: str,
    model: str,
    blocks: list[dict[str, Any]],
    post_json: PostJson | None,
) -> dict[str, Any]:
    safe_key = str(api_key or "").strip()
    if not safe_key:
        raise ConsoleError("pre_review_llm_api_key_required")
    response = (post_json or _post_json)(
        OPENAI_RESPONSES_URL,
        {
            "Authorization": f"Bearer {safe_key}",
            "Content-Type": "application/json",
        },
        _request_payload(model=model, blocks=blocks),
        DEFAULT_TIMEOUT_SECONDS,
    )
    if not isinstance(response, dict):
        raise ConsoleError("pre_review_llm_response_invalid")
    try:
        proposal = json.loads(_extract_output_text(response))
    except json.JSONDecodeError as exc:
        raise ConsoleError("pre_review_llm_response_invalid") from exc
    if not isinstance(proposal, dict):
        raise ConsoleError("pre_review_llm_response_invalid")
    if str(proposal.get("abstain_reason") or "").strip():
        raise ConsoleError("pre_review_llm_abstained")
    return proposal


def _semantic_execution_before_review(
    fragments: list[dict[str, Any]],
    *,
    document_id: str,
    api_key: str,
    model: str,
    formation_context: Mapping[str, Any] | None = None,
    post_json: PostJson | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    safe_model = str(model or "").strip()
    if not safe_model:
        raise ConsoleError("pre_review_llm_model_required")

    content_fragments = _content_fragments(fragments)
    blocks = semantic_source_blocks(content_fragments)
    content_units: list[dict[str, Any]] = []
    replay_record: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    execution = EXECUTION_INFERENCE
    replay_rejection_reason: str | None = None

    identity = _replay_identity(
        document_id=document_id,
        model=safe_model,
        blocks=blocks,
        content_fragments=content_fragments,
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
                replay_units = semantic_units_from_proposal(
                    content_fragments,
                    document_id=document_id,
                    proposal=lookup.proposal,
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

    if blocks and proposal is None:
        proposal = _provider_proposal(
            api_key=api_key,
            model=safe_model,
            blocks=blocks,
            post_json=post_json,
        )
        try:
            content_units = semantic_units_from_proposal(
                content_fragments,
                document_id=document_id,
                proposal=proposal,
            )
        except SemanticPassageError as exc:
            raise ConsoleError("pre_review_llm_proposal_rejected", exc.code) from exc
        execution = EXECUTION_INFERENCE
        if identity is not None:
            replay_record = validated_inference_record(
                identity=identity,
                proposal=proposal,
                replay_rejection_reason=replay_rejection_reason,
            )
    elif not blocks and not str(api_key or "").strip():
        # Preserve the pre-F2 configuration contract for semantic mode even
        # when a document contains only deterministic headings.
        raise ConsoleError("pre_review_llm_api_key_required")

    if proposal is not None:
        source_blocks_hash = _stable_json_hash(blocks)
        proposal_hash = _stable_json_hash(proposal)
        for unit in content_units:
            semantic_passage = unit.get("semantic_passage")
            if (
                isinstance(semantic_passage, dict)
                and semantic_passage.get("selection_origin") == SELECTION_ORIGIN_PROPOSAL
            ):
                semantic_passage.update(
                    {
                        "formation_mode": SEMANTIC_MODE,
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
    proposed_relations_for_units(units)
    return units, replay_record


def semantic_units_before_review(
    fragments: list[dict[str, Any]],
    *,
    document_id: str,
    api_key: str,
    model: str,
    formation_context: Mapping[str, Any] | None = None,
    post_json: PostJson | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic headings plus source-reconstructed semantic candidates."""

    units, _replay_record = _semantic_execution_before_review(
        fragments,
        document_id=document_id,
        api_key=api_key,
        model=model,
        formation_context=formation_context,
        post_json=post_json,
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
) -> dict[str, Any]:
    units, replay_record = _semantic_execution_before_review(
        fragments,
        document_id=document_id,
        api_key=api_key,
        model=model,
        formation_context=formation_context,
        post_json=post_json,
    )
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
        if semantic_suppressed.get():
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

        mode = str(env.get(PASSAGE_FORMATION_MODE_ENV, "") or "").strip() or DETERMINISTIC_MODE
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

        fragments = console._extract(
            kind,
            path,
            document_id=document_id,
            source_id=source_id,
        )
        provider = load_llm_provider_config(env)
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
