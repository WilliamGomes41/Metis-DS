"""T9 review authority regressions against production entrypoints.

RED/GREEN classification is recorded in the change contract after baseline CI.
# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json

import pytest

from src.integrity_kernel import exact_review_snapshot_hash, stamp_canonical_hashes
from src.knowledge_path_v1 import content_reviewable
from src.operations_console_v1 import ConsoleError, OperationsConsole, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.proportionate_review_v1 import regular_review_queue
from src.review_duty_v1 import exact_current_approver_ids, reviewer_route_for
from src.review_workflow_v3 import apply_reviews
from tests.semantic_fixture_support import bind_fixture_selections
from test_t4_single_knowledge_path_invariants import _allowed_candidate, _allowed_source, _binding


def _console(tmp_path):
    console = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    author = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    bind_fixture_selections(console, [("Oedeem is een ophoping van vocht.", "definition")])
    receipt = console.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=b"<html><body><h1>Begrippen</h1><p>Oedeem is een ophoping van vocht.</p></body></html>",
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-10-07", live_url="",
        class_="richtlijn", family="test", named_reviewers=[reviewer["account_id"]])
    sid = receipt["snapshot_id"]
    candidate = next(o for o in console.snapshot_objects(sid) if content_reviewable(o))
    return console, reviewer, sid, candidate


def _approve(console, reviewer, sid, obj, **kwargs):
    return console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
        object_id=obj["object_id"], decision="approve", confirmed_object_type="definition", **kwargs)


@pytest.mark.parametrize("kind", ["blocked", "deterministic", "coverage", "heading", "malformed"])
def test_direct_workflow_cannot_create_content_authority_without_candidate(tmp_path, kind):
    console, reviewer, sid, candidate = _console(tmp_path)
    obj = deepcopy(candidate)
    semantic = obj["metadata"]["semantic_passage"]
    if kind == "blocked":
        obj["metadata"]["admission"]["gate_result"] = "blocked"
    elif kind == "deterministic":
        obj["metadata"].pop("semantic_passage")
    elif kind == "coverage":
        semantic["selection_origin"] = "coverage_remainder"
    elif kind == "heading":
        obj["object_type"] = "heading"
        obj["proposed_object_type"] = "heading"
    else:
        semantic["spans"][0]["end"] = -1
    stamp_canonical_hashes(obj)
    ledger = tmp_path / "isolated-review.jsonl"
    before = deepcopy(obj)
    updated, report = apply_reviews([obj], [{"object_id": obj["object_id"], "decision": "approve",
        "reviewer": reviewer["username"], "reviewed_canonical_object_hash": exact_review_snapshot_hash(obj)}],
        track=obj["governance"]["review_track"], schema_path=console.schema_path, ledger_path=ledger)
    assert report["errors"], "Direct workflow must refuse content review"
    assert updated == [before]
    assert not ledger.exists() or not ledger.read_text().strip()


@pytest.mark.parametrize("field", ["text", "spans", "context", "type", "relations"])
def test_unstamped_content_mutation_cannot_reuse_stored_hash(field):
    obj = _allowed_candidate()
    obj["confirmed_object_type"] = "definition"
    stamp_canonical_hashes(obj)
    binding = _binding(obj)
    if field == "text":
        obj["content"]["clean_text"] += " Veranderd."
    elif field == "spans":
        obj["metadata"]["semantic_passage"]["spans"][0]["end"] -= 1
    elif field == "context":
        obj["metadata"]["review_context"] = {"changed": True}
    elif field == "type":
        obj["object_type"] = "explanation"
    else:
        obj["relations"] = [{"relation_type": "applies_if", "target_object_id": "changed"}]
    assert exact_review_snapshot_hash(obj) != binding["canonical_object_hash"]
    assert exact_current_approver_ids(obj, [binding]) == ()


def test_binding_iterator_cannot_make_existing_approver_actionable():
    obj = _allowed_candidate()
    obj["confirmed_object_type"] = "definition"
    obj["risk"] = {"risk_level": "high", "requires_second_review": True}
    stamp_canonical_hashes(obj)
    binding = _binding(obj, "bert")
    route = reviewer_route_for(obj, review_path="richtlijn", reviewer_id="bert", bindings=iter([binding]), fragments=_allowed_source())
    assert route and not route["actionable"]
    assert route["current_approver_ids"] == ["bert"]


def test_completed_candidate_cannot_be_reclassified_by_fresh_approve(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj, expected_revision=console.objects_revision(sid))
    before = console.snapshot_objects(sid)
    bindings = console.object_review_bindings(sid)
    ledger = console._ledger_path.read_bytes() if console._ledger_path.exists() else b""
    with pytest.raises(ConsoleError, match="content_duty_required|review_complete"):
        console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
            object_id=obj["object_id"], decision="approve", confirmed_object_type="explanation",
            expected_revision=console.objects_revision(sid))
    assert console.snapshot_objects(sid) == before
    assert console.object_review_bindings(sid) == bindings
    assert (console._ledger_path.read_bytes() if console._ledger_path.exists() else b"") == ledger


def test_general_queue_does_not_reopen_completed_candidate(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj)
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
    assert regular_review_queue([current], review_path="richtlijn",
        bindings=console.object_review_bindings(sid), fragments=console.review_source_fragments(sid)) == []


def test_failed_review_store_commit_leaves_no_approval_ledger(tmp_path, monkeypatch):
    console, reviewer, sid, obj = _console(tmp_path)
    before = console.snapshot_objects(sid)
    bindings = console.object_review_bindings(sid)
    ledger = console._ledger_path.read_bytes() if console._ledger_path.exists() else b""
    def fail(**_kwargs):
        raise ConsoleError("injected_store_failure")
    monkeypatch.setattr(console, "_commit_prepared_store", fail)
    with pytest.raises(ConsoleError, match="injected_store_failure"):
        _approve(console, reviewer, sid, obj)
    assert console.snapshot_objects(sid) == before
    assert console.object_review_bindings(sid) == bindings
    assert (console._ledger_path.read_bytes() if console._ledger_path.exists() else b"") == ledger


def test_stale_revision_does_not_commit_any_review_evidence(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    stale = console.objects_revision(sid)
    heading = next(o for o in console.snapshot_objects(sid) if o["object_type"] == "heading")
    console.batch_confirm_headings(actor_id=reviewer["account_id"], snapshot_id=sid,
        object_ids=[heading["object_id"]], expected_revision=stale)
    before = console.snapshot_objects(sid)
    bindings = console.object_review_bindings(sid)
    ledger = console._ledger_path.read_bytes() if console._ledger_path.exists() else b""
    with pytest.raises(ConsoleError, match=SNAPSHOT_OBJECT_WRITE_CONFLICT):
        _approve(console, reviewer, sid, obj, expected_revision=stale)
    assert console.snapshot_objects(sid) == before
    assert console.object_review_bindings(sid) == bindings
    assert (console._ledger_path.read_bytes() if console._ledger_path.exists() else b"") == ledger


def test_valid_candidate_approval_is_exact_and_reject_never_changes_admission(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj)
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
    assert exact_current_approver_ids(current, console.object_review_bindings(sid)) == (reviewer["account_id"],)
    other, reviewer2, sid2, obj2 = _console(tmp_path / "reject")
    gate = deepcopy(obj2["metadata"]["admission"])
    other.review_object(actor_id=reviewer2["account_id"], snapshot_id=sid2, object_id=obj2["object_id"],
        decision="reject", comment="Inhoudelijk afgewezen")
    rejected = next(o for o in other.snapshot_objects(sid2) if o["object_id"] == obj2["object_id"])
    assert rejected["metadata"]["admission"] == gate
    assert exact_current_approver_ids(rejected, other.object_review_bindings(sid2)) == ()

@pytest.mark.parametrize("mutation", ["text", "bounds", "mapping", "provenance"])
def test_corrupt_persisted_candidate_has_no_duty_even_with_allowed_gate(tmp_path, mutation):
    from src.review_duty_v1 import review_duty_for
    console, reviewer, sid, obj = _console(tmp_path)
    bad = deepcopy(obj)
    if mutation == "text":
        bad["content"]["clean_text"] += " Veranderd."
    elif mutation == "bounds":
        bad["metadata"]["semantic_passage"]["spans"][0]["end"] = 999999
    elif mutation == "mapping":
        bad["metadata"]["semantic_passage"]["source_mapping"] = []
    else:
        bad["provenance"]["source_fragments"][0]["raw_content_hash"] = "forged"
    stamp_canonical_hashes(bad)
    assert review_duty_for(bad, review_path="richtlijn", bindings=[],
                           fragments=console.review_source_fragments(sid)) is None


def test_content_queue_parity_uses_real_source_and_exact_bindings(tmp_path):
    from src.review_duty_v1 import review_duty_for
    from src.proportionate_review_v1 import normal_risk_batch_queue, regular_individual_review_queue
    from src.build_review_queue_v3 import build
    console, reviewer, sid, obj = _console(tmp_path)
    objects = console.snapshot_objects(sid)
    fragments = console.review_source_fragments(sid)
    bindings = console.object_review_bindings(sid)
    args = {"review_path": "richtlijn", "bindings": bindings, "fragments": fragments}
    expected = {o["object_id"] for o in objects if review_duty_for(o, **args)}
    assert expected == {obj["object_id"]}
    assert {o["object_id"] for o in regular_review_queue(objects, **args)} == expected
    assert {o["object_id"] for o in normal_risk_batch_queue(objects, **args)} == expected
    assert regular_individual_review_queue(objects, **args) == []
    assert {o["object_id"] for o in build(objects, obj["governance"]["review_track"], **args)} == expected
    _approve(console, reviewer, sid, obj)
    current = console.snapshot_objects(sid)
    args["bindings"] = console.object_review_bindings(sid)
    assert regular_review_queue(current, **args) == []
    assert normal_risk_batch_queue(current, **args) == []
    assert build(current, obj["governance"]["review_track"], **args) == []


def test_structure_confirmation_is_qa_and_general_content_approve_is_denied(tmp_path):
    from src.knowledge_path_v1 import is_structural_projection
    from src.review_duty_v1 import review_duty_for
    console, reviewer, sid, obj = _console(tmp_path)
    heading = next(o for o in console.snapshot_objects(sid) if is_structural_projection(o))
    with pytest.raises(ConsoleError, match="structure_confirmation_command_required"):
        console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
            object_id=heading["object_id"], decision="approve", confirmed_object_type="heading")
    rows = console.batch_confirm_headings(actor_id=reviewer["account_id"], snapshot_id=sid,
        object_ids=[heading["object_id"]], expected_revision=console.objects_revision(sid))
    confirmed = rows[0]
    assert not content_reviewable(confirmed)
    assert review_duty_for(confirmed, review_path="richtlijn",
        bindings=console.object_review_bindings(sid), fragments=console.review_source_fragments(sid)) is None
    assert any(event["event_type"] == "structure_approve" for event in
        map(json.loads, console._ledger_path.read_text().splitlines()))

def test_standalone_second_review_cannot_bypass_current_working_revision(tmp_path):
    from src.second_review_workflow_v3 import apply_second
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj)
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
    before = deepcopy(current)
    ledger = tmp_path / "standalone-second.jsonl"
    updated, report = apply_second([current], [{"object_id": current["object_id"], "decision": "approve",
        "reviewer": "ai", "review_date": "2026-10-07",
        "reviewed_canonical_object_hash": exact_review_snapshot_hash(current)}], ledger)
    assert report["errors"]
    assert updated == [before]
    assert not ledger.exists()
