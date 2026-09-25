"""D2b2-A PDF source hierarchy regression tests.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import pymupdf

from src.extract_pdf_v2 import (
    PARSER_VERSION,
    _update_heading_stack,
    extract,
)
from src.object_taxonomy_v1 import section_role_for_path


def _hierarchy_pdf(tmp_path):
    path = tmp_path / "eenzaamheid-hierarchy.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        rows = [
            ("Eenzaamheid onder ouderen", 18, "hebo"),
            ("Inhoud", 15, "hebo"),
            ("1. Samenvatting", 13, "hebo"),
            ("Dit is alleen de samenvatting.", 11, "helv"),
            ("2. Inleiding", 13, "hebo"),
            ("Dit is tekst uit de inleiding.", 11, "helv"),
            ("3. Vaststellen van eenzaamheid", 13, "hebo"),
            ("Dit hoofdstuk beschrijft vaststellen.", 11, "helv"),
            ("3.1 Screening", 13, "hebo"),
            ("Screening staat onder hoofdstuk drie.", 11, "helv"),
            ("4. Interventies", 13, "hebo"),
            ("Interventies is een nieuw hoofdhoofdstuk.", 11, "helv"),
        ]
        y = 60
        for text, size, font in rows:
            page.insert_text((72, y), text, fontsize=size, fontname=font)
            y += 34
        pdf.save(path)
    return path


def _by_text(rows):
    return {row["clean_text"]: row for row in rows}


def test_numbered_pdf_chapters_are_siblings_not_cumulative_ancestors(tmp_path) -> None:
    rows = extract(
        _hierarchy_pdf(tmp_path),
        document_id="doc-eenzaamheid",
        source_id="source-eenzaamheid",
    )
    by_text = _by_text(rows)
    root = "Eenzaamheid onder ouderen"

    assert by_text["Dit is alleen de samenvatting."]["section_path"] == [
        root,
        "1. Samenvatting",
    ]
    assert by_text["Dit is tekst uit de inleiding."]["section_path"] == [
        root,
        "2. Inleiding",
    ]
    assert "1. Samenvatting" not in by_text["Dit is tekst uit de inleiding."]["section_path"]
    assert "Inhoud" not in by_text["Dit is tekst uit de inleiding."]["section_path"]

    assert by_text["Screening staat onder hoofdstuk drie."]["section_path"] == [
        root,
        "3. Vaststellen van eenzaamheid",
        "3.1 Screening",
    ]
    assert by_text["Interventies is een nieuw hoofdhoofdstuk."]["section_path"] == [
        root,
        "4. Interventies",
    ]

    assert section_role_for_path(
        by_text["Dit is alleen de samenvatting."]["section_path"]
    ) == "summary"
    assert section_role_for_path(
        by_text["Dit is tekst uit de inleiding."]["section_path"]
    ) != "summary"


def test_equal_visual_heading_levels_replace_previous_siblings() -> None:
    stack = _update_heading_stack([], heading="Richtlijn", max_size=18)
    stack = _update_heading_stack(
        stack,
        heading="Achtergrond",
        max_size=13,
    )
    assert [text for _level, text, _size in stack] == [
        "Richtlijn",
        "Achtergrond",
    ]

    stack = _update_heading_stack(
        stack,
        heading="Methode",
        max_size=13,
    )
    assert [text for _level, text, _size in stack] == [
        "Richtlijn",
        "Methode",
    ]


def test_numbered_headings_without_document_title_remain_root_siblings() -> None:
    stack = _update_heading_stack([], heading="1. Inleiding", max_size=13)
    stack = _update_heading_stack(stack, heading="2. Methode", max_size=13)
    assert [text for _level, text, _size in stack] == ["2. Methode"]


def test_hierarchy_fix_preserves_source_bound_fragment_evidence(tmp_path) -> None:
    rows = extract(
        _hierarchy_pdf(tmp_path),
        document_id="doc-eenzaamheid",
        source_id="source-eenzaamheid",
    )

    assert PARSER_VERSION == "pdf-fragments-v2.2.0"
    assert [row["sequence"] for row in rows] == list(range(1, len(rows) + 1))
    assert all(row["parser_version"] == PARSER_VERSION for row in rows)
    assert all(row["raw_text"] == row["clean_text"] for row in rows)
    assert all(row["source_page"] == 1 for row in rows)
    assert all(row["bbox"] and len(row["bbox"]) == 4 for row in rows)
    assert all(
        row["source_locator"]["locator_value"].startswith("page:1;bbox:")
        for row in rows
    )
