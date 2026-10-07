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


def _inputs():
    fragments = [_fragment("selected", "Bespreek met de patiënt welke behandeling het beste past."),
                 _fragment("other", "Controleer de bloeddruk dagelijks.")]
    blocks = semantic_source_blocks(fragments)
    decisions = semantic_units_from_proposal(fragments, document_id="doc-t8", proposal=_proposal(blocks[0]))
    return fragments, decisions


def _canonical():
    fragments, decisions = _inputs()
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
                                 "extra_ref", "missing_ref", "unknown_ref", "checksum", "version"])
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
