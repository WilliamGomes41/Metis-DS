"""Authenticated settings hub regressions.

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


def _client(tmp_path: Path) -> TestClient:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    console.create_account(
        username="publisher.carla",
        password="carla-secret",
        roles=("publisher",),
        display_name="Carla Publisher",
    )
    client = TestClient(create_console_app(console))
    login = client.post(
        "/login",
        data={"username": "publisher.carla", "password": "carla-secret"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    return client


def test_settings_routes_require_login(tmp_path: Path) -> None:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    client = TestClient(create_console_app(console))

    assert client.get("/settings").status_code == 401
    assert client.get("/settings/llm").status_code == 401


def test_settings_is_single_top_level_door_for_accounts_llm_and_about(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/settings")
    assert response.status_code == 200
    nav = response.text[response.text.find('class="rooms"') : response.text.find("</nav>")]
    assert 'href="/settings" aria-current="page">Instellingen' in nav
    assert 'href="/accounts"' not in nav
    assert 'href="/over-console"' not in nav

    assert 'href="/accounts"' in response.text
    assert 'href="/settings/llm"' in response.text
    assert 'href="/over-console"' in response.text
    assert "Accounts" in response.text
    assert "LLM-instellingen" in response.text
    assert "Over Metis" in response.text


def test_llm_settings_only_exposes_shared_deployment_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("METIS_LLM_API_KEY", "never-render-this-secret")
    monkeypatch.setenv("METIS_LLM_MODEL", "shared-test-model")
    client = _client(tmp_path)

    response = client.get("/settings/llm")
    assert response.status_code == 200
    assert "shared-test-model" in response.text
    assert "Geconfigureerd" in response.text
    assert "never-render-this-secret" not in response.text
    assert 'name="api_key"' not in response.text
    assert 'name="model"' not in response.text
    assert "deploymentconfiguratie" in response.text


def test_settings_deep_links_remain_compatible_and_keep_settings_active(tmp_path: Path) -> None:
    client = _client(tmp_path)

    for path in ("/accounts", "/over-console"):
        response = client.get(path)
        assert response.status_code == 200
        nav = response.text[response.text.find('class="rooms"') : response.text.find("</nav>")]
        assert 'href="/settings" aria-current="page">Instellingen' in nav
