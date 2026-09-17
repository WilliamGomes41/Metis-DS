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

import json
import os
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.atomic_split_v1 import proposed_relations_for_units
from src.context_aware_split_v1 import split_context_aware_units
from src.object_taxonomy_v1 import extract_object_type
from src.operations_console_v1 import ConsoleError
from src.semantic_passage_v1 import (
    ALLOWED_PROPOSED_TYPES,
    SemanticPassageError,
    semantic_source_blocks,
    semantic_units_from_proposal,
)


PASSAGE_FORMATION_MODE_ENV = "METIS_PASSAGE_FORMATION_MODE"
PRE_REVIEW_LLM_API_KEY_ENV = "METIS_PRE_REVIEW_LLM_API_KEY"
PRE_REVIEW_LLM_MODEL_ENV = "METIS_PRE_REVIEW_LLM_MODEL"
DETERMINISTIC_MODE = "deterministic-v1"
SEMANTIC_MODE = "semantic-source-bound-v1"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_TIMEOUT_SECONDS = 60

PostJson = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]
SpecBuilder = Callable[..., dict[str, Any]]

_INSTALLED = False
_ORIGINAL_SPEC_BUILDER: SpecBuilder | None = None


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
                "content": (
                    "Form meaning units for human review by selecting only exact source spans. "
                    "Do not write, rewrite or paraphrase candidate knowledge text. "
                    "Group spans only when they form one independently understandable unit. "
                    "Keep target group, conditions, exceptions and modality with the statement "
                    "they qualify. If no safe source-bound proposal is possible, return zero "
                    "objects and a short abstain_reason."
                ),
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


def semantic_units_before_review(
    fragments: list[dict[str, Any]],
    *,
    document_id: str,
    api_key: str,
    model: str,
    post_json: PostJson | None = None,
) -> list[dict[str, Any]]:
    """Return headings plus source-reconstructed LLM content candidates."""

    safe_key = str(api_key or "").strip()
    safe_model = str(model or "").strip()
    if not safe_key:
        raise ConsoleError("pre_review_llm_api_key_required")
    if not safe_model:
        raise ConsoleError("pre_review_llm_model_required")

    content_fragments = _content_fragments(fragments)
    blocks = semantic_source_blocks(content_fragments)
    content_units: list[dict[str, Any]] = []
    if blocks:
        response = (post_json or _post_json)(
            OPENAI_RESPONSES_URL,
            {
                "Authorization": f"Bearer {safe_key}",
                "Content-Type": "application/json",
            },
            _request_payload(model=safe_model, blocks=blocks),
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
        try:
            content_units = semantic_units_from_proposal(
                content_fragments,
                document_id=document_id,
                proposal=proposal,
            )
        except SemanticPassageError as exc:
            raise ConsoleError("pre_review_llm_proposal_rejected", exc.code) from exc

    units = _heading_units(fragments, document_id=document_id) + content_units
    proposed_relations_for_units(units)
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
    post_json: PostJson | None = None,
) -> dict[str, Any]:
    objects: list[dict[str, Any]] = [
        {
            "object_id": f"{document_id}-document",
            "object_type": "document",
            "text": title,
            "review_track": "technical",
        }
    ]
    objects.extend(
        semantic_units_before_review(
            fragments,
            document_id=document_id,
            api_key=api_key,
            model=model,
            post_json=post_json,
        )
    )
    return {
        "spec_version": "console-ingest-1.0",
        "document_id": document_id,
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": [family, f"class:{class_}", f"source-kind:{content_kind}"],
        "objects": objects,
    }


def install_pre_review_semantic_processing(
    *,
    environ: Mapping[str, str] | None = None,
    post_json: PostJson | None = None,
) -> None:
    """Bind one explicit passage-formation policy to normal console ingest.

    Missing mode keeps the existing deterministic path for backwards-compatible
    rollout. Once semantic mode is selected, every error is fail-closed and the
    deterministic path is never invoked as an implicit fallback.
    """

    global _INSTALLED, _ORIGINAL_SPEC_BUILDER
    if _INSTALLED:
        return

    from src import operations_console_v1 as console_module

    original = console_module._spec_from_fragments
    env = environ if environ is not None else os.environ

    def configured_builder(**kwargs: Any) -> dict[str, Any]:
        mode = str(env.get(PASSAGE_FORMATION_MODE_ENV, "") or "").strip() or DETERMINISTIC_MODE
        if mode == DETERMINISTIC_MODE:
            return original(**kwargs)
        if mode != SEMANTIC_MODE:
            raise ConsoleError("passage_formation_mode_invalid")
        return semantic_spec_from_fragments(
            **kwargs,
            api_key=str(env.get(PRE_REVIEW_LLM_API_KEY_ENV, "") or ""),
            model=str(env.get(PRE_REVIEW_LLM_MODEL_ENV, "") or ""),
            post_json=post_json,
        )

    _ORIGINAL_SPEC_BUILDER = original
    console_module._spec_from_fragments = configured_builder
    _INSTALLED = True
