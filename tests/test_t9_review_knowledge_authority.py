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
        data=b"<html><body><h1>Begrippen</h1><p>Oedeem is een ophoping van vocht.</p><p>Een aanvullende bronpassage.</p></body></html>",
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


def test_explicit_reapproval_reuses_exact_authorization_without_erasing_events(tmp_path):
    """A withdrawn authority needs a fresh command, not a new tuple row."""
    from src.review_ledger import read_events
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj, expected_revision=console.objects_revision(sid))
    old = deepcopy(console.object_review_bindings(sid)[0])
    first_events = deepcopy(read_events(console._ledger_path))
    console._bindings[sid][0]["valid"] = False
    console._save_bindings()
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
    assert exact_current_approver_ids(current, console.object_review_bindings(sid)) == ()
    _approve(console, reviewer, sid, current, expected_revision=console.objects_revision(sid))
    rows = console.object_review_bindings(sid)
    assert len(rows) == 1, "One semantic approval tuple must not create duplicate authority rows"
    assert rows[0] == old, "Exact reviewed evidence stays unchanged; only withdrawn validity can be renewed"
    events = read_events(console._ledger_path)
    assert events[:len(first_events)] == first_events
    assert len(events) == len(first_events) + 1
    assert exact_current_approver_ids(current, rows) == (reviewer["account_id"],)


def _state(console, sid):
    from src.review_ledger import read_events
    return deepcopy(console.snapshot_objects(sid)), deepcopy(console.object_review_bindings(sid)), deepcopy(read_events(console._ledger_path)) if console._ledger_path.exists() else []


def _http(console):
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app
    client = TestClient(create_console_app(console))
    response = client.post("/login", data={"username": "bert", "password": "bert-secret"})
    assert response.status_code in {200, 303}
    return client


def _post_review(client, sid, obj, revision):
    return client.post("/review", data={"snapshot_id": sid, "object_id": obj["object_id"],
        "decision": "approve", "confirmed_object_type": "definition", "suitability": "ja",
        "snapshot_revision": revision}, follow_redirects=False)


def test_direct_post_cannot_force_blocked_content_review(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    rows = console._load_objects(sid)
    for row in rows:
        if row["object_id"] == obj["object_id"]:
            row["metadata"]["admission"]["gate_result"] = "blocked"
            stamp_canonical_hashes(row)
    console._save_objects(sid, rows)
    before = _state(console, sid)
    response = _post_review(_http(console), sid, obj, console.objects_revision(sid))
    assert response.status_code == 400
    assert _state(console, sid) == before


def test_stale_browser_post_commits_no_object_binding_or_event(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    client = _http(console)
    revision = console.objects_revision(sid)
    rows = console._load_objects(sid)
    document = next(o for o in rows if o["object_type"] == "document")
    document.setdefault("metadata", {})["t9_competing_writer"] = True
    stamp_canonical_hashes(document)
    console._save_objects(sid, rows)
    before = _state(console, sid)
    response = _post_review(client, sid, obj, revision)
    assert response.status_code == 409
    assert _state(console, sid) == before


@pytest.mark.parametrize("decision", ["later", "revise", "reject"])
def test_nonapproval_decisions_never_grant_approval(tmp_path, decision):
    console, reviewer, sid, obj = _console(tmp_path)
    console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid, object_id=obj["object_id"],
        decision=decision, comment="Beoordeling blijft zonder approval.",
        expected_revision=console.objects_revision(sid))
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
    assert current["metadata"]["admission"]["gate_result"] == "allowed"
    assert exact_current_approver_ids(current, console.object_review_bindings(sid)) == ()
    assert not any(b.get("valid") and b.get("decision") == "approve" for b in console.object_review_bindings(sid))


def test_duplicate_submit_is_no_transition_and_not_a_second_reviewer(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj, expected_revision=console.objects_revision(sid))
    before = _state(console, sid)
    _approve(console, reviewer, sid, obj, expected_revision=console.objects_revision(sid))
    assert _state(console, sid) == before
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
    assert exact_current_approver_ids(current, console.object_review_bindings(sid)) == (reviewer["account_id"],)


def test_four_eyes_uses_unique_exact_human_bindings():
    from src.review_duty_v1 import review_stage, FIRST_REVIEW, SECOND_REVIEW
    obj = _allowed_candidate()
    obj["risk"] = {"risk_level": "high", "requires_second_review": True}
    stamp_canonical_hashes(obj)
    a, b, agent = _binding(obj, "bert"), _binding(obj, "carla"), _binding(obj, "ai")
    args = {"review_path": "richtlijn", "fragments": _allowed_source()}
    assert review_stage(obj, bindings=[], **args) == FIRST_REVIEW
    assert review_stage(obj, bindings=[a, a, agent], **args) == SECOND_REVIEW
    assert review_stage(obj, bindings=[a, b], **args) is None


def test_historical_binding_survives_changed_context_without_approval_carry(tmp_path):
    from src.review_duty_v1 import review_stage, FIRST_REVIEW
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj, expected_revision=console.objects_revision(sid))
    old = deepcopy(console.object_review_bindings(sid))
    rows = console._load_objects(sid)
    for row in rows:
        if row["object_id"] == obj["object_id"] and row["object_version"] == old[0]["object_version"]:
            row.setdefault("metadata", {})["review_context"] = {"t9_changed": True}
            stamp_canonical_hashes(row)
    console._save_objects(sid, rows)
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
    assert console._bindings[sid] == old
    assert exact_current_approver_ids(current, console.object_review_bindings(sid)) == ()
    assert review_stage(current, review_path="richtlijn", bindings=console.object_review_bindings(sid),
                        fragments=console.review_source_fragments(sid)) == FIRST_REVIEW

from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


def test_native_stale_review_does_not_attempt_a_restorative_write(workflow_postgres, tmp_path, monkeypatch):
    from tests.test_review_batch_atomic_postgres import _console as native_console
    console = native_console(tmp_path, workflow_postgres)
    author = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    text = "Oedeem is een ophoping van vocht."
    bind_fixture_selections(console, [(text, "definition")])
    receipt = console.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body><h1>Bron</h1><p>" + text + "</p></body></html>").encode(),
        ingest_kind="new", title="T9 stale", version="1.0", date="2026-10-07", live_url="",
        class_="richtlijn", family="test", named_reviewers=[reviewer["account_id"]])
    sid = receipt["snapshot_id"]
    obj = next(o for o in console.snapshot_objects(sid) if o.get("proposed_object_type") == "definition")
    stale = console.objects_revision(sid)
    rows = console._load_objects(sid)
    document = next(o for o in rows if o["object_type"] == "document")
    document.setdefault("metadata", {})["t9_winner"] = True
    stamp_canonical_hashes(document)
    console._save_objects(sid, rows)
    store = console.workflow_document_store
    before = deepcopy(store.list_document_objects(sid))
    bindings = deepcopy(console.workflow_review_store.read_bindings())
    events = deepcopy(console.workflow_review_store.read_events())
    writes = []
    original = store.write_bundle
    def counted_write(**kwargs):
        writes.append(deepcopy(kwargs))
        return original(**kwargs)
    monkeypatch.setattr(store, "write_bundle", counted_write)
    with pytest.raises(ConsoleError, match=SNAPSHOT_OBJECT_WRITE_CONFLICT):
        _approve(console, reviewer, sid, obj, expected_revision=stale)
    assert writes == [], "A stale review must not commit even an unchanged restoration bundle"
    assert store.list_document_objects(sid) == before
    assert console.workflow_review_store.read_bindings() == bindings
    assert console.workflow_review_store.read_events() == events


def test_second_worker_rechecks_durable_bindings_before_duplicate_submit(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    second = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    _approve(console, reviewer, sid, obj, expected_revision=console.objects_revision(sid))
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
    before = _state(console, sid)
    _approve(second, reviewer, sid, current, expected_revision=second.objects_revision(sid))
    assert _state(console, sid) == before
    assert len(second.object_review_bindings(sid)) == 1


@pytest.mark.parametrize("kind", ["blocked", "deterministic", "coverage", "heading", "malformed"])
def test_direct_console_approve_cannot_create_authority_for_nonreview_work(tmp_path, kind):
    console, reviewer, sid, obj = _console(tmp_path)
    rows = console._load_objects(sid)
    if kind in {"heading", "coverage"}:
        from src.knowledge_path_v1 import is_structural_projection
        from src.source_accountability_v1 import is_source_record
        target = next(o for o in rows if (is_structural_projection(o) if kind == "heading" else is_source_record(o)))
    else:
        target = next(o for o in rows if o["object_id"] == obj["object_id"])
        if kind == "blocked":
            target["metadata"]["admission"]["gate_result"] = "blocked"
        elif kind == "deterministic":
            target["metadata"].pop("semantic_passage", None)
        else:
            target["content"]["clean_text"] += " Onjuiste nieuwe tekst."
        stamp_canonical_hashes(target)
        console._save_objects(sid, rows)
    before = _state(console, sid)
    with pytest.raises(ConsoleError):
        console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
            object_id=target["object_id"], decision="approve",
            confirmed_object_type="heading" if kind == "heading" else "definition",
            expected_revision=console.objects_revision(sid))
    assert _state(console, sid) == before


def test_actual_four_eyes_commands_require_an_independent_second_human(tmp_path):
    from src.review_duty_v1 import review_stage, SECOND_REVIEW
    console, reviewer, sid, obj = _console(tmp_path)
    second = console.create_account(username="carla", password="carla-secret", roles=("reviewer",))
    console._envelopes[sid]["named_reviewers"].append(second["account_id"])
    console._save_envelopes()
    rows = console._load_objects(sid)
    target = next(o for o in rows if o["object_id"] == obj["object_id"])
    target["risk"]["risk_level"] = "high"
    stamp_canonical_hashes(target)
    console._save_objects(sid, rows)
    _approve(console, reviewer, sid, target, expected_revision=console.objects_revision(sid))
    current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
    args = {"review_path": "richtlijn", "bindings": console.object_review_bindings(sid),
            "fragments": console.review_source_fragments(sid)}
    assert review_stage(current, **args) == SECOND_REVIEW
    before = _state(console, sid)
    with pytest.raises(ConsoleError, match="independent_second_reviewer_required"):
        console.approve_second_review(actor_id=reviewer["account_id"], snapshot_id=sid,
            object_id=obj["object_id"], expected_revision=console.objects_revision(sid))
    assert _state(console, sid) == before
    approved = console.approve_second_review(actor_id=second["account_id"], snapshot_id=sid,
        object_id=obj["object_id"], expected_revision=console.objects_revision(sid))
    assert approved["object_version"] == current["object_version"]
    assert exact_review_snapshot_hash(approved) == exact_review_snapshot_hash(current)
    args["bindings"] = console.object_review_bindings(sid)
    assert review_stage(approved, **args) is None
    assert set(exact_current_approver_ids(approved, args["bindings"])) == {reviewer["account_id"], second["account_id"]}


def test_forbidden_reviewer_account_alias_does_not_close_four_eyes():
    from src.review_duty_v1 import review_stage, SECOND_REVIEW
    obj = _allowed_candidate()
    obj["risk"] = {"risk_level": "high"}
    stamp_canonical_hashes(obj)
    human = _binding(obj, "bert")
    agent = _binding(obj, "ai")
    agent["reviewer_account_id"] = agent.pop("reviewer_id")
    assert exact_current_approver_ids(obj, [human, agent]) == ("bert",)
    assert review_stage(obj, review_path="richtlijn", bindings=[human, agent],
                        fragments=_allowed_source()) == SECOND_REVIEW


@pytest.mark.parametrize("domain", ["structure", "source_disposition", "decision_tree"])
def test_other_domain_binding_cannot_grant_knowledge_approval(domain):
    obj = _allowed_candidate()
    binding = _binding(obj, "bert")
    binding["review_domain"] = domain
    assert exact_current_approver_ids(obj, [binding]) == ()

@pytest.mark.parametrize("pin", [None, "", "   "])
def test_direct_review_post_requires_the_reviewed_revision(tmp_path, pin):
    """A client cannot discard its reviewed revision and approve current state."""
    console, reviewer, sid, obj = _console(tmp_path)
    client = _http(console)
    before = _state(console, sid)
    payload = {"snapshot_id": sid, "object_id": obj["object_id"], "decision": "approve",
               "confirmed_object_type": "definition", "suitability": "ja"}
    if pin is not None:
        payload["snapshot_revision"] = pin
    response = client.post("/review", data=payload, follow_redirects=False)
    assert response.status_code == 400
    assert _state(console, sid) == before


@pytest.mark.parametrize("pin", [None, "", "   ", "current"])
def test_second_review_post_requires_the_reviewed_revision(tmp_path, pin):
    console, reviewer, sid, obj = _console(tmp_path)
    second = console.create_account(username="carla", password="carla-secret", roles=("reviewer",))
    console._envelopes[sid]["named_reviewers"].append(second["account_id"])
    console._save_envelopes()
    rows = console._load_objects(sid)
    target = next(o for o in rows if o["object_id"] == obj["object_id"])
    target["risk"]["risk_level"] = "high"
    stamp_canonical_hashes(target)
    console._save_objects(sid, rows)
    _approve(console, reviewer, sid, target, expected_revision=console.objects_revision(sid))
    client = _http(console)
    client.post("/login", data={"username": "carla", "password": "carla-secret"})
    before = _state(console, sid)
    payload = {"snapshot_id": sid, "object_id": obj["object_id"], "action": "approve"}
    if pin is not None:
        payload["snapshot_revision"] = console.objects_revision(sid) if pin == "current" else pin
    response = client.post("/review/second-review", data=payload, follow_redirects=False)
    if pin == "current":
        assert response.status_code == 303
        current = next(o for o in console.snapshot_objects(sid) if o["object_id"] == obj["object_id"])
        assert set(exact_current_approver_ids(current, console.object_review_bindings(sid))) == {
            reviewer["account_id"], second["account_id"]}
    else:
        assert response.status_code == 400
        assert _state(console, sid) == before
