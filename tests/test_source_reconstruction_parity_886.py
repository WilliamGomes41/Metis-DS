"""Source reconstruction keeps the complete pre-optimization representation.

# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json
from pathlib import Path
import random

from src.vorming.source_reconstruction_v1 import reconstruct_source_fragments


def _cases():
    rng = random.Random(886)
    texts = ["De patiënt heeft", "ondersteuning nodig", "bij zorg.", "bijvoorbeeld advies",
             "Verder begint iets nieuws", "Niet doen", "niet", "doen", "  met\tspaties  ",
             "1", "Een kop", "19-10-2026", "tekst;", "vervolg", "einde!", ""]
    cases = [[]]
    for case in range(60):
        rows = []
        for index in range(rng.randrange(1, 9)):
            text = rng.choice(texts)
            tag = rng.choice(["p", "p", "p", "h2"])
            rows.append({
                "fragment_id": f"f{case}-{index}", "clean_text": text, "raw_text": text,
                "heading": text if tag == "h2" else None,
                "section_path": rng.choice([[], ["A"], ["B"]]),
                "source_locator": {"locator_type": "web_line_range", "locator_value": f"lines:{index};{tag}:{index}"},
                "source_page": index, "bbox": [index, 1, 2, 3],
            })
        cases.append(rows)
    # Force a long continuation so the optimized path is covered as well.
    cases.append([{"fragment_id": f"long-{i}", "clean_text": text, "raw_text": text,
                   "section_path": ["A"], "bbox": [i, 0, 1, 2],
                   "source_locator": {"locator_type": "web_line_range", "locator_value": f"lines:{i};p:{i}"}}
                  for i, text in enumerate(["De patiënt heeft"] + ["ondersteuning nodig"] * 35 + ["bij zorg."])])
    return cases


def test_complete_preoptimization_output_and_input_immutability():
    expected = json.loads((Path(__file__).parent / "fixtures" / "source_reconstruction_886.json").read_text())
    cases = _cases()
    before = deepcopy(cases)
    actual = [reconstruct_source_fragments(rows) for rows in cases]
    assert actual == expected
    assert cases == before


def test_compact_readable_example_and_mutation_isolation():
    rows = [{"fragment_id": "a", "clean_text": "De patiënt heeft", "raw_text": "De patiënt heeft",
             "section_path": ["Zorg"], "bbox": [1, 2, 3, 4]},
            {"fragment_id": "b", "clean_text": "ondersteuning nodig.", "raw_text": "ondersteuning nodig.",
             "section_path": ["Zorg"], "bbox": [5, 6, 7, 8]}]
    before = deepcopy(rows)
    [block] = reconstruct_source_fragments(rows)
    assert block["clean_text"] == "De patiënt heeft ondersteuning nodig."
    assert block["source_fragment_ids"] == ["a", "b"]
    assert block["_source_reconstruction_spans"] == [
        {"start": 0, "end": 16, "source_fragment_ids": ["a"]},
        {"start": 17, "end": 37, "source_fragment_ids": ["b"]},
    ]
    assert [(item.get("kind"), item["start"], item["end"]) for item in block["_raw_source_mapping"]] == [
        (None, 0, 16), ("join_separator", 16, 17), (None, 17, 37),
    ]
    block["bbox"][0] = 99
    block["_raw_source_mapping"][-1]["bbox"][0] = 99
    assert rows == before
    assert reconstruct_source_fragments(rows)[0]["bbox"] == [1, 2, 3, 4]


def test_long_text_can_become_exact_heading_at_a_later_join():
    first = 'De patiënt ' + 'heeft ' * 110 + 'zorg nodig'
    heading = first + ' en begeleiding van familie'
    rows = [{'fragment_id': 'a', 'clean_text': first, 'raw_text': first, 'heading': heading},
            {'fragment_id': 'b', 'clean_text': 'en begeleiding', 'raw_text': 'en begeleiding'},
            {'fragment_id': 'c', 'clean_text': 'van familie', 'raw_text': 'van familie'},
            {'fragment_id': 'd', 'clean_text': 'voor later.', 'raw_text': 'voor later.'}]
    blocks = reconstruct_source_fragments(rows)
    assert [block['clean_text'] for block in blocks] == [heading, 'voor later.']
    assert [block['source_fragment_ids'] for block in blocks] == [['a', 'b', 'c'], ['d']]


def test_work_scales_for_many_mappings_and_a_long_initial_fragment(monkeypatch):
    import src.vorming.source_reconstruction_v1 as reconstruction

    original_text = reconstruction._fragment_text
    original_copy = reconstruction.deepcopy
    work = {'text': 0, 'copied_spans': 0}

    def text(fragment):
        work['text'] += len(str(fragment.get('clean_text') or fragment.get('raw_text') or ''))
        return original_text(fragment)

    def copied(value, *args, **kwargs):
        if isinstance(value, dict):
            work['copied_spans'] += len(value.get('_source_reconstruction_spans') or [])
        return original_copy(value, *args, **kwargs)

    monkeypatch.setattr(reconstruction, '_fragment_text', text)
    monkeypatch.setattr(reconstruction, 'deepcopy', copied)

    def run(count, first):
        work.update(text=0, copied_spans=0)
        rows = [{'fragment_id': str(i), 'clean_text': first if i == 0 else 'vervolg tekst',
                 'raw_text': first if i == 0 else 'vervolg tekst'} for i in range(count)]
        [result] = reconstruct_source_fragments(rows)
        assert len(result['_source_reconstruction_spans']) == count
        return work.copy()

    small, large = run(150, 'De patiënt heeft zorg nodig'), run(600, 'De patiënt heeft zorg nodig')
    assert large['text'] <= 6 * small['text']
    assert large['copied_spans'] <= 6 * small['copied_spans']
    long_text = 'De patiënt ' + 'heeft zorg nodig ' * 6000
    measured = run(150, long_text)
    assert measured['text'] < 20 * len(long_text)
