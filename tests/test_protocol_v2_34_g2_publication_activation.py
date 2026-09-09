from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_34_G2_PUBLICATION_ACTIVATION_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_34_approval.json"


def test_v234_owner_approval_matches_exact_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.34.0"
    assert manifest["protocol_path"] == DELTA.relative_to(ROOT).as_posix()
    assert manifest["protocol_sha256"] == hashlib.sha256(DELTA.read_bytes()).hexdigest()
    assert manifest["approval_date"] == "2026-09-09"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "conditionally_activates_g2_publication"


def test_v234_opens_only_a_verified_conditional_gate() -> None:
    text = DELTA.read_text(encoding="utf-8")
    assert "SUPERSEDES only earlier statements that G2 and `publish()` MUST remain unconditionally BLOCKED" in text
    assert "Publication is not generally open" in text
    for requirement in (
        "explicitly confirms the publication action",
        "current `approve` review binding",
        "high-risk four-eyes checks pass",
        "schema-valid",
        "immutable source store can read the blob",
        "SHA-256",
        "derived retrieval projection",
    ):
        assert requirement in text
    assert "app setting, locator-shaped string, UI choice" in text


def test_v234_requires_atomic_evidence_and_rollback() -> None:
    text = DELTA.read_text(encoding="utf-8")
    assert "immutable release manifest" in text
    assert "replaced atomically" in text
    assert "`release_published`" in text
    assert "failed cutover MUST restore" in text
    assert "already published snapshot MUST fail closed" in text
    assert "MUST NOT be silently rewritten by publication" in text


def test_root_protocol_and_roadmap_point_to_v234() -> None:
    protocol = (ROOT / "PROTOCOL.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    assert "baseline is Protocol v2.34.0 plus v2.33.0" in roadmap
    assert "aangevuld met Protocol v2.34.0 plus Protocol v2.33.0" in protocol
    assert "PROTOCOL_V2_34_G2_PUBLICATION_ACTIVATION_DELTA.md" in protocol
    assert "Dit SUPERSEDEERT alleen oudere onvoorwaardelijke `publish()`-BLOCKED statusregels" in roadmap
