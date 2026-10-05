"""Literal source references -> exact positions -> unchanged validation/storage.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

from src.source_evidence_resolution_v1 import resolve_proposal_evidence
from src.semantic_passage_v1 import SemanticPassageError, semantic_source_blocks, semantic_units_from_proposal
from src.pre_review_semantic_v1 import _request_payload, semantic_units_before_review
from src.source_bound_fields_v2 import FIELDS, KEY, MODE

FIXTURE = json.loads((Path(__file__).parent / "fixtures/smetten_offset_failure.json").read_text())
TEXT = FIXTURE["request_block"]["text"]
ACTION = TEXT[:118]


def literal(block, text, **extra):
    return {"block_id": block["block_id"], "literal": text, "occurrence": None, **extra}


def proposal(block):
    ref = lambda text: literal(block, text)
    fields = {name: {"span": None, "missing_reason": "not_applicable"} for name in FIELDS}
    for name, text in {"subject_span": "iedere patiënt", "predicate_span": ACTION,
                       "type_evidence_spans": ACTION, "actor_of_scope": "iedere patiënt",
                       "recommended_action": ACTION, "action_object_or_goal": "risicofactoren voor smetten",
                       "recommendation_evidence_span": ACTION}.items():
        fields[name] = {"span": ref(text), "missing_reason": None}
    return {"objects": [{"spans": [ref(TEXT)], "proposed_object_type": "recommendation",
            "recommendation_semantics": {"direction": "for", "direction_evidence": ref(ACTION),
                "strength": "strong", "strength_status": "explicit", "strength_evidence": ref("Sterk – voor")},
            "field_evidence": fields, "context_evidence": [
                {"role": "target_group", "span": ref("iedere patiënt"), "unresolved_reason": None}]}],
            "relations": [], "abstain_reason": None, "source_assessments": []}


def resolve(p, blocks):
    return resolve_proposal_evidence(p, blocks=blocks, evidence_blocks=blocks)


def response(p):
    return {"id": "literal-response", "status": "completed", "output": [
        {"type": "message", "content": [{"type": "output_text", "text": json.dumps(p, ensure_ascii=False)}]}]}


def test_recorded_failure_and_canonical_unicode_are_reproduced():
    fragments = [FIXTURE["fragment"]]
    blocks = semantic_source_blocks(fragments)
    assert blocks[0] == {**FIXTURE["request_block"], "position": 0}
    payload = _request_payload(model="test", blocks=blocks, evidence_blocks=blocks, field_contract_v2=True)
    offered = json.loads(payload["input"][1]["content"])["source_blocks"][0]
    assert offered["text"] == TEXT and len(TEXT) == 131
    assert TEXT.index("Sterk – voor") == 119
    original = {"objects": [FIXTURE["raw_object"]], "relations": [], "abstain_reason": None}
    with pytest.raises(SemanticPassageError, match="semantic_span_bounds_invalid"):
        semantic_units_from_proposal(fragments, document_id="doc", proposal=original, field_contract_v2=True)
    # Old output has no literal; the intended text cannot be guessed from offsets.
    assert resolve(original, blocks) == original
    new = proposal(blocks[0])
    jsonschema.validate(new, payload["text"]["format"]["schema"])
    resolved = resolve(new, blocks)
    assert resolved["objects"][0]["spans"][0] == {"block_id": offered["block_id"], "start": 0, "end": 131}
    assert resolved["objects"][0]["recommendation_semantics"]["strength_evidence"] == {
        "block_id": offered["block_id"], "start": 119, "end": 131}
    units = semantic_units_from_proposal(fragments, document_id="doc", proposal=resolved, field_contract_v2=True)
    assert units[0]["clean_text"] == TEXT
    assert units[0]["proposed_recommendation_semantics"]["strength"] == "strong"
    assert units[0]["proposed_recommendation_semantics"]["direction"] == "for"


@pytest.mark.parametrize("delta", [2, -1])
def test_offset_hints_never_determine_positions(delta):
    block = FIXTURE["request_block"]
    p = proposal(block)
    p["objects"][0]["spans"][0].update(start=delta, end=131 + delta)
    p["objects"][0]["recommendation_semantics"]["strength_evidence"].update(start=119 + delta, end=131 + delta)
    before = deepcopy(p)
    first = resolve(p, [block])
    assert first == resolve(p, [block]) and p == before
    assert first == resolve(proposal(block), [block])


@pytest.mark.parametrize("text,ref,expected", [
    ("abc", {"literal": "b"}, (1, 2)),
    ("abc abc", {"literal": "abc", "occurrence": 1}, (4, 7)),
    ("aaaa", {"literal": "aa", "occurrence": 2}, (2, 4)),
    ("🙂 patiënt Sterk – voor", {"literal": "Sterk – voor"}, (10, 22)),
    ("Sterk - voor", {"literal": "Sterk - voor"}, (0, 12)),
])
def test_exact_matches_use_python_code_points(text, ref, expected):
    result = resolve({"block_id": "b", **ref}, [{"block_id": "b", "text": text}])
    assert (result["start"], result["end"]) == expected
    assert text[result["start"]:result["end"]] == ref["literal"]


@pytest.mark.parametrize("text,ref,code", [
    ("abc", {"literal": "xyz"}, "literal_not_found"),
    ("abc abc", {"literal": "abc"}, "literal_ambiguous"),
    ("abc abc", {"literal": "abc", "start": 4, "end": 7}, "literal_ambiguous"),
    ("abc", {"literal": ""}, "literal_invalid"),
    ("abc", {"literal": "abc", "occurrence": True}, "occurrence_invalid"),
    ("abc", {"literal": "abc", "occurrence": -1}, "occurrence_invalid"),
    ("abc", {"literal": "abc", "occurrence": 1}, "occurrence_invalid"),
    ("abc", {"literal": "abc", "block_id": "unknown"}, "unknown_block"),
    ("Sterk – voor", {"literal": "Sterk - voor"}, "literal_not_found"),
    ("café", {"literal": "cafe\u0301"}, "literal_not_found"),
    ("a b", {"literal": "a\u00a0b"}, "literal_not_found"),
    ("abc", {"literal": "abc", "trusted": True}, "reference_invalid"),
])
def test_fail_closed_without_normalization_or_offset_disambiguation(text, ref, code):
    with pytest.raises(SemanticPassageError, match=f"semantic_evidence_{code}"):
        resolve({"block_id": "b", **ref}, [{"block_id": "b", "text": text}])


def test_generic_fields_context_relations_and_nulls_share_one_resolver():
    block = {"block_id": "b", "text": "Een term betekent uitleg."}
    ref = literal(block, "term")
    p = {"objects": [{"spans": [ref], "field_evidence": {"defined_term": {"span": ref, "missing_reason": None}},
                     "context_evidence": [{"span": ref}], "recommendation_semantics": None}],
         "relations": [{"source_spans": [ref], "target_spans": [ref], "evidence_spans": [ref]}]}
    r = resolve(p, [block]); span = {"block_id": "b", "start": 4, "end": 8}
    assert r["objects"][0]["field_evidence"]["defined_term"]["span"] == span
    assert r["objects"][0]["context_evidence"][0]["span"] == span
    assert r["objects"][0]["recommendation_semantics"] is None
    assert all(r["relations"][0][key] == [span] for key in ("source_spans", "target_spans", "evidence_spans"))
    with pytest.raises(SemanticPassageError, match="semantic_evidence_block_conflict"):
        resolve_proposal_evidence(p, blocks=[block], evidence_blocks=[{**block, "text": "different"}])


def test_provider_path_preserves_raw_and_resolved_evidence_and_replays_diagnostics():
    from src.attempt_diagnostics_v1 import checkpoint, replay_diagnostic, validator_identity
    from src.semantic_replay_v1 import stable_json_hash
    attempt = {}
    def post(url, headers, payload, timeout):
        b = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        return response(proposal(b))
    units = semantic_units_before_review([FIXTURE["fragment"]], document_id="doc", api_key="test", model="test",
        post_json=post, field_contract_v2=True, formation_context={
            "snapshot_id": "snap", "source_sha256": "a" * 64,
            "diagnostic_checkpoint": lambda phase, values: checkpoint(attempt, phase, values)})
    assert units[0]["clean_text"] == TEXT
    d = attempt["diagnostic"]
    assert d["proposal"]["objects"][0]["spans"][0]["literal"] == TEXT
    assert d["proposal_hash"] == stable_json_hash(d["proposal"])
    assert d["resolved_proposal"]["objects"][0]["spans"][0]["end"] == 131
    assert "source_evidence_resolution_v1.py" in validator_identity()
    assert replay_diagnostic(attempt)["status"] == "validated"


def test_provider_resolution_failure_preserves_raw_diagnostic():
    from src.attempt_diagnostics_v1 import checkpoint, replay_diagnostic
    from src.operations_console_v1 import ConsoleError
    attempt = {}
    def post(url, headers, payload, timeout):
        b = json.loads(payload["input"][1]["content"])["source_blocks"][0]
        p = proposal(b); p["objects"][0]["spans"][0]["literal"] = "invented text"
        return response(p)
    with pytest.raises(ConsoleError, match="semantic_evidence_literal_not_found"):
        semantic_units_before_review([FIXTURE["fragment"]], document_id="doc", api_key="test", model="test",
            post_json=post, field_contract_v2=True, formation_context={
                "diagnostic_checkpoint": lambda phase, values: checkpoint(attempt, phase, values)})
    d = attempt["diagnostic"]
    assert d["finding"]["candidate_index"] == 0
    assert d["proposal"]["objects"][0]["spans"][0]["literal"] == "invented text"
    assert replay_diagnostic(attempt)["reason_code"] == "semantic_evidence_literal_not_found"


@pytest.mark.parametrize("mutation,code", [
    ("strength", "recommendation_strength_literal_mismatch"),
    ("direction", "recommendation_direction_literal_mismatch"),
    ("outside_field", "source_bound_field_outside_candidate"),
    ("eligibility", "semantic_span_not_candidate_selectable"),
])
def test_resolved_literals_do_not_bypass_existing_validators(mutation, code):
    fragments = [FIXTURE["fragment"]]; blocks = semantic_source_blocks(fragments)
    p = proposal(blocks[0]); row = p["objects"][0]
    row["spans"] = [literal(blocks[0], ACTION)]
    if mutation == "strength":
        row["recommendation_semantics"]["strength"] = "weak"
    elif mutation == "direction":
        row["recommendation_semantics"]["direction"] = "against"
    elif mutation == "outside_field":
        row["field_evidence"]["recommended_action"]["span"] = literal(blocks[0], "Sterk – voor")
    with pytest.raises(SemanticPassageError, match=code):
        semantic_units_from_proposal(fragments, document_id="doc", proposal=resolve(p, blocks),
            field_contract_v2=True, allowed_candidate_block_ids=set() if mutation == "eligibility" else None)


def test_literal_relation_endpoints_reach_existing_relation_attachment():
    from tests.test_d4_2_relation_proposals import _fragment, _many_to_many_proposal
    texts = ["De patiënt heeft een verhoogd risico wanneer score X aanwezig is.",
             "De werkgroep adviseert de verpleegkundige interventie A te gebruiken.",
             "Deze toelichting beschrijft waarom intensieve monitoring nodig is.",
             "De werkgroep adviseert de verpleegkundige interventie B te gebruiken."]
    fragments = [_fragment(f"f{i}", text) for i, text in enumerate(texts)]
    def post(url, headers, payload, timeout):
        blocks = json.loads(payload["input"][1]["content"])["source_blocks"]
        by_id = {b["block_id"]: b for b in blocks}
        def convert(value):
            if isinstance(value, list):
                return [convert(v) for v in value]
            if isinstance(value, dict):
                if set(value) == {"block_id", "start", "end"}:
                    block = by_id[value["block_id"]]
                    return literal(block, block["text"][value["start"]:value["end"]])
                return {k: convert(v) for k, v in value.items()}
            return value
        p = convert(_many_to_many_proposal(blocks))
        jsonschema.validate(p, payload["text"]["format"]["schema"])
        return response(p)
    units = semantic_units_before_review(fragments, document_id="doc", api_key="test", model="test", post_json=post)
    from src.knowledge_relations_v1 import PROPOSED_FIELD
    relations = [r for u in units for r in u.get(PROPOSED_FIELD, [])]
    assert len({r["relation_id"] for r in relations}) == 2
    assert all(r["relation_type"] == "applies_if" for r in relations)


def test_console_literal_evidence_persists_and_replays_after_restart(tmp_path):
    from src.operations_console_v1 import OperationsConsole
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing, PASSAGE_FORMATION_MODE_ENV
    from src.llm_provider_v1 import LLM_API_KEY_ENV, LLM_MODEL_ENV
    calls = []
    reject = [False]
    def post(url, headers, payload, timeout):
        calls.append(payload)
        b = next(b for b in json.loads(payload["input"][1]["content"])["source_blocks"] if b["text"] == TEXT)
        p = proposal(b)
        # Keep the strength label as supporting evidence; the recommendation
        # itself is a complete sentence under the existing admission contract.
        p["objects"][0]["spans"] = [literal(b, ACTION)]
        if reject[0]:
            p["objects"][0]["field_evidence"]["recommended_action"]["span"]["literal"] = "invented"
        return response(p)
    env = {PASSAGE_FORMATION_MODE_ENV: MODE, LLM_API_KEY_ENV: "test", LLM_MODEL_ENV: "test-model"}
    def open_console():
        c = OperationsConsole(root=tmp_path, source_store=tmp_path/"sources", runtime=tmp_path/"runtime")
        bind_pre_review_semantic_processing(c, environ=env, post_json=post)
        return c
    c = open_console()
    author = c.create_account(username="author", password="test-password-strong", roles=("researcher",))
    reviewer = c.create_account(username="reviewer", password="test-password-strong", roles=("reviewer",))
    receipt = c.ingest(actor_id=author["account_id"], filename="test.html",
        data=f"<html><body><h1>Risicofactoren</h1><p>{TEXT}</p></body></html>".encode(),
        content_type="text/html", ingest_kind="new", title="Test", version="1", date="2026-10-03",
        live_url="", class_="richtlijn", family="test", named_reviewers=[reviewer["account_id"]])
    sid = receipt["snapshot_id"]
    before = c.snapshot_objects(sid, include_blocked=True)
    target = next(o for o in before if KEY in (o.get("metadata") or {}))
    assert target["metadata"]["admission"]["gate_result"] == "allowed", target["metadata"]["admission"]["reason_codes"]
    replay = deepcopy(c._envelope(sid)["semantic_replay"])
    assert replay["proposal"]["objects"][0]["spans"][0]["end"] == 118
    assert replay["proposal"]["objects"][0]["recommendation_semantics"]["strength_evidence"]["end"] == 131
    assert json.loads(replay["provider_evidence"]["response"]["output_text"])["objects"][0]["spans"][0]["literal"] == ACTION
    c = open_console()
    assert c.snapshot_objects(sid, include_blocked=True) == before
    c.reextract_unpublished(actor_id=author["account_id"], snapshot_id=sid)
    assert len(calls) == 1
    assert c._envelope(sid)["semantic_replay"]["proposal"] == replay["proposal"]
    # A failed fresh model call must not replace the existing objectset/replay.
    preserved = deepcopy(c.snapshot_objects(sid, include_blocked=True))
    existing_replay = deepcopy(c._envelope(sid)["semantic_replay"])
    reject[0] = True; env[LLM_MODEL_ENV] = "different-model"
    from src.operations_console_v1 import ConsoleError
    with pytest.raises(ConsoleError, match="semantic_evidence_literal_not_found"):
        c.reextract_unpublished(actor_id=author["account_id"], snapshot_id=sid)
    c = open_console()
    assert c.snapshot_objects(sid, include_blocked=True) == preserved
    assert c._envelope(sid)["semantic_replay"] == existing_replay
