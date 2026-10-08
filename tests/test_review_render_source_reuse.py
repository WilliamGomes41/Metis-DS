"""#548: source-valid HTTP review reads reuse work without changing decisions.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.document_status_ui_v1 import install_document_status_ui
from src.operations_console_app import create_console_app
from src.review_closure_v1 import ReviewClosureConsole
from src.review_workboard_v1 import install_review_workboard
from tests.semantic_fixture_support import bind_fixture_selections


@pytest.fixture
def review_client(tmp_path):
    console = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "source",
                                   runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming." for i in range(20)]
    bind_fixture_selections(console, [(text, "definition") for text in texts])
    sid = console.ingest(
        actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join(f"<p>{text}</p>" for text in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Review render proof", version="1.0", date="2026-10-08",
        live_url="", class_="richtlijn", family="fixture", named_reviewers=[reviewer["account_id"]],
    )["snapshot_id"]
    # PostgreSQL supplies this light list projection. Keep its storage I/O out
    # of this source-rendering regression; retain the actual middleware/routes.
    console.list_document_lifecycle_statuses = lambda: {sid: {
        "workflow_status": "in_review", "release_status": "none", "serving_status": "inactive",
        "presentation_status": "in_review",
    }}
    app = create_console_app(console)
    install_document_status_ui(app, console)
    install_review_workboard(app, console)
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                               follow_redirects=False)
        assert response.status_code == 303
        yield console, client, sid


@pytest.mark.parametrize("task", ["structure", "contextual", "batch", "inventory", "disposition",
                                  "waiting", "history", "second_review", "repair", "object"])
def test_http_review_render_reuses_source_and_matches_uncached_read(review_client, monkeypatch, task):
    import src.knowledge_materialisation_v1 as materialisation
    import src.operations_console_app as ui
    import src.review_workboard_v1 as workboard

    console, client, sid = review_client
    before = deepcopy(console.snapshot_objects(sid))
    params = {"document": sid, "task": task}
    if task == "object":
        params = {"document": sid, "object": next(
            obj["object_id"] for obj in before
            if (obj.get("metadata") or {}).get("semantic_passage", {}).get("spans"))}
    # Only generated form identifiers differ between identical read requests.
    monkeypatch.setattr(ui, "new_review_interaction_id", lambda: "fixture-interaction")
    monkeypatch.setattr(ui.uuid, "uuid4", lambda: UUID(int=1))
    renderer = workboard._render_review_room
    with monkeypatch.context() as baseline:
        baseline.setattr(workboard, "_render_review_room", getattr(renderer, "__wrapped__", renderer))
        expected = client.get("/review", params=params)
    assert expected.status_code == 200

    original = materialisation._selection_blocks
    calls = []

    def counted(rows):
        calls.append(1)
        return original(rows)

    monkeypatch.setattr(materialisation, "_selection_blocks", counted)
    for expected_calls in (1, 2):
        response = client.get("/review", params=params)
        assert response.status_code == 200
        assert response.text == expected.text
        assert len(calls) == expected_calls
    assert console.snapshot_objects(sid) == before
