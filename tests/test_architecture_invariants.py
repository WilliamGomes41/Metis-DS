from __future__ import annotations

import json
from pathlib import Path

from src.answerability_gate_v1 import AnswerabilityConfig
from src.hybrid_retrieval_v1 import HybridConfig
from src.lexical_retrieval_v1 import RetrievalConfig
from src.product_api_v1 import ProductPaths
from src.safe_retrieval_v1 import SafeRetrievalIndex
from src.semantic_vector_retrieval_v1 import VectorConfig


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data/fixtures/baseline_v0_1"


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _safe_index() -> SafeRetrievalIndex:
    return SafeRetrievalIndex(
        _read_jsonl(FIXTURES / "baseline_fixture_records.jsonl"),
        HybridConfig.from_dict(_read_json(ROOT / "config/hybrid_retrieval_v1.json")),
        RetrievalConfig.from_dict(_read_json(ROOT / "config/retrieval_baseline_v1.json")),
        VectorConfig.from_dict(_read_json(ROOT / "config/vector_retrieval_v1.json")),
        AnswerabilityConfig.from_dict(_read_json(ROOT / "config/answerability_gate_v1.json")),
    )


def test_tests_and_fixture_mode_do_not_depend_on_runtime_output():
    fixture_path = ProductPaths.defaults(ROOT).fixture_records
    assert fixture_path.is_relative_to(ROOT / "data/fixtures")
    assert fixture_path.exists()


def test_retrieval_projection_preserves_structured_logic():
    records = _read_jsonl(FIXTURES / "baseline_fixture_records.jsonl")
    assert records
    assert all("structured_logic" in record for record in records)
    assert any(
        isinstance(record["structured_logic"], dict)
        and record["structured_logic"].get("predicates")
        for record in records
    )


def test_answerability_remains_a_separate_fail_closed_decision():
    index = _safe_index()
    supported = index.search("Wanneer gebruik je de risicofactorenscore?")
    unsupported = index.search("Hoe vaak moet een DXA-meting tijdens behandeling worden herhaald?")
    assert supported["behavior"] == "retrieve"
    assert supported["answerability"] == "supported"
    assert unsupported["behavior"] == "abstain"
    assert unsupported["answerability"] == "insufficient_evidence"
    assert unsupported["results"] == []


def test_source_manifests_retain_stable_source_ids_and_fail_closed_integrity():
    source1 = _read_json(ROOT / "data/source_manifest.v2.json")["canonical_source"]
    source2 = _read_json(ROOT / "data/source_manifest.continentie.v1.json")["canonical_source"]
    for source in (source1, source2):
        assert source["source_id"]
        assert source["integrity_status"] == "binary_unavailable"
        assert source["source_checksum"] is None


def test_html_provenance_contract_retains_source_locator():
    raw_schema = _read_json(ROOT / "schemas/raw_fragment.schema.v1.1.json")
    object_schema = _read_json(ROOT / "schemas/knowledge_object.schema.v1.2.json")
    assert "source_locator" in raw_schema["properties"]
    fragment = object_schema["properties"]["provenance"]["properties"]["source_fragments"]["items"]
    assert "source_locator" in fragment["properties"]


def test_canonical_store_uses_integrity_kernel_hashes():
    from src.canonical_store import first_review_snapshot_hash, recompute_content_hash
    from src.integrity_kernel import compute_canonical_object_hash, exact_review_snapshot_hash

    records = _read_jsonl(FIXTURES / "fractuurpreventie_page15_semantic_v21.jsonl")
    obj = records[0]
    assert recompute_content_hash(obj) == compute_canonical_object_hash(obj)
    assert first_review_snapshot_hash(obj) == exact_review_snapshot_hash(obj)
    assert recompute_content_hash(obj) == first_review_snapshot_hash(obj)
    tampered = dict(obj)
    tampered["source"] = dict(obj["source"], title="tampered")
    assert recompute_content_hash(tampered) != recompute_content_hash(obj)
