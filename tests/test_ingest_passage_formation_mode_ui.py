"""Read-only projection of the active passage-formation runtime mode.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole
from src.passage_formation_policy_v1 import DETERMINISTIC_MODE, SEMANTIC_MODE
from src.pre_review_semantic_v1 import PASSAGE_FORMATION_MODE_ENV


def _client(tmp_path: Path) -> TestClient:
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
    login = client.post(
        "/login",
        data={"username": "researcher.anne", "password": "anne-secret"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    return client


def test_ingest_shows_deterministic_as_runtime_default_without_control(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv(PASSAGE_FORMATION_MODE_ENV, raising=False)
    page = _client(tmp_path).get("/ingest")

    assert page.status_code == 200
    assert 'data-passage-formation-mode="deterministic"' in page.text
    assert "Actieve verwerkingsmodus: Deterministisch" in page.text
    assert "Nieuwe en opnieuw verwerkte passages worden momenteel zonder taalmodel gevormd." in page.text
    assert "Beslisbomen blijven deterministisch." in page.text
    assert "Review blijft verplicht." in page.text
    assert f'name="{PASSAGE_FORMATION_MODE_ENV}"' not in page.text
    assert 'name="passage_formation_mode"' not in page.text
    assert "Wijzig modus" not in page.text


def test_ingest_projects_explicit_deterministic_runtime_mode(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(PASSAGE_FORMATION_MODE_ENV, DETERMINISTIC_MODE)
    page = _client(tmp_path).get("/ingest")

    assert page.status_code == 200
    assert 'data-passage-formation-mode="deterministic"' in page.text
    assert "Actieve verwerkingsmodus: Deterministisch" in page.text


def test_ingest_projects_semantic_runtime_mode_and_replay_behavior(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(PASSAGE_FORMATION_MODE_ENV, SEMANTIC_MODE)
    page = _client(tmp_path).get("/ingest")

    assert page.status_code == 200
    assert 'data-passage-formation-mode="semantic"' in page.text
    assert "Actieve verwerkingsmodus: Semantisch" in page.text
    assert "Nieuwe en opnieuw verwerkte HTML- en PDF-passages worden brongebonden semantisch gevormd." in page.text
    assert "Exacte replay wordt hergebruikt wanneer mogelijk" in page.text
    assert "Beslisbomen blijven deterministisch." in page.text
    assert "Review blijft verplicht." in page.text


def test_ingest_does_not_lie_when_runtime_mode_is_invalid(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(PASSAGE_FORMATION_MODE_ENV, "unsupported-mode")
    page = _client(tmp_path).get("/ingest")

    assert page.status_code == 200
    assert 'data-passage-formation-mode="invalid"' in page.text
    assert "Actieve verwerkingsmodus: Configuratiefout" in page.text
    assert "Nieuwe passagevorming is geblokkeerd totdat de deploymentconfiguratie is hersteld." in page.text
    assert "Actieve verwerkingsmodus: Deterministisch" not in page.text
    assert "Actieve verwerkingsmodus: Semantisch" not in page.text
