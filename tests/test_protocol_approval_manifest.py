from __future__ import annotations

from pathlib import Path

import pytest

from src.protocol_approval_manifest import build_manifest


def test_approved_v22_protocol_manifest_is_commit_bound(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_2.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol version:** 2.2.0\n"
        "**Approval date:** 2026-08-22\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "a" * 40)
    assert manifest["protocol_version"] == "2.2.0"
    assert manifest["approval_date"] == "2026-08-22"
    assert manifest["commit_sha"] == "a" * 40
    assert len(str(manifest["protocol_sha256"])) == 64


def test_approved_v23_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_3_TECHNICAL_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.3.0\n"
        "**Approval date:** 2026-08-25\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "b" * 40)
    assert manifest["protocol_version"] == "2.3.0"
    assert manifest["approval_date"] == "2026-08-25"
    assert manifest["commit_sha"] == "b" * 40


def test_approved_v25_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.5.0\n"
        "**Approval date:** 2026-08-27\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "c" * 40)
    assert manifest["protocol_version"] == "2.5.0"
    assert manifest["approval_date"] == "2026-08-27"
    assert manifest["commit_sha"] == "c" * 40


def test_approved_v26_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.6.0\n"
        "**Approval date:** 2026-08-28\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "d" * 40)
    assert manifest["protocol_version"] == "2.6.0"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["commit_sha"] == "d" * 40


def test_approved_v27_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.7.0\n"
        "**Approval date:** 2026-08-28\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "e" * 40)
    assert manifest["protocol_version"] == "2.7.0"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["commit_sha"] == "e" * 40


def test_approved_v28_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.8.0\n"
        "**Approval date:** 2026-08-28\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "f" * 40)
    assert manifest["protocol_version"] == "2.8.0"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["commit_sha"] == "f" * 40


def test_approved_v29_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_9_CONSOLE_UX_BRAND_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.9.0\n"
        "**Approval date:** 2026-08-28\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "a" * 40)
    assert manifest["protocol_version"] == "2.9.0"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["commit_sha"] == "a" * 40


def test_approved_v210_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_10_CONSOLE_NAV_ACCOUNTS_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.10.0\n"
        "**Approval date:** 2026-08-28\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "b" * 40)
    assert manifest["protocol_version"] == "2.10.0"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["commit_sha"] == "b" * 40


def test_approved_v211_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_11_HTML_FREEZE_LOCATOR_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.11.0\n"
        "**Approval date:** 2026-08-28\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "c" * 40)
    assert manifest["protocol_version"] == "2.11.0"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["commit_sha"] == "c" * 40


def test_approved_v212_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_12_OBJECT_TYPE_REVIEW_PROJECTION_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.12.0\n"
        "**Approval date:** 2026-08-28\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "c" * 40)
    assert manifest["protocol_version"] == "2.12.0"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["commit_sha"] == "c" * 40


def test_approved_v213_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_13_ATOMIC_OBJECT_SEMANTICS_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.13.0\n"
        "**Approval date:** 2026-08-28\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "d" * 40)
    assert manifest["protocol_version"] == "2.13.0"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["commit_sha"] == "d" * 40


def test_approved_v215_delta_manifest_is_supported(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_15_INGEST_DATE_VERSION_REVIEW_LANES_DELTA.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol delta version:** 2.15.0\n"
        "**Approval date:** 2026-09-01\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "e" * 40)
    assert manifest["protocol_version"] == "2.15.0"
    assert manifest["approval_date"] == "2026-09-01"
    assert manifest["commit_sha"] == "e" * 40


def test_draft_protocol_cannot_receive_approval_manifest(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text(
        "**Status:** Draft\n"
        "**Protocol version:** 2.3.0\n"
        "**Approval date:** 2026-08-25\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="protocol_not_approved"):
        build_manifest(protocol, "a" * 40)


def test_manifest_requires_version_and_approval_date(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text("**Status:** Approved for project use\n", encoding="utf-8")
    with pytest.raises(ValueError, match="protocol_version_missing"):
        build_manifest(protocol, "a" * 40)

    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol version:** 2.3.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="approval_date_missing"):
        build_manifest(protocol, "a" * 40)


def test_manifest_rejects_non_commit_reference(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text(
        "**Status:** Approved for project use\n"
        "**Protocol version:** 2.3.0\n"
        "**Approval date:** 2026-08-25\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="commit_sha_invalid"):
        build_manifest(protocol, "main")
