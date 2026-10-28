from tests.semantic_fixture_support import install_fixture_history
from test_t4_single_knowledge_path_invariants import _allowed_source
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
from src.publication.publication_readiness_v1 import review_followup_queues, source_passage_closure
from src.review.review_workboard_v1 import review_work_item, _workboard_card
from src.review.review_duty_v1 import reviewer_route_counts
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
    assert 'data-personal-open>5<' in card
    assert 'task=contextual' in card
    assert '338' not in card  # Source handling is owned by Vorming, not personal review.
    assert 'task=disposition' not in card
    assert 'task=inventory' not in card

    contextual = _render_review_index("snap-test", objects, "tekst", task="contextual", bindings=[], fragments=_allowed_source())
    assert "allowed-0" in contextual
    assert "missing-0" not in contextual
    from src.vorming.prepared_source_views_v1 import prepare
    fragments = prepare(_allowed_source()).fragments
    for task, expected in (("disposition", {f"missing-{i}" for i in range(338)}),
                           ("inventory", {obj['object_id'] for obj in objects})):
        seen = set()
        for page in range(1, (len(expected) + 24) // 25 + 1):
            body = _render_review_index("snap-test", objects, "tekst", task=task,
                                       page=page, bindings=[], fragments=fragments)
            ids = _inventory_ids(body)
            assert 0 < len(ids) <= 25 and len(ids) == len(set(ids))
            assert not seen & set(ids)
            seen.update(ids)
            if task == 'disposition':
                assert "Gebruik van bronpassage bepalen" in body
        assert seen == expected
    assert objects == before  # All projections are read-only.


def test_followup_counts_lists_and_final_blocked_history_are_disjoint():
    blocked = _obj("blocked", "recommendation", gate_result="blocked")
    final = _obj("excluded", "recommendation", gate_result="blocked", validation_status="rejected")
    final["metadata"]["passage_register"].update(status="excluded_with_reason", source="review")
    unknown = _obj("unknown", "recommendation", gate_result=None)
    unknown["metadata"]["passage_register"] = {}
    objects = [blocked, final, unknown]
    queues = review_followup_queues(objects, review_path="tekst", bindings=[], fragments=_allowed_source())
    assert [r["object_id"] for r in queues["repair"]] == ["blocked"]
    assert [r["object_id"] for r in queues["disposition"]] == ["unknown"]
    for task in ("repair", "disposition"):
        html = _render_review_index("snap", objects, "tekst", task=task, bindings=[], fragments=_allowed_source())
        assert set(_inventory_ids(html)) == {r["object_id"] for r in queues[task]}
    dashboard = _render_review_index("snap", objects, "tekst", bindings=[], fragments=_allowed_source())
    assert "Alle reviewtaken zijn afgerond" not in dashboard
    assert 'data-content-review-workplace' in dashboard
    assert 'task=inventory' in dashboard
    assert 'task=disposition' not in dashboard and 'task=repair' not in dashboard
    inventory = _render_review_index("snap", objects, "tekst", task="inventory", bindings=[], fragments=_allowed_source())
    assert set(_inventory_ids(inventory)) == {"blocked", "excluded", "unknown"}
    assert 'object=excluded&amp;task=history' in inventory


def test_open_second_review_is_not_reclassified_as_missing_disposition():
    obj = _obj("second", "exception")
    obj.update(object_version="1.0", confirmed_object_type="exception")
    from src.integrity_kernel import stamp_canonical_hashes
    stamp_canonical_hashes(obj)
    binding = dict(valid=True, decision="approve", object_id="second", object_version="1.0",
                   canonical_object_hash=obj["provenance"]["canonical_object_hash"], confirmed_object_type="exception", reviewer_id="reviewer-a")
    queues = review_followup_queues([obj], review_path="tekst", bindings=[binding], fragments=_allowed_source())
    assert queues == {"repair": [], "disposition": []}
    waiting = _render_review_index("snap", [obj], "tekst", task="waiting", bindings=[binding], reviewer_id="reviewer-a", fragments=_allowed_source())
    assert _inventory_ids(waiting) == ["second"]
    assert 'data-passage-category="waiting"' in waiting
    assert reviewer_route_counts([obj], review_path="tekst", bindings=[binding], reviewer_id="reviewer-b", fragments=_allowed_source())["actionable_second_review_duties"] == 1


@pytest.mark.parametrize("gate,task", [(None, "disposition"), ("blocked", "repair")])
def test_http_followup_is_reachable_and_can_be_resolved_without_losing_history(tmp_path, gate, task, *, production_app, production_console):
    console, accounts, receipt, _ = _system(tmp_path, production_console=production_console)
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
    install_fixture_history(console, sid, objects)  # seeded persisted state, not a T11 command
    before = console.objects_revision(sid)
    client = _client(console, production_app=production_app)
    _login(client, accounts["reviewer_a"]["username"])
    response = client.get(f"/review?document={sid}&task={task}")
    assert response.status_code == 200
    assert target["object_id"] in _inventory_ids(response.text)
    detail = client.get(f"/review?document={sid}&task={task}&object={target['object_id']}")
    assert detail.status_code == 200
    if task == 'repair':
        assert 'data-formation-repair' in detail.text and 'action="/review/resolve"' in detail.text
        assert 'action="/review"' not in detail.text
    else:
        assert ("kan nog niet worden goedgekeurd" if gate else "nog niet beschikbaar voor goedkeuring") in detail.text
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
