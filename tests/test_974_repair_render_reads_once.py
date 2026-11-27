"""Detached reads of the persisted review object remain independent.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest
from fastapi.testclient import TestClient

from tests.semantic_fixture_support import bind_fixture_selections

PARAGRAPHS = 30
SELECTED = 3


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
    return console, _signed_in(production_app(console)), sid, obj


def _signed_in(app):
    client = TestClient(app, base_url="https://testserver")
    login = client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                        headers={"origin": "https://testserver"}, follow_redirects=False)
    assert login.status_code in (302, 303)
    return client








def test_current_object_stays_a_detached_copy_inside_a_read_snapshot(repair_document):
    """The repair readers borrow the snapshot's rows; their callers still own a copy."""
    console, _client, sid, obj = repair_document
    with console.document_read_operation():
        mine = console._current_object(sid, obj["object_id"])
        mine["content"]["clean_text"] = "Gewijzigd."
        mine["governance"]["validation_status"] = "approved"
        again = console._current_object(sid, obj["object_id"])
        listed = next(row for row in console.snapshot_objects(sid) if row["object_id"] == obj["object_id"])
    assert again["content"]["clean_text"] == listed["content"]["clean_text"] == _text(0)
    assert again["governance"]["validation_status"] == listed["governance"]["validation_status"] == "needs_review"
    assert again is not mine
