"""KO-1 (#995): one derived statechart state per knowledge object, never written.

Field combinations map to exactly one state; forbidden combinations surface as
invalid codes. Review stage and candidate lifecycle are the existing
classifiers; here they are fixed per case so the table is about the mapping.

# release-control-evidence: scope/belofte een afgeleide toestand per kennisobject
# release-control-evidence: opslag schrijft niets, bindingen blijven autoriteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from src.review import knowledge_object_state_v1 as ko
from src.review.review_duty_v1 import FIRST_REVIEW, SECOND_REVIEW


def _obj(status="needs_review", *, gate="allowed", reasons=(), register="selected_as_candidate",
         evidence=True, second=None):
    obj = {
        "object_id": "o1",
        "object_type": "recommendation",
        "governance": {"validation_status": status},
        "metadata": {
            "admission": {"gate_result": gate, "reason_codes": list(reasons)},
            "passage_register": {"status": register, "source": "extract"},
        },
    }
    if second is not None:
        obj["governance"]["second_review"] = second
    if evidence:
        obj["proposed_knowledge_relations"] = [{"relation_type": "supported_by", "target_object_id": "e1"}]
    return obj


@pytest.fixture
def fixed(monkeypatch):
    def apply(stage=None, lifecycle="admitted"):
        monkeypatch.setattr(ko, "review_stage", lambda *a, **k: stage)
        monkeypatch.setattr(ko, "candidate_lifecycle", lambda obj: lifecycle)
        # One exact current approver unless a case says otherwise.
        monkeypatch.setattr(ko, "exact_current_approver_ids", lambda obj, bindings: ("reviewer",))
        monkeypatch.setattr(ko, "provenance_resolves", lambda obj, fragments: True)
    return apply


def _state(obj, **kw):
    kw.setdefault("review_path", "richtlijn")
    return ko.derive_ko_state(obj, **kw)


CASES = [
    # (name, object, stage, lifecycle, release, state, invalid)
    ("superseded", _obj("superseded"), None, "admitted", "none", ko.VERVANGEN, []),
    ("rejected", _obj("rejected"), None, "admitted", "none", ko.AFGEWEZEN, []),
    ("legacy revise", _obj("revise"), None, "admitted", "none", ko.KANDIDAAT, ["legacy_revise_persisted"]),
    ("materialisation failed", _obj(), None, "materialisation_failed", "none", ko.KANDIDAAT, []),
    ("context unresolved", _obj(gate="blocked", reasons=["context_necessary_unresolved"]), None, "blocked", "none",
     ko.CONTEXT_OPEN, []),
    ("admission blocked", _obj(gate="blocked", reasons=["unresolved_reference"]), None, "blocked", "none",
     ko.KANDIDAAT, []),
    ("no evidence", _obj(evidence=False), FIRST_REVIEW, "admitted", "none", ko.BEWIJS_OPEN, []),
    ("package complete, no duty", _obj(), None, "admitted", "none", ko.SAMENGESTELD, []),
    ("first review open", _obj(), FIRST_REVIEW, "admitted", "none", ko.IN_REVIEW, []),
    ("second review open", _obj("approved"), SECOND_REVIEW, "admitted", "none", ko.TWEEDE_REVIEW, []),
    ("approved", _obj("approved"), None, "admitted", "none", ko.GOEDGEKEURD, []),
    ("published", _obj("approved"), None, "admitted", "published", ko.GEPUBLICEERD, []),
    ("release superseded", _obj("approved"), None, "admitted", "superseded", ko.VERVANGEN, []),
    ("withdrawn", _obj("approved"), None, "admitted", "withdrawn", ko.INGETROKKEN, []),
    ("approved mirror with open first review", _obj("approved"), FIRST_REVIEW, "admitted", "none", ko.IN_REVIEW,
     ["approved_mirror_with_open_first_review"]),
    ("approved, passage not assessed", _obj("approved", register="not_yet_assessed"), None, "admitted", "none",
     ko.GOEDGEKEURD, ["approved_with_passage_not_assessed"]),
    ("second-review mirror says done", _obj("approved", second={"required": True, "status": "approved"}),
     SECOND_REVIEW, "admitted", "none", ko.TWEEDE_REVIEW, ["second_review_mirror_disagrees"]),
]


@pytest.mark.parametrize("name,obj,stage,lifecycle,release,state,invalid", CASES, ids=[c[0] for c in CASES])
def test_field_combination_maps_to_one_state(fixed, name, obj, stage, lifecycle, release, state, invalid):
    fixed(stage, lifecycle)
    result = _state(obj, release_status=release)
    assert result["state"] == state
    assert result["state"] in ko.KO_STATES
    assert result["invalid"] == invalid
    assert result["reasons"]


def test_every_statechart_state_is_reachable():
    assert {case[5] for case in CASES} == set(ko.KO_STATES)


def test_derivation_writes_nothing(fixed):
    fixed(FIRST_REVIEW)
    obj = _obj()
    before = deepcopy(obj)
    _state(obj, bindings=[{"object_id": "o1", "valid": True, "decision": "approve", "suitability": "ja"}])
    assert obj == before


@pytest.mark.parametrize("lifecycle", ["structure", "source"])
def test_heading_and_source_record_are_not_knowledge_objects(fixed, lifecycle):
    fixed(None, lifecycle)
    assert _state(_obj())["state"] is None
    assert _state({"object_type": "document"})["state"] is None


def test_approval_for_a_suitability_that_forbids_it_is_invalid(fixed):
    fixed(None)
    obj = _obj("approved", register="excluded_with_reason")
    binding = {"object_id": "o1", "valid": True, "decision": "approve", "suitability": "geen_kenniseenheid"}
    assert "approval_outside_suitability" in _state(obj, bindings=[binding])["invalid"]


def test_register_that_disagrees_with_the_reviewed_suitability_is_invalid(fixed):
    fixed(None)
    obj = _obj("approved", register="excluded_with_reason")
    binding = {"object_id": "o1", "valid": True, "decision": "approve", "suitability": "ja"}
    assert "register_disagrees_with_review" in _state(obj, bindings=[binding])["invalid"]


def test_other_objects_bindings_do_not_count(fixed):
    fixed(None)
    obj = _obj("approved", register="excluded_with_reason")
    binding = {"object_id": "other", "valid": True, "decision": "approve", "suitability": "geen_kenniseenheid"}
    assert _state(obj, bindings=[binding])["invalid"] == []


def test_confirmed_explains_counts_as_evidence(fixed):
    fixed(FIRST_REVIEW)
    obj = _obj(evidence=False)
    obj["confirmed_knowledge_relations"] = [{"relation_type": "explains", "target_object_id": "e2"}]
    assert _state(obj)["state"] == ko.IN_REVIEW
    obj["confirmed_knowledge_relations"] = [{"relation_type": "applies_if", "target_object_id": "c1"}]
    assert _state(obj)["state"] == ko.BEWIJS_OPEN


def test_counts_carry_no_identifiers():
    rows = [
        {"state": ko.IN_REVIEW, "reasons": [], "invalid": []},
        {"state": ko.GOEDGEKEURD, "reasons": [], "invalid": ["approved_with_passage_not_assessed"]},
        {"state": None, "reasons": ["not_knowledge_object"], "invalid": []},
    ]
    counts = ko.count_states(rows)
    assert counts["states"][ko.IN_REVIEW] == 1
    assert counts["invalid_total"] == 1
    assert counts["not_knowledge_object"] == 1
    assert counts["ko_state_unclassified"] == 0
    assert set(counts) == {"states", "invalid", "invalid_total", "not_knowledge_object", "ko_state_unclassified"}


def test_duplicated_final_sets_agree_with_the_single_definition():
    from src.operations_console_app import _review_is_final
    from src.review.review_duty_v1 import _terminal_without_open_review
    from src.workflows.workflow_badge_counts_postgres_v1 import _LIST_FINAL_REVIEW_STATUSES
    statuses = ["approved", "rejected", "superseded", "revise", "needs_review", ""]
    assert set(_LIST_FINAL_REVIEW_STATUSES) == ko.FINAL_VALIDATION_STATUSES
    for status in statuses:
        obj = {"governance": {"validation_status": status}}
        assert _review_is_final(obj) is (status in ko.FINAL_VALIDATION_STATUSES)
        assert _terminal_without_open_review(obj) is (status in ko.RETIRED_VALIDATION_STATUSES)


def test_reprocess_retirement_without_successor_is_vervangen_and_valid(fixed):
    # revision_workflow.reprocessed_history retires a removed candidate as superseded
    # without superseded_by; that supported flow is not a malformed record.
    fixed(None)
    result = _state(_obj("superseded"))
    assert result["state"] == ko.VERVANGEN
    assert result["invalid"] == []


def test_boom_path_is_structure_not_a_knowledge_object(fixed):
    # Codex on #996: on the boom path, `path` is structure (operations_console_v1.review_lane).
    fixed(None)
    path_obj = dict(_obj(), object_type="path", confirmed_object_type="path")
    assert ko.derive_ko_state(path_obj, review_path="boom")["state"] is None
    node = dict(_obj(), object_type="node")
    assert ko.derive_ko_state(node, review_path="boom")["state"] is not None


def test_replaced_primary_keeps_the_other_binding_and_reports_the_mirror(fixed, monkeypatch):
    # Codex on #996: a still-valid second binding is not "no current binding", and the
    # second-review mirror is checked independently of the open stage.
    fixed(FIRST_REVIEW)
    monkeypatch.setattr(ko, "exact_current_approver_ids", lambda obj, bindings: ("secondary",))
    obj = _obj("approved", second={"required": True, "status": "approved"})
    result = _state(obj)
    assert result["state"] == ko.IN_REVIEW
    assert result["invalid"] == ["approved_mirror_with_open_first_review", "second_review_mirror_disagrees"]
    monkeypatch.setattr(ko, "exact_current_approver_ids", lambda obj, bindings: ())
    assert "approved_without_current_binding" in _state(obj)["invalid"]


def test_approved_without_binding_is_invalid_even_without_an_open_stage(fixed, monkeypatch):
    # Codex on #996: review_stage returns None when lineage no longer resolves; the binding
    # check must not depend on an open stage.
    fixed(None)
    monkeypatch.setattr(ko, "exact_current_approver_ids", lambda obj, bindings: ())
    result = _state(_obj("approved"))
    assert result["state"] == ko.GOEDGEKEURD
    assert result["invalid"] == ["approved_without_current_binding"]
    monkeypatch.setattr(ko, "exact_current_approver_ids", lambda obj, bindings: ("reviewer",))
    assert _state(_obj("approved"))["invalid"] == []


def test_unresolved_provenance_is_not_an_assembled_package(fixed, monkeypatch):
    # Codex on #996: review_stage is None when lineage no longer resolves; that must not
    # read as a complete package.
    fixed(None)
    monkeypatch.setattr(ko, "provenance_resolves", lambda obj, fragments: False)
    result = _state(_obj())
    assert result["state"] == ko.KANDIDAAT
    assert result["reasons"] == ["provenance_unresolved"]
    monkeypatch.setattr(ko, "provenance_resolves", lambda obj, fragments: True)
    assert _state(_obj())["state"] == ko.SAMENGESTELD
