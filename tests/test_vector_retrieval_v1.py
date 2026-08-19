from __future__ import annotations
import json
from pathlib import Path

from src.semantic_vector_retrieval_v1 import LocalVectorIndex, VectorConfig, read_jsonl
from src.evaluate_vector_retrieval import evaluate

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "output/v2/retrieval/baseline_fixture_records.jsonl"
GOLDEN = ROOT / "data/golden/fractuurpreventie_page15_golden_v0.1.json"
CONFIG = ROOT / "config/vector_retrieval_v1.json"


def cfg():
    return VectorConfig.from_dict(json.loads(CONFIG.read_text(encoding="utf-8")))


def test_empty_corpus_abstains():
    result = LocalVectorIndex([], cfg()).search("Wat is de score?")
    assert result["behavior"] == "abstain"
    assert result["reason"] == "empty_published_corpus"


def test_index_signature_is_deterministic():
    records = read_jsonl(RECORDS)
    a = LocalVectorIndex(records, cfg())
    b = LocalVectorIndex(list(reversed(records)), cfg())
    assert a.index_signature == b.index_signature


def test_high_risk_operator_query_retrieves_correct_rule():
    records = read_jsonl(RECORDS)
    result = LocalVectorIndex(records, cfg()).search("Hoe wordt roken en/of alcoholgebruik van 3 of meer eenheden per dag gescoord?")
    assert result["behavior"] == "retrieve"
    assert result["results"][0]["object_id"].endswith("score-07")


def test_no_answer_calcium_abstains():
    records = read_jsonl(RECORDS)
    result = LocalVectorIndex(records, cfg()).search("Hoeveel milligram calcium per dag wordt in deze pilotkennisset geadviseerd?")
    assert result["behavior"] == "abstain"


def test_preliminary_golden_metrics_preserve_safety_and_improve_recall():
    records = read_jsonl(RECORDS)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report = evaluate(records, golden, cfg())
    m = report["metrics"]
    assert m["retrieve_any_hit_at_5"] >= 0.90
    assert m["retrieve_any_hit_at_5"] > 0.6875
    assert m["abstention_accuracy"] == 1.0
    assert m["projection_content_integrity"] == 1.0


def test_metadata_filter_can_fail_closed():
    records = read_jsonl(RECORDS)
    result = LocalVectorIndex(records, cfg()).search("fractuur", filters={"document_id": "does-not-exist"})
    assert result["behavior"] == "abstain"
    assert result["reason"] == "no_records_after_filter"
