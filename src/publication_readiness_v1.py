"""Derived publication readiness for completed review work.

This slice is read-only: it derives readiness from current passage-register,
governance and existing publication-gate state. It does not publish or persist
a duplicate completion status.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.passage_register_v1 import passage_register_of
from src.review_disposition_v1 import definitive_review_disposition
from src.source_containers_v1 import source_accountability, source_closure

REVIEW_WORK_INCOMPLETE = "review_work_incomplete"
SOURCE_PASSAGE_REVIEW_INCOMPLETE = "source_passage_review_incomplete"
REVIEW_DISPOSITION_INCONSISTENT = "review_disposition_inconsistent"

# The lower technical gate predates the read/action split and performs a publisher
# role check before its otherwise read-only evaluation. Keep that compatibility
# detail private to the readiness boundary: this object is a capability, not an
# account identity, and is accepted only while evaluating readiness.
_READINESS_EVALUATION_CAPABILITY = object()


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


def source_passage_closure(objects: Iterable[dict[str, Any]], *, review_path="richtlijn",
                           bindings=None, fragments=None, projection=None) -> dict[str, Any]:
    """Compatibility reader: source-domain authority alone decides closure."""
    if projection is None:
        projection = source_accountability(objects, review_path=review_path, bindings=bindings, fragments=fragments)
    return source_closure(projection)


def review_followup_queues(
    objects: list[dict[str, Any]], *, review_path: str,
    bindings: list[dict[str, Any]] | None = None, fragments=None, projection=None,
) -> dict[str, list[dict[str, Any]]]:
    """Map source-domain actions to existing queues without another decision."""
    if projection is None:
        projection = source_accountability(objects, review_path=review_path, bindings=bindings, fragments=fragments)
    queues: dict[str, list[dict[str, Any]]] = {"disposition": [], "repair": []}
    for obj in objects:
        action = projection.get(str(obj.get("object_id") or ""), {}).get("human_action")
        if action == "source_disposition":
            queues["disposition"].append(obj)
        elif action == "technical_repair":
            queues["repair"].append(obj)
    return queues


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
        if (has_disposition_conflict and code == REVIEW_DISPOSITION_INCONSISTENT)
        or code == "source_context_review_incomplete"
        or code.startswith("decision_graph_")
        or code == "required_policy_review_missing"
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
    """Combine curator completeness with existing technical publish gates."""

    def _require_role(self, account_id: Any, role: str) -> dict[str, Any]:
        """Adapt the legacy technical gate for internal read-only evaluation only.

        Runtime consoles provide a lower role authority. Small policy adapters
        used to exercise this mixin may intentionally omit one; preserve that
        pre-existing composability without weakening runtime authorization.
        """
        if account_id is _READINESS_EVALUATION_CAPABILITY and role == "publisher":
            return {}
        require_role = getattr(super(), "_require_role", None)
        if require_role is None:
            return {}
        return require_role(account_id, role)

    def publication_readiness(self, snapshot_id: str) -> dict[str, Any]:
        """Evaluate publication readiness without granting publication authority."""
        considered = super().consider_publish(  # type: ignore[misc]
            actor_id=_READINESS_EVALUATION_CAPABILITY,
            snapshot_id=snapshot_id,
        )
        existing = _existing_gate_readiness(considered)
        objects = self.snapshot_objects(snapshot_id)  # type: ignore[attr-defined]
        readiness = publication_review_readiness(objects)
        from src.beslisboom_path_v1 import review_path_for_klasse
        envelope = self._envelope(snapshot_id) if hasattr(self, "_envelope") else {}
        bindings = self.object_review_bindings(snapshot_id) if hasattr(self, "object_review_bindings") else None
        fragments = self.review_source_fragments(snapshot_id) if hasattr(self, "review_source_fragments") else None
        closure = source_passage_closure(objects, review_path=review_path_for_klasse(str(envelope["class"])) if envelope.get("class") else "richtlijn",
                                         bindings=bindings, fragments=fragments)
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

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        """Authorize the publisher action boundary, then reuse read-only readiness."""
        self._require_role(actor_id, "publisher")
        return self.publication_readiness(snapshot_id)
