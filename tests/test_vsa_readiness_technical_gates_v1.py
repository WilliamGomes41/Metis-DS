"""VSA Slice 4: one publication-readiness result over curation + technical gates.

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
    REVIEW_WORK_INCOMPLETE,
    SOURCE_PASSAGE_REVIEW_INCOMPLETE,
    source_passage_closure,
)
from src.review_disposition_v1 import definitive_review_disposition


def _object(
    object_id: str,
    *,
    register_status: str = "selected_as_candidate",
    review_status: str = "approved",
    register_source: str = "extract",
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
    def __init__(self, objects: list[dict[str, Any]], result: dict[str, Any]) -> None:
        self._objects = objects
        self._result = result

    def snapshot_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        return self._objects

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        _ = actor_id, snapshot_id
        return deepcopy(self._result)


class _Subject(PublicationReadinessMixin, _ExistingGate):
    pass


def _technical_pass() -> dict[str, Any]:
    return {
        "publish_allowed": True,
        "blockers": [],
        "publishable_object_count": 1,
    }


def test_curation_open_technical_green_blocks_publication() -> None:
    open_candidate = _object(
        "candidate",
        review_status="needs_review",
    )

    considered = _Subject([open_candidate], _technical_pass()).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert considered["technical_ready"] is True
    assert considered["technical_blockers"] == []
    assert considered["curation_ready"] is False
    assert considered["curation_blockers"] == [
        REVIEW_WORK_INCOMPLETE,
        SOURCE_PASSAGE_REVIEW_INCOMPLETE,
    ]
    assert considered["publication_ready"] is False
    assert considered["publish_allowed"] is False


def test_curation_green_technical_blocker_stays_technical() -> None:
    approved = _object("approved")
    base = {
        "publish_allowed": False,
        "blockers": ["g2_source_store_unavailable", "prepublication_schema_invalid"],
        "publishable_object_count": 1,
    }

    considered = _Subject([approved], base).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert considered["curation_ready"] is True
    assert considered["curation_blockers"] == []
    assert considered["technical_ready"] is False
    assert considered["technical_blockers"] == [
        "g2_source_store_unavailable",
        "prepublication_schema_invalid",
    ]
    assert considered["blockers"] == base["blockers"]
    assert considered["publication_ready"] is False
    assert considered["publish_allowed"] is False


def test_curation_and_technical_green_make_publication_ready() -> None:
    considered = _Subject([_object("approved")], _technical_pass()).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert considered["technical_ready"] is True
    assert considered["curation_ready"] is True
    assert considered["publication_ready"] is True
    assert considered["publish_allowed"] is True
    assert considered["technical_blockers"] == []
    assert considered["curation_blockers"] == []


def test_disposition_conflict_is_curation_not_technical() -> None:
    base = {
        "publish_allowed": False,
        "blockers": [REVIEW_DISPOSITION_INCONSISTENT],
        "publishable_object_count": 1,
        "disposition_conflict_object_ids": ["approved"],
    }

    considered = _Subject([_object("approved")], base).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert considered["technical_ready"] is True
    assert considered["technical_blockers"] == []
    assert considered["curation_ready"] is False
    assert considered["curation_blockers"] == [REVIEW_DISPOSITION_INCONSISTENT]
    assert considered["publication_ready"] is False
    assert considered["publish_allowed"] is False


def test_mixed_blockers_keep_order_and_category() -> None:
    open_candidate = _object("candidate", review_status="needs_review")
    base = {
        "publish_allowed": False,
        "blockers": ["four_eyes_required", REVIEW_DISPOSITION_INCONSISTENT],
        "publishable_object_count": 1,
        "disposition_conflict_object_ids": ["candidate"],
    }

    considered = _Subject([open_candidate], base).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert considered["technical_blockers"] == ["four_eyes_required"]
    assert considered["curation_blockers"] == [
        REVIEW_DISPOSITION_INCONSISTENT,
        REVIEW_WORK_INCOMPLETE,
        SOURCE_PASSAGE_REVIEW_INCOMPLETE,
    ]
    assert considered["blockers"] == [
        "four_eyes_required",
        REVIEW_DISPOSITION_INCONSISTENT,
        REVIEW_WORK_INCOMPLETE,
        SOURCE_PASSAGE_REVIEW_INCOMPLETE,
    ]


def test_already_published_remains_lifecycle_technical_blocker() -> None:
    base = {
        "publish_allowed": False,
        "blockers": ["already_published"],
        "publishable_object_count": 0,
        "state": "published",
    }

    considered = _Subject([_object("approved")], base).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert considered["curation_ready"] is True
    assert considered["technical_ready"] is False
    assert considered["technical_blockers"] == ["already_published"]
    assert considered["curation_blockers"] == []
    assert considered["publication_ready"] is False


def test_deferred_review_written_non_candidate_disposition_stays_open() -> None:
    deferred = _object(
        "deferred-context",
        register_status="used_as_context",
        review_status="needs_review",
        register_source="review",
    )
    deferred["metadata"]["review_passage"] = {
        "suitability": "mist_context",
        "eindoordeel": "later_beoordelen",
    }

    disposition = definitive_review_disposition(deferred)
    closure = source_passage_closure([deferred])

    assert disposition["state"] == "open"
    assert disposition["final"] is False
    assert disposition["valid"] is True
    assert disposition["outcome"] == "review_open"
    assert closure["source_passage_review_complete"] is False
    assert closure["unresolved_source_passage_ids"] == ["deferred-context"]


def test_terminal_review_written_non_candidate_disposition_is_final() -> None:
    reviewed_context = _object(
        "reviewed-context",
        register_status="used_as_context",
        review_status="approved",
        register_source="review",
    )

    disposition = definitive_review_disposition(reviewed_context)

    assert disposition["state"] == "final"
    assert disposition["final"] is True
    assert disposition["outcome"] == "used_as_context"
