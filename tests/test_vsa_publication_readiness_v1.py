"""T12: publication readiness consumes T9 ReviewDuty output.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.publication_readiness_v1 import (
    PublicationReadinessMixin,
    REVIEW_WORK_INCOMPLETE,
    publication_review_readiness,
)
from src.review_closure_v1 import ReviewClosureConsole
from src.review_duty_v1 import FIRST_REVIEW, SECOND_REVIEW


def _duty(object_id: str, stage: str = FIRST_REVIEW) -> dict[str, str]:
    return {
        "object_id": object_id,
        "object_version": "1.0",
        "canonical_object_hash": f"hash-{object_id}",
        "stage": stage,
        "lane": "batch",
        "object_type": "explanation",
    }


class _ExistingPublicationGate:
    def __init__(self, result: dict[str, Any]) -> None:
        self._result = result

    def snapshot_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        return []

    def technical_publication_readiness(
        self, *, snapshot_id: str, **_context: Any
    ) -> dict[str, Any]:
        _ = snapshot_id
        return deepcopy(self._result)


class _PublicationReadinessSubject(PublicationReadinessMixin, _ExistingPublicationGate):
    pass


def test_one_t9_projection_does_not_close_ninety_nine_open_duties() -> None:
    duties = [_duty(f"ko-{index:03d}") for index in range(2, 101)]

    readiness = publication_review_readiness(duties)

    assert readiness["review_required_object_count"] == 99
    assert readiness["unresolved_review_object_count"] == 99
    assert readiness["review_complete"] is False
    assert readiness["first_review_duty_count"] == 99


def test_t9_first_and_second_review_stages_are_preserved() -> None:
    readiness = publication_review_readiness(
        [_duty("first"), _duty("second", SECOND_REVIEW)]
    )

    assert readiness["unresolved_review_object_ids"] == ["first", "second"]
    assert readiness["first_review_duty_count"] == 1
    assert readiness["second_review_duty_count"] == 1
    assert REVIEW_WORK_INCOMPLETE == "review_work_incomplete"


def test_empty_t9_projection_is_review_complete() -> None:
    readiness = publication_review_readiness([])

    assert readiness["review_complete"] is True
    assert readiness["unresolved_review_object_count"] == 0


def test_existing_technical_blockers_are_preserved() -> None:
    subject = _PublicationReadinessSubject(
        {
            "publish_allowed": False,
            "blockers": ["g2_source_store_unavailable"],
            "publishable_object_count": 1,
        }
    )

    considered = subject.publication_readiness("snapshot")

    assert considered["publish_allowed"] is False
    assert considered["technical_blockers"] == ["g2_source_store_unavailable"]
    assert considered["review_complete"] is True


def test_current_closed_review_workflow_includes_readiness_slice() -> None:
    assert issubclass(ReviewClosureConsole, PublicationReadinessMixin)
