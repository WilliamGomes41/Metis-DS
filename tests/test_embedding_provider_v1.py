from __future__ import annotations
import json
from pathlib import Path

import pytest

from src.embedding_provider_v1 import build_provider
from src.provider_vector_retrieval_v1 import ProviderVectorIndex, ProviderVectorConfig
from src.semantic_vector_retrieval_v1 import LocalVectorIndex, VectorConfig, read_jsonl

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "data/fixtures/baseline_v0_1/baseline_fixture_records.jsonl"
PCFG = ROOT / "config/embedding_provider_local_v1.json"
VCFG = ROOT / "config/vector_retrieval_v1.json"


def provider():
    return build_provider(json.loads(PCFG.read_text(encoding="utf-8")))


def test_provider_config_rejects_secret_material():
    with pytest.raises(ValueError, match="secret_material_not_allowed"):
        build_provider({"provider": "local_char_tfidf", "api_key": "do-not-store"})


def test_unknown_provider_fails_closed():
    with pytest.raises(ValueError, match="embedding_provider_not_implemented"):
        build_provider({"provider": "azure_openai"})


def test_local_provider_metadata_is_auditable():
    p = provider(); p.fit(["alpha", "beta"]); meta = p.metadata()
    assert meta["provider_id"] == "local-char-tfidf-v1"
    assert meta["deterministic"] is True
    assert meta["credentials_in_config"] is False
    assert meta["dimension"] > 0


def test_provider_vector_index_matches_step8_top5_and_scores():
    records = read_jsonl(RECORDS)
    old_cfg = VectorConfig.from_dict(json.loads(VCFG.read_text(encoding="utf-8")))
    old = LocalVectorIndex(records, old_cfg)
    new = ProviderVectorIndex(records, provider(), ProviderVectorConfig(top_k=old_cfg.top_k, min_similarity=old_cfg.min_similarity))
    queries = [
        "Welke aandoeningen worden in de achtergrond bij de risicofactoren genoemd?",
        "Hoe wordt roken en/of alcoholgebruik van 3 of meer eenheden per dag gescoord?",
        "Hoeveel milligram calcium per dag wordt in deze pilotkennisset geadviseerd?",
    ]
    for q in queries:
        a, b = old.search(q), new.search(q)
        assert a["behavior"] == b["behavior"]
        assert [x["object_id"] for x in a.get("results", [])] == [x["object_id"] for x in b.get("results", [])]
        if a.get("results"):
            assert [x["score"] for x in a["results"]] == [x["score"] for x in b["results"]]
