"""Inleveren reads as one column with one clear reviewer choice."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def test_ingest_form_has_sections_choice_row_and_alone_hides_colleagues(production_console, production_app) -> None:
    console = production_console()
    console.create_account("researcher.anne", "anne-secret", roles=("researcher", "reviewer"), display_name="Anne")
    client = TestClient(production_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    html = client.get("/ingest").text
    assert '<section class="room ingest-room">' in html
    assert [h for h in re.findall(r"<h2>(.*?)</h2>", html)] == ["Bron", "Document", "Reviewers"]
    row = re.search(r'<div class="choice-row">(.*?)</div>', html, re.S).group(1)
    assert row.count('class="choice"') == 4
    for option in ("uploader_sole", "one_other", "uploader_and_other", "two_others"):
        assert f'name="review_option" value="{option}" required' in row
    four_eyes = re.search(r'<fieldset id="review-four-eyes">(.*?)</fieldset>', html, re.S).group(1)
    assert four_eyes.count('class="choice"') == 2
    assert '<div id="review-colleagues">' in html
    assert 'aria-describedby="review-reviewers-help"' in html
    assert "list.disabled = alone;" in html
    assert '<div class="form-submit">' in html
