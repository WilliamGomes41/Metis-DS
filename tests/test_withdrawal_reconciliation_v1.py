"""Focused recovery evidence for Repair 11 withdrawal reconciliation.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery replay
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.durable_publication_console_v1 import DurablePublicationConsole


pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


class _Cursor:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


class _Connection:
    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, sql: str, _params: Any = None) -> _Cursor:
        if "SELECT rel.release_id, rel.status, rel.published_at" in sql:
            return _Cursor(
                {
                    "release_id": "release-withdrawn",
                    "status": "withdrawn",
                    "published_at": "2026-09-16T18:01:00+00:00",
                    "logical_document_id": "logical-doc-1",
                }
            )
        raise AssertionError(f"unexpected SQL: {sql}")


class _Canonical(PostgresCanonicalPublicationStore):
    def __init__(self) -> None:
        pass

    def _connect(self) -> _Connection:
        return _Connection()

    def release_for_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        assert snapshot_id == "snap-withdrawn"
        return {
            "release_id": "release-withdrawn",
            "release_version": "2.0",
            "release_owner": "governance-owner",
            "published_at": "2026-09-16T18:01:00+00:00",
            "snapshot_id": snapshot_id,
            "source_sha256": "2" * 64,
            "source_locator": "g2://sha256/source/2.0.html",
            "objects": [
                {
                    "object_id": "object-b",
                    "object_version": "2.0",
                    "canonical_object_hash": "hash-b",
                    "content_hash": "hash-b",
                    "confirmed_object_type": "explanation",
                }
            ],
        }

    def active_publication_rows(self) -> list[dict[str, Any]]:
        return []


def _console(tmp_path: Path) -> DurablePublicationConsole:
    console = object.__new__(DurablePublicationConsole)
    console.canonical_publication_store = _Canonical()
    console.runtime = tmp_path
    console._envelopes_path = tmp_path / "envelopes.json"
    console._ledger_path = tmp_path / "review_ledger.jsonl"
    console._accounts = {
        "publisher-1": {
            "account_id": "publisher-1",
            "username": "publisher",
            "roles": ["publisher"],
        }
    }
    console._envelopes = {
        "snap-withdrawn": {
            "snapshot_id": "snap-withdrawn",
            "version": "2.0",
            "state": "published",
        }
    }
    console._published_projection_path = lambda: tmp_path / "published_projection.jsonl"  # type: ignore[method-assign]
    console._envelope = lambda snapshot_id: console._envelopes[snapshot_id]  # type: ignore[method-assign]
    return console


def test_reconciliation_projects_canonical_withdrawn_state_locally(tmp_path: Path) -> None:
    console = _console(tmp_path)

    release = console._durable_release_for_snapshot("snap-withdrawn")
    assert release is not None
    assert release["release_status"] == "withdrawn"

    console._apply_local_release_copy(release, [])

    assert console._envelopes["snap-withdrawn"]["state"] == "withdrawn"
    assert (tmp_path / "published_projection.jsonl").read_text(encoding="utf-8") == ""


def test_publish_retry_of_withdrawn_snapshot_fails_closed(tmp_path: Path) -> None:
    console = _console(tmp_path)

    result = console._publish_locked(actor_id="publisher-1", snapshot_id="snap-withdrawn")

    assert result["status"] == "BLOCKED"
    assert result["state"] == "withdrawn"
    assert result["blockers"] == ["release_withdrawn"]
    assert result["cutover"] is False
    assert console._envelopes["snap-withdrawn"]["state"] == "withdrawn"


class _SupersededConnection(_Connection):
    def execute(self, sql: str, _params: Any = None) -> _Cursor:
        if "SELECT rel.release_id, rel.status, rel.published_at" in sql:
            return _Cursor(
                {
                    "release_id": "release-old",
                    "status": "published",
                    "published_at": "2026-09-16T18:00:00+00:00",
                    "logical_document_id": "logical-doc-1",
                }
            )
        if "COUNT(*) AS item_count" in sql:
            return _Cursor(
                {
                    "item_count": 1,
                    "active_same_release": 0,
                    "active_other_release": 1,
                }
            )
        if "SELECT 1" in sql and "rel.published_at>%s" in sql:
            return _Cursor({"exists": 1})
        raise AssertionError(f"unexpected SQL: {sql}")


class _SupersededCanonical(_Canonical):
    def _connect(self) -> _SupersededConnection:
        return _SupersededConnection()

    def release_for_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        assert snapshot_id == "snap-old"
        return {
            "release_id": "release-old",
            "release_version": "1.0",
            "release_owner": "publisher",
            "published_at": "2026-09-16T18:00:00+00:00",
            "snapshot_id": snapshot_id,
            "source_sha256": "1" * 64,
            "source_locator": "g2://sha256/source/1.0.html",
            "objects": [
                {
                    "object_id": "object-old",
                    "object_version": "1.0",
                    "canonical_object_hash": "hash-old",
                    "content_hash": "hash-old",
                    "confirmed_object_type": "explanation",
                }
            ],
        }


def test_publish_retry_of_superseded_snapshot_fails_closed(tmp_path: Path) -> None:
    console = object.__new__(DurablePublicationConsole)
    console.canonical_publication_store = _SupersededCanonical()
    console.runtime = tmp_path
    console._envelopes_path = tmp_path / "envelopes.json"
    console._ledger_path = tmp_path / "review_ledger.jsonl"
    console._accounts = {
        "publisher-1": {
            "account_id": "publisher-1",
            "username": "publisher",
            "roles": ["publisher"],
        }
    }
    console._envelopes = {
        "snap-old": {
            "snapshot_id": "snap-old",
            "version": "1.0",
            "state": "published",
        }
    }
    console._published_projection_path = lambda: tmp_path / "published_projection.jsonl"  # type: ignore[method-assign]
    console._envelope = lambda snapshot_id: console._envelopes[snapshot_id]  # type: ignore[method-assign]

    result = console._publish_locked(actor_id="publisher-1", snapshot_id="snap-old")

    assert result["status"] == "BLOCKED"
    assert result["state"] == "superseded"
    assert result["blockers"] == ["release_superseded"]
    assert result["cutover"] is False
    assert result["local_projection"] == "reconciled"
    assert console._envelopes["snap-old"]["state"] == "superseded"
