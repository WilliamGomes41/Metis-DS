"""Derived publication readiness for completed review work.

This slice is read-only: it derives readiness from current passage-register,
governance and existing publication-gate state. It does not publish or persist
a duplicate completion status.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.operations_console_v1 import review_lane
from src.passage_register_v1 import passage_register_of
from src.review_disposition_v1 import definitive_review_disposition

REVIEW_WORK_INCOMPLETE = "review_work_incomplete"
SOURCE_PASSAGE_REVIEW_INCOMPLETE = "source_passage_review_incomplete"
REVIEW_DISPOSITION_INCONSISTENT = "review_disposition_inconsistent"


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


def _existing_gate_readiness(considered: dict[str, Any]) -> dict[str, Any]:
    """Separate existing technical gates from inherited curation blockers.

    ``OperationsConsole.consider_publish`` remains the technical authority.
    Closed Review can add a disposition-consistency blocker above that layer;
    this helper only classifies that already-computed result and never reruns a
    technical gate.
    """
    blockers = list(considered.get("blockers") or [])
    has_disposition_conflict = bool(considered.get("disposition_conflict_object_ids"))
    inherited_curation = [
        code
        for code in blockers
        if has_disposition_conflict and code == REVIEW_DISPOSITION_INCONSISTENT
    ]
    technical_blockers = [code for code in blockers if code not in inherited_curation]

    if inherited_curation:
        technical_ready = not technical_blockers and bool(
            considered.get("publishable_object_count")
        )
    else:
        technical_ready = bool(considered.get("publish_allowed"))

    return {
        "technical_ready": technical_ready,
        "technical_blockers": technical_blockers,
        "inherited_curation_blockers": inherited_curation,
    }


class PublicationReadinessMixin:
    """Combine curator completeness with the existing technical publish gates."""

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        considered = super().consider_publish(actor_id=actor_id, snapshot_id=snapshot_id)  # type: ignore[misc]
        existing = _existing_gate_readiness(considered)
        objects = self.snapshot_objects(snapshot_id)  # type: ignore[attr-defined]
        readiness = publication_review_readiness(objects)
        closure = source_passage_closure(objects)
        considered.update(readiness)
        considered.update(closure)

        blockers = list(considered.get("blockers") or [])
        curation_blockers = list(existing["inherited_curation_blockers"])
        if not readiness["review_complete"]:
            if REVIEW_WORK_INCOMPLETE not in blockers:
                blockers.append(REVIEW_WORK_INCOMPLETE)
            if REVIEW_WORK_INCOMPLETE not in curation_blockers:
                curation_blockers.append(REVIEW_WORK_INCOMPLETE)
        if not closure["source_passage_review_complete"]:
            if SOURCE_PASSAGE_REVIEW_INCOMPLETE not in blockers:
                blockers.append(SOURCE_PASSAGE_REVIEW_INCOMPLETE)
            if SOURCE_PASSAGE_REVIEW_INCOMPLETE not in curation_blockers:
                curation_blockers.append(SOURCE_PASSAGE_REVIEW_INCOMPLETE)

        curation_ready = not curation_blockers
        technical_ready = bool(existing["technical_ready"])
        publication_ready = technical_ready and curation_ready

        considered["blockers"] = blockers
        considered["technical_ready"] = technical_ready
        considered["technical_blockers"] = list(existing["technical_blockers"])
        considered["curation_ready"] = curation_ready
        considered["curation_blockers"] = curation_blockers
        considered["publication_ready"] = publication_ready
        considered["publish_allowed"] = publication_ready
        return considered
