"""T12: one readiness result over disjoint curation and technical gates.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.publication_readiness_v1 import (
    PublicationReadinessMixin,
    REVIEW_DISPOSITION_INCONSISTENT,
    source_passage_closure,
)
from src.review_disposition_v1 import definitive_review_disposition


def _source_object(
    object_id: str,
    *,
    register_status: str,
    review_status: str,
    register_source: str = "review",
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": "explanation",
        "proposed_object_type": "explanation",
        "metadata": {
            "passage_register": {
                "status": register_status,
                "source": register_source,
            }
        },
        "governance": {"validation_status": review_status},
    }


class _ExistingGate:
    def __init__(self, result: dict[str, Any]) -> None:
        self._result = result

    def snapshot_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        return []

    def technical_publication_readiness(
        self, *, snapshot_id: str, **_context: Any
    ) -> dict[str, Any]:
        _ = snapshot_id
        return deepcopy(self._result)


class _Subject(PublicationReadinessMixin, _ExistingGate):
    pass


def _readiness(base: dict[str, Any]) -> dict[str, Any]:
    return _Subject(base).publication_readiness("snapshot")


def test_curation_green_technical_blocker_stays_technical() -> None:
    base = {
        "publish_allowed": False,
        "blockers": ["g2_source_store_unavailable", "prepublication_schema_invalid"],
        "publishable_object_count": 1,
    }

    considered = _readiness(base)

    assert considered["curation_ready"] is True
    assert considered["curation_blockers"] == []
    assert considered["technical_ready"] is False
    assert considered["technical_blockers"] == [
        "g2_source_store_unavailable",
        "prepublication_schema_invalid",
    ]
    assert considered["blockers"] == base["blockers"]


def test_curation_and_technical_green_make_publication_ready() -> None:
    considered = _readiness(
        {
            "publish_allowed": True,
            "blockers": [],
            "publishable_object_count": 1,
        }
    )

    assert considered["technical_ready"] is True
    assert considered["curation_ready"] is True
    assert considered["publication_ready"] is True
    assert considered["publish_allowed"] is True


def test_disposition_conflict_is_curation_not_technical() -> None:
    considered = _readiness(
        {
            "publish_allowed": False,
            "blockers": [REVIEW_DISPOSITION_INCONSISTENT],
            "publishable_object_count": 1,
            "disposition_conflict_object_ids": ["approved"],
        }
    )

    assert considered["technical_ready"] is True
    assert considered["technical_blockers"] == []
    assert considered["curation_ready"] is False
    assert considered["curation_blockers"] == [REVIEW_DISPOSITION_INCONSISTENT]


def test_human_review_codes_have_one_curation_category() -> None:
    considered = _readiness(
        {
            "publish_allowed": False,
            "blockers": [
                "four_eyes_required",
                "required_policy_review_missing",
                "decision_graph_review_incomplete",
                REVIEW_DISPOSITION_INCONSISTENT,
            ],
            "publishable_object_count": 1,
        }
    )

    assert considered["technical_blockers"] == []
    assert considered["curation_blockers"] == [
        "four_eyes_required",
        "required_policy_review_missing",
        "decision_graph_review_incomplete",
        REVIEW_DISPOSITION_INCONSISTENT,
    ]
    assert set(considered["curation_blockers"]).isdisjoint(
        considered["technical_blockers"]
    )


def test_decision_graph_integrity_stays_technical() -> None:
    considered = _readiness(
        {
            "publish_allowed": False,
            "blockers": ["decision_graph_endpoint_stale"],
            "publishable_object_count": 1,
        }
    )

    assert considered["technical_blockers"] == ["decision_graph_endpoint_stale"]
    assert considered["curation_blockers"] == []


def test_already_published_remains_lifecycle_technical_blocker() -> None:
    considered = _readiness(
        {
            "publish_allowed": False,
            "blockers": ["already_published"],
            "publishable_object_count": 0,
            "state": "published",
        }
    )

    assert considered["curation_ready"] is True
    assert considered["technical_ready"] is False
    assert considered["technical_blockers"] == ["already_published"]


def test_deferred_review_written_non_candidate_disposition_stays_open() -> None:
    deferred = _source_object(
        "deferred-context",
        register_status="used_as_context",
        review_status="needs_review",
    )
    deferred["metadata"]["review_passage"] = {
        "suitability": "mist_context",
        "eindoordeel": "later_beoordelen",
    }

    disposition = definitive_review_disposition(deferred)
    closure = source_passage_closure([deferred])

    assert disposition["state"] == "open"
    assert disposition["final"] is False
    assert closure["source_passage_review_complete"] is False
    assert closure["unresolved_source_passage_ids"] == ["deferred-context"]


def test_terminal_review_written_non_candidate_disposition_is_final() -> None:
    reviewed_context = _source_object(
        "reviewed-context",
        register_status="used_as_context",
        review_status="approved",
    )

    disposition = definitive_review_disposition(reviewed_context)

    assert disposition["state"] == "final"
    assert disposition["final"] is True
    assert disposition["outcome"] == "used_as_context"
