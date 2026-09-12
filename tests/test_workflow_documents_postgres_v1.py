"""Workflow document-store migration regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.workflow_documents_postgres_v1 import (
    WorkflowDocumentStoreError,
    _read_legacy_runtime,
)

ROOT = Path(__file__).resolve().parents[1]


def _envelope(snapshot_id: str = "snap-aaaaaaaaaaaaaaaa-bbbbbbbb") -> dict:
    return {
        "snapshot_id": snapshot_id,
        "source_id": "src-aaaaaaaaaaaaaaaa",
        "document_id": "console-test-1",
        "title": "Test",
        "family": "test",
        "class": "richtlijn",
        "state": "captured_not_published",
        "publication_eligibility": "blocked_pending_immutable_storage",
        "content_kind": "pdf",
        "ingest_kind": "new",
        "version": "1.0",
        "date": "2026-09-12",
        "sha256": "a" * 64,
        "locator": "g0-local:sources/private/test.pdf",
        "immutable_storage_locator": None,
        "live_url": "",
        "uploader_account_id": "acc-uploader",
        "named_reviewers": ["acc-reviewer"],
        "review_passes": {},
        "replaces_snapshot_id": None,
        "object_diff": None,
        "clinical_rereview_required": False,
        "acquired_at": "2026-09-12T09:00:00Z",
        "console_version": "operations-console-v1.0.0",
    }


def _write_runtime(tmp_path: Path, *, envelope: dict | None = None, objects: list[dict] | None = None) -> Path:
    runtime = tmp_path / "operations-console"
    runtime.mkdir()
    env = envelope or _envelope()
    (runtime / "envelopes.json").write_text(json.dumps({env["snapshot_id"]: env}), encoding="utf-8")
    objects_dir = runtime / "objects"
    objects_dir.mkdir()
    rows = objects if objects is not None else [
        {"object_id": "obj-1", "object_version": "1.0", "object_type": "document"},
        {"object_id": "obj-2", "object_version": "1.0", "object_type": "recommendation"},
    ]
    (objects_dir / f"{env['snapshot_id']}.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return runtime


def test_legacy_runtime_reads_complete_document_bundle(tmp_path: Path) -> None:
    runtime = _write_runtime(tmp_path)
    bundles = _read_legacy_runtime(runtime)
    assert len(bundles) == 1
    assert bundles[0]["envelope"]["snapshot_id"] == _envelope()["snapshot_id"]
    assert [row["object_id"] for row in bundles[0]["objects"]] == ["obj-1", "obj-2"]


def test_legacy_runtime_rejects_snapshot_key_mismatch(tmp_path: Path) -> None:
    runtime = tmp_path / "operations-console"
    runtime.mkdir()
    env = _envelope()
    (runtime / "envelopes.json").write_text(json.dumps({"snap-wrong": env}), encoding="utf-8")
    with pytest.raises(WorkflowDocumentStoreError, match="workflow_legacy_snapshot_identity_mismatch"):
        _read_legacy_runtime(runtime)


def test_legacy_runtime_rejects_duplicate_object_identity(tmp_path: Path) -> None:
    obj = {"object_id": "obj-1", "object_version": "1.0", "object_type": "recommendation"}
    runtime = _write_runtime(tmp_path, objects=[obj, dict(obj)])
    with pytest.raises(WorkflowDocumentStoreError, match="workflow_legacy_object_identity_invalid"):
        _read_legacy_runtime(runtime)


def test_document_store_keeps_atomic_and_exact_replay_contract() -> None:
    text = (ROOT / "src" / "workflow_documents_postgres_v1.py").read_text(encoding="utf-8")
    assert "with con.transaction()" in text
    assert "FOR UPDATE" in text
    assert "workflow_document_migration_conflict" in text
    assert "workflow_document_reviewers_migration_conflict" in text
    assert "workflow_document_objects_migration_conflict" in text
    assert "allow_exact_existing=True" in text


def test_document_store_is_not_wired_into_console_yet() -> None:
    text = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert "workflow_documents_postgres_v1" not in text


def test_migration_cli_is_explicit_not_startup_side_effect() -> None:
    cli = (ROOT / "scripts" / "migrate_workflow_documents_postgres.py").read_text(encoding="utf-8")
    assert "--runtime" in cli
    assert "migrate_legacy_runtime" in cli
    assert "PostgresWorkflowDocumentStore" in cli
