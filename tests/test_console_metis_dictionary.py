"""Authenticated, read-only regressions for the Metis explanation page.

Release-control markers identify the route, login boundary and the deliberately
small console extension. They are test metadata, not live-release evidence.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole


pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def test_metis_dictionary_requires_login_and_renders_read_only_explanations(tmp_path: Path) -> None:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher",),
        display_name="Anne Onderzoeker",
    )
    client = TestClient(create_console_app(console))

    assert client.get("/over-console").status_code == 401

    login = client.post(
        "/login",
        data={"username": "researcher.anne", "password": "anne-secret"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    envelopes_before = console.list_envelopes()
    response = client.get("/over-console")

    assert response.status_code == 200
    assert 'href="/settings" aria-current="page">Instellingen' in response.text
    assert "Metis uitgelegd" in response.text
    assert "Zo werkt Metis" in response.text
    assert "Bron aanleveren" in response.text
    assert "Kennisvoorstellen maken" in response.text
    assert "Inhoudelijk beoordelen" in response.text
    assert "Kennisstuk (kennisobject)" in response.text
    assert "Context" in response.text
    assert "Voorwaarde" in response.text
    assert "Uitzondering" in response.text
    assert "Inhoudelijke beoordeling (review)" in response.text
    assert "Publicatiecontrole (publicatiegate)" in response.text
    assert "Geen onderbouwd antwoord (abstain)" in response.text
    assert "Onderzoek naar Metis" in response.text
    assert "Technische begrippen" in response.text
    assert "READY FOR IMPLEMENTATION" in response.text
    assert "V&amp;VN-bron" not in response.text
    assert "Gecontroleerde kennis</li>" not in response.text
    assert response.text.index("Werken met een bron") < response.text.index("Automatisering in Metis")
    assert response.text.index("Kennis publiceren") < response.text.index("Technische begrippen")
    assert console.list_envelopes() == envelopes_before
