"""Decision review keeps evidence separate from help without changing authority.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import fitz
import pytest
from fastapi.testclient import TestClient

from tests.test_decision_graph_chain import _accounts, _console, _ingest_boom, policy


@pytest.mark.parametrize("source", ["pdf", "bundle", "export"])
def test_decision_review_moves_type_explanations_to_help_without_mutating_evidence(tmp_path, source, *, production_app, production_console):
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    kwargs = {}
    if source != "export":
        with fitz.open() as doc:
            page = doc.new_page()
            page.insert_text((70, 80), "Plan:\n- Neem contact op.\n- Maak een afspraak."
                             if source == "bundle" else "Is er valrisico?")
            kwargs = dict(data=doc.tobytes(), filename="boom.pdf", content_type="application/pdf")
    sid = _ingest_boom(console, accounts, named_reviewers=[], review_policy=policy(accounts), **kwargs)["snapshot_id"]
    before = deepcopy(console.snapshot_objects(sid))
    envelope = deepcopy(console._envelope(sid))
    client = TestClient(production_app(console))
    assert client.get(f"/review?document={sid}", follow_redirects=False).status_code == 401
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    graph = client.get("/review/decision-graph", params={"document": sid})
    assert graph.status_code == 200
    for obj in before:
        if obj["object_type"] == "document":
            continue
        legacy = client.get("/source-selection", params={
            "document": sid, "object": obj["object_id"], "task": "repair", "repair_kind": "classification"
        }, follow_redirects=False)
        assert legacy.status_code == 404
    for label in ("Pad — route of resultaatbundel", "Knoop — vraag of beslispunt", "Uitkomst — afsluitend advies"):
        assert label in graph.text
    assert "scorelijstitem" not in graph.text and "Een pad is zelf geen advies" not in graph.text
    help_page = client.get("/help/review")
    assert help_page.status_code == 200
    assert "scorelijstitem" in help_page.text and "Een pad is zelf geen advies" in help_page.text
    assert "geen inhoudelijke classificatie" in help_page.text
    graph = client.get(f"/review/decision-graph?document={sid}")
    assert graph.status_code == 200
    assert 'name="node_mode"' not in graph.text
    graph = client.get(f"/source-selection?document={sid}&task=graph")
    assert "Verbinding 1" in graph.text and "Soort verbinding" in graph.text
    assert "Een route bestaat uit opeenvolgende stappen" not in graph.text
    assert 'href="/help/review"' in graph.text
    assert "Verbindingen opslaan" in graph.text
    assert console.snapshot_objects(sid) == before
    assert console._envelope(sid) == envelope

@pytest.mark.parametrize("passage_type", ["node", "path", "outcome"])
def test_passage_type_repair_reopens_the_exact_passage(tmp_path, production_app, production_console, monkeypatch, passage_type):
    from tests.test_source_context_review_ui_v1 import Forms
    from tests.test_decision_graph_chain import complete_graph, command, ingest

    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    console.update_decision_graph(**command(console, accounts, sid, "routes", graph=complete_graph(console, sid)))
    client = TestClient(production_app(console), base_url="https://testserver")
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    url = "/review/decision-graph"
    view = client.get(url, params={"document": sid})
    form = next(form for form in Forms(view.text).forms
                if any(field.get("name") == "object_id" for field in form["inputs"]))
    fields = {field["name"]: field["value"] for field in form["inputs"] if field.get("type") == "hidden"}
    fields.update(action="classification", confirmed_object_type=passage_type, reason="Type gecontroleerd tegen de bron.")
    before = console._current_object(sid, fields["object_id"])
    for invalid in ({"confirmed_object_type": "heading"}, {"expected_revision": ""}):
        assert client.post(url, data={**fields, **invalid}).status_code == 400
    outsider = TestClient(production_app(console), base_url="https://testserver")
    outsider.post("/login", data={"username": "publisher.carla", "password": "carla-secret"})
    assert outsider.post(url, data=fields).status_code in (400, 403)
    assert console.objects_revision(sid) == fields["expected_revision"]
    with monkeypatch.context() as patch:
        patch.setattr(console, "snapshot_is_published", lambda _sid: True)
        assert 'value="classification"' not in client.get(url, params={"document": sid}).text
        assert client.post(url, data=fields).status_code == 400
        assert console.objects_revision(sid) == fields["expected_revision"]
    result = client.post(url, data=fields, follow_redirects=False)
    assert result.status_code == 303, result.text
    assert result.headers["location"] == url + "?document=" + sid + "#passage-" + fields["object_id"]
    updated = console._current_object(sid, fields["object_id"])
    assert updated["confirmed_object_type"] == passage_type
    assert updated["object_version"] != before["object_version"]
    assert updated["governance"]["validation_status"] == "needs_review"
    assert updated["provenance"]["source_fragments"] == before["provenance"]["source_fragments"]
    revision = console.objects_revision(sid)
    assert client.post(url, data=fields).status_code in (400, 409)
    assert console.objects_revision(sid) == revision
    assert _console(tmp_path, production_console=production_console)._current_object(sid, fields["object_id"]) == updated


def test_structural_heading_never_receives_a_route_type(tmp_path, production_app, production_console):
    """A heading in a decision tree keeps its structural type; no form and no command (#1180)."""
    from tests.semantic_fixture_support import install_fixture_history
    from tests.test_decision_graph_chain import ingest

    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    rows = console._load_objects(sid)
    heading = next(row for row in rows if row["object_type"] != "document")
    heading.update(object_type="heading", proposed_object_type="heading")
    install_fixture_history(console, sid, rows)
    client = TestClient(production_app(console), base_url="https://testserver")
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    url = "/review/decision-graph"
    view = client.get(url, params={"document": sid})
    assert view.status_code == 200
    assert f'id="passage-{heading["object_id"]}"' not in view.text
    before = deepcopy(console._current_object(sid, heading["object_id"]))
    revision = console.objects_revision(sid)
    for passage_type in ("node", "path", "outcome"):
        response = client.post(url, data={"document": sid, "expected_revision": revision, "object_id": heading["object_id"],
                                          "action": "classification", "confirmed_object_type": passage_type,
                                          "reason": "Kop als route opslaan."})
        assert response.status_code == 400
    assert console.objects_revision(sid) == revision
    assert console._current_object(sid, heading["object_id"]) == before


def test_graph_context_passage_never_receives_a_route_type(tmp_path, production_app, production_console):
    """A context-only graph node supports routes; it gets no form and no type command (#1180)."""
    from tests.test_decision_graph_chain import command, complete_graph, ingest

    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    graph = complete_graph(console, sid)
    # Fixture has two passages: one terminal route passage and one context-only passage.
    graph["nodes"][0]["mode"], graph["edges"] = "terminal", []
    context = graph["nodes"][-1]
    context["mode"] = "context"
    console.update_decision_graph(**command(console, accounts, sid, "context", graph=graph))
    client = TestClient(production_app(console), base_url="https://testserver")
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    url = "/review/decision-graph"
    view = client.get(url, params={"document": sid})
    assert view.status_code == 200
    assert f'id="passage-{context["object_id"]}"' not in view.text
    assert 'id="passage-' + graph["nodes"][0]["object_id"] + '"' in view.text
    before = deepcopy(console._current_object(sid, context["object_id"]))
    revision = console.objects_revision(sid)
    for passage_type in ("node", "path", "outcome"):
        response = client.post(url, data={"document": sid, "expected_revision": revision,
                                          "object_id": context["object_id"], "action": "classification",
                                          "confirmed_object_type": passage_type, "reason": "Context als route opslaan."})
        assert response.status_code == 400
    assert console.objects_revision(sid) == revision
    assert console._current_object(sid, context["object_id"]) == before
    link = "Passagetype in de beslisboomreview bekijken"
    card = client.get("/review", params={"document": sid, "object": context["object_id"]})
    route = client.get("/review", params={"document": sid, "object": graph["nodes"][0]["object_id"]})
    assert card.status_code == route.status_code == 200
    assert link not in card.text and link in route.text
