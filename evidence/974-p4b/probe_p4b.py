"""#974 P4b probe: one repair render through the production ASGI app.

Run it unchanged at trunk and at head (it needs the tests/conftest.py fixtures
and a disposable PostgreSQL 16):
    cp evidence/974-p4b/probe_p4b.py tests/p4b_probe_tmp.py
    P4B_OUT=<dir> P4B_LABEL=<trunk|head> P4B_RUN=<n> python -m pytest -q tests/p4b_probe_tmp.py
    rm tests/p4b_probe_tmp.py
`run_p4b.sh` does this and alternates trunk and head.

The fixture is synthetic: one HTML guideline with P4B_PARAGRAPHS paragraphs
(default 923, the production document's evidence-fragment count), of which
P4B_SELECTED become knowledge candidates. Both repair entries are measured:
``POST /review`` (a revise decision; the structured-repair exception handler
renders the page) and ``GET /source-selection?task=repair``. Each is sent
twice and the second one is measured. Call counts come from counting wrappers
installed for the measured request only; times and query counts come from the
app's own ``metis_diagnostic`` request_finished event.
"""
import hashlib
import json
import logging
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from tests.semantic_fixture_support import bind_fixture_selections

OUT = Path(os.environ.get("P4B_OUT", "p4b-receipts")) / os.environ.get("P4B_LABEL", "unlabelled")
TOKEN = re.compile(r"snap-[0-9a-f]+-[0-9a-f]+|pa_[0-9a-f]{32}|[0-9a-f]{32,64}"
                   r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|obj-[A-Za-z0-9_-]+")


def normalized(html):
    """Rename run-specific ids canonically so pages from two ingests compare."""
    names = {}
    return TOKEN.sub(lambda m: names.setdefault(m.group(0), f"<id{len(names)}>"), html)


@contextmanager
def diagnostics():
    from src.request_diagnostics_v1 import _LOGGER
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            text = record.getMessage()
            if text.startswith("metis_diagnostic "):
                seen.append(json.loads(text[len("metis_diagnostic "):]))

    handler = Capture()
    _LOGGER.addHandler(handler)
    try:
        yield seen
    finally:
        _LOGGER.removeHandler(handler)


@contextmanager
def counted(monkeypatch, console):
    """Count calls to the source and document readers named in the incident."""
    from src.vorming import knowledge_materialisation_v1 as km
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    from src.review import deterministic_review_repair_v1 as repair
    from src.console_performance_v1 import _CURRENT as PERFORMANCE
    calls = {"render": {}, "render_ms": [], "render_db_queries": [], "render_db_json_bytes": []}
    inside = []
    with monkeypatch.context() as patch:
        def wrap(owner, name):
            original = getattr(owner, name)

            def counting(*args, **kwargs):
                calls[name] = calls.get(name, 0) + 1
                if inside:
                    calls["render"][name] = calls["render"].get(name, 0) + 1
                return original(*args, **kwargs)
            patch.setattr(owner, name, counting)

        render = repair.render_repair

        def timed_render(*args, **kwargs):
            metrics = PERFORMANCE.get()
            before = (metrics.queries, metrics.json_bytes) if metrics else (0, 0)
            inside.append(True)
            started = time.perf_counter()
            try:
                return render(*args, **kwargs)
            finally:
                calls["render_ms"].append(round((time.perf_counter() - started) * 1000, 1))
                inside.pop()
                if metrics:
                    calls["render_db_queries"].append(metrics.queries - before[0])
                    calls["render_db_json_bytes"].append(metrics.json_bytes - before[1])
        patch.setattr(repair, "render_repair", timed_render)

        cls = type(console)
        for name in ("_read_source_fragments", "_verified_source_bytes", "_envelope",
                     "snapshot_objects_and_revision", "_current_object", "source_units",
                     "source_fragment_catalog", "review_source_fragments"):
            if hasattr(cls, name):
                wrap(cls, name)
        wrap(km, "_read_source_blocks")
        wrap(FormationTaskStore, "read_review_source")
        yield calls


def measured(client, monkeypatch, console, send):
    with diagnostics() as seen, counted(monkeypatch, console) as calls:
        started = time.perf_counter()
        response = send(client)
        wall_ms = (time.perf_counter() - started) * 1000
    finished = [row for row in seen if row.get("event") == "request_finished"][-1]
    phases = finished.get("phases") or {}
    return {"status": response.status_code, "wall_ms": round(wall_ms, 1),
            "elapsed_ms": finished.get("elapsed_ms"), "db": finished.get("db"),
            "counters": finished.get("counters") or {},
            "phases": {k: phases[k] for k in sorted(phases)},
            "tree": finished.get("phase_tree"),
            "calls": calls,
            "page_sha256": hashlib.sha256(normalized(response.text).encode()).hexdigest(),
            "repair_page": "Correctie specificeren" in response.text,
            "options": response.text.count("<option ")}


def ingest(console, paragraphs, selected):
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg. "
             f"De verpleegkundige legt waarneming {i} vast." for i in range(paragraphs)]
    step = max(1, paragraphs // max(1, selected))
    bind_fixture_selections(console, [(text, "definition") for text in texts[::step][:selected]])
    sid = console.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body><h1>Richtlijn</h1>" + "".join(f"<p>{t}</p>" for t in texts) + "</body></html>").encode(),
        ingest_kind="new", title="P4b probe", version="1.0", date="2026-11-05", live_url="",
        class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    return sid


def test_perf(tmp_path, production_console, production_app, monkeypatch):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    sid = ingest(console, int(os.environ.get("P4B_PARAGRAPHS", "923")), int(os.environ.get("P4B_SELECTED", "92")))
    obj = next(row for row in console.snapshot_objects(sid)
               if row.get("object_type") not in {"document", "heading"} and row.get("proposed_object_type") != "heading")
    client = TestClient(production_app(console), base_url="https://testserver", raise_server_exceptions=False)
    login = client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                        headers={"origin": "https://testserver"}, follow_redirects=False)
    assert login.status_code in (302, 303)
    revise = {"snapshot_id": sid, "object_id": obj["object_id"], "snapshot_revision": console.objects_revision(sid),
              "suitability": "mist_context", "documentpositie_action": "dit_klopt", "type_action": "dit_klopt",
              "proposed_object_type": obj.get("proposed_object_type") or "definition",
              "eindoordeel": "goedkeuren_na_correctie", "comment": "Context ontbreekt."}

    def post(c):
        return c.post("/review", data=revise, headers={"origin": "https://testserver"})

    def get(c):
        return c.get(f"/source-selection?document={sid}&object={obj['object_id']}&task=repair")

    receipt = {"run": os.environ.get("P4B_RUN", "0"), "objects": len(console.snapshot_objects(sid))}
    for name, send in (("post_review", post), ("get_repair", get)):
        warm = measured(client, monkeypatch, console, send)
        receipt[name] = {"warm": warm, "measured": measured(client, monkeypatch, console, send)}
        assert receipt[name]["measured"]["status"] == 200 and receipt[name]["measured"]["repair_page"], receipt[name]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"perf-{receipt['run']}.json").write_text(json.dumps(receipt, indent=1, sort_keys=True))
