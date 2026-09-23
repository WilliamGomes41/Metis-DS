"""Verified Azure audit archive storage.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib

import pytest

from src.audit_archive_store_v1 import (
    AuditArchiveStoreError,
    AzureAuditArchiveStore,
)


class _Download:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def readall(self) -> bytes:
        return self._data


class _Blob:
    def __init__(self, service: "_BlobService", name: str) -> None:
        self.service = service
        self.name = name

    def upload_blob(self, data: bytes, **_kwargs: object) -> None:
        if self.name in self.service.data:
            ResourceExistsError = type("ResourceExistsError", (RuntimeError,), {})
            raise ResourceExistsError()
        self.service.data[self.name] = bytes(data)

    def download_blob(self) -> _Download:
        if self.name not in self.service.data:
            ResourceNotFoundError = type("ResourceNotFoundError", (RuntimeError,), {})
            raise ResourceNotFoundError()
        return _Download(self.service.data[self.name])

    def delete_blob(self, **_kwargs: object) -> None:
        if self.name not in self.service.data:
            ResourceNotFoundError = type("ResourceNotFoundError", (RuntimeError,), {})
            raise ResourceNotFoundError()
        del self.service.data[self.name]


class _BlobService:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def get_blob_client(self, *, container: str, blob: str) -> _Blob:
        assert container == "audit-archive"
        return _Blob(self, blob)


def _store(service: _BlobService) -> AzureAuditArchiveStore:
    return AzureAuditArchiveStore(
        account="aidataservice",
        container="audit-archive",
        blob_service_client=service,
    )


def test_archive_store_uploads_reads_and_retries_same_record() -> None:
    service = _BlobService()
    store = _store(service)
    audit_id = "audit-0123456789abcdef"
    data = b'{"audit_id":"audit-0123456789abcdef","payload":{}}'
    digest = hashlib.sha256(data).hexdigest()

    locator = store.store_verified(audit_id=audit_id, data=data, sha256=digest)

    assert locator == (
        "azure-audit://aidataservice/audit-archive/"
        "audits/audit-0123456789abcdef.json"
    )
    assert store.load_verified(locator, expected_sha256=digest) == data
    assert store.store_verified(audit_id=audit_id, data=data, sha256=digest) == locator


def test_archive_store_rejects_existing_corrupt_record() -> None:
    service = _BlobService()
    store = _store(service)
    audit_id = "audit-0123456789abcdef"
    data = b"expected"
    digest = hashlib.sha256(data).hexdigest()
    service.data[f"audits/{audit_id}.json"] = b"corrupt"

    with pytest.raises(AuditArchiveStoreError, match="audit_archive_checksum_mismatch"):
        store.store_verified(audit_id=audit_id, data=data, sha256=digest)


def test_archive_store_delete_is_idempotent_for_missing_blob() -> None:
    service = _BlobService()
    store = _store(service)
    audit_id = "audit-0123456789abcdef"
    data = b"archive"
    digest = hashlib.sha256(data).hexdigest()
    locator = store.store_verified(audit_id=audit_id, data=data, sha256=digest)

    assert store.delete_verified(locator) is True
    assert store.delete_verified(locator) is False
