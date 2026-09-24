"""D2a processing-diagnostics contract.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy

from src.domain_dimensions_v1 import processing_issue_objects
from src.operations_console_app import _processing_diagnostics_html
from src.processing_diagnostics_v1 import (
    DEPENDENCY_RESOLUTION,
    SEMANTIC_CONTRACT,
    SOURCE_BINDING,
    UNCLASSIFIED,
    UNIT_COMPLETENESS,
    processing_diagnostics,
    processing_issue_family,
)


def _obj(
    object_id: str,
    *,
    gate_result: str = "blocked",
    reasons: list[str] | None = None,
    proposed_type: str = "explanation",
    section_role: str = "regular",
    formation_strategy: str = "semantic",
    selection_origin: str = "proposal_selected",
) -> dict:
    metadata: dict = {
        "admission": {
            "gate_result": gate_result,
            "reason_codes": list(reasons or []),
            "proposed_type": proposed_type,
            "section_role": section_role,
            "section_path": ["Richtlijn", "Behandeling"],
        },
        "passage_formation": {
            "strategy": formation_strategy,
        },
        "passage_register": {
            "status": "not_yet_assessed",
            "source": "extract",
        },
    }
    if selection_origin:
        metadata["semantic_passage"] = {
            "selection_origin": selection_origin,
            "source_bound": True,
        }
    return {
        "object_id": object_id,
        "object_type": "unclassified",
        "proposed_object_type": proposed_type,
        "metadata": metadata,
        "structure": {"section_path": ["Richtlijn", "Behandeling"]},
        "governance": {"validation_status": "needs_review"},
        "content": {"clean_text": f"Passage {object_id}."},
    }


def test_candidate_count_is_distinct_from_issue_occurrence_count() -> None:
    objects = [
        _obj(
            "a",
            reasons=["incomplete_sentence", "subject_missing", "source_fidelity_failure"],
        ),
        _obj("b", reasons=["comparison_target_missing"]),
    ]

    result = processing_diagnostics(objects)

    assert result["blocked_candidate_count"] == 2
    assert result["issue_occurrence_count"] == 4
    assert result["by_family"][UNIT_COMPLETENESS] == {
        "candidate_count": 1,
        "issue_occurrence_count": 2,
    }
    assert result["by_family"][SOURCE_BINDING] == {
        "candidate_count": 1,
        "issue_occurrence_count": 1,
    }
    assert result["by_family"][DEPENDENCY_RESOLUTION] == {
        "candidate_count": 1,
        "issue_occurrence_count": 1,
    }


def test_one_candidate_can_contribute_to_multiple_families_without_primary_reason() -> None:
    objects = [
        _obj(
            "a",
            reasons=[
                "source_fidelity_failure",
                "no_independent_claim",
                "recommendation_evidence_missing",
            ],
            proposed_type="recommendation",
        )
    ]

    result = processing_diagnostics(objects)

    assert result["blocked_candidate_count"] == 1
    assert result["by_family"][SOURCE_BINDING]["candidate_count"] == 1
    assert result["by_family"][UNIT_COMPLETENESS]["candidate_count"] == 1
    assert result["by_family"][SEMANTIC_CONTRACT]["candidate_count"] == 1
    assert "primary_reason" not in result


def test_raw_reason_codes_are_preserved_and_unknown_codes_fail_visible() -> None:
    raw_unknown = "future_parser_reason_v2"
    objects = [
        _obj(
            "a",
            reasons=["type_contract_incomplete", raw_unknown],
        )
    ]

    result = processing_diagnostics(objects)

    assert set(result["by_reason_code"]) == {
        "type_contract_incomplete",
        raw_unknown,
    }
    assert result["unknown_reason_codes"] == [raw_unknown]
    assert result["by_family"][UNCLASSIFIED] == {
        "candidate_count": 1,
        "issue_occurrence_count": 1,
    }
    assert processing_issue_family(raw_unknown) == UNCLASSIFIED


def test_blocked_without_reason_is_an_anomaly_not_healthy() -> None:
    result = processing_diagnostics([_obj("missing", reasons=[])])

    assert result["blocked_candidate_count"] == 1
    assert result["issue_occurrence_count"] == 0
    assert result["blocked_without_reason_count"] == 1
    assert result["blocked_without_reason_ids"] == ["missing"]
    assert result["by_family"][UNCLASSIFIED]["candidate_count"] == 1


def test_allowed_candidates_are_excluded_from_processing_diagnostics() -> None:
    allowed = _obj(
        "allowed",
        gate_result="allowed",
        reasons=["incomplete_sentence"],
    )
    blocked = _obj("blocked", reasons=["incomplete_sentence"])

    result = processing_diagnostics([allowed, blocked])

    assert result["blocked_candidate_count"] == 1
    assert result["issue_occurrence_count"] == 1
    assert [row["object_id"] for row in processing_issue_objects([allowed, blocked])] == [
        "blocked"
    ]


def test_breakdowns_use_existing_processing_context_deterministically() -> None:
    objects = [
        _obj(
            "a",
            reasons=["incomplete_sentence"],
            proposed_type="recommendation",
            section_role="primary",
            formation_strategy="semantic",
            selection_origin="proposal_selected",
        ),
        _obj(
            "b",
            reasons=["type_contract_incomplete"],
            proposed_type="explanation",
            section_role="secondary",
            formation_strategy="semantic",
            selection_origin="coverage_remainder",
        ),
        _obj(
            "c",
            reasons=["locator_invalid"],
            proposed_type="condition",
            section_role="regular",
            formation_strategy="deterministic",
            selection_origin="",
        ),
    ]

    result = processing_diagnostics(objects)

    assert result["by_proposed_type"] == {
        "condition": 1,
        "explanation": 1,
        "recommendation": 1,
    }
    assert result["by_section_role"] == {
        "primary": 1,
        "regular": 1,
        "secondary": 1,
    }
    assert result["by_formation_strategy"] == {
        "deterministic": 1,
        "semantic": 2,
    }
    assert result["by_selection_origin"] == {
        "coverage_remainder": 1,
        "not_applicable": 1,
        "proposal_selected": 1,
    }


def test_diagnostics_are_pure_and_do_not_change_blocked_authority() -> None:
    objects = [
        _obj("a", reasons=["incomplete_sentence"]),
        _obj("b", reasons=["source_fidelity_failure"]),
    ]
    before = deepcopy(objects)
    blocked_before = [row["object_id"] for row in processing_issue_objects(objects)]

    first = processing_diagnostics(objects)
    second = processing_diagnostics(objects)

    assert first == second
    assert objects == before
    assert [row["object_id"] for row in processing_issue_objects(objects)] == blocked_before


def test_technical_control_copy_distinguishes_passages_signals_and_root_cause() -> None:
    objects = [
        _obj(
            "a",
            reasons=["incomplete_sentence", "source_fidelity_failure"],
            proposed_type="recommendation",
        ),
        _obj("b", reasons=["future_parser_reason_v2"]),
    ]

    html = _processing_diagnostics_html(objects)

    assert "<b>2</b> passages hebben samen <b>3</b> technische signalen" in html
    assert "ze bewijzen niet automatisch de onderliggende root cause" in html
    assert "geen inhoudelijke afwijzing door een reviewer" in html
    assert "incomplete_sentence" in html
    assert "source_fidelity_failure" in html
    assert "future_parser_reason_v2" in html
    assert "Niet ingedeelde reason codes" in html
