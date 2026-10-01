"""Successors preserve published history and source bytes under new policy/class.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: toegang
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import pytest

from src.operations_console_v1 import ConsoleError
from tests.test_decision_graph_chain import _console, _accounts, ingest, finish, policy


def test_successor_keeps_source_and_prior_graph_with_new_object_identity(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    before = deepcopy(console._envelope(sid))
    command = dict(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                   command_id="successor", expected_revision=console.objects_revision(sid),
                   reason="Herbeoordeling van deelname")
    result = console.create_review_successor(**command)
    successor = console._envelope(result["snapshot_id"])
    assert successor["sha256"] == before["sha256"]
    assert successor["version"] == before["version"]
    assert successor["document_id"] != before["document_id"]
    assert successor["replaces_snapshot_id"] == sid
    assert successor["review_policy"]["revision"] == 2
    assert successor["decision_graph_reviews"] == []
    assert console._envelope(sid) == before
    assert console.create_review_successor(**command)["snapshot_id"] == result["snapshot_id"]
    with pytest.raises(ConsoleError, match="ingest_command_conflict"):
        console.create_review_successor(**{**command, "reason": "Conflicterende herhaling"})
    converted = console.create_review_successor(**{**command, "command_id": "convert", "class_": "richtlijn"})
    assert "decision_graph" not in console._envelope(converted["snapshot_id"])
    assert console._envelope(sid) == before
    converted_id = converted["snapshot_id"]
    back = console.create_review_successor(**{**command, "snapshot_id": converted_id,
        "expected_revision": console.objects_revision(converted_id), "command_id": "back-to-graph", "class_": "beslisboom"})
    assert console._envelope(back["snapshot_id"])["decision_graph"]["unresolved"]
    assert back["sha256"] == before["sha256"]


def test_successor_form_uses_kernel_command_and_requires_reason(tmp_path):
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    with TestClient(create_console_app(console), base_url="https://testserver") as client:
        client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
        form = client.get("/review/policy", params={"document": sid})
        assert 'formaction="/review/successor"' in form.text
        response = client.post("/review/successor", data={"document": sid,
            "expected_revision": console.objects_revision(sid), "command_id": "ui-successor",
            "reason": "Nieuwe controle", "primary": accounts["researcher"]["account_id"],
            "policy_revision": "2", "new_class": "beslisboom"}, follow_redirects=False)
        assert response.status_code == 303, response.text
        assert response.headers["location"] != f"/review/policy?document={sid}"
    assert len(console.list_envelopes()) == 2


def test_native_successor_cutover_and_failed_publication_preserve_v1(tmp_path, monkeypatch):
    from tests.decision_graph_native_support import native_state
    from src.decision_graph_v1 import read_active_graph
    from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError
    state, store, source = native_state(tmp_path)
    console = state()
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    finish(console, accounts, sid)
    v1 = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
    assert v1["status"] == "PASS"
    prior = deepcopy(console._envelope(sid))
    command = dict(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
        command_id="new-policy", expected_revision=console.objects_revision(sid), reason="Nieuwe beoordeling")
    sid2 = console.create_review_successor(**command)["snapshot_id"]
    assert console._envelope(sid2)["logical_document_id"] == prior["logical_document_id"]
    assert read_active_graph(store, source, sid)["release_id"] == v1["release_id"]
    assert read_active_graph(store, source, sid2) is None
    finish(console, accounts, sid2)
    original = store.persist_published_release
    def fail(**kwargs):
        raise CanonicalPublicationStoreError("test_failure_before_commit")
    monkeypatch.setattr(store, "persist_published_release", fail)
    with pytest.raises(ConsoleError) as failure:
        console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid2)
    assert failure.value.code == "durable_publication_store_failed"
    assert read_active_graph(store, source, sid)["release_id"] == v1["release_id"]
    monkeypatch.setattr(store, "persist_published_release", original)
    v2 = state().publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid2)
    assert v2["status"] == "PASS", v2
    assert read_active_graph(store, source, sid) is None
    assert read_active_graph(store, source, sid2)["release_id"] == v2["release_id"]
    assert store.release_for_snapshot(sid)["decision_graph_release"]["policy"]["revision"] == 1
