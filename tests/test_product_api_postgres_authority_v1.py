"""REAL Product API must read PostgreSQL authority, never local JSONL.

# release-control-evidence: opslag
# release-control-evidence: scope/belofte
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.product_api_v1 import ProductCorpusError, ProductPaths, create_product_app
from src.product_security_v1 import TenantPolicy, TenantRegistry, hash_api_key
from src.usage_ledger_v1 import UsageLedger

ROOT = Path(__file__).resolve().parents[1]
KEY = "postgres-authority-test-key"

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_releasebewijs,
]


class Authority:
    def __init__(self, rows: list[dict] | None = None, *, fail: bool = False) -> None:
        self.rows = rows or []
        self.fail = fail
        self.reads = 0

    def active_publication_rows(self) -> list[dict]:
        self.reads += 1
        if self.fail:
            raise RuntimeError("postgres unavailable")
        return self.rows


def _object() -> dict:
    return {
        "object_id": "ko-postgres-1",
        "document_id": "doc-postgres",
        "object_version": "1.0",
        "object_type": "explanation",
        "confirmed_object_type": "explanation",
        "parent_object_id": None,
        "content": {
            "clean_text": "Dit record komt uitsluitend uit de PostgreSQL publication registry.",
            "topic": ["test"],
            "target_group": [],
            "care_setting": [],
        },
        "structure": {"section_path": [], "heading": None},
        "source": {
            "title": "PostgreSQL authority",
            "source_url": "https://example.test/source",
            "source_page": 1,
            "version": "1.0",
        },
        "provenance": {
            "content_hash": "a" * 64,
            "source_fragments": [],
        },
        "governance": {"validation_status": "approved"},
        "uncertainty": {"has_uncertainty": False},
        "logic": {},
        "risk": {"risk_level": "low"},
        "relations": [],
    }


def _paths(tmp_path: Path) -> ProductPaths:
    defaults = ProductPaths.defaults(ROOT)
    poison_records = tmp_path / "real_current_retrieval_records.jsonl"
    poison_published = tmp_path / "real_current_published.jsonl"
    poison_records.write_text(json.dumps({"retrieval_text": "POISON LOCAL JSONL"}) + "\n", encoding="utf-8")
    poison_published.write_text(json.dumps({"knowledge_object": {"object_id": "poison"}}) + "\n", encoding="utf-8")
    return ProductPaths(
        real_records=poison_records,
        fixture_records=defaults.fixture_records,
        real_published=poison_published,
        lexical_config=defaults.lexical_config,
        vector_config=defaults.vector_config,
        hybrid_config=defaults.hybrid_config,
        tenant_config=tmp_path / "unused.json",
        usage_db=tmp_path / "usage.sqlite",
    )


def _registry() -> TenantRegistry:
    return TenantRegistry([
        TenantPolicy.from_dict({
            "tenant_id": "postgres-test",
            "name": "Postgres test",
            "enabled": True,
            "api_key_sha256": hash_api_key(KEY),
            "scopes": ["retrieve", "knowledge:read", "documents:read", "updates:read"],
            "allowed_document_ids": ["*"],
            "allowed_topics": ["*"],
            "requests_per_minute": 100,
            "max_top_k": 5,
        })
    ])


def _authority() -> Authority:
    obj = _object()
    return Authority([
        {
            "knowledge_object": obj,
            "publication": {
                "release_id": "release-postgres-1",
                "release_version": "1.0",
                "published_at": "2026-09-11T20:00:00+00:00",
            },
            "snapshot_id": "snap-authority",
            "release_owner": "publisher",
        }
    ])


def test_real_mode_ignores_poisoned_local_jsonl_and_reads_postgres(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    authority = _authority()
    app = create_product_app(
        "real",
        paths=paths,
        tenant_registry=_registry(),
        canonical_publication_store=authority,
        usage_ledger=UsageLedger(paths.usage_db),
    )
    state = app.state.product

    assert authority.reads >= 1
    assert len(state.records) == 1
    assert state.records[0]["metadata"]["object_id"] == "ko-postgres-1"
    assert "POISON LOCAL JSONL" not in json.dumps(state.records)

    client = TestClient(app)
    health = client.get("/v1/health").json()
    assert health["published_corpus_authority"] == "postgres"
    assert health["corpus_reload_policy"] == "postgres_active_publication_registry"


def test_real_mode_has_no_local_jsonl_fallback_when_postgres_fails(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    with pytest.raises(ProductCorpusError, match="canonical_publication_store_unavailable"):
        create_product_app(
            "real",
            paths=paths,
            tenant_registry=_registry(),
            canonical_publication_store=Authority(fail=True),
            usage_ledger=UsageLedger(paths.usage_db),
        )


def test_real_mode_requires_authority_instead_of_accepting_legacy_files(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    with pytest.raises(ProductCorpusError, match="canonical_publication_store_required"):
        from src.product_api_v1 import ProductState
        ProductState(
            "real",
            paths,
            _registry(),
            canonical_publication_store=None,
            usage_ledger=UsageLedger(paths.usage_db),
        )
