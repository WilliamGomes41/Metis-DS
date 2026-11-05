"""#974 P4b: one repair render reads its document and source once.

A revise decision on ``POST /review`` renders the repair page in the
structured-repair exception handler. The page must read the document
envelope, its current objects and the prepared review source at most once,
as the ``GET /source-selection?task=repair`` page does, and its HTML must not
change.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from collections import Counter
from contextlib import contextmanager, nullcontext

import pytest
from fastapi.testclient import TestClient

from tests.semantic_fixture_support import bind_fixture_selections

PARAGRAPHS = 30
SELECTED = 3
# One read each: the envelope, the object histories (for the snapshot
# revision), the current objects and the prepared review source.
ONCE = {"get_envelope": 1, "list_document_objects": 1, "current_document_objects": 1, "read_review_source": 1}


def _text(index):
    return (f"Begrip {index} is een beschrijving van een afzonderlijke waarneming in de zorg. "
            f"De verpleegkundige legt waarneming {index} vast.")


@pytest.fixture
def repair_document(tmp_path, production_console, production_app):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path,
                                 source_store=tmp_path / "source", runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [_text(i) for i in range(PARAGRAPHS)]
    bind_fixture_selections(console, [(text, "definition") for text in texts[:SELECTED]])
    sid = console.ingest(
        actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body><h1>Richtlijn</h1>" + "".join(f"<p>{t}</p>" for t in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Repair reads once", version="1.0", date="2026-11-05", live_url="",
        class_="richtlijn", family="probe", named_reviewers=[reviewer["account_id"]],
    )["snapshot_id"]
    obj = next(row for row in console.snapshot_objects(sid)
               if (row.get("content") or {}).get("clean_text") == _text(0))
    client = TestClient(production_app(console), base_url="https://testserver")
    login = client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                        headers={"origin": "https://testserver"}, follow_redirects=False)
    assert login.status_code in (302, 303)
    return console, client, sid, obj


def _revise(console, sid, obj):
    return {"snapshot_id": sid, "object_id": obj["object_id"], "snapshot_revision": console.objects_revision(sid),
            "suitability": "mist_context", "documentpositie_action": "dit_klopt", "type_action": "dit_klopt",
            "proposed_object_type": "definition", "eindoordeel": "goedkeuren_na_correctie",
            "comment": "Context ontbreekt."}


@contextmanager
def render_reads(monkeypatch, console):
    """Count authoritative store reads made while the repair page renders."""
    from src.review import deterministic_review_repair_v1 as repair
    from src.workflows.formation_task_store_v1 import FormationTaskStore
    reads, rendering = [], []
    store = type(console.workflow_document_store)

    def counted(owner, name):
        original = getattr(owner, name)

        def call(*args, **kwargs):
            if rendering:
                reads.append(name)
            return original(*args, **kwargs)
        monkeypatch.setattr(owner, name, call)

    for name in ("get_envelope", "current_document_objects", "list_document_objects"):
        counted(store, name)
    counted(FormationTaskStore, "read_review_source")
    render = repair.render_repair

    def observed(*args, **kwargs):
        rendering.append(True)
        try:
            return render(*args, **kwargs)
        finally:
            rendering.pop()
    monkeypatch.setattr(repair, "render_repair", observed)
    yield reads


def test_revise_repair_page_reads_document_and_source_once(repair_document, monkeypatch):
    console, client, sid, obj = repair_document
    with render_reads(monkeypatch, console) as reads:
        response = client.post("/review", data=_revise(console, sid, obj), headers={"origin": "https://testserver"})
    assert response.status_code == 200
    assert "Correctie specificeren" in response.text
    assert dict(Counter(reads)) == ONCE


def test_get_repair_page_reads_document_and_source_once(repair_document, monkeypatch):
    console, client, sid, obj = repair_document
    with render_reads(monkeypatch, console) as reads:
        response = client.get(f"/source-selection?document={sid}&object={obj['object_id']}&task=repair")
    assert response.status_code == 200
    assert dict(Counter(reads)) == ONCE


def test_repair_page_html_is_unchanged_by_the_read_snapshot(repair_document, monkeypatch):
    """The page equals one rendered with every read going to PostgreSQL."""
    console, client, sid, obj = repair_document
    payload = _revise(console, sid, obj)
    headers = {"origin": "https://testserver"}
    scoped = client.post("/review", data=payload, headers=headers)
    with monkeypatch.context() as patch:
        patch.setattr(type(console), "document_read_operation", lambda self, **_: nullcontext())
        unscoped = client.post("/review", data=payload, headers=headers)
    assert scoped.status_code == unscoped.status_code == 200
    assert scoped.text == unscoped.text
    # Every sentence of every content paragraph is offered once as a source unit.
    assert scoped.text.count('<option value="') == 2 * PARAGRAPHS
    assert f"De verpleegkundige legt waarneming {PARAGRAPHS - 1} vast.</option>" in scoped.text
    assert f"<p><b>Huidige passage:</b> {_text(0)}</p>" in scoped.text
