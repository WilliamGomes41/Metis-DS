"""Shared console header: one line on wide screens, readable name and roles.

Release-control evidence: presentation-only change to the logged-in header
(scope/belofte, slop); routes and login are exercised unchanged (toegang);
these executable regressions are the release proof (releasebewijs).
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient
import pytest


pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.pure_function
def test_header_css_keeps_nav_on_one_line_until_it_cannot_fit() -> None:
    css = (ROOT / "assets/brand/console.css").read_text(encoding="utf-8")
    header = css.split("/* Shared header readability")[1]
    assert ".home-tile" not in header
    assert re.search(r"\.rooms\s*\{[^}]*flex:\s*1 1 auto;\s*flex-wrap:\s*nowrap", header)
    assert re.search(r"\.who\s*\{[^}]*min-width:\s*0", header)
    assert re.search(r"\.who-name,\s*\.who-roles\s*\{\s*overflow-wrap:\s*anywhere", header)
    assert re.search(r"\.rooms a,\s*\.rooms button\s*\{[^}]*white-space:\s*nowrap", header)
    narrow = re.search(r"@media \(max-width: 1359px\)\s*\{(.*?)\n\}", header, re.S)
    assert narrow and "flex-basis: 100%; flex-wrap: wrap" in narrow.group(1)
    assert re.search(r"\.theme-toggle\s*\{[^}]*width:\s*44px;[^}]*height:\s*44px", header)
    assert re.search(r'html\[data-theme="dark"\] \.theme-icon-sun\s*\{\s*display:\s*block', header)


def test_header_shows_name_then_roles_and_an_icon_theme_toggle(production_console, production_app) -> None:
    console = production_console()
    console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher", "reviewer"),
        display_name="Anne Onderzoeker",
    )
    client = TestClient(production_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    html = client.get("/ingest").text
    who = re.search(r'<div class="who">(.*?)</div>', html, re.S).group(1)
    assert '<span class="who-name">Anne Onderzoeker</span>' in who
    assert '<span class="sr-only">rollen: </span>researcher · reviewer' in who
    toggle = re.search(r'<button class="theme-toggle"[^>]*>(.*?)</button>', html, re.S)
    assert 'aria-label="Wissel tussen lichte en donkere modus"' in toggle.group(0)
    assert 'title="Donkere modus"' in toggle.group(0)
    assert "theme-icon-moon" in toggle.group(1) and "theme-icon-sun" in toggle.group(1)
    assert "button.title = dark ? 'Lichte modus' : 'Donkere modus';" in html
