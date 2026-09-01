from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.g2_source_store import AzureBlobSourceStore, G2SourceStoreError
from src.operations_console_v1 import ConsoleError, OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data" / "fixtures" / "source2_html_factory_fixture.html"


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
        return _Download(self.service.data[self.name])


class _BlobService:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def get_blob_client(self, *, container: str, blob: str) -> _Blob:
        assert container == "canonical-sources"
        return _Blob(self, blob)


class _FailingStore:
    def store_verified(self, **_kwargs: object) -> str:
        raise G2SourceStoreError("canonical_source_upload_failed")

    def load_verified(self, _locator: str) -> bytes:
        raise AssertionError("not reached")


def _console(tmp_path: Path, store: object) -> tuple[OperationsConsole, dict[str, str]]:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "source-cache",
        runtime=tmp_path / "runtime",
        immutable_source_store=store,  # type: ignore[arg-type]
    )
    researcher = console.create_account(
        "researcher",
        "researcher-password",
        ("researcher", "reviewer"),
    )
    reviewer = console.create_account("reviewer", "reviewer-password", ("reviewer",))
    return console, {
        "researcher": researcher["account_id"],
        "reviewer": reviewer["account_id"],
    }


def _ingest(console: OperationsConsole, accounts: dict[str, str]) -> dict[str, object]:
    return console.ingest(
        actor_id=accounts["researcher"],
        filename="source.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Canonical source",
        version="1.0",
        date="2026-09-01",
        live_url="https://example.test/source",
        class_="richtlijn",
        family="test-family",
        named_reviewers=[accounts["reviewer"]],
    )


def test_azure_adapter_uploads_and_reads_back_exact_bytes() -> None:
    service = _BlobService()
    store = AzureBlobSourceStore(blob_service_client=service)
    data = b"exact canonical bytes"
    digest = hashlib.sha256(data).hexdigest()

    locator = store.store_verified(data=data, sha256=digest, filename="source.pdf")
    assert locator == f"azure://aidataservice/canonical-sources/{digest}/source.pdf"
    assert store.load_verified(locator) == data

    # Idempotent retry reads and verifies the already-present content.
    assert store.store_verified(data=data, sha256=digest, filename="source.pdf") == locator


def test_azure_adapter_rejects_corrupt_readback() -> None:
    service = _BlobService()
    store = AzureBlobSourceStore(blob_service_client=service)
    data = b"expected"
    digest = hashlib.sha256(data).hexdigest()
    service.data[f"{digest}/source.pdf"] = b"corrupt"

    with pytest.raises(G2SourceStoreError, match="canonical_source_checksum_mismatch"):
        store.store_verified(data=data, sha256=digest, filename="source.pdf")


def test_azure_adapter_rejects_noncanonical_filename() -> None:
    store = AzureBlobSourceStore(blob_service_client=_BlobService())
    data = b"expected"
    digest = hashlib.sha256(data).hexdigest()

    with pytest.raises(ValueError, match="g2_locator_filename_invalid"):
        store.store_verified(data=data, sha256=digest, filename="../source.pdf")


def test_console_binds_azure_locator_and_recovers_missing_local_cache(tmp_path: Path) -> None:
    store = AzureBlobSourceStore(blob_service_client=_BlobService())
    console, accounts = _console(tmp_path, store)
    receipt = _ingest(console, accounts)

    assert str(receipt["immutable_storage_locator"]).startswith(
        "azure://aidataservice/canonical-sources/"
    )
    assert receipt["publication_eligibility"] == "eligible_for_transform_and_review"

    envelope = console._envelope(str(receipt["snapshot_id"]))
    freeze_path = Path(envelope["binary_path"])
    freeze_path.unlink()
    object_id = next(
        row["object_id"]
        for row in console.snapshot_objects(str(receipt["snapshot_id"]))
        if row["object_type"] != "document"
    )
    passage = console.open_source_passage(
        snapshot_id=str(receipt["snapshot_id"]),
        object_id=object_id,
    )
    assert passage
    assert freeze_path.read_bytes() == HTML_FIXTURE.read_bytes()


def test_console_fails_closed_before_creating_snapshot_when_upload_fails(tmp_path: Path) -> None:
    console, accounts = _console(tmp_path, _FailingStore())

    with pytest.raises(ConsoleError, match="immutable_source_storage_failed"):
        _ingest(console, accounts)
    assert console._envelopes == {}
