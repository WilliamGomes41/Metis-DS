"""T7: selection decides, only the materialiser creates a KnowledgeCandidate.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import pytest

from src.admission_gate_v1 import (
    admission_of,
    apply_admission_gate,
    is_inhoudelijk_candidate,
)
from src.candidate_eligibility_v1 import assess_candidate_eligibility
from src.context_aware_split_v1 import split_context_aware_units
from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
from src.knowledge_path_v1 import content_reviewable
from src.semantic_passage_v1 import (
    semantic_source_blocks,
    semantic_units_from_proposal,
    source_coverage_records,
)
from src.semantic_transform_generic_v1 import transform


_CANONICAL_OBJECT_KEYS = {
    "object_id",
    "object_type",
    "clean_text",
    "text",
    "review_track",
    "semantic_passage",
    "metadata",
    "admission",
}


def _fragment(fragment_id: str, text: str) -> dict:
    return {
        "fragment_id": fragment_id,
        "fragment_hash": f"hash-{fragment_id}",
        "raw_text": text,
        "clean_text": text,
        "section_path": ["Behandeling"],
        "source_locator": {
            "locator_type": "web_line_range",
            "locator_value": "lines:1-1",
        },
    }


def _proposal(block: dict, *, proposed_object_type: str = "recommendation") -> dict:
    return {
        "objects": [
            {
                "spans": [
                    {
                        "block_id": block["block_id"],
                        "start": 0,
                        "end": len(block["text"]),
                    }
                ],
                "proposed_object_type": proposed_object_type,
            }
        ],
        "relations": [
            {
                "source_spans": [
                    {
                        "block_id": block["block_id"],
                        "start": 0,
                        "end": len(block["text"]),
                    }
                ],
                "relation_type": "elaborates",
                "target_spans": [
                    {
                        "block_id": block["block_id"],
                        "start": 0,
                        "end": len(block["text"]),
                    }
                ],
                "evidence_spans": [
                    {
                        "block_id": block["block_id"],
                        "start": 0,
                        "end": len(block["text"]),
                    }
                ],
            }
        ],
        "abstain_reason": None,
    }


def _manifest() -> dict:
    return {
        "canonical_source": {
            "source_id": "source-t7",
            "title": "T7 source",
            "publisher": "V&VN",
            "source_url": "https://example.org/t7",
            "source_type": "pdf",
            "source_level": 1,
            "canonicality": "canonical",
            "source_checksum": "a" * 64,
            "checksum_algorithm": "sha256",
            "integrity_status": "verified",
            "publication_date": "2026-10-07",
            "version": "1.0",
        }
    }


def _gate(rows: list[dict], fragments: list[dict]) -> list[dict]:
    return apply_admission_gate(
        rows,
        klasse="richtlijn",
        fragments=fragments,
        document_version="1.0",
        source_hash="a" * 64,
    )


def test_selector_returns_a_decision_and_not_a_knowledge_candidate() -> None:
    text = "Bespreek met de patiënt welke behandeling het beste past."
    fragments = [_fragment("frag-1", text)]
    block = semantic_source_blocks(fragments)[0]
    decisions = semantic_units_from_proposal(
        fragments,
        document_id="doc-t7",
        proposal=_proposal(block),
    )

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["decision_kind"] == "semantic_selection"
    assert decision["selection_origin"] == "proposal_selected"
    assert decision["proposed_object_type"] == "recommendation"
    assert decision["spans"] == [
        {"block_id": block["block_id"], "start": 0, "end": len(block["text"])}
    ]
    assert decision["context"] == []
    assert decision["relations"] == [_proposal(block)["relations"][0]]
    assert "relation_id" not in decision["relations"][0]
    assert "target_object_id" not in decision["relations"][0]
    assert _CANONICAL_OBJECT_KEYS.isdisjoint(decision)
    assert "_identity_material" not in decision
    assert materialise_knowledge_candidates(
        decisions, document_id="doc-t7", fragments=fragments
    )[0]["object_id"] not in {row.get("object_id") for row in decisions}


def test_only_the_materialiser_assigns_identity_and_exact_source_text() -> None:
    text = "Bespreek met de patiënt welke behandeling het beste past."
    fragments = [_fragment("frag-1", text)]
    block = semantic_source_blocks(fragments)[0]
    decisions = semantic_units_from_proposal(
        fragments,
        document_id="doc-t7",
        proposal=_proposal(block),
    )

    first = materialise_knowledge_candidates(
        decisions, document_id="doc-t7", fragments=fragments
    )
    second = materialise_knowledge_candidates(
        decisions, document_id="doc-t7", fragments=fragments
    )

    assert len(first) == 1
    candidate = first[0]
    assert candidate["object_id"] == second[0]["object_id"]
    assert candidate["object_id"].startswith("doc-t7-sem-")
    assert "-semcov-" not in candidate["object_id"]
    assert candidate["clean_text"] == text
    assert candidate["text"] == text
    assert candidate["semantic_passage"]["source_bound"] is True
    assert candidate["semantic_passage"]["selection_origin"] == "proposal_selected"
    assert candidate["semantic_passage"]["spans"] == decisions[0]["spans"]
    assert candidate["relations"] == []
    assert is_inhoudelijk_candidate(candidate) is True
    assert content_reviewable(candidate) is False

    mutated = dict(decisions[0])
    mutated["source_text"] = "Een geparafraseerde zin."
    with pytest.raises(ValueError, match="materialisation_text_mismatch"):
        materialise_knowledge_candidates([mutated], document_id="doc-t7", fragments=fragments)

    stamped = dict(decisions[0])
    stamped["object_id"] = "doc-t7-sem-already"
    with pytest.raises(ValueError, match="selection_decision_is_not_a_candidate"):
        materialise_knowledge_candidates([stamped], document_id="doc-t7", fragments=fragments)


def test_abstain_coverage_is_not_a_knowledge_candidate() -> None:
    fragments = [_fragment("frag-1", "Een moeilijk interpreteerbare passage.")]
    proposal = {"objects": [], "abstain_reason": "insufficient_semantic_context"}
    decisions = semantic_units_from_proposal(
        fragments, document_id="doc-t7", proposal=proposal
    )
    coverage = source_coverage_records(
        fragments, document_id="doc-t7", proposal=proposal
    )

    assert decisions == []
    assert materialise_knowledge_candidates(
        decisions, document_id="doc-t7", fragments=fragments
    ) == []
    assert len(coverage) == 1
    assert coverage[0]["object_id"].startswith("doc-t7-semcov-")
    assert is_inhoudelijk_candidate(coverage[0]) is False


def test_deterministic_fragment_cannot_become_a_candidate_by_classification_or_admission() -> None:
    text = "Bespreek met de patiënt welke behandeling het beste past."
    fragments = [_fragment("p1", text)]
    [spec_item] = [
        row for row in split_context_aware_units(fragments, document_id="doc-t7")
        if row.get("object_type") != "heading"
    ]
    spec_item["proposed_object_type"] = "definition"
    assert "-sem-" not in spec_item["object_id"]
    with pytest.raises(ValueError, match="materialiser_requires_selection_decision"):
        materialise_knowledge_candidates([spec_item], document_id="doc-t7", fragments=fragments)

    spec = {
        "spec_version": "t7",
        "document_id": "doc-t7",
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": ["test"],
        "objects": [spec_item],
    }
    [row] = transform(spec, _manifest(), fragments)
    row.setdefault("metadata", {})
    row["metadata"]["candidate_eligibility"] = {
        "version": "candidate-eligibility-v1.0.0",
        "eligible": True,
        "reason": "explicit_type_proposal",
        "source": "deterministic",
    }
    assert assess_candidate_eligibility(row).eligible is False
    [gated] = _gate([row], fragments)
    assert assess_candidate_eligibility(gated).eligible is False
    assert admission_of(gated) == {}
    assert is_inhoudelijk_candidate(gated) is False
    assert content_reviewable(gated) is False
    assert "-sem-" not in gated["object_id"]


def test_same_source_has_one_semantic_candidate_and_a_separate_deterministic_row() -> None:
    text = "Bespreek met de patiënt welke behandeling het beste past."
    fragments = [_fragment("p1", text)]
    block = semantic_source_blocks(fragments)[0]
    decisions = semantic_units_from_proposal(
        fragments,
        document_id="doc-t7",
        proposal=_proposal(block, proposed_object_type="definition"),
    )
    [candidate] = materialise_knowledge_candidates(
        decisions, document_id="doc-t7", fragments=fragments
    )
    [deterministic] = [
        row for row in split_context_aware_units(fragments, document_id="doc-t7")
        if row.get("clean_text") == text
    ]

    assert candidate["clean_text"] == deterministic["clean_text"] == text
    assert candidate["object_id"] != deterministic["object_id"]
    assert candidate["object_id"].startswith("doc-t7-sem-")
    assert is_inhoudelijk_candidate(candidate) is True
    assert is_inhoudelijk_candidate(deterministic) is False


def test_forged_identity_material_cannot_change_candidate_identity() -> None:
    text = "Bespreek met de patiënt welke behandeling het beste past."
    fragments = [_fragment("frag-1", text)]
    block = semantic_source_blocks(fragments)[0]
    decisions = semantic_units_from_proposal(
        fragments,
        document_id="doc-t7",
        proposal=_proposal(block),
    )
    [plain] = materialise_knowledge_candidates(
        decisions, document_id="doc-t7", fragments=fragments
    )
    forged = dict(decisions[0])
    forged["_identity_material"] = "forged-selector-identity"
    [other] = materialise_knowledge_candidates(
        [forged], document_id="doc-t7", fragments=fragments
    )
    assert other["object_id"] == plain["object_id"]


def test_changed_ordered_spans_change_identity_despite_forged_material() -> None:
    fragments = [
        _fragment("frag-1", "Eerste volledige passage."),
        _fragment("frag-2", "Tweede volledige passage."),
    ]
    blocks = semantic_source_blocks(fragments)

    def decision(block: dict) -> dict:
        return {
            "decision_kind": "semantic_selection",
            "selection_origin": "proposal_selected",
            "spans": [
                {"block_id": block["block_id"], "start": 0, "end": len(block["text"])}
            ],
            "source_text": block["text"],
            "source_fragment_ids": [block["block_id"]],
            "section_path": ["Behandeling"],
            "_identity_material": "same-forged-material",
        }

    left = materialise_knowledge_candidates(
        [decision(blocks[0])], document_id="doc-t7", fragments=fragments
    )[0]["object_id"]
    right = materialise_knowledge_candidates(
        [decision(blocks[1])], document_id="doc-t7", fragments=fragments
    )[0]["object_id"]
    assert left != right
    assert left.startswith("doc-t7-sem-")
    assert right.startswith("doc-t7-sem-")
