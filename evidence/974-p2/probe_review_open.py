"""#974 P2 probe: Review open on a 2,000-paragraph fixture through the production ASGI app.

Copied into a tree's tests/ directory by run_probe.py and run there with pytest, so
it uses that tree's own code (trunk or head) and the test PostgreSQL fixtures.

PROBE_MODE=perf  : one warm-up and PROBE_REQUESTS measured GET /review?document=<sid>.
PROBE_MODE=lanes : one receipt per live lane (see README.md).
PROBE_OUT        : JSON output file.

It only records what request_finished says; run_probe.py judges the lanes.
"""
import json
import logging
import os
import re
import threading
from pathlib import Path

from tests.semantic_fixture_support import bind_fixture_selections

PARAGRAPHS = 2000


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []
        self.guard = threading.Lock()

    def emit(self, record):
        text = record.getMessage()
        if text.startswith("metis_diagnostic "):
            with self.guard:
                self.events.append(json.loads(text[len("metis_diagnostic "):]))

    def finished(self, response):
        rid = response.headers.get("x-metis-request-id")
        with self.guard:
            rows = [e for e in self.events if e.get("event") == "request_finished"
                    and (rid is None or e.get("request_id") == rid)]
        return rows[-1]


def _summary(finished, status):
    db = finished.get("db") or {}
    by_phase = finished.get("db_json_bytes_by_phase")
    return {"status": status, "route": finished.get("route"), "method": finished.get("method"),
            "outcome": finished.get("outcome"), "elapsed_ms": finished.get("elapsed_ms"),
            "db_json_bytes": db.get("db_json_bytes"), "db_queries": db.get("db_queries"),
            "db_json_bytes_by_phase": by_phase,
            "by_phase_sum": sum(by_phase.values()) if isinstance(by_phase, dict) else None,
            "db_json_bytes_by_phase_truncated": finished.get("db_json_bytes_by_phase_truncated", False),
            "phase_tree_truncated": finished.get("phase_tree_truncated", False),
            "error": finished.get("error")}


def _fixture(tmp_path, production_console, production_app):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg." for i in range(PARAGRAPHS)]
    bind_fixture_selections(console, [(t, "definition") for t in texts[:200]])
    sid = console.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{t}</p>" for t in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Probe 974 P2", version="1.0", date="2026-11-04", live_url="",
        class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    from fastapi.testclient import TestClient
    app = production_app(console)
    client = TestClient(app, base_url="https://testserver")
    login = client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                        headers={"origin": "https://testserver"}, follow_redirects=False)
    assert login.status_code in (302, 303), login.text[:200]
    return console, app, client, sid, {"author": author["account_id"], "reviewer": reviewer["account_id"]}


def _perf(capture, client, sid):
    client.get(f"/review?document={sid}")  # warm-up: imports, caches, first connections
    runs = []
    for _ in range(int(os.environ.get("PROBE_REQUESTS", "3"))):
        response = client.get(f"/review?document={sid}")
        runs.append(_summary(capture.finished(response), response.status_code))
    return {"runs": runs}


def _lanes(capture, console, app, client, sid, accounts):
    from fastapi.testclient import TestClient
    from concurrent.futures import ThreadPoolExecutor
    lanes = {}
    client.get(f"/review?document={sid}")  # warm-up, same as perf
    response = client.get(f"/review?document={sid}")
    lanes["review-document"] = _summary(capture.finished(response), response.status_code)
    response = client.get(f"/source-selection?document={sid}")
    lanes["formation"] = _summary(capture.finished(response), response.status_code)
    anonymous = TestClient(app, base_url="https://testserver")
    response = anonymous.get("/login")
    lanes["no-json"] = _summary(capture.finished(response), response.status_code)
    objects = console.snapshot_objects(sid)
    from src.review.proportionate_review_v1 import normal_risk_batch_queue
    # The large fixture has no reviewable candidate; save on the review_system document instead.
    bind_fixture_selections(console)
    reviewer_id, author_id = accounts["reviewer"], accounts["author"]
    save_sid = console.ingest(
        actor_id=author_id, filename="begrippen.html", content_type="text/html",
        data=b'<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>'
             b'<p>De Dutch Job Group (dJG) is een meetinstrument voor werkbelasting.</p>'
             b'<p>Een observatie is een systematische waarneming van gedrag.</p></body></html>',
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-09-08", live_url="",
        class_="richtlijn", family="begrippen", named_reviewers=[reviewer_id])["snapshot_id"]
    save_objects = console.snapshot_objects(save_sid)
    objects = objects + save_objects
    queue = normal_risk_batch_queue(save_objects, review_path="richtlijn",
                                    bindings=console.object_review_bindings(save_sid),
                                    fragments=console.review_source_fragments(save_sid))
    target = queue[0] if queue else None
    if target is None:
        lanes["save"] = {"skipped": "no reviewable object in the fixture"}
        lanes["error"] = {"skipped": "no reviewable object in the fixture"}
    else:
        page = client.get("/review", params={"document": save_sid, "object": target["object_id"]})
        match = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text)
        form = {"snapshot_id": save_sid, "object_id": target["object_id"],
                "snapshot_revision": match.group(1) if match else "",
                "suitability": "ja", "documentpositie_action": "dit_klopt",
                "type_action": "dit_klopt", "confirmed_object_type": "definition",
                "eindoordeel": "goedkeuren", "decision": "approve", "relation_review_ack": "1"}
        # A stale revision is refused as a write conflict page (no ConsoleError evidence).
        stale = {**form, "snapshot_revision": "0" * 64}
        response = client.post("/review", data=stale, headers={"origin": "https://testserver"},
                               follow_redirects=False)
        lanes["conflict"] = _summary(capture.finished(response), response.status_code)
        # An inconsistent decision raises a ConsoleError after the source was read.
        invalid = {**form, "source_discrepancy": "context_ontbreekt"}
        response = client.post("/review", data=invalid, headers={"origin": "https://testserver"},
                               follow_redirects=False)
        lanes["error-form"] = _summary(capture.finished(response), response.status_code)
        response = client.post("/review", data=form, headers={"origin": "https://testserver"},
                               follow_redirects=False)
        lanes["save"] = _summary(capture.finished(response), response.status_code)
    # A ConsoleError that reaches the app's handler is recorded with its code.
    row = None
    for path in ("/review?document=snap-00000000-0000", "/source-selection?document=snap-00000000-0000",
                 f"/review?document={sid}&object=unknown-object"):
        response = client.get(path)
        row = _summary(capture.finished(response), response.status_code)
        if row["error"]:
            break
    lanes["error"] = row if row["error"] else {"not_reached": "no probed request recorded a ConsoleError",
                                                "last": row}
    with ThreadPoolExecutor(2) as pool:
        pending = [pool.submit(client.get, path) for path in
                   (f"/review?document={sid}", f"/source-selection?document={sid}")]
        lanes["concurrent"] = [_summary(capture.finished(p.result()), p.result().status_code) for p in pending]
    lanes["truncated"] = _truncated(capture)
    with capture.guard:
        events = list(capture.events)
    text = json.dumps(events)
    forbidden_values = {"snapshot_id": [sid, save_sid], "object_id": [o["object_id"] for o in objects if o.get("object_id")],
               "sql": ["SELECT ", " FROM ", "INSERT ", "UPDATE "]}
    request_events = [e for e in events if str(e.get("event", "")).startswith(("request_", "phase_", "response_"))]
    request_text = json.dumps(request_events)
    lanes["privacy"] = {"events": len(events), "request_events": len(request_events),
                        "hits": {kind: sum(value in text for value in values) for kind, values in forbidden_values.items()},
                        "request_event_hits": {kind: sum(value in request_text for value in values)
                                               for kind, values in forbidden_values.items()},
                        # Producers outside request diagnostics; the hub maps their ids to doc_ref.
                        "events_with_snapshot_id": sorted({e.get("event") for e in events if sid in json.dumps(e) or save_sid in json.dumps(e)}),
                        "checked_values": {kind: len(values) for kind, values in forbidden_values.items()}}
    return lanes


def _truncated(capture):
    """No production route has more than MAX_TREE_NODES phase paths: force them on a
    measured app reading real JSON from the same test PostgreSQL."""
    import psycopg
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.console_performance_v1 import connect_postgres, install_console_performance
    from src.request_diagnostics_v1 import MAX_TREE_NODES, PHASES, diagnostic_phase
    names = sorted(PHASES - {"db_connect", "db_execute", "db_fetch"})
    pairs = [(outer, inner) for outer in names[:9] for inner in names[9:18]]
    app = FastAPI()
    install_console_performance(app)

    @app.get("/tree")
    def tree():
        with connect_postgres(psycopg, os.environ["METIS_TEST_POSTGRES_DSN"]) as connection:
            connection.execute("SELECT '22'::jsonb").fetchone()
            for outer, inner in pairs:
                with diagnostic_phase(outer), diagnostic_phase(inner):
                    connection.execute("SELECT '1'::jsonb").fetchone()
        return "ok"

    response = TestClient(app).get("/tree")
    return {**_summary(capture.finished(response), response.status_code),
            "forced_phase_paths": len(pairs), "max_tree_nodes": MAX_TREE_NODES}


def test_probe(tmp_path, production_console, production_app):
    from src.request_diagnostics_v1 import _LOGGER
    capture = _Capture()
    _LOGGER.addHandler(capture)
    try:
        console, app, client, sid, accounts = _fixture(tmp_path, production_console, production_app)
        if os.environ.get("PROBE_MODE", "perf") == "count":
            # Head only: how many JSON loads (attribution calls) one Review open makes.
            import src.console_performance_v1 as performance
            original, calls = performance.diagnostic_json_bytes, []
            performance.diagnostic_json_bytes = lambda size: (calls.append(size), original(size))
            try:
                client.get(f"/review?document={sid}")
                calls.clear()
                response = client.get(f"/review?document={sid}")
            finally:
                performance.diagnostic_json_bytes = original
            result = {"json_loads": len(calls), "json_bytes": sum(calls),
                      "request": _summary(capture.finished(response), response.status_code)}
        elif os.environ.get("PROBE_MODE", "perf") == "lanes":
            result = _lanes(capture, console, app, client, sid, accounts)
        else:
            result = _perf(capture, client, sid)
    finally:
        _LOGGER.removeHandler(capture)
    Path(os.environ["PROBE_OUT"]).write_text(json.dumps(result, indent=2, sort_keys=True))
