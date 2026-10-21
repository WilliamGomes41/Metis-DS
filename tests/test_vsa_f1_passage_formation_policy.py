"""VSA F1 contract tests: passage-formation policy + source authority."""

# release-control-evidence: kwaliteit
from __future__ import annotations

import pytest

from src.context_aware_split_v1 import split_context_aware_units
from src.passage_formation_policy_v1 import (
    DETERMINISTIC_MODE,
    REASON_AUTHORITATIVE_TREE,
    REASON_EXPLICIT_ROLLBACK,
    REASON_SEMANTIC_FREE_TEXT,
    SEMANTIC_MODE,
    STRATEGY_DETERMINISTIC,
    STRATEGY_SEMANTIC,
    PassageFormationPolicyError,
    resolve_passage_formation_strategy,
)
from src.semantic_transform_generic_v1 import transform
from src.source_occurrence_authority_v1 import (
    REASON_AUTHORITATIVE_SECTION,
    prefer_authoritative_exact_occurrences,
)


PASSAGE = "Gebruik de afgesproken interventie."


def _fragment(
    fragment_id: str,
    section_path: list[str],
    *,
    text: str = PASSAGE,
    ordinal: int = 1,
) -> dict:
    return {
        "fragment_id": fragment_id,
        "clean_text": text,
        "raw_text": text,
        "heading": None,
        "section_path": section_path,
        "source_locator": {
            "locator_type": "web_line_range",
            "locator_value": f"lines:{ordinal}-{ordinal};p:{ordinal}",
        },
    }


def _unit(
    object_id: str,
    fragment_id: str,
    section_path: list[str],
    text: str = PASSAGE,
) -> dict:
    return {
        "object_id": object_id,
        "object_type": "unclassified",
        "text": text,
        "clean_text": text,
        "source_fragment_ids": [fragment_id],
        "section_path": section_path,
        "heading": section_path[-1] if section_path else None,
        "review_track": "clinical",
        "relations": [],
        "confirmed_relations": [],
    }


def test_policy_keeps_authoritative_tree_deterministic_even_in_semantic_mode() -> None:
    decision = resolve_passage_formation_strategy(
        content_kind="boom",
        deployment_mode=SEMANTIC_MODE,
    )
    assert decision.strategy == STRATEGY_DETERMINISTIC
    assert decision.reason == REASON_AUTHORITATIVE_TREE


def test_policy_routes_unstructured_prose_to_semantic_when_enabled() -> None:
    decision = resolve_passage_formation_strategy(
        content_kind="html",
        deployment_mode=SEMANTIC_MODE,
    )
    assert decision.strategy == STRATEGY_SEMANTIC
    assert decision.reason == REASON_SEMANTIC_FREE_TEXT


def test_policy_keeps_explicit_deterministic_rollback() -> None:
    decision = resolve_passage_formation_strategy(
        content_kind="pdf",
        deployment_mode=DETERMINISTIC_MODE,
    )
    assert decision.strategy == STRATEGY_DETERMINISTIC
    assert decision.reason == REASON_EXPLICIT_ROLLBACK


def test_policy_rejects_unknown_mode_instead_of_guessing() -> None:
    with pytest.raises(PassageFormationPolicyError, match="passage_formation_mode_invalid"):
        resolve_passage_formation_strategy(
            content_kind="html",
            deployment_mode="automatic-fallback",
        )


def test_summary_first_primary_later_prefers_primary_and_keeps_alternate() -> None:
    summary = _unit(
        "doc-summary",
        "summary-fragment",
        ["Richtlijn", "Samenvatting", "Aanbevelingen"],
    )
    primary = _unit(
        "doc-primary",
        "primary-fragment",
        ["Richtlijn", "2 Aanbevelingen"],
    )

    rows = prefer_authoritative_exact_occurrences([summary, primary])

    assert len(rows) == 1
    row = rows[0]
    assert row["object_id"] == "doc-primary"
    assert row["section_path"] == ["Richtlijn", "2 Aanbevelingen"]
    assert row["source_fragment_ids"] == ["primary-fragment"]
    authority = row["metadata"]["source_occurrence_authority"]
    assert authority["principal_section_role"] == "primary"
    assert authority["reason"] == REASON_AUTHORITATIVE_SECTION
    assert authority["alternate_occurrences"] == [
        {
            "source_fragment_ids": ["summary-fragment"],
            "section_role": "summary",
            "section_path": ["Richtlijn", "Samenvatting", "Aanbevelingen"],
        }
    ]


def test_summary_only_is_retained_without_inventing_an_alternate() -> None:
    summary = _unit(
        "doc-summary",
        "summary-fragment",
        ["Richtlijn", "Samenvatting"],
    )
    rows = prefer_authoritative_exact_occurrences([summary])
    assert rows == [summary]


def test_exact_primary_duplicates_collapse_without_fuzzy_matching() -> None:
    first = _unit(
        "doc-a",
        "fragment-a",
        ["Richtlijn", "2 Aanbevelingen"],
    )
    second = _unit(
        "doc-b",
        "fragment-b",
        ["Richtlijn", "2 Aanbevelingen"],
    )
    different = _unit(
        "doc-c",
        "fragment-c",
        ["Richtlijn", "2 Aanbevelingen"],
        text="Gebruik de afgesproken interventie bij ouderen.",
    )

    rows = prefer_authoritative_exact_occurrences([first, second, different])

    assert len(rows) == 2
    assert rows[0]["object_id"] == "doc-a"
    assert rows[0]["source_fragment_ids"] == ["fragment-a"]
    assert rows[1]["object_id"] == "doc-c"


def test_deterministic_splitter_routes_exact_duplicates_through_source_authority() -> None:
    summary = _fragment(
        "summary-fragment",
        ["Richtlijn", "Samenvatting", "Aanbevelingen"],
        ordinal=1,
    )
    primary = _fragment(
        "primary-fragment",
        ["Richtlijn", "2 Aanbevelingen"],
        ordinal=2,
    )

    rows = split_context_aware_units(
        [summary, primary],
        document_id="doc-authority",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["object_id"] == "doc-authority-primary-fragment"
    assert row["section_path"] == ["Richtlijn", "2 Aanbevelingen"]
    assert row["source_fragment_ids"] == ["primary-fragment"]
    authority = row["metadata"]["source_occurrence_authority"]
    assert authority["principal_section_role"] == "primary"
    assert authority["alternate_occurrences"][0]["section_role"] == "summary"


def test_transform_persists_only_closed_f1_system_evidence() -> None:
    raw = [
        {
            "fragment_id": "primary-fragment",
            "fragment_hash": "a" * 64,
            "raw_text": PASSAGE,
            "clean_text": PASSAGE,
            "source_page": None,
            "bbox": None,
            "source_locator": {
                "locator_type": "web_line_range",
                "locator_value": "lines:2-2;p:2",
            },
        },
        {
            "fragment_id": "summary-fragment",
            "fragment_hash": "b" * 64,
            "raw_text": PASSAGE,
            "clean_text": PASSAGE,
            "source_page": None,
            "bbox": None,
            "source_locator": {
                "locator_type": "web_line_range",
                "locator_value": "lines:1-1;p:1",
            },
        },
    ]
    manifest = {
        "canonical_source": {
            "source_id": "source-test",
            "title": "Test source",
            "publisher": "V&VN",
            "source_url": "https://example.org/test",
            "source_type": "html",
            "source_level": 1,
            "canonicality": "canonical",
            "source_checksum": None,
            "checksum_algorithm": "sha256",
            "integrity_status": "binary_unavailable",
            "publication_date": "2026-09-24",
            "version": "1.0",
        }
    }
    formation = {
        "policy_version": "passage-formation-policy-v1.0.0",
        "strategy": "deterministic",
        "reason": "explicit_operational_rollback",
    }
    authority = {
        "version": "source-occurrence-authority-v1.0.0",
        "principal_section_role": "primary",
        "reason": "authoritative_section_preferred",
        "alternate_occurrences": [
            {
                "source_fragment_ids": ["summary-fragment"],
                "section_role": "summary",
                "section_path": ["Richtlijn", "Samenvatting", "Aanbevelingen"],
            }
        ],
    }
    spec = {
        "spec_version": "console-ingest-1.0",
        "document_id": "doc-test",
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": ["test"],
        "objects": [
            {
                "object_id": "doc-test-primary",
                "object_type": "unclassified",
                "text": PASSAGE,
                "clean_text": PASSAGE,
                "source_fragment_ids": ["primary-fragment"],
                "section_path": ["Richtlijn", "2 Aanbevelingen"],
                "review_track": "clinical",
                "metadata": {
                    "passage_formation": formation,
                    "source_occurrence_authority": authority,
                    "untrusted_extra": {"must": "not persist"},
                },
            }
        ],
    }

    row = transform(spec, manifest, raw)[0]

    assert row["metadata"]["passage_formation"] == formation
    assert row["metadata"]["source_occurrence_authority"] == authority
    assert "untrusted_extra" not in row["metadata"]
    assert [
        ref["raw_object_id"]
        for ref in row["provenance"]["source_fragments"]
    ] == ["primary-fragment"]



def test_equal_primary_authority_prefers_direct_occurrence_over_reconstructed_duplicate() -> None:
    reconstructed = _unit(
        "doc-reconstructed",
        "fragment-a",
        ["Richtlijn", "2 Aanbevelingen"],
    )
    reconstructed["source_fragment_ids"] = ["fragment-a", "fragment-b"]
    direct = _unit(
        "doc-direct",
        "fragment-c",
        ["Richtlijn", "2 Aanbevelingen"],
    )

    rows = prefer_authoritative_exact_occurrences([reconstructed, direct])

    assert len(rows) == 1
    row = rows[0]
    assert row["object_id"] == "doc-direct"
    assert row["source_fragment_ids"] == ["fragment-c"]
    authority = row["metadata"]["source_occurrence_authority"]
    assert authority["principal_section_role"] == "primary"
    assert authority["alternate_occurrences"] == [
        {
            "source_fragment_ids": ["fragment-a", "fragment-b"],
            "section_role": "primary",
            "section_path": ["Richtlijn", "2 Aanbevelingen"],
        }
    ]



def test_admission_paragraph_context_stops_at_heading_boundary() -> None:
    from src.admission_gate_v1 import candidate_from_object

    heading_a = {
        "object_id": "h-a",
        "object_type": "heading",
        "content": {"clean_text": "1 Context"},
        "structure": {"section_path": ["Richtlijn", "1 Context"]},
        "provenance": {"source_fragments": []},
    }
    previous = {
        "object_id": "p-a",
        "object_type": "unclassified",
        "content": {"clean_text": "Wanneer de cliënt ouder is, geldt extra aandacht."},
        "structure": {"section_path": ["Richtlijn", "1 Context"]},
        "proposed_object_type": "condition",
        "provenance": {"source_fragments": []},
    }
    heading_b = {
        "object_id": "h-b",
        "object_type": "heading",
        "content": {"clean_text": "2 Aanbevelingen"},
        "structure": {"section_path": ["Richtlijn", "2 Aanbevelingen"]},
        "provenance": {"source_fragments": []},
    }
    candidate = {
        "object_id": "rec-b",
        "object_type": "unclassified",
        "content": {"clean_text": "De werkgroep adviseert de verpleegkundige dit te gebruiken."},
        "structure": {"section_path": ["Richtlijn", "2 Aanbevelingen"]},
        "proposed_object_type": "recommendation",
        "provenance": {"source_fragments": []},
    }

    record = candidate_from_object(
        candidate,
        objects=[heading_a, previous, heading_b, candidate],
        index=3,
        document_version="1.0",
        source_hash="a" * 64,
    )

    assert record["context_before"] == ""
    assert record["previous_paragraph"] == ""
