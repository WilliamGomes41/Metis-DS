"""One read-only PublicationReadiness authority over current durable state.

PublicationReadiness combines T9 review duties, T10 source accountability,
T11 current revision selection, and the existing technical publication gates.
It never publishes and never persists a readiness value.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.review_duty_v1 import (
    FIRST_REVIEW,
    SECOND_REVIEW,
    review_repair_duties,
    review_duties,
)
from src.source_containers_v1 import source_accountability, source_closure

REVIEW_WORK_INCOMPLETE = "review_work_incomplete"
REVIEW_REPAIR_INCOMPLETE = "review_repair_incomplete"
SOURCE_PASSAGE_REVIEW_INCOMPLETE = "source_passage_review_incomplete"
REVIEW_DISPOSITION_INCONSISTENT = "review_disposition_inconsistent"
PUBLISHABLE_OBJECT_REQUIRED = "publishable_object_required"
READINESS_AUTHORITY_UNAVAILABLE = "readiness_authority_unavailable"

# These codes already mean that a human decision is outstanding. All other
# lower-gate codes are machine, durability, integrity, or lifecycle blockers.
# Keep this explicit: blocker producers must not be classified by string prefix.
CURATION_GATE_BLOCKERS = frozenset(
    {
        REVIEW_DISPOSITION_INCONSISTENT,
        "source_context_review_incomplete",
        "decision_graph_review_incomplete",
        "required_policy_review_missing",
        "archived_required_review_unfilled",
        "second_named_reviewer_required",
        "object_tuple_required",
        "four_eyes_required",
    }
)


def publication_review_readiness(
    duties: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Format the T9 ReviewDuty projection without deciding review state."""
    rows = list(duties)
    unresolved_ids = list(
        dict.fromkeys(str(row.get("object_id") or "") for row in rows if row.get("object_id"))
    )
    return {
        "review_complete": not rows,
        "review_required_object_ids": unresolved_ids,
        "review_required_object_count": len(unresolved_ids),
        "unresolved_review_object_ids": unresolved_ids,
        "unresolved_review_object_count": len(unresolved_ids),
        "first_review_duty_count": sum(row.get("stage") == FIRST_REVIEW for row in rows),
        "second_review_duty_count": sum(row.get("stage") == SECOND_REVIEW for row in rows),
        "review_duties": rows,
    }


def source_passage_closure(
    objects: Iterable[dict[str, Any]],
    *,
    review_path: str = "richtlijn",
    bindings=None,
    fragments=None,
    projection=None,
) -> dict[str, Any]:
    """Compatibility reader: T10 alone decides source closure."""
    if projection is None:
        projection = source_accountability(
            objects,
            review_path=review_path,
            bindings=bindings,
            fragments=fragments,
        )
    return source_closure(projection)


def review_followup_queues(
    objects: list[dict[str, Any]],
    *,
    review_path: str,
    bindings: list[dict[str, Any]] | None = None,
    fragments=None,
    projection=None,
) -> dict[str, list[dict[str, Any]]]:
    """Expose T10 human actions without creating another source decision tree."""
    if projection is None:
        projection = source_accountability(
            objects,
            review_path=review_path,
            bindings=bindings,
            fragments=fragments,
        )
    queues: dict[str, list[dict[str, Any]]] = {"disposition": [], "repair": []}
    for obj in objects:
        action = projection.get(str(obj.get("object_id") or ""), {}).get("human_action")
        if action == "source_disposition":
            queues["disposition"].append(obj)
        elif action == "technical_repair":
            # T10's internal label describes the repair kind. A human repair
            # remains curation work at the readiness boundary.
            queues["repair"].append(obj)
    return queues


def _existing_gate_readiness(considered: dict[str, Any]) -> dict[str, Any]:
    """Classify an already-computed lower-gate result exactly once."""
    blockers = list(dict.fromkeys(considered.get("blockers") or []))
    curation = [code for code in blockers if code in CURATION_GATE_BLOCKERS]
    technical = [code for code in blockers if code not in CURATION_GATE_BLOCKERS]
    return {
        "technical_ready": not technical,
        "technical_blockers": technical,
        "inherited_curation_blockers": curation,
    }


def _failed_readiness(snapshot_id: str, error: Exception) -> dict[str, Any]:
    """Fail closed when a required authority cannot be read."""
    return {
        "snapshot_id": snapshot_id,
        "publish_allowed": False,
        "publication_ready": False,
        "curation_ready": False,
        "curation_complete_known": False,
        "technical_ready": False,
        "blockers": [READINESS_AUTHORITY_UNAVAILABLE],
        "curation_blockers": [],
        "technical_blockers": [READINESS_AUTHORITY_UNAVAILABLE],
        "authority_error": type(error).__name__,
        "publishable_object_ids": [],
        "publishable_object_count": 0,
        "review_complete": False,
        "source_passage_review_complete": False,
    }


class PublicationReadinessMixin:
    """Combine current authorities into the one total readiness projection."""

    def _publication_readiness_inputs(self, snapshot_id: str) -> dict[str, Any]:
        envelope = self._envelope(snapshot_id) if hasattr(self, "_envelope") else {}
        try:
            objects = self.snapshot_objects(  # type: ignore[attr-defined]
                snapshot_id, envelope=envelope
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            objects = self.snapshot_objects(snapshot_id)  # type: ignore[attr-defined]
        if hasattr(self, "object_review_bindings"):
            try:
                bindings = self.object_review_bindings(snapshot_id, objects=objects)
            except TypeError as exc:
                if "unexpected keyword argument" not in str(exc):
                    raise
                bindings = self.object_review_bindings(snapshot_id)
        else:
            bindings = []
        if hasattr(self, "review_source_fragments"):
            try:
                fragments = self.review_source_fragments(snapshot_id, envelope=envelope)
            except TypeError as exc:
                if "unexpected keyword argument" not in str(exc):
                    raise
                fragments = self.review_source_fragments(snapshot_id)
        else:
            fragments = None
        from src.beslisboom_path_v1 import review_path_for_klasse
        review_path = (
            review_path_for_klasse(str(envelope["class"]))
            if envelope.get("class")
            else "richtlijn"
        )
        return {
            "envelope": envelope,
            "objects": objects,
            "bindings": bindings,
            "fragments": fragments,
            "review_path": review_path,
        }

    def publication_readiness(self, snapshot_id: str) -> dict[str, Any]:
        """Derive readiness without actor identity, writes, or cached authority."""
        try:
            inputs = PublicationReadinessMixin._publication_readiness_inputs(
                self, snapshot_id
            )
            technical_projection = self.technical_publication_readiness(  # type: ignore[attr-defined]
                snapshot_id=snapshot_id,
                envelope=inputs["envelope"],
                objects=inputs["objects"],
                bindings=inputs["bindings"],
                fragments=inputs["fragments"],
            )
            duties = review_duties(
                inputs["objects"],
                review_path=inputs["review_path"],
                bindings=inputs["bindings"],
                fragments=inputs["fragments"],
            )
            source_projection = source_accountability(
                inputs["objects"],
                review_path=inputs["review_path"],
                bindings=inputs["bindings"],
                fragments=inputs["fragments"],
            )
        except (KeyError, OSError, TypeError, ValueError) as exc:
            return _failed_readiness(snapshot_id, exc)

        existing = _existing_gate_readiness(technical_projection)
        review = publication_review_readiness(duties)
        closure = source_passage_closure(
            inputs["objects"],
            review_path=inputs["review_path"],
            bindings=inputs["bindings"],
            fragments=inputs["fragments"],
            projection=source_projection,
        )
        source_queues = review_followup_queues(
            inputs["objects"],
            review_path=inputs["review_path"],
            bindings=inputs["bindings"],
            fragments=inputs["fragments"],
            projection=source_projection,
        )
        repair_duties = review_repair_duties(
            inputs["objects"],
            review_path=inputs["review_path"],
        )
        repair_ids = [str(row["object_id"]) for row in repair_duties]
        repair_count = len(repair_duties)
        repair_open = bool(repair_duties)

        considered = dict(technical_projection)
        considered.update(review)
        considered.update(closure)
        considered["source_disposition_object_ids"] = [
            str(obj.get("object_id") or "") for obj in source_queues["disposition"]
        ]
        considered["source_repair_object_ids"] = [
            str(obj.get("object_id") or "") for obj in source_queues["repair"]
        ]
        considered["review_repair_object_ids"] = repair_ids
        considered["review_repair_duty_count"] = repair_count

        blockers = list(dict.fromkeys(considered.get("blockers") or []))
        curation_blockers = list(existing["inherited_curation_blockers"])
        if not review["review_complete"]:
            curation_blockers.append(REVIEW_WORK_INCOMPLETE)
        if not closure["source_passage_review_complete"]:
            curation_blockers.append(SOURCE_PASSAGE_REVIEW_INCOMPLETE)
        if repair_open:
            curation_blockers.append(REVIEW_REPAIR_INCOMPLETE)
        curation_blockers = list(dict.fromkeys(curation_blockers))
        for code in curation_blockers:
            if code not in blockers:
                blockers.append(code)

        technical_blockers = list(existing["technical_blockers"])
        curation_ready = not curation_blockers
        if (
            curation_ready
            and not technical_blockers
            and not considered.get("publishable_object_count")
            and PUBLISHABLE_OBJECT_REQUIRED not in technical_blockers
        ):
            technical_blockers.append(PUBLISHABLE_OBJECT_REQUIRED)
            blockers.append(PUBLISHABLE_OBJECT_REQUIRED)
        technical_ready = not technical_blockers
        publication_ready = curation_ready and technical_ready

        considered["blockers"] = list(dict.fromkeys(blockers))
        considered["technical_ready"] = technical_ready
        considered["technical_blockers"] = technical_blockers
        considered["curation_ready"] = curation_ready
        considered["curation_blockers"] = curation_blockers
        considered["publication_ready"] = publication_ready
        considered["publish_allowed"] = publication_ready
        return considered

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        """Authorize the action boundary, then reuse the same current projection."""
        self._require_role(actor_id, "publisher")
        return self.publication_readiness(snapshot_id)


def derive_publication_readiness(authority: Any, snapshot_id: str) -> dict[str, Any]:
    """Run the one total authority for lower-level compatibility callers."""
    return PublicationReadinessMixin.publication_readiness(authority, snapshot_id)
