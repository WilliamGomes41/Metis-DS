"""V4 source function, bounded plan, resume and atomic support targets.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery version-compat
# release-control-evidence: beschikbaarheid toegang
# release-control-evidence: kwaliteit metrics slop releasebewijs
"""
from copy import deepcopy
import json

import pytest

from src.bounded_formation_v2 import PLAN_VERSION, VERSION, build_plan, execute, plan_tasks
from src.bounded_model_call_v1 import ModelCallLimits
from src.closed_review_loop_v1 import ClosedLoopReviewConsole
from src.integrity_kernel import stamp_canonical_hashes
from src.knowledge_relations_v1 import confirmed_knowledge_relations_of, knowledge_relation_errors
from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES
from src.operations_console_v1 import ConsoleError
from src.passage_register_v1 import apply_passage_register, passage_register_of
from src.pre_review_semantic_v1 import _replay_identity, _semantic_execution_before_review, bind_pre_review_semantic_processing
from src.publication_readiness_v1 import source_passage_closure
from src.review_ledger import read_events
from src.semantic_passage_v1 import semantic_source_blocks
from src.semantic_replay_v1 import LOOKUP_MISS, exact_replay_lookup
from src.serving_relations_v1 import binding_relations
from src.source_accountability_v1 import VERSION_V3, evidence_of
from src.source_bound_fields_v4 import MODE
from tests.test_recommendation_context_v3 import response_for, source
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


BACKGROUND = "In de praktijk bestaat veel variatie in het gebruik van barrièremiddelen."
CONTEXT = "Bij volwassenen in de langdurige zorg."
RECOMMENDATION = "Gebruik een barrièremiddel bij incontinentie."
SUPPORT = "De aanbeveling steunt op observationele studies."
UNRESOLVED = "De betekenis van deze passage is niet vast te stellen."


def _fragments():
    rows = []
    for index, (heading, text) in enumerate((
        ("Achtergrond", BACKGROUND),
        ("Doelgroep", CONTEXT),
        ("Aanbevelingen", RECOMMENDATION),
        ("Overwegingen", SUPPORT),
        ("Open", UNRESOLVED),
    )):
        rows.append({
            "fragment_id": f"h{index}", "fragment_hash": f"h{index}", "object_type": "heading",
            "raw_text": heading, "clean_text": heading, "section_path": [heading],
            "source_locator": {"locator_type": "web_line_range", "locator_value": f"lines:{index};h1:1"},
        })
        rows.append({
            "fragment_id": str(index), "fragment_hash": str(index),
            "raw_text": text, "clean_text": text, "section_path": [heading],
            "source_locator": {"locator_type": "web_line_range", "locator_value": f"lines:{index}"},
        })
    return rows


def _assessment(block, role, reason):
    return {"span": {"block_id": block["block_id"], "literal": block["text"], "occurrence": None},
            "role": role, "reason": reason}


def _proposal_for(payload):
    data = json.loads(payload["input"][1]["content"])
    blocks = data["source_blocks"]
    roles = (
        (BACKGROUND, "background", "historical_context"),
        (CONTEXT, "context", "target_group"),
        (SUPPORT, "support", "proposed_support"),
        (UNRESOLVED, "unresolved", "uncertain_source_role"),
    )

    def assess(block):
        for text, role, reason in roles:
            if text in block["text"]:
                return _assessment(block, role, reason)
        return None

    if any(RECOMMENDATION in block["text"] for block in blocks):
        proposal = response_for(payload, RECOMMENDATION)
        proposal["source_assessments"] = [row for row in (assess(block) for block in blocks) if row]
        return proposal
    assessments = [row for row in (assess(block) for block in blocks) if row]
    if not assessments:
        return {"objects": [], "relations": [], "abstain_reason": "no_validated_proposals", "source_assessments": []}
    return {"objects": [], "relations": [], "abstain_reason": None, "source_assessments": assessments}


def _provider(calls):
    def post(_url, _headers, payload, _timeout):
        calls.append(json.loads(payload["input"][1]["content"]))
        proposal = _proposal_for(payload)
        return {"id": f"call-{len(calls)}", "status": "completed", "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal)}]}]}
    return post


def _context(snapshot="snap-v4"):
    return {"snapshot_id": snapshot, "source_sha256": "a" * 64}


def test_background_is_not_an_object_type_and_not_answer_bearing():
    assert "background" not in CLOSED_OBJECT_TYPES
    calls = []
    units, replay = _semantic_execution_before_review(
        _fragments(), document_id="smetten", api_key="fixture", model="fixture",
        field_contract_v4=True, post_json=_provider(calls), formation_context=_context(),
    )
    selected = [unit["text"] for unit in units if (unit.get("semantic_passage") or {}).get("selection_origin") == "proposal_selected"]
    assert selected == [RECOMMENDATION]
    assert RECOMMENDATION not in {BACKGROUND, CONTEXT, SUPPORT}
    background = next(unit for unit in units if unit.get("text") == BACKGROUND)
    evidence = evidence_of({"metadata": {"source_accountability": background["source_accountability"],
                                         "semantic_passage": background["semantic_passage"]},
                            "content": {"clean_text": background["clean_text"]}})
    assert evidence["proposed_role"] == "background"
    assert evidence["answer_bearing"] is False
    assert evidence["version"] == VERSION_V3
    context = next(unit for unit in units if unit.get("text") == CONTEXT)
    assert context["source_accountability"]["proposed_role"] == "context"
    assert context["source_accountability"]["answer_bearing"] is False
    assert (context.get("semantic_passage") or {}).get("selection_origin") == "coverage_remainder"
    support = next(unit for unit in units if unit.get("text") == SUPPORT)
    stamped = apply_passage_register([{"object_id": "support", "object_type": "explanation",
        "proposed_object_type": "explanation", "content": {"clean_text": SUPPORT},
        "structure": {"section_path": ["Overwegingen"]},
        "metadata": {"admission": {"gate_result": "allowed", "proposed_type": "explanation",
                                   "section_role": "support", "reason_codes": []}}}])
    assert passage_register_of(stamped[0])["status"] == "not_yet_assessed"
    assert support["source_accountability"]["proposed_role"] == "support"
    unresolved = next(unit for unit in units if unit.get("text") == UNRESOLVED)
    closure = source_passage_closure([{
        "object_id": unresolved["object_id"],
        "object_type": "unclassified",
        "content": {"clean_text": unresolved["clean_text"]},
        "metadata": {"source_accountability": unresolved["source_accountability"],
                     "semantic_passage": unresolved["semantic_passage"]},
        "governance": {"validation_status": "needs_review"},
    }])
    assert unresolved["object_id"] in closure["unresolved_source_passage_ids"]
    plan = replay["provider_evidence"]["formation_plan"]
    assert plan["version"] == PLAN_VERSION
    _, replay_again = _semantic_execution_before_review(
        _fragments(), document_id="smetten", api_key="fixture", model="fixture",
        field_contract_v4=True, post_json=_provider([]), formation_context=_context(),
    )
    assert replay_again["provider_evidence"]["formation_plan"]["plan_hash"] == plan["plan_hash"]
    assert replay_again["provider_evidence"]["formation_plan"]["tasks"] == plan["tasks"]


def test_v3_replay_is_not_a_v4_replay():
    fragments = _fragments()
    blocks = semantic_source_blocks(fragments)
    v3 = _replay_identity(document_id="smetten", model="fixture", blocks=blocks, evidence_blocks=blocks,
                          source_fragments=fragments, formation_context=_context(), field_contract_v3=True)
    v4 = _replay_identity(document_id="smetten", model="fixture", blocks=blocks, evidence_blocks=blocks,
                          source_fragments=fragments, formation_context=_context(), field_contract_v4=True)
    assert v3["hash"] != v4["hash"]
    assert "bounded-formation-v2" in v4["components"]["semantic_contract_version"]
    assert "source-bound-fields-v4" in v4["components"]["semantic_contract_version"]
    record = {"version": "semantic-replay-v1.0.0", "identity": v3, "proposal": {"objects": []},
              "proposal_hash": "0" * 64, "validation": "passed", "formation_method": "semantic",
              "origin_execution": "inference"}
    assert exact_replay_lookup(record, expected_identity=v4).status == LOOKUP_MISS


def test_budget_exhaustion_is_one_checkpoint_and_resume_skips_completed_ranges(monkeypatch):
    fragments = [dict(source(text)[0], fragment_id=str(index), fragment_hash=str(index), section_path=[str(index)])
                 for index, text in enumerate([RECOMMENDATION, "Controleer dagelijks de huid bij smetten."])]
    # The formation budget and the in-call timeout share time.monotonic. Advance
    # only after the successful call's own timeout check, so the next task is
    # persisted once instead of being reported as a provider timeout.
    clock = {"mode": "hold"}

    def monotonic():
        if clock["mode"] == "pass_check":
            clock["mode"] = "exhausted"
            return 0.0
        if clock["mode"] == "exhausted":
            return 100.0
        return 0.0

    monkeypatch.setattr("src.bounded_formation_v2.time.monotonic", monotonic)
    calls = []

    def post(_url, _headers, payload, _timeout):
        calls.append(json.loads(payload["input"][1]["content"]))
        if clock["mode"] == "hold":
            clock["mode"] = "pass_check"
        text = calls[-1]["source_blocks"][0]["text"]
        proposal = response_for(payload, text)
        proposal["source_assessments"] = []
        return {"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps(proposal)}]}]}

    checkpoints = []
    units, replay = _semantic_execution_before_review(
        fragments, document_id="smetten", api_key="fixture", model="fixture", field_contract_v4=True,
        post_json=post, formation_context={**_context(), "diagnostic_checkpoint": lambda phase, values: checkpoints.append(phase)},
        model_limits=ModelCallLimits(total=5, connect=1, idle=1, attempt=120, max_attempts=4),
    )
    evidence = replay["provider_evidence"]
    assert evidence["task_policy"] == VERSION
    assert evidence["formation_state"] == "pending"
    assert evidence["formation_progress"]["pending_task_count"] == 1
    assert checkpoints.count("proposal_received") == 2
    assert [block["text"] for block in calls[0]["source_blocks"]] == [RECOMMENDATION]
    first_ids = [unit["object_id"] for unit in units if unit.get("text") == RECOMMENDATION]

    clock["mode"] = "hold"
    resumed_calls = []

    def resume_post(_url, _headers, payload, _timeout):
        resumed_calls.append(json.loads(payload["input"][1]["content"]))
        text = resumed_calls[-1]["source_blocks"][0]["text"]
        proposal = response_for(payload, text)
        proposal["source_assessments"] = []
        return {"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps(proposal)}]}]}

    units_after, replay_after = _semantic_execution_before_review(
        fragments, document_id="smetten", api_key="fixture", model="fixture", field_contract_v4=True,
        post_json=resume_post, formation_context={**_context(), "resume_formation": True, "semantic_replay": replay},
        model_limits=ModelCallLimits(total=30, connect=5, idle=5, attempt=120, max_attempts=4),
    )
    assert len(resumed_calls) == 1
    assert resumed_calls[0]["source_blocks"][0]["text"] != RECOMMENDATION
    assert replay_after["provider_evidence"]["formation_state"] == "complete"
    assert first_ids[0] in {unit["object_id"] for unit in units_after}


def test_fifty_unstarted_tasks_make_one_checkpoint_and_zero_provider_calls():
    fragments = [dict(source(f"Bronpassage {index} met voldoende klinische tekst voor een eigen taak.")[0],
                      fragment_id=str(index), fragment_hash=str(index), section_path=[str(index)])
                 for index in range(50)]
    blocks = semantic_source_blocks(fragments)
    checkpoints = []

    def forbidden(**kwargs):
        raise AssertionError("provider must not run")

    proposal, evidence = execute(
        blocks=blocks, evidence_blocks=blocks,
        validator_input={"fragments": fragments, "document_id": "smetten", "evidence_fragments": fragments,
                         "allowed_candidate_block_ids": [block["block_id"] for block in blocks],
                         "field_contract_v4": True, "source_accountability_version": VERSION_V3},
        provider=forbidden, limits=ModelCallLimits(total=0),
        checkpoint=lambda phase, values: checkpoints.append((phase, deepcopy(values))),
        plan_identity={"source_hash": "a" * 64, "extractor_version": "fixture",
                       "reconstruction_version": "fixture", "semantic_contract_version": MODE},
    )
    assert proposal["objects"] == []
    assert len(evidence["tasks"]) == 50
    assert len(checkpoints) == 1
    assert evidence["formation_state"] == "pending"
    assert evidence["formation_plan"]["plan_hash"]
    spans = [span for task in evidence["formation_plan"]["tasks"] for span in task["target_spans"]]
    assert len(spans) == 50


def test_unassessed_abstention_stays_pending_and_can_resume():
    fragments = [dict(source(BACKGROUND)[0], fragment_id="0", fragment_hash="0", section_path=["0"])]
    blocks = semantic_source_blocks(fragments)
    seen = []

    def provider(**kwargs):
        seen.append(kwargs.get("selection_targets"))
        block = kwargs["blocks"][0]
        if len(seen) == 1:
            return {"objects": [], "relations": [], "source_assessments": [],
                    "abstain_reason": "no_validated_proposals"}
        return {"objects": [], "relations": [], "abstain_reason": None, "source_assessments": [{
            "span": {"block_id": block["block_id"], "start": 0, "end": len(block["text"])},
            "role": "background", "reason": "historical_context",
        }]}

    validator = {"fragments": fragments, "document_id": "smetten", "evidence_fragments": fragments,
                 "allowed_candidate_block_ids": [block["block_id"] for block in blocks],
                 "field_contract_v4": True, "source_accountability_version": VERSION_V3}
    identity = {"source_hash": "a" * 64, "extractor_version": "fixture",
                "reconstruction_version": "fixture", "semantic_contract_version": MODE}
    proposal, evidence = execute(
        blocks=blocks, evidence_blocks=blocks, validator_input=validator, provider=provider,
        limits=ModelCallLimits(total=30, connect=5, idle=5, attempt=120, max_attempts=4),
        plan_identity=identity,
    )
    assert evidence["formation_state"] == "pending"
    assert evidence["tasks"][0]["status"] == "partial"
    assert evidence["pending_rejections"]
    assert seen == [None]

    proposal, evidence = execute(
        blocks=blocks, evidence_blocks=blocks, validator_input=validator, provider=provider,
        limits=ModelCallLimits(total=30, connect=5, idle=5, attempt=120, max_attempts=4),
        proposal=proposal, evidence=evidence, plan_identity=identity,
    )
    assert seen[1] is not None
    assert evidence["formation_state"] == "complete"
    assert evidence["pending_rejections"] == []
    assert proposal["source_assessments"][0]["role"] == "background"


def _support_console(tmp_path):
    console = ClosedLoopReviewConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    receipt = console.ingest(
        actor_id=researcher["account_id"], filename="smetten.html", content_type="text/html",
        data="<html><body><h1>Smetten</h1><p>Gebruik een barrièremiddel bij incontinentie.</p></body></html>".encode(),
        ingest_kind="new", title="Smetten", version="1.0", date="2026-10-05", live_url="",
        class_="richtlijn", family="smetten", named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    base = next(row for row in console.snapshot_objects(sid) if row.get("object_type") not in {"document", "heading"})
    rows = [row for row in console._load_objects(sid, remember=False) if row.get("object_type") in {"document", "heading"}]
    support = deepcopy(base)
    support.update(object_id="support-1", object_type="explanation", proposed_object_type="explanation", object_version="1.0")
    support["content"] = {**support.get("content", {}), "clean_text": SUPPORT}
    claims = []
    for index in range(3):
        claim = deepcopy(base)
        claim.update(object_id=f"claim-{index}", object_type="recommendation", proposed_object_type="recommendation", object_version="1.0")
        claim["content"] = {**claim.get("content", {}), "clean_text": f"{RECOMMENDATION} {index}"}
        claim["confirmed_relations"] = []
        stamp_canonical_hashes(claim)
        claims.append(claim)
    support["confirmed_relations"] = []
    stamp_canonical_hashes(support)
    rows.extend([support, *claims])
    console._commit_prepared_store(objects=(sid, rows), expected_revision=console.objects_revision(sid))
    return console, reviewer, sid


def _prove_atomic_support(console, reviewer, sid, monkeypatch):
    before_objects = console.snapshot_objects(sid)
    before_ledger = list(read_events(console._ledger_path))
    revision = console.objects_revision(sid)

    def fail_commit(**kwargs):
        raise RuntimeError("commit failed")

    monkeypatch.setattr(console, "_commit_prepared_store", fail_commit)
    with pytest.raises(RuntimeError, match="commit failed"):
        console.confirm_support_targets(
            actor_id=reviewer["account_id"], snapshot_id=sid, support_object_id="support-1",
            claim_object_ids=["claim-0", "claim-1", "claim-2"], expected_revision=revision, command_id="cmd-fail",
        )
    assert console.snapshot_objects(sid) == before_objects
    assert list(read_events(console._ledger_path)) == before_ledger
    monkeypatch.undo()

    result = console.confirm_support_targets(
        actor_id=reviewer["account_id"], snapshot_id=sid, support_object_id="support-1",
        claim_object_ids=["claim-0", "claim-1", "claim-2"], expected_revision=revision, command_id="cmd-1",
    )
    current = {row["object_id"]: row for row in console.snapshot_objects(sid)}
    assert result["confirmed_edge_count"] == 3
    assert sum(1 for claim in ("claim-0", "claim-1", "claim-2") for rel in binding_relations(current[claim])
               if rel.get("relation_type") == "supported_by" and rel.get("target_object_id") == "support-1") == 3
    assert len([row for row in console.snapshot_objects(sid) if row["object_id"] == "support-1"]) == 1
    support_version = current["support-1"]["object_version"]
    for claim_id in ("claim-0", "claim-1", "claim-2"):
        claim = current[claim_id]
        assert knowledge_relation_errors(claim) == []
        canonical = confirmed_knowledge_relations_of(claim)
        assert [(row["relation_type"], row["target_object_id"], row["target_object_version"]) for row in canonical] == [
            ("supported_by", "support-1", support_version)
        ]
    assert passage_register_of(current["support-1"])["status"] == "linked_as_support"
    audits = [event for event in read_events(console._ledger_path)
              if (event.get("details") or {}).get("decision") == "confirm_support_targets"]
    assert len(audits) == 1
    again = console.confirm_support_targets(
        actor_id=reviewer["account_id"], snapshot_id=sid, support_object_id="support-1",
        claim_object_ids=["claim-0", "claim-1", "claim-2"],
        expected_revision=console.objects_revision(sid), command_id="cmd-1",
    )
    assert again["command_id"] == "cmd-1"
    assert len([event for event in read_events(console._ledger_path)
                if (event.get("details") or {}).get("decision") == "confirm_support_targets"]) == 1
    with pytest.raises(ConsoleError):
        console.confirm_support_targets(
            actor_id=reviewer["account_id"], snapshot_id=sid, support_object_id="support-1",
            claim_object_ids=["claim-0"], expected_revision="stale", command_id="cmd-stale",
        )


def test_confirm_support_targets_is_one_atomic_command(tmp_path, monkeypatch):
    console, reviewer, sid = _support_console(tmp_path)
    _prove_atomic_support(console, reviewer, sid, monkeypatch)


def test_postgres_support_confirmation_is_atomic(workflow_postgres, tmp_path, monkeypatch):
    from tests.test_review_batch_atomic_postgres import _console
    console = _console(tmp_path / "pg", workflow_postgres)
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    receipt = console.ingest(
        actor_id=researcher["account_id"], filename="smetten.html", content_type="text/html",
        data="<html><body><h1>Smetten</h1><p>Gebruik een barrièremiddel bij incontinentie.</p></body></html>".encode(),
        ingest_kind="new", title="Smetten", version="1.0", date="2026-10-05", live_url="",
        class_="richtlijn", family="smetten", named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    base = next(row for row in console.snapshot_objects(sid) if row.get("object_type") not in {"document", "heading"})
    rows = [row for row in console._load_objects(sid, remember=False) if row.get("object_type") in {"document", "heading"}]
    support = deepcopy(base)
    support.update(object_id="support-1", object_type="explanation", proposed_object_type="explanation", object_version="1.0")
    support["content"] = {**support.get("content", {}), "clean_text": SUPPORT}
    claims = []
    for index in range(3):
        claim = deepcopy(base)
        claim.update(object_id=f"claim-{index}", object_type="recommendation", proposed_object_type="recommendation", object_version="1.0")
        claim["content"] = {**claim.get("content", {}), "clean_text": f"{RECOMMENDATION} {index}"}
        claim["confirmed_relations"] = []
        stamp_canonical_hashes(claim)
        claims.append(claim)
    support["confirmed_relations"] = []
    stamp_canonical_hashes(support)
    rows.extend([support, *claims])
    console._commit_prepared_store(objects=(sid, rows), expected_revision=console.objects_revision(sid))
    _prove_atomic_support(console, reviewer, sid, monkeypatch)
