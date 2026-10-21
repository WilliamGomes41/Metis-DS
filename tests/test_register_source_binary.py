from __future__ import annotations

from pathlib import Path

import pytest

from src.g2_source_store import build_g2_locator
from src.integrity_kernel import sha256_file
from src.register_source_binary import build_record, update_registry


def _record(path: Path, source_id: str = "source-1"):
    return build_record(
        path,
        source_id=source_id,
        title="Canonical test source",
        source_url="https://example.test/source.pdf",
        source_version="1.0",
        content_type="application/pdf",
        acquisition_method="official_download",
        acquired_at="2026-08-22T12:00:00Z",
    )


def test_build_record_hashes_exact_bytes(tmp_path: Path):
    source = (tmp_path / "source.pdf").resolve()
    source.write_bytes(b"%PDF-1.7\nexact-test-bytes\n")
    record = _record(source)
    assert record["source_checksum"] == sha256_file(source)
    assert record["size_bytes"] == source.stat().st_size
    assert record["integrity_status"] == "verified_local"
    assert record["binary_path"] == str(source)
    assert record["immutable_storage_locator"] is None
    assert record["publication_eligibility"] == "blocked_pending_immutable_storage"


def test_immutable_locator_opens_transform_eligibility(tmp_path: Path):
    source = (tmp_path / "source.pdf").resolve()
    source.write_bytes(b"%PDF-1.7\nexact-test-bytes\n")
    locator = build_g2_locator(sha256=sha256_file(source), filename="source.pdf")
    record = build_record(
        source,
        source_id="source-1",
        title="Canonical test source",
        source_url="https://example.test/source.pdf",
        source_version="1.0",
        content_type="application/pdf",
        acquisition_method="official_download",
        acquired_at="2026-08-22T12:00:00Z",
        immutable_storage_locator=locator,
    )
    assert record["integrity_status"] == "verified"
    assert record["publication_eligibility"] == "eligible_for_transform_and_review"
    assert record["immutable_storage_locator"] == locator


def test_build_record_rejects_missing_binary(tmp_path: Path):
    with pytest.raises(ValueError, match="source_binary_missing"):
        _record((tmp_path / "missing.pdf").resolve())


def test_registry_fails_closed_on_same_id_with_changed_bytes(tmp_path: Path):
    first = (tmp_path / "first.pdf").resolve()
    second = (tmp_path / "second.pdf").resolve()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    registry = update_registry({"registry_version": "1.0", "sources": []}, _record(first))
    with pytest.raises(ValueError, match="source_id_checksum_conflict_requires_new_source_version"):
        update_registry(registry, _record(second))
