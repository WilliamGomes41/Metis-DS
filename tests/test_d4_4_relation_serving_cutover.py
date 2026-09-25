"""D4.4 confirmed KnowledgeRelation serving cutover regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.knowledge_relations_v1 import build_knowledge_relation
from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import TenantPolicy, TenantRegistry, hash_api_key
from src.retrieval.retrieval_projection_v2 import build_projection
from src.usage_ledger_v1 import UsageLedger


ROOT = Path(__file__).resolve().parents[1]
SEMANTIC = ROOT / "data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v2.jsonl"
KEY = "d44-fixture-key"


def _fixture_objects() -> dict[str, dict]:
    rows = [
        json.loads(line)
        for line in SEMANTIC.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {row["object_id"]: row for row in rows}


def _published(obj: dict) -> dict:
    row = copy.deepcopy(obj)
    row.setdefault("governance", {})["validation_status"] = "approved"
    row["uncertainty"] = {"has_uncertainty": False, "items": []}
    if not row.get("confirmed_object_type"):
        row["confirmed_object_type"] = row["object_type"]
    return {
        "knowledge_object": row,
        "publication": {
            "release_id": "d44-release",
            "release_version": "1",
            "published_at": "2026-09-25T16:00:00+00:00",
        },
    }


def _registry() -> TenantRegistry:
    return TenantRegistry(
        [
            TenantPolicy.from_dict(
                {
                    "tenant_id": "d44-test",
                    "name": "D4.4 test",
                    "enabled": True,
                    "api_key_sha256": hash_api_key(KEY),
                    "scopes": ["retrieve", "knowledge:read"],
                    "allowed_document_ids": ["*"],
                    "allowed_topics": ["*"],
                    "requests_per_minute": 100,
                    "max_top_k": 5,
                }
            )
        ]
    )


def _client(tmp_path: Path, records: list[dict]) -> TestClient:
    path = tmp_path / "records.jsonl"
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )
    defaults = ProductPaths.defaults(ROOT)
    paths = ProductPaths(
        real_records=defaults.real_records,
        fixture_records=path,
        real_published=defaults.real_published,
        lexical_config=defaults.lexical_config,
        vector_config=defaults.vector_config,
        hybrid_config=defaults.hybrid_config,
        tenant_config=tmp_path / "unused-tenants.json",
        usage_db=tmp_path / "usage.sqlite",
    )
    return TestClient(
        create_product_app(
            "fixture",
            paths=paths,
            tenant_registry=_registry(),
            usage_ledger=UsageLedger(paths.usage_db),
            allow_fixture=True,
        )
    )


def _case() -> tuple[dict, dict, dict, dict]:
    objs = _fixture_objects()
    condition = copy.deepcopy(
        objs["vvn-osteoporose-fractuurpreventie-2024-p015-condition-recent-fracture-50plus"]
    )
    rec_a = copy.deepcopy(
        objs["vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-01"]
    )
    rec_b = copy.deepcopy(
        objs["vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-02"]
    )
    explanation = copy.deepcopy(condition)
    explanation["object_id"] = "d44-explanation"
    explanation["object_type"] = "explanation"
    explanation["confirmed_object_type"] = "explanation"
    explanation["parent_object_id"] = None
    explanation["content"]["clean_text"] = "Onderbouwing voor deze aanbeveling."

    for row in (condition, rec_a, rec_b, explanation):
        row["parent_object_id"] = None
        row["relations"] = []
        row.pop("confirmed_relations", None)
        row.pop("proposed_knowledge_relations", None)
        row.pop("confirmed_knowledge_relations", None)
        row["confirmed_object_type"] = row["object_type"]

    return condition, rec_a, rec_b, explanation


def test_projection_serves_many_to_many_confirmed_relations_only() -> None:
    condition, rec_a, rec_b, explanation = _case()

    rec_a["confirmed_knowledge_relations"] = [
        build_knowledge_relation(
            source_object_id=rec_a["object_id"],
            source_object_version=rec_a["object_version"],
            relation_type="applies_if",
            target_object_id=condition["object_id"],
            target_object_version=condition["object_version"],
        ),
        build_knowledge_relation(
            source_object_id=rec_a["object_id"],
            source_object_version=rec_a["object_version"],
            relation_type="supported_by",
            target_object_id=explanation["object_id"],
            target_object_version=explanation["object_version"],
        ),
    ]
    rec_a["confirmed_knowledge_relations"].sort(
        key=lambda row: (
            row["relation_type"],
            row["target_object_id"],
            row["target_object_version"],
            row["relation_id"],
        )
    )
    rec_b["confirmed_knowledge_relations"] = [
        build_knowledge_relation(
            source_object_id=rec_b["object_id"],
            source_object_version=rec_b["object_version"],
            relation_type="applies_if",
            target_object_id=condition["object_id"],
            target_object_version=condition["object_version"],
        )
    ]

    records, blocked = build_projection(
        [_published(condition), _published(explanation), _published(rec_a), _published(rec_b)]
    )
    assert blocked == []

    by_id = {row["metadata"]["object_id"]: row for row in records}
    a = by_id[rec_a["object_id"]]
    b = by_id[rec_b["object_id"]]

    assert a["metadata"]["confirmed_knowledge_relations"] == rec_a["confirmed_knowledge_relations"]
    assert b["metadata"]["confirmed_knowledge_relations"] == rec_b["confirmed_knowledge_relations"]
    assert a["metadata"]["applies_if_object_ids"] == [condition["object_id"]]
    assert b["metadata"]["applies_if_object_ids"] == [condition["object_id"]]
    assert condition["content"]["clean_text"] in a["retrieval_text"]
    assert explanation["content"]["clean_text"] in a["retrieval_text"]
    assert condition["content"]["clean_text"] in b["retrieval_text"]


def test_proposal_and_legacy_semantic_edges_are_not_promoted() -> None:
    condition, rec, _rec_b, _explanation = _case()

    rec["proposed_knowledge_relations"] = [
        build_knowledge_relation(
            source_object_id=rec["object_id"],
            source_object_version=rec["object_version"],
            relation_type="applies_if",
            target_object_id=condition["object_id"],
            target_object_version=condition["object_version"],
        )
    ]
    rec["relations"] = [
        {
            "relation_type": "applies_if",
            "target_object_id": condition["object_id"],
            "target_object_version": condition["object_version"],
            "confirmed": False,
        }
    ]
    rec["confirmed_relations"] = [
        {
            "relation_type": "applies_if",
            "target_object_id": condition["object_id"],
            "confirmed": True,
        }
    ]

    records, blocked = build_projection([_published(condition), _published(rec)])
    assert blocked == []
    projected = next(row for row in records if row["metadata"]["object_id"] == rec["object_id"])
    assert projected["metadata"]["confirmed_knowledge_relations"] == []
    assert projected["metadata"]["applies_if_object_ids"] == []
    assert condition["content"]["clean_text"] not in projected["retrieval_text"]


def test_product_api_exposes_same_confirmed_relations_and_bounds(tmp_path: Path) -> None:
    condition, rec, _rec_b, _explanation = _case()
    rec["confirmed_knowledge_relations"] = [
        build_knowledge_relation(
            source_object_id=rec["object_id"],
            source_object_version=rec["object_version"],
            relation_type="applies_if",
            target_object_id=condition["object_id"],
            target_object_version=condition["object_version"],
        )
    ]
    records, blocked = build_projection([_published(condition), _published(rec)])
    assert blocked == []
    expected = rec["confirmed_knowledge_relations"]

    client = _client(tmp_path, records)
    knowledge = client.get(
        f"/v1/knowledge/{rec['object_id']}",
        headers={"Authorization": f"Bearer {KEY}"},
    )
    assert knowledge.status_code == 200
    assert knowledge.json()["knowledge_relations"] == expected

    state = client.app.state.product

    class SupportedIndex:
        def search(self, query: str, top_k: int) -> dict:
            return {
                "behavior": "retrieve",
                "answerability": "supported",
                "reason": "evidence_gate_passed",
                "false_positive_class": None,
                "labels": ["V", "VN"],
                "advice_weight": True,
                "abstain_sentence": None,
                "results": [
                    {
                        "object_id": rec["object_id"],
                        "object_version": rec["object_version"],
                        "object_type": "recommendation",
                        "rrf_score": 1.0,
                        "lexical_score": 1.0,
                        "vector_score": 1.0,
                        "advice_weight": True,
                        "labels": ["V", "VN"],
                    }
                ],
            }

    state._safe_index = lambda rows: SupportedIndex()
    response = client.post(
        "/v1/retrieve",
        headers={"Authorization": f"Bearer {KEY}"},
        json={"query": "Wanneer geldt deze aanbeveling?", "top_k": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["knowledge_relations"] == expected
    assert data["results"][0]["applies_if"][0]["knowledge_object_id"] == condition["object_id"]


def test_legacy_semantic_metadata_cannot_reenter_product_api_bounds(tmp_path: Path) -> None:
    condition, rec, _rec_b, _explanation = _case()
    records, blocked = build_projection([_published(condition), _published(rec)])
    assert blocked == []

    projected = next(row for row in records if row["metadata"]["object_id"] == rec["object_id"])
    projected["metadata"]["confirmed_relations"] = [
        {
            "relation_type": "applies_if",
            "target_object_id": condition["object_id"],
            "confirmed": True,
        }
    ]

    client = _client(tmp_path, records)
    state = client.app.state.product

    class SupportedIndex:
        def search(self, query: str, top_k: int) -> dict:
            return {
                "behavior": "retrieve",
                "answerability": "supported",
                "reason": "evidence_gate_passed",
                "false_positive_class": None,
                "labels": ["V", "VN"],
                "advice_weight": True,
                "abstain_sentence": None,
                "results": [
                    {
                        "object_id": rec["object_id"],
                        "object_version": rec["object_version"],
                        "object_type": "recommendation",
                        "rrf_score": 1.0,
                        "lexical_score": 1.0,
                        "vector_score": 1.0,
                        "advice_weight": True,
                        "labels": ["V", "VN"],
                    }
                ],
            }

    state._safe_index = lambda rows: SupportedIndex()
    response = client.post(
        "/v1/retrieve",
        headers={"Authorization": f"Bearer {KEY}"},
        json={"query": "Wanneer geldt deze aanbeveling?", "top_k": 1},
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["applies_if"] == []
    assert "knowledge_relations" not in result
