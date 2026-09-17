"""Regression proof for source-bound semantic passage formation before Review.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json

import pytest

from src.operations_console_v1 import ConsoleError
from src.pre_review_semantic_v1 import (
    DETERMINISTIC_MODE,
    OPENAI_RESPONSES_URL,
    PASSAGE_FORMATION_MODE_ENV,
    PRE_REVIEW_LLM_API_KEY_ENV,
    PRE_REVIEW_LLM_MODEL_ENV,
    SEMANTIC_MODE,
    install_pre_review_semantic_processing,
    semantic_units_before_review,
)


def _fragment(fragment_id: str, text: str, *, object_type: str | None = None) -> dict:
    row = {
        "fragment_id": fragment_id,
        "raw_text": text,
        "clean_text": text,
        "section_path": ["Behandeling"],
    }
    if object_type:
        row["object_type"] = object_type
    return row


def _response(proposal: dict) -> dict:
    return {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps(proposal)}
                ],
            }
        ]
    }


def test_semantic_processing_runs_before_review_and_reconstructs_source_only() -> None:
    fragments = [
        _fragment("h1", "Behandeling", object_type="heading"),
        _fragment("p1", "Bespreek samen welke behandeling het beste past."),
    ]
    captured: dict = {}

    def fake_post(url: str, headers: dict, payload: dict, timeout: int) -> dict:
        captured.update(url=url, headers=headers, payload=payload, timeout=timeout)
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        return _response(
            {
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": len(block["text"]),
                            }
                        ],
                        "proposed_object_type": "recommendation",
                    }
                ],
                "abstain_reason": None,
            }
        )

    units = semantic_units_before_review(
        fragments,
        document_id="doc-1",
        api_key="product-key",
        model="test-model",
        post_json=fake_post,
    )

    assert captured["url"] == OPENAI_RESPONSES_URL
    assert captured["headers"]["Authorization"] == "Bearer product-key"
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert [row["clean_text"] for row in units] == [
        "Behandeling",
        "Bespreek samen welke behandeling het beste past.",
    ]
    content = units[1]
    assert content["proposed_object_type"] == "recommendation"
    assert content["semantic_passage"]["source_bound"] is True
    assert content["source_fragment_ids"] == ["p1"]


def test_semantic_mode_rejects_model_authored_text_instead_of_falling_back() -> None:
    fragments = [_fragment("p1", "Bespreek samen de behandeling.")]

    def fake_post(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        return _response(
            {
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": len(block["text"]),
                            }
                        ],
                        "proposed_object_type": "recommendation",
                        "candidate_text": "Vrije modeltekst mag niet doorstromen.",
                    }
                ],
                "abstain_reason": None,
            }
        )

    with pytest.raises(ConsoleError) as error:
        semantic_units_before_review(
            fragments,
            document_id="doc-1",
            api_key="product-key",
            model="test-model",
            post_json=fake_post,
        )

    assert error.value.code == "pre_review_llm_proposal_rejected"


def test_provider_failure_is_fail_closed_without_deterministic_fallback() -> None:
    def unavailable(*_args):
        raise ConsoleError("pre_review_llm_provider_unavailable")

    with pytest.raises(ConsoleError) as error:
        semantic_units_before_review(
            [_fragment("p1", "Bespreek samen de behandeling.")],
            document_id="doc-1",
            api_key="product-key",
            model="test-model",
            post_json=unavailable,
        )

    assert error.value.code == "pre_review_llm_provider_unavailable"


def test_runtime_policy_uses_semantic_route_and_keeps_explicit_rollback_mode() -> None:
    from src import operations_console_v1 as console_module
    from src import pre_review_semantic_v1 as semantic_module

    original = console_module._spec_from_fragments
    env = {
        PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE,
        PRE_REVIEW_LLM_API_KEY_ENV: "product-key",
        PRE_REVIEW_LLM_MODEL_ENV: "test-model",
    }

    def fake_post(_url: str, _headers: dict, payload: dict, _timeout: int) -> dict:
        block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        return _response(
            {
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": len(block["text"]),
                            }
                        ],
                        "proposed_object_type": "recommendation",
                    }
                ],
                "abstain_reason": None,
            }
        )

    try:
        semantic_module._INSTALLED = False
        semantic_module._ORIGINAL_SPEC_BUILDER = None
        install_pre_review_semantic_processing(environ=env, post_json=fake_post)
        semantic_spec = console_module._spec_from_fragments(
            document_id="doc-1",
            title="Titel",
            family="kwaliteit",
            class_="richtlijn",
            fragments=[_fragment("p1", "Bespreek samen de behandeling.")],
            content_kind="html",
        )
        assert semantic_spec["objects"][1]["semantic_passage"]["source_bound"] is True

        env[PASSAGE_FORMATION_MODE_ENV] = DETERMINISTIC_MODE
        rollback_spec = console_module._spec_from_fragments(
            document_id="doc-2",
            title="Titel",
            family="kwaliteit",
            class_="richtlijn",
            fragments=[_fragment("p2", "Bespreek samen de behandeling.")],
            content_kind="html",
        )
        assert "semantic_passage" not in rollback_spec["objects"][1]
    finally:
        console_module._spec_from_fragments = original
        semantic_module._INSTALLED = False
        semantic_module._ORIGINAL_SPEC_BUILDER = None
