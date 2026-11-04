"""#974 design prototype: which read carries Review-open JSON bytes.

Run (needs the tests/conftest.py fixtures and a test PostgreSQL):
    cp evidence/974-design/prototype_review_open_bytes.py tests/proto_974_b_tmp.py
    python -m pytest -q -s tests/proto_974_b_tmp.py; rm tests/proto_974_b_tmp.py
Measures db_json_bytes for GET /review?document=<sid> and, separately, for the
full envelope read and the review navigation read on the same document.
"""
from src.console_performance_v1 import performance_scope
from tests.test_navigation_source_reuse import bind_fixture_selections

PARAGRAPHS = 2000


def test_prototype(tmp_path, production_console, production_app):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg." for i in range(PARAGRAPHS)]
    bind_fixture_selections(console, [(t, "definition") for t in texts[:200]])
    sid = console.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{t}</p>" for t in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Prototype 974", version="1.0", date="2026-11-04", live_url="",
        class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    app = production_app(console)
    from fastapi.testclient import TestClient
    client = TestClient(app, base_url="https://testserver")
    login = client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                        headers={"origin": "https://testserver"}, follow_redirects=False)
    assert login.status_code in (302, 303), login.text[:200]
    import json, logging
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
        response = client.get(f"/review?document={sid}")
    finally:
        _LOGGER.removeHandler(handler)
    finished = [e for e in seen if e.get("event") == "request_finished"][-1]
    db = finished.get("db") or {}
    top = sorted(((v["inclusive_ms"], k) for k, v in (finished.get("phase_tree") or {}).items()), reverse=True)[:6]
    with performance_scope() as env:
        console._envelope(sid)
    with performance_scope() as hist:
        console._processing_history_envelope(sid)
    print(f"\nPROTOTYPE status={response.status_code} request_json_bytes={db.get('db_json_bytes')} "
          f"queries={db.get('db_queries')} elapsed_ms={finished.get('elapsed_ms')} top_phases={top} envelope_json_bytes={env.json_bytes} history_envelope_json_bytes={hist.json_bytes}")
