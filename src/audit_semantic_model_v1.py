"""Audit-only LLM caller for source-bound semantic passage experiments.

The caller has no write path into canonical knowledge, review, publication or
production workflow state. Model output is accepted only after the deterministic
semantic passage contract reconstructs candidate units from exact source spans.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.audit_llm_secret_v1 import AuditLLMSecretStore
from src.operations_console_v1 import ConsoleError
from src.semantic_passage_v1 import (
    ALLOWED_PROPOSED_TYPES,
    SemanticPassageError,
    semantic_source_blocks,
    semantic_units_from_proposal,
)


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_TIMEOUT_SECONDS = 60

PostJson = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]


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
        raise ConsoleError("audit_llm_provider_unavailable") from exc
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConsoleError("audit_llm_response_invalid") from exc
    if not isinstance(decoded, dict):
        raise ConsoleError("audit_llm_response_invalid")
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
        raise ConsoleError("audit_llm_response_invalid")
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
                raise ConsoleError("audit_llm_refused")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    text = "".join(texts).strip()
    if not text:
        raise ConsoleError("audit_llm_response_empty")
    return text


def _frozen_item_fragment(item: dict[str, Any]) -> dict[str, Any]:
    item_id = str(item.get("item_id") or "").strip()
    source_text = item.get("source_text")
    if not item_id or not isinstance(source_text, str) or not source_text:
        raise ConsoleError("experiment_dataset_item_invalid")
    return {
        "fragment_id": f"audit-{item_id}",
        "raw_text": source_text,
        "clean_text": source_text,
        "section_path": ["Audit frozen source"],
    }


def _request_payload(*, model: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "developer",
                "content": (
                    "Select only exact source spans from the supplied blocks. "
                    "Do not write, rewrite or paraphrase candidate knowledge text. "
                    "Group spans only when they belong to one independently understandable "
                    "meaning unit. Preserve conditions, exceptions, target group and modality. "
                    "If no safe source-bound proposal is possible, return zero objects and a "
                    "short abstain_reason."
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
                "name": "semantic_passage_proposal",
                "strict": True,
                "schema": _proposal_schema(),
            }
        },
    }


def run_audit_semantic_candidate(
    runtime: Path,
    *,
    item: dict[str, Any],
    model: str,
    post_json: PostJson | None = None,
) -> dict[str, Any]:
    """Call one Audit model route and return source-reconstructed experiment output."""

    safe_model = str(model or "").strip()
    if not safe_model:
        raise ConsoleError("audit_llm_model_required")

    fragment = _frozen_item_fragment(item)
    fragments = [fragment]
    blocks = semantic_source_blocks(fragments)
    if not blocks:
        raise ConsoleError("audit_llm_source_empty")

    api_key = AuditLLMSecretStore(runtime).read_api_key()
    transport = post_json or _post_json
    response = transport(
        OPENAI_RESPONSES_URL,
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        _request_payload(model=safe_model, blocks=blocks),
        DEFAULT_TIMEOUT_SECONDS,
    )
    if not isinstance(response, dict):
        raise ConsoleError("audit_llm_response_invalid")

    try:
        proposal = json.loads(_extract_output_text(response))
    except json.JSONDecodeError as exc:
        raise ConsoleError("audit_llm_response_invalid") from exc
    if not isinstance(proposal, dict):
        raise ConsoleError("audit_llm_response_invalid")

    try:
        units = semantic_units_from_proposal(
            fragments,
            document_id=str(item.get("snapshot_id") or item.get("item_id") or "audit"),
            proposal=proposal,
        )
    except SemanticPassageError as exc:
        raise ConsoleError("audit_llm_proposal_rejected", exc.code) from exc

    return {
        "item_id": str(item.get("item_id") or ""),
        "model": safe_model,
        "proposal": proposal,
        "candidate_units": units,
    }
