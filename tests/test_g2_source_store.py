from __future__ import annotations

from pathlib import Path

import pytest

from src.g2_source_store import (
    build_g2_locator,
    g2_gate_status,
    is_g2_locator,
    load_g2_store,
    parse_g2_locator,
)
from src.integrity_kernel import sha256_file
from src.register_source_binary import build_record


DIGEST = "a" * 64


def test_store_coordinates_match_venvn_blob() -> None:
    store = load_g2_store()
    assert store["storage_account"] == "aidataservice"
    assert store["container"] == "canonical-sources"
    assert store["region"] == "westeurope"
    assert store["resource_group"] == "AI_Dataservice"
    assert store["subscription_id"] == "8c829c96-1784-4947-8a2b-92027c51fec9"
    assert store["public_access"] == "private"
    assert store["g2_status"] == "BLOCKED"
    assert g2_gate_status() == "BLOCKED"


def test_locator_roundtrip() -> None:
    locator = build_g2_locator(sha256=DIGEST, filename="source.pdf")
    assert locator == f"azure://aidataservice/canonical-sources/{DIGEST}/source.pdf"
    assert is_g2_locator(locator)
    parsed = parse_g2_locator(locator)
    assert parsed is not None
    assert parsed["sha256"] == DIGEST
    assert parsed["filename"] == "source.pdf"


def test_foreign_or_empty_locator_is_rejected() -> None:
    assert is_g2_locator(None) is False
    assert is_g2_locator("") is False
    assert is_g2_locator("azure://canonical/sha256/test/source.pdf") is False
    assert is_g2_locator(f"azure://otheraccount/canonical-sources/{DIGEST}/source.pdf") is False
    assert is_g2_locator("https://aidataservice.blob.core.windows.net/canonical-sources/x") is False


def test_build_locator_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="g2_locator_checksum_invalid"):
        build_g2_locator(sha256="abc", filename="source.pdf")
    with pytest.raises(ValueError, match="g2_locator_filename_invalid"):
        build_g2_locator(sha256=DIGEST, filename="../source.pdf")


def test_register_requires_matching_g2_locator(tmp_path: Path) -> None:
    source = (tmp_path / "source.pdf").resolve()
    source.write_bytes(b"%PDF-1.7\nexact-test-bytes\n")
    digest = sha256_file(source)
    locator = build_g2_locator(sha256=digest, filename="source.pdf")
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
    assert record["publication_eligibility"] == "eligible_for_transform_and_review"
    assert record["immutable_storage_locator"] == locator

    with pytest.raises(ValueError, match="g2_locator_invalid"):
        build_record(
            source,
            source_id="source-1",
            title="Canonical test source",
            source_url="https://example.test/source.pdf",
            source_version="1.0",
            content_type="application/pdf",
            acquisition_method="official_download",
            acquired_at="2026-08-22T12:00:00Z",
            immutable_storage_locator="azure://canonical/sha256/test/source.pdf",
        )
