"""VSA Slice 1: publication requires completed candidate review."""
from __future__ import annotations

from typing import Any

from src.publication_readiness_v1 import (
    PublicationReadinessMixin,
    REVIEW_WORK_INCOMPLETE,
    publication_review_readiness,
)
from src.review_closure_v1 import ReviewClosureConsole


def _object(
    object_id: str,
    validation_status: str,
    *,
    register_status: str = "selected_as_candidate",
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": "explanation",
        "governance": {"validation_status": validation_status},
        "metadata": {"passage_register": {"status": register_status}},
    }


class _ExistingPublicationGate:
    def __init__(self, objects: list[dict[str, Any]], blockers: list[str] | None = None) -> None:
        self._objects = objects
        self._blockers = list(blockers or [])

    def snapshot_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        return self._objects

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        _ = actor_id, snapshot_id
        return {
            "publish_allowed": not self._blockers,
            "blockers": list(self._blockers),
        }


class _PublicationReadinessSubject(PublicationReadinessMixin, _ExistingPublicationGate):
    pass


def test_one_approved_candidate_does_not_close_ninety_nine_open_candidates() -> None:
    objects = [_object("ko-001", "approved")] + [
        _object(f"ko-{index:03d}", "needs_review")
        for index in range(2, 101)
    ]

    readiness = publication_review_readiness(objects)
    considered = _PublicationReadinessSubject(objects).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert readiness["review_required_object_count"] == 100
    assert readiness["unresolved_review_object_count"] == 99
    assert readiness["review_complete"] is False
    assert considered["publish_allowed"] is False
    assert REVIEW_WORK_INCOMPLETE in considered["blockers"]
    assert len(considered["unresolved_review_object_ids"]) == 99


def test_deferred_candidate_remains_unresolved() -> None:
    objects = [
        _object("approved", "approved"),
        _object("later", "needs_review"),
    ]

    considered = _PublicationReadinessSubject(objects).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert considered["publish_allowed"] is False
    assert considered["unresolved_review_object_ids"] == ["later"]
    assert considered["unresolved_review_object_count"] == 1


def test_approved_and_rejected_candidates_are_final_for_readiness() -> None:
    objects = [
        _object("publish-me", "approved"),
        _object("do-not-publish", "rejected"),
    ]

    considered = _PublicationReadinessSubject(objects).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert considered["review_complete"] is True
    assert considered["unresolved_review_object_count"] == 0
    assert considered["publish_allowed"] is True
    assert REVIEW_WORK_INCOMPLETE not in considered["blockers"]


def test_non_candidate_passage_is_outside_slice_one_boundary() -> None:
    objects = [
        _object("candidate", "approved"),
        _object("context", "needs_review", register_status="used_as_context"),
        _object("unassessed", "needs_review", register_status="not_yet_assessed"),
    ]

    readiness = publication_review_readiness(objects)

    assert readiness["review_required_object_ids"] == ["candidate"]
    assert readiness["review_complete"] is True


def test_existing_technical_blockers_are_preserved() -> None:
    objects = [_object("candidate", "approved")]
    subject = _PublicationReadinessSubject(objects, blockers=["g2_source_store_unavailable"])

    considered = subject.consider_publish(actor_id="publisher", snapshot_id="snapshot")

    assert considered["publish_allowed"] is False
    assert considered["blockers"] == ["g2_source_store_unavailable"]
    assert considered["review_complete"] is True


def test_current_closed_review_workflow_includes_readiness_slice() -> None:
    assert issubclass(ReviewClosureConsole, PublicationReadinessMixin)
