import json
from pathlib import Path

from src.answerability_gate_v1 import AnswerabilityConfig, parse_query
from src.hybrid_retrieval_v1 import HybridConfig
from src.lexical_retrieval_v1 import RetrievalConfig
from src.safe_retrieval_v1 import SafeRetrievalIndex
from src.semantic_vector_retrieval_v1 import VectorConfig

ROOT = Path(__file__).resolve().parents[1]


def load_index():
    records = [json.loads(x) for x in (ROOT / "data/fixtures/baseline_v0_1/baseline_fixture_records.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    h = HybridConfig.from_dict(json.loads((ROOT / "config/hybrid_retrieval_v1.json").read_text()))
    l = RetrievalConfig.from_dict(json.loads((ROOT / "config/retrieval_baseline_v1.json").read_text()))
    v = VectorConfig.from_dict(json.loads((ROOT / "config/vector_retrieval_v1.json").read_text()))
    a = AnswerabilityConfig.from_dict(json.loads((ROOT / "config/answerability_gate_v1.json").read_text()))
    return SafeRetrievalIndex(records, h, l, v, a)


def test_query_parser_recognizes_frequency_relation():
    spec = parse_query("Hoe vaak moet aanvullend onderzoek naar osteoporose worden uitgevoerd?")
    assert spec.intent == "frequency_lookup"
    assert "frequency" in spec.required_relations
    assert "osteoporose" in spec.anchors


def test_relation_overlap_without_frequency_evidence_abstains():
    data = load_index().search("Hoe vaak moet aanvullend onderzoek naar osteoporose worden uitgevoerd?")
    assert data["behavior"] == "abstain"
    assert data["answerability"] == "insufficient_evidence"
    assert data["reason"] == "required_relation_not_present"
    assert data["false_positive_class"] == "relation_mismatch"
    assert data["results"] == []


def test_numeric_score_constraint_historical_score_rule_is_not_served():
    data = load_index().search("Hoeveel punten krijgt leeftijd van 60 jaar of ouder?")
    assert data["behavior"] == "abstain"
    assert data["answerability"] != "supported"
    ids = [x["object_id"] for x in data.get("results") or []]
    assert "vvn-osteoporose-fractuurpreventie-2024-p015-score-01" not in ids


def test_unknown_recommendation_subject_abstains():
    data = load_index().search("Adviseert deze kennisset het routinematig gebruik van rollators?")
    assert data["behavior"] == "abstain"
    assert data["results"] == []
    assert data["false_positive_class"] in {"semantic_neighbor", "concept_overlap", "below_confidence_threshold"}


def test_linked_context_can_form_one_evidence_cluster():
    data = load_index().search("Moet bij iedere client van 60 jaar of ouder automatisch de risicofactorenscore worden gebruikt?")
    assert data["behavior"] == "retrieve"
    ids = {x["object_id"] for x in data["results"]}
    assert "vvn-osteoporose-fractuurpreventie-2024-p015-condition-screening-60plus" in ids
    assert "vvn-osteoporose-fractuurpreventie-2024-p015-rec-screening-60plus-01" in ids
    assert any(c["support"] and len(c["object_ids"]) >= 2 for c in data["evidence_clusters"])


def test_patient_specific_diagnosis_is_not_answerable():
    data = load_index().search("Heeft deze specifieke patient osteoporose?")
    assert data["behavior"] == "abstain"
    assert data["reason"] == "patient_specific_context_not_available"
    assert data["false_positive_class"] == "context_mismatch"


def test_numeric_constraint_without_exact_rule_abstains():
    data = load_index().search("Hoeveel punten krijgt leeftijd van 65 jaar of ouder?")
    assert data["behavior"] == "abstain"
    assert data["answerability"] != "supported"


def test_dose_relation_requires_actual_dose_evidence():
    data = load_index().search("Welke dosis prednison wordt geadviseerd?")
    assert data["behavior"] == "abstain"
    assert data["reason"] == "required_relation_not_present"
    assert data["false_positive_class"] == "relation_mismatch"


def test_duration_relation_requires_duration_evidence():
    data = load_index().search("Hoe lang moet prednison worden gebruikt?")
    assert data["behavior"] == "abstain"
    assert data["reason"] == "required_relation_not_present"


def test_score_threshold_relation_is_supported_by_result_threshold():
    data = load_index().search("Bij welke score wordt verwezen naar de huisarts?")
    assert data["behavior"] == "retrieve"
    assert data["answerability"] == "supported"
    assert [x["object_id"] for x in data["results"]] == [
        "vvn-osteoporose-fractuurpreventie-2024-p015-rec-screening-60plus-02"
    ]


def test_recommendation_relation_is_supported():
    data = load_index().search("Adviseert deze kennisset preventieve maatregelen bij verhoogd fractuurrisico?")
    assert data["behavior"] == "retrieve"
    assert data["answerability"] == "supported"
    assert "vvn-osteoporose-fractuurpreventie-2024-p015-rec-recent-fracture-50plus-03" in {
        x["object_id"] for x in data["results"]
    }
