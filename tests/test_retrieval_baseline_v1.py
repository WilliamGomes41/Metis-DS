import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lexical_retrieval_v1 import LexicalIndex, RetrievalConfig, tokenize
from evaluate_retrieval_baseline import evaluate
from retrieval_projection_v2 import build_projection
from semantic_transform_v2 import load_json, transform, sha256_bytes


def fixture_records():
    spec_p = ROOT / "data/semantic_page15_spec.v2.0.json"
    man_p = ROOT / "data/source_manifest.v2.json"
    spec = load_json(spec_p)
    man = load_json(man_p)
    raw_p = ROOT / spec["source_extract"]
    objs = transform(spec, man, sha256_bytes(spec_p.read_bytes()), sha256_bytes(raw_p.read_bytes()))
    envelopes = []
    for obj in objs:
        obj = json.loads(json.dumps(obj))
        obj["governance"]["validation_status"] = "approved"
        obj["uncertainty"] = {"has_uncertainty": False, "items": []}
        envelopes.append({
            "knowledge_object": obj,
            "publication": {
                "release_id": "SYNTHETIC-TEST-ONLY",
                "release_version": "fixture-v1",
                "published_at": "2026-08-19T00:00:00Z",
            },
        })
    records, blocked = build_projection(envelopes)
    assert not blocked
    return records


def config():
    return RetrievalConfig.from_dict(json.loads((ROOT / "config/retrieval_baseline_v1.json").read_text()))


def test_operator_normalization_is_deterministic():
    assert tokenize("BMI < 20 en alcohol ≥ 3") == ["bmi", "lt", "20", "alcohol", "gte", "3"]


def test_fixture_builds_serving_type_records_only():
    records = fixture_records()
    types = {(r.get("metadata") or {}).get("object_type") for r in records}
    assert "score_rule" not in types
    assert "decision" not in types
    assert "action" not in types
    assert len(records) == 11
    assert all("structured_logic" in r for r in records)


def test_baseline_abstains_on_out_of_corpus_vitamin_d_question():
    idx = LexicalIndex(fixture_records(), config())
    r = idx.search("Welke dagelijkse vitamine D-dosering adviseert deze pilotkennisset?")
    assert r["behavior"] == "abstain"


def test_baseline_does_not_serve_historical_score_rule():
    idx = LexicalIndex(fixture_records(), config())
    r = idx.search("Hoe wordt roken en/of alcoholgebruik van 3 of meer eenheden per dag gescoord?")
    ids = [row["object_id"] for row in r.get("results") or []]
    assert not any(item.endswith("score-07") for item in ids)


def test_golden_baseline_prioritizes_abstention_safety():
    golden = json.loads((ROOT / "data/golden/fractuurpreventie_page15_golden_v0.1.json").read_text())
    rep = evaluate(fixture_records(), golden, config())
    m = rep["metrics"]
    # Historical types (score_rule, …) are not served. Lexical hits that used
    # those objects now miss; remaining no-answer cases stay fail-closed.
    assert m["abstention_accuracy"] >= 0.8
    # This is a lexical comparator over the closed serving typeset, not the
    # final acceptance engine. Score-rule questions no longer have a serving
    # object; keep a floor so remaining recommendation/condition hits do not
    # regress.
    assert m["retrieve_any_hit_at_5"] >= 0.40
    # Phrase/logic checks against expected score_rule IDs fail closed because
    # those objects are not in the serving projection.
    assert m["projection_content_integrity"] >= 0.8
