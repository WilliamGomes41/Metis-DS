"""PostgreSQL document cut-over regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.operations_console_v1 import (
    SNAPSHOT_OBJECT_WRITE_CONFLICT,
    OperationsConsole,
    _objects_jsonl_bytes,
)
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_documents_cutover_v1 import (
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
        self.object_reads = 0
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
            self.object_reads += 1
            return deepcopy(self.objects[snapshot_id])

    @staticmethod
    def _revision(rows: list[dict[str, Any]]) -> str:
        return PostgresWorkflowDocumentRuntimeStore._revision(rows)

    def revision_for_rows(self, rows: list[dict[str, Any]]) -> str:
        return self._revision(rows)

    def objects_revision(self, snapshot_id: str) -> str:
        with self.lock:
            return self._revision(self.objects[snapshot_id])

    def write_bundle(
        self,
        *,
        envelope: dict[str, Any],
        objects: list[dict[str, Any]] | None = None,
        expected_revision: str | None = None,
    ) -> str:
        snapshot_id = str(envelope["snapshot_id"])
        with self.lock:
            current_revision = self._revision(self.objects[snapshot_id])
            if expected_revision is not None and expected_revision != current_revision:
                raise AssertionError("unexpected stale revision")
            self.envelopes[snapshot_id] = deepcopy(envelope)
            if objects is not None:
                self.objects[snapshot_id] = deepcopy(objects)
            return self._revision(self.objects[snapshot_id])


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


def test_concurrent_store_revision_for_rows_uses_object_aware_token() -> None:
    rows = [
        {"object_id": "a", "object_version": "1.0", "text": "A"},
        {"object_id": "b", "object_version": "1.0", "text": "B"},
    ]
    store = object.__new__(PostgresConcurrentWorkflowDocumentStore)

    revision = store.revision_for_rows(rows)

    assert revision.startswith(PostgresConcurrentWorkflowDocumentStore.REVISION_PREFIX)
    assert revision != PostgresWorkflowDocumentRuntimeStore._revision(rows)


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
    source = (ROOT / "src" / "workflows" / "workflow_documents_cutover_v1.py").read_text(encoding="utf-8")
    assert "ORDER BY position" in source
    assert "workflow_document_cutover_not_prepared" in source
    assert "expected_revision" in source
    assert SNAPSHOT_OBJECT_WRITE_CONFLICT == "snapshot_object_write_conflict"


def test_local_files_are_declared_compatibility_mirrors_not_authority() -> None:
    source = (ROOT / "src" / "workflows" / "workflow_documents_cutover_v1.py").read_text(encoding="utf-8")
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


def test_snapshot_objects_and_revision_uses_one_authoritative_object_fetch(tmp_path: Path) -> None:
    store = _SharedDocumentStore()
    store.objects["snap-a"] = [
        {"object_id": f"a-{index:03d}", "object_version": "1.0", "text": f"row-{index}"}
        for index in range(250)
    ]
    expected_objects = deepcopy(store.objects["snap-a"])
    expected_revision = PostgresWorkflowDocumentRuntimeStore._revision(expected_objects)
    console = _document_console(tmp_path, store)
    store.object_reads = 0

    objects, revision = console.snapshot_objects_and_revision("snap-a", include_blocked=True)

    assert store.object_reads == 1
    assert objects == expected_objects
    assert revision == expected_revision


def test_snapshot_objects_and_revision_uses_store_concurrency_token(tmp_path: Path) -> None:
    store = _SharedDocumentStore()
    store.revision_for_rows = lambda _rows: "m2.object-aware"  # type: ignore[method-assign]
    console = _document_console(tmp_path, store)
    store.object_reads = 0

    _objects, revision = console.snapshot_objects_and_revision("snap-a", include_blocked=True)

    assert store.object_reads == 1
    assert revision == "m2.object-aware"


def test_authoritative_object_read_replaces_stale_worker_revision(tmp_path: Path) -> None:
    store = _SharedDocumentStore()
    console = _document_console(tmp_path, store)
    console._load_objects("snap-a", remember=True)
    first_revision = PostgresWorkflowDocumentRuntimeStore._revision(store.objects["snap-a"])
    assert console._objects_expected_revs()["snap-a"] == first_revision

    store.objects["snap-a"][0]["object_version"] = "2.0"
    console._load_objects("snap-a", remember=True)
    next_revision = PostgresWorkflowDocumentRuntimeStore._revision(store.objects["snap-a"])

    assert next_revision != first_revision
    assert console._objects_expected_revs()["snap-a"] == next_revision


def test_separate_authoritative_snapshot_reads_detect_intervening_change(tmp_path: Path) -> None:
    store = _SharedDocumentStore()
    console = _document_console(tmp_path, store)
    store.object_reads = 0

    first_objects, first_revision = console.snapshot_objects_and_revision("snap-a", include_blocked=True)
    store.objects["snap-a"][0] = {"object_id": "a", "object_version": "2.0"}
    second_objects, second_revision = console.snapshot_objects_and_revision("snap-a", include_blocked=True)

    assert store.object_reads == 2
    assert first_objects != second_objects
    assert first_revision != second_revision


def test_postgres_document_startup_ignores_corrupt_envelope_mirror_and_repairs_it(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "envelopes.json").write_text('{"broken":', encoding="utf-8")
    store = _SharedDocumentStore()

    console = _document_console(tmp_path, store)

    assert {row["snapshot_id"] for row in console.list_envelopes()} == {"snap-a", "snap-b"}
    repaired = json.loads((runtime / "envelopes.json").read_text(encoding="utf-8"))
    assert set(repaired) == {"snap-a", "snap-b"}


def test_local_only_startup_still_fails_closed_on_corrupt_envelope_json(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "local-runtime"
    runtime.mkdir(parents=True)
    (runtime / "envelopes.json").write_text('{"broken":', encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        OperationsConsole(
            root=tmp_path,
            runtime=runtime,
            source_store=tmp_path / "local-sources",
        )


@pytest.mark.parametrize('fail_commit', [True, False])
def test_delete_source_cleanup_follows_transaction_commit_and_restart(tmp_path, fail_commit):
    """Real console/mixin/transaction code with a rollback-capable store double."""
    from contextlib import contextmanager
    from types import SimpleNamespace
    from src.g2_source_store import build_g2_locator
    from src.operations_console_v1 import ConsoleError
    from src.workflows.workflow_transaction_v1 import workflow_transaction, workflow_transaction_active

    class Source:
        def __init__(self):
            self.blobs = {}
            self.deletes = 0

        def store_verified(self, *, data, sha256, filename):
            locator = build_g2_locator(sha256=sha256, filename=filename)
            self.blobs[locator] = data
            return locator

        def load_verified(self, locator):
            return self.blobs[locator]

        def delete_verified(self, locator):
            assert not workflow_transaction_active(), 'source deletion before outer commit'
            self.deletes += 1
            return self.blobs.pop(locator, None) is not None

    class Store(_SharedDocumentStore):
        config = SimpleNamespace(dsn='test-double')

        def delete_document(self, snapshot_id):
            del self.envelopes[snapshot_id]
            del self.objects[snapshot_id]

        @contextmanager
        def _connect(self):
            yield self

        @contextmanager
        def transaction(self):
            before = deepcopy(self.envelopes), deepcopy(self.objects)
            try:
                yield
                if fail_commit:
                    raise RuntimeError('injected_commit_failure')
            except Exception:
                self.envelopes, self.objects = before
                raise

    source = Source()
    local = OperationsConsole(root=tmp_path, runtime=tmp_path/'runtime', source_store=tmp_path/'sources', immutable_source_store=source)
    actor = local.create_account('delete-author', 'test-password', ('researcher', 'reviewer'))
    reviewer = local.create_account('delete-reviewer', 'test-password', ('reviewer',))
    receipt = local.ingest(actor_id=actor['account_id'], filename='source.html',
                           data=b'<html><h1>Bron</h1><p>Bespreek passende ondersteuning met de client.</p></html>',
                           content_type='text/html', ingest_kind='new', title='Bron', version='1.0',
                           date='2026-09-30', live_url='', class_='richtlijn', family='test',
                           named_reviewers=[reviewer['account_id']])
    sid = receipt['snapshot_id']
    store = Store()
    store.envelopes = deepcopy(local._envelopes)
    store.objects = {sid: deepcopy(local._load_objects(sid))}
    def restart():
        return _DocumentConsole(root=tmp_path, runtime=tmp_path/'runtime', source_store=tmp_path/'sources',
                                immutable_source_store=source, workflow_document_store=store)
    console = restart()
    locator = console._envelope(sid)['immutable_storage_locator']
    original = source.load_verified(locator)
    command = dict(actor_id=actor['account_id'], snapshot_id=sid, confirmed=True, confirm_title='Bron')
    if fail_commit:
        with pytest.raises(RuntimeError, match='injected_commit_failure'):
            console.delete_unpublished_snapshot(**command)
        assert source.deletes == 0
        console = restart()
        assert console._envelope(sid)['snapshot_id'] == sid
        assert source.load_verified(locator) == original
        assert console.snapshot_objects(sid)
    else:
        # A nested transaction is rejected before it can mutate domain state.
        with workflow_transaction(store):
            with pytest.raises(ConsoleError, match='unpublished_delete_requires_independent_transaction'):
                console.delete_unpublished_snapshot(**command)
            assert store.get_envelope(sid) is not None
            assert source.deletes == 0
        result = console.delete_unpublished_snapshot(**command)
        assert result['deleted'] and result['freeze_bytes_removed']
        assert source.deletes == 1 and locator not in source.blobs
        console = restart()
        assert console.list_envelopes() == []
        with pytest.raises(ConsoleError, match='unknown_snapshot'):
            console.delete_unpublished_snapshot(**command)
        assert source.deletes == 1
