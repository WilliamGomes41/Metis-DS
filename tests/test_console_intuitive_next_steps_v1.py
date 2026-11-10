"""Empty console screens name the next step; Inleveren asks for colleagues when needed."""
from __future__ import annotations

from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]

ROOT = Path(__file__).resolve().parents[1]


def _client(production_console, production_app) -> TestClient:
    console = production_console()
    console.create_account("researcher.anne", "anne-secret",
                           roles=("researcher", "reviewer", "publisher"), display_name="Anne")
    client = TestClient(production_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    return client


def test_empty_screens_name_the_next_step(production_console, production_app) -> None:
    client = _client(production_console, production_app)
    documents = client.get("/tree").text
    assert 'Nog geen documenten. <a href="/ingest">Lever een document in</a> om te beginnen.' in documents
    assert "<span>0 documenten</span>" in documents
    publish = client.get("/publish").text
    assert "Een ingeleverd document verschijnt hier; publiceren kan zodra de review is afgerond." in publish
    review = client.get("/review").text
    assert review.count('class="review-empty"') == 1
    assert "Geen aan jou toegewezen reviewdocumenten." in review
    assert "geen uitvoerbare beoordelingen" not in review


def test_one_result_is_counted_in_the_singular() -> None:
    # The pager is shared by Documenten and Vorming; a browser pass showed "1 document".
    source = (ROOT / "src/operations_console_app.py").read_text()
    assert '{"document" if len(matches) == 1 else "documenten"}' in source


def test_ingest_asks_for_colleagues_only_when_the_choice_needs_them(production_console, production_app) -> None:
    html = _client(production_console, production_app).get("/ingest").text
    # Markup and field names stay as they were; the page script decides visibility.
    assert '<div id="review-colleagues">' in html
    assert html.count('name="review_reviewers"') == 1
    assert "colleagues.hidden = !chosen || alone;" in html
    assert "list.disabled = alone;" in html
    assert '''label.textContent = two ? "Kies twee collega's" : "Kies een collega";''' in html
    assert "help.hidden = !two;" in html


def test_settings_has_no_label_above_the_heading_and_groups_links(production_console, production_app) -> None:
    html = _client(production_console, production_app).get("/settings").text
    assert 'class="eyebrow"' not in html
    assert html.count('<div class="doc-list settings-links">') == 3
    assert re.findall(r"<h2>(.*?)</h2>", html) == ["Inzicht", "Beheer", "Uitleg"]


def test_press_feedback_is_additive_and_respects_reduced_motion() -> None:
    css = (ROOT / "assets/brand/console.css").read_text()
    block = css.split("/* Interaction feedback and next-step links", 1)[1]
    assert css.count("/* Interaction feedback and next-step links") == 1
    motion = re.search(r"@media \(prefers-reduced-motion: no-preference\) \{(.*?)\n\}", block, re.S).group(1)
    assert "transform: scale(0.97)" in motion and "120ms" in motion
    assert "scale(" not in block.replace(motion, "")
    assert ".home-tile" not in block and ".topbar" not in block and ".rooms" not in block


def test_account_roles_are_one_labelled_group_with_unchanged_values(production_console, production_app) -> None:
    html = _client(production_console, production_app).get("/accounts").text
    group = re.search(r'<fieldset class="account-roles">(.*?)</fieldset>', html, re.S).group(1)
    assert "<legend>Rollen</legend>" in group
    assert re.findall(r'<input type="checkbox" name="roles" value="(\w+)"', group) == ["researcher", "reviewer", "publisher"]
    assert group.count('class="choice"') == 3
    assert '<form method="post" action="/accounts" class="account-new">' in html
    assert '<button class="btn-secondary" type="submit">Rollen wijzigen</button>' in html
