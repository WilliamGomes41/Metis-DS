"""P0 evidence: published source bytes are authoritative only when Blob verifies.

# release-control-evidence: opslag azure blob source authority readback sha256
# release-control-evidence: scope/belofte
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from src.azure_authoritative_publication_console_v1 import AzureAuthoritativePublicationConsole
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_v1 import ConsoleError

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_releasebewijs,
]


class _CanonicalStore:
    def __init__(self, *, snapshot_id: str, sha256: str, locator: str) -> None:
        self.snapshot_id = snapshot_id
        self.sha256 = sha256
        self.locator = locator

    def active_publication_rows(self) -> list[dict[str, Any]]:
        return [{"snapshot_id": self.snapshot_id}]

    def release_for_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        if snapshot_id != self.snapshot_id:
            return None
        return {
            "snapshot_id": self.snapshot_id,
            "source_sha256": self.sha256,
            "source_locator": self.locator,
        }


class _SourceStore:
    def __init__(self, data: bytes | None) -> None:
        self.data = data
        self.reads: list[str] = []

    def load_verified(self, locator: str) -> bytes:
        self.reads.append(locator)
        if self.data is None:
            raise G2SourceStoreError("canonical_source_missing")
        return self.data


def _console(tmp_path: Path, *, expected: bytes, actual: bytes | None) -> tuple[AzureAuthoritativePublicationConsole, _SourceStore]:
    digest = hashlib.sha256(expected).hexdigest()
    locator = build_g2_locator(sha256=digest, filename="source.pdf")
    source = _SourceStore(actual)
    canonical = _CanonicalStore(snapshot_id="snap-0123456789abcdef-01234567", sha256=digest, locator=locator)
    console = AzureAuthoritativePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
        immutable_source_store=source,  # type: ignore[arg-type]
        canonical_publication_store=canonical,  # type: ignore[arg-type]
    )
    return console, source


def test_active_publication_source_is_read_back_from_blob_and_sha256_verified(tmp_path: Path) -> None:
    expected = b"published canonical source bytes"
    console, source = _console(tmp_path, expected=expected, actual=expected)

    assert console._verify_active_authority_sources() == 1
    assert len(source.reads) == 1


def test_missing_blob_blocks_authoritative_publication_rebuild(tmp_path: Path) -> None:
    console, _source = _console(tmp_path, expected=b"expected", actual=None)

    with pytest.raises(ConsoleError) as caught:
        console._verify_active_authority_sources()
    assert caught.value.code == "azure_blob_source_readback_failed"


def test_sha256_mismatch_blocks_authoritative_publication_rebuild(tmp_path: Path) -> None:
    console, _source = _console(tmp_path, expected=b"expected", actual=b"different")

    with pytest.raises(ConsoleError) as caught:
        console._verify_active_authority_sources()
    assert caught.value.code == "azure_blob_source_sha256_mismatch"


def test_missing_blob_store_blocks_authoritative_publication_rebuild(tmp_path: Path) -> None:
    expected = b"expected"
    digest = hashlib.sha256(expected).hexdigest()
    locator = build_g2_locator(sha256=digest, filename="source.pdf")
    canonical = _CanonicalStore(
        snapshot_id="snap-0123456789abcdef-01234567",
        sha256=digest,
        locator=locator,
    )
    console = AzureAuthoritativePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
        immutable_source_store=None,
        canonical_publication_store=canonical,  # type: ignore[arg-type]
    )

    with pytest.raises(ConsoleError) as caught:
        console._verify_active_authority_sources()
    assert caught.value.code == "azure_blob_source_store_required"
