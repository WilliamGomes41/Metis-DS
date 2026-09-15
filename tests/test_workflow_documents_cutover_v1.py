"""PostgreSQL document cut-over regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.operations_console_v1 import (
    SNAPSHOT_OBJECT_WRITE_CONFLICT,
    OperationsConsole,
    _objects_jsonl_bytes,
)
from src.workflow_documents_cutover_v1 import (
    PostgresWorkflowDocumentRuntimeStore,
    _PostgresWorkflowDocumentsMixin,
)

ROOT = Path(__file__).resolve().parents[1]


class _SharedDocumentStore:
    def __init__(self) -> None:
        self.envelopes = {
            "snap-a": {"snapshot_id": "snap-a", "family": "old-a"},
            "snap-b": {"snapshot_id": "snap-b", "family": "old-b"},
        }
        self.objects = {
            "snap-a": [{"object_id": "a", "object_version": "1.0"}],
            "snap-b": [{"object_id": "b", "object_version": "1.0"}],
        }
        self.revisions = {"snap-a": "rev-a-1", "snap-b": "rev-b-1"}
        self.lock = threading.Lock()

    def verify_cutover_schema(self) -> None:
        return None

    def list_envelopes(self) -> list[dict[str, Any]]:
        with self.lock:
            return deepcopy(list(self.envelopes.values()))

    def get_envelope(self, snapshot_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.envelopes.get(snapshot_id)
            return deepcopy(row) if row is not None else None

    def list_document_objects(self, snapshot_id: str) -> list[dict[str, Any]]:
        with self.lock:
            return deepcopy(self.objects[snapshot_id])

    def objects_revision(self, snapshot_id: str) -> str:
        with self.lock:
            return self.revisions[snapshot_id]

    def write_bundle(
        self,
        *,
        envelope: dict[str, Any],
        objects: list[dict[str, Any]] | None = None,
        expected_revision: str | None = None,
    ) -> str:
        snapshot_id = str(envelope["snapshot_id"])
        with self.lock:
            if expected_revision is not None and expected_revision != self.revisions[snapshot_id]:
                raise AssertionError("unexpected stale revision")
            self.envelopes[snapshot_id] = deepcopy(envelope)
            if objects is not None:
                self.objects[snapshot_id] = deepcopy(objects)
            return self.revisions[snapshot_id]


class _DocumentConsole(_PostgresWorkflowDocumentsMixin, OperationsConsole):
    pass


def _document_console(
    tmp_path: Path, store: _SharedDocumentStore
) -> _DocumentConsole:
    return _DocumentConsole(
        root=tmp_path,
        runtime=tmp_path / "runtime",
        source_store=tmp_path / "sources",
        workflow_document_store=store,  # type: ignore[arg-type]
    )


def test_cutover_revision_preserves_object_order() -> None:
    rows = [
        {"object_id": "z", "object_version": "1.0", "text": "first"},
        {"object_id": "a", "object_version": "1.0", "text": "second"},
    ]
    expected = hashlib.sha256(_objects_jsonl_bytes(rows)).hexdigest()
    assert PostgresWorkflowDocumentRuntimeStore._revision(rows) == expected
    assert PostgresWorkflowDocumentRuntimeStore._revision(list(reversed(rows))) != expected


def test_cutover_schema_preserves_full_envelope_and_object_position() -> None:
    sql = (ROOT / "db" / "migrations" / "003_workflow_document_envelope_payload.sql").read_text(encoding="utf-8")
    assert "envelope_payload JSONB" in sql
    assert "position INTEGER" in sql


def test_cutover_is_explicit_and_never_runs_legacy_migration_on_startup() -> None:
    asgi = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert "METIS_WORKFLOW_DOCUMENT_STORE" in asgi
    assert "workflow_identity_store_required_for_document_store" in asgi
    assert "migrate_legacy_runtime" not in asgi
    assert "prepare_legacy_cutover" not in asgi


def test_cutover_runtime_reads_objects_by_migrated_position() -> None:
    source = (ROOT / "src" / "workflow_documents_cutover_v1.py").read_text(encoding="utf-8")
    assert "ORDER BY position" in source
    assert "workflow_document_cutover_not_prepared" in source
    assert "expected_revision" in source
    assert SNAPSHOT_OBJECT_WRITE_CONFLICT == "snapshot_object_write_conflict"


def test_local_files_are_declared_compatibility_mirrors_not_authority() -> None:
    source = (ROOT / "src" / "workflow_documents_cutover_v1.py").read_text(encoding="utf-8")
    assert "compatibility mirror" in source
    assert "authoritative in PostgreSQL" in source


def test_two_console_process_models_rebase_distinct_envelope_commits(tmp_path: Path) -> None:
    """Independent worker caches cannot erase another worker's committed key."""
    store = _SharedDocumentStore()
    first = _document_console(tmp_path, store)
    second = _document_console(tmp_path, store)
    prepared_a = deepcopy(first._envelopes)
    prepared_b = deepcopy(second._envelopes)
    prepared_a["snap-a"]["family"] = "new-a"
    prepared_b["snap-b"]["family"] = "new-b"
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def commit(console: _DocumentConsole, snapshot_id: str, prepared: dict[str, Any]) -> None:
        try:
            barrier.wait(timeout=5)
            console._commit_prepared_store(
                envelopes=prepared,
                snapshot_id=snapshot_id,
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [
        threading.Thread(target=commit, args=(first, "snap-a", prepared_a)),
        threading.Thread(target=commit, args=(second, "snap-b", prepared_b)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    assert errors == []
    assert store.envelopes["snap-a"]["family"] == "new-a"
    assert store.envelopes["snap-b"]["family"] == "new-b"


def test_authoritative_object_read_replaces_stale_worker_revision(tmp_path: Path) -> None:
    store = _SharedDocumentStore()
    console = _document_console(tmp_path, store)
    console._load_objects("snap-a", remember=True)
    assert console._objects_expected_revs()["snap-a"] == "rev-a-1"
    store.revisions["snap-a"] = "rev-a-2"
    console._load_objects("snap-a", remember=True)
    assert console._objects_expected_revs()["snap-a"] == "rev-a-2"
