"""Sandbox separation proof; GitHub privacy API itself needs Codespaces evidence.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import os
import subprocess
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from scripts import security_sandbox as sandbox


def test_application_does_not_inherit_production_credentials():
    with patch.dict(os.environ, {
        "PATH": "/usr/bin", "METIS_CANONICAL_STORE": "postgres",
        "PGHOST": "production.example", "AZURE_CLIENT_SECRET": "synthetic-secret",
        "METIS_ENTRA_CLIENT_SECRET": "synthetic-secret", "GH_TOKEN": "synthetic-secret",
    }, clear=True):
        env = sandbox.sandbox_environment(postgres=True)
    assert env["METIS_TEST_POSTGRES_DSN"] == sandbox.TEST_DSN
    assert env["METIS_CONSOLE_AUTH"] == "local"
    assert not {"METIS_CANONICAL_STORE", "PGHOST", "AZURE_CLIENT_SECRET",
                "METIS_ENTRA_CLIENT_SECRET", "GH_TOKEN"} & env.keys()


def test_external_database_is_rejected_before_any_test_runs(monkeypatch):
    monkeypatch.setenv("METIS_TEST_POSTGRES_DSN", "postgresql://production.example/metis")
    with patch.object(subprocess, "call") as tests:
        with pytest.raises(SystemExit, match="Refusing non-sandbox"):
            sandbox.run_tests(local=True)
    tests.assert_not_called()


def test_port_privacy_failure_prevents_server_and_account_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "RUNTIME", tmp_path)
    with patch.dict(os.environ, {"CODESPACE_NAME": "synthetic-sandbox"}, clear=True), \
         patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(1, "gh")):
        with pytest.raises(subprocess.CalledProcessError):
            sandbox.serve()
    assert not (tmp_path / "accounts.json").exists()


def test_sandbox_roles_login_and_origin_guard(tmp_path, monkeypatch):
    import uvicorn
    # Initialize platform metadata before mocking the external GitHub command.
    from src.console_asgi import build_app  # noqa: F401
    monkeypatch.setattr(sandbox, "RUNTIME", tmp_path)
    origin = "https://synthetic-sandbox-8000.app.github.dev"
    original_run = subprocess.run

    def private_port(command, **kwargs):
        if command[0] == "gh":
            assert command == ["gh", "codespace", "ports", "visibility", "8000:private", "-c", "synthetic-sandbox"]
            assert kwargs == {"check": True}
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, **kwargs)

    with patch.dict(os.environ, {"CODESPACE_NAME": "synthetic-sandbox"}, clear=True), \
         patch.object(subprocess, "run", side_effect=private_port), \
         patch.object(uvicorn, "run") as server:
        sandbox.serve()
        app = server.call_args.args[0]
        client = TestClient(app, base_url=origin)
        credentials = tmp_path / "accounts.json"
        accounts = json.loads(credentials.read_text())
        assert credentials.stat().st_mode & 0o777 == 0o600
        assert [a["roles"] for a in accounts] == [["researcher"], ["researcher"], ["reviewer"], ["publisher"]]
        assert client.post("/login", headers={"Origin": "https://evil.example"}).status_code == 403
        account = accounts[0]
        response = client.post("/login", headers={"Origin": origin},
                               data={"username": account["username"], "password": account["password"]},
                               follow_redirects=False)
        assert response.status_code == 303
        assert "Secure" in response.headers["set-cookie"]
        assert "HttpOnly" in response.headers["set-cookie"]
