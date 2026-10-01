"""Bullet outcomes retain their shared routing context and separate exact reviews.

# release-control-evidence: kwaliteit
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
"""
from copy import deepcopy
import fitz
import pytest

from src.decision_graph_v1 import graph_issues, verify_source_evidence
from src.operations_console_v1 import ConsoleError
from tests.test_decision_graph_chain import _console, _accounts, _ingest_boom, policy, command


def test_pdf_bundle_needs_each_member_review_and_preserves_source(tmp_path):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((70, 80), "Plan:\n- Neem contact op.\n- Maak een afspraak.")
        data = doc.tobytes()
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = _ingest_boom(console, accounts, data=data, filename="bundle.pdf", content_type="application/pdf",
        named_reviewers=[], review_policy=policy(accounts))["snapshot_id"]
    env = console._envelope(sid)
    objects = [o for o in console.snapshot_objects(sid) if o["object_type"] != "document"]
    assert len(objects) == 3
    container = next(o for o in objects if o["metadata"]["result_bundle"]["role"] == "container")
    members = [o for o in objects if o["metadata"]["result_bundle"]["role"] == "member"]
    assert {o["content"]["clean_text"] for o in members} == {"- Neem contact op.", "- Maak een afspraak."}
    graph = deepcopy(env["decision_graph"])
    for node in graph["nodes"]:
        node["mode"] = "terminal" if node["object_id"] == container["object_id"] else "context"
    graph.update(entrypoints=[container["object_id"]], edges=[], unresolved=[])
    console.update_decision_graph(**command(console, accounts, sid, "bundle-graph", graph=graph))
    for obj in [container, members[0]]:
        console.review_object(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
            object_id=obj["object_id"], decision="approve", confirmed_object_type="path" if obj == container else "outcome",
            recommendation_strength=None if obj == container else "doen")
    def refresh_graph():
        updated = deepcopy(console._envelope(sid)["decision_graph"])
        versions = {o["object_id"]: o["object_version"] for o in console.snapshot_objects(sid)}
        for node in updated["nodes"]:
            node["object_version"] = versions[node["object_id"]]
        return updated
    console.update_decision_graph(**command(console, accounts, sid, "bundle-endpoints", graph=refresh_graph()))
    with pytest.raises(ConsoleError, match="decision_graph_passage_review_required"):
        console.confirm_decision_graph(**command(console, accounts, sid, "missing-member"))
    console.review_object(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
        object_id=members[1]["object_id"], decision="approve", confirmed_object_type="outcome", recommendation_strength="doen")
    console.update_decision_graph(**command(console, accounts, sid, "bundle-final", graph=refresh_graph()))
    console.confirm_decision_graph(**command(console, accounts, sid, "bundle-confirm"))
    env = console._envelope(sid)
    verify_source_evidence(console, env)
    assert graph_issues(env["decision_graph"], console.snapshot_objects(sid), env["decision_graph_evidence"]) == []
    detached = deepcopy(env["decision_graph"])
    next(n for n in detached["nodes"] if n["object_id"] == members[0]["object_id"])["mode"] = "terminal"
    assert "decision_graph_bundle_context_missing" in graph_issues(detached, console.snapshot_objects(sid), env["decision_graph_evidence"])


def test_explicit_json_bundle_preserves_legacy_source_adapter(tmp_path):
    import json
    from tests.test_v225_beslisboom_path import _boom_freeze_bytes
    payload = json.loads(_boom_freeze_bytes())
    payload["outcomes"][0]["text"] = "Plan:\n- Neem contact op.\n- Maak een afspraak."
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = _ingest_boom(console, accounts, data=json.dumps(payload).encode(), named_reviewers=[],
                       review_policy=policy(accounts))["snapshot_id"]
    objects = console.snapshot_objects(sid)
    assert len([o for o in objects if o.get("metadata", {}).get("result_bundle", {}).get("role") == "member"]) == 2
    verify_source_evidence(console, console._envelope(sid))
    successor = console.create_review_successor(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
        command_id="json-class", reason="Andere interpretatie", expected_revision=console.objects_revision(sid), class_="richtlijn")
    assert successor["content_kind"] == "boom"
    assert successor["sha256"] == console._envelope(sid)["sha256"]
    assert "decision_graph" not in successor
