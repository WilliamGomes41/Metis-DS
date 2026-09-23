"""Shared LLM provider and compiled-knowledge boundary regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.compiled_knowledge_v1 import (
    CompiledKnowledgeInputError,
    compiled_knowledge_inputs,
)
from src.g2_source_store import build_g2_locator
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
            "src/workflows/workflow_remaining_cutover_v1.py",
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


class _CanonicalAuthority:
    def __init__(self, rows, *, source_bytes=b"source") -> None:
        self.rows = rows
        self.source_bytes = source_bytes
        digest = hashlib.sha256(source_bytes).hexdigest()
        self.locator = build_g2_locator(sha256=digest, filename="source.pdf")

    def active_publication_rows(self):
        return self.rows

    def release_for_snapshot(self, snapshot_id):
        return {
            "source_sha256": hashlib.sha256(self.source_bytes).hexdigest(),
            "source_locator": self.locator,
        }


class _SourceAuthority:
    def __init__(self, data=b"source") -> None:
        self.data = data

    def load_verified(self, _locator):
        return self.data


def _published_row(object_id="ko-1", snapshot_id="snap-1"):
    return {
        "snapshot_id": snapshot_id,
        "knowledge_object": {"object_id": object_id, "text": "Kennis"},
        "publication": {"release_id": "rel-1"},
    }


def test_compiled_knowledge_reads_active_registry_and_proves_source_bytes() -> None:
    row = _published_row()
    canonical = _CanonicalAuthority([row])
    result = compiled_knowledge_inputs(
        canonical_store=canonical,
        source_store=_SourceAuthority(),
    )
    assert result == [{"knowledge_object": row["knowledge_object"], "publication": row["publication"]}]
    assert result[0]["knowledge_object"] is not row["knowledge_object"]


def test_compiled_knowledge_fails_closed_on_source_mismatch() -> None:
    canonical = _CanonicalAuthority([_published_row()])
    with pytest.raises(CompiledKnowledgeInputError, match="product_source_sha256_mismatch"):
        compiled_knowledge_inputs(
            canonical_store=canonical,
            source_store=_SourceAuthority(b"tampered"),
        )


@pytest.mark.parametrize(
    "rows,error",
    [
        ([{"snapshot_id": "snap-1", "knowledge_object": {"object_id": "ko-1"}}], "compiled_knowledge_publication_row_invalid"),
        ([{"snapshot_id": "snap-1", "publication": {"release_id": "rel-1"}}], "compiled_knowledge_publication_row_invalid"),
        ([{"snapshot_id": "snap-1", "knowledge_object": {}, "publication": {}}], "compiled_knowledge_object_id_required"),
        ([_published_row("ko-1", "snap-1"), _published_row("ko-1", "snap-1")], "compiled_knowledge_duplicate_object"),
    ],
)
def test_compiled_knowledge_rejects_invalid_or_ambiguous_active_rows(rows, error) -> None:
    canonical = _CanonicalAuthority(rows)
    with pytest.raises(CompiledKnowledgeInputError, match=error):
        compiled_knowledge_inputs(
            canonical_store=canonical,
            source_store=_SourceAuthority(),
        )
