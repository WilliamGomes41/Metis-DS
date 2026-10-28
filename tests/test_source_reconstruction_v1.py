"""Reconstruct source boundaries before knowledge-object formation.

# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from src.vorming.knowledge_materialisation_v1 import materialise_knowledge_candidates, selection_source_blocks
from src.vorming.source_reconstruction_v1 import (
    RULE_ADJACENT_GRAMMATICAL_CONTINUATION,
    STATUS_RECONSTRUCTED,
    STATUS_UNRESOLVED,
    reconstruct_source_fragments,
)


pytestmark = [
    pytest.mark.release_control_beschikbaarheid,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


FIRST = (
    "De werkgroep adviseert gepast gebruik te maken van een betrouwbare en goed "
    "gevalideerde eenzaamheidsschaal om een indicatie te krijgen van de ernst van "
    "de eenzaamheid. De werkgroep is van mening dat voor dit doel de de Jong "
    "Gierveld 6-item"
)
CONTINUATION = "versie voor wijkverpleegkundigen het meest geschikte instrument is."
COMPLETE = f"{FIRST} {CONTINUATION}"


def _fragment(
    fragment_id: str,
    text: str,
    *,
    tag: str = "p",
    line: int = 1,
    section_path: list[str] | None = None,
) -> dict:
    return {
        "fragment_id": fragment_id,
        "clean_text": text,
        "raw_text": text,
        "heading": text if tag.startswith("h") else None,
        "section_path": section_path or ["Eenzaamheid"],
        "source_locator": {
            "locator_type": "web_line_range",
            "locator_value": f"lines:{line}-{line};{tag}:{line}",
        },
    }


def test_reconstructs_adjacent_lowercase_continuation_without_invention() -> None:
    fragments = [
        _fragment("f1", FIRST, line=1),
        _fragment("f2", CONTINUATION, line=2),
    ]

    result = reconstruct_source_fragments(fragments)

    assert len(result) == 1
    assert result[0]["clean_text"] == COMPLETE
    assert result[0]["raw_text"] == COMPLETE
    assert result[0]["source_fragment_ids"] == ["f1", "f2"]
    assert result[0]["source_reconstruction"] == {
        "version": "source-reconstruction-v1.2.0",
        "status": STATUS_RECONSTRUCTED,
        "rule": RULE_ADJACENT_GRAMMATICAL_CONTINUATION,
        "source_fragment_ids": ["f1", "f2"],
    }


def test_review_window_never_cuts_a_reconstructed_sentence():
    from src.vorming.source_reconstruction_v1 import review_source_window
    from src.vorming.semantic_passage_v1 import _reconstructed_blocks
    fragments = [_fragment('before', 'Een afgeronde zin.'), _fragment('f1', FIRST),
                 _fragment('f2', CONTINUATION), _fragment('after', 'Een andere afgeronde zin.')]
    blocks = _reconstructed_blocks(fragments)
    joined = next(public for public, _ in blocks if public['text'] == COMPLETE)
    obj = {'metadata': {'semantic_passage': {'spans': [
        {'block_id': joined['block_id'], 'start': 0, 'end': len(COMPLETE)}]}},
        'provenance': {'source_fragments': [{'raw_object_id': 'f1'}, {'raw_object_id': 'f2'}]}}
    assert review_source_window(fragments, [obj]) is fragments


def test_review_window_preserves_extractor_evidence():
    from src.vorming.docling_contract_v1 import ExtractedFragments
    from src.vorming.source_reconstruction_v1 import review_source_window
    fragments = ExtractedFragments([_fragment('first', 'Een afgeronde zin.'),
        _fragment('other', 'Een andere afgeronde zin.')], {'set_aside_pages': [3]})
    window = review_source_window(fragments, [{'provenance': {'source_fragments': [
        {'raw_object_id': 'first'}]}}])
    assert [row['fragment_id'] for row in window] == ['first']
    assert window.extraction_record == fragments.extraction_record
    assert window.extraction_record is not fragments.extraction_record


def test_reconstructs_chained_continuations_until_sentence_is_closed() -> None:
    fragments = [
        _fragment("f1", "De werkgroep adviseert het gebruik van een betrouwbare", line=1),
        _fragment("f2", "en goed gevalideerde eenzaamheidsschaal voor", line=2),
        _fragment("f3", "wijkverpleegkundigen.", line=3),
    ]

    result = reconstruct_source_fragments(fragments)

    assert [row["source_fragment_ids"] for row in result] == [["f1", "f2", "f3"]]
    assert result[0]["clean_text"] == (
        "De werkgroep adviseert het gebruik van een betrouwbare en goed "
        "gevalideerde eenzaamheidsschaal voor wijkverpleegkundigen."
    )
    assert result[0]["source_reconstruction"]["status"] == STATUS_RECONSTRUCTED


def test_does_not_cross_heading_or_section_boundary_and_marks_open_text() -> None:
    fragments = [
        _fragment("f1", FIRST, line=1),
        _fragment("h1", "Andere aanbevelingen", tag="h2", line=2),
        _fragment(
            "f2",
            CONTINUATION,
            line=3,
            section_path=["Andere aanbevelingen"],
        ),
    ]

    result = reconstruct_source_fragments(fragments)

    assert len(result) == 3
    assert result[0]["clean_text"] == FIRST
    assert result[0]["source_reconstruction"]["status"] == STATUS_UNRESOLVED
    assert result[1]["clean_text"] == "Andere aanbevelingen"
    assert result[2]["clean_text"] == CONTINUATION


def test_uppercase_next_paragraph_is_not_guessed_as_a_continuation() -> None:
    result = reconstruct_source_fragments(
        [
            _fragment("f1", FIRST, line=1),
            _fragment("f2", "Een nieuwe alinea begint hier.", line=2),
        ]
    )

    assert len(result) == 2
    assert result[0]["source_reconstruction"]["status"] == STATUS_UNRESOLVED
    assert result[1]["clean_text"] == "Een nieuwe alinea begint hier."


def test_reconstruction_does_not_mutate_extracted_source_fragments() -> None:
    fragments = [
        _fragment("f1", FIRST, line=1),
        _fragment("f2", CONTINUATION, line=2),
    ]
    original = deepcopy(fragments)

    reconstruct_source_fragments(fragments)

    assert fragments == original


def test_candidates_form_only_after_reconstruction_and_keep_provenance() -> None:
    fragments = [
        _fragment("f1", FIRST, line=1),
        _fragment("f2", CONTINUATION, line=2),
    ]
    [block] = selection_source_blocks(fragments)
    assert block["source_fragment_ids"] == ["f1", "f2"]
    target = "De werkgroep is van mening"
    start = block["text"].index(target)
    first_end = block["text"].index("ernst van de eenzaamheid.") + len("ernst van de eenzaamheid.")
    assert "Jong Gierveld 6-item versie" in block["text"][start:]
    decisions = [
        {"decision_kind": "semantic_selection", "selection_origin": "proposal_selected",
         "spans": [{"block_id": block["block_id"], "start": 0, "end": first_end}],
         "source_text": block["text"][:first_end]},
        {"decision_kind": "semantic_selection", "selection_origin": "proposal_selected",
         "spans": [{"block_id": block["block_id"], "start": start, "end": len(block["text"])}],
         "source_text": block["text"][start:]},
    ]
    preceding, matching = materialise_knowledge_candidates(
        decisions, document_id="doc-eenzaamheid", fragments=fragments)

    assert matching["clean_text"].endswith("meest geschikte instrument is.")
    assert matching["source_fragment_ids"] == ["f1", "f2"]
    assert preceding["clean_text"].endswith("ernst van de eenzaamheid.")
    assert preceding["source_fragment_ids"] == ["f1"]
