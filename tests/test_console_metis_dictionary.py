"""Authenticated, read-only regressions for the Metis explanation page.

Release-control markers identify the route, login boundary and the deliberately
small console extension. They are test metadata, not live-release evidence.
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

from pathlib import Path

import pytest
from fastapi.testclient import TestClient



pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def test_metis_dictionary_requires_login_and_renders_read_only_explanations(tmp_path: Path, *, production_app, production_console) -> None:
    console = production_console(processing_binder=bind_fixture_selections,
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
    client = TestClient(production_app(console))

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
    assert '/brand/metis-explained.css?v=' in response.text
    assert 'href="/settings" aria-current="page">Instellingen' in response.text
    assert "Metis uitgelegd" in response.text
    assert "Zo werkt Metis" in response.text
    assert "Bron aanleveren" in response.text
    assert "Kennisvoorstellen maken" in response.text
    assert "Inhoudelijk beoordelen" in response.text
    response = client.get("/over-console?section=begrippen")
    assert response.status_code == 200
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

    for section in ("start", "begrippen", "modellen", "kennisbasis"):
        response = client.get("/over-console", params={"section": section})
        assert response.status_code == 200
        assert f'section={section}" aria-current="page"' in response.text

    search = client.get("/over-console", params={"q": "gold standard"})
    assert search.status_code == 200
    assert '#begrip-referentieset' in search.text
    assert 'name="q" value="gold standard"' in search.text
    mixed = client.get("/over-console", params={"q": "brontrouw"})
    assert 'model=bron' in mixed.text
    assert '#begrip-brontrouw' in mixed.text
    dossier = client.get("/over-console?section=modellen&model=context")
    assert dossier.status_code == 200
    assert "Context- en relatiemodel" in dossier.text
    assert "Niet vastgesteld op deze pagina" in dossier.text
    assert "Onderbouwing en bewijsgrens" in dossier.text
    assert 'id="model-grenzen"' in dossier.text

    empty = client.get("/over-console", params={"q": "zzzonbestaandbegrip"})
    assert "Geen uitleg gevonden" in empty.text
    assert "Bekijk alle begrippen" in empty.text
    malicious = '<img src=x onerror="alert(1)">'
    escaped = client.get("/over-console", params={"q": malicious})
    assert malicious not in escaped.text
    assert "&lt;img" in escaped.text
    assert client.get("/over-console?section=onbekend").status_code == 404
    assert client.get("/over-console?section=modellen&model=../../secret").status_code == 404
    assert client.get("/over-console?section=start&model=context").status_code == 404
    assert client.get("/over-console", params={"q": "a" * 201}).status_code == 422
    assert console.list_envelopes() == envelopes_before

    client.post("/logout")
    for path in ("/over-console?section=begrippen", "/over-console?q=brontrouw",
                 "/over-console?section=modellen&model=context", "/over-console?section=kennisbasis"):
        assert client.get(path).status_code == 401
