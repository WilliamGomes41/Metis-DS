from __future__ import annotations

import os
from pathlib import Path

from src.console_asgi import bootstrap_accounts, build_app
from src.operations_console_v1 import OperationsConsole


def test_bootstrap_creates_owner_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CONSOLE_BOOTSTRAP_USERNAME", "william")
    monkeypatch.setenv("CONSOLE_BOOTSTRAP_PASSWORD", "Metis2026!")
    monkeypatch.setenv("CONSOLE_BOOTSTRAP_REVIEWER_USERNAME", "reviewer")
    monkeypatch.setenv("CONSOLE_BOOTSTRAP_REVIEWER_PASSWORD", "Review2026!")
    console = OperationsConsole(root=tmp_path, source_store=tmp_path / "src", runtime=tmp_path / "rt")
    bootstrap_accounts(console)
    bootstrap_accounts(console)
    names = {row["username"] for row in console._accounts.values()}
    assert names == {"william", "reviewer"}


def test_build_app_serves_login(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CONSOLE_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("CONSOLE_BOOTSTRAP_USERNAME", raising=False)
    monkeypatch.delenv("CONSOLE_BOOTSTRAP_PASSWORD", raising=False)
    from fastapi.testclient import TestClient

    client = TestClient(build_app())
    response = client.get("/login")
    assert response.status_code == 200
    assert "Aanmelden" in response.text
