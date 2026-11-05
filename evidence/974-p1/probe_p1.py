"""#974 P1 probe: Vorming detail through the production ASGI app.

Run it unchanged at trunk and at the PR head (it needs the tests/conftest.py
fixtures and a disposable PostgreSQL 16):
    cp evidence/974-p1/probe_p1.py tests/p1_probe_tmp.py
    P1_OUT=<dir> P1_LABEL=<trunk|head> python -m pytest -q tests/p1_probe_tmp.py -k <perf|lane>
    rm tests/p1_probe_tmp.py
Each test writes one JSON receipt to $P1_OUT/$P1_LABEL/. Requests are driven
only over HTTP; fixtures prepare state before a lane, never during it.
`compare_p1.py` turns trunk and head receipts into lane verdicts.
"""
import hashlib
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread

import pytest
from fastapi.testclient import TestClient

from tests.semantic_fixture_support import bind_fixture_selections

OUT = Path(os.environ.get("P1_OUT", "p1-receipts")) / os.environ.get("P1_LABEL", "unlabelled")
TOKEN = re.compile(r"snap-[0-9a-f]+-[0-9a-f]+|pa_[0-9a-f]{32}|[0-9a-f]{32,64}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|obj-[A-Za-z0-9_-]+")


def normalized(html):
    """Rename run-specific ids canonically so trunk and head pages compare."""
    names = {}
    return TOKEN.sub(lambda m: names.setdefault(m.group(0), f"<id{len(names)}>"), html)


def page_facts(html):
    # Problems sort by problem_id, a hash over the run-specific snapshot id, so
    # their order differs between two ingests of the same source. The order-free
    # digest compares the multiset of tag fragments with every id masked.
    text = normalized(html)
    fragments = sorted(TOKEN.sub("<id>", html).split("<"))
    return {"sha256": hashlib.sha256(text.encode()).hexdigest(),
            "content_sha256": hashlib.sha256("\x00".join(fragments).encode()).hexdigest(),
            "problem_ids": re.findall(r'id="problem-([^"]+)"', text),
            "hrefs": re.findall(r'href="([^"]+)"', text),
            "progress_refresh": "ververst elke 5 seconden" in text,
            "progress_line": re.findall(r"<p>Fase: [^<]*</p>", text)}


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


def opened(client, path):
    with diagnostics() as seen:
        response = client.get(path, follow_redirects=False)
    finished = [row for row in seen if row.get("event") == "request_finished"][-1]
    return response, finished


def summary(response, finished, html=True):
    phases = finished.get("phases") or {}
    return {"status": response.status_code, "outcome": finished.get("outcome"),
            "error": finished.get("error"), "elapsed_ms": finished.get("elapsed_ms"),
            "counters": finished.get("counters") or {},
            "source_reconstruction": phases.get("source_reconstruction"),
            "location": response.headers.get("location"),
            **({"page": page_facts(response.text)} if html else {})}


def save(name, receipt):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(receipt, indent=1, sort_keys=True))


def client_for(app, username):
    client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    login = client.post("/login", data={"username": username, "password": "fixture-only"},
                        headers={"origin": "https://testserver"}, follow_redirects=False)
    assert login.status_code in (302, 303)
    return client


def ingest(console, paragraphs, selected):
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    console.create_account(username="outsider", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg." for i in range(paragraphs)]
    bind_fixture_selections(console, [(text, "definition") for text in texts[:selected]])
    return console.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{t}</p>" for t in texts) + "</body></html>").encode(),
        ingest_kind="new", title="P1 probe", version="1.0", date="2026-11-04", live_url="",
        class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]])["snapshot_id"]


def test_perf(tmp_path, production_console, production_app):
    """Lane 1 and the perf metric: 2,000 paragraphs, 200 materialised candidates."""
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    sid = ingest(console, int(os.environ.get("P1_PARAGRAPHS", "2000")), int(os.environ.get("P1_SELECTED", "200")))
    client = client_for(production_app(console), "reviewer")
    warm = summary(*opened(client, f"/source-selection?document={sid}"))
    measured = summary(*opened(client, f"/source-selection?document={sid}"))
    run = os.environ.get("P1_RUN", "0")
    save(f"perf-{run}", {"lane": "perf", "run": run, "warm": warm, "measured": measured})


@pytest.fixture
def small(tmp_path, production_console, production_app):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    sid = ingest(console, 20, 5)
    return production_app(console), console, sid


def test_lane_rejections(tmp_path, production_console, monkeypatch):
    from tests.test_review_formation_problems import received, execute
    console, sid, author, *_ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, "p1-rejections")
    client = client_for(console._metis_test_application, "reviewer")
    detail = summary(*opened(client, f"/source-selection?document={sid}"))
    problems = summary(*opened(client, f"/formation-problems?document={sid}"))
    save("rejections", {"lane": 2, "source_selection": detail, "formation_problems": problems})


def test_lane_running(tmp_path, production_console, monkeypatch):
    from tests.test_review_formation_problems import received, execute
    console, sid, author, _, calls, mode, _ = received(tmp_path, production_console, monkeypatch)
    entered, release = Event(), Event()
    mode["pause"] = entered, release
    worker = Thread(target=execute, args=(console, sid, author, "p1-running"), daemon=True)
    worker.start()
    try:
        assert entered.wait(20)
        client = client_for(console._metis_test_application, "author")
        running = summary(*opened(client, f"/source-selection?document={sid}"))
    finally:
        release.set()
        worker.join(30)
    running["page"].pop("sha256")  # elapsed time is part of the page text
    save("running", {"lane": 3, "source_selection": running})


def test_lane_overview(small):
    app, _, _ = small
    response, finished = opened(client_for(app, "reviewer"), "/source-selection")
    save("overview", {"lane": 4, "source_selection": summary(response, finished),
                      "phase_names": sorted((finished.get("phases") or {}).keys())})


def test_lane_not_named(small):
    app, _, sid = small
    save("not-named", {"lane": 5, "source_selection": summary(*opened(client_for(app, "outsider"),
                                                                    f"/source-selection?document={sid}"))})


@pytest.mark.parametrize("route", ["decision-boom", "legacy-html"])
def test_lane_route(route, tmp_path, complete_postgres, monkeypatch):
    from tests.test_a10_source_cache_repair import seed
    app, _, _, sid, _, _ = seed(tmp_path, "postgres", route, monkeypatch)
    detail = summary(*opened(client_for(app, "reviewer"), f"/source-selection?document={sid}"))
    save("boom" if route == "decision-boom" else "legacy", {"lane": 6 if route == "decision-boom" else 7,
                                                            "source_selection": detail})


def test_lane_disposition(small):
    app, _, sid = small
    save("disposition", {"lane": 8, "source_selection": summary(*opened(
        client_for(app, "reviewer"), f"/source-selection?document={sid}&task=disposition"))})


def test_lane_twice(small):
    app, _, sid = small
    client = client_for(app, "reviewer")
    first = summary(*opened(client, f"/source-selection?document={sid}"))
    second = summary(*opened(client, f"/source-selection?document={sid}"))
    save("twice", {"lane": 9, "first": first, "second": second})


def test_lane_concurrent(small):
    app, _, sid = small
    clients = [client_for(app, "reviewer"), client_for(app, "reviewer")]
    with diagnostics() as seen, ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda c: c.get(f"/source-selection?document={sid}"), clients))
    finished = [row for row in seen if row.get("event") == "request_finished"]
    save("concurrent", {"lane": 10, "statuses": [r.status_code for r in responses],
                        "pages": [page_facts(r.text) for r in responses],
                        "raw_problem_ids": [re.findall(r'id="problem-([0-9a-f]{64})"', r.text) for r in responses],
                        "counters": [row.get("counters") for row in finished]})
