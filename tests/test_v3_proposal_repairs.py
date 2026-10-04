"""Real failure shapes, using synthetic source text only.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.source_evidence_resolution_v1 import resolve_proposal_evidence
from src.semantic_passage_v1 import SemanticPassageError
from tests.test_recommendation_context_v3 import prepare
from tests.test_recommendation_context_v3 import source


def repeated_label(core="Controleer de ondersteuning", stamp="Sterk – voor"):
    text = f"1. Bespreek de voorkeuren {stamp} 2. {core} {stamp}"
    ref = lambda literal: {"block_id": "b", "literal": literal, "occurrence": None}
    proposal = {"objects": [{"spans": [ref(core)], "proposed_object_type": "recommendation",
        "field_evidence": {"recommendation_evidence_span": {"span": ref(core), "missing_reason": None}},
        "recommendation_semantics": {"strength_evidence": ref(stamp)}}]}
    return proposal, [{"block_id": "b", "text": text}]


@pytest.mark.parametrize("stamp", ["Sterk – voor", "Zwak – voor", "Sterk – tegen", "Zwak – tegen"])
def test_v3_repeated_stamp_uses_exact_adjacency_not_first_occurrence(stamp):
    p, blocks = repeated_label(stamp=stamp)
    original = deepcopy(p)
    result = resolve_proposal_evidence(p, blocks=blocks, evidence_blocks=blocks, field_contract_v3=True)
    span = result["objects"][0]["recommendation_semantics"]["strength_evidence"]
    assert span["start"] == blocks[0]["text"].rindex(stamp)
    assert blocks[0]["text"][span["start"]:span["end"]] == stamp
    assert p == original


@pytest.mark.parametrize("mutation", ["legacy", "gap", "ambiguous_core", "wrong_field", "cross_block", "word_suffix", "missing_core", "outside_core"])
def test_repeated_stamp_without_unique_adjacent_core_stays_rejected(mutation):
    p, blocks = repeated_label()
    obj = p["objects"][0]
    if mutation == "gap":
        blocks[0]["text"] = blocks[0]["text"].replace("ondersteuning Sterk", "ondersteuning extra voorwaarde Sterk")
    if mutation == "ambiguous_core":
        blocks[0]["text"] += " Controleer de ondersteuning"
    if mutation == "wrong_field":
        obj["recommendation_semantics"]["direction_evidence"] = obj["recommendation_semantics"].pop("strength_evidence")
    if mutation == "cross_block":
        blocks.append({"block_id": "c", "text": "Controleer de ondersteuning"})
        obj["spans"][0]["block_id"] = "c"
    if mutation == "missing_core":
        obj["field_evidence"] = {}
    if mutation == "outside_core":
        obj["field_evidence"]["recommendation_evidence_span"]["span"]["literal"] = "Bespreek de voorkeuren"
    if mutation == "word_suffix":
        blocks[0]["text"] += "behoud"
    with pytest.raises(SemanticPassageError, match="semantic_evidence_literal_ambiguous"):
        resolve_proposal_evidence(p, blocks=blocks, evidence_blocks=blocks, field_contract_v3=mutation != "legacy")


def test_nonliteral_model_text_is_never_repaired_by_similarity():
    p, blocks = repeated_label()
    p["objects"][0]["spans"][0]["literal"] = "Controleer alle ondersteuning"
    with pytest.raises(SemanticPassageError, match="semantic_evidence_literal_not_found"):
        resolve_proposal_evidence(p, blocks=blocks, evidence_blocks=blocks, field_contract_v3=True)


def test_bound_condition_heading_survives_transform_admission_and_rebinding():
    heading = "Bij een kwetsbare situatie:"
    def mutate(p):
        f = p["objects"][0]["field_evidence"]
        f["condition_span"] = deepcopy(f["scope_span"])
    _, _, obj, fragments = prepare("Bespreek de voorkeuren", heading=heading, mutate=mutate)
    assert obj["metadata"]["admission"]["gate_result"] == "allowed"
    assert obj["metadata"]["admission"]["condition_span"] == heading
    from src.source_bound_fields_v3 import validate_object_fields
    validate_object_fields(obj, fragments)


@pytest.mark.parametrize("mutation", ["no_context", "wrong_role", "action_from_context"])
def test_external_field_without_matching_condition_role_is_rejected(mutation):
    def mutate(p):
        obj = p["objects"][0]
        f = obj["field_evidence"]
        f["condition_span"] = deepcopy(f["scope_span"])
        if mutation == "no_context": obj["context_evidence"] = []
        if mutation == "wrong_role": obj["context_evidence"][0]["role"] = "scope"
        if mutation == "action_from_context": f["recommended_action"] = deepcopy(f["scope_span"])
    from src.operations_console_v1 import ConsoleError
    with pytest.raises(ConsoleError, match="source_bound_field_outside_candidate"):
        prepare("Bespreek de voorkeuren", heading="Bij een kwetsbare situatie:", mutate=mutate)


@pytest.mark.parametrize("items,allowed", [
    ("• Eerste evaluatie na zeven dagen • Vervolg wekelijks", True),
    ("· Eerste evaluatie na zeven dagen · Vervolg wekelijks", True),
    ("* Eerste evaluatie na zeven dagen", True),
    ("- Eerste evaluatie na zeven dagen", True),
    ("Na zeven dagen", False),
    ("•", False),
])
def test_announced_evaluation_list_accepts_bound_timing_items_not_a_bare_time(items, allowed):
    core = "Evalueer de opties:"
    def mutate(p):
        obj = p["objects"][0]
        obj["context_evidence"] = [{"role": "timing", "span": {
            "block_id": obj["spans"][0]["block_id"], "literal": items, "occurrence": None,
        }, "unresolved_reason": None}]
    _, _, obj, _ = prepare(core, fragments=source(core + " " + items), mutate=mutate)
    codes = obj["metadata"]["admission"]["reason_codes"]
    assert ("recommendation_list_missing" not in codes) == allowed


@pytest.mark.parametrize("include_stamp", [False, True])
def test_repeated_stamp_binds_normative_core_through_admission(include_stamp):
    core, stamp = "Controleer de ondersteuning", "Sterk – voor"
    candidate = core + (" " + stamp if include_stamp else "")
    def mutate(p):
        obj = p["objects"][0]
        if not include_stamp:
            ref = deepcopy(obj["spans"][0])
            ref["literal"] = stamp
            obj["recommendation_semantics"].update(
                strength="strong", strength_status="explicit", strength_evidence=ref)
    _, _, obj, fragments = prepare(candidate, stamp=stamp if include_stamp else None,
        fragments=source(f"Bespreek de voorkeuren {stamp} {core} {stamp}"), mutate=mutate)
    assert obj["metadata"]["admission"]["gate_result"] == "allowed"
    assert obj["metadata"]["admission"]["recommendation_evidence_span"] == core
    from src.source_bound_fields_v3 import validate_object_fields
    validate_object_fields(obj, fragments)
