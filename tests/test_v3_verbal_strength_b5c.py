"""B5-c: verbal strength and a lead-in label in a v3 recommendation core.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.vorming.recommendation_semantics_v1 import (
    is_source_strength_label, preceding_source_strength_span, source_label_direction,
    source_literal_strength, source_verbal_strength_cues, verbal_cue_direction,
)
from src.vorming.semantic_passage_v1 import SemanticPassageError, semantic_source_blocks, semantic_units_from_proposal
from src.vorming.source_bound_fields_v3 import FIELDS
from tests.test_d3_2_recommendation_semantics_proposal import _fragment


def validate(text, core, *, direction, status="explicit", strength="strong", label=None, version="v3"):
    fragments = [_fragment("b", text, section_path=["Aanbevelingen"])]
    block = semantic_source_blocks(fragments)[0]
    def ref(literal):
        start = block["text"].index(literal)
        return {"block_id": block["block_id"], "start": start, "end": start + len(literal)}
    fields = {f: {"span": None, "missing_reason": "not_applicable"} for f in FIELDS}
    for f, literal in {"predicate_span": core.split()[0], "type_evidence_spans": core,
                       "recommended_action": core, "action_object_or_goal": core.split()[-1],
                       "recommendation_evidence_span": core}.items():
        fields[f] = {"span": ref(literal), "missing_reason": None}
    p = {"objects": [{"spans": [ref(text)], "proposed_object_type": "recommendation",
         "recommendation_semantics": {"direction": direction, "direction_evidence": ref(core),
             "strength_status": status, "strength": strength if status == "explicit" else None,
             "strength_evidence": ref(label) if label else None},
         "field_evidence": fields, "context_evidence": []}], "relations": [], "abstain_reason": None}
    if version == "v2":
        for name in ("actor_span", "target_group_span", "scope_span"):
            fields.pop(name)
        fields["actor_of_scope"] = {"span": None, "missing_reason": "not_stated"}
    before = deepcopy(p)
    rows = semantic_units_from_proposal(fragments, document_id="b5c", proposal=p, evidence_fragments=fragments,
                                        field_contract_v3=version == "v3", field_contract_v2=version == "v2")
    assert p == before
    return rows[0]["proposed_recommendation_semantics"]


@pytest.mark.parametrize("verb,direction", [("aanbevolen", "for"), ("geadviseerd", "for"),
                                            ("afgeraden", "against"), ("ontraden", "against")])
def test_closed_verbal_list_in_core_is_explicit_strong(verb, direction):
    core = f"Fixatie wordt sterk {verb}."
    semantics = validate(core, core, direction=direction, label=f"sterk {verb}")
    assert semantics["strength"] == "strong" and semantics["direction"] == direction
    assert semantics["source_label"] == f"sterk {verb}"


def test_verbal_direction_contradiction_is_rejected():
    core = "Fixatie wordt sterk afgeraden."
    with pytest.raises(SemanticPassageError, match="recommendation_direction_literal_mismatch"):
        validate(core, core, direction="for", label="sterk afgeraden")


def test_verbal_strength_in_core_cannot_be_not_stated():
    core = "Fixatie wordt sterk afgeraden."
    with pytest.raises(SemanticPassageError, match="recommendation_strength_not_stated_conflict"):
        validate(core, core, direction="against", status="not_stated")


def test_weak_is_never_inferred_from_a_verb():
    core = "Fixatie wordt sterk afgeraden."
    with pytest.raises(SemanticPassageError, match="recommendation_strength_literal_mismatch"):
        validate(core, core, direction="against", strength="weak", label="sterk afgeraden")


@pytest.mark.parametrize("text", ["Fixatie wordt niet sterk aanbevolen.",
                                  "Fixatie wordt in die gevallen niet zo sterk aanbevolen."])
def test_negated_verbal_strength_is_not_a_cue(text):
    with pytest.raises(SemanticPassageError, match="recommendation_strength_literal_mismatch"):
        validate(text, text, direction="for", label="sterk aanbevolen")
    assert validate(text, text, direction="for", status="not_stated")["strength"] is None


def test_verbal_strength_outside_the_core_does_not_count():
    text = "Fixatie wordt sterk afgeraden. Gebruik geen zalf."
    core = "Gebruik geen zalf."
    assert validate(text, core, direction="against", status="not_stated")["strength"] is None
    with pytest.raises(SemanticPassageError, match="recommendation_strength_literal_mismatch"):
        validate(text, core, direction="against", label="sterk afgeraden")


def test_verbal_strength_stays_outside_v2():
    core = "Fixatie wordt sterk afgeraden."
    assert validate(core, core, direction="against", status="not_stated", version="v2")["strength"] is None


@pytest.mark.parametrize("text", ["De kans is sterk verhoogd.", "Dit is sterk afhankelijk van de situatie.",
                                  "sterk aanbevolenheid", "Sterke aanbeveling", "Zwak afgeraden",
                                  "Geen sterk afgeraden middel", "sterk\naanbevolen. Niet"])
def test_other_meanings_of_sterk_are_not_verbal_cues(text):
    expected = ["sterk\naanbevolen"] if text.startswith("sterk\n") else []
    assert [m.group() for m in source_verbal_strength_cues(text)] == expected


def test_verbal_cue_helpers_never_widen_label_vocabulary():
    for text in ("wordt sterk afgeraden", "sterk aanbevolen"):
        assert source_literal_strength(text) is None
        assert source_label_direction(text) is None
        assert not is_source_strength_label(text)
    assert [verbal_cue_direction(m) for m in source_verbal_strength_cues("X wordt sterk ontraden")] == ["against"]


@pytest.mark.parametrize("label,strength,direction", [
    ("Sterke aanbeveling", "strong", "against"), ("Zwakke aanbeveling", "weak", "against"),
    ("Sterk – tegen", "strong", "against")])
@pytest.mark.parametrize("gap", [": ", " ", ":"])
def test_lead_in_label_directly_before_core_binds(label, strength, direction, gap):
    core = "Gebruik geen zalf."
    semantics = validate(f"{label}{gap}{core}", core, direction=direction, strength=strength, label=label)
    assert semantics["strength"] == strength


@pytest.mark.parametrize("text", [
    "Sterke aanbeveling. Gebruik geen zalf.",           # other sentence
    "Sterke aanbeveling: bij twijfel, Gebruik geen zalf.",  # prose between label and core
])
def test_lead_in_label_needs_same_sentence_adjacency(text):
    core = "Gebruik geen zalf."
    with pytest.raises(SemanticPassageError, match="recommendation_strength_evidence_not_applicable"):
        validate(text, core, direction="against", label="Sterke aanbeveling")


def test_label_above_a_list_does_not_bind():
    # A list introduction is its own source block; only a same-block label binds.
    label, core = "Sterke aanbeveling:", "Gebruik geen zalf."
    fragments = [_fragment("l", label, section_path=["Aanbevelingen"]),
                 _fragment("b", core, section_path=["Aanbevelingen"])]
    evidence = semantic_source_blocks(fragments)
    candidates = fragments[1:]
    block = semantic_source_blocks(candidates)[0]
    owner = next(x for x in evidence if "l" in x["source_fragment_ids"])
    span = {"block_id": block["block_id"], "start": 0, "end": len(core)}
    fields = {f: {"span": None, "missing_reason": "not_applicable"} for f in FIELDS}
    for f in ("predicate_span", "type_evidence_spans", "recommended_action", "action_object_or_goal",
              "recommendation_evidence_span"):
        fields[f] = {"span": dict(span), "missing_reason": None}
    p = {"objects": [{"spans": [dict(span)], "proposed_object_type": "recommendation",
         "recommendation_semantics": {"direction": "against", "direction_evidence": dict(span),
             "strength_status": "explicit", "strength": "strong",
             "strength_evidence": {"block_id": owner["block_id"], "start": 0, "end": len("Sterke aanbeveling")}},
         "field_evidence": fields, "context_evidence": []}], "relations": [], "abstain_reason": None}
    with pytest.raises(SemanticPassageError, match="recommendation_strength_evidence_not_applicable"):
        semantic_units_from_proposal(candidates, document_id="b5c", proposal=p, evidence_fragments=fragments,
                                     field_contract_v3=True)


def test_lead_in_label_outside_the_object_does_not_bind():
    text = "Sterke aanbeveling: Gebruik geen zalf."
    core = "Gebruik geen zalf."
    fragments = [_fragment("b", text, section_path=["Aanbevelingen"])]
    block = semantic_source_blocks(fragments)[0]
    assert preceding_source_strength_span(block["text"], block["text"].index(core)) == (0, len("Sterke aanbeveling"))
    # The candidate covers only the core: the label is outside the object.
    start = block["text"].index(core)
    span = {"block_id": block["block_id"], "start": start, "end": start + len(core)}
    fields = {f: {"span": None, "missing_reason": "not_applicable"} for f in FIELDS}
    for f in ("predicate_span", "type_evidence_spans", "recommended_action", "action_object_or_goal",
              "recommendation_evidence_span"):
        fields[f] = {"span": dict(span), "missing_reason": None}
    p = {"objects": [{"spans": [dict(span)], "proposed_object_type": "recommendation",
         "recommendation_semantics": {"direction": "against", "direction_evidence": dict(span),
             "strength_status": "explicit", "strength": "strong",
             "strength_evidence": {"block_id": block["block_id"], "start": 0, "end": len("Sterke aanbeveling")}},
         "field_evidence": fields, "context_evidence": []}], "relations": [], "abstain_reason": None}
    with pytest.raises(SemanticPassageError, match="recommendation_strength_evidence_not_applicable"):
        semantic_units_from_proposal(fragments, document_id="b5c", proposal=p, evidence_fragments=fragments,
                                     field_contract_v3=True)
