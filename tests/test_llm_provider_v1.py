"""Shared LLM provider and compiled-knowledge boundary regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.compiled_knowledge_v1 import (
    CompiledKnowledgeInputError,
    compiled_knowledge_inputs,
)
from src.llm_provider_v1 import (
    LLM_API_KEY_ENV,
    LLM_MODEL_ENV,
    load_llm_provider_config,
)

ROOT = Path(__file__).resolve().parents[1]


def test_one_provider_config_is_shared_by_all_llm_capabilities() -> None:
    config = load_llm_provider_config(
        {LLM_API_KEY_ENV: "provider-secret", LLM_MODEL_ENV: "shared-model"}
    )
    assert config.api_key == "provider-secret"
    assert config.model == "shared-model"
    assert config.configured is True


def test_missing_shared_provider_config_remains_unconfigured() -> None:
    assert load_llm_provider_config({}).configured is False
    assert load_llm_provider_config({LLM_API_KEY_ENV: "key"}).configured is False
    assert load_llm_provider_config({LLM_MODEL_ENV: "model"}).configured is False


def test_active_llm_runtime_has_no_capability_specific_provider_keys_or_models() -> None:
    active = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "src/llm_provider_v1.py",
            "src/audit_room_v1.py",
            "src/audit_semantic_safety_v1.py",
            "src/pre_review_semantic_v1.py",
            "src/console_asgi.py",
            "src/workflow_remaining_cutover_v1.py",
            "src/compiled_knowledge_v1.py",
        )
    )
    for deprecated in (
        "METIS_AUDIT_SECRET_KEY",
        "METIS_AUDIT_LLM_MODEL",
        "METIS_PRE_REVIEW_LLM_API_KEY",
        "METIS_PRE_REVIEW_LLM_MODEL",
        "AuditLLMSecretStore",
        "PostgresAuditLLMSecretStore",
    ):
        assert deprecated not in active


def test_compiled_knowledge_accepts_only_publication_authority_rows() -> None:
    rows = [
        {
            "knowledge_object": {"object_id": "ko-1", "text": "Kennis"},
            "publication": {"release_id": "rel-1"},
        }
    ]
    result = compiled_knowledge_inputs(rows)
    assert result == rows
    assert result is not rows
    assert result[0] is not rows[0]


@pytest.mark.parametrize(
    "rows,error",
    [
        ([{"knowledge_object": {"object_id": "ko-1"}}], "compiled_knowledge_publication_row_required"),
        ([{"publication": {"release_id": "rel-1"}}], "compiled_knowledge_publication_row_required"),
        ([{"knowledge_object": {}, "publication": {}}], "compiled_knowledge_object_id_required"),
        ([
            {"knowledge_object": {"object_id": "ko-1"}, "publication": {}},
            {"knowledge_object": {"object_id": "ko-1"}, "publication": {}},
        ], "compiled_knowledge_duplicate_object"),
    ],
)
def test_compiled_knowledge_rejects_non_authoritative_or_ambiguous_input(rows, error) -> None:
    with pytest.raises(CompiledKnowledgeInputError, match=error):
        compiled_knowledge_inputs(rows)
