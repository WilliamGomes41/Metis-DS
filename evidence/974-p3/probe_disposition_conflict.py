"""#974 P3 probe: a conflicting POST /review on a ~2,000 paragraph document.

Run (needs the tests/conftest.py fixtures and a test PostgreSQL):
    cp evidence/974-p3/probe_disposition_conflict.py tests/probe_974_p3_tmp.py
    python -m pytest -q -s -p no:logging tests/probe_974_p3_tmp.py; rm tests/probe_974_p3_tmp.py

"trunk" mode disables only the new early call (review_command_v1.
_refuse_static_disposition), which restores trunk's command order exactly;
the extracted owner function keeps trunk's semantics (table test). Modes are
interleaved run by run on the same document. Set P3_PROBE_LABEL to tag a run
taken on a real trunk checkout (the toggle is then a no-op).
"""
import hashlib
import json
import logging
import os
import re
import statistics
from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_navigation_source_reuse import bind_fixture_selections

PARAGRAPHS = 2000
RUNS = 10
OUT = Path(os.environ.get("P3_PROBE_OUT", "evidence/974-p3"))
LABEL = os.environ.get("P3_PROBE_LABEL", "head")


def _capture(client, data):
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
        response = client.post("/review", data=data, follow_redirects=False)
    finally:
        _LOGGER.removeHandler(handler)
    finished = [e for e in seen if e.get("event") == "request_finished"][-1]
    paths = set(finished.get("phases") or {}) | set(finished.get("phase_tree") or {})
    names = sorted({n for p in paths for n in p.split("/")})
    return {"status": response.status_code, "error_code": (finished.get("error") or {}).get("code"),
            "elapsed_ms": finished.get("elapsed_ms"), "db_queries": (finished.get("db") or {}).get("db_queries"),
            "store_transaction": "store_transaction" in names,
            "source_preparation": any(n.startswith("source_") for n in names),
            "phases": names, "location": response.headers.get("location")}


def _events(console):
    with console.workflow_review_store._connect() as con:
        return con.execute("SELECT count(*) AS n FROM workflow.review_events").fetchone()["n"]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_probe(tmp_path, production_console, production_app, monkeypatch):
    from src.review import review_command_v1
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg." for i in range(PARAGRAPHS)]
    bind_fixture_selections(console, [(t, "definition") for t in texts[:200]])
    sid = console.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{t}</p>" for t in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Probe 974 P3", version="1.0", date="2026-11-04", live_url="",
        class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    ids = [o["object_id"] for o in console.snapshot_objects(sid) if o.get("proposed_object_type") == "definition"]
    assert len(ids) >= 20
    client = TestClient(production_app(console), base_url="https://testserver")
    assert client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                       headers={"origin": "https://testserver"}, follow_redirects=False).status_code in (302, 303)
    original_precheck = getattr(review_command_v1, "_refuse_static_disposition", None)
    original_window = console.workflow_document_store.review_command_window

    def mode(name, path):
        if original_precheck is not None:
            monkeypatch.setattr(review_command_v1, "_refuse_static_disposition",
                                original_precheck if name == "head" else (lambda command: None))
        monkeypatch.setattr(console.workflow_document_store, "review_command_window",
                            original_window if path == "prepared" else (lambda *a, **k: None))

    def form(oid, **overrides):
        page = client.get("/review", params={"document": sid, "object": oid})
        assert page.status_code == 200
        token = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text).group(1)
        return {"snapshot_id": sid, "object_id": oid, "snapshot_revision": token,
                "suitability": "ja", "documentpositie_action": "dit_klopt", "type_action": "dit_klopt",
                "confirmed_object_type": "definition", "eindoordeel": "goedkeuren", "decision": "approve",
                "relation_review_ack": "1", **overrides}

    def post(name, path, data):
        mode(name, path)
        before = _events(console)
        result = _capture(client, data)
        result["review_events_delta"] = _events(console) - before
        return result

    # Perf: conflicting POST, 10 runs interleaved trunk/head per path.
    conflict = form(ids[0], suitability="geen_kenniseenheid")
    post("head", "prepared", conflict)  # warm-up, not recorded
    perf = {}
    for path in ("serial", "prepared"):
        runs = {"trunk": [], "head": []}
        for i in range(RUNS):
            for name in (("trunk", "head") if i % 2 == 0 else ("head", "trunk")):
                runs[name].append(post(name, path, conflict))
        perf[path] = {name: {"elapsed_ms": [r["elapsed_ms"] for r in rs],
                             "db_queries": [r["db_queries"] for r in rs],
                             "median_elapsed_ms": statistics.median(r["elapsed_ms"] for r in rs),
                             "median_db_queries": statistics.median(r["db_queries"] for r in rs),
                             "any_store_transaction": any(r["store_transaction"] for r in rs),
                             "any_source_preparation": any(r["source_preparation"] for r in rs),
                             "statuses": sorted({r["status"] for r in rs}),
                             "error_codes": sorted({str(r["error_code"]) for r in rs}),
                             "review_events_delta": sum(r["review_events_delta"] for r in rs)}
                      for name, rs in runs.items()}
    head_serial, trunk_prepared, head_prepared = perf["serial"]["head"], perf["prepared"]["trunk"], perf["prepared"]["head"]
    perf["rule"] = {
        "serial_head_no_store_transaction": not head_serial["any_store_transaction"],
        "serial_head_no_source_preparation": not head_serial["any_source_preparation"],
        "serial_head_max_elapsed_le_300ms": max(head_serial["elapsed_ms"]) <= 300,
        "prepared_head_queries_strictly_lower": max(head_prepared["db_queries"]) < min(trunk_prepared["db_queries"]),
    }
    perf["rule"]["pass"] = all(perf["rule"].values())

    # Live lanes, both modes, serial path unless stated; fresh objects for writes.
    lanes = {}
    free = iter(ids[1:])

    def both(lane, build, path="serial"):
        lanes[lane] = {name: post(name, path, build()) for name in ("trunk", "head")}
        return lanes[lane]

    both("1_regression_prepared", lambda: form(ids[0], suitability="geen_kenniseenheid"), "prepared")
    both("1_regression", lambda: form(ids[0], suitability="geen_kenniseenheid"))
    both("2_mist_context", lambda: form(ids[0], suitability="mist_context"))
    both("3_allowed", lambda: form(next(free)))
    both("4_support", lambda: form(ids[0], suitability="alleen_onderbouwing"))
    both("5_later", lambda: form(next(free), eindoordeel="later_beoordelen", decision="later"))
    both("6_no_write", lambda: form(ids[0], suitability="samenvoegen"))

    def stale():
        data = form(ids[0], suitability="geen_kenniseenheid")
        mode("head", "serial")
        assert client.post("/review", data=form(next(free)), follow_redirects=False).status_code == 303
        return data
    both("7_stale", stale)
    both("8_revise", lambda: form(ids[0], suitability="samenvoegen", eindoordeel="goedkeuren_na_correctie",
                                  decision="revise", comment="Samenvoegen met de vorige passage."))
    both("9_unknown", lambda: form(ids[0], suitability="onbekend"))
    objects = {o["object_id"]: o for o in console.snapshot_objects(sid)}

    def same(lane, keys=("status", "error_code", "review_events_delta")):
        return all(lanes[lane]["trunk"][k] == lanes[lane]["head"][k] for k in keys)
    verdict = {
        "1": same("1_regression") and same("1_regression_prepared")
             and lanes["1_regression"]["head"]["error_code"] == "review_disposition_conflict"
             and not lanes["1_regression"]["head"]["store_transaction"]
             and not lanes["1_regression_prepared"]["head"]["store_transaction"],
        "2": same("2_mist_context") and lanes["2_mist_context"]["head"]["error_code"] == "review_disposition_conflict"
             and not lanes["2_mist_context"]["head"]["source_preparation"],
        "3": same("3_allowed", ("status", "review_events_delta")) and lanes["3_allowed"]["head"]["status"] == 303,
        "4": same("4_support") and lanes["4_support"]["head"]["error_code"] == "support_relation_required",
        "5": same("5_later", ("status", "review_events_delta")) and lanes["5_later"]["head"]["status"] == 303,
        "6": all(r["review_events_delta"] == 0 for r in lanes["6_no_write"].values()) and same("6_no_write"),
        "7": all(400 <= r["status"] < 500 and r["review_events_delta"] == 0 for r in lanes["7_stale"].values()),
        "8": same("8_revise", ("status", "error_code", "review_events_delta")),
        "9": same("9_unknown") and lanes["9_unknown"]["head"]["error_code"] == "suitability_required",
        "10": "no MCP review route: src/settings/metis_mcp_v1.py exposes only read-only tools "
              "(readOnlyHint true); nothing there calls review_object",
    }
    approved = [oid for oid in ids if (objects[oid].get("governance") or {}).get("validation_status") == "approved"]
    receipt = {"label": LABEL, "paragraphs": PARAGRAPHS, "runs": RUNS,
               "sources": {p: _sha(p) for p in ("src/review/review_command_v1.py",
                                                 "src/review/closed_review_loop_v1.py")},
               "perf": perf, "lanes": lanes, "lane_verdicts": verdict, "approved_objects": len(approved)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"probe-{LABEL}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("\nP3PROBE", json.dumps({"perf_rule": perf["rule"], "verdicts": verdict,
          "medians": {p: {n: [perf[p][n]["median_elapsed_ms"], perf[p][n]["median_db_queries"]]
                          for n in ("trunk", "head")} for p in ("serial", "prepared")}}))
