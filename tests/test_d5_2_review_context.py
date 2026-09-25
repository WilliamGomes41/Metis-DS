"""D5.2 relation-aware ReviewContext regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy

from src.knowledge_relations_v1 import build_knowledge_relation
from src.operations_console_app import (
    _knowledge_relation_review_block,
    _review_context_block,
)
from src.review_context_v1 import (
    AUTHORITY_CONFIRMED,
    AUTHORITY_PROPOSED,
    DIRECTION_INCOMING,
    DIRECTION_OUTGOING,
    RESOLUTION_CURRENT,
    RESOLUTION_MISSING,
    RESOLUTION_VERSION_MISMATCH,
    review_context,
)


def _obj(
    object_id: str,
    object_type: str,
    *,
    version: str = "1.0",
    status: str = "needs_review",
    gate: str = "allowed",
    second_required: bool = False,
    second_status: str = "not_required",
    text: str | None = None,
) -> dict:
    return {
        "object_id": object_id,
        "object_version": version,
        "object_type": object_type,
        "confirmed_object_type": object_type,
        "content": {"clean_text": text or f"Tekst van {object_id}."},
        "metadata": {
            "admission": {
                "gate_result": gate,
                "section_path": ["Inhoud"],
            }
        },
        "governance": {
            "validation_status": status,
            "second_review": {
                "required": second_required,
                "status": second_status,
            },
        },
        "risk": {
            "level": "normal",
            "requires_second_review": second_required,
        },
        "uncertainty": {"has_uncertainty": False, "items": []},
        "provenance": {"canonical_object_hash": f"hash-{object_id}-{version}"},
    }


def _edge(source: dict, relation_type: str, target: dict) -> dict:
    return build_knowledge_relation(
        source_object_id=source["object_id"],
        source_object_version=source["object_version"],
        relation_type=relation_type,
        target_object_id=target["object_id"],
        target_object_version=target["object_version"],
    )


def test_first_review_projects_confirmed_and_proposed_one_hop_context() -> None:
    rec = _obj("rec", "recommendation")
    condition = _obj("condition", "condition")
    explanation = _obj("explanation", "explanation")

    confirmed = _edge(rec, "applies_if", condition)
    proposed = _edge(rec, "supported_by", explanation)
    rec["confirmed_knowledge_relations"] = [confirmed]
    rec["proposed_knowledge_relations"] = [proposed]

    context = review_context(
        rec,
        objects=[rec, condition, explanation],
        review_path="richtlijn",
    )

    assert context["stage"] == "first_review"
    assert [(row["authority"], row["relation_type"]) for row in context["links"]] == [
        (AUTHORITY_CONFIRMED, "applies_if"),
        (AUTHORITY_PROPOSED, "supported_by"),
    ]
    assert all(row["direction"] == DIRECTION_OUTGOING for row in context["links"])
    assert all(row["target"]["resolution"] == RESOLUTION_CURRENT for row in context["links"])
    assert context["issues"] == []


def test_second_review_projects_confirmed_only() -> None:
    rec = _obj(
        "rec",
        "recommendation",
        status="approved",
        second_required=True,
        second_status="pending",
    )
    condition = _obj("condition", "condition")
    explanation = _obj("explanation", "explanation")
    rec["confirmed_knowledge_relations"] = [_edge(rec, "applies_if", condition)]
    rec["proposed_knowledge_relations"] = [_edge(rec, "supported_by", explanation)]

    context = review_context(
        rec,
        objects=[rec, condition, explanation],
        review_path="richtlijn",
    )

    assert context["stage"] == "second_review"
    assert len(context["links"]) == 1
    assert context["links"][0]["authority"] == AUTHORITY_CONFIRMED
    assert context["links"][0]["target"]["object_id"] == "condition"


def test_incoming_context_shows_multiple_sources_without_reversing_edges() -> None:
    condition = _obj("condition", "condition")
    rec_a = _obj("rec-a", "recommendation")
    rec_b = _obj("rec-b", "recommendation")
    rec_a["confirmed_knowledge_relations"] = [_edge(rec_a, "applies_if", condition)]
    rec_b["confirmed_knowledge_relations"] = [_edge(rec_b, "applies_if", condition)]

    context = review_context(
        condition,
        objects=[condition, rec_a, rec_b],
        review_path="richtlijn",
    )

    incoming = [row for row in context["links"] if row["direction"] == DIRECTION_INCOMING]
    assert {row["source"]["object_id"] for row in incoming} == {"rec-a", "rec-b"}
    assert {row["target"]["object_id"] for row in incoming} == {"condition"}
    assert all(row["relation_type"] == "applies_if" for row in incoming)


def test_exact_duplicate_confirmed_edge_suppresses_proposed_duplicate() -> None:
    rec = _obj("rec", "recommendation")
    condition = _obj("condition", "condition")
    relation = _edge(rec, "applies_if", condition)
    rec["confirmed_knowledge_relations"] = [deepcopy(relation)]
    rec["proposed_knowledge_relations"] = [deepcopy(relation)]

    context = review_context(
        rec,
        objects=[rec, condition],
        review_path="richtlijn",
    )

    assert len(context["links"]) == 1
    assert context["links"][0]["authority"] == AUTHORITY_CONFIRMED


def test_blocked_proposal_legacy_and_structural_relations_are_not_context_authority() -> None:
    rec = _obj("rec", "recommendation", gate="blocked")
    condition = _obj("condition", "condition")
    heading = _obj("heading", "heading")

    rec["proposed_knowledge_relations"] = [_edge(rec, "applies_if", condition)]
    rec["confirmed_relations"] = [
        {
            "relation_type": "supported_by",
            "target_object_id": condition["object_id"],
            "target_object_version": condition["object_version"],
            "confirmed": True,
        }
    ]
    rec["confirmed_knowledge_relations"] = [_edge(rec, "child", heading)]

    context = review_context(
        rec,
        objects=[rec, condition, heading],
        review_path="richtlijn",
        stage="first_review",
    )

    assert context["links"] == []


def test_target_version_mismatch_and_missing_are_explicit_without_rebinding() -> None:
    rec = _obj("rec", "recommendation")
    condition_v1 = _obj("condition", "condition", version="1.0")
    missing = _obj("missing", "explanation", version="1.0")
    rec["confirmed_knowledge_relations"] = [
        _edge(rec, "applies_if", condition_v1),
        _edge(rec, "supported_by", missing),
    ]

    condition_v2 = _obj("condition", "condition", version="2.0")
    context = review_context(
        rec,
        objects=[rec, condition_v2],
        review_path="richtlijn",
    )

    by_target = {row["target"]["object_id"]: row for row in context["links"]}
    stale = by_target["condition"]["target"]
    absent = by_target["missing"]["target"]

    assert stale["expected_version"] == "1.0"
    assert stale["current_version"] == "2.0"
    assert stale["resolution"] == RESOLUTION_VERSION_MISMATCH
    assert absent["expected_version"] == "1.0"
    assert absent["resolution"] == RESOLUTION_MISSING
    assert {row["resolution"] for row in context["issues"]} == {
        RESOLUTION_VERSION_MISMATCH,
        RESOLUTION_MISSING,
    }


def test_related_review_duty_is_observation_not_shared_approval() -> None:
    rec = _obj("rec", "recommendation")
    condition = _obj("condition", "condition")
    rec["confirmed_knowledge_relations"] = [_edge(rec, "applies_if", condition)]

    context = review_context(
        rec,
        objects=[rec, condition],
        review_path="richtlijn",
    )

    [link] = context["links"]
    assert link["target"]["review_duty"]["object_id"] == "condition"
    assert link["target"]["review_duty"]["stage"] == "first_review"


def test_confirmed_relation_reuses_semantic_proposal_evidence_after_relation_id_rebind() -> None:
    rec = _obj("rec", "recommendation", version="2.0")
    condition = _obj("condition", "condition")
    confirmed = _edge(rec, "applies_if", condition)
    rec["confirmed_knowledge_relations"] = [confirmed]
    rec["metadata"]["knowledge_relation_evidence"] = {
        "version": "knowledge-relation-evidence-v1",
        "relations": [
            {
                "relation_id": "rel-" + "1" * 64,
                "relation_type": "applies_if",
                "target_object_id": condition["object_id"],
                "target_object_version": condition["object_version"],
                "source_spans": [
                    {
                        "block_id": "source",
                        "start": 0,
                        "end": 3,
                        "source_fragment_ids": ["f1"],
                    }
                ],
                "target_spans": [
                    {
                        "block_id": "target",
                        "start": 0,
                        "end": 3,
                        "source_fragment_ids": ["f2"],
                    }
                ],
                "evidence_spans": [
                    {
                        "block_id": "evidence",
                        "start": 0,
                        "end": 3,
                        "source_fragment_ids": ["f2"],
                    }
                ],
            }
        ],
    }

    context = review_context(
        rec,
        objects=[rec, condition],
        review_path="richtlijn",
    )

    [link] = context["links"]
    assert link["relation_id"] == confirmed["relation_id"]
    assert link["evidence"]["relation_id"] != confirmed["relation_id"]
    assert link["evidence"]["target_object_id"] == condition["object_id"]


def test_malformed_new_format_relation_set_fails_closed() -> None:
    rec = _obj("rec", "recommendation")
    condition = _obj("condition", "condition")
    bad = _edge(rec, "applies_if", condition)
    bad["relation_id"] = "rel-" + "0" * 64
    rec["confirmed_knowledge_relations"] = [bad]

    context = review_context(
        rec,
        objects=[rec, condition],
        review_path="richtlijn",
    )

    assert context["links"] == []


def test_review_context_ui_marks_stale_version_and_does_not_change_relation_choice() -> None:
    rec = _obj("rec", "recommendation")
    condition_v1 = _obj("condition", "condition", version="1.0")
    relation = _edge(rec, "applies_if", condition_v1)
    rec["proposed_knowledge_relations"] = [relation]
    condition_v2 = _obj("condition", "condition", version="2.0", text="Nieuwe voorwaarde.")

    context_html = _review_context_block(
        rec,
        [rec, condition_v2],
        snapshot_id="snap-1",
        review_path="richtlijn",
    )
    review_html = _knowledge_relation_review_block(
        rec,
        [rec, condition_v2],
        review_path="richtlijn",
    )

    assert "Samenhang met andere kennisobjecten" in context_html
    assert "verwacht versie 1.0; actuele versie 2.0" in context_html
    assert 'data-relation-resolution="version_mismatch"' in context_html
    assert "Deze relatie is niet automatisch aangepast." in review_html
    assert relation["target_object_version"] == "1.0"
    assert relation["target_object_id"] in review_html
