"""Review room readability: spacing scale, neutral document bar, readable passage."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]

ROOT = Path(__file__).resolve().parents[1]


def _block() -> str:
    css = (ROOT / "assets/brand/console.css").read_text(encoding="utf-8")
    return css.split("/* Review room: space and hierarchy")[1]


@pytest.mark.pure_function
def test_review_block_defines_spacing_scale_and_quiet_document_bar() -> None:
    block = _block()
    for step in range(1, 9):
        assert f"--space-{step}:" in block
    bar = re.search(r"\.review-room > \.review-document-card \{(.*?)\}", block, re.S).group(1)
    assert "border: 1px solid var(--line)" in bar
    assert "rood" not in bar.lower()
    assert re.search(r"\.review-document-card \.doc-title \{ color: var\(--text\)", block)
    assert re.search(r"\.review-room \.banner\.warn \{[^}]*var\(--alert-bg\)", block)


@pytest.mark.pure_function
def test_passage_reads_as_text_and_choices_have_44px_targets() -> None:
    block = _block()
    passage = re.search(r"\[data-full-knowledge-passage\] \{(.*?)\}", block, re.S).group(1)
    assert "font-size: 1.25rem" in passage and "font-weight: 400" in passage and "max-width: 65ch" in passage
    assert re.search(r"\.review-room label\.check \{[^}]*min-height: 44px", block)
    assert "html[data-theme=\"dark\"] mark.broncontext-marked { color: #1f2933; }" in block


def test_trajectory_and_overview_use_room_layout(production_console, production_app) -> None:
    from fastapi.testclient import TestClient
    from src.review_participation_ui_v1 import filters
    console = production_console()
    assert filters(console, work="all", theme="").startswith('<form method="get" action="/review" class="review-filters">')
    console.create_account("rob", "rob-secret-pass", roles=("reviewer",), display_name="Rob")
    client = TestClient(production_app(console))
    client.post("/login", data={"username": "rob", "password": "rob-secret-pass"})
    html = client.get("/review").text
    assert '<p class="review-empty">Geen aan jou toegewezen reviewdocumenten.' in html
