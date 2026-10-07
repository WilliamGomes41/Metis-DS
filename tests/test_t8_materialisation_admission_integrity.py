"""T8: materialisation failure is processing evidence, never blocked Admission.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import pytest

from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
from src.semantic_passage_v1 import semantic_source_blocks, semantic_units_from_proposal, SemanticPassageError
from src.semantic_transform_generic_v1 import transform
from src.admission_gate_v1 import admission_of
from tests.test_t7_creator_cut import _fragment, _manifest, _gate, _proposal


def _inputs(text="Bespreek met de patiënt welke behandeling het beste past."):
    fragments = [_fragment("selected", text),
                 _fragment("other", "Controleer de bloeddruk dagelijks.")]
    blocks = semantic_source_blocks(fragments)
    decisions = semantic_units_from_proposal(fragments, document_id="doc-t8", proposal=_proposal(blocks[0]))
    return fragments, decisions


def _canonical(text="Bespreek met de patiënt welke behandeling het beste past."):
    fragments, decisions = _inputs(text)
    candidates = materialise_knowledge_candidates(decisions, document_id="doc-t8", fragments=fragments)
    for candidate in candidates:
        candidate["semantic_passage"].update(formation_mode="semantic-source-bound-v1", model="test",
                                            source_blocks_hash="a" * 64, proposal_hash="b" * 64)
    spec = {"spec_version": "console-ingest-1.0", "document_id": "doc-t8",
            "object_version": "1.0", "target_group": [], "care_setting": [], "topic": [],
            "objects": candidates}
    return fragments, transform(spec, _manifest(), fragments)


@pytest.mark.parametrize("case,code", [
    ("unknown", "materialisation_unknown_block"),
    ("bool", "materialisation_span_invalid"),
    ("bounds", "materialisation_span_invalid"),
    ("text", "materialisation_text_mismatch"),
    ("order", "materialisation_span_order_invalid"),
])
def test_materialisation_error_is_controlled_and_precisely_located(case, code):
    fragments, decisions = _inputs()
    bad = deepcopy(decisions[0])
    if case == "unknown":
        bad["spans"][0]["block_id"] = "missing"
    elif case == "bool":
        bad["spans"][0]["start"] = False
    elif case == "bounds":
        bad["spans"][0]["end"] = 999999
    elif case == "text":
        bad["source_text"] = "Invented source."
    else:
        bad["spans"].append(deepcopy(bad["spans"][0]))
    with pytest.raises(SemanticPassageError) as caught:
        materialise_knowledge_candidates([decisions[0], bad], document_id="doc-t8", fragments=fragments)
    assert caught.value.code == code
    assert caught.value.finding["candidate_index"] == 1
    assert caught.value.finding["reason_code"] == code


@pytest.mark.parametrize("case", ["unknown", "bounds", "text", "missing_mapping", "mapping",
                                 "extra_ref", "missing_ref", "unknown_ref", "locator", "checksum", "version"])
def test_invalid_persisted_candidate_gets_no_admission_decision(case):
    fragments, rows = _canonical()
    row = rows[0]
    if case == "unknown":
        row["metadata"]["semantic_passage"]["spans"][0]["block_id"] = "missing"
    elif case == "bounds":
        row["metadata"]["semantic_passage"]["spans"][0]["end"] = 999999
    elif case == "text":
        row["content"]["clean_text"] = "Invented source."
    elif case == "missing_mapping":
        row["metadata"]["semantic_passage"].pop("source_mapping")
    elif case == "mapping":
        row["metadata"]["semantic_passage"]["source_mapping"][0]["raw_end"] = 999999
    elif case == "extra_ref":
        other = transform({"spec_version": "console-ingest-1.0", "document_id": "doc-other",
                           "object_version": "1.0", "target_group": [], "care_setting": [], "topic": [],
                           "objects": [{"object_id": "doc-other-document", "object_type": "document",
                                        "text": "Other", "source_fragment_ids": ["other"]}]},
                          _manifest(), fragments)[0]
        row["provenance"]["source_fragments"].extend(other["provenance"]["source_fragments"])
    elif case == "missing_ref":
        row["provenance"]["source_fragments"] = []
    elif case == "unknown_ref":
        row["provenance"]["source_fragments"][0]["raw_object_id"] = "UNKNOWN"
    elif case == "locator":
        row["provenance"]["source_fragments"][0]["source_locator"] = {"locator_type": "web_line_range", "locator_value": "lines:999-999"}
    elif case == "checksum":
        row["source"]["source_checksum"] = "c" * 64
    else:
        row["source"]["version"] = "999.0"
    row["metadata"]["admission"] = {"gate_result": "allowed"}
    before = deepcopy(rows)
    result = _gate(rows, fragments)
    assert not admission_of(result[0])
    assert rows == before


def test_valid_candidate_can_receive_domain_admission():
    fragments, rows = _canonical()
    result = _gate(rows, fragments)
    assert admission_of(result[0]).get("gate_result") in {"allowed", "blocked"}


def test_absent_authoritative_source_cannot_create_admission():
    _fragments, rows = _canonical()
    assert not admission_of(_gate(rows, [])[0])


def test_domain_block_keeps_a_materialised_candidate():
    fragments, rows = _canonical("Dit is achtergrondinformatie over de behandeling.")
    result = _gate(rows, fragments)
    assert admission_of(result[0])["gate_result"] == "blocked"
    assert result[0]["object_id"] == rows[0]["object_id"]
    from src.knowledge_path_v1 import content_reviewable
    assert not content_reviewable(result[0])


def test_materialisation_failure_preserves_independent_recovery(monkeypatch):
    import json
    from src import recoverable_formation_v1 as recovery
    from tests.test_recommendation_context_v3 import response_for, source
    from tests.test_recommendation_coverage_v1 import FIRST, SECOND
    fragments = [{**source(text)[0], "fragment_id": str(i), "fragment_hash": str(i)}
                 for i, text in enumerate([FIRST, SECOND])]
    blocks = semantic_source_blocks(fragments)
    payload = {"input": [{"role": "developer", "content": ""},
                        {"role": "user", "content": json.dumps(
                            {"source_blocks": blocks, "evidence_blocks": blocks})}]}
    proposal = {"objects": [response_for(payload, text)["objects"][0] for text in [FIRST, SECOND]],
                "relations": [], "source_assessments": [], "abstain_reason": None}
    original = recovery.semantic_units_from_proposal
    def corrupt_selection(*args, **kwargs):
        decisions = original(*args, **kwargs)
        for decision in decisions:
            if decision["source_text"] == SECOND:
                decision["source_text"] = "Corrupted selection text."
        return decisions
    monkeypatch.setattr(recovery, "semantic_units_from_proposal", corrupt_selection)
    data = {"fragments": fragments, "evidence_fragments": fragments, "document_id": "doc-t8",
            "allowed_candidate_block_ids": {block["block_id"] for block in blocks},
            "field_contract_v3": True}
    result, evidence = recovery.prepare(proposal, blocks=blocks, evidence_blocks=blocks,
                                       validator_input=data)
    assert len(result["objects"]) == 1
    assert result["objects"][0]["spans"][0]["block_id"] == blocks[0]["block_id"]
    assert evidence["status"] == "partial"
    assert evidence["accepted_object_count"] == 1
    assert len(evidence["rejections"]) == 1
    failure = evidence["rejections"][0]
    assert failure["reason_code"] == "materialisation_text_mismatch"
    assert failure["index"] == 1
    assert failure["finding"]["candidate_index"] == 1
    assert failure["spans"][0]["block_id"] == blocks[1]["block_id"]


def test_transform_refuses_forged_candidate_before_returning_a_bundle():
    from src.knowledge_materialisation_v1 import MaterialisationError
    fragments, decisions = _inputs()
    candidates = materialise_knowledge_candidates(decisions, document_id="doc-t8", fragments=fragments)
    candidates[0]["source_fragment_ids"].append("other")
    spec = {"spec_version": "console-ingest-1.0", "document_id": "doc-t8",
            "object_version": "1.0", "target_group": [], "care_setting": [], "topic": [],
            "objects": candidates}
    with pytest.raises(MaterialisationError, match="materialisation_source_fragments_invalid"):
        transform(spec, _manifest(), fragments)


def test_failed_preparation_keeps_previous_bundle_across_restart(tmp_path, monkeypatch):
    from src import knowledge_materialisation_v1 as materialisation
    from tests.test_recoverable_formation_v1 import system
    state, sid, actor, reviewer, _calls, _mode, make, bind = system(tmp_path, broken=False)
    before = deepcopy(state.snapshot_objects(sid))
    revision = state.objects_revision(sid)
    bindings = deepcopy(state._bindings.get(sid))
    def fail(*args, **kwargs):
        raise materialisation.MaterialisationError("materialisation_source_mapping_invalid")
    monkeypatch.setattr(materialisation, "validate_materialised_candidate", fail)
    from src.operations_console_v1 import ConsoleError
    with pytest.raises(ConsoleError) as caught:
        state.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    assert caught.value.code == "pre_review_llm_proposal_rejected"
    assert caught.value.pre_review_diagnostics["reason_code"] == "materialisation_source_mapping_invalid"
    assert state.snapshot_objects(sid) == before
    assert state.objects_revision(sid) == revision
    assert state._bindings.get(sid) == bindings
    assert state.processing_status(sid)["state"] == "failed"
    restarted = make()
    bind(restarted)
    assert restarted.snapshot_objects(sid) == before
    assert restarted.objects_revision(sid) == revision
    assert restarted._bindings.get(sid) == bindings


def test_incomplete_raw_mapping_cannot_materialise(monkeypatch):
    from src import knowledge_materialisation_v1 as materialisation
    fragments, decisions = _inputs()
    original = materialisation._selection_blocks
    def incomplete(rows):
        blocks = deepcopy(original(rows))
        for _public, source in blocks.values():
            source["_raw_source_mapping"] = []
        return blocks
    monkeypatch.setattr(materialisation, "_selection_blocks", incomplete)
    with pytest.raises(SemanticPassageError, match="materialisation_source_mapping_invalid"):
        materialise_knowledge_candidates(decisions, document_id="doc-t8", fragments=fragments)


def test_empty_selected_text_has_its_original_materialisation_reason():
    fragments, decisions = _inputs()
    start = decisions[0]["source_text"].index(" ")
    decisions[0]["spans"][0].update(start=start, end=start + 1)
    with pytest.raises(SemanticPassageError) as caught:
        materialise_knowledge_candidates(decisions, document_id="doc-t8", fragments=fragments)
    assert caught.value.code == "materialisation_text_empty"
    assert caught.value.finding["candidate_index"] == 0


def test_producer_exposes_materialisation_reason_as_controlled_processing_evidence(monkeypatch):
    from src import semantic_passage_v1 as selection
    from src.pre_review_semantic_v1 import semantic_spec_from_fragments
    from src.operations_console_v1 import ConsoleError
    fragments, decisions = _inputs()
    original = selection._project_semantic_selection
    def corrupt(*args, **kwargs):
        selected, coverage = original(*args, **kwargs)
        selected[0]["source_text"] = "Corrupted selection."
        return selected, coverage
    monkeypatch.setattr(selection, "_project_semantic_selection", corrupt)
    import json
    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        proposal = _proposal(data["source_blocks"][0])
        proposal["relations"] = []
        return {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(proposal)}]}]}
    with pytest.raises(ConsoleError) as caught:
        semantic_spec_from_fragments(document_id="doc-t8", title="Test", family="test",
                                    class_="richtlijn", fragments=fragments,
                                    content_kind="html", api_key="fixture", model="fixture",
                                    post_json=provider)
    assert caught.value.code == "pre_review_llm_proposal_rejected"
    assert caught.value.pre_review_diagnostics["reason_code"] == "materialisation_text_mismatch"
