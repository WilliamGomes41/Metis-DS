from __future__ import annotations

from pathlib import Path

import pytest

from src.protocol_approval_manifest import build_manifest


def test_approved_protocol_manifest_is_commit_bound(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_2.md"
    protocol.write_text(
        "**Status:** Approved for project use\n**Protocol version:** 2.2.0\n",
        encoding="utf-8",
    )
    manifest = build_manifest(protocol, "a" * 40)
    assert manifest["protocol_version"] == "2.2.0"
    assert manifest["commit_sha"] == "a" * 40
    assert len(str(manifest["protocol_sha256"])) == 64


def test_draft_protocol_cannot_receive_approval_manifest(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_2.md"
    protocol.write_text("**Status:** Draft\n**Protocol version:** 2.2.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="protocol_not_approved"):
        build_manifest(protocol, "a" * 40)


def test_manifest_rejects_non_commit_reference(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL_V2_2.md"
    protocol.write_text(
        "**Status:** Approved for project use\n**Protocol version:** 2.2.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="commit_sha_invalid"):
        build_manifest(protocol, "main")
