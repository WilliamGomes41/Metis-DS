"""Section-derived review priority is presentation only.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, ordinary_review_queue
from src.object_taxonomy_v1 import (
    REVIEW_PRIORITY_FOCUS,
    REVIEW_PRIORITY_REGULAR,
    REVIEW_PRIORITY_SECONDARY,
    review_priority_for_path,
)
from src.operations_console_v1 import slow_review_duty
from src.proportionate_review_v1 import (
    normal_risk_batch_queue,
    regular_individual_review_queue,
    regular_review_queue,
)
from src.source_occurrence_authority_v1 import prefer_authoritative_exact_occurrences


def _obj(
    object_id: str,
    section_path: list[str],
    *,
    proposed_type: str = "recommendation",
    gate: str = GATE_ALLOWED,
    register_status: str = "selected_as_candidate",
) -> dict:
    return {
        "object_id": object_id,
        "object_type": "unclassified",
        "proposed_object_type": proposed_type,
        "structure": {"section_path": list(section_path)},
        "metadata": {
            "admission": {
                "gate_result": gate,
                "section_path": list(section_path),
            },
            "passage_register": {
                "status": register_status,
                "source": "extract",
            },
        },
        "governance": {"validation_status": "needs_review"},
        "content": {"clean_text": f"Passage {object_id}."},
    }


def _ids(rows: list[dict]) -> list[str]:
    return [str(row["object_id"]) for row in rows]


def test_review_priority_model_is_closed_and_summary_container_wins() -> None:
    assert review_priority_for_path(["Richtlijn", "3 Aanbevelingen"]) == REVIEW_PRIORITY_FOCUS
    assert review_priority_for_path(["Richtlijn", "Conclusies"]) == REVIEW_PRIORITY_FOCUS
    assert review_priority_for_path(["Richtlijn", "Behandeling"]) == REVIEW_PRIORITY_REGULAR
    assert review_priority_for_path(["Richtlijn", "Samenvatting"]) == REVIEW_PRIORITY_SECONDARY
    assert (
        review_priority_for_path(["Richtlijn", "Samenvatting", "Aanbevelingen"])
        == REVIEW_PRIORITY_SECONDARY
    )


def test_priority_queues_are_focus_regular_secondary_and_stable_within_tier() -> None:
    rows = [
        _obj("summary-1", ["Richtlijn", "Samenvatting"]),
        _obj("regular-1", ["Richtlijn", "Behandeling"]),
        _obj("focus-1", ["Richtlijn", "Aanbevelingen"]),
        _obj("focus-2", ["Richtlijn", "Conclusies"]),
        _obj("regular-2", ["Richtlijn", "Diagnostiek"]),
        _obj("summary-2", ["Richtlijn", "Kernpunten"]),
    ]
    expected = [
        "focus-1",
        "focus-2",
        "regular-1",
        "regular-2",
        "summary-1",
        "summary-2",
    ]

    assert _ids(slow_review_duty(rows, review_path="richtlijn")) == expected
    assert _ids(ordinary_review_queue(rows, review_path="richtlijn")) == expected
    assert _ids(regular_review_queue(rows, review_path="richtlijn")) == expected


def test_regular_individual_queue_uses_same_priority_without_changing_state() -> None:
    rows = [
        _obj(
            "summary",
            ["Richtlijn", "Samenvatting"],
            proposed_type="unclassified",
        ),
        _obj(
            "regular",
            ["Richtlijn", "Achtergrond"],
            proposed_type="unclassified",
        ),
        _obj(
            "focus",
            ["Richtlijn", "Conclusies"],
            proposed_type="unclassified",
        ),
    ]
    before = deepcopy(rows)

    queue = regular_individual_review_queue(rows, review_path="richtlijn")

    assert _ids(queue) == ["focus", "regular", "summary"]
    assert rows == before
    assert rows[0]["metadata"]["passage_register"]["status"] == "selected_as_candidate"


def test_normal_risk_batches_follow_section_priority() -> None:
    rows = [
        _obj("summary", ["Richtlijn", "Samenvatting"], proposed_type="definition"),
        _obj("regular", ["Richtlijn", "Behandeling"], proposed_type="definition"),
        _obj("focus", ["Richtlijn", "Conclusies"], proposed_type="definition"),
    ]

    assert _ids(normal_risk_batch_queue(rows, review_path="richtlijn")) == [
        "focus",
        "regular",
        "summary",
    ]


def test_priority_never_opens_admission_gate() -> None:
    blocked_focus = _obj(
        "blocked-focus",
        ["Richtlijn", "Aanbevelingen"],
        gate=GATE_BLOCKED,
    )
    allowed_summary = _obj(
        "allowed-summary",
        ["Richtlijn", "Samenvatting"],
    )

    queue = ordinary_review_queue(
        [allowed_summary, blocked_focus],
        review_path="richtlijn",
    )

    assert _ids(queue) == ["allowed-summary"]
    assert blocked_focus["metadata"]["admission"]["gate_result"] == GATE_BLOCKED


def test_exact_duplicate_source_authority_is_unchanged_by_review_priority() -> None:
    summary = {
        "object_id": "summary",
        "object_type": "unclassified",
        "clean_text": "Bespreek eenzaamheid met de oudere.",
        "source_fragment_ids": ["summary-fragment"],
        "section_path": ["Richtlijn", "Samenvatting", "Aanbevelingen"],
    }
    primary = {
        "object_id": "primary",
        "object_type": "unclassified",
        "clean_text": "Bespreek eenzaamheid met de oudere.",
        "source_fragment_ids": ["primary-fragment"],
        "section_path": ["Richtlijn", "3 Aanbevelingen"],
    }

    rows = prefer_authoritative_exact_occurrences([summary, primary])

    assert len(rows) == 1
    assert rows[0]["object_id"] == "primary"
    assert rows[0]["source_fragment_ids"] == ["primary-fragment"]
    assert rows[0]["metadata"]["source_occurrence_authority"]["principal_section_role"] == "primary"
