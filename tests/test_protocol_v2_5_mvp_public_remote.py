from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_5_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v25_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.5.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(DELTA)
    assert manifest["commit_sha"] == "118123f1273054f0a420a72c6a21d2346af1a2b5"
    assert manifest["approval_date"] == "2026-08-27"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v25_remains_an_approved_component_of_current_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.5.0" in delta
    assert "docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md" in root_protocol
    assert "Protocol v2.5.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.4.0" not in root_protocol
    assert "**Geldend protocol:** v2.13.0" in handoff
    assert "Protocol v2.5.0" in roadmap


def test_v25_relaxes_private_remote_only_for_declared_mvp_period() -> None:
    delta = _read(DELTA)
    assert "v2.2 §4.1" in delta
    assert "WilliamGomes41/VENVN-DS" in delta
    assert "the authoritative software remote MAY be public" in delta
    assert "relaxed **only** for a declared MVP period" in delta
    assert "Public hosting is not the production baseline." in delta
    assert "a new plan MUST restore private hosting" in delta


def test_v25_keeps_fail_closed_exclusions_and_gitignore() -> None:
    delta = _read(DELTA)
    gitignore = _read(ROOT / ".gitignore")
    tenants = (ROOT / "config" / "tenants.v1.json").read_text(encoding="utf-8")

    for phrase in (
        "Canonical source binaries",
        "MUST NOT be committed to Git",
        "config/tenants.v1.json",
        "Confidential review artefacts MUST NOT be committed",
        "Runtime databases",
        "`.gitignore` already covers these classes and MUST be kept",
    ):
        assert phrase in delta

    for pattern in (
        "*.pem",
        "*.key",
        "*.pdf",
        "*.sqlite",
        "sources/private/",
        "output/runtime/",
        "output/*_review.csv",
    ):
        assert pattern in gitignore

    assert '"tenants": []' in tenants


def test_v25_records_g1_protection_without_waiting_on_github_setting() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    required = (
        "required CI checks `test (3.12)` and `test (3.13)`",
        "require a pull request before merging",
        "no force-push to `main`",
        "no deleting `main`",
        "This protocol pull request does not wait for that GitHub setting to exist",
        "G1 remains `BLOCKED`",
    )
    for phrase in required:
        assert phrase in delta
    assert "G1" in handoff
    assert "BLOCKED" in handoff


def test_v25_accepts_software_artefacts_but_not_canonical_source() -> None:
    delta = _read(DELTA)
    assert "Fixtures, holdouts and already-tracked historical artefacts under `output/` MAY remain" in delta
    assert "not canonical source binaries" in delta
    assert "Canonical source HTML/PDF still MUST NOT be committed" in delta


def test_v25_requires_private_security_reporting_for_public_mvp() -> None:
    delta = _read(DELTA)
    security = _read(ROOT / "SECURITY.md")
    assert "GitHub private vulnerability reporting" in delta
    assert "MUST NOT post source bytes, credentials, unpublished knowledge" in delta
    assert "GitHub private vulnerability reporting" in security
    assert "MUST NOT post source bytes, credentials, unpublished knowledge" in security
    assert "the authoritative remote MAY be public" in security
    assert "must not be posted in public issues" not in security


def test_v25_is_c5_with_owner_approval_and_retrospective_review() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    assert "**Highest change class:** C5" in delta
    assert "Named C5 reviewers are not yet staffed" in delta
    assert "The project owner approves this delta" in delta
    assert "Retrospective independent technical and security/operations review remains due" in delta
    assert "does not reopen GD-03" in delta
    assert "GD-03 is ESTABLISHED" in handoff
    assert "GD-03 is niet langer OPEN" in handoff
    assert "geen nieuwe protocolversie" in handoff
