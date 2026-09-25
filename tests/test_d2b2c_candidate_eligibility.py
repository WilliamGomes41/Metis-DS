"""D2b2-C: source passages are not automatically KnowledgeCandidates.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from src.admission_gate_v1 import (
    GATE_BLOCKED,
    admission_of,
    apply_admission_gate,
    is_inhoudelijk_candidate,
)
from src.candidate_eligibility_v1 import (
    CANDIDATE_ELIGIBILITY_VERSION,
    REASON_EXPLICIT_TYPE,
    REASON_NO_TYPE,
    REASON_SEMANTIC_COVERAGE,
    REASON_SEMANTIC_PROPOSAL,
    candidate_eligibility_of,
)
from src.domain_dimensions_v1 import processing_issue_objects
from src.passage_register_v1 import apply_passage_register, passage_register_of


def _passage(
    *,
    object_id: str,
    text: str,
    proposed_type: str = "",
    metadata: dict | None = None,
) -> dict:
    row = {
        "object_id": object_id,
        "document_id": "doc-d2b2c",
        "object_version": "1.0",
        "object_type": "unclassified",
        "source": {"source_checksum": "a" * 64},
        "structure": {"section_path": ["2. Inleiding"]},
        "content": {"raw_text": text, "clean_text": text},
        "metadata": {
            "source_locator": {
                "locator_type": "page_bbox",
                "locator_value": "page:1;bbox:1,1,2,2",
            }
        },
    }
    if proposed_type:
        row["proposed_object_type"] = proposed_type
    if metadata:
        row["metadata"].update(metadata)
    return row


def _gate(objects: list[dict]) -> list[dict]:
    return apply_admission_gate(
        objects,
        klasse="richtlijn",
        document_version="1.0",
        source_hash="a" * 64,
    )


def test_deterministic_unclassified_passage_is_coverage_not_candidate() -> None:
    source = _passage(
        object_id="plain-1",
        text="Eenzaamheid komt veel voor onder ouderen.",
    )

    [row] = apply_passage_register(_gate([source]))

    eligibility = candidate_eligibility_of(row)
    assert eligibility == {
        "version": CANDIDATE_ELIGIBILITY_VERSION,
        "eligible": False,
        "reason": REASON_NO_TYPE,
        "source": "deterministic",
    }
    assert admission_of(row) == {}
    assert is_inhoudelijk_candidate(row) is False
    assert processing_issue_objects([row]) == []
    assert passage_register_of(row)["status"] == "not_yet_assessed"
    assert passage_register_of(row)["source"] == "extract"


def test_explicit_deterministic_type_proposal_enters_admission() -> None:
    source = _passage(
        object_id="definition-1",
        text="Continentie is een klinisch onderwerp in de ouderenzorg.",
        proposed_type="definition",
    )

    [row] = _gate([source])

    eligibility = candidate_eligibility_of(row)
    assert eligibility["eligible"] is True
    assert eligibility["reason"] == REASON_EXPLICIT_TYPE
    assert eligibility["source"] == "deterministic"
    assert admission_of(row)
    assert is_inhoudelijk_candidate(row) is True


def test_semantic_proposal_selected_is_candidate_even_when_type_is_unclassified() -> None:
    source = _passage(
        object_id="semantic-selected",
        text="Deze passage is door de locator als kandidaat geselecteerd.",
        proposed_type="unclassified",
        metadata={
            "semantic_passage": {
                "selection_origin": "proposal_selected",
            }
        },
    )

    [row] = _gate([source])

    eligibility = candidate_eligibility_of(row)
    assert eligibility["eligible"] is True
    assert eligibility["reason"] == REASON_SEMANTIC_PROPOSAL
    assert eligibility["source"] == "semantic"
    assert admission_of(row)
    assert admission_of(row)["gate_result"] == GATE_BLOCKED


def test_semantic_coverage_remainder_never_enters_admission() -> None:
    source = _passage(
        object_id="semantic-coverage",
        text="Gebruik deze tekst alleen voor volledige brondekking.",
        proposed_type="recommendation",
        metadata={
            "semantic_passage": {
                "selection_origin": "coverage_remainder",
            }
        },
    )

    [row] = apply_passage_register(_gate([source]))

    eligibility = candidate_eligibility_of(row)
    assert eligibility["eligible"] is False
    assert eligibility["reason"] == REASON_SEMANTIC_COVERAGE
    assert eligibility["source"] == "semantic"
    assert admission_of(row) == {}
    assert processing_issue_objects([row]) == []
    assert passage_register_of(row)["status"] == "not_yet_assessed"


def test_reprocessing_ineligible_passage_removes_stale_admission_but_keeps_review_disposition() -> None:
    source = _passage(
        object_id="legacy-false-candidate",
        text="Eenzaamheid komt veel voor onder ouderen.",
        metadata={
            "admission": {
                "gate_result": "blocked",
                "reason_codes": ["type_evidence_missing"],
                "proposed_type": "recommendation",
            },
            "passage_register": {
                "status": "excluded_with_reason",
                "reason_codes": ["geen_kenniseenheid"],
                "suitability": "geen_kenniseenheid",
                "source": "review",
                "linked_object_id": "",
                "section_path": ["2. Inleiding"],
            },
        },
    )

    [gated] = _gate([source])
    [row] = apply_passage_register([gated])

    assert admission_of(row) == {}
    assert candidate_eligibility_of(row)["eligible"] is False
    assert passage_register_of(row)["status"] == "excluded_with_reason"
    assert passage_register_of(row)["source"] == "review"
    assert passage_register_of(row)["suitability"] == "geen_kenniseenheid"


def test_legacy_persisted_admission_remains_candidate_projection_until_reprocessed() -> None:
    legacy = _passage(
        object_id="legacy-candidate",
        text="Eenzaamheid komt veel voor onder ouderen.",
        metadata={
            "admission": {
                "gate_result": "blocked",
                "reason_codes": ["type_evidence_missing"],
            }
        },
    )

    assert candidate_eligibility_of(legacy) == {}
    assert is_inhoudelijk_candidate(legacy) is True


def test_candidate_eligibility_does_not_infer_type_from_prevalence_text() -> None:
    source = _passage(
        object_id="prevalence-source",
        text="Urine-incontinentie komt bij ouderen vaak voor in Nederland.",
    )

    [row] = _gate([source])

    assert candidate_eligibility_of(row)["reason"] == REASON_NO_TYPE
    assert candidate_eligibility_of(row)["eligible"] is False
    assert admission_of(row) == {}
