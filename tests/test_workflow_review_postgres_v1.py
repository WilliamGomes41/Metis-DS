"""PostgreSQL review authority regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from src.review_ledger import (
    append_event,
    buffer_events,
    read_events,
    register_backend,
    unregister_backend,
    verify_ledger,
)
from src.workflow_review_postgres_v1 import PostgresWorkflowReviewStore, WorkflowReviewStoreError

ROOT = Path(__file__).resolve().parents[1]


class FakeLedgerBackend:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.pending: list[dict] | None = None

    def read_events(self) -> list[dict]:
        return list(self.events)

    def append_event(self, **kwargs):
        previous = None
        target = self.pending if self.pending is not None else self.events
        if target:
            previous = target[-1]["event_hash"]
        elif self.events:
            previous = self.events[-1]["event_hash"]
        event = PostgresWorkflowReviewStore._new_event(
            previous_event_hash=previous,
            **kwargs,
        )
        target.append(event)
        return event

    @contextmanager
    def buffered(self):
        if self.pending is not None:
            yield
            return
        self.pending = []
        try:
            yield
        except Exception:
            raise
        else:
            self.events.extend(self.pending)
        finally:
            self.pending = None


def test_review_ledger_backend_keeps_existing_api_and_buffer_rollback(tmp_path: Path) -> None:
    path = tmp_path / "review_ledger.jsonl"
    backend = FakeLedgerBackend()
    register_backend(path, backend)
    try:
        append_event(
            path,
            event_type="review_approve",
            object_id="obj-1",
            object_version="1.0",
            actor="reviewer",
            details={"snapshot_id": "snap-1"},
        )
        assert len(read_events(path)) == 1
        with pytest.raises(RuntimeError):
            with buffer_events(path):
                append_event(
                    path,
                    event_type="review_revise",
                    object_id="obj-1",
                    object_version="1.0",
                    actor="reviewer",
                    details={"snapshot_id": "snap-1"},
                )
                raise RuntimeError("rollback")
        assert len(read_events(path)) == 1
        assert verify_ledger(path) == []
    finally:
        unregister_backend(path)


def test_legacy_review_chain_is_verified_without_rewriting(tmp_path: Path) -> None:
    path = tmp_path / "review_ledger.jsonl"
    first = PostgresWorkflowReviewStore._new_event(
        event_type="x",
        object_id="o",
        object_version="1",
        actor="migration",
        details={},
        previous_event_hash=None,
    )
    path.write_text(__import__("json").dumps(first, sort_keys=True) + "\n", encoding="utf-8")
    assert PostgresWorkflowReviewStore._read_legacy_events(path) == [first]
    broken = dict(first)
    broken["actor"] = "changed"
    path.write_text(__import__("json").dumps(broken, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(WorkflowReviewStoreError):
        PostgresWorkflowReviewStore._read_legacy_events(path)


def test_review_schema_preserves_exact_payload_and_authorization_order() -> None:
    sql = (ROOT / "db" / "migrations" / "004_workflow_review_authority.sql").read_text(encoding="utf-8")
    assert "event_payload JSONB" in sql
    assert "actor_text TEXT" in sql
    assert "position INTEGER" in sql
    assert "actor_account_id DROP NOT NULL" in sql
    assert "snapshot_id DROP NOT NULL" in sql


def test_review_cutover_is_explicit_and_prerequisite_bound() -> None:
    asgi = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert "METIS_WORKFLOW_REVIEW_STORE" in asgi
    assert "workflow_identity_store_required_for_review_store" in asgi
    assert "workflow_document_store_required_for_review_store" in asgi
    assert "migrate_legacy_runtime" not in asgi


def test_review_runtime_buffers_events_and_keeps_local_files_as_mirrors() -> None:
    source = (ROOT / "src" / "workflow_review_cutover_v1.py").read_text(encoding="utf-8")
    assert "buffer_events(self._ledger_path)" in source
    assert "workflow_review_store.replace_snapshot_bindings" in source
    assert "workflow_review_store.replace_bindings" not in source
    assert "workflow_review_cutover_not_prepared" in source
    assert "_mirror_bindings" in source
