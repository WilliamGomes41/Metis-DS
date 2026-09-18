"""Contract tests for source-bound semantic passage proposals.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""

import pytest

from src.semantic_passage_v1 import (
    SemanticPassageError,
    semantic_source_blocks,
    semantic_units_from_proposal,
)


def _fragment(fragment_id: str, text: str, *, section: str = "Behandeling") -> dict:
    return {
        "fragment_id": fragment_id,
        "raw_text": text,
        "clean_text": text,
        "section_path": [section],
    }


def test_semantic_proposal_reconstructs_only_selected_source_text() -> None:
    fragments = [
        _fragment(
            "frag-1",
            "Bespreek met de patiënt welke behandeling het beste past.",
        )
    ]
    blocks = semantic_source_blocks(fragments)
    text = blocks[0]["text"]

    units = semantic_units_from_proposal(
        fragments,
        document_id="doc-1",
        proposal={
            "objects": [
                {
                    "spans": [
                        {
                            "block_id": blocks[0]["block_id"],
                            "start": 0,
                            "end": len(text),
                        }
                    ],
                    "proposed_object_type": "recommendation",
                }
            ]
        },
    )

    assert len(units) == 1
    assert units[0]["clean_text"] == text
    assert units[0]["source_fragment_ids"] == ["frag-1"]
    assert units[0]["proposed_object_type"] == "recommendation"
    assert units[0]["semantic_passage"]["source_bound"] is True


def test_model_authored_candidate_text_is_outside_the_contract() -> None:
    fragments = [_fragment("frag-1", "Bespreek de behandeling.")]
    block = semantic_source_blocks(fragments)[0]

    with pytest.raises(
        SemanticPassageError,
        match="semantic_object_contains_untrusted_fields",
    ):
        semantic_units_from_proposal(
            fragments,
            document_id="doc-1",
            proposal={
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": len(block["text"]),
                            }
                        ],
                        "proposed_object_type": "recommendation",
                        "candidate_text": "AI verzint deze tekst.",
                    }
                ]
            },
        )


def test_invalid_source_span_fails_closed() -> None:
    fragments = [_fragment("frag-1", "Bespreek de behandeling.")]
    block = semantic_source_blocks(fragments)[0]

    with pytest.raises(SemanticPassageError, match="semantic_span_bounds_invalid"):
        semantic_units_from_proposal(
            fragments,
            document_id="doc-1",
            proposal={
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": 9999,
                            }
                        ],
                        "proposed_object_type": "recommendation",
                    }
                ]
            },
        )


def test_unknown_source_block_fails_closed() -> None:
    fragments = [_fragment("frag-1", "Bespreek de behandeling.")]

    with pytest.raises(SemanticPassageError, match="semantic_span_unknown_block"):
        semantic_units_from_proposal(
            fragments,
            document_id="doc-1",
            proposal={
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": "semblock-does-not-exist",
                                "start": 0,
                                "end": 8,
                            }
                        ]
                    }
                ]
            },
        )


def test_abstain_creates_no_candidate() -> None:
    fragments = [_fragment("frag-1", "Een moeilijk interpreteerbare passage.")]

    units = semantic_units_from_proposal(
        fragments,
        document_id="doc-1",
        proposal={
            "objects": [],
            "abstain_reason": "insufficient_semantic_context",
        },
    )

    assert units == []


def test_model_order_cannot_override_source_order() -> None:
    fragments = [
        _fragment("frag-1", "Eerste volledige passage."),
        _fragment("frag-2", "Tweede volledige passage."),
    ]
    blocks = semantic_source_blocks(fragments)

    units = semantic_units_from_proposal(
        fragments,
        document_id="doc-1",
        proposal={
            "objects": [
                {
                    "spans": [
                        {
                            "block_id": blocks[1]["block_id"],
                            "start": 0,
                            "end": len(blocks[1]["text"]),
                        }
                    ]
                },
                {
                    "spans": [
                        {
                            "block_id": blocks[0]["block_id"],
                            "start": 0,
                            "end": len(blocks[0]["text"]),
                        }
                    ]
                },
            ]
        },
    )

    assert [unit["clean_text"] for unit in units] == [
        "Eerste volledige passage.",
        "Tweede volledige passage.",
    ]


def test_cross_section_merge_fails_closed() -> None:
    fragments = [
        _fragment("frag-1", "Eerste passage.", section="Diagnostiek"),
        _fragment("frag-2", "Tweede passage.", section="Behandeling"),
    ]
    blocks = semantic_source_blocks(fragments)

    with pytest.raises(SemanticPassageError, match="semantic_cross_section_merge"):
        semantic_units_from_proposal(
            fragments,
            document_id="doc-1",
            proposal={
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": blocks[0]["block_id"],
                                "start": 0,
                                "end": len(blocks[0]["text"]),
                            },
                            {
                                "block_id": blocks[1]["block_id"],
                                "start": 0,
                                "end": len(blocks[1]["text"]),
                            },
                        ]
                    }
                ]
            },
        )


def test_overlapping_spans_in_one_block_fail_closed() -> None:
    fragments = [_fragment("frag-1", "Bespreek samen de behandeling.")]
    block = semantic_source_blocks(fragments)[0]

    with pytest.raises(SemanticPassageError, match="semantic_span_overlap"):
        semantic_units_from_proposal(
            fragments,
            document_id="doc-1",
            proposal={
                "objects": [
                    {
                        "spans": [
                            {"block_id": block["block_id"], "start": 0, "end": 12},
                            {"block_id": block["block_id"], "start": 8, "end": 20},
                        ]
                    }
                ]
            },
        )


def test_invalid_proposed_type_fails_closed() -> None:
    fragments = [_fragment("frag-1", "Bespreek de behandeling.")]
    block = semantic_source_blocks(fragments)[0]

    with pytest.raises(SemanticPassageError, match="semantic_object_type_invalid"):
        semantic_units_from_proposal(
            fragments,
            document_id="doc-1",
            proposal={
                "objects": [
                    {
                        "spans": [
                            {
                                "block_id": block["block_id"],
                                "start": 0,
                                "end": len(block["text"]),
                            }
                        ],
                        "proposed_object_type": "diagnosis",
                    }
                ]
            },
        )


def test_unselected_source_block_remains_as_unclassified_coverage_passage() -> None:
    fragments = [
        _fragment("frag-a", "Gebruik behandeling X."),
        _fragment("frag-b", "Niet gebruiken bij patiënten met nierfalen."),
        _fragment("frag-c", "Controleer na vier weken."),
    ]
    blocks = semantic_source_blocks(fragments)

    units = semantic_units_from_proposal(
        fragments,
        document_id="doc-coverage",
        proposal={
            "objects": [
                {
                    "spans": [
                        {
                            "block_id": blocks[0]["block_id"],
                            "start": 0,
                            "end": len(blocks[0]["text"]),
                        }
                    ],
                    "proposed_object_type": "recommendation",
                },
                {
                    "spans": [
                        {
                            "block_id": blocks[2]["block_id"],
                            "start": 0,
                            "end": len(blocks[2]["text"]),
                        }
                    ],
                    "proposed_object_type": "recommendation",
                },
            ],
            "abstain_reason": None,
        },
    )

    assert [unit["clean_text"] for unit in units] == [
        "Gebruik behandeling X.",
        "Niet gebruiken bij patiënten met nierfalen.",
        "Controleer na vier weken.",
    ]
    omitted = units[1]
    assert omitted["object_type"] == "unclassified"
    assert omitted["proposed_object_type"] == "unclassified"
    assert omitted["source_fragment_ids"] == ["frag-b"]
    assert omitted["semantic_passage"]["source_bound"] is True


def test_partial_source_selection_preserves_prefix_and_suffix_as_coverage() -> None:
    text = "Voorafgaande context. Gebruik behandeling X. Afrondende context."
    fragments = [_fragment("frag-1", text)]
    block = semantic_source_blocks(fragments)[0]
    selected = "Gebruik behandeling X."
    start = block["text"].index(selected)
    end = start + len(selected)

    units = semantic_units_from_proposal(
        fragments,
        document_id="doc-partial",
        proposal={
            "objects": [
                {
                    "spans": [
                        {
                            "block_id": block["block_id"],
                            "start": start,
                            "end": end,
                        }
                    ],
                    "proposed_object_type": "recommendation",
                }
            ],
            "abstain_reason": None,
        },
    )

    assert [unit["clean_text"] for unit in units] == [
        "Voorafgaande context.",
        "Gebruik behandeling X.",
        "Afrondende context.",
    ]
    assert units[0]["proposed_object_type"] == "unclassified"
    assert units[2]["proposed_object_type"] == "unclassified"


def test_full_source_selection_does_not_create_coverage_duplicate() -> None:
    fragments = [_fragment("frag-1", "Gebruik behandeling X.")]
    block = semantic_source_blocks(fragments)[0]

    units = semantic_units_from_proposal(
        fragments,
        document_id="doc-full",
        proposal={
            "objects": [
                {
                    "spans": [
                        {
                            "block_id": block["block_id"],
                            "start": 0,
                            "end": len(block["text"]),
                        }
                    ],
                    "proposed_object_type": "recommendation",
                }
            ],
            "abstain_reason": None,
        },
    )

    assert len(units) == 1
    assert units[0]["clean_text"] == "Gebruik behandeling X."
