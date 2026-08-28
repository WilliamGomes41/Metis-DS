from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_4_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v24_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.4.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(DELTA)
    assert manifest["commit_sha"] == "725987260cd345a92d38b44aaa6c219e8b72fc78"
    assert manifest["approval_date"] == "2026-08-27"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v24_remains_an_approved_component_of_current_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")

    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.4.0" in delta
    assert "docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md" in root_protocol
    assert "Protocol v2.4.0" in root_protocol
    assert "**Geldend protocol:** v2.8.0" in handoff
    assert "Fase 6 — Externe integratiepilot" in roadmap


def test_v24_limits_mvp_to_source_navigation_and_knowledge_response() -> None:
    delta = _read(DELTA)
    assert "U1 Source navigation" in delta
    assert "U2 Knowledge response" in delta
    assert "The first V&VN DS MVP is limited to U1 and U2." in delta
    assert "U3 Deterministic decision rule" in delta
    assert "U4 Patient-specific recommendation" in delta
    assert "U5 Predictive or trained model" in delta


def test_v24_keeps_frontend_generation_and_patient_data_outside_ds_mvp() -> None:
    delta = _read(DELTA)
    assert "A reference application MAY consume the Product API" in delta
    assert "it is a separate consuming product" in delta
    assert "MUST NOT process patient records" in delta
    assert "MUST NOT be offered or described as general model-training data" in delta


def test_v24_requires_external_use_and_withdrawal_controls() -> None:
    delta = _read(DELTA)
    required = (
        "consumer and accountable owner",
        "declared use mode and intended users",
        "update, supersession and withdrawal handling",
        "incident, error and misuse reporting",
        "Technical access MUST NOT be treated as permission",
        "consumer notification",
    )
    for phrase in required:
        assert phrase in delta
