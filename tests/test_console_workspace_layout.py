"""Workspace layout: wide white canvas, Water-light edges only, short room copy."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole

ROOT = Path(__file__).resolve().parents[1]


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def test_css_drops_a4_shell_and_keeps_water_light_edges() -> None:
    css = (ROOT / "assets/brand/console.css").read_text(encoding="utf-8")
    assert "max-width: 1120px" not in css
    assert re.search(r"\.shell\s*\{[^}]*max-width:\s*none", css)
    assert re.search(r"\.canvas\s*\{[^}]*background:\s*var\(--wit\)", css)
    assert re.search(r"body\s*\{[^}]*background:\s*#EAF8F8", css)
    assert not re.search(r"body\s*\{[^}]*background:\s*#E23100", css)
    assert not re.search(r"body\s*\{[^}]*background:\s*#000000", css)
    assert not re.search(r"\.metis-mark-frame\s*\{[^}]*background:\s*var\(--zwart\)", css)
    assert re.search(r"\.metis-mark-frame\s*\{[^}]*background:\s*transparent", css)
    assert re.search(r"\.topbar\s*\{[^}]*margin:\s*0 0 48px", css)
    assert re.search(r"\.login-brand\s*\{[^}]*margin:\s*0 0 2\.75rem", css)
    source = (ROOT / "src/operations_console_app.py").read_text(encoding="utf-8")
    assert 'class="canvas"' in source
    assert 'width="96"' in source


def test_rooms_use_one_short_lead_not_stacked_protocol_prose(tmp_path: Path) -> None:
    console = _console(tmp_path)
    console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher", "reviewer", "publisher"),
        display_name="Anne Onderzoeker",
    )
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    ingest = client.get("/ingest").text
    lower = ingest.lower()
    assert 'class="canvas"' in ingest
    assert 'src="/brand/metis-mark.jpg"' in ingest
    assert "onderzoekerspad" in lower
    assert "continentie" in lower
    assert "daarna:" not in lower
    assert "verwacht:" not in lower
    login = client.get("/login").text.lower()
    assert "geen open registratie" in login
    assert 'src="/brand/metis-wordmark.jpg"' in login
    primary_login = login.split("<details")[0]
    assert "geen gedeelde login" not in primary_login
    publish = client.get("/publish").text.lower()
    assert "publiceren" in publish
    assert "geblokkeerd" in publish
    accounts = client.get("/accounts").text.lower()
    assert "accounts" in accounts
