import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from object_taxonomy_v1 import CLOSED_OBJECT_TYPES
from retrieval_projection_v2 import build_projection, canonical_hash
from validate_golden_set import validate

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs

SEMANTIC = ROOT / "data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v2.jsonl"
GOLDEN = ROOT / "data/golden/fractuurpreventie_page15_golden_v0.1.json"


def load_semantic():
    return [json.loads(x) for x in SEMANTIC.read_text(encoding="utf-8").splitlines() if x.strip()]


def published_envelope(obj, release="fixture-release-1"):
    o = copy.deepcopy(obj)
    o["governance"]["validation_status"] = "approved"
    o["uncertainty"] = {"has_uncertainty": False, "items": []}
    if o.get("object_type") in CLOSED_OBJECT_TYPES and not o.get("confirmed_object_type"):
        o["confirmed_object_type"] = o["object_type"]
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
    assert "Bovenliggende context:" in rr["retrieval_text"]
    assert rr["metadata"]["chunk_readiness"] == {
        "status": "ready",
        "basis": "semantic_not_length",
        "anchor_object_id": rec["object_id"],
        "context_object_ids": [condition["object_id"]],
        "source_anchored": True,
    }


def test_short_atomic_fact_is_chunk_ready_without_length_requirement():
    obj = copy.deepcopy(by_id()["vvn-osteoporose-fractuurpreventie-2024-p015-condition-recent-fracture-50plus"])
    obj["content"]["clean_text"] = "Er is een verhoogd fractuurrisico."
    records, blocked = build_projection([published_envelope(obj)])
    assert blocked == []
    assert "Er is een verhoogd fractuurrisico." in records[0]["retrieval_text"]
    readiness = records[0]["metadata"]["chunk_readiness"]
    assert readiness["status"] == "ready"
    assert readiness["basis"] == "semantic_not_length"
    assert "word" not in json.dumps(readiness).lower()


def test_projection_blocks_dangling_required_context_instead_of_silently_dropping_it():
    rec = by_id()["vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-01"]
    records, blocked = build_projection([published_envelope(rec)])
    assert records == []
    assert blocked == [{
        "object_id": rec["object_id"],
        "object_version": rec["object_version"],
        "errors": [
            "context_target_not_published:"
            "vvn-osteoporose-fractuurpreventie-2024-p015-condition-recent-fracture-50plus"
        ],
    }]


def test_projection_blocks_empty_semantic_content_and_missing_source_anchor():
    obj = copy.deepcopy(by_id()["vvn-osteoporose-fractuurpreventie-2024-p015-condition-recent-fracture-50plus"])
    obj["content"]["clean_text"] = ""
    obj["source"]["source_page"] = None
    obj["source"]["source_url"] = None
    obj["provenance"].pop("source_fragments", None)
    records, blocked = build_projection([published_envelope(obj)])
    assert records == []
    assert blocked[0]["errors"] == ["semantic_content_missing", "source_anchor_missing"]


def test_confirmed_relation_is_typed_and_unrelated_neighbour_is_not_padded_in():
    objs = by_id()
    condition = copy.deepcopy(objs["vvn-osteoporose-fractuurpreventie-2024-p015-condition-recent-fracture-50plus"])
    rec = copy.deepcopy(objs["vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-01"])
    neighbour = copy.deepcopy(objs["vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-02"])
    rec["confirmed_relations"] = [{
        "relation_type": "applies_if",
        "target_object_id": condition["object_id"],
        "confirmed": True,
    }]
    neighbour["parent_object_id"] = None
    neighbour["relations"] = []
    records, blocked = build_projection([
        published_envelope(condition),
        published_envelope(rec),
        published_envelope(neighbour),
    ])
    assert blocked == []
    projected = next(row for row in records if row["metadata"]["object_id"] == rec["object_id"])
    assert "Voorwaarde:" in projected["retrieval_text"]
    assert neighbour["content"]["clean_text"] not in projected["retrieval_text"]
    assert projected["metadata"]["context_relations"][0]["relation_type"] == "applies_if"


def test_projection_does_not_serve_historical_score_rule():
    obj = by_id()["vvn-osteoporose-fractuurpreventie-2024-p015-score-07"]
    records, blocked = build_projection([published_envelope(obj)])
    assert blocked == []
    assert records == []


def test_projection_hash_is_deterministic():
    objs = by_id()
    obj = objs["vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-01"]
    condition = objs["vvn-osteoporose-fractuurpreventie-2024-p015-condition-recent-fracture-50plus"]
    envelopes = [published_envelope(condition), published_envelope(obj)]
    a, _ = build_projection(envelopes)
    b, _ = build_projection(envelopes)
    a = [row for row in a if row["metadata"]["object_id"] == obj["object_id"]]
    b = [row for row in b if row["metadata"]["object_id"] == obj["object_id"]]
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
