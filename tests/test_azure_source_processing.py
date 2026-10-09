"""Azure-owned lifecycle: native claim/recovery, pure readers and fail-closed composition.
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event
import shutil

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.processing_retry_v1 import now
from tests.test_availability_repair import accounts, bind, provider, installed_app, login, drain, state
from tests.test_review_batch_atomic_postgres import _console
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


class ImmutableBlobFixture:
    """Synthetic cloud boundary; native PostgreSQL is real, Azure is not contacted."""
    def __init__(self):
        self.blobs = {}
        self.reads = 0

    def store_verified(self, *, data, sha256, filename):
        from src.g2_source_store import build_g2_locator
        locator = build_g2_locator(sha256=sha256, filename=filename)
        self.blobs[locator] = bytes(data)
        return locator

    def load_verified(self, locator):
        from src.g2_source_store import G2SourceStoreError
        self.reads += 1
        if locator not in self.blobs:
            raise G2SourceStoreError("canonical_source_missing")
        return self.blobs[locator]


def received(console, calls=None):
    author, reviewer = accounts(console)
    def post(*args):
        if calls is not None:
            calls.append(1)
        return provider(*args)
    bind(console, post)
    receipt = console.receive_source(actor_id=author, filename="fixture.html",
        data=b"<html><body><p>Gebruik geen zalf.</p></body></html>", content_type="text/html",
        ingest_kind="new", title="Fixture", version="1", date="2026-10-09", live_url="",
        class_="richtlijn", family="fixture", named_reviewers=[author, reviewer], command_id="receipt")
    return author, reviewer, receipt["snapshot_id"]


def reserve(console, author, sid, command="start"):
    return console.reserve_source_selection(actor_id=author, snapshot_id=sid, command_id=command,
                                            expected_revision=console.objects_revision(sid))


def test_restart_recovers_pending_sql_command_after_http_wake_failure_without_files(workflow_postgres, tmp_path, monkeypatch):
    calls = []
    first = _console(tmp_path / "first", workflow_postgres)
    blob = ImmutableBlobFixture()
    first.immutable_source_store = blob
    author, _, sid = received(first)
    from src.source_processing_dispatch_v1 import SourceProcessingDispatcher
    app = installed_app(first)
    with monkeypatch.context() as patch, TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as client:
        login(client)
        def lost_wake(*args):
            raise RuntimeError("request_lost_after_durable_reservation")
        patch.setattr(SourceProcessingDispatcher, "notify", lost_wake)
        response = client.post("/source-selection/start", data={"document": sid, "command_id": "start",
            "expected_revision": first.objects_revision(sid)}, follow_redirects=False)
        assert response.status_code == 500
    attempt = first._envelope(sid)["processing_attempts"][-1]
    assert attempt["dispatch"]["state"] == "pending"
    assert first.snapshot_objects(sid) == []
    shutil.rmtree(tmp_path / "first")  # every cache/mirror is disposable
    second = _console(tmp_path / "second", workflow_postgres)
    second.immutable_source_store = blob
    def post(*args):
        calls.append(1)
        return provider(*args)
    bind(second, post)
    app = installed_app(second)
    with TestClient(app, base_url="https://testserver") as client:
        drain(client, app)
        login(client)
        assert "Status: voltooid" in client.get("/source-selection", params={"document": sid}).text
    final = _console(tmp_path / "third", workflow_postgres)
    final.immutable_source_store = blob
    assert final._envelope(sid)["processing_attempts"][-1]["command_id"] == "start"
    assert final._envelope(sid)["processing_attempts"][-1]["dispatch"]["state"] == "claimed"
    assert final._envelope(sid)["processing_attempts"][-1]["state"] == "succeeded"
    assert calls == [1] and blob.reads >= 2
    assert final._verified_source_bytes(final._envelope(sid))[1].startswith(b"<html>")


def test_native_two_kernels_claim_one_attempt_and_writer_remains_available(workflow_postgres, tmp_path):
    from contextlib import contextmanager
    from time import perf_counter, sleep
    import json
    import psycopg
    from psycopg.rows import dict_row
    from src.workflows.workflow_transaction_v1 import _ACTIVE_CONNECTION
    entered, release = Event(), Event()
    claim_held, release_claim, waiter_started = Event(), Event(), Event()
    records, holder, waiter = [], {}, {}
    first = _console(tmp_path / "first", workflow_postgres)
    blob = ImmutableBlobFixture()
    first.immutable_source_store = blob
    author, _, sid = received(first)
    attempt, _ = reserve(first, author, sid)
    second = _console(tmp_path / "second", workflow_postgres)
    second.immutable_source_store = blob
    calls = []
    def observe(pid):
        with psycopg.connect(workflow_postgres.dsn, autocommit=True, row_factory=dict_row) as observer:
            activity = observer.execute(
                "SELECT EXTRACT(EPOCH FROM clock_timestamp()-xact_start)::float AS transaction_age_seconds, "
                "pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE pid=%s", (pid,)).fetchone()
            locks = observer.execute(
                "SELECT count(*) AS count FROM pg_locks WHERE pid=%s AND granted "
                "AND relation='workflow.documents'::regclass", (pid,)).fetchone()["count"]
            return {"transaction_age_seconds": activity["transaction_age_seconds"] if activity else None,
                    "blockers": activity["blockers"] if activity else [], "document_locks": locks}
    for console in (first, second):
        boundary = console._reprocessing_transaction
        @contextmanager
        def measured(sid, _boundary=boundary, _console=console):
            start = perf_counter()
            acquired = None
            pid = None
            try:
                with _boundary(sid):
                    acquired = perf_counter()
                    pid = _ACTIVE_CONNECTION.get().info.backend_pid
                    sample = observe(pid)
                    assert sample["transaction_age_seconds"] is not None
                    assert sample["document_locks"] > 0
                    if _console is first and not holder:
                        holder.update(pid=pid, acquired=acquired, sample=sample)
                        claim_held.set()
                        assert release_claim.wait(10)
                    yield
            finally:
                # Outside the context: outer transaction has committed/rolled
                # back and the real PostgreSQL connection has released locks.
                finished = perf_counter()
                if pid is not None:
                    after = observe(pid)
                    assert after["document_locks"] == 0
                    assert after["transaction_age_seconds"] is None
                    records.append({"backend_pid": pid,
                        "boundary_through_commit_seconds": finished-start,
                        "acquired_to_post_commit_seconds": finished-acquired,
                        "database_sample": sample, "post_commit_sample": after})
        console._reprocessing_transaction = measured
        if not hasattr(console, "_source_processing_strategy"):
            bind(console, provider)
        original = console._fragments_and_spec
        def paused(*args, _original=original, **kwargs):
            from src.workflows.workflow_transaction_v1 import workflow_transaction_active
            assert not workflow_transaction_active()
            calls.append(1)
            entered.set()
            assert release.wait(10)
            return _original(*args, **kwargs)
        console._fragments_and_spec = paused
    def contend_same_row():
        with psycopg.connect(workflow_postgres.dsn) as connection:
            connection.execute("SET lock_timeout='5s'")
            waiter["pid"] = connection.info.backend_pid
            waiter_started.set()
            connection.execute("SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE", (sid,))
        return True
    def write_same_row():
        with psycopg.connect(workflow_postgres.dsn) as connection:
            connection.execute("SET lock_timeout='1s'")
            # Actual committed SQL writer on the same aggregate while provider
            # is paused, without changing any domain identity/content/review.
            connection.execute("UPDATE workflow.documents SET title=title WHERE snapshot_id=%s", (sid,))
        return True
    with ThreadPoolExecutor(3) as pool:
        work = pool.submit(first.execute_source_selection, actor_id=author, snapshot_id=sid, attempt=attempt)
        try:
            assert claim_held.wait(5)
            contender = pool.submit(contend_same_row)
            assert waiter_started.wait(2)
            deadline = perf_counter()+3
            blocking = observe(waiter["pid"])
            while holder["pid"] not in blocking["blockers"] and perf_counter() < deadline:
                sleep(.01)
                blocking = observe(waiter["pid"])
            assert holder["pid"] in blocking["blockers"]
            locked_sample = observe(holder["pid"])
            assert locked_sample["document_locks"] > 0
            assert locked_sample["transaction_age_seconds"] > 0
            assert not contender.done()
            release_claim.set()
            assert contender.result(timeout=3)
            assert entered.wait(5)
            # Independent observer sees the claim connection already released;
            # long preparation holds no workflow.documents lock.
            assert observe(holder["pid"])["document_locks"] == 0
            assert pool.submit(write_same_row).result(timeout=2)
            duplicate = pool.submit(second.execute_source_selection, actor_id=author, snapshot_id=sid, attempt=attempt)
            duplicate.result(timeout=2)
            pool.submit(second.create_account, username="independent", password="fixture", roles=("researcher",)).result(timeout=2)
            assert calls == [1]
        finally:
            release_claim.set()
            release.set()
            work.result(timeout=10)
    assert second._envelope(sid)["processing_attempts"][-1]["state"] == "succeeded"
    assert len(second._envelope(sid)["processing_attempts"]) == 1
    assert records and max(r["boundary_through_commit_seconds"] for r in records) < 5
    print("NATIVE_LOCK_EVIDENCE=" + json.dumps({
        "measurement_version": "postgres-lock-through-commit-v2",
        "transactions": len(records),
        "max_boundary_through_commit_seconds": max(r["boundary_through_commit_seconds"] for r in records),
        "max_acquired_to_post_commit_seconds": max(r["acquired_to_post_commit_seconds"] for r in records),
        "held_database_sample": locked_sample, "blocked_waiter_sample": blocking,
        "same_row_writer_committed_during_preparation": True,
        "provider_calls": len(calls), "records": records}))


def test_changed_strategy_fails_before_provider_and_preserves_receipt(tmp_path):
    console = state(tmp_path)
    calls = []
    author, _, sid = received(console, calls)
    attempt, _ = reserve(console, author, sid)
    console._processing_configuration_reader = lambda: {"mode": "different", "model": "different"}
    with pytest.raises(ConsoleError, match="processing_configuration_changed"):
        console.execute_source_selection(actor_id=author, snapshot_id=sid, attempt=attempt)
    stored = console._envelope(sid)
    assert stored["processing_attempts"][-1]["state"] == "failed"
    assert stored["processing_attempts"][-1]["error_code"] == "processing_configuration_changed"
    assert console.snapshot_objects(sid) == [] and calls == []
    assert console._verified_source_bytes(stored)[1]


def test_expired_pending_command_is_interrupted_not_automatically_retried(tmp_path, monkeypatch):
    from src.source_processing_dispatch_v1 import pending
    console = state(tmp_path)
    calls = []
    author, _, sid = received(console, calls)
    attempt, _ = reserve(console, author, sid)
    future = datetime.fromisoformat(attempt["expires_at"]) + timedelta(seconds=1)
    monkeypatch.setattr("src.source_processing_dispatch_v1.now", lambda: future)
    assert pending(console) == []
    assert console._envelope(sid)["processing_attempts"][-1]["state"] == "interrupted"
    assert console._envelope(sid)["processing_attempts"][-1]["command_id"] == "start"
    assert calls == []


def test_binding_never_replaces_methods_or_reader_and_catalog_calls_no_provider(tmp_path):
    from tests.test_pre_review_semantic_v1 import _fragment
    from src.operations_console_v1 import OperationsConsole
    class Catalog(OperationsConsole):
        def source_fragment_catalog(self):
            return self._deterministic_fragments_and_spec("html", tmp_path/"source.html", data=b"x",
                document_id="doc", source_id="src", title="T", family="F", class_="richtlijn")[0]
    console = Catalog(root=tmp_path, source_store=tmp_path/"sources", runtime=tmp_path/"runtime")
    console._extract = lambda *args, **kwargs: [_fragment("p1", "Gebruik geen zalf.")]
    def forbidden(*args):
        raise AssertionError("read invoked model")
    bind(console, forbidden)
    assert "_fragments_and_spec" not in console.__dict__
    assert "source_fragment_catalog" not in console.__dict__
    assert console.source_fragment_catalog()


def test_azure_cannot_use_local_workflow_fallback(monkeypatch):
    from src.console_asgi import _require_azure_workflow_authorities
    monkeypatch.setenv("WEBSITE_SITE_NAME", "synthetic")
    for missing in range(4):
        stores = [object()] * 4
        stores[missing] = None
        with pytest.raises(RuntimeError, match="azure_workflow_authorities_required"):
            _require_azure_workflow_authorities(*stores)
    _require_azure_workflow_authorities(*([object()] * 4))


def test_native_receipt_requires_blob_readback_even_with_valid_cache(workflow_postgres, tmp_path):
    console = _console(tmp_path, workflow_postgres)
    blob = ImmutableBlobFixture()
    console.immutable_source_store = blob
    _, _, sid = received(console)
    stored = deepcopy(console._envelope(sid))
    assert blob.reads >= 1
    blob.blobs.clear()
    with pytest.raises(ConsoleError, match="immutable_source_recovery_failed"):
        console._durable_receipt(stored)
    assert console._envelope(sid)["sha256"] == stored["sha256"]


def test_native_simultaneous_receipts_and_distinct_successor_commands(workflow_postgres, tmp_path):
    from threading import Barrier
    first = _console(tmp_path / "first", workflow_postgres)
    author, reviewer = accounts(first)
    blob = ImmutableBlobFixture()
    first.immutable_source_store = blob
    second = _console(tmp_path / "second", workflow_postgres)
    second.immutable_source_store = blob
    command = dict(actor_id=author, filename="fixture.html",
        data=b"<html><body><p>Gebruik geen zalf.</p></body></html>", content_type="text/html",
        ingest_kind="new", title="Fixture", version="1", date="2026-10-09", live_url="",
        class_="richtlijn", family="fixture", named_reviewers=[author, reviewer])
    def together(operation, commands):
        barrier = Barrier(2)
        def invoke(console, command):
            barrier.wait(timeout=5)
            try:
                return ("ok", getattr(console, operation)(**command))
            except ConsoleError as error:
                return ("error", error.code)
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(invoke, console, command)
                       for console, command in zip((first, second), commands)]
            return [future.result(timeout=10) for future in futures]
    identical = together("receive_source", [{**command, "command_id": "double-click"}]*2)
    assert [row[0] for row in identical] == ["ok", "ok"]
    assert identical[0][1]["snapshot_id"] == identical[1][1]["snapshot_id"]
    assert len(first.list_envelopes()) == 1
    conflicting = together("receive_source", [
        {**command, "command_id": "conflicting-receipt", "title": title} for title in ("First", "Second")])
    assert sorted(row[0] for row in conflicting) == ["error", "ok"]
    # Both the command guard and a losing database CAS refuse the conflicting
    # payload. The invariant is refusal with one durable identity, not which
    # concurrency boundary detects it first.
    assert next(row[1] for row in conflicting if row[0] == "error") in {
        "ingest_command_conflict", "snapshot_object_write_conflict"}
    winner = next(row[1] for row in conflicting if row[0] == "ok")
    accepted_title = first._envelope(winner["snapshot_id"])["title"]
    rejected_title = "Second" if accepted_title == "First" else "First"
    with pytest.raises(ConsoleError, match="ingest_command_conflict"):
        second.receive_source(**{**command, "command_id": "conflicting-receipt", "title": rejected_title})
    assert first._envelope(winner["snapshot_id"])["title"] == accepted_title
    assert len(first.list_envelopes()) == 2
    policy = {"contract": "explicit-review-v1", "revision": 1, "primary": author, "assignments": []}
    parent = first.receive_source(**{**command, "command_id": "parent", "named_reviewers": [],
                                    "review_policy": policy})["snapshot_id"]
    before = deepcopy(first._envelope(parent))
    successor = dict(actor_id=author, snapshot_id=parent, expected_revision=first.objects_revision(parent),
                     reason="Nieuwe controle", receive_only=True)
    results = together("create_review_successor", [
        {**successor, "command_id": key} for key in ("successor-a", "successor-b")])
    assert sorted(row[0] for row in results) == ["error", "ok"]
    assert next(row[1] for row in results if row[0] == "error") == "review_successor_already_exists"
    children = [first._envelope(row["snapshot_id"]) for row in first.list_envelopes()
                if first._envelope(row["snapshot_id"]).get("replaces_snapshot_id") == parent]
    assert len(children) == 1 and children[0].get("processing_attempts", []) == []
    assert first._envelope(parent) == before
    assert first.snapshot_objects(parent) == [] and first.snapshot_objects(children[0]["snapshot_id"]) == []


def test_native_blob_orphan_registration_failure_retry_has_one_identity(workflow_postgres, tmp_path, monkeypatch):
    first = _console(tmp_path / "first", workflow_postgres)
    author, reviewer = accounts(first)
    blob = ImmutableBlobFixture()
    first.immutable_source_store = blob
    command = dict(actor_id=author, filename="fixture.html",
        data=b"<html><body><p>Gebruik geen zalf.</p></body></html>", content_type="text/html",
        ingest_kind="new", title="Fixture", version="1", date="2026-10-09", live_url="",
        class_="richtlijn", family="fixture", named_reviewers=[author, reviewer], command_id="receipt-orphan")
    with monkeypatch.context() as patch:
        def fail(**kwargs):
            raise ConsoleError("workflow_document_write_failed")
        patch.setattr(first, "_commit_prepared_store", fail)
        with pytest.raises(ConsoleError, match="workflow_document_write_failed"):
            first.receive_source(**command)
    assert len(blob.blobs) == 1
    assert first.list_envelopes() == []
    restarted = _console(tmp_path / "second", workflow_postgres)
    restarted.immutable_source_store = blob
    receipt = restarted.receive_source(**command)
    assert restarted.receive_source(**command)["snapshot_id"] == receipt["snapshot_id"]
    assert len(restarted.list_envelopes()) == 1 and len(blob.blobs) == 1
    assert restarted._envelope(receipt["snapshot_id"]).get("processing_attempts", []) == []
    assert restarted._verified_source_bytes(restarted._envelope(receipt["snapshot_id"]))[1] == command["data"]
