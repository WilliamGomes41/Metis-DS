from __future__ import annotations
import json
from pathlib import Path

from src.hybrid_retrieval_v1 import HybridIndex, HybridConfig
from src.lexical_retrieval_v1 import RetrievalConfig
from src.semantic_vector_retrieval_v1 import VectorConfig, read_jsonl
from src.evaluate_hybrid_retrieval import evaluate

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "output/v2/retrieval/baseline_fixture_records.jsonl"
GOLDEN = ROOT / "data/golden/fractuurpreventie_page15_golden_v0.1.json"
HCFG = ROOT / "config/hybrid_retrieval_v1.json"
LCFG = ROOT / "config/retrieval_baseline_v1.json"
VCFG = ROOT / "config/vector_retrieval_v1.json"


def configs():
    return (
        HybridConfig.from_dict(json.loads(HCFG.read_text(encoding="utf-8"))),
        RetrievalConfig.from_dict(json.loads(LCFG.read_text(encoding="utf-8"))),
        VectorConfig.from_dict(json.loads(VCFG.read_text(encoding="utf-8"))),
    )


def test_empty_corpus_abstains():
    h, l, v = configs()
    r = HybridIndex([], h, l, v).search("Wat is het fractuurrisico?")
    assert r["behavior"] == "abstain"
    assert r["reason"] == "empty_published_corpus"


def test_no_answer_still_abstains():
    h, l, v = configs(); records = read_jsonl(RECORDS)
    r = HybridIndex(records, h, l, v).search("Hoeveel milligram calcium per dag wordt in deze pilotkennisset geadviseerd?")
    assert r["behavior"] == "abstain"
    assert r["reason"] == "all_child_engines_abstained"


def test_hybrid_recovers_vector_fact_miss():
    h, l, v = configs(); records = read_jsonl(RECORDS)
    r = HybridIndex(records, h, l, v).search("Welke aandoeningen worden in de achtergrond bij de risicofactoren genoemd?")
    ids = [x["object_id"] for x in r["results"]]
    assert "vvn-osteoporose-fractuurpreventie-2024-p015-background-score-footnote" in ids


def test_hybrid_preserves_high_risk_rule():
    h, l, v = configs(); records = read_jsonl(RECORDS)
    r = HybridIndex(records, h, l, v).search("Hoe wordt roken en/of alcoholgebruik van 3 of meer eenheden per dag gescoord?")
    assert r["behavior"] == "retrieve"
    assert r["results"][0]["object_id"].endswith("score-07")


def test_index_signature_deterministic_across_record_order():
    h, l, v = configs(); records = read_jsonl(RECORDS)
    a = HybridIndex(records, h, l, v)
    b = HybridIndex(list(reversed(records)), h, l, v)
    assert a.index_signature == b.index_signature


def test_golden_metrics_improve_vector_without_safety_loss():
    h, l, v = configs(); records = read_jsonl(RECORDS)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report = evaluate(records, golden, h, l, v)
    m = report["metrics"]
    assert m["retrieve_any_hit_at_5"] == 1.0
    assert m["micro_expected_object_recall_at_5"] == 1.0
    assert m["abstention_accuracy"] == 1.0
    assert m["projection_content_integrity"] == 1.0
