"""Documenten reads as compact rows with a status label and one column of actions."""
from __future__ import annotations

import re
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]

CSS = (Path(__file__).resolve().parents[1] / "assets" / "brand" / "console.css").read_text(encoding="utf-8")
BLOCK = CSS[CSS.index("/* Documenten (docs/change-contracts/console-documents-readability.md)"):]


def _pdf() -> bytes:
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Eenzaamheid bij ouderen", fontsize=14)
        page.insert_text((72, 110), "Bespreek met de oudere welke contacten steun bieden.", fontsize=11)
        return pdf.tobytes()


def _documents_page(production_console, production_app):
    console = production_console()
    console.create_account("anne", "anne-secret-123456", roles=("researcher", "reviewer"), display_name="Anne")
    rob = console.create_account("rob", "rob-secret-1234567", roles=("reviewer",), display_name="Rob")
    client = TestClient(production_app(console), base_url="https://testserver")
    assert client.post("/login", data={"username": "anne", "password": "anne-secret-123456"}).status_code == 200
    form = dict(ingest_kind="new", title="Eenzaamheid bij ouderen", version="1.2", date="2026-09-05",
                class_="richtlijn", family="Eenzaamheid", named_reviewers=[rob["account_id"]],
                review_option="one_other", review_reviewers=[rob["account_id"]])
    assert client.post("/ingest", data=form, files={"file": ("e.pdf", _pdf(), "application/pdf")}).status_code < 400
    return client


def _visible_text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def test_documents_rows_show_status_aligned_actions_and_closed_delete(production_console, production_app) -> None:
    client = _documents_page(production_console, production_app)
    html = client.get("/tree").text
    assert '<section class="room" id="documents">' in html
    row = re.search(r'<details class="doc-card document-disclosure document-row">(.*?)</details>\s*</div>', html, re.S).group(1)
    summary = re.search(r"<summary>(.*?)</summary>", row, re.S).group(1)
    assert '<span class="doc-title">Eenzaamheid bij ouderen</span>' in summary
    assert '<span class="meta">Versie 1.2 · richtlijn</span>' in summary
    assert '<span class="document-status" data-tone="warn">' in summary
    assert "Bronselectie" in row and "/source-selection?document=" in row
    labels = re.findall(r'<h3 class="document-action-label">(.*?)</h3>', row)
    assert labels == ["Onderwerp", "Klasse", "Diagnose"]
    assert "Nu: <b>Eenzaamheid</b>" in row and "Nu: <b>richtlijn</b>" in row
    assert "Deze wijziging vereist een nieuwe beoordeling" in row
    danger = re.search(r'<details class="document-danger">\s*<summary>Document verwijderen</summary>(.*?)</details>', row, re.S)
    assert danger and "Verwijder unpublished document" in danger.group(1)
    assert 'name="confirm_title"' in danger.group(1)
    assert "1 documenten" in html and "pagina 1 van 1" not in html


def test_documents_empty_search_offers_a_way_back(production_console, production_app) -> None:
    client = _documents_page(production_console, production_app)
    text = _visible_text(client.get("/tree?q=onvindbaar").text)
    assert "Geen documenten gevonden voor ‘onvindbaar’." in text
    assert "Wis zoekopdracht" in text


def test_documents_css_is_scoped_appended_and_fixes_checkbox_and_contrast() -> None:
    assert CSS.index("/* Task-only execution/evidence layout;") < CSS.index(BLOCK[:60])
    assert re.search(r"#documents input\[type=\"checkbox\"\] \{ min-width: 0;", BLOCK)
    assert "#documents .document-action {\n  display: grid;\n  grid-template-columns: 9rem minmax(0, 1fr);" in BLOCK
    assert "#documents .klasse-wijzigen-consequence { max-width: 65ch;" in BLOCK
    assert "min-height: 44px" in BLOCK
    assert "color: var(--review-red);" in BLOCK
    assert "#documents input::placeholder { color: var(--muted); font-weight: 400; opacity: 1; }" in BLOCK

    def luminance(hex_colour: str) -> float:
        channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    def ratio(a: str, b: str) -> float:
        high, low = sorted((luminance(a), luminance(b)), reverse=True)
        return (high + 0.05) / (low + 0.05)

    tokens = re.findall(r"--review-red: (#[0-9a-f]{6});", CSS)
    muted = re.findall(r"--muted: (#[0-9a-f]{6});", CSS)
    surfaces = re.findall(r"--wit: (#[0-9A-Fa-f]{6});", CSS)
    for ink, surface in zip(tokens[:2], ["#FFFFFF", surfaces[1]]):
        assert ratio(ink, surface) >= 4.5
    for ink, surface in zip(muted[:2], ["#FFFFFF", surfaces[1]]):
        assert ratio(ink, surface) >= 4.5
