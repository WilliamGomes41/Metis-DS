"""Final local-authority removal regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet

from src.workflow_remaining_cutover_v1 import (
    PostgresAuditLLMSecretStore,
    PostgresAuditRegistry,
)

ROOT = Path(__file__).resolve().parents[1]


class _FakeRemainingStore:
    def __init__(self) -> None:
        self.audits: dict[str, dict] = {}
        self.secrets: dict[str, dict] = {}

    def list_audits(self):
        return sorted(self.audits.values(), key=lambda row: (row["created_at"], row["audit_id"]), reverse=True)

    def get_audit(self, audit_id):
        return self.audits.get(audit_id)

    def create_audit(self, record):
        if record["audit_id"] in self.audits:
            raise RuntimeError("duplicate")
        self.audits[record["audit_id"]] = dict(record)
        return dict(record)

    def get_secret_payload(self, name):
        return self.secrets.get(name)

    def set_secret_payload(self, name, payload):
        self.secrets[name] = dict(payload)

    def delete_secret(self, name):
        self.secrets.pop(name, None)


def test_audit_registry_uses_shared_store_not_runtime_files() -> None:
    store = _FakeRemainingStore()
    registry = PostgresAuditRegistry(store)  # type: ignore[arg-type]
    created = registry.create(
        audit_type="experiment",
        title="Passage experiment",
        actor_id="acc-researcher",
        payload={"state": "setup"},
    )
    assert registry.get_audit(created["audit_id"]) == created
    assert registry.list_audits() == [created]


def test_audit_secret_stays_encrypted_in_shared_store() -> None:
    store = _FakeRemainingStore()
    key = Fernet.generate_key().decode("ascii")
    secrets = PostgresAuditLLMSecretStore(store, environ={"METIS_AUDIT_SECRET_KEY": key})  # type: ignore[arg-type]
    secrets.set_api_key("provider-secret")
    assert secrets.status() == {"available": True, "configured": True}
    assert store.secrets["llm_api_key"]["ciphertext"] != "provider-secret"
    assert secrets.read_api_key() == "provider-secret"
    secrets.clear_api_key()
    assert secrets.status() == {"available": True, "configured": False}


def test_remaining_store_is_explicit_and_requires_previous_cutovers() -> None:
    source = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert "METIS_WORKFLOW_REMAINING_STORE" in source
    assert "workflow_identity_store_required_for_remaining_store" in source
    assert "workflow_document_store_required_for_remaining_store" in source
    assert "workflow_review_store_required_for_remaining_store" in source
    assert "migrate_workflow_remaining_postgres" not in source


def test_class_history_and_publication_state_no_longer_depend_on_local_files() -> None:
    source = (ROOT / "src" / "workflow_remaining_cutover_v1.py").read_text(encoding="utf-8")
    assert '"objects": deepcopy(rows)' in source
    assert "workflow_class_history_cutover_not_prepared" in source
    assert "workflow_document_store.write_bundle(envelope=current)" in source
    assert "read_events(self._ledger_path)" in source


def test_release_files_are_declared_rebuildable_not_authority() -> None:
    docs = (ROOT / "docs" / "RUNTIME_DATA_RECOVERY.md").read_text(encoding="utf-8")
    assert "release manifests" in docs.lower()
    assert "rebuildable" in docs.lower()
    assert "geen workflow-authority" in docs.lower()
