"""Regression proof for #595: object proposals never redefine source evidence."""
# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from copy import deepcopy

import pytest

from src.atomic_split_v1 import (
    is_single_grammatical_claim,
    proposed_relations_for_units,
    split_meaning_units,
    split_sentences,
)
from src.context_aware_split_v1 import split_context_aware_units
from src.object_taxonomy_v1 import is_continuation_fragment


pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_beschikbaarheid,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def row(object_id, kind, section=None):
    return {
        "object_id": object_id,
        "proposed_object_type": kind,
        "section_path": section or [],
        "relations": [],
        "confirmed_relations": [],
    }


def bounds(item):
    return [r for r in item["relations"] if r["relation_type"] in {"applies_if", "except_if"}]


def test_quotes_and_abbreviations_preserve_sentence_text():
    text = 'Overleg met dr. Jansen. “Bespreek het vervolg.” Controleer de klachten.'
    assert split_sentences(text) == [
        'Overleg met dr. Jansen.', '“Bespreek het vervolg.”', 'Controleer de klachten.'
    ]


def test_independent_semicolon_claims_but_integrated_condition_stays():
    assert split_meaning_units("Gebruik een dagboek; controleer de klachten.") == [
        "Gebruik een dagboek;", "controleer de klachten."
    ]
    conditional = "Gebruik een dagboek bij klachten; tenzij de cliënt hiervan afziet."
    assert split_meaning_units(conditional) == [conditional]
    assert not is_single_grammatical_claim("")
    assert not is_single_grammatical_claim("Gebruik een dagboek; controleer de klachten.")


def test_optional_independent_advice_is_not_a_continuation():
    advice = "Eventueel bespreek het vervolg met de huisarts."
    assert not is_continuation_fragment(advice)
    assert split_meaning_units(f"Gebruik een dagboek. {advice}") == [
        "Gebruik een dagboek.", advice
    ]
    example = "Bijvoorbeeld bij een vaste plasroutine."
    assert is_continuation_fragment(example)
    assert split_meaning_units(f"Gebruik een dagboek. {example}") == [
        f"Gebruik een dagboek. {example}"
    ]


def test_relations_are_adjacent_section_bound_and_repeatable():
    units = [row("c", "condition"), row("r1", "recommendation"),
             row("e", "explanation"), row("r2", "recommendation"), row("x", "exception")]
    proposed_relations_for_units(units)
    assert bounds(units[1]) == [{"relation_type": "applies_if", "target_object_id": "c", "confirmed": False}]
    assert bounds(units[3]) == [{"relation_type": "except_if", "target_object_id": "x", "confirmed": False}]
    once = deepcopy(units)
    proposed_relations_for_units(units)
    assert units == once
    distant = [row("r", "recommendation"), row("e", "explanation"), row("x", "exception")]
    proposed_relations_for_units(distant)
    assert not bounds(distant[0])
    sections = [row("c", "condition", ["A"]), row("r", "recommendation", ["B"])]
    proposed_relations_for_units(sections)
    assert not bounds(sections[1])


def test_structural_parent_does_not_cross_section_or_change_confirmations():
    heading = row("h", "heading", ["A"])
    rec = row("r", "recommendation", ["B"])
    rec["confirmed_relations"] = [{"relation_type": "supported_by", "target_object_id": "proof", "confirmed": True}]
    confirmed = deepcopy(rec["confirmed_relations"])
    proposed_relations_for_units([heading, rec])
    assert rec["relations"] == []
    assert rec["confirmed_relations"] == confirmed


def test_split_spans_and_pure_relations_preserve_input():
    from src.atomic_split_v1 import relation_proposals_for_units, split_meaning_unit_spans

    text = '  Gebruik  een dagboek.\n\t“Controleer de klachten.”  '
    spans = split_meaning_unit_spans(text)
    assert [text[s.start:s.end] for s in spans] == [
        "Gebruik  een dagboek.", '“Controleer de klachten.”'
    ]
    assert [s.text for s in spans] == split_meaning_units(text)
    units = [row("c", "condition"), row("r", "recommendation")]
    before = deepcopy(units)
    proposed = relation_proposals_for_units(units)
    assert units == before
    assert bounds(proposed[1])
    assert relation_proposals_for_units(proposed) == proposed


def test_context_split_preserves_source_fragment_assignment():
    fragments = [
        {"fragment_id": "f1", "clean_text": "Gebruik  een dagboek.", "section_path": ["Behandeling"]},
        {"fragment_id": "f2", "clean_text": "Controleer de klachten.", "section_path": ["Behandeling"]},
    ]
    original = deepcopy(fragments)
    units = split_context_aware_units(fragments, document_id="doc")
    assert fragments == original
    assert len(units) == 2
    assert units[0]["source_fragment_ids"] == ["f1"]
    assert units[1]["source_fragment_ids"] == ["f2"]
