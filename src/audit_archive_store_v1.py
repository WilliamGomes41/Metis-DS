"""Azure-backed archive store for complete audit records.

Audit retention is deliberately separate from canonical source storage. Archived
audit bytes are immutable evidence records addressed by audit id and verified by
SHA-256 before a LIVE record may be removed from the console runtime.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Mapping, Protocol


AUDIT_ID_RE = re.compile(r"^audit-[0-9a-f]{16}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACCOUNT_RE = re.compile(r"^[a-z0-9]{3,24}$")
CONTAINER_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
LOCATOR_RE = re.compile(
    r"^azure-audit://(?P<account>[a-z0-9]+)/(?P<container>[a-z0-9-]+)"
    r"/audits/(?P<audit_id>audit-[0-9a-f]{16})\.json$"
)

ACCOUNT_ENV = "METIS_AUDIT_ARCHIVE_ACCOUNT"
CONTAINER_ENV = "METIS_AUDIT_ARCHIVE_CONTAINER"
DEFAULT_CONTAINER = "audit-archive"


class AuditArchiveStoreError(RuntimeError):
    """Fail-closed error raised for archive storage failures."""


class AuditArchiveStore(Protocol):
    def store_verified(
        self,
        *,
        audit_id: str,
        data: bytes,
        sha256: str,
    ) -> str: ...

    def load_verified(
        self,
        locator: str,
        *,
        expected_sha256: str,
    ) -> bytes: ...

    def delete_verified(self, locator: str) -> bool: ...


def _load_azure_blob_sdk() -> tuple[Any, Any]:
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise AuditArchiveStoreError("audit_archive_sdk_missing") from exc
    return DefaultAzureCredential, BlobServiceClient


def _archive_coordinates(environ: Mapping[str, str] | None = None) -> tuple[str, str]:
    env = environ if environ is not None else os.environ
    account = str(
        env.get(ACCOUNT_ENV, "")
        or env.get("G2_STORAGE_ACCOUNT", "")
        or ""
    ).strip()
    container = str(env.get(CONTAINER_ENV, "") or DEFAULT_CONTAINER).strip()
    if ACCOUNT_RE.fullmatch(account) is None:
        raise AuditArchiveStoreError("audit_archive_account_invalid")
    if CONTAINER_RE.fullmatch(container) is None:
        raise AuditArchiveStoreError("audit_archive_container_invalid")
    return account, container


def build_audit_archive_locator(
    *,
    account: str,
    container: str,
    audit_id: str,
) -> str:
    safe_account = str(account or "").strip()
    safe_container = str(container or "").strip()
    safe_audit_id = str(audit_id or "").strip()
    if ACCOUNT_RE.fullmatch(safe_account) is None:
        raise AuditArchiveStoreError("audit_archive_account_invalid")
    if CONTAINER_RE.fullmatch(safe_container) is None:
        raise AuditArchiveStoreError("audit_archive_container_invalid")
    if AUDIT_ID_RE.fullmatch(safe_audit_id) is None:
        raise AuditArchiveStoreError("audit_archive_id_invalid")
    return (
        f"azure-audit://{safe_account}/{safe_container}/audits/"
        f"{safe_audit_id}.json"
    )


class AzureAuditArchiveStore:
    """Verified Azure Blob adapter for complete audit JSON records."""

    def __init__(
        self,
        *,
        account: str | None = None,
        container: str | None = None,
        environ: Mapping[str, str] | None = None,
        blob_service_client: Any | None = None,
    ) -> None:
        env = environ if environ is not None else os.environ
        self.account = str(
            account
            or env.get(ACCOUNT_ENV, "")
            or env.get("G2_STORAGE_ACCOUNT", "")
            or ""
        ).strip()
        self.container = str(
            container
            or env.get(CONTAINER_ENV, "")
            or DEFAULT_CONTAINER
        ).strip()
        if ACCOUNT_RE.fullmatch(self.account) is None:
            raise AuditArchiveStoreError("audit_archive_account_invalid")
        if CONTAINER_RE.fullmatch(self.container) is None:
            raise AuditArchiveStoreError("audit_archive_container_invalid")
        if blob_service_client is None:
            DefaultAzureCredential, BlobServiceClient = _load_azure_blob_sdk()
            blob_service_client = BlobServiceClient(
                account_url=f"https://{self.account}.blob.core.windows.net",
                credential=DefaultAzureCredential(),
            )
        self._service = blob_service_client

    @staticmethod
    def _verify(data: bytes, expected_sha256: str) -> None:
        digest = str(expected_sha256 or "").strip().lower()
        if SHA256_RE.fullmatch(digest) is None:
            raise AuditArchiveStoreError("audit_archive_checksum_invalid")
        actual = hashlib.sha256(data).hexdigest()
        if actual != digest:
            raise AuditArchiveStoreError("audit_archive_checksum_mismatch")

    def _parse_locator(self, locator: str) -> dict[str, str]:
        match = LOCATOR_RE.fullmatch(str(locator or "").strip())
        if match is None:
            raise AuditArchiveStoreError("audit_archive_locator_invalid")
        parts = match.groupdict()
        if parts["account"] != self.account or parts["container"] != self.container:
            raise AuditArchiveStoreError("audit_archive_locator_invalid")
        return parts

    def _blob_client(self, audit_id: str) -> Any:
        if AUDIT_ID_RE.fullmatch(str(audit_id or "").strip()) is None:
            raise AuditArchiveStoreError("audit_archive_id_invalid")
        return self._service.get_blob_client(
            container=self.container,
            blob=f"audits/{audit_id}.json",
        )

    def store_verified(
        self,
        *,
        audit_id: str,
        data: bytes,
        sha256: str,
    ) -> str:
        safe_id = str(audit_id or "").strip()
        self._verify(data, sha256)
        locator = build_audit_archive_locator(
            account=self.account,
            container=self.container,
            audit_id=safe_id,
        )
        blob = self._blob_client(safe_id)
        try:
            blob.upload_blob(
                data,
                overwrite=False,
                metadata={"sha256": sha256, "audit_id": safe_id},
            )
        except Exception as exc:
            if exc.__class__.__name__ != "ResourceExistsError":
                raise AuditArchiveStoreError("audit_archive_upload_failed") from exc
        try:
            stored = bytes(blob.download_blob().readall())
        except Exception as exc:
            raise AuditArchiveStoreError("audit_archive_readback_failed") from exc
        self._verify(stored, sha256)
        if stored != data:
            raise AuditArchiveStoreError("audit_archive_readback_mismatch")
        return locator

    def load_verified(
        self,
        locator: str,
        *,
        expected_sha256: str,
    ) -> bytes:
        parts = self._parse_locator(locator)
        blob = self._blob_client(parts["audit_id"])
        try:
            data = bytes(blob.download_blob().readall())
        except Exception as exc:
            raise AuditArchiveStoreError("audit_archive_download_failed") from exc
        self._verify(data, expected_sha256)
        return data

    def delete_verified(self, locator: str) -> bool:
        parts = self._parse_locator(locator)
        blob = self._blob_client(parts["audit_id"])
        try:
            blob.delete_blob(delete_snapshots="include")
        except Exception as exc:
            if exc.__class__.__name__ == "ResourceNotFoundError":
                return False
            raise AuditArchiveStoreError("audit_archive_delete_failed") from exc
        return True
