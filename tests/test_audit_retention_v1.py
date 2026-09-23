"""LIVE -> ARCHIVED audit retention semantics.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.audit_archive_store_v1 import AuditArchiveStoreError
from src.audit_retention_v1 import AuditRetentionService, canonical_audit_bytes
from src.audit_room_v1 import AuditRegistry
from src.operations_console_v1 import ConsoleError


class _MemoryArchiveStore:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.fail_store = False

    def _locator(self, audit_id: str) -> str:
        return f"memory-audit://{audit_id}"

    def store_verified(self, *, audit_id: str, data: bytes, sha256: str) -> str:
        if self.fail_store:
            raise AuditArchiveStoreError("audit_archive_upload_failed")
        assert hashlib.sha256(data).hexdigest() == sha256
        locator = self._locator(audit_id)
        existing = self.data.get(locator)
        if existing is not None and existing != data:
            raise AuditArchiveStoreError("audit_archive_conflict")
        self.data[locator] = bytes(data)
        return locator

    def load_verified(self, locator: str, *, expected_sha256: str) -> bytes:
        data = self.data[locator]
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise AuditArchiveStoreError("audit_archive_checksum_mismatch")
        return data

    def delete_verified(self, locator: str) -> bool:
        return self.data.pop(locator, None) is not None


def _created(registry: AuditRegistry) -> dict:
    return registry.create(
        audit_type="experiment",
        title="Audit voor archief",
        actor_id="acct-researcher",
        payload={"state": "semantic_safety_completed", "evidence": {"pass": False}},
    )


def test_archive_atomically_replaces_live_record_with_payload_free_reference(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    registry = AuditRegistry(runtime)
    original = _created(registry)
    archive = _MemoryArchiveStore()
    service = AuditRetentionService(
        live_store=registry,
        archive_store=archive,
        runtime=runtime,
    )

    row = service.archive(original["audit_id"], actor_id="acct-researcher")

    assert registry.get_audit(original["audit_id"]) is None
    assert registry.list_audits() == []
    assert "payload" not in row
    assert set(row) == {
        "record_kind",
        "schema_version",
        "audit_id",
        "title",
        "audit_type",
        "created_at",
        "archived_at",
        "archived_by",
        "archive_locator",
        "checksum_sha256",
    }
    local_path = runtime / "audits" / f'{original["audit_id"]}.json'
    local_record = json.loads(local_path.read_text(encoding="utf-8"))
    assert local_record == row
    assert "payload" not in local_record
    assert not (runtime / "audits" / "archive-index").exists()
    assert service.load_archived(original["audit_id"]) == original
    assert archive.data[row["archive_locator"]] == canonical_audit_bytes(original)


def test_archive_store_failure_preserves_live_audit_and_no_archived_reference(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    registry = AuditRegistry(runtime)
    original = _created(registry)
    archive = _MemoryArchiveStore()
    archive.fail_store = True
    service = AuditRetentionService(
        live_store=registry,
        archive_store=archive,
        runtime=runtime,
    )

    with pytest.raises(ConsoleError, match="audit_archive_store_failed"):
        service.archive(original["audit_id"], actor_id="acct-researcher")

    assert registry.get_audit(original["audit_id"]) == original
    assert service.list_archived() == []
    stored = json.loads(
        (runtime / "audits" / f'{original["audit_id"]}.json').read_text(encoding="utf-8")
    )
    assert stored["payload"] == original["payload"]


class _ReplaceFailsOnce:
    def __init__(self, registry: AuditRegistry) -> None:
        self.registry = registry
        self.failures = 1

    def get_audit(self, audit_id: str) -> dict | None:
        return self.registry.get_audit(audit_id)

    def replace_with_archived_ref(self, audit_id: str, reference: dict) -> None:
        if self.failures:
            self.failures -= 1
            raise ConsoleError("simulated_atomic_replace_failure")
        self.registry.replace_with_archived_ref(audit_id, reference)


def test_failed_local_state_flip_keeps_live_and_retry_completes_transition(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    registry = AuditRegistry(runtime)
    original = _created(registry)
    live = _ReplaceFailsOnce(registry)
    archive = _MemoryArchiveStore()
    service = AuditRetentionService(
        live_store=live,
        archive_store=archive,
        runtime=runtime,
    )

    with pytest.raises(ConsoleError, match="simulated_atomic_replace_failure"):
        service.archive(original["audit_id"], actor_id="acct-researcher")

    assert registry.get_audit(original["audit_id"]) == original
    assert service.list_archived() == []
    assert archive.data == {}

    retried = service.archive(original["audit_id"], actor_id="acct-researcher")

    assert retried["audit_id"] == original["audit_id"]
    assert registry.get_audit(original["audit_id"]) is None
    assert service.load_archived(original["audit_id"]) == original


def test_archiving_already_archived_audit_is_idempotent(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    registry = AuditRegistry(runtime)
    original = _created(registry)
    archive = _MemoryArchiveStore()
    service = AuditRetentionService(
        live_store=registry,
        archive_store=archive,
        runtime=runtime,
    )

    first = service.archive(original["audit_id"], actor_id="acct-researcher")
    second = service.archive(original["audit_id"], actor_id="acct-researcher")

    assert second == first
    assert len(service.list_archived()) == 1
    assert service.load_archived(original["audit_id"]) == original


def test_restart_preserves_archived_state_and_verified_content(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    first_registry = AuditRegistry(runtime)
    original = _created(first_registry)
    archive = _MemoryArchiveStore()
    first_service = AuditRetentionService(
        live_store=first_registry,
        archive_store=archive,
        runtime=runtime,
    )
    first_service.archive(original["audit_id"], actor_id="acct-researcher")

    restarted_registry = AuditRegistry(runtime)
    restarted_service = AuditRetentionService(
        live_store=restarted_registry,
        archive_store=archive,
        runtime=runtime,
    )

    assert restarted_registry.list_audits() == []
    assert restarted_registry.get_audit(original["audit_id"]) is None
    assert [row["audit_id"] for row in restarted_service.list_archived()] == [
        original["audit_id"]
    ]
    assert restarted_service.load_archived(original["audit_id"]) == original
