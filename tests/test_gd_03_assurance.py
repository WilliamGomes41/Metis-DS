from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = ROOT / "docs" / "GOVERNANCE.md"
ARTEFACT = ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json"

EXPECTED_MATRIX = {
    "C3": {
        "class_name": "Canonical/review",
        "minimum": 2,
        "required_roles": ["clinical", "technical"],
    },
    "C4": {
        "class_name": "Retrieval/answerability",
        "minimum": 2,
        "required_roles": ["evaluation", "technical"],
    },
    "C5": {
        "class_name": "Publication/security",
        "minimum": 2,
        "required_roles": ["security/operations", "technical"],
    },
    "C6": {
        "class_name": "Generation",
        "minimum": 3,
        "required_roles": ["clinical", "technical", "safety/evaluation"],
    },
}

OPEN_SIBLINGS = ("GD-01", "GD-02", "GD-04", "GD-05", "GD-06", "GD-07")


def test_gd03_assurance_matches_governance_bytes_and_is_established() -> None:
    manifest = json.loads(ARTEFACT.read_text(encoding="utf-8"))
    assert manifest["decision_id"] == "GD-03"
    assert manifest["status"] == "ESTABLISHED"
    assert manifest["status"] != "OPEN"
    assert manifest["decision_date"] == "2026-08-27"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["owner"] == "project owner V&VN Data Services"
    assert manifest["protocol_version"] == "2.4.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_2.md"
    assert manifest["evidence_path"] == "docs/GOVERNANCE.md"
    assert manifest["evidence_url"] == "docs/GOVERNANCE.md"
    assert manifest["governance_sha256"] == sha256_file(GOVERNANCE)
    assert manifest["conformance_effect"] == "does_not_override_gate_status"
    assert manifest["named_reviewers_status"] == "later_staffing_step_does_not_keep_decision_open"
    assert manifest["reviewer_matrix"] == EXPECTED_MATRIX
    assert manifest["open_sibling_decisions"] == list(OPEN_SIBLINGS)
    constraints = manifest["constraints"]
    assert constraints["reviewers_independent_of_author"] is True
    assert constraints["same_exact_commit_or_snapshot"] is True
    assert constraints["ai_grok_bot_metis_must_not_count_as_required_c3_c6_reviewer"] is True
    assert constraints["ai_grok_bot_metis_must_not_approve"] is True
    assert constraints["ai_grok_bot_metis_must_not_publish"] is True


def test_gd03_human_record_and_handoff_keep_other_decisions_open() -> None:
    governance = GOVERNANCE.read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")

    assert "| GD-03 |" in governance
    assert "ESTABLISHED" in governance
    assert "GD-03 is ESTABLISHED" in handoff
    assert "GD-03 is niet langer OPEN" in handoff
    assert "geen nieuwe protocolversie" in handoff
    assert "GD-03 reviewervereisten ESTABLISHED" in roadmap

    for decision_id in OPEN_SIBLINGS:
        assert f"| {decision_id} |" in governance
        assert decision_id in handoff

    assert "OPEN-besluiten mogen niet als established" in governance
    assert "AI, Grok Bot en Metis MUST NOT meetellen" in governance
    assert "| C3 Canonical/review | 2 | clinical + technical |" in governance
    assert "| C4 Retrieval/answerability | 2 | evaluation + technical |" in governance
    assert "| C5 Publication/security | 2 | security/operations + technical |" in governance
    assert "| C6 Generation | 3 | clinical + technical + safety/evaluation |" in governance
