"""Derived publication readiness for completed review work.

This slice is read-only: it derives readiness from current passage-register and
governance state. It does not publish or persist a duplicate completion status.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.operations_console_v1 import review_lane
from src.passage_register_v1 import passage_register_of
from src.review_disposition_v1 import definitive_review_disposition

REVIEW_WORK_INCOMPLETE = "review_work_incomplete"
SOURCE_PASSAGE_REVIEW_INCOMPLETE = "source_passage_review_incomplete"


def publication_review_readiness(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return whether every current review-required candidate is final."""
    required_ids: list[str] = []
    unresolved_ids: list[str] = []

    for obj in objects:
        if obj.get("object_type") == "document":
            continue
        if passage_register_of(obj).get("status") != "selected_as_candidate":
            continue
        object_id = str(obj.get("object_id") or "")
        if not object_id:
            continue
        required_ids.append(object_id)
        if not definitive_review_disposition(obj)["final"]:
            unresolved_ids.append(object_id)

    return {
        "review_complete": not unresolved_ids,
        "review_required_object_ids": required_ids,
        "review_required_object_count": len(required_ids),
        "unresolved_review_object_ids": unresolved_ids,
        "unresolved_review_object_count": len(unresolved_ids),
    }


def source_passage_closure(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return whether every substantive current source passage is final.

    Existing review routing is the boundary: document objects and fast-lane
    structure (heading/path) are not substantive passage work. Every other
    current object must have a final Slice 2 disposition. Admission failures
    remain open through their existing ``not_yet_assessed`` disposition; this
    function never mutates or auto-excludes them.
    """
    required_ids: list[str] = []
    unresolved_ids: list[str] = []

    for obj in objects:
        if obj.get("object_type") == "document" or review_lane(obj) == "fast":
            continue
        object_id = str(obj.get("object_id") or "")
        if not object_id:
            continue
        required_ids.append(object_id)
        if not definitive_review_disposition(obj)["final"]:
            unresolved_ids.append(object_id)

    return {
        "source_passage_review_complete": not unresolved_ids,
        "review_required_source_passage_ids": required_ids,
        "review_required_source_passage_count": len(required_ids),
        "unresolved_source_passage_ids": unresolved_ids,
        "unresolved_source_passage_count": len(unresolved_ids),
    }


class PublicationReadinessMixin:
    """Fail closed while candidate review or substantive passage work is open."""

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        considered = super().consider_publish(actor_id=actor_id, snapshot_id=snapshot_id)  # type: ignore[misc]
        objects = self.snapshot_objects(snapshot_id)  # type: ignore[attr-defined]
        readiness = publication_review_readiness(objects)
        closure = source_passage_closure(objects)
        considered.update(readiness)
        considered.update(closure)

        blockers = list(considered.get("blockers") or [])
        if not readiness["review_complete"] and REVIEW_WORK_INCOMPLETE not in blockers:
            blockers.append(REVIEW_WORK_INCOMPLETE)
        if (
            not closure["source_passage_review_complete"]
            and SOURCE_PASSAGE_REVIEW_INCOMPLETE not in blockers
        ):
            blockers.append(SOURCE_PASSAGE_REVIEW_INCOMPLETE)
        if blockers != list(considered.get("blockers") or []):
            considered["blockers"] = blockers
        if not readiness["review_complete"] or not closure["source_passage_review_complete"]:
            considered["publish_allowed"] = False
        return considered
