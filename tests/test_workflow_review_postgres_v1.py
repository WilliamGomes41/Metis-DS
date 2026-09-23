"""PostgreSQL review authority regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from src.operations_console_v1 import OperationsConsole
from src.review_ledger import (
    append_event,
    buffer_events,
    read_events,
    register_backend,
    unregister_backend,
    verify_ledger,
)
from src.workflows.workflow_review_cutover_v1 import _PostgresWorkflowReviewMixin
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore, WorkflowReviewStoreError

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


class FakeAuthoritativeReviewStore:
    def __init__(self, events: list[dict], bindings: dict[str, list[dict]]) -> None:
        self.events = events
        self.bindings = bindings

    def read_events(self) -> list[dict]:
        return list(self.events)

    def read_bindings(self) -> dict[str, list[dict]]:
        return {snapshot_id: list(rows) for snapshot_id, rows in self.bindings.items()}


class _ReviewStartupConsole(_PostgresWorkflowReviewMixin, OperationsConsole):
    pass


class _StartupReviewStore(FakeAuthoritativeReviewStore):
    def verify_review_schema(self) -> None:
        return None

    def bind_ledger_mirror(self, path: Path) -> None:
        self.mirror_path = path


class _Rows:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict]:
        return self._rows


class _Connection:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _query: str) -> _Rows:
        return _Rows(self._rows)


def _event_chain(count: int) -> list[dict]:
    events: list[dict] = []
    previous = None
    for index in range(count):
        event = PostgresWorkflowReviewStore._new_event(
            event_type="review_approve",
            object_id=f"obj-{index}",
            object_version="1.0",
            actor="reviewer",
            details={"snapshot_id": "snap-1"},
            previous_event_hash=previous,
        )
        events.append(event)
        previous = event["event_hash"]
    return events


def _remirror_subject(
    tmp_path: Path,
    *,
    events: list[dict],
    bindings: dict[str, list[dict]],
) -> _PostgresWorkflowReviewMixin:
    subject = object.__new__(_PostgresWorkflowReviewMixin)
    subject.workflow_review_store = FakeAuthoritativeReviewStore(events, bindings)
    subject._ledger_path = tmp_path / "review_ledger.jsonl"
    subject._bindings_path = tmp_path / "publish_authorizations.json"
    subject._bindings = {}
    return subject


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
    path.write_text(json.dumps(first, sort_keys=True) + "\n", encoding="utf-8")
    assert PostgresWorkflowReviewStore._read_legacy_events(path) == [first]
    broken = dict(first)
    broken["actor"] = "changed"
    path.write_text(json.dumps(broken, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(WorkflowReviewStoreError):
        PostgresWorkflowReviewStore._read_legacy_events(path)


def test_boot_remirror_replaces_stale_subset_mirrors_from_postgres(tmp_path: Path) -> None:
    events = _event_chain(3)
    bindings = {"snap-1": [{"decision": "approve", "valid": True}]}
    subject = _remirror_subject(tmp_path, events=events, bindings=bindings)
    subject._ledger_path.write_text(
        json.dumps(events[0], ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    subject._bindings_path.write_text(json.dumps({"stale": []}) + "\n", encoding="utf-8")

    current = subject._remirror_review_runtime()

    assert current == bindings
    assert PostgresWorkflowReviewStore._read_legacy_events(subject._ledger_path) == events
    assert json.loads(subject._bindings_path.read_text(encoding="utf-8")) == bindings


def test_boot_remirror_creates_missing_mirrors_from_postgres(tmp_path: Path) -> None:
    events = _event_chain(3)
    bindings = {"snap-1": [{"decision": "approve", "valid": True}]}
    subject = _remirror_subject(tmp_path, events=events, bindings=bindings)

    current = subject._remirror_review_runtime()

    assert current == bindings
    assert PostgresWorkflowReviewStore._read_legacy_events(subject._ledger_path) == events
    assert json.loads(subject._bindings_path.read_text(encoding="utf-8")) == bindings


def test_postgres_event_payload_missing_still_fails_closed() -> None:
    store = object.__new__(PostgresWorkflowReviewStore)
    store._connect = lambda: _Connection([{"event_payload": None}])

    with pytest.raises(WorkflowReviewStoreError, match="workflow_review_cutover_not_prepared"):
        store.read_events()


def test_authorization_read_preserves_complete_exact_payload() -> None:
    payload = {
        "object_id": "obj-1",
        "object_version": "1.0",
        "canonical_object_hash": "a" * 64,
        "confirmed_object_type": "recommendation",
        "reviewer": "Reviewer",
        "reviewer_id": "acc-reviewer",
        "decision": "approve",
        "valid": True,
        "suitability": "ja",
        "eindoordeel": "goedkeuren",
        "documentpositie": {"path": ["Preventie"]},
    }
    row = {
        "snapshot_id": "snap-1",
        "object_id": payload["object_id"],
        "object_version": payload["object_version"],
        "canonical_object_hash": payload["canonical_object_hash"],
        "confirmed_object_type": payload["confirmed_object_type"],
        "reviewer_display_name": payload["reviewer"],
        "reviewer_account_id": payload["reviewer_id"],
        "decision": payload["decision"],
        "valid": payload["valid"],
        "authorization_payload": json.dumps(payload),
    }
    store = object.__new__(PostgresWorkflowReviewStore)
    store._connect = lambda: _Connection([row])

    assert store.read_bindings() == {"snap-1": [payload]}


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
    assert "_remirror_review_runtime" in source
    assert "_atomic_replace_bytes(self._ledger_path" in source
    assert "_assert_review_cutover_prepared" not in source
    assert "_mirror_bindings" in source


def test_postgres_review_startup_ignores_corrupt_binding_mirror_and_repairs_it(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "review-runtime"
    runtime.mkdir(parents=True)
    (runtime / "publish_authorizations.json").write_text('{"broken":', encoding="utf-8")
    events = _event_chain(1)
    bindings = {"snap-1": [{"decision": "approve", "valid": True}]}
    store = _StartupReviewStore(events, bindings)

    console = _ReviewStartupConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=runtime,
        workflow_review_store=store,  # type: ignore[arg-type]
    )

    assert console._bindings == bindings
    assert json.loads(
        (runtime / "publish_authorizations.json").read_text(encoding="utf-8")
    ) == bindings
    assert PostgresWorkflowReviewStore._read_legacy_events(
        runtime / "review_ledger.jsonl"
    ) == events
