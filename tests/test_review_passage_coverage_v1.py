"""#405: counts never hide open source work.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import re
import pytest

from src.operations_console_app import _render_review_index
from src.publication_readiness_v1 import review_followup_queues, source_passage_closure
from src.review_workboard_v1 import review_work_item, _workboard_card
from src.review_duty_v1 import reviewer_route_counts
from tests.test_vsa_review_workboard_v1 import (
    _QueueConsole, _account, _envelope, _obj, _system, _client, _login,
)


def _inventory_ids(html):
    return re.findall(r'data-passage-id="([^"]+)"', html)


def test_343_to_5_keeps_all_338_missing_admission_passages_reachable():
    objects = [_obj(f"allowed-{i}", "recommendation") for i in range(5)]
    objects += [_obj(f"missing-{i}", "recommendation", gate_result=None) for i in range(338)]
    before = deepcopy(objects)
    console = _QueueConsole(objects)
    item = review_work_item(console, account=_account(), envelope=_envelope())
    assert item["actionable_contextual_duties"] == 5
    assert item["closure_gap_count"] == 338
    assert not item["source_passage_review_complete"]
    card = _workboard_card(item)
    assert 'task=disposition">338 bronpassages afhandelen' in card
    assert 'task=inventory' in card

    contextual = _render_review_index("snap-test", objects, "tekst", task="contextual", bindings=[])
    assert "allowed-0" in contextual
    assert "missing-0" not in contextual
    remaining = _render_review_index("snap-test", objects, "tekst", task="disposition", bindings=[])
    assert set(_inventory_ids(remaining)) == {f"missing-{i}" for i in range(338)}
    assert "Toelating ontbreekt of is onbekend" in remaining
    inventory = _render_review_index("snap-test", objects, "tekst", task="inventory", bindings=[])
    assert len(_inventory_ids(inventory)) == 343
    assert len(set(_inventory_ids(inventory))) == 343
    assert objects == before  # All projections are read-only.


def test_followup_counts_lists_and_final_blocked_history_are_disjoint():
    blocked = _obj("blocked", "recommendation", gate_result="blocked")
    final = _obj("excluded", "recommendation", gate_result="blocked", validation_status="rejected")
    final["metadata"]["passage_register"].update(status="excluded_with_reason", source="review")
    unknown = _obj("unknown", "recommendation", gate_result=None)
    unknown["metadata"]["passage_register"] = {}
    objects = [blocked, final, unknown]
    queues = review_followup_queues(objects, review_path="tekst", bindings=[])
    assert [r["object_id"] for r in queues["repair"]] == ["blocked"]
    assert [r["object_id"] for r in queues["disposition"]] == ["unknown"]
    for task in ("repair", "disposition"):
        html = _render_review_index("snap", objects, "tekst", task=task, bindings=[])
        assert set(_inventory_ids(html)) == {r["object_id"] for r in queues[task]}
    dashboard = _render_review_index("snap", objects, "tekst", bindings=[])
    assert "Alle reviewtaken zijn afgerond" not in dashboard
    assert 'task=disposition' in dashboard
    assert 'task=repair' in dashboard
    inventory = _render_review_index("snap", objects, "tekst", task="inventory", bindings=[])
    assert set(_inventory_ids(inventory)) == {"blocked", "excluded", "unknown"}
    assert 'object=excluded&amp;task=history' in inventory


def test_open_second_review_is_not_reclassified_as_missing_disposition():
    obj = _obj("second", "exception")
    obj.update(object_version="1.0", confirmed_object_type="exception", provenance={"canonical_object_hash": "hash"})
    binding = dict(valid=True, decision="approve", object_id="second", object_version="1.0",
                   canonical_object_hash="hash", confirmed_object_type="exception", reviewer_id="reviewer-a")
    queues = review_followup_queues([obj], review_path="tekst", bindings=[binding])
    assert queues == {"repair": [], "disposition": []}
    waiting = _render_review_index("snap", [obj], "tekst", task="waiting", bindings=[binding], reviewer_id="reviewer-a")
    assert _inventory_ids(waiting) == ["second"]
    assert 'data-passage-category="waiting"' in waiting
    assert reviewer_route_counts([obj], review_path="tekst", bindings=[binding], reviewer_id="reviewer-b")["actionable_second_review_duties"] == 1


@pytest.mark.parametrize("gate,task", [(None, "disposition"), ("blocked", "repair")])
def test_http_followup_is_reachable_and_can_be_resolved_without_losing_history(tmp_path, gate, task):
    console, accounts, receipt, _ = _system(tmp_path)
    sid = receipt["snapshot_id"]
    objects = console._load_objects(sid)
    target = next(o for o in objects if o["object_type"] not in {"document", "heading"})
    target["object_type"] = "unclassified"
    target["confirmed_object_type"] = None
    target["proposed_object_type"] = "recommendation"
    target.setdefault("metadata", {}).pop("admission", None)
    if gate:
        target["metadata"]["admission"] = {"gate_result": gate, "reason_codes": ["source_fidelity_failure"]}
    target["metadata"]["passage_register"] = {"status": "not_yet_assessed", "source": "extract"}
    console._save_objects(sid, objects)
    before = console.objects_revision(sid)
    client = _client(console)
    _login(client, accounts["reviewer_a"]["username"])
    response = client.get(f"/review?document={sid}&task={task}")
    assert response.status_code == 200
    assert target["object_id"] in _inventory_ids(response.text)
    detail = client.get(f"/review?document={sid}&task={task}&object={target['object_id']}")
    assert detail.status_code == 200
    assert ("technisch geblokkeerd" if gate else "technische toelating") in detail.text
    assert "Metis heeft de technische controles uitgevoerd" not in detail.text
    assert console.objects_revision(sid) == before
    assert not source_passage_closure(console.snapshot_objects(sid))["source_passage_review_complete"]
    submission = dict(snapshot_id=sid, object_id=target["object_id"], snapshot_revision=before,
                      suitability="geen_kenniseenheid", eindoordeel="afwijzen",
                      comment="Geen zelfstandige kennispassage", return_task=task)
    # Read access retains the existing policy; mutations require assignment.
    _login(client, accounts["reviewer_b"]["username"])
    denied = client.post("/review", data=submission, follow_redirects=False)
    assert denied.status_code in {400, 403}, denied.text
    assert "reviewer_not_named_on_snapshot" in denied.text
    assert console.objects_revision(sid) == before
    _login(client, accounts["reviewer_a"]["username"])
    saved = client.post("/review", data=submission, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    assert f"task={task}" in saved.headers["location"]
    remaining = client.get(saved.headers["location"])
    assert target["object_id"] not in _inventory_ids(remaining.text)
    inventory = client.get(f"/review?document={sid}&task=inventory")
    assert target["object_id"] in _inventory_ids(inventory.text)
    assert "Gemotiveerd uitgesloten" in inventory.text
    duplicate = client.post("/review", data=submission, follow_redirects=False)
    assert duplicate.status_code == 409
