from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs" / "PROTOCOL_V2_3_TECHNICAL_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_3_approval.json"
INFRA = ROOT / "config" / "infrastructure_manifest.v1.json"


def test_v23_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.3.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(PROTOCOL)
    assert manifest["approval_date"] == "2026-08-25"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"
    assert len(manifest["commit_sha"]) == 40


def test_v23_remains_an_approved_component_of_current_baseline() -> None:
    protocol = PROTOCOL.read_text(encoding="utf-8")
    root_protocol = (ROOT / "PROTOCOL.md").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    assert "**Status:** Approved for project use" in protocol
    assert "**Protocol delta version:** 2.3.0" in protocol
    assert "docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md" in root_protocol
    assert "**Geldend protocol:** v2.8.0" in handoff


def test_infrastructure_baseline_is_approved_without_overstating_azure() -> None:
    manifest = json.loads(INFRA.read_text(encoding="utf-8"))
    assert manifest["status"] == "approved"
    assert manifest["protocol_target"] == "2.3.0"
    azure_required = [
        item
        for item in manifest["dependencies"]
        if item["environment"] == "azure_dev"
        and item["requirement_status"] == "required"
    ]
    assert azure_required
    assert any(
        item["implementation_status"] in {"decision_open", "selected_not_provisioned", "blocked"}
        for item in azure_required
    )
