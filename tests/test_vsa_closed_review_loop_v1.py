"""VSA Slice 3: substantive source passages must reach final disposition.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from typing import Any

from src.publication_readiness_v1 import (
    PublicationReadinessMixin,
    REVIEW_WORK_INCOMPLETE,
    SOURCE_PASSAGE_REVIEW_INCOMPLETE,
    source_passage_closure,
)


def _object(
    object_id: str,
    *,
    object_type: str = "explanation",
    register_status: str = "not_yet_assessed",
    review_status: str = "needs_review",
    proposed_type: str = "explanation",
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": object_type,
        "proposed_object_type": proposed_type,
        "metadata": {"passage_register": {"status": register_status}},
        "governance": {"validation_status": review_status},
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


class _Subject(PublicationReadinessMixin, _ExistingPublicationGate):
    pass


def test_candidate_review_complete_but_unassessed_substantive_passage_blocks() -> None:
    objects = [
        _object(
            "approved-candidate",
            register_status="selected_as_candidate",
            review_status="approved",
        ),
        _object("open-source-passage"),
    ]

    considered = _Subject(objects).consider_publish(actor_id="publisher", snapshot_id="snapshot")

    assert considered["review_complete"] is True
    assert considered["source_passage_review_complete"] is False
    assert considered["unresolved_source_passage_ids"] == ["open-source-passage"]
    assert considered["unresolved_source_passage_count"] == 1
    assert considered["publish_allowed"] is False
    assert SOURCE_PASSAGE_REVIEW_INCOMPLETE in considered["blockers"]
    assert REVIEW_WORK_INCOMPLETE not in considered["blockers"]


def test_all_existing_terminal_dispositions_close_substantive_passages() -> None:
    objects = [
        _object(
            "approved",
            register_status="selected_as_candidate",
            review_status="approved",
        ),
        _object(
            "rejected",
            register_status="selected_as_candidate",
            review_status="rejected",
        ),
        _object("context", register_status="used_as_context"),
        _object("support", register_status="linked_as_support"),
        _object("excluded", register_status="excluded_with_reason"),
    ]

    closure = source_passage_closure(objects)

    assert closure["source_passage_review_complete"] is True
    assert closure["review_required_source_passage_count"] == 5
    assert closure["unresolved_source_passage_ids"] == []


def test_admission_blocked_substantive_passage_is_not_auto_excluded() -> None:
    blocked = _object("blocked-source")
    blocked["metadata"]["admission_gate"] = {
        "gate_result": "blocked",
        "blockers": ["missing_source_evidence"],
    }

    before = dict(blocked["metadata"]["passage_register"])
    closure = source_passage_closure([blocked])

    assert closure["source_passage_review_complete"] is False
    assert closure["unresolved_source_passage_ids"] == ["blocked-source"]
    assert blocked["metadata"]["passage_register"] == before
    assert blocked["metadata"]["passage_register"]["status"] == "not_yet_assessed"


def test_explicit_exclusion_closes_passage_without_making_it_candidate_work() -> None:
    excluded = _object("excluded", register_status="excluded_with_reason")

    closure = source_passage_closure([excluded])
    considered = _Subject([excluded]).consider_publish(actor_id="publisher", snapshot_id="snapshot")

    assert closure["source_passage_review_complete"] is True
    assert considered["review_required_object_count"] == 0
    assert considered["source_passage_review_complete"] is True
    assert SOURCE_PASSAGE_REVIEW_INCOMPLETE not in considered["blockers"]


def test_fast_lane_structure_does_not_create_substantive_review_work() -> None:
    heading = _object(
        "heading",
        object_type="heading",
        proposed_type="heading",
        register_status="not_yet_assessed",
    )

    closure = source_passage_closure([heading])

    assert closure["source_passage_review_complete"] is True
    assert closure["review_required_source_passage_count"] == 0
    assert closure["unresolved_source_passage_count"] == 0


def test_slice_one_candidate_blocker_remains_independent() -> None:
    unresolved_candidate = _object(
        "candidate",
        register_status="selected_as_candidate",
        review_status="needs_review",
    )

    considered = _Subject([unresolved_candidate]).consider_publish(
        actor_id="publisher", snapshot_id="snapshot"
    )

    assert considered["review_complete"] is False
    assert considered["source_passage_review_complete"] is False
    assert REVIEW_WORK_INCOMPLETE in considered["blockers"]
    assert SOURCE_PASSAGE_REVIEW_INCOMPLETE in considered["blockers"]
    assert considered["publish_allowed"] is False


def test_existing_technical_blocker_is_preserved_after_full_closure() -> None:
    approved = _object(
        "approved",
        register_status="selected_as_candidate",
        review_status="approved",
    )
    subject = _Subject([approved], blockers=["g2_source_store_unavailable"])

    considered = subject.consider_publish(actor_id="publisher", snapshot_id="snapshot")

    assert considered["review_complete"] is True
    assert considered["source_passage_review_complete"] is True
    assert considered["publish_allowed"] is False
    assert considered["blockers"] == ["g2_source_store_unavailable"]
