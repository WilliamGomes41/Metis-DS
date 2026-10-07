"""Behavioral T10 regressions using pre-existing public entrypoints.
# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
"""
from copy import deepcopy
import pytest

from src.source_containers_v1 import partition, source_usage
from src.publication_readiness_v1 import source_passage_closure, review_followup_queues
from src.source_accountability_v1 import KEY, record
from src.review_duty_v1 import review_duty_for
from tests.test_source_containers_v1 import context_story


def _linked(rows):
    return next(item["record"] for item in partition(rows)["source"]
                if item["record"]["content"]["clean_text"] == "Bij volwassenen.")


@pytest.mark.parametrize("damage", ["binding", "spans", "text"])
def test_corrupt_source_is_repair_not_disposition(damage):
    rows = context_story()
    source = _linked(rows)
    if damage == "binding":
        source["metadata"][KEY]["binding_hash"] = "corrupt"
    elif damage == "spans":
        source["metadata"][KEY]["spans"][0]["end"] += 1
    else:
        source["content"]["clean_text"] += " corrupt"
    queues = review_followup_queues(rows, review_path="richtlijn")
    assert source["object_id"] in {o["object_id"] for o in queues["repair"]}
    assert source["object_id"] not in {o["object_id"] for o in queues["disposition"]}


def test_governance_approved_alone_cannot_close_target_context():
    rows = context_story()
    source = _linked(rows)
    target = partition(rows)["knowledge"][0]
    target["governance"]["validation_status"] = "approved"
    assert not source_usage(rows)[source["object_id"]]["accounted"]
    assert source["object_id"] in source_passage_closure(rows)["unresolved_source_passage_ids"]


def test_invalid_human_role_cannot_hide_behind_context_waiting():
    rows = context_story()
    source = _linked(rows)
    source["metadata"]["source_role_review"] = {"role": "context", "literal_hash": "bad"}
    queues = review_followup_queues(rows, review_path="richtlijn")
    assert source["object_id"] in {o["object_id"] for o in queues["repair"]}


def test_valid_pending_context_has_no_duplicate_source_task():
    rows = context_story()
    source = _linked(rows)
    before = deepcopy(rows)
    queues = review_followup_queues(rows, review_path="richtlijn")
    assert source["object_id"] not in {o["object_id"] for q in queues.values() for o in q}
    assert source["object_id"] in source_passage_closure(rows)["unresolved_source_passage_ids"]
    assert rows == before


def test_source_records_never_open_content_review():
    rows = context_story()
    for item in partition(rows)["source"]:
        assert review_duty_for(item["record"], review_path="richtlijn", bindings=[]) is None


def _context_inputs():
    from tests.test_recommendation_context_v3 import source
    fragments = source("Gebruik geen zalf")
    fragments.append({**source("Bij volwassenen. Bij kinderen geldt ander beleid.")[0],
                      "fragment_id": "context", "fragment_hash": "context-hash"})
    rows = context_story()
    return rows, fragments


def _approve_bindings(target):
    from src.integrity_kernel import stamp_canonical_hashes
    from tests.test_t4_single_knowledge_path_invariants import _binding
    target["confirmed_object_type"] = "recommendation"
    target["governance"]["validation_status"] = "approved"
    stamp_canonical_hashes(target)
    return [_binding(target, "human-one"), _binding(target, "human-two")]


def test_exact_target_approvals_close_context_and_stale_bindings_reopen():
    from src.source_containers_v1 import source_accountability, source_closure
    rows, fragments = _context_inputs()
    source = _linked(rows)
    target = partition(rows)["knowledge"][0]
    bindings = _approve_bindings(target)
    args = dict(bindings=bindings, fragments=fragments)
    closed = source_accountability(rows, **args)
    assert closed[source["object_id"]]["closure"] == "accounted"
    for binding in bindings:
        binding["valid"] = False
    waiting = source_accountability(rows, **args)
    assert waiting[source["object_id"]]["closure"] == "waiting_on_target"
    assert waiting[source["object_id"]]["human_action"] == "none"
    assert source_passage_closure(rows, projection=waiting) == source_closure(waiting)


@pytest.mark.parametrize("status", ["rejected", "superseded", "revise"])
def test_terminal_target_removes_automatic_context_closure(status):
    from src.source_containers_v1 import source_accountability
    rows, fragments = _context_inputs()
    source = _linked(rows)
    target = partition(rows)["knowledge"][0]
    bindings = _approve_bindings(target)
    target["governance"]["validation_status"] = status
    state = source_accountability(rows, bindings=bindings, fragments=fragments)[source["object_id"]]
    assert state["closure"] == "open"
    assert state["human_action"] == "source_disposition"


def test_stale_context_binding_is_repair_even_with_old_approval():
    from src.source_containers_v1 import source_accountability
    rows, fragments = _context_inputs()
    source = _linked(rows)
    target = partition(rows)["knowledge"][0]
    bindings = _approve_bindings(target)
    target["content"]["clean_text"] += " gewijzigd"
    state = source_accountability(rows, bindings=bindings, fragments=fragments)[source["object_id"]]
    assert state["closure"] == "repair_required"
    assert state["human_action"] == "technical_repair"


def test_projection_wrappers_ui_and_t9_duties_share_one_snapshot():
    from src.source_containers_v1 import source_accountability, source_closure
    from src.operations_console_app import _render_review_index
    from src.review_duty_v1 import review_duties
    rows, fragments = _context_inputs()
    source = _linked(rows)
    source["metadata"][KEY]["binding_hash"] = "bad"
    before = deepcopy(rows)
    duties = review_duties(rows, review_path="richtlijn", bindings=[], fragments=fragments)
    projection = source_accountability(rows, bindings=[], fragments=fragments)
    queues = review_followup_queues(rows, review_path="richtlijn", projection=projection)
    for name, action in (("repair", "technical_repair"), ("disposition", "source_disposition")):
        assert {o["object_id"] for o in queues[name]} == {oid for oid, r in projection.items() if r["human_action"] == action}
    assert source_passage_closure(rows, projection=projection) == source_closure(projection)
    page = _render_review_index("snapshot", rows, "richtlijn", bindings=[], fragments=fragments, task="repair")
    assert f'data-source-record="{source["object_id"]}"' in page
    assert "Technisch herstel nodig" in page
    assert rows == before
    assert review_duties(rows, review_path="richtlijn", bindings=[], fragments=fragments) == duties


@pytest.mark.parametrize("text,role", [("Versie: 1.2", "document_information"),
    ("Datum: oktober 2026", "document_information"), ("Inhoud................3", "navigation"),
    ("Versie: 1.2; gebruik geen zalf", "unresolved")])
def test_closed_metadata_rules_and_legacy_policy(text, role):
    from src.source_containers_v1 import source_accountability
    rows = context_story()
    source = deepcopy(_linked(rows))
    spans = [{"block_id": "metadata", "start": 0, "end": len(text)}]
    source["content"]["clean_text"] = text
    source["metadata"]["semantic_passage"]["spans"] = spans
    source["metadata"][KEY] = record(text=text, spans=spans, version="source-accountability-v2")
    state = source_accountability([source])[source["object_id"]]
    assert state["role"] == role
    source["metadata"][KEY] = record(text=text, spans=spans)
    legacy = source_accountability([source])[source["object_id"]]
    assert legacy["human_action"] == "source_disposition"
    assert legacy["reason"] == "legacy_source_policy"


@pytest.mark.parametrize("status", ["used_as_context", "linked_as_support", "excluded_with_reason"])
def test_explicit_dispositions_remain_evidence_without_knowledge_authority(status):
    from src.source_containers_v1 import source_accountability
    from src.passage_register_v1 import passage_register_record
    source = deepcopy(_linked(context_story()))
    source["metadata"]["passage_register"] = passage_register_record(status=status, source="review",
                                                                    reason_codes=["human_reason"])
    source["governance"]["validation_status"] = "rejected"
    before = deepcopy(source)
    assert source_accountability([source])[source["object_id"]]["closure"] == "accounted"
    assert source == before
    assert review_duty_for(source, review_path="richtlijn", bindings=[]) is None


def test_confirm_reset_duplicate_conflict_restart_and_projection(tmp_path):
    from tests.test_source_context_review_v1 import _system
    from src.review_closure_v1 import ReviewClosureConsole
    from src.source_containers_v1 import source_accountability
    from src.operations_console_v1 import ConsoleError
    from src.review_ledger import read_events
    state, _, reviewer, source, target, command = _system(tmp_path)
    sid = command["snapshot_id"]
    state.confirm_source_context(**command)
    def project(console):
        return source_accountability(console.snapshot_objects(sid),
            bindings=console.object_review_bindings(sid), fragments=console.review_source_fragments(sid))
    initial = project(state)
    assert state.confirm_source_context(**command)["idempotent"]
    with pytest.raises(ConsoleError, match="source_context_command_conflict"):
        state.confirm_source_context(**{**command, "reason": "different"})
    before = deepcopy(state.snapshot_objects(sid))
    events = read_events(state._ledger_path)
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        state.confirm_source_context(**{**command, "command_id": "stale"})
    assert state.snapshot_objects(sid) == before
    assert read_events(state._ledger_path) == events
    state.review_object(actor_id=reviewer["account_id"], snapshot_id=sid, object_id=target["object_id"],
                        decision="approve", confirmed_object_type="definition", relation_review_ack=True)
    assert project(state)[source["object_id"]]["closure"] == "accounted"
    restarted = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert project(restarted) == project(state)
    restarted.confirm_source_context(**{**command, "role": "reset", "target_object_ids": [],
        "command_id": "reset", "expected_revision": restarted.objects_revision(sid)})
    assert project(restarted)[source["object_id"]]["closure"] == "open"
    assert all(event in read_events(restarted._ledger_path) for event in events)


def test_corrupt_source_detail_requests_repair_not_a_human_disposition():
    from src.operations_console_app import _source_context_panel
    rows = context_story()
    source = _linked(rows)
    source["metadata"][KEY]["binding_hash"] = "bad"
    page = _source_context_panel(source, rows, "snapshot", "revision")
    assert "data-source-repair" in page
    assert 'action="/review/source-context"' not in page


def test_export_uses_same_current_target_authority_as_containers():
    from src.processing_evidence_export_v1 import processing_evidence_tables
    rows, fragments = _context_inputs()
    source = _linked(rows)
    target = partition(rows)["knowledge"][0]
    bindings = _approve_bindings(target)
    tables, _ = processing_evidence_tables(snapshot_id="snapshot", revision="revision",
        envelope={"class": "richtlijn"}, objects=rows, bindings=bindings, fragments=fragments)
    exported = next(r for r in tables["source_usage"] if r["object_id"] == source["object_id"])
    usage = source_usage(rows, bindings=bindings, fragments=fragments)[source["object_id"]]
    assert {key: exported[key] for key in usage} == usage
    assert exported["closure"] == "accounted"


@pytest.mark.parametrize("field", ["text", "source_mapping", "source_refs", "role"])
def test_corrupt_machine_context_is_repair(field):
    from src.source_containers_v1 import source_accountability
    rows, fragments = _context_inputs()
    source = _linked(rows)
    target = partition(rows)["knowledge"][0]
    entry = target["metadata"]["source_bound_context"]["entries"][0]
    entry[field] = "corrupt" if field in {"text", "role"} else []
    state = source_accountability(rows, fragments=fragments)[source["object_id"]]
    assert state["human_action"] == "technical_repair"


@pytest.mark.parametrize("refs", [[None], ["bad"]])
def test_malformed_source_provenance_is_repair_not_reader_crash(refs):
    from src.source_containers_v1 import source_accountability
    rows, fragments = _context_inputs()
    source = _linked(rows)
    source["provenance"]["source_fragments"] = refs
    assert source_accountability(rows, fragments=fragments)[source["object_id"]]["closure"] == "repair_required"


@pytest.mark.parametrize("field", ["source_hash", "document_version"])
def test_mismatched_admission_binding_has_repair_instead_of_disappearing(field):
    from src.source_containers_v1 import source_accountability
    rows, fragments = _context_inputs()
    target = partition(rows)["knowledge"][0]
    target["metadata"]["admission"][field] = "wrong"
    assert review_duty_for(target, review_path="richtlijn", bindings=[], fragments=fragments) is None
    state = source_accountability(rows, bindings=[], fragments=fragments)[target["object_id"]]
    assert state["human_action"] == "technical_repair"


@pytest.mark.parametrize("raw", ["bad", {"entries": "bad"}])
def test_malformed_machine_context_target_requires_repair(raw):
    from src.source_containers_v1 import source_accountability
    rows, fragments = _context_inputs()
    target = partition(rows)["knowledge"][0]
    target["metadata"]["source_bound_context"] = raw
    state = source_accountability(rows, fragments=fragments)[target["object_id"]]
    assert state["human_action"] == "technical_repair"
