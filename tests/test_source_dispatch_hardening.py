"""One delivery authority under backlog, capacity contention and shutdown.
# release-control-evidence: scope/belofte opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
import json
import multiprocessing
import os
import sys
from threading import Event

import pytest
from fastapi.testclient import TestClient

from src.docling_pdf_v1 import reserve_conversion_capacity, release_conversion_capacity, extract
from src.operations_console_v1 import ConsoleError
from src.processing_retry_v1 import now
from src.source_processing_dispatch_v1 import SourceProcessingDispatcher, pending, claim
from tests.test_availability_repair import accounts, bind, provider, state, installed_app, login, drain
from tests.test_pre_review_semantic_v1 import _fragment
from tests.test_review_batch_atomic_postgres import _console
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


@pytest.fixture(params=["local", "postgres"])
def console(request, tmp_path):
    if request.param == "postgres":
        return _console(tmp_path, request.getfixturevalue("workflow_postgres"))
    return state(tmp_path)


def receive(console, actor, reviewer, name, *, pdf=False):
    return console.receive_source(actor_id=actor, filename=name + (".pdf" if pdf else ".html"),
        data=b"%PDF-1.4\nsynthetic" if pdf else b"<html><body><p>Gebruik geen zalf.</p></body></html>",
        content_type="application/pdf" if pdf else "text/html", ingest_kind="new",
        title=name, version="1", date="2026-10-09", live_url="", class_="richtlijn",
        family=name, named_reviewers=[actor, reviewer], command_id="receipt-" + name)["snapshot_id"]


def reserve(console, actor, sid):
    return console.reserve_source_selection(actor_id=actor, snapshot_id=sid, command_id="start-" + sid,
        expected_revision=console.objects_revision(sid))[0]


def test_http_technical_routes_only_navigate_and_unauthorized_cannot_start(console, monkeypatch):
    actor, reviewer = accounts(console)
    bind(console, provider)
    sid = receive(console, actor, reviewer, "technical")
    def forbidden(**kwargs):
        raise AssertionError("technical navigation executed or reserved processing")
    monkeypatch.setattr(console, "retry_pre_review", forbidden)
    monkeypatch.setattr(console, "resume_formation", forbidden)
    monkeypatch.setattr(console, "reserve_source_selection", forbidden)
    app = installed_app(console)
    with TestClient(app, base_url="https://testserver") as client:
        login(client)
        for route in ("/tree/reprocess", "/tree/resume-formation"):
            response = client.post(route, data={"snapshot_id": sid, "command_id": "old",
                "expected_revision": "old"}, follow_redirects=False)
            assert response.status_code == 303
            assert response.headers["location"] == f"/source-selection?document={sid}"
        assert console._envelope(sid).get("processing_attempts", []) == []
        assert console.snapshot_objects(sid) == []
        page = client.get("/settings/technical/processing", params={"document": sid}).text
        assert f'href="/source-selection?document={sid}"' in page
        stranger = console.create_account(username="stranger", password="fixture-only", roles=("reviewer",))
        login(client, stranger["username"])
        for route in ("/tree/reprocess", "/tree/resume-formation"):
            assert client.post(route, data={"snapshot_id": sid}, follow_redirects=False).status_code == 400


def test_notify_and_scan_bound_handles_shutdown_keeps_unstarted_work(console):
    actor, reviewer = accounts(console)
    entered, release = Event(), Event()
    calls = []
    def paused(*args):
        calls.append(1)
        if len(calls) == 2:
            entered.set()
        assert release.wait(10)
        return provider(*args)
    bind(console, paused)
    ids = [receive(console, actor, reviewer, "backlog" + str(i)) for i in range(6)]
    attempts = [reserve(console, actor, sid) for sid in ids]
    async def scenario():
        dispatcher = SourceProcessingDispatcher(console, shutdown_grace=.01)
        for sid, attempt in zip(ids, attempts):
            dispatcher.notify(sid, attempt)
        try:
            assert len(dispatcher.workers) == 2
            assert await asyncio.to_thread(entered.wait, 5)
            for sid, attempt in zip(ids, attempts):
                assert not dispatcher.notify(sid, attempt)
            await dispatcher.scan()
            assert len(dispatcher.workers) == 2 and len(calls) == 2
            assert len(pending(console, limit=1)) == 1
            await asyncio.wait_for(dispatcher.stop(), timeout=1)
            assert len(dispatcher.workers) == 2  # grace did not pretend threads stopped
            for sid, attempt in zip(ids[2:], attempts[2:]):
                stored = console._envelope(sid)["processing_attempts"][-1]
                assert stored == attempt and stored["dispatch"]["state"] == "pending"
            assert not dispatcher.notify(ids[-1], attempts[-1])
        finally:
            release.set()
            await asyncio.gather(*tuple(dispatcher.workers))
        recovered = SourceProcessingDispatcher(console)
        for _ in range(3):
            await recovered.scan()
            await asyncio.gather(*tuple(recovered.workers))
        await recovered.stop()
    asyncio.run(scenario())
    assert len(calls) == 6
    assert all(console._envelope(sid)["processing_attempts"][-1]["state"] == "succeeded" for sid in ids)


def test_shutdown_before_scheduled_thread_claim_leaves_pending(console):
    actor, reviewer = accounts(console)
    calls = []
    bind(console, lambda *args: calls.append(1) or provider(*args))
    sid = receive(console, actor, reviewer, "not-started")
    attempt = reserve(console, actor, sid)
    async def scenario():
        dispatcher = SourceProcessingDispatcher(console)
        assert dispatcher.notify(sid, attempt)
        await dispatcher.stop()  # no event-loop yield between notify and stop
        assert not dispatcher.workers
    asyncio.run(scenario())
    assert calls == []
    assert console._envelope(sid)["processing_attempts"][-1] == attempt


def test_stop_event_checked_inside_claim_transaction(console):
    from contextlib import contextmanager
    actor, reviewer = accounts(console)
    bind(console, provider)
    sid = receive(console, actor, reviewer, "claim-stop")
    attempt = reserve(console, actor, sid)
    stop = Event()
    original = console._reprocessing_transaction
    @contextmanager
    def stopping_transaction(snapshot):
        with original(snapshot):
            stop.set()
            yield
    console._reprocessing_transaction = stopping_transaction
    assert claim(console, snapshot_id=sid, attempt_id=attempt["attempt_id"], stop_event=stop) is None
    assert console._envelope(sid)["processing_attempts"][-1] == attempt


def _hold_conversion_slot(path, entered, release):
    os.environ["METIS_DOCLING_LOCK_PATH"] = path
    with reserve_conversion_capacity() as available:
        assert available
        entered.set()
        assert release.wait(15)


@pytest.mark.parametrize("dispatchers", [1, 2])
def test_pdf_capacity_other_process_keeps_durable_command_pending_then_recovers(console, tmp_path, monkeypatch, dispatchers):
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    monkeypatch.setenv("METIS_DOCLING_LOCK_PATH", str(tmp_path / "conversion.lock"))
    actor, reviewer = accounts(console)
    calls = []
    def checked_provider(*args):
        # Retained/synthetic extraction has released the handoff before inference.
        with reserve_conversion_capacity() as available:
            assert available
        calls.append(1)
        return provider(*args)
    bind(console, checked_provider)
    monkeypatch.setattr(console, "_extract", lambda *args, **kw: [_fragment("p1", "Gebruik geen zalf.")])
    ids = [receive(console, actor, reviewer, "pdf" + str(i), pdf=True) for i in range(2)]
    attempts = [reserve(console, actor, sid) for sid in ids]
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    process = context.Process(target=_hold_conversion_slot,
        args=(str(tmp_path / "conversion.lock"), entered, release))
    process.start()
    try:
        assert entered.wait(5)
        async def blocked():
            deliveries = [SourceProcessingDispatcher(console) for _ in range(dispatchers)]
            for delivery in deliveries:
                await delivery.scan()
                await asyncio.gather(*tuple(delivery.workers))
                await delivery.stop()
        asyncio.run(blocked())
        for sid, attempt in zip(ids, attempts):
            assert console._envelope(sid)["processing_attempts"][-1] == attempt
        assert calls == []
        app = installed_app(console)
        with TestClient(app, base_url="https://testserver") as client:
            login(client)
            drain(client, app)
            screen = client.get("/source-selection", params={"document": ids[0]}).text
            assert "Status: wacht op uitvoering" in screen
            assert "Verstreken sinds aanvraag:" in screen
            assert "telt deze poging mee voor de herstelgrens" in screen
            assert 'window.location.reload' in screen and ">Hervatten</button>" not in screen
    finally:
        release.set()
        process.join(5)
        if process.is_alive():
            process.terminate()
            process.join(5)
    assert process.exitcode == 0
    async def recovered():
        delivery = SourceProcessingDispatcher(console)
        for _ in range(3):
            await delivery.scan()
            await asyncio.gather(*tuple(delivery.workers))
        await delivery.stop()
    asyncio.run(recovered())
    assert calls == [1, 1]
    for sid in ids:
        stored = console._envelope(sid)["processing_attempts"]
        assert len(stored) == 1 and stored[-1]["state"] == "succeeded"


def test_extractor_consumes_same_descriptor_and_releases_before_scope_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("METIS_DOCLING_LOCK_PATH", str(tmp_path / "conversion.lock"))
    monkeypatch.setenv("METIS_DOCLING_PYTHON", sys.executable)
    monkeypatch.setenv("METIS_DOCLING_ARTIFACTS_PATH", str(tmp_path))
    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(b"%PDF-1.4\nsynthetic")
    def conversion(command, *, pass_fds, **kw):
        with reserve_conversion_capacity() as available:
            assert not available  # conversion slot remains held through actual worker boundary
        os.write(pass_fds[-1], json.dumps({"result": {"metrics": {}}}).encode())
        return {"worker_reaped": True}
    monkeypatch.setattr("src.docling_pdf_v1.supervise", conversion)
    monkeypatch.setattr("src.docling_pdf_v1.translate", lambda *a, **kw: ["translated"])
    with reserve_conversion_capacity() as available:
        assert available
        assert extract(pdf, document_id="document", source_id="source") == ["translated"]
        with reserve_conversion_capacity() as after:
            assert after  # conversion lock is not held during later inference


def test_reserved_capacity_released_on_exception_and_retained_source_path(tmp_path, monkeypatch):
    monkeypatch.setenv("METIS_DOCLING_LOCK_PATH", str(tmp_path / "conversion.lock"))
    with pytest.raises(RuntimeError):
        with reserve_conversion_capacity() as available:
            assert available
            raise RuntimeError("synthetic")
    with reserve_conversion_capacity() as available:
        assert available
        release_conversion_capacity()
        with reserve_conversion_capacity() as second:
            assert second


def test_waiting_keeps_original_expiry_and_retry_budget(console, monkeypatch):
    actor, reviewer = accounts(console)
    bind(console, provider)
    sid = receive(console, actor, reviewer, "expiry")
    attempt = reserve(console, actor, sid)
    future = datetime.fromisoformat(attempt["expires_at"]) + timedelta(seconds=1)
    monkeypatch.setattr("src.source_processing_dispatch_v1.now", lambda: future)
    assert pending(console) == []
    stored = console._envelope(sid)["processing_attempts"][-1]
    assert stored["expires_at"] == attempt["expires_at"]
    assert stored["state"] == "interrupted" and stored["dispatch"]["state"] == "pending"
    result = console.processing_status(sid, actor_id=actor)
    assert result["retry_attempts_used"] == 1


def test_busy_pdf_prefix_does_not_starve_unrelated_html(console, tmp_path, monkeypatch):
    monkeypatch.setenv("METIS_PDF_EXTRACTOR", "docling")
    monkeypatch.setenv("METIS_DOCLING_LOCK_PATH", str(tmp_path / "fairness.lock"))
    actor, reviewer = accounts(console)
    calls = []
    bind(console, lambda *args: calls.append(1) or provider(*args))
    pdfs = [receive(console, actor, reviewer, "busy" + str(i), pdf=True) for i in range(2)]
    html = receive(console, actor, reviewer, "unrelated")
    for sid in [*pdfs, html]:
        reserve(console, actor, sid)
    async def scenario():
        dispatcher = SourceProcessingDispatcher(console)
        # Match durable enumeration rather than relying on random snapshot ids.
        rows = {row["snapshot_id"]: row for row in console.list_envelopes()}
        monkeypatch.setattr(console, "list_envelopes", lambda: [rows[sid] for sid in [*pdfs, html]])
        with reserve_conversion_capacity() as available:
            assert available
            for _ in range(2):
                await dispatcher.scan()
                await asyncio.gather(*tuple(dispatcher.workers))
            assert console._envelope(html)["processing_attempts"][-1]["state"] == "succeeded"
            assert all(console._envelope(sid)["processing_attempts"][-1]["dispatch"]["state"] == "pending" for sid in pdfs)
        await dispatcher.stop()
    asyncio.run(scenario())
    assert calls == [1]
