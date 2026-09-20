from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole


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

    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    envelopes_before = console.list_envelopes()
    response = client.get("/over-console")

    assert response.status_code == 200
    assert 'href="/over-console" aria-current="page">Over console' in response.text
    assert "Metis uitgelegd" in response.text
    assert "Kennisobject" in response.text
    assert "Publicatiegate" in response.text
    assert "Abstain" in response.text
    assert "READY FOR IMPLEMENTATION" in response.text
    assert console.list_envelopes() == envelopes_before
