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


def test_archive_moves_complete_record_to_archive_and_leaves_payload_free_index(
    tmp_path: Path,
) -> None:
    registry = AuditRegistry(tmp_path / "runtime")
    original = _created(registry)
    archive = _MemoryArchiveStore()
    service = AuditRetentionService(
        live_store=registry,
        archive_store=archive,
        runtime=tmp_path / "runtime",
    )

    row = service.archive(original["audit_id"], actor_id="acct-researcher")

    assert registry.get_audit(original["audit_id"]) is None
    assert "payload" not in row
    assert set(row) == {
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
    assert service.load_archived(original["audit_id"]) == original
    assert archive.data[row["archive_locator"]] == canonical_audit_bytes(original)


def test_archive_store_failure_preserves_live_audit_and_writes_no_index(
    tmp_path: Path,
) -> None:
    registry = AuditRegistry(tmp_path / "runtime")
    original = _created(registry)
    archive = _MemoryArchiveStore()
    archive.fail_store = True
    service = AuditRetentionService(
        live_store=registry,
        archive_store=archive,
        runtime=tmp_path / "runtime",
    )

    with pytest.raises(ConsoleError, match="audit_archive_store_failed"):
        service.archive(original["audit_id"], actor_id="acct-researcher")

    assert registry.get_audit(original["audit_id"]) == original
    assert service.list_archived() == []


class _DeleteFailsOnce:
    def __init__(self, record: dict) -> None:
        self.record = record
        self.failures = 1

    def get_audit(self, audit_id: str) -> dict | None:
        if self.record and self.record["audit_id"] == audit_id:
            return self.record
        return None

    def remove_audit(self, audit_id: str) -> bool:
        if self.record is None or self.record["audit_id"] != audit_id:
            return False
        if self.failures:
            self.failures -= 1
            return False
        self.record = None
        return True


def test_retry_completes_cleanup_when_archive_and_index_already_exist(
    tmp_path: Path,
) -> None:
    registry = AuditRegistry(tmp_path / "seed")
    original = _created(registry)
    live = _DeleteFailsOnce(original)
    archive = _MemoryArchiveStore()
    service = AuditRetentionService(
        live_store=live,
        archive_store=archive,
        runtime=tmp_path / "runtime",
    )

    with pytest.raises(ConsoleError, match="audit_archive_live_delete_failed"):
        service.archive(original["audit_id"], actor_id="acct-researcher")

    index = service.get_archived_index(original["audit_id"])
    assert index is not None
    assert live.get_audit(original["audit_id"]) == original

    retried = service.archive(original["audit_id"], actor_id="acct-researcher")

    assert retried == index
    assert live.get_audit(original["audit_id"]) is None
    assert service.load_archived(original["audit_id"]) == original


def test_archiving_already_archived_audit_is_idempotent(tmp_path: Path) -> None:
    registry = AuditRegistry(tmp_path / "runtime")
    original = _created(registry)
    archive = _MemoryArchiveStore()
    service = AuditRetentionService(
        live_store=registry,
        archive_store=archive,
        runtime=tmp_path / "runtime",
    )

    first = service.archive(original["audit_id"], actor_id="acct-researcher")
    second = service.archive(original["audit_id"], actor_id="acct-researcher")

    assert second == first
    assert len(service.list_archived()) == 1
    assert service.load_archived(original["audit_id"]) == original
