"""Derived publication readiness for completed knowledge-object review.

This slice is read-only: it derives readiness from current passage-register and
governance state. It does not publish, persist a duplicate status, or redefine
full source-passage closure.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.passage_register_v1 import passage_register_of
from src.review_disposition_v1 import definitive_review_disposition

REVIEW_WORK_INCOMPLETE = "review_work_incomplete"


def publication_review_readiness(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return whether every current review-required candidate is final.

    Protocol v2.33 makes ``selected_as_candidate`` the passage-register state
    for a candidate knowledge object. Slice 1 deliberately stops at that
    knowledge-object boundary; complete closure of every substantive source
    passage remains a separate workflow concern.
    """
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


class PublicationReadinessMixin:
    """Fail closed before publication while candidate review remains open."""

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        considered = super().consider_publish(actor_id=actor_id, snapshot_id=snapshot_id)  # type: ignore[misc]
        readiness = publication_review_readiness(self.snapshot_objects(snapshot_id))  # type: ignore[attr-defined]
        considered.update(readiness)
        if not readiness["review_complete"]:
            blockers = list(considered.get("blockers") or [])
            if REVIEW_WORK_INCOMPLETE not in blockers:
                blockers.append(REVIEW_WORK_INCOMPLETE)
            considered["blockers"] = blockers
            considered["publish_allowed"] = False
        return considered
