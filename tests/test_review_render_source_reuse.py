"""#548: source-valid HTTP review reads reuse work without changing decisions.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from contextlib import contextmanager
import json
from types import MethodType, SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.document_status_ui_v1 import install_document_status_ui
from src.operations_console_app import create_console_app
from src.review_closure_v1 import ReviewClosureConsole
from src.review_workboard_v1 import install_review_workboard
from tests.semantic_fixture_support import bind_fixture_selections


@pytest.fixture
def review_client(tmp_path, request):
    console = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "source",
                                   runtime=tmp_path / "runtime")
    author = console.create_account(username="author", password="fixture-only", roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password="fixture-only", roles=("reviewer",))
    texts = [f"Begrip {i} is een beschrijving van een afzonderlijke waarneming." for i in range(20)]
    retained = getattr(request, "param", None) == "retained"
    if retained:
        from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
        from tests.test_recommendation_context_v3 import response_for
        core = "Gebruik geen zalf."
        texts.insert(0, core)

        def provider(_url, _headers, payload, _timeout):
            data = json.loads(payload["input"][1]["content"])
            proposal = (response_for(payload, core)
                        if not data.get("selection_targets") and any(core in b["text"] for b in data["source_blocks"])
                        else {"objects": [], "relations": [], "abstain_reason": "uncertain"})
            return {"status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": json.dumps(proposal)}]}]}

        bind_pre_review_semantic_processing(console, environ={
            "METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v3",
            "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "fixture",
        }, post_json=provider)
    else:
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


@pytest.mark.parametrize("review_client", ["retained"], indirect=True)
def test_postgres_overview_reuses_full_source_for_retained_records(review_client, monkeypatch):
    import src.knowledge_materialisation_v1 as materialisation
    import src.semantic_passage_v1 as semantic
    import src.review_workboard_v1 as workboard
    from src.source_accountability_v1 import is_source_record
    from src.workflows.workflow_badge_counts_postgres_v1 import _PostgresBadgeCountsMixin

    console, client, sid = review_client
    before = deepcopy(console.snapshot_objects(sid))
    assert sum(is_source_record(obj) for obj in before) == 20
    envelope = deepcopy(console._envelope(sid))
    batch_reads = []

    @contextmanager
    def connect():
        def execute(_sql, params):
            assert params[:2] == (envelope["named_reviewers"][0], None)
            return SimpleNamespace(fetchall=lambda: [{"snapshot_id": sid, "envelope_payload": deepcopy(envelope)}])
        yield SimpleNamespace(execute=execute)

    def objects(ids):
        assert ids == [sid]
        batch_reads.append(1)
        return {sid: deepcopy(before)}

    # Only storage adapters are disposable; run the production summary/enrichment
    # implementation and actual review-work-item calculation through HTTP.
    console.workflow_document_store = SimpleNamespace(_connect=connect, list_current_objects_batch=objects)
    console.workflow_review_store = SimpleNamespace(read_bindings=lambda ids: {sid: []})
    for name in ("review_workboard_summaries", "_enrich_review_workboard_summaries"):
        setattr(console, name, MethodType(getattr(_PostgresBadgeCountsMixin, name), console))
    renderer = workboard.review_work_item
    with monkeypatch.context() as baseline:
        baseline.setattr(workboard, "review_work_item", renderer.__wrapped__)
        expected = client.get("/review")
    assert expected.status_code == 200
    assert len(batch_reads) == 1

    original = semantic._reconstructed_blocks
    calls = []

    def counted(rows):
        calls.append(1)
        return original(rows)

    monkeypatch.setattr(semantic, "_reconstructed_blocks", counted)
    monkeypatch.setattr(materialisation, "_reconstructed_blocks", counted)
    for request_number in (2, 3):
        calls.clear()
        response = client.get("/review")
        assert response.status_code == 200
        assert response.text == expected.text
        # Full source and filtered candidate source are distinct views; neither
        # may be rebuilt for every retained source record.
        assert 1 <= len(calls) <= 2
        assert len(batch_reads) == request_number
    assert console.snapshot_objects(sid) == before
