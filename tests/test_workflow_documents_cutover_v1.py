"""PostgreSQL document cut-over regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from src.operations_console_v1 import SNAPSHOT_OBJECT_WRITE_CONFLICT, _objects_jsonl_bytes
from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore

ROOT = Path(__file__).resolve().parents[1]


def test_cutover_revision_preserves_object_order() -> None:
    rows = [
        {"object_id": "z", "object_version": "1.0", "text": "first"},
        {"object_id": "a", "object_version": "1.0", "text": "second"},
    ]
    expected = hashlib.sha256(_objects_jsonl_bytes(rows)).hexdigest()
    assert PostgresWorkflowDocumentRuntimeStore._revision(rows) == expected
    assert PostgresWorkflowDocumentRuntimeStore._revision(list(reversed(rows))) != expected


def test_cutover_schema_preserves_full_envelope_and_object_position() -> None:
    sql = (ROOT / "db" / "migrations" / "003_workflow_document_envelope_payload.sql").read_text(encoding="utf-8")
    assert "envelope_payload JSONB" in sql
    assert "position INTEGER" in sql


def test_cutover_is_explicit_and_never_runs_legacy_migration_on_startup() -> None:
    asgi = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert "METIS_WORKFLOW_DOCUMENT_STORE" in asgi
    assert "workflow_identity_store_required_for_document_store" in asgi
    assert "migrate_legacy_runtime" not in asgi
    assert "prepare_legacy_cutover" not in asgi


def test_cutover_runtime_reads_objects_by_migrated_position() -> None:
    source = (ROOT / "src" / "workflow_documents_cutover_v1.py").read_text(encoding="utf-8")
    assert "ORDER BY position" in source
    assert "workflow_document_cutover_not_prepared" in source
    assert "expected_revision" in source
    assert SNAPSHOT_OBJECT_WRITE_CONFLICT == "snapshot_object_write_conflict"


def test_local_files_are_declared_compatibility_mirrors_not_authority() -> None:
    source = (ROOT / "src" / "workflow_documents_cutover_v1.py").read_text(encoding="utf-8")
    assert "compatibility mirror" in source
    assert "PostgreSQL becomes authority" in source
