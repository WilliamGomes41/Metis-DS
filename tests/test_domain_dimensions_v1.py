"""Domain-first contract for the five orthogonal Review dimensions.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
"""
from __future__ import annotations

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, blocked_audit_lane
from src.domain_dimensions_v1 import (
    knowledge_candidate_dimension,
    knowledge_relations_dimension,
    processing_issue_dimension,
    processing_issue_objects,
    project_review_domain_dimensions,
    review_decision_dimension,
    source_structure_dimension,
)
from src.proportionate_review_v1 import normal_risk_batch_counts


def _obj(
    object_id: str,
    *,
    object_type: str = "unclassified",
    proposed_type: str = "explanation",
    gate_result: str | None = GATE_ALLOWED,
    reason_codes: list[str] | None = None,
    section_path: list[str] | None = None,
    register_status: str = "selected_as_candidate",
    register_source: str = "extract",
    validation_status: str = "needs_review",
) -> dict:
    metadata: dict = {
        "passage_register": {
            "status": register_status,
            "source": register_source,
            "reason_codes": list(reason_codes or []),
        }
    }
    if gate_result is not None:
        metadata["admission"] = {
            "gate_result": gate_result,
            "reason_codes": list(reason_codes or []),
            "proposed_type": proposed_type,
            "section_path": section_path or ["Richtlijn", "Behandeling"],
        }
    return {
        "object_id": object_id,
        "object_type": object_type,
        "proposed_object_type": proposed_type,
        "metadata": metadata,
        "structure": {"section_path": section_path or ["Richtlijn", "Behandeling"]},
        "governance": {"validation_status": validation_status},
        "content": {"clean_text": f"Passage {object_id}."},
    }


def test_blocked_candidate_is_candidate_and_processing_issue_not_rejection() -> None:
    row = _obj(
        "blocked",
        proposed_type="recommendation",
        gate_result=GATE_BLOCKED,
        reason_codes=["recommendation_evidence_missing", "comparison_target_missing"],
        register_status="not_yet_assessed",
    )

    projected = project_review_domain_dimensions(row)

    assert projected["knowledge_candidate"] == {
        "is_candidate": True,
        "proposed_type": "recommendation",
        "confirmed_type": "",
        "stored_type": "",
    }
    assert projected["processing_issue"] == {
        "has_issue": True,
        "gate_result": GATE_BLOCKED,
        "reason_codes": [
            "recommendation_evidence_missing",
            "comparison_target_missing",
        ],
    }
    assert projected["review_decision"]["has_human_decision"] is False
    assert projected["review_decision"]["validation_status"] == ""
    assert projected["review_decision"]["passage_disposition"] == ""


def test_heading_is_source_structure_not_knowledge_candidate_or_processing_issue() -> None:
    row = _obj(
        "heading",
        object_type="heading",
        proposed_type="heading",
        gate_result=None,
        section_path=["Richtlijn", "2 Aanbevelingen"],
        register_status="not_yet_assessed",
    )

    assert source_structure_dimension(row) == {
        "kind": "heading",
        "section_path": ["Richtlijn", "2 Aanbevelingen"],
        "section_role": "primary",
    }
    assert knowledge_candidate_dimension(row)["is_candidate"] is False
    assert processing_issue_dimension(row)["has_issue"] is False


def test_allowed_candidate_has_candidate_dimension_without_processing_issue() -> None:
    row = _obj(
        "allowed",
        proposed_type="condition",
        gate_result=GATE_ALLOWED,
    )

    candidate = knowledge_candidate_dimension(row)
    issue = processing_issue_dimension(row)

    assert candidate["is_candidate"] is True
    assert candidate["proposed_type"] == "condition"
    assert issue == {
        "has_issue": False,
        "gate_result": GATE_ALLOWED,
        "reason_codes": [],
    }


def test_relation_dimension_preserves_multiple_edges_and_confirmation_separately() -> None:
    row = _obj("relations")
    row["relations"] = [
        {
            "relation_type": "supported_by",
            "target_object_id": "support-a",
            "confirmed": False,
        },
        {
            "relation_type": "supported_by",
            "target_object_id": "support-b",
            "confirmed": True,
        },
        {
            "relation_type": "applies_if",
            "target_object_id": "condition-c",
            "confirmed": False,
        },
    ]
    row["confirmed_relations"] = [
        {
            "relation_type": "supported_by",
            "target_object_id": "support-b",
            "confirmed": True,
        }
    ]

    relations = knowledge_relations_dimension(row)

    assert [item["target_object_id"] for item in relations["proposed"]] == [
        "support-a",
        "support-b",
        "condition-c",
    ]
    assert relations["confirmed"] == [
        {
            "relation_type": "supported_by",
            "target_object_id": "support-b",
            "confirmed": True,
        }
    ]


def test_extract_register_state_is_not_mistaken_for_human_review_decision() -> None:
    extract_row = _obj(
        "extract",
        register_status="not_yet_assessed",
        register_source="extract",
        validation_status="needs_review",
    )
    human_row = _obj(
        "human",
        register_status="excluded_with_reason",
        register_source="review",
        validation_status="rejected",
    )
    human_row["metadata"]["passage_register"]["suitability"] = "geen_kenniseenheid"

    assert review_decision_dimension(extract_row) == {
        "has_human_decision": False,
        "validation_status": "",
        "passage_disposition": "",
        "suitability": "",
    }
    assert review_decision_dimension(human_row) == {
        "has_human_decision": True,
        "validation_status": "rejected",
        "passage_disposition": "excluded_with_reason",
        "suitability": "geen_kenniseenheid",
    }


def test_same_section_batch_is_review_strategy_not_semantic_relation() -> None:
    first = _obj("definition-a", proposed_type="definition")
    second = _obj("definition-b", proposed_type="definition")
    objects = [first, second]

    passages, batches = normal_risk_batch_counts(objects, review_path="richtlijn")

    assert (passages, batches) == (2, 1)
    assert knowledge_relations_dimension(first) == {"proposed": [], "confirmed": []}
    assert knowledge_relations_dimension(second) == {"proposed": [], "confirmed": []}


def test_processing_projection_matches_existing_blocked_authority() -> None:
    objects = [
        _obj("allowed", gate_result=GATE_ALLOWED),
        _obj(
            "blocked-a",
            gate_result=GATE_BLOCKED,
            reason_codes=["subject_missing"],
            register_status="not_yet_assessed",
        ),
        _obj(
            "blocked-b",
            gate_result=GATE_BLOCKED,
            reason_codes=["source_fidelity_failure"],
            register_status="not_yet_assessed",
        ),
    ]

    assert [row["object_id"] for row in processing_issue_objects(objects)] == [
        row["object_id"] for row in blocked_audit_lane(objects)
    ]
