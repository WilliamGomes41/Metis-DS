from copy import deepcopy
import os
import uuid

import fitz
import pytest

from src.decision_graph_v1 import CONTRACT
from src.operations_console_v1 import ConsoleError
from tests.test_explicit_review_policy import policy
from tests.test_v225_beslisboom_path import _accounts, _console, _ingest_boom

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: beschikbaarheid
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs


def source_pdf():
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((80, 80), "Bespreek de situatie.")
        page.insert_text((80, 200), "Maak een vervolgafspraak.")
        page.draw_line((120, 90), (120, 180))
        return doc.tobytes()


def ingest(console, accounts, participation=None):
    return _ingest_boom(console, accounts, data=source_pdf(), filename="source.pdf",
                        content_type="application/pdf", named_reviewers=[],
                        review_policy=policy(accounts, participation))


def complete_graph(console, sid):
    env = console._envelope(sid)
    objects = [o for o in console.snapshot_objects(sid) if o["object_type"] != "document"]
    graphic = next(k for k, v in env["decision_graph_evidence"]["items"].items() if v["kind"] == "graphic")
    return {"contract": CONTRACT, "source_sha256": env["sha256"], "unresolved": [],
            "entrypoints": [objects[0]["object_id"]],
            "nodes": [{"object_id": o["object_id"], "object_version": o["object_version"],
                       "mode": "continue" if i == 0 else "terminal",
                       "evidence_ids": [o["provenance"]["source_fragments"][0]["raw_object_id"]]}
                      for i, o in enumerate(objects)],
            "edges": [{"id": "route-1", "from": objects[0]["object_id"], "to": objects[1]["object_id"],
                       "kind": "continue", "label": "", "evidence_ids": [graphic]}]}


def command(console, accounts, sid, command_id, **extra):
    return dict(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                expected_revision=console.objects_revision(sid), command_id=command_id,
                reason="Gecontroleerd tegen bron", **extra)


@pytest.mark.parametrize("participation", [None, "optional", "required"])
@pytest.mark.parametrize("backend", ["local", "postgres"])
def test_pdf_requires_passage_and_graph_review_after_restart(tmp_path, participation, backend):
    if backend == "postgres":
        from tests.decision_graph_native_support import native_state
        state, _, _ = native_state(tmp_path)
    else:
        state = lambda: _console(tmp_path)
    console = state()
    accounts = _accounts(console)
    receipt = ingest(console, accounts, participation)
    sid = receipt["snapshot_id"]
    assert receipt["content_kind"] == "pdf"
    assert receipt["class"] == "beslisboom"
    assert "decision_graph_unresolved" in console.consider_publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)["blockers"]
    console.update_decision_graph(**command(console, accounts, sid, "initial-graph", graph=complete_graph(console, sid)))
    for o in console.snapshot_objects(sid):
        if o["object_type"] != "document":
            console.review_object(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                                  object_id=o["object_id"], decision="approve", confirmed_object_type="node")
    graph = complete_graph(console, sid)
    cmd = command(console, accounts, sid, "graph-1", graph=graph)
    console.update_decision_graph(**cmd)
    assert console.update_decision_graph(**cmd)["idempotent"]
    console.confirm_decision_graph(**command(console, accounts, sid, "confirm-1"))
    console = state()
    result = console.consider_publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
    assert ("decision_graph_review_incomplete" in result["blockers"]) == (participation == "required")
    if backend == "postgres":
        assert console.waiting_task_counts(accounts["researcher"]["account_id"])["review"] == 0
        if participation == "required":
            assert console.waiting_task_counts(accounts["reviewer"]["account_id"])["review"] == 1
    if participation == "required":
        secondary = accounts["reviewer"]["account_id"]
        cmd = command(console, accounts, sid, "confirm-2")
        cmd["actor_id"] = secondary
        with pytest.raises(ConsoleError, match="decision_graph_passage_review_required"):
            console.confirm_decision_graph(**cmd)
        for o in console.snapshot_objects(sid):
            if o["object_type"] != "document":
                console.approve_second_review(actor_id=secondary, snapshot_id=sid, object_id=o["object_id"])
        cmd["expected_revision"] = console.objects_revision(sid)
        console.confirm_decision_graph(**cmd)
        result = console.consider_publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
        assert "decision_graph_review_incomplete" not in result["blockers"]


def test_policy_change_is_versioned_and_replay_safe(tmp_path):
    from tests.test_review_participation_management import change
    from src.review_policy_v1 import object_policy
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    rev = console.objects_revision(sid)
    extra = dict(command_id="policy-1", expected_revision=rev)
    change(console, accounts, sid, "add_required", accounts["reviewer"]["account_id"], **extra)
    assert change(console, accounts, sid, "add_required", accounts["reviewer"]["account_id"], **extra)["idempotent"]
    with pytest.raises(ConsoleError, match="participation_command_conflict"):
        change(console, accounts, sid, "add_optional", accounts["reviewer"]["account_id"], **extra)
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        change(console, accounts, sid, "archive", accounts["reviewer"]["account_id"], expected_revision=rev)
    console = _console(tmp_path)
    p = console._envelope(sid)["review_policy"]
    assert p["revision"] == 2
    assert all(object_policy(o) == p for o in console.snapshot_objects(sid))


def test_text_cannot_replace_graphic_evidence(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    graph = complete_graph(console, sid)
    graph["edges"][0]["evidence_ids"] = graph["nodes"][0]["evidence_ids"]
    with pytest.raises(ConsoleError, match="decision_graph_graphic_evidence_missing"):
        console.update_decision_graph(**command(console, accounts, sid, "bad-graph", graph=graph))


def test_graph_review_form_and_class_conversion_cannot_drop_routes(tmp_path):
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    with TestClient(create_console_app(console), base_url="https://testserver") as client:
        client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
        response = client.get("/review/decision-graph", params={"document": sid})
        assert response.status_code == 200, response.text
        assert "Beslisroutes controleren" in response.text
        assert "Lijnbewijs" in response.text
        response = client.get("/review/policy", params={"document": sid})
        assert response.status_code == 200, response.text
        assert "Primaire reviewer" in response.text
    before = deepcopy(console._envelope(sid))
    with pytest.raises(ConsoleError, match="decision_graph_class_change_requires_successor"):
        console.promote_class(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                              new_class="richtlijn", reextract=True)
    assert console._envelope(sid) == before


def finish(console, accounts, sid):
    console.update_decision_graph(**command(console, accounts, sid, "draft", graph=complete_graph(console, sid)))
    for o in console.snapshot_objects(sid):
        if o["object_type"] != "document":
            console.review_object(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                                  object_id=o["object_id"], decision="approve", confirmed_object_type="node")
    console.update_decision_graph(**command(console, accounts, sid, "endpoints", graph=complete_graph(console, sid)))
    console.confirm_decision_graph(**command(console, accounts, sid, "confirmed"))


def test_durable_release_keeps_graph_out_of_prose_and_restarts(tmp_path):
    from src.durable_publication_console_v1 import DurablePublicationConsole
    from src.decision_graph_v1 import read_active_graph
    from tests.test_durable_publication_console_v1 import MemoryCanonicalStore, MemorySourceStore

    class GraphStore(MemoryCanonicalStore):
        withdrawn = False

        def release_for_snapshot(self, sid):
            release = super().release_for_snapshot(sid)
            if release:
                release["decision_graph_release"] = deepcopy(self.releases[release["release_id"]]["decision_graph_release"])
            return release

        def active_publication_rows(self):
            return [] if self.withdrawn else super().active_publication_rows()

    store, source = GraphStore(), MemorySourceStore()
    def state():
        return DurablePublicationConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime",
                                         canonical_publication_store=store, immutable_source_store=source)
    console = state()
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    finish(console, accounts, sid)
    result = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
    assert result["status"] == "PASS", result
    graph = read_active_graph(store, source, sid)
    assert graph["applicability"] == "not_evaluated"
    assert len(graph["graph"]["edges"]) == 1
    assert console._projection_from_authority() == []
    from fastapi.testclient import TestClient
    from src.product_api_v1 import create_product_app
    from src.usage_ledger_v1 import UsageLedger
    from tests.test_product_api_postgres_authority_v1 import _paths, _registry, KEY
    paths = _paths(tmp_path)
    client = TestClient(create_product_app("real", paths=paths, tenant_registry=_registry(),
        canonical_publication_store=store, immutable_source_store=source,
        usage_ledger=UsageLedger(paths.usage_db)))
    endpoint = f"/v1/decision-graphs/{sid}"
    assert client.get(endpoint).status_code == 401
    headers = {"Authorization": f"Bearer {KEY}"}
    response = client.get(endpoint, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["graph"] == graph["graph"]
    assert response.json()["applicability"] == "not_evaluated"
    assert response.json()["generation_enabled"] is False
    assert "reviews" not in response.json()
    restarted = state()
    restarted.reconcile_durable_publications()
    assert read_active_graph(store, source, sid) == graph
    assert restarted.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)["release_id"] == result["release_id"]
    with pytest.raises(ConsoleError, match="published_working_revision_immutable"):
        restarted.change_review_policy(**command(restarted, accounts, sid, "new-policy", policy=policy(accounts, "required")))
    # Registry withdrawal removes the graph immediately; immutable evidence survives.
    store.withdrawn = True
    assert read_active_graph(store, source, sid) is None
    assert client.get(endpoint, headers=headers).status_code == 404
    assert store.release_for_snapshot(sid)["decision_graph_release"]["graph"] == graph["graph"]


def test_route_change_invalidates_passages_and_reextract_preserves_policy(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    finish(console, accounts, sid)
    graph = complete_graph(console, sid)
    graph["edges"] = []
    graph["nodes"][0]["mode"] = "terminal"
    graph["entrypoints"].append(graph["nodes"][1]["object_id"])
    console.update_decision_graph(**command(console, accounts, sid, "correct-route", graph=graph))
    assert not any(r["valid"] for r in console.object_review_bindings(sid))
    with pytest.raises(ConsoleError, match="decision_graph_passage_review_required"):
        console.confirm_decision_graph(**command(console, accounts, sid, "cannot-skip"))
    console.reextract_unpublished(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid)
    assert console._envelope(sid)["review_policy"] == policy(accounts)
    assert all(o["metadata"]["review_policy"] == policy(accounts) for o in console.snapshot_objects(sid))
    assert console._envelope(sid)["decision_graph"]["unresolved"]


def test_ingest_command_deduplicates_and_rejects_changed_payload(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    kwargs = dict(data=source_pdf(), filename="source.pdf", content_type="application/pdf",
                  named_reviewers=[], review_policy=policy(accounts), command_id="one-upload")
    receipt = _ingest_boom(console, accounts, **kwargs)
    restarted = _console(tmp_path)
    assert _ingest_boom(restarted, accounts, **kwargs)["snapshot_id"] == receipt["snapshot_id"]
    assert len(restarted.list_envelopes()) == 1
    with pytest.raises(ConsoleError, match="ingest_command_conflict"):
        _ingest_boom(restarted, accounts, **{**kwargs, "title": "Different"})


def test_native_postgres_graph_publication_restart_and_withdrawal(tmp_path):
    from datetime import datetime, timedelta
    from tests.decision_graph_native_support import native_state
    from src.decision_graph_v1 import read_active_graph
    state, store, source = native_state(tmp_path)
    console = state()
    suffix = uuid.uuid4().hex[:10]
    accounts = {name: console.create_account(username=f"{name}-{suffix}", password="test-only-local-secret", roles=roles)
                for name, roles in [("researcher", ("researcher", "reviewer")), ("reviewer", ("reviewer",)), ("publisher", ("publisher",))]}
    sid = ingest(console, accounts)["snapshot_id"]
    finish(console, accounts, sid)
    result = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
    assert result["status"] == "PASS", result
    before = read_active_graph(store, source, sid)
    restarted = state()
    assert restarted._envelope(sid)["review_policy"] == policy(accounts)
    assert read_active_graph(store, source, sid) == before
    env = restarted._envelope(sid)
    published_at = datetime.fromisoformat(store.release_for_snapshot(sid)["published_at"])
    store.withdraw_logical_document(logical_document_id=env["logical_document_id"], expected_release_id=result["release_id"],
        actor="test-reviewer", reason="Test withdrawal", withdrawn_at=(published_at + timedelta(seconds=1)).isoformat())
    assert read_active_graph(store, source, sid) is None
    assert store.release_for_snapshot(sid)["decision_graph_release"]["graph"] == before["graph"]
