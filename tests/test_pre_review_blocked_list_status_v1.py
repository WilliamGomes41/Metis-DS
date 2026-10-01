"""Blocked pre-review must remain visible without claiming active processing.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.durable_publication_console_v1 import DurablePublicationConsole
from src.operations_console_v1 import CAPTURED, PRE_REVIEW_BLOCKED, ConsoleError
from src.workflows.workflow_badge_counts_postgres_v1 import _PostgresBadgeCountsMixin


class _ListStatusReader(_PostgresBadgeCountsMixin):
    def __init__(self, rows, releases=None):
        self.rows = rows
        self.releases = releases or {}
        self.canonical_publication_store = object() if releases is not None else None

    def _workflow_list_status_rows(self, snapshot_ids=None):
        return deepcopy(self.rows)

    def _canonical_list_release_rows(self, snapshot_ids):
        return deepcopy(self.releases)

    def publication_readiness(self, snapshot_id):
        raise AssertionError("List presentation must not evaluate full publish readiness")

    def snapshot_objects(self, snapshot_id):
        raise AssertionError("List presentation must not materialize object payloads")


@pytest.mark.parametrize("has_open_review", [False, True])
def test_pre_review_block_takes_precedence_over_open_review_without_mutating_authority(has_open_review):
    rows = {
        "blocked": {"state": CAPTURED, "publication_eligibility": PRE_REVIEW_BLOCKED,
                    "has_open_review": has_open_review},
        "ordinary": {"state": CAPTURED, "publication_eligibility": "eligible_for_transform_and_review",
                     "has_open_review": has_open_review},
    }
    before = deepcopy(rows)
    statuses = _ListStatusReader(rows).list_document_lifecycle_statuses()
    assert statuses["blocked"] == {
        "workflow_status": "blocked", "release_status": "none",
        "serving_status": "inactive", "presentation_status": "blocked",
    }
    assert statuses["ordinary"]["presentation_status"] == ("in_review" if has_open_review else "processing")
    assert rows == before


@pytest.mark.parametrize("release, expected", [
    ({"status": "withdrawn"}, "withdrawn"),
    ({"status": "published", "item_count": 1, "active_same_release": 1}, "published"),
    ({"status": "published", "item_count": 1, "active_same_release": 0, "active_other_release": 1}, "superseded"),
    ({"status": "published", "item_count": 1, "active_same_release": 0}, "published_inactive"),
])
def test_pre_review_block_cannot_override_canonical_release_or_serving(release, expected):
    rows = {"snapshot": {"state": CAPTURED, "publication_eligibility": PRE_REVIEW_BLOCKED,
                         "has_open_review": True}}
    status = _ListStatusReader(rows, {"snapshot": release}).list_document_lifecycle_statuses()["snapshot"]
    assert status["workflow_status"] == "closed"
    assert status["presentation_status"] == expected
    assert status["serving_status"] == ("active" if expected == "published" else "inactive")


def test_blocked_empty_capture_has_same_local_and_postgres_list_status_after_restart(tmp_path: Path):
    console = DurablePublicationConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    actor = console.create_account(username="researcher", password="test-researcher-secret", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="test-reviewer-secret", roles=("reviewer",))

    def rejected(*args, **kwargs):
        raise ConsoleError("pre_review_llm_proposal_rejected", "semantic_span_bounds_invalid")

    console._fragments_and_spec = rejected
    receipt = console.ingest(
        actor_id=actor["account_id"], filename="blocked.html", data=b"<p>source</p>",
        content_type="text/html", ingest_kind="new", title="Blocked", version="1", date="2026-10-01",
        live_url="", class_="richtlijn", family="test", named_reviewers=[reviewer["account_id"]],
    )
    snapshot_id = receipt["snapshot_id"]
    restarted = DurablePublicationConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert restarted.snapshot_objects(snapshot_id) == []
    assert restarted.waiting_task_counts(reviewer["account_id"])["review"] == 0
    row = {**restarted._envelope(snapshot_id), "has_open_review": False}
    assert _ListStatusReader({snapshot_id: row}).list_document_lifecycle_statuses()[snapshot_id] == restarted.document_lifecycle_status(snapshot_id)
    assert restarted.document_status(snapshot_id) == "blocked"
