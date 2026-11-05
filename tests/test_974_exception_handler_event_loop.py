"""Synchronous exception-handler work must not block the event loop (#974).

Production runs one worker. A ``POST /review`` revise decision raises
``StructuredRepairRequired``; its handler rendered the repair page on the
event loop, so a slow render starved every other request until the worker
timed out. These tests serve the production app with a real uvicorn server
(one event loop), slow the synchronous handler work down, and prove that a
concurrent cheap request is still answered while the handler runs.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import logging
import json
import re
import socket
import threading
import time
from contextlib import contextmanager

import httpx
import pytest
import uvicorn

from tests.semantic_fixture_support import bind_fixture_selections

SLOW = 2.0
# The concurrent request is cheap; anything near SLOW means it queued behind
# the handler on the event loop.
RESPONSIVE = 0.75


@contextmanager
def _serve(app):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_level="warning", loop="asyncio"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        assert thread.is_alive() and time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(15)
        sock.close()


def _console(tmp_path, production_console):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    receipt = console.ingest(
        actor_id=researcher["account_id"], filename="bron.html", content_type="text/html",
        data=(b"<html><body><h1>Richtlijn</h1><h2>1 Zorg</h2>"
              b"<p>Wanneer de client ondersteuning wil, bespreekt de verpleegkundige passende ondersteuning.</p>"
              b"<p>De verpleegkundige verwijst de client zo nodig naar passende ondersteuning.</p>"
              b"</body></html>"),
        ingest_kind="new", title="Bron", version="1.0", date="2026-09-11", live_url="",
        class_="richtlijn", family="zorg", named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    obj = next(row for row in console.snapshot_objects(sid)
               if row.get("object_type") not in {"document", "heading"}
               and row.get("proposed_object_type") != "heading")
    return console, sid, obj


def _revise_payload(console, sid, obj):
    return {
        "snapshot_id": sid, "object_id": obj["object_id"],
        "snapshot_revision": console.objects_revision(sid),
        "suitability": "mist_context", "documentpositie_action": "dit_klopt", "type_action": "dit_klopt",
        "proposed_object_type": obj.get("proposed_object_type") or obj.get("object_type") or "explanation",
        "eindoordeel": "goedkeuren_na_correctie", "comment": "Context ontbreekt.",
    }


def _slowed(original, entered):
    def slow(*args, **kwargs):
        entered.set()
        time.sleep(SLOW)
        return original(*args, **kwargs)
    return slow


def _concurrent(base, send_slow, entered):
    """Run ``send_slow`` in a thread; time a cheap GET issued while it is slowed."""
    outcome = {}

    def run():
        try:
            outcome["response"] = send_slow()
        except BaseException as exc:  # surfaced in the main thread
            outcome["error"] = exc

    worker = threading.Thread(target=run)
    worker.start()
    if not entered.wait(30):
        worker.join(60)
        raise AssertionError(f"slowed handler work was never reached: {outcome}")
    started = time.monotonic()
    with httpx.Client(base_url=base, timeout=30) as probe:
        cheap = probe.get("/login")
    elapsed = time.monotonic() - started
    worker.join(60)
    assert "error" not in outcome, outcome.get("error")
    assert cheap.status_code == 200
    return outcome["response"], elapsed


def test_structured_repair_render_does_not_block_other_requests(tmp_path, production_app, production_console, monkeypatch):
    from src.review import deterministic_review_repair_v1 as repair
    console, sid, obj = _console(tmp_path, production_console)
    app = production_app(console)
    entered = threading.Event()
    monkeypatch.setattr(repair, "render_repair", _slowed(repair.render_repair, entered))
    with _serve(app) as base, httpx.Client(base_url=base, timeout=30) as client:
        login = client.post("/login", data={"username": "bert", "password": "bert-secret"})
        # The session cookie is Secure; replay it explicitly over the plain-HTTP test server.
        client.cookies.set("console_session", login.cookies["console_session"])
        payload = _revise_payload(console, sid, obj)
        response, elapsed = _concurrent(base, lambda: client.post("/review", data=payload), entered)
    assert response.status_code == 200, response.text[:300]
    assert "Correctie specificeren" in response.text
    assert "Er is nog niets gewijzigd" in response.text
    assert elapsed < RESPONSIVE, f"GET /login waited {elapsed:.2f}s behind the repair render"


def test_console_error_page_does_not_block_other_requests(tmp_path, production_app, production_console, monkeypatch):
    from src import operations_console_app as console_app
    console, _sid, _obj = _console(tmp_path, production_console)
    app = production_app(console)
    entered = threading.Event()
    monkeypatch.setattr(console_app, "_nav", _slowed(console_app._nav, entered))
    with _serve(app) as base, httpx.Client(base_url=base, timeout=30) as client:
        response, elapsed = _concurrent(base, lambda: client.get("/review"), entered)
    assert response.status_code == 401, response.text[:300]
    assert 'data-error-code="not_authenticated"' in response.text
    assert elapsed < RESPONSIVE, f"GET /login waited {elapsed:.2f}s behind the error page"


def test_console_error_raised_by_repair_handler_is_rendered_as_before(tmp_path, production_app, production_console):
    """The repair handler refuses another actor's submission through the ConsoleError page."""
    from fastapi.testclient import TestClient
    from src.operations_console_app import ERROR_COPY
    from src.request_diagnostics_v1 import _LOGGER
    from src.review.deterministic_review_repair_v1 import StructuredRepairRequired
    console, sid, obj = _console(tmp_path, production_console)
    app = production_app(console)

    def foreign_submission():
        raise StructuredRepairRequired({"actor_id": "someone-else", "snapshot_id": sid,
                                        "object_id": obj["object_id"]})

    app.add_api_route("/test-974/foreign-repair", foreign_submission, methods=["POST"])
    client = TestClient(app)
    client.post("/login", data={"username": "bert", "password": "bert-secret"})
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            text = record.getMessage()
            if text.startswith("metis_diagnostic "):
                seen.append(json.loads(text[len("metis_diagnostic "):]))

    handler = Capture()
    _LOGGER.addHandler(handler)
    try:
        response = client.post("/test-974/foreign-repair")
    finally:
        _LOGGER.removeHandler(handler)
    assert response.status_code == 403
    banner = re.search(r'data-error-code="([^"]*)" data-request-id="([^"]*)">([^<]*)<', response.text)
    assert banner is not None, response.text[:500]
    code, request_id, message = banner.groups()
    assert code == "correction_role_required"
    assert message == ERROR_COPY["correction_role_required"]
    finished = [e for e in seen if e.get("event") == "request_finished"]
    assert finished, "request_finished diagnostic missing"
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)
    assert finished[-1]["request_id"] == request_id
    assert finished[-1]["error"] == {"type": "ConsoleError", "code": "correction_role_required", "handled": True}
