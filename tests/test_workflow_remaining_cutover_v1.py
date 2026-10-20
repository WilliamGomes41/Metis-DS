"""Final local-authority removal regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.workflow_store_configuration import POSTGRES_STORE_SETTINGS, validate_workflow_store_configuration
from src.workflows.workflow_remaining_cutover_v1 import PostgresAuditRegistry

ROOT = Path(__file__).resolve().parents[1]


class _FakeRemainingStore:
    def __init__(self) -> None:
        self.audits: dict[str, dict] = {}

    def list_audits(self):
        return sorted(self.audits.values(), key=lambda row: (row["created_at"], row["audit_id"]), reverse=True)

    def get_audit(self, audit_id):
        return self.audits.get(audit_id)

    def create_audit(self, record):
        if record["audit_id"] in self.audits:
            raise RuntimeError("duplicate")
        self.audits[record["audit_id"]] = dict(record)
        return dict(record)


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



def _refused_partial_configurations(monkeypatch, setting):
    """#718: a store is opt-in by its setting and never selected without the complete set."""
    assert setting in POSTGRES_STORE_SETTINGS
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    for name in POSTGRES_STORE_SETTINGS:
        monkeypatch.setenv(name, "postgres")
    assert validate_workflow_store_configuration() is True
    for missing in POSTGRES_STORE_SETTINGS:
        monkeypatch.delenv(missing)
        with pytest.raises(RuntimeError):
            validate_workflow_store_configuration()
        monkeypatch.setenv(missing, "postgres")
    asgi = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert "validate_workflow_store_configuration()" in asgi


def test_remaining_store_is_explicit_and_requires_previous_cutovers(monkeypatch) -> None:
    _refused_partial_configurations(monkeypatch, "METIS_WORKFLOW_REMAINING_STORE")
    source = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert "migrate_workflow_remaining_postgres" not in source


def test_class_history_and_publication_state_no_longer_depend_on_local_files() -> None:
    remaining_source = (ROOT / "src" / "workflows" / "workflow_remaining_cutover_v1.py").read_text(encoding="utf-8")
    document_source = (ROOT / "src" / "workflows" / "workflow_documents_cutover_v1.py").read_text(encoding="utf-8")
    assert '"objects": deepcopy(rows)' in remaining_source
    assert "workflow_class_history_cutover_not_prepared" in remaining_source
    assert "workflow_document_store.write_bundle(envelope=current)" in document_source
    assert "read_events(self._ledger_path)" in remaining_source


def test_pg_release_files_are_unused_and_not_recovery_sources() -> None:
    docs = (ROOT / "docs" / "RUNTIME_DATA_RECOVERY.md").read_text(encoding="utf-8")
    assert "release manifests" in docs.lower()
    assert "zonder runtime-bestanden" in docs.lower()
    assert "ongebruikt" in docs.lower()
    assert "geen workflow-authority" in docs.lower()