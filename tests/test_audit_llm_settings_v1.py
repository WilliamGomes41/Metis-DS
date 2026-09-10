"""Audit-only LLM credential management stays secret and outside the kernel."""
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest

from src.audit_llm_secret_v1 import AuditLLMSecretStore
from src.audit_llm_settings_v1 import install_audit_llm_settings_routes
from src.audit_room_v1 import AuditRegistry, install_audit_routes
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole


ROOT = Path(__file__).resolve().parents[1]


def _system(tmp_path, monkeypatch, *, roles=("researcher",)):
    monkeypatch.setenv("METIS_AUDIT_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    account = console.create_account(
        username="anne",
        password="anne-secret",
        roles=roles,
        display_name="Anne",
    )
    app = create_console_app(console)
    install_audit_llm_settings_routes(app, console)
    install_audit_routes(app, console)
    client = TestClient(app, raise_server_exceptions=False)
    client.post("/login", data={"username": "anne", "password": "anne-secret"})
    return console, client, account


def test_researcher_can_set_replace_and_remove_write_only_key(tmp_path, monkeypatch):
    console, client, _account = _system(tmp_path, monkeypatch)
    store = AuditLLMSecretStore(console.runtime)

    page = client.get("/audit/llm-settings")
    assert page.status_code == 200
    assert "Niet geconfigureerd" in page.text
    assert 'type="password"' in page.text

    first = "sk-test-first-secret-value"
    response = client.post("/audit/llm-settings", data={"api_key": first}, follow_redirects=False)
    assert response.status_code == 303
    assert store.read_api_key() == first
    ciphertext_file = console.runtime / "audit_secrets" / "llm_api_key.json"
    stored_bytes = ciphertext_file.read_bytes()
    assert first.encode("utf-8") not in stored_bytes

    configured = client.get(response.headers["location"])
    assert configured.status_code == 200
    assert "Geconfigureerd" in configured.text
    assert first not in configured.text

    second = "sk-test-replacement-secret-value"
    response = client.post("/audit/llm-settings", data={"api_key": second}, follow_redirects=False)
    assert response.status_code == 303
    assert store.read_api_key() == second
    stored_text = ciphertext_file.read_text(encoding="utf-8")
    assert first not in stored_text
    assert second not in stored_text

    response = client.post("/audit/llm-settings/delete", follow_redirects=False)
    assert response.status_code == 303
    assert not ciphertext_file.exists()
    with pytest.raises(ConsoleError, match="audit_llm_api_key_missing"):
        store.read_api_key()


def test_llm_key_management_does_not_touch_audit_or_kernel_state(tmp_path, monkeypatch):
    console, client, _account = _system(tmp_path, monkeypatch)
    before_envelopes = console.list_envelopes()
    before_audits = AuditRegistry(console.runtime).list_audits()

    response = client.post("/audit/llm-settings", data={"api_key": "sk-audit-only"}, follow_redirects=False)
    assert response.status_code == 303
    assert console.list_envelopes() == before_envelopes == []
    assert AuditRegistry(console.runtime).list_audits() == before_audits == []
    assert not (console.runtime / "published_projection.jsonl").exists()


def test_non_researcher_cannot_open_or_change_llm_settings(tmp_path, monkeypatch):
    console, client, _account = _system(tmp_path, monkeypatch, roles=("reviewer",))
    assert client.get("/audit/llm-settings").status_code == 403
    assert client.post("/audit/llm-settings", data={"api_key": "sk-denied"}).status_code == 403
    assert not (console.runtime / "audit_secrets" / "llm_api_key.json").exists()


def test_missing_master_key_disables_secret_input(tmp_path, monkeypatch):
    monkeypatch.delenv("METIS_AUDIT_SECRET_KEY", raising=False)
    console = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    console.create_account(username="anne", password="anne-secret", roles=("researcher",), display_name="Anne")
    app = create_console_app(console)
    install_audit_llm_settings_routes(app, console)
    client = TestClient(app)
    client.post("/login", data={"username": "anne", "password": "anne-secret"})

    page = client.get("/audit/llm-settings")
    assert page.status_code == 200
    assert "Niet beschikbaar" in page.text
    assert "METIS_AUDIT_SECRET_KEY" in page.text
    assert 'name="api_key"' not in page.text


def test_roadmap_locks_write_only_audit_llm_key_boundary():
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    for required in (
        "Audit → LLM-instellingen",
        "de API-key is write-only",
        "METIS_AUDIT_SECRET_KEY",
        "dit is geen algemene environment-variable- of secret-editor",
        "LLM API-key via Audit-console",
    ):
        assert required in roadmap
