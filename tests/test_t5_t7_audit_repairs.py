"""T5-T7 audit regressions: existing identities and independent domain paths.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: opslag durable recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import hashlib
import json

import pytest

from src.four_eyes_v1 import publish_authorization_contract
from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
from src.knowledge_path_v1 import content_reviewable, source_lineage_resolves
from src.recoverable_formation_v1 import preserve_unchanged
from src.semantic_passage_v1 import semantic_source_blocks, semantic_units_from_proposal
from test_t7_creator_cut import _fragment, _proposal
from test_t4_single_knowledge_path_invariants import (
    _allowed_candidate, _allowed_source, _binding, _stamp_hash,
    _console, _append, _project_policy, _row,
)
from test_v225_beslisboom_path import _console as boom_console, _accounts, _ingest_boom


def _contract(obj, *, bindings=None, fragments=None, review_path="richtlijn"):
    obj = _stamp_hash(obj)
    return publish_authorization_contract(
        obj=obj, bindings=bindings if bindings is not None else [_binding(obj)],
        uploader_id="uploader-anne", immutable_locator=None,
        fragments=fragments, review_path=review_path,
    )


def test_pre_t7_identity_is_preserved_for_multiple_ordered_spans_and_recovery():
    fragments = [_fragment("one", "Eerste passage."), _fragment("two", "Tweede passage.")]
    blocks = semantic_source_blocks(fragments)
    spans = [{"block_id": b["block_id"], "start": 0, "end": len(b["text"])} for b in blocks]
    decisions = semantic_units_from_proposal(
        fragments, document_id="doc-old",
        proposal={"objects": [{"spans": spans, "proposed_object_type": "definition"}],
                  "abstain_reason": None},
    )
    [candidate] = materialise_knowledge_candidates(
        decisions, document_id="doc-old", fragments=iter(fragments)
    )
    material = "|".join(f'{s["block_id"]}:{s["start"]}:{s["end"]}' for s in spans)
    old_id = "doc-old-sem-" + hashlib.sha256(material.encode()).hexdigest()[:16]
    assert candidate["object_id"] == old_id
    previous = deepcopy(candidate)
    previous["metadata"] = {"semantic_passage": {"proposal_hash": "old"}}
    current = deepcopy(previous)
    current["metadata"]["semantic_passage"]["proposal_hash"] = "new"
    assert preserve_unchanged([current], [previous]) == [previous]


def test_materialiser_rebuilds_fragment_ids_mapping_and_structure_from_source():
    fragments = [_fragment("one", "Eerste passage."), _fragment("other", "Andere passage.")]
    block = semantic_source_blocks(fragments)[0]
    decisions = semantic_units_from_proposal(
        fragments, document_id="doc", proposal=_proposal(block, proposed_object_type="definition")
    )
    [expected] = materialise_knowledge_candidates(decisions, document_id="doc", fragments=fragments)
    forged = deepcopy(decisions[0])
    forged.update(source_fragment_ids=["one", "other"], source_mapping=[{"forged": True}],
                  section_path=["Verzonnen"], heading="Verzonnen")
    [actual] = materialise_knowledge_candidates([forged], document_id="doc", fragments=fragments)
    assert actual == expected
    assert actual["source_fragment_ids"] == ["one"]


@pytest.mark.parametrize("kind", ["path", "node", "outcome"])
def test_boom_tuple_uses_explicit_boom_contract_and_cannot_bypass_richtlijn(kind):
    obj = _row("boom-" + kind, kind, confirmed=kind, validation="approved")
    _stamp_hash(obj)
    binding = _binding(obj)
    allowed = _contract(obj, bindings=iter([binding]), review_path="boom")
    assert allowed["tuple_authorization"] is True
    assert "not_knowledge_candidate" not in allowed["blockers"]
    assert "blocked_pending_immutable_locator" in allowed["blockers"]
    assert content_reviewable(obj) is False
    denied = _contract(obj, bindings=[binding])
    assert denied["tuple_authorization"] is False
    assert "not_knowledge_candidate" in denied["blockers"]


def test_stale_second_tuple_cannot_satisfy_four_eyes():
    obj = _allowed_candidate()
    obj["risk"] = {"risk_level": "high"}
    _stamp_hash(obj)
    first, stale = _binding(obj, "bert"), _binding(obj, "carla")
    stale["canonical_object_hash"] = "old-hash"
    result = _contract(obj, bindings=iter([first, stale]), fragments=_allowed_source())
    assert result["tuple_authorization"] is True
    assert result["four_eyes_satisfied"] is False
    assert "four_eyes_required" in result["blockers"]


@pytest.mark.parametrize("mutation", ["unknown", "bounds", "text"])
def test_persisted_source_lineage_must_resolve_without_rewriting_history(mutation):
    obj = _allowed_candidate()
    if mutation == "unknown":
        obj["metadata"]["semantic_passage"]["spans"][0]["block_id"] = "does-not-exist"
    elif mutation == "bounds":
        obj["metadata"]["semantic_passage"]["spans"][0]["end"] = 999999
    else:
        obj["content"]["clean_text"] = "Tekst die niet in de bron staat."
    _stamp_hash(obj)
    binding = _binding(obj)
    before = json.dumps([obj, binding], sort_keys=True)
    assert not source_lineage_resolves(obj, fragments=_allowed_source())
    result = _contract(obj, bindings=[binding], fragments=_allowed_source())
    assert result["tuple_authorization"] is False
    assert "source_lineage_incomplete" in result["blockers"]
    assert json.dumps([obj, binding], sort_keys=True) == before


def test_source_input_is_required_even_with_a_valid_approval():
    obj = _allowed_candidate()
    assert source_lineage_resolves(obj, fragments=_allowed_source())
    assert not source_lineage_resolves(obj, fragments=None)
    assert _contract(obj)["tuple_authorization"] is False


def test_consider_publish_passes_explicit_boom_path(tmp_path):
    console = boom_console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_boom(console, accounts)
    snapshot = receipt["snapshot_id"]
    target = next(o for o in console.snapshot_objects(snapshot)
                  if (o.get("proposed_object_type") or o.get("object_type")) == "node")
    rows = console.review_object(
        actor_id=accounts["reviewer"]["account_id"], snapshot_id=snapshot,
        object_id=target["object_id"], decision="approve", confirmed_object_type="node",
    )
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot
    )
    contract = next(c for c in considered["object_contracts"] if c["object_id"] == target["object_id"])
    assert contract["tuple_authorization"]
    assert "not_knowledge_candidate" not in considered["blockers"]


def test_historical_heading_does_not_enter_publish_set_or_change_knowledge_gate(tmp_path):
    console, reviewer, snapshot = _console(tmp_path)
    publisher = console.create_account(username="carla", password="carla-secret", roles=("publisher",))
    envelope = console._envelope(snapshot)
    path, _ = console._verified_source_bytes(envelope)
    fragments = console._read_source_fragments(envelope, path)
    block = semantic_source_blocks(f for f in fragments if f.get("object_type") != "heading")[-1]
    obj = deepcopy(next(
        o for o in console.snapshot_objects(snapshot)
        if (o.get("content") or {}).get("clean_text") == block["text"]
    ))
    obj.update(object_id="selected", object_type="definition", confirmed_object_type="definition")
    obj["governance"]["validation_status"] = "approved"
    obj.setdefault("metadata", {})["admission"] = {"gate_result": "allowed"}
    [materialised] = materialise_knowledge_candidates(
        [{"decision_kind": "semantic_selection", "selection_origin": "proposal_selected",
          "spans": [{"block_id": block["block_id"], "start": 0, "end": len(block["text"])}],
          "source_text": block["text"]}], document_id=envelope["document_id"], fragments=fragments)
    obj["metadata"]["semantic_passage"] = materialised["semantic_passage"]
    _project_policy(console, snapshot, obj)
    _stamp_hash(obj)
    _append(console, snapshot, obj)
    console._bindings[snapshot] = [_binding(obj, reviewer["account_id"])]
    before = console.consider_publish(actor_id=publisher["account_id"], snapshot_id=snapshot)
    heading = _row("historical-heading", "heading", confirmed="heading", validation="approved",
                   text="Begrippen", origin="not_applicable", structural=True)
    _project_policy(console, snapshot, heading)
    _stamp_hash(heading)
    _append(console, snapshot, heading)
    console._bindings[snapshot].append(_binding(heading, reviewer["account_id"]))
    after = console.consider_publish(actor_id=publisher["account_id"], snapshot_id=snapshot)
    assert before["tuple_authorization"] is True
    assert "source_lineage_incomplete" not in before["blockers"]
    assert "not_knowledge_candidate" not in before["blockers"]
    assert after["blockers"] == before["blockers"]
    assert after["publishable_object_ids"] == before["publishable_object_ids"] == ["selected"]
    assert "structural_projection_not_knowledge" not in after["blockers"]


@pytest.mark.parametrize("command", ["first", "second"])
def test_corrupt_persisted_source_cannot_acquire_review_binding(tmp_path, command):
    from src.operations_console_v1 import ConsoleError
    console, reviewer, snapshot = _console(tmp_path)
    obj = _allowed_candidate()
    obj["object_id"] = "corrupt-selected"
    obj["metadata"]["semantic_passage"]["spans"][0]["block_id"] = "missing-block"
    obj["risk"] = {"risk_level": "high"}
    _project_policy(console, snapshot, obj)
    _stamp_hash(obj)
    _append(console, snapshot, obj)
    before_rows = console.snapshot_objects(snapshot)
    before_bindings = console.object_review_bindings(snapshot)
    with pytest.raises(ConsoleError, match="source_lineage_incomplete"):
        if command == "first":
            console.review_object(
                actor_id=reviewer["account_id"], snapshot_id=snapshot,
                object_id=obj["object_id"], decision="approve",
                confirmed_object_type="definition",
            )
        else:
            console.approve_second_review(
                actor_id=reviewer["account_id"], snapshot_id=snapshot,
                object_id=obj["object_id"],
            )
    assert console.snapshot_objects(snapshot) == before_rows
    assert console.object_review_bindings(snapshot) == before_bindings



def test_reviewed_selected_candidate_repeat_is_safe_but_cannot_reclassify(tmp_path):
    from src.operations_console_v1 import OperationsConsole, ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
    from tests.semantic_fixture_support import bind_fixture_selections
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
    def approve(type_):
        console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
            object_id=candidate["object_id"], decision="approve", confirmed_object_type=type_,
            expected_revision=console.objects_revision(sid))
        return next(o for o in console.snapshot_objects(sid) if o["object_id"] == candidate["object_id"])
    first = approve("definition")
    repeated = approve("definition")
    assert repeated["object_version"] == first["object_version"]
    with pytest.raises(ConsoleError, match="content_duty_required"):
        approve("explanation")
    assert approve("definition")["object_version"] == first["object_version"]
    before = console.snapshot_objects(sid)
    bindings = console.object_review_bindings(sid)
    with pytest.raises(ConsoleError) as caught:
        console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
            object_id=candidate["object_id"], decision="approve", confirmed_object_type="explanation",
            expected_revision="stale")
    assert caught.value.code == SNAPSHOT_OBJECT_WRITE_CONFLICT
    assert console.snapshot_objects(sid) == before
    assert console.object_review_bindings(sid) == bindings
