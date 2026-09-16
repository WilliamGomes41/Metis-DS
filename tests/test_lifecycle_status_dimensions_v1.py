"""Repair #219: workflow, release and serving status stay separate.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from src.document_status_v1 import derive_lifecycle_status
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.proportionate_review_v1 import ProportionateReviewConsole
from src.review_workboard_v1 import review_work_item


pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def test_lifecycle_dimensions_do_not_collapse_release_and_serving_truth() -> None:
    assert derive_lifecycle_status(
        readiness={"curation_ready": False, "technical_ready": True},
        release_status="none",
        serving_status="inactive",
    ) == {
        "workflow_status": "in_review",
        "release_status": "none",
        "serving_status": "inactive",
        "presentation_status": "in_review",
    }
    assert derive_lifecycle_status(
        readiness={},
        release_status="published",
        serving_status="active",
    ) == {
        "workflow_status": "closed",
        "release_status": "published",
        "serving_status": "active",
        "presentation_status": "published",
    }
    assert derive_lifecycle_status(
        readiness={"publication_ready": True},
        release_status="published",
        serving_status="inactive",
    )["presentation_status"] == "published_inactive"
    assert derive_lifecycle_status(
        readiness={"publication_ready": True},
        release_status="superseded",
        serving_status="inactive",
    )["presentation_status"] == "superseded"
    assert derive_lifecycle_status(
        readiness={"publication_ready": True},
        release_status="withdrawn",
        serving_status="inactive",
    )["presentation_status"] == "withdrawn"


class _Cursor:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    def fetchone(self) -> dict[str, Any] | None:
        return deepcopy(self._row)


class _Connection:
    def __init__(
        self,
        *,
        release: dict[str, Any] | None,
        counts: dict[str, Any] | None,
    ) -> None:
        self.release = release
        self.counts = counts

    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, sql: str, _params: Any = None) -> _Cursor:
        if "SELECT rel.release_id, rel.status" in sql:
            return _Cursor(self.release)
        if "COUNT(*) AS item_count" in sql:
            return _Cursor(self.counts)
        raise AssertionError(f"unexpected SQL: {sql}")


class _CanonicalStore:
    def __init__(
        self,
        *,
        release: dict[str, Any] | None,
        counts: dict[str, Any] | None = None,
    ) -> None:
        self.release = release
        self.counts = counts

    def _connect(self) -> _Connection:
        return _Connection(release=self.release, counts=self.counts)


def _status_from_canonical(
    *,
    release_status: str | None,
    item_count: int = 2,
    active_same: int = 0,
    active_other: int = 0,
) -> dict[str, str]:
    console = object.__new__(DurablePublicationConsole)
    console.canonical_publication_store = _CanonicalStore(
        release=(
            {"release_id": "release-1", "status": release_status}
            if release_status is not None
            else None
        ),
        counts=(
            {
                "item_count": item_count,
                "active_same_release": active_same,
                "active_other_release": active_other,
            }
            if release_status == "published"
            else None
        ),
    )
    return console.document_release_serving_status("snap-1")


def test_canonical_registry_is_the_serving_authority() -> None:
    assert _status_from_canonical(release_status=None) == {
        "release_status": "none",
        "serving_status": "inactive",
    }
    assert _status_from_canonical(
        release_status="published",
        active_same=2,
    ) == {
        "release_status": "published",
        "serving_status": "active",
    }
    assert _status_from_canonical(
        release_status="published",
        active_other=2,
    ) == {
        "release_status": "superseded",
        "serving_status": "inactive",
    }
    # Partial displacement is deliberately not promoted to superseded.
    assert _status_from_canonical(
        release_status="published",
        active_same=1,
        active_other=1,
    ) == {
        "release_status": "published",
        "serving_status": "inactive",
    }
    assert _status_from_canonical(release_status="withdrawn") == {
        "release_status": "withdrawn",
        "serving_status": "inactive",
    }


class _ClosedQueueConsole(ProportionateReviewConsole):
    def __init__(self, objects: list[dict[str, Any]]) -> None:
        self._test_objects = objects

    def snapshot_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        return deepcopy(self._test_objects)

    def document_lifecycle_status(self, _snapshot_id: str) -> dict[str, str]:
        return {
            "workflow_status": "closed",
            "release_status": "published",
            "serving_status": "active",
            "presentation_status": "published",
        }


def test_closed_historical_revision_never_reopens_from_stale_review_rows() -> None:
    stale_open_heading = {
        "object_id": "heading-open",
        "object_type": "heading",
        "proposed_object_type": "heading",
        "metadata": {
            "passage_register": {
                "status": "selected_as_candidate",
                "source": "extract",
            },
            "admission": {
                "gate_result": "allowed",
                "section_path": ["Hoofdstuk"],
            },
        },
        "governance": {"validation_status": "needs_review"},
        "content": {"clean_text": "Nog open volgens legacy reviewrij"},
    }
    console = _ClosedQueueConsole([stale_open_heading])
    item = review_work_item(
        console,
        account={"account_id": "reviewer-1", "roles": ["reviewer"]},
        envelope={
            "snapshot_id": "snap-1",
            "title": "Historische release",
            "version": "1.0",
            "family": "zorg",
            "class": "richtlijn",
            "state": "published",
            "named_reviewers": ["reviewer-1"],
        },
    )

    assert item is not None
    assert item["remaining_review_items"] > 0
    assert item["lifecycle_status"]["workflow_status"] == "closed"
    assert item["work_state"] == "complete"
    assert item["next_task"] == ""
    assert item["next_href"] == ""
