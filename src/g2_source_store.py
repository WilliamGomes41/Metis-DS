"""G2 canonical source-store coordinates and verified Azure Blob adapter.

The adapter authenticates with Microsoft Entra ID through
``DefaultAzureCredential``. Storage keys, connection strings and SAS tokens are
deliberately unsupported.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "g2_source_store.v1.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
LOCATOR_RE = re.compile(
    r"^azure://(?P<account>[a-z0-9]+)/(?P<container>[a-z0-9-]+)"
    r"/(?P<sha256>[0-9a-f]{64})/(?P<filename>[A-Za-z0-9._-]+)$"
)


def load_g2_store() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def g2_gate_status() -> str:
    store = load_g2_store()
    status = str(store.get("g2_status") or "BLOCKED")
    return status if status == "BLOCKED" else "BLOCKED"


def build_g2_locator(*, sha256: str, filename: str) -> str:
    digest = sha256.strip().lower()
    raw = filename.replace("\\", "/")
    name = Path(raw).name
    if not SHA256_RE.fullmatch(digest):
        raise ValueError("g2_locator_checksum_invalid")
    if raw != name or not FILENAME_RE.fullmatch(name):
        raise ValueError("g2_locator_filename_invalid")
    store = load_g2_store()
    return f"azure://{store['storage_account']}/{store['container']}/{digest}/{name}"


def parse_g2_locator(locator: str | None) -> dict[str, str] | None:
    if not locator or not str(locator).strip():
        return None
    match = LOCATOR_RE.fullmatch(str(locator).strip())
    if match is None:
        return None
    parts = match.groupdict()
    store = load_g2_store()
    if parts["account"] != store["storage_account"]:
        return None
    if parts["container"] != store["container"]:
        return None
    return parts


def is_g2_locator(locator: str | None) -> bool:
    return parse_g2_locator(locator) is not None


class G2SourceStoreError(RuntimeError):
    """Fail-closed error raised when canonical bytes cannot be verified."""


class ImmutableSourceStore(Protocol):
    def store_verified(self, *, data: bytes, sha256: str, filename: str) -> str: ...

    def load_verified(self, locator: str) -> bytes: ...


class AzureBlobSourceStore:
    """Content-addressed canonical source storage backed by Azure Blob."""

    def __init__(self, *, blob_service_client: Any | None = None) -> None:
        store = load_g2_store()
        self.account = str(store["storage_account"])
        self.container = str(store["container"])
        if blob_service_client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.storage.blob import BlobServiceClient
            except ImportError as exc:  # pragma: no cover - deployment dependency guard
                raise G2SourceStoreError("azure_blob_sdk_missing") from exc
            credential = DefaultAzureCredential()
            blob_service_client = BlobServiceClient(
                account_url=f"https://{self.account}.blob.core.windows.net",
                credential=credential,
            )
        self._service = blob_service_client

    @staticmethod
    def _verify(data: bytes, expected_sha256: str) -> None:
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256:
            raise G2SourceStoreError("canonical_source_checksum_mismatch")

    def _blob_client(self, *, sha256: str, filename: str) -> Any:
        locator = build_g2_locator(sha256=sha256, filename=filename)
        parsed = parse_g2_locator(locator)
        if parsed is None:  # defensive: build and parse must stay symmetric
            raise G2SourceStoreError("canonical_source_locator_invalid")
        return self._service.get_blob_client(
            container=self.container,
            blob=f"{parsed['sha256']}/{parsed['filename']}",
        )

    def store_verified(self, *, data: bytes, sha256: str, filename: str) -> str:
        locator = build_g2_locator(sha256=sha256, filename=filename)
        parsed = parse_g2_locator(locator)
        if parsed is None:  # defensive: build and parse must stay symmetric
            raise G2SourceStoreError("canonical_source_locator_invalid")
        name = parsed["filename"]
        self._verify(data, sha256)
        blob = self._blob_client(sha256=sha256, filename=name)
        try:
            blob.upload_blob(
                data,
                overwrite=False,
                metadata={"sha256": sha256},
            )
        except Exception as exc:
            # A content-addressed object may already exist. In every case the
            # authoritative read-back below decides whether it is acceptable.
            if exc.__class__.__name__ != "ResourceExistsError":
                raise G2SourceStoreError("canonical_source_upload_failed") from exc
        try:
            stored = bytes(blob.download_blob().readall())
        except Exception as exc:
            raise G2SourceStoreError("canonical_source_readback_failed") from exc
        self._verify(stored, sha256)
        return locator

    def load_verified(self, locator: str) -> bytes:
        parsed = parse_g2_locator(locator)
        if parsed is None:
            raise G2SourceStoreError("canonical_source_locator_invalid")
        blob = self._blob_client(sha256=parsed["sha256"], filename=parsed["filename"])
        try:
            data = bytes(blob.download_blob().readall())
        except Exception as exc:
            raise G2SourceStoreError("canonical_source_download_failed") from exc
        self._verify(data, parsed["sha256"])
        return data
