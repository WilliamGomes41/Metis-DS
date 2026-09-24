"""VSA F1 contract tests: passage-formation policy + source authority."""
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
    assert row["source_fragment_ids"] == [
        "primary-fragment",
        "summary-fragment",
    ]
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
    assert rows[0]["source_fragment_ids"] == ["fragment-a", "fragment-b"]
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
    assert row["source_fragment_ids"] == [
        "primary-fragment",
        "summary-fragment",
    ]
    authority = row["metadata"]["source_occurrence_authority"]
    assert authority["principal_section_role"] == "primary"
    assert authority["alternate_occurrences"][0]["section_role"] == "summary"
