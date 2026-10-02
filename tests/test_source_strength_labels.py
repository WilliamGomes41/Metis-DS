"""Source-bound strength labels preserve advice and safety checks in v1/v2.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json

import pytest

from src.operations_console_v1 import ConsoleError
from src.pre_review_semantic_v1 import _candidate_fragments, _evidence_fragments, semantic_spec_from_fragments
from src.recommendation_semantics_v1 import is_source_strength_label, source_label_direction, source_literal_strength
from src.source_bound_fields_v2 import FIELDS


@pytest.mark.parametrize("word,strength", [("Sterk", "strong"), ("Zwak", "weak")])
@pytest.mark.parametrize("label_direction,direction", [("voor", "for"), ("tegen", "against")])
@pytest.mark.parametrize("separator", [" - ", "–", " —\u00a0", ":\n"])
def test_directional_label_variants(word, strength, label_direction, direction, separator):
    label = f"{word}{separator}{label_direction}."
    assert source_literal_strength(label) == strength
    assert source_label_direction(label) == direction
    assert is_source_strength_label(label)


@pytest.mark.parametrize("text", [
    "Sterk bewijs", "Zwak bewijs", "Sterk – bewijs", "Sterk voor verbetering",
    "De cliënt heeft een sterke voorkeur.", "Conditionele aanbeveling",
    "Voorwaardelijke aanbeveling", "Sterk – vooraf", "Zwak – tegenover",
    "Bewijskracht: laag", "Bewijskracht: hoog",
])
def test_non_recommendation_labels_are_not_normalized(text):
    assert source_literal_strength(text) is None
    assert source_label_direction(text) is None
    assert not is_source_strength_label(text)


def test_conflicting_labels_remain_ambiguous():
    assert source_literal_strength("Sterk – voor; Zwak – voor") is None
    assert source_label_direction("Sterk – voor; Sterk – tegen") is None


def fragment(text, identity="f1"):
    return {"fragment_id": identity, "fragment_hash": "original-hash",
            "raw_text": text, "clean_text": text, "section_path": ["Aanbevelingen"],
            "source_locator": {"locator_type": "page_bbox", "locator_value": "page:1;bbox:1,2,3,4"}}


@pytest.mark.parametrize("label", ["Sterk – voor", "Zwak – tegen", "Sterke aanbeveling", "Zwakke (conditionele) aanbeveling"])
def test_only_standalone_labels_are_excluded_from_candidates(label):
    advice = "Gebruik geen zalf bij deze patiënten, tenzij de arts anders adviseert."
    rows = [fragment(label, "label"), fragment(advice + " " + label, "mixed")]
    assert _candidate_fragments(rows) == [rows[1]]
    assert _evidence_fragments(rows) == rows
    assert rows[1]["raw_text"] == advice + " " + label


def prepare(text, label, strength, direction, v2, mutation=None, standalone=False):
    source = [fragment(text)]
    if standalone:
        source.append(fragment(label, "label"))
    captured = {}
    def post(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        captured.update(data)
        block = data["source_blocks"][0]
        def span(owner, value):
            start = owner["text"].index(value)
            return {"block_id": owner["block_id"], "start": start, "end": start + len(value)}
        selected = span(block, block["text"])
        evidence = next(b for b in data["evidence_blocks"] if label in b["text"])
        obj = {"spans": [selected], "proposed_object_type": "recommendation",
               "recommendation_semantics": {"direction": direction, "direction_evidence": selected,
                   "strength": strength, "strength_status": "explicit", "strength_evidence": span(evidence, label)}}
        if v2:
            obj["context_evidence"] = []
            obj["field_evidence"] = {f: {"span": None, "missing_reason": "uncertain"} for f in FIELDS}
        if mutation:
            mutation(obj, block)
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"objects": [obj], "abstain_reason": None})}]}]}
    spec = semantic_spec_from_fragments(document_id="doc", title="Richtlijn", family="Test", class_="richtlijn",
        content_kind="pdf", fragments=source, api_key="fake", model="fake", post_json=post, field_contract_v2=v2)
    return spec, captured, source


@pytest.mark.parametrize("v2", [False, True])
@pytest.mark.parametrize("advice,label,strength,direction", [
    ("Breng bij iedere patiënt de risicofactoren voor smetten in kaart, om te bepalen of preventieve maatregelen nodig zijn.", "Sterk – voor", "strong", "for"),
    ("Gebruik geen zalf.", "Sterk – tegen", "strong", "against"),
    ("Overweeg een zinkoxidesmeersel FNA.", "Zwak – voor", "weak", "for"),
    ("Gebruik geen 5 mg binnen 4 uur bij een score van 2, tenzij de arts anders adviseert.", "Zwak – tegen", "weak", "against"),
])
@pytest.mark.parametrize("standalone", [False, True])
def test_provider_path_accepts_literal_labels_and_preserves_complete_source(v2, advice, label, strength, direction, standalone):
    text = advice if standalone else advice + " " + label
    spec, captured, source = prepare(text, label, strength, direction, v2, standalone=standalone)
    assert captured["source_blocks"][0]["text"] == text
    assert source[0]["clean_text"] == text
    assert source[0]["fragment_id"] == "f1"
    obj = spec["objects"][1]
    assert obj["text"] == text
    semantics = obj["proposed_recommendation_semantics"]
    assert semantics["strength"] == strength
    assert semantics["direction"] == direction
    assert semantics["strength_evidence_span"] == label
    evidence = obj["recommendation_semantics_evidence"]
    assert evidence["direction"]["source_fragment_ids"] == ["f1"]
    assert evidence["strength"]["source_fragment_ids"] == (["label"] if standalone else ["f1"])


@pytest.mark.parametrize("v2", [False, True])
@pytest.mark.parametrize("strength,direction,code", [
    ("weak", "against", "recommendation_strength_literal_mismatch"),
    ("strong", "for", "recommendation_direction_literal_mismatch"),
])
def test_contradicting_literal_labels_still_reject(v2, strength, direction, code):
    with pytest.raises(ConsoleError) as exc:
        prepare("Gebruik geen zalf. Sterk – tegen", "Sterk – tegen", strength, direction, v2)
    assert exc.value.code == "pre_review_llm_proposal_rejected"
    assert str(exc.value) == code


@pytest.mark.parametrize("v2", [False, True])
def test_hidden_clinical_gap_is_not_relaxed(v2):
    def omit(obj, block):
        start = block["text"].index("geen")
        obj["spans"] = [{"block_id": block["block_id"], "start": 0, "end": start},
                        {"block_id": block["block_id"], "start": start + len("geen"), "end": len(block["text"])}]
    with pytest.raises(ConsoleError) as exc:
        prepare("Gebruik geen zalf. Sterk – tegen", "Sterk – tegen", "strong", "against", v2, omit)
    assert str(exc.value) == "semantic_span_hidden_gap"
