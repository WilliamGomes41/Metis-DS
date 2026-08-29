import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from retrieval_projection_v2 import build_projection, canonical_hash
from validate_golden_set import validate

SEMANTIC = ROOT / "data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v2.jsonl"
GOLDEN = ROOT / "data/golden/fractuurpreventie_page15_golden_v0.1.json"


def load_semantic():
    return [json.loads(x) for x in SEMANTIC.read_text(encoding="utf-8").splitlines() if x.strip()]


def published_envelope(obj, release="fixture-release-1"):
    o = copy.deepcopy(obj)
    o["governance"]["validation_status"] = "approved"
    o["uncertainty"] = {"has_uncertainty": False, "items": []}
    return {
        "knowledge_object": o,
        "publication": {
            "release_id": release,
            "release_version": "fixture-v1",
            "published_at": "2026-08-19T12:00:00+00:00",
        },
    }


def by_id():
    return {o["object_id"]: o for o in load_semantic()}


def test_projection_requires_explicit_publication_envelope():
    obj = load_semantic()[1]
    records, blocked = build_projection([{"knowledge_object": obj}])
    assert records == []
    assert blocked[0]["errors"] == ["publication_envelope_missing"]


def test_projection_blocks_unapproved_object():
    obj = copy.deepcopy(load_semantic()[1])
    obj["uncertainty"] = {"has_uncertainty": False, "items": []}
    env = {"knowledge_object": obj, "publication": {"release_id": "r", "release_version": "v", "published_at": "t"}}
    records, blocked = build_projection([env])
    assert records == []
    assert "object_not_clinically_approved" in blocked[0]["errors"]


def test_projection_excludes_non_searchable_document_and_section():
    objs = by_id()
    envs = [
        published_envelope(objs["vvn-osteoporose-fractuurpreventie-2024-document"]),
        published_envelope(objs["vvn-osteoporose-fractuurpreventie-2024-p015-table-risk-score"]),
    ]
    records, blocked = build_projection(envs)
    assert blocked == []
    assert records == []


def test_recommendation_inherits_published_condition_context():
    objs = by_id()
    condition = objs["vvn-osteoporose-fractuurpreventie-2024-p015-condition-recent-fracture-50plus"]
    rec = objs["vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-01"]
    records, blocked = build_projection([published_envelope(condition), published_envelope(rec)])
    assert blocked == []
    rr = next(r for r in records if r["metadata"]["object_id"] == rec["object_id"])
    assert condition["object_id"] in rr["metadata"]["context_object_ids"]
    assert "≥ 50 jaar" in rr["retrieval_text"]
    assert "DXA-VFA" in rr["retrieval_text"]


def test_projection_does_not_serve_historical_score_rule():
    obj = by_id()["vvn-osteoporose-fractuurpreventie-2024-p015-score-07"]
    records, blocked = build_projection([published_envelope(obj)])
    assert blocked == []
    assert records == []


def test_projection_hash_is_deterministic():
    obj = by_id()["vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-01"]
    env = published_envelope(obj)
    a, _ = build_projection([env])
    b, _ = build_projection([env])
    assert a == b
    core = {k: a[0][k] for k in ("retrieval_id", "retrieval_text", "structured_logic", "metadata")}
    assert a[0]["projection_hash"] == canonical_hash(core)


def test_golden_set_is_structurally_valid_and_has_25pct_abstention():
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report = validate(data)
    assert report["status"] == "PASS"
    assert report["questions"] == 24
    assert report["class_counts"]["no_answer"] == 6
    assert report["no_answer_share"] == 0.25


def test_golden_expected_objects_exist_in_current_semantic_fixture():
    known = set(by_id())
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    missing = []
    for q in data["questions"]:
        for oid in q.get("expected_object_ids", []):
            if oid not in known:
                missing.append((q["id"], oid))
    assert missing == []


def test_all_no_answer_questions_require_abstention():
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    no_answer = [q for q in data["questions"] if q["class"] == "no_answer"]
    assert no_answer
    assert all(q["expected_behavior"] == "abstain" and q.get("expected_object_ids") == [] for q in no_answer)
