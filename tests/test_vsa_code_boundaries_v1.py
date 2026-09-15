"""VSA Slice 10: explicit Review/readiness/Publishing code boundaries.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.document_status_v1 import DocumentStatusReadinessMixin
from src.operations_console_v1 import ConsoleError
from src.publication_readiness_v1 import PublicationReadinessMixin

ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


class _TechnicalGate:
    def __init__(self) -> None:
        self.role_checks: list[tuple[Any, str]] = []
        self.technical_evaluations = 0
        self._envelopes = {
            "snap-test": {"snapshot_id": "snap-test", "state": "captured_not_published"}
        }

    def _require_role(self, account_id: Any, role: str) -> dict[str, Any]:
        self.role_checks.append((account_id, role))
        if account_id != "publisher-1" or role != "publisher":
            raise ConsoleError("publisher_role_required")
        return {"account_id": "publisher-1", "username": "publisher", "roles": ["publisher"]}

    def consider_publish(self, *, actor_id: Any, snapshot_id: str) -> dict[str, Any]:
        self._require_role(actor_id, "publisher")
        self.technical_evaluations += 1
        return {
            "snapshot_id": snapshot_id,
            "publish_allowed": False,
            "publishable_object_count": 0,
            "publishable_object_ids": [],
            "blockers": ["object_tuple_required"],
            "g2": "PASS",
        }

    def snapshot_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        return []

    def _envelope(self, snapshot_id: str) -> dict[str, Any]:
        return self._envelopes[snapshot_id]


class _BoundaryConsole(
    DocumentStatusReadinessMixin,
    PublicationReadinessMixin,
    _TechnicalGate,
):
    pass


def test_document_status_has_no_publisher_impersonation_boundary() -> None:
    source = (ROOT / "src" / "document_status_v1.py").read_text(encoding="utf-8")

    assert "_require_role" not in DocumentStatusReadinessMixin.__dict__
    assert "_READ_ONLY_STATUS_ACTOR" not in source
    assert "document-status-read" not in source
    assert "roles\": [\"publisher\"]" not in source


def test_read_only_readiness_reuses_gate_logic_without_action_authorization() -> None:
    console = _BoundaryConsole()

    read_only = console.document_readiness("snap-test")

    assert console.role_checks == []
    assert console.technical_evaluations == 1
    assert read_only["technical_blockers"] == ["object_tuple_required"]
    assert read_only["curation_ready"] is True
    assert read_only["publication_ready"] is False

    publisher_view = console.consider_publish(
        actor_id="publisher-1",
        snapshot_id="snap-test",
    )

    assert console.role_checks == [("publisher-1", "publisher")]
    assert console.technical_evaluations == 2
    assert publisher_view == read_only


def test_nonpublisher_cannot_cross_consider_publish_action_boundary() -> None:
    console = _BoundaryConsole()

    with pytest.raises(ConsoleError, match="publisher_role_required"):
        console.consider_publish(actor_id="reviewer-1", snapshot_id="snap-test")

    assert console.role_checks == [("reviewer-1", "publisher")]
    assert console.technical_evaluations == 0


def test_readiness_and_document_status_are_derived_without_workflow_mutation() -> None:
    console = _BoundaryConsole()
    before = deepcopy(console._envelopes)

    readiness = console.document_readiness("snap-test")
    status = console.document_status("snap-test")

    assert readiness["publication_ready"] is False
    assert status == "blocked"
    assert console._envelopes == before
