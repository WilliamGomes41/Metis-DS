"""Source-bound decision-tree proposal route, still inside the experiment boundary.

The candidate route must use the sole deterministic materialiser, keep text and
identity out of model output, leave unbound relations unresolved, and stay
unreachable from production ingest until an accepted protocol change.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import fitz
import pytest

from src.vorming.decision_tree_construction_v1 import FORMATION_MODE, HUMAN_CONFIRMATION, construct, proposal_inputs
from src.vorming.decision_tree_experiment_v1 import (
    THRESHOLD_KEYS, compare_to_reference, decide, frozen_input, route_output as candidate_arm,
)
from src.vorming.decision_tree_route_v1 import request_proposal
from src.vorming.decision_tree_proposal_v1 import DecisionTreeProposalError
from src.vorming.knowledge_materialisation_v1 import MaterialisationError, materialise_knowledge_candidates

ROOT = Path(__file__).resolve().parents[1]


def _arrow(shape, start, tip):
    shape.draw_line(start, tip)
    x, y = tip
    shape.draw_line((x - 6, y - 8), (x, y))
    shape.draw_line((x + 6, y - 8), (x, y))


def _tree_pdf(tmp_path, *, second_line=True):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((150, 60), "Is er sprake van een")
        page.insert_text((150, 74), "mantelzorger?")
        page.insert_text((120, 200), "Bespreek de situatie.")
        page.insert_text((230, 280), "Maak een afspraak.")
        page.insert_text((176, 140), "Ja")
        page.insert_text((246, 140), "Nee")
        page.insert_text((60, 420), "Alleen bij volwassen mantelzorgers.")
        shape = page.new_shape()
        _arrow(shape, (170, 80), (170, 188))
        if second_line:
            _arrow(shape, (240, 80), (240, 268))
        shape.finish(closePath=False)
        shape.commit()
        path = tmp_path / "tree.pdf"
        path.write_bytes(doc.tobytes())
    return frozen_input(path, document_id="doc", source_id="src")


def _bundle_pdf(tmp_path):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((70, 60), "Heeft de mantelzorger hulp nodig?")
        page.insert_text((70, 200), "Adviseer het volgende:")
        page.insert_textbox(fitz.Rect(70, 220, 400, 300), "- Bied steun aan.\n- Plan een gesprek.")
        page.insert_text((70, 400), "Ga verder op pagina 2.")
        second = doc.new_page()
        second.insert_text((70, 60), "Verwijs naar de huisarts.")
        path = tmp_path / "bundle.pdf"
        path.write_bytes(doc.tobytes())
    return frozen_input(path, document_id="doc", source_id="src")


class _Source:
    def __init__(self, frozen):
        self.blocks = {b["text"]: b["block_id"] for b in proposal_inputs(frozen["fragments"])}
        self.fid = {f["clean_text"]: f["fragment_id"] for f in frozen["fragments"]}
        self.graphic = next(k for k, v in frozen["inventory"]["items"].items() if v["kind"] == "graphic") \
            if any(v["kind"] == "graphic" for v in frozen["inventory"]["items"].values()) else None

    def span(self, text, start=0, end=None):
        return {"block_id": self.blocks[text], "start": start, "end": len(text) if end is None else end}

    def unit(self, ref, text, role, *, entry=False, selection=None, spans=None):
        return {"ref": ref, "role": role, "selection": selection, "entry": entry,
                "spans": spans or [self.span(text)], "quoted_text": text}


def _proposal(src):
    return {"contract": "decision-tree-proposal-v1",
            "units": [src.unit("q", "Is er sprake van een mantelzorger?", "question", entry=True, selection="single"),
                      src.unit("a1", "Bespreek de situatie.", "outcome"),
                      src.unit("a2", "Maak een afspraak.", "outcome"),
                      src.unit("k", "Alleen bij volwassen mantelzorgers.", "context")],
            "connections": [
                {"ref": "c1", "from": "q", "to": "a1", "kind": "answer", "label_span": src.span("Ja Nee", 0, 2),
                 "evidence_ids": [src.graphic, src.fid["Ja"]]},
                {"ref": "c2", "from": "q", "to": "a2", "kind": "answer", "label_span": src.span("Ja Nee", 3, 6),
                 "evidence_ids": [src.graphic, src.fid["Nee"]]}],
            "context_bindings": [{"ref": "b1", "context": "k", "applies_to": ["a1", "a2"]}],
            "result_bundles": [], "unresolved": []}


def _construct(frozen, proposal):
    return construct(proposal, document_id="doc", title="Boom", family="f", class_="beslisboom",
                     content_kind="pdf", fragments=deepcopy(frozen["fragments"]),
                     inventory=frozen["inventory"], model="test-model")


def test_candidate_route_binds_literal_units_labels_and_conditions(tmp_path):
    frozen = _tree_pdf(tmp_path)
    arm = candidate_arm(frozen, _proposal(_Source(frozen)), model="test-model")
    texts = {o["object_id"]: o["content"]["clean_text"] for o in arm["objects"] if o["object_type"] != "document"}
    assert sorted(texts.values()) == sorted(["Is er sprake van een mantelzorger?", "Bespreek de situatie.",
                                             "Maak een afspraak.", "Alleen bij volwassen mantelzorgers."])
    edges = {(texts[e["from"]], texts[e["to"]], e["label"]) for e in arm["graph"]["edges"]}
    assert edges == {("Is er sprake van een mantelzorger?", "Bespreek de situatie.", "Ja"),
                     ("Is er sprake van een mantelzorger?", "Maak een afspraak.", "Nee")}
    # Labels are route evidence, never nodes; human confirmation stays mandatory.
    assert "Ja" not in texts.values() and "Nee" not in texts.values()
    assert arm["issues"] == ["decision_graph_unresolved"]
    assert arm["graph"]["unresolved"] == [HUMAN_CONFIRMATION]
    bindings = arm["context_bindings"]
    assert [texts[bindings[0]["context"]]] == ["Alleen bij volwassen mantelzorgers."]
    assert {texts[t] for t in bindings[0]["applies_to"]} == {"Bespreek de situatie.", "Maak een afspraak."}
    for obj in arm["objects"][1:]:
        assert obj["metadata"]["semantic_passage"]["formation_mode"] == FORMATION_MODE


def test_sole_materialiser_owns_text_identity_and_mapping(tmp_path, monkeypatch):
    frozen = _tree_pdf(tmp_path)
    proposal = _proposal(_Source(frozen))
    construction = _construct(frozen, proposal)
    decisions = [{"decision_kind": "semantic_selection", "selection_origin": "proposal_selected",
                  "spans": u["spans"], "source_text": u["quoted_text"]} for u in proposal["units"]]
    direct = materialise_knowledge_candidates(decisions, document_id="doc", fragments=frozen["fragments"])
    produced = construction["spec"]["objects"][1:]
    assert [(c["object_id"], c["clean_text"], c["source_fragment_ids"], c["semantic_passage"]["source_mapping"])
            for c in produced] == [(c["object_id"], c["clean_text"], c["source_fragment_ids"],
                                    c["semantic_passage"]["source_mapping"]) for c in direct]
    assert construction == _construct(frozen, deepcopy(proposal))  # deterministic, repeatable

    import src.vorming.knowledge_materialisation_v1 as materialiser

    def refuse(*_args, **_kwargs):
        raise MaterialisationError("materialisation_source_mapping_invalid")
    monkeypatch.setattr(materialiser, "materialise_knowledge_candidates", refuse)
    with pytest.raises(MaterialisationError):
        _construct(frozen, proposal)


@pytest.mark.parametrize("mutate, code", [
    (lambda p: p["units"][1].update(quoted_text="Bespreek de situatie met de huisarts."),
     "materialisation_text_mismatch"),
    (lambda p: p["units"][1].update(object_id="doc-forged"), "decision_proposal_unit_invalid"),
    (lambda p: p["units"][1].update(clean_text="Verzonnen."), "decision_proposal_unit_invalid"),
    (lambda p: p["units"][1]["spans"][0].update(end=999), "decision_proposal_span_invalid"),
    (lambda p: p["units"][1]["spans"][0].update(block_id="semblock-forged"), "decision_proposal_unknown_block"),
    (lambda p: p["connections"][0].update(evidence_ids=["p9-drawing-9"]), "decision_proposal_evidence_unknown"),
    (lambda p: p["connections"][0].update(to="ghost"), "decision_proposal_endpoint_unknown"),
    (lambda p: p["units"][0].update(selection=None), "decision_proposal_selection_invalid"),
    (lambda p: p.update(contract="decision-tree-proposal-v0"), "decision_proposal_contract_unsupported"),
    (lambda p: p["units"].append(deepcopy(p["units"][1]) | {"ref": "dup"}), "decision_construction_duplicate_unit"),
])
def test_fabricated_or_malformed_proposals_fail_closed(tmp_path, mutate, code):
    frozen = _tree_pdf(tmp_path)
    proposal = _proposal(_Source(frozen))
    mutate(proposal)
    with pytest.raises((DecisionTreeProposalError, MaterialisationError)) as error:
        _construct(frozen, proposal)
    assert error.value.code == code


def test_unbound_or_unknown_relations_stay_unresolved(tmp_path):
    frozen = _tree_pdf(tmp_path, second_line=False)
    src = _Source(frozen)
    proposal = _proposal(src)
    proposal["connections"].append({"ref": "c3", "from": "a1", "to": None, "kind": "continue",
                                    "label_span": None, "evidence_ids": [src.graphic]})
    proposal["connections"].append({"ref": "c4", "from": "a2", "to": None, "kind": "continue",
                                    "label_span": None, "evidence_ids": [src.graphic]})
    proposal["unresolved"].append({"ref": "r1", "subject": "c3", "code": "target_unknown"})
    arm = candidate_arm(frozen, proposal, model="test-model")
    codes = {code for row in arm["construction"]["relation_findings"] for code in row["codes"]}
    # Without a second line the "Nee" relation has no graphic attached to its endpoints;
    # c4 has an unknown target that the proposer did not declare.
    assert codes == {"graphic_not_bound_to_endpoints", "target_unknown"}
    assert len(arm["graph"]["edges"]) == 1
    assert any(item.startswith("target_unknown:") for item in arm["graph"]["unresolved"])
    assert {"decision_graph_unresolved", "decision_graph_answers_incomplete"} <= set(arm["issues"])


def test_connection_doubted_by_the_proposer_never_becomes_an_edge(tmp_path):
    frozen = _tree_pdf(tmp_path)
    proposal = _proposal(_Source(frozen))
    proposal["unresolved"].append({"ref": "r1", "subject": "c2", "code": "direction_unverified"})
    plan = _construct(frozen, proposal)["graph_plan"]
    assert len(plan["edges"]) == 1 and plan["edges"][0]["label"] == "Ja"
    assert any(item.startswith("direction_unverified:") and "->" in item for item in plan["unresolved"])


def test_label_must_be_next_to_the_cited_line(tmp_path):
    frozen = _tree_pdf(tmp_path)
    src = _Source(frozen)
    proposal = _proposal(src)
    # Swap labels: both are literal source text, neither lies on the other route.
    proposal["connections"][0].update(label_span=src.span("Ja Nee", 3, 6), evidence_ids=[src.graphic, src.fid["Nee"]])
    proposal["connections"][1].update(label_span=src.span("Ja Nee", 0, 2), evidence_ids=[src.graphic, src.fid["Ja"]])
    construction = _construct(frozen, proposal)
    # One drawing holds both lines; the label must lie on the line joining these endpoints.
    assert [row["codes"] for row in construction["relation_findings"]] == [["label_not_on_route"]] * 2
    assert construction["graph_plan"]["edges"] == []


def test_result_bundles_and_page_transitions_are_source_checked(tmp_path):
    frozen = _bundle_pdf(tmp_path)
    src = _Source(frozen)
    container_text = "- Bied steun aan. - Plan een gesprek."
    transition = src.fid["Ga verder op pagina 2."]
    proposal = {"contract": "decision-tree-proposal-v1",
                "units": [src.unit("q", "Heeft de mantelzorger hulp nodig?", "question", entry=True,
                                   selection="single"),
                          src.unit("adv", "Adviseer het volgende: " + container_text, "action",
                                   spans=[src.span("Adviseer het volgende:"), src.span(container_text)]),
                          src.unit("m1", "- Bied steun aan.", "context"),
                          src.unit("m2", "- Plan een gesprek.", "context"),
                          src.unit("ref", "Verwijs naar de huisarts.", "outcome")],
                "connections": [{"ref": "t1", "from": "adv", "to": "ref", "kind": "page_transition",
                                 "label_span": None, "evidence_ids": [transition]}],
                "context_bindings": [],
                "result_bundles": [{"ref": "b1", "container": "adv", "members": ["m1", "m2"]}],
                "unresolved": []}
    construction = _construct(frozen, proposal)
    assert construction["relation_findings"] == []
    assert construction["result_bundle_issues"] == []
    assert len(construction["graph_plan"]["edges"]) == 1
    arm = candidate_arm(frozen, proposal, model="test-model")
    # The current graph validator accepts only graphic/export relation evidence:
    # a page transition stays a publication blocker until it is extended.
    assert "decision_graph_graphic_evidence_missing" in arm["issues"]
    assert "decision_graph_bundle_evidence_mismatch" not in arm["issues"]

    wrong = deepcopy(proposal)
    wrong["result_bundles"][0]["members"] = ["m1", "ref"]
    wrong["connections"][0]["evidence_ids"] = [src.fid["Adviseer het volgende:"]]
    construction = _construct(frozen, wrong)
    assert construction["result_bundle_issues"]
    assert construction["relation_findings"][0]["codes"] == ["page_transition_unverified"]


def test_provider_failure_raises_without_any_other_route(tmp_path):
    from src.vorming.bounded_model_call_v1 import ModelCallLimits
    from src.operations_console_v1 import ConsoleError
    frozen = _tree_pdf(tmp_path)

    def timeout(*_args, **_kwargs):
        raise ConsoleError("pre_review_llm_processing_timeout")
    with pytest.raises(ConsoleError) as error:
        request_proposal(frozen, api_key="k", model="m", limits=ModelCallLimits(total=5), post_json=timeout)
    assert error.value.code == "pre_review_llm_processing_timeout"
    with pytest.raises(ConsoleError) as error:
        request_proposal(frozen, api_key="", model="m", limits=ModelCallLimits(total=5), post_json=timeout)
    assert error.value.code == "pre_review_llm_api_key_required"
    refused = {"status": "completed", "output": [{"content": [{"type": "refusal", "refusal": "no"}]}]}
    with pytest.raises(ConsoleError):
        request_proposal(frozen, api_key="k", model="m", limits=ModelCallLimits(total=5),
                         post_json=lambda *a: refused)


def test_acceptance_comparison_and_preregistered_decision(tmp_path):
    frozen = _tree_pdf(tmp_path)
    reference = {"units": [{"text": "Is er sprake van een mantelzorger?"}, {"text": "Bespreek de situatie."},
                           {"text": "Maak een afspraak."}],
                 "connections": [{"from": "Is er sprake van een mantelzorger?", "to": "Bespreek de situatie.",
                                  "label": "Ja"},
                                 {"from": "Is er sprake van een mantelzorger?", "to": "Maak een afspraak.",
                                  "label": "Nee"}],
                 "conditions": [{"context": "Alleen bij volwassen mantelzorgers.",
                                 "applies_to": "Bespreek de situatie."}]}
    result = compare_to_reference(candidate_arm(frozen, _proposal(_Source(frozen)), model="m"),
                                  reference, frozen["fragments"])
    assert result["fabricated_content"] == 0
    assert result["edges"]["recall"] == 1.0 and result["units"]["recall"] == 1.0
    case = {"source_sha256": frozen["source_sha256"], "reference_independent": False, "result": result}
    assert decide({"thresholds": {}}, [case])["reason"] == "thresholds_unspecified"
    thresholds = {k: 0.9 for k in THRESHOLD_KEYS} | {"correction_actions_max_per_reference_unit": 1.0}
    assert decide({"thresholds": thresholds}, [case])["reason"] == "independent_reference_missing"
    case["reference_independent"] = True
    assert decide({"thresholds": thresholds}, [case])["decision"] == "ACCEPTANCE_CRITERIA_MET"
    assert decide({"thresholds": thresholds | {"edge_precision_min": 1.1}}, [case])["decision"] == "ITERATE"


def test_preregistration_is_blocked_until_thresholds_and_references_exist():
    import json
    criteria = json.loads((ROOT / "data/audit/decision_tree_route_experiment_v1.json").read_text())
    assert decide(criteria, [])["decision"] == "BLOCKED"
    assert criteria["corpus"] == []


def test_legacy_inventory_lists_retired_route_work_read_only():
    from src.vorming.decision_tree_experiment_v1 import legacy_route_inventory
    envelopes = [
        {"snapshot_id": "snap-a", "content_kind": "pdf", "class": "beslisboom",
         "decision_unit_contract": "decision-unit-construction-v1",
         "processing_configuration": {"mode": "semantic-source-bound-v2"},
         "processing_attempts": [{"attempt_id": "a1", "state": "running"}]},
        {"snapshot_id": "snap-b", "content_kind": "boom", "class": "beslisboom", "decision_graph": {}},
        {"snapshot_id": "snap-c", "content_kind": "pdf", "class": "beslisboom",
         "decision_tree_formation": {"route": "decision-tree-source-bound-v1"}},
        {"snapshot_id": "snap-d", "content_kind": "pdf", "class": "richtlijn"},
    ]
    before = deepcopy(envelopes)
    report = legacy_route_inventory(envelopes)
    assert envelopes == before
    assert [r["snapshot_id"] for r in report["legacy_snapshots"]] == ["snap-a", "snap-b"]
    # The recorded prose mode does not describe the route a tree actually used.
    assert report["legacy_snapshots"][0]["recorded_processing_mode"] == "semantic-source-bound-v2"
    assert report["legacy_snapshots"][0]["recorded_route"] == "decision-unit-construction-v1"
    assert report["attempts_reserved_before_cutover"] == ["snap-a"]
