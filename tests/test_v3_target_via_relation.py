"""B5-f/B5-d: V3 targets may name a relation; a list introduction may carry scope.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from src.vorming.source_bound_fields_v2 import KEY, evidence_schema as schema_v2
from src.vorming.source_bound_fields_v3 import (
    FIELDS, TARGET_FIELDS, VIA_RELATION, additional_context_codes, bind_fields, bound_values, evidence_schema,
    incoming_relation_targets, keep_relation_targets,
)

TEXT = "Controleer de huid dagelijks."
SELECTED = [{"block_id": "b", "start": 0, "end": len(TEXT), "text": TEXT}]
SPAN = {"type": "object"}


def _raw(**fields):
    raw = {name: {"span": None, "missing_reason": "not_applicable"} for name in FIELDS}
    raw.update(fields)
    return raw


def test_v3_schema_offers_via_relation_only_for_target_fields():
    v3 = evidence_schema(SPAN)["properties"]
    for name in TARGET_FIELDS:
        assert VIA_RELATION in v3[name]["properties"]["missing_reason"]["enum"]
    assert VIA_RELATION not in v3["subject_span"]["properties"]["missing_reason"]["enum"]
    v2 = schema_v2(SPAN)["properties"]
    assert all(VIA_RELATION not in v2[name]["properties"]["missing_reason"]["enum"] for name in TARGET_FIELDS)


@pytest.mark.parametrize("field", TARGET_FIELDS)
def test_target_via_relation_binds_and_reads_back_without_a_value(field):
    record = bind_fields(_raw(**{field: {"span": None, "missing_reason": VIA_RELATION}}),
                         selected=SELECTED, candidate_text=TEXT, proposed_type="condition")
    assert field not in record["values"]
    assert field not in bound_values(record, text=TEXT, proposed_type="condition")


def test_via_relation_is_refused_for_a_non_target_field():
    with pytest.raises(ValueError, match="source_bound_missing_reason_required"):
        bind_fields(_raw(subject_span={"span": None, "missing_reason": VIA_RELATION}),
                    selected=SELECTED, candidate_text=TEXT, proposed_type="condition")


def test_admission_keeps_a_relation_target_only_for_via_relation_fields():
    record = bind_fields(_raw(condition_target={"span": None, "missing_reason": VIA_RELATION}),
                         selected=SELECTED, candidate_text=TEXT, proposed_type="condition")
    row = {KEY: record, "condition_target": "", "supported_object": ""}
    keep_relation_targets(row, {"condition_target": "obj-target", "supported_object": "obj-other"})
    assert row["condition_target"] == "obj-target"
    assert row["supported_object"] == ""  # not via_relation: no target from proximity or relations
    keep_relation_targets(row := {KEY: record, "condition_target": ""}, {"condition_target": ""})
    assert row["condition_target"] == ""  # no relation: admission still reports condition_target_missing


def test_list_introduction_context_may_carry_scope():
    intro = "Bij patiënten met diabetes:"
    context = [{"role": "list_introduction", "span": {"block_id": "h", "start": 0, "end": len(intro)},
                "text": intro, "unresolved_reason": None}]
    raw = _raw(scope_span={"span": {"block_id": "h", "start": 4, "end": 26}, "missing_reason": None})
    record = bind_fields(raw, selected=SELECTED, candidate_text=TEXT, proposed_type="recommendation", context=context)
    assert record["values"]["scope_span"] == "patiënten met diabetes"
    assert bound_values(record, text=TEXT, proposed_type="recommendation", context=context)["scope_span"] == "patiënten met diabetes"


QUALIFIER = {"object_id": "cond", "object_version": "2"}


def _peer(object_id, relation_type, version="2", target="cond"):
    return {"object_id": object_id, "relations_for_test": [
        {"relation_type": relation_type, "target_object_id": target, "target_object_version": version}]}


@pytest.fixture
def relations(monkeypatch):
    import src.vorming.knowledge_relation_proposal_v1 as proposals
    invalid = set()
    monkeypatch.setattr(proposals, "proposed_knowledge_relations_of", lambda obj: obj.get("relations_for_test") or [])
    monkeypatch.setattr(proposals, "relation_proposal_admission_codes",
                        lambda obj, *, objects: ["relation_proposal_invalid"] if obj["object_id"] in invalid else [])
    return invalid


def test_target_comes_from_one_valid_incoming_relation_on_this_revision(relations):
    # knowledge_relation_proposal_v1: statement applies_if condition, so the edge is incoming.
    objects = [QUALIFIER, _peer("rec", "applies_if"), _peer("claim", "supported_by")]
    assert incoming_relation_targets(QUALIFIER, objects) == {"condition_target": "rec", "supported_object": "claim"}


@pytest.mark.parametrize("peers,invalid", [
    ([_peer("rec", "applies_if", version="1")], set()),                 # stale endpoint version
    ([_peer("rec", "applies_if")], {"rec"}),                             # relation fails admission checks
    ([_peer("rec", "applies_if"), _peer("rec2", "applies_if")], set()),  # ambiguous target
    ([_peer("rec", "applies_if", target="other")], set()),               # names another object
    ([_peer("rec", "except_if")], set()),                                # wrong type for condition_target
])
def test_no_target_without_one_valid_matching_relation(relations, peers, invalid):
    relations.update(invalid)
    assert "condition_target" not in incoming_relation_targets(QUALIFIER, [QUALIFIER, *peers])


def test_admission_restores_only_a_validated_via_relation_target(relations):
    from src.vorming.admission_gate_v1 import _apply_bound_fields
    record = bind_fields(_raw(condition_target={"span": None, "missing_reason": VIA_RELATION}),
                         selected=SELECTED, candidate_text=TEXT, proposed_type="condition")
    def row():  # the legacy _target_for value must never be trusted as such
        return {KEY: record, "candidate_text": TEXT, "proposed_type": "condition", "condition_target": "peer"}
    stale = row()
    assert _apply_bound_fields(stale, QUALIFIER, [QUALIFIER, _peer("rec", "applies_if", version="1")]) == []
    assert stale["condition_target"] == ""
    valid = row()
    assert _apply_bound_fields(valid, QUALIFIER, [QUALIFIER, _peer("rec", "applies_if")]) == []
    assert valid["condition_target"] == "rec"


def test_list_introduction_realizes_a_scope_heading():
    heading = "Bij patiënten met diabetes:"
    row = {"recommendation_evidence_span": TEXT, "section_path": [heading]}
    realized = [{"role": "list_introduction", "text": heading}]
    assert additional_context_codes(row, {"realized": realized}) == []
    assert additional_context_codes(row, {"realized": [{"role": "support", "text": heading}]}) == [
        "recommendation_scope_context_missing"]
