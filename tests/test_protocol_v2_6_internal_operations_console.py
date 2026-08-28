from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_6_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v26_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.6.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(DELTA)
    assert manifest["commit_sha"] == "9614c4deec708933a5be87527e3c2e1c2679cd93"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v26_remains_an_approved_component_of_current_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.6.0" in delta
    assert "docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md" in root_protocol
    assert "Protocol v2.6.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.5.0" not in root_protocol
    assert "**Geldend protocol:** v2.8.0" in handoff
    assert "Protocol v2.6.0" in roadmap


def test_v26_hierarchy_remains_a_listed_baseline_component() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    delta = _read(DELTA)
    assert "docs/PROTOCOL_V2_2.md" in root_protocol
    assert "docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md" in root_protocol
    assert (
        "v2.2.0, v2.3.0, v2.4.0, v2.5.0 and this delta jointly form normative baseline v2.6.0"
        in delta
    )


def test_v26_scoped_supersession_keeps_care_frontend_forbidden() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "scoped supersession" in delta
    assert "no product frontend in this repository" in delta
    assert "An **internal operations console** MAY live in this repository" in delta
    for phrase in (
        "a care-app frontend",
        "a chatbot as a product surface",
        "an EPD/ECD UI",
        "a public website",
    ):
        assert phrase in delta
    assert "zorgapp-frontend" in root_protocol
    assert "EPD/ECD-UI" in root_protocol
    assert "zorgapp-frontend" in roadmap
    assert "De console is goedgekeurde scope, niet bestaande code" in root_protocol


def test_v26_states_four_rooms_independence_and_uploader_rule() -> None:
    delta = _read(DELTA)
    assert "The four rooms are not four buttons for one person" in delta
    assert "### 5.1 Ingest (mailbox)" in delta
    assert "### 5.2 Review" in delta
    assert "### 5.3 Publish" in delta
    assert "### 5.4 Analytics" in delta
    assert "The return loop is mandatory" in delta
    assert "The uploader MAY also be a reviewer" in delta
    assert "The uploader MUST NOT be the only required reviewer on that snapshot" in delta
    assert (
        "Publish stays BLOCKED until at least one other named reviewer has passed the same snapshot"
        in delta
    )
    assert "enforced in the console (accounts), not as a social rule" in delta
    assert "Publish is not the same click as ingest" in delta
    assert "Do not build analytics first" in delta
    assert "**Console MVP:** ingest + review-loop" in delta


def test_v26_forbids_chat_in_the_console() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    assert "Chat is not a room in this console" in delta
    assert "later consumer of the Product API" in delta
    assert "G7/C6" in delta
    assert "U1/U2" in delta
    assert "Chat hoort niet in de console" in handoff
    assert "A chatbot MUST NOT be added to the console" in delta


def test_v26_keeps_fail_closed_exclusions_and_gitignore() -> None:
    delta = _read(DELTA)
    gitignore = _read(ROOT / ".gitignore")
    tenants = (ROOT / "config" / "tenants.v1.json").read_text(encoding="utf-8")

    for phrase in (
        "Canonical source binaries",
        "MUST NOT be committed to Git",
        "config/tenants.v1.json",
        "Confidential review artefacts MUST NOT be committed",
        "Runtime databases",
        "GD-03 remains ESTABLISHED",
        "does not reopen GD-03",
        "AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT count as required reviewers",
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


def test_v26_records_identity_without_closing_g8() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    stack = _read(ROOT / "docs" / "STACK_SETUP_BASELINE.md")
    infra = json.loads((ROOT / "config" / "infrastructure_manifest.v1.json").read_text(encoding="utf-8"))
    assert "Accounts and roles are required" in delta
    assert "researcher" in delta
    assert "reviewer" in delta
    assert "publisher" in delta
    assert "No shared login for review or publish" in delta
    assert "internal identity, not public signup" in delta
    assert "does not by itself close G8 or provision Azure AD" in delta
    assert "subject to G0" in delta
    assert "G0 Azure DEV blijft `BLOCKED`" in handoff
    assert "Vercel, Neon and a hosted LLM" in stack
    assert "no vendor is selected" in stack
    capability_ids = {item["capability_id"] for item in infra["dependencies"]}
    assert "operations-console-ui-local" in capability_ids
    assert "operations-console-identity-local" in capability_ids
    assert "operations-console-ui-azure-dev" in capability_ids
    assert "operations-console-identity-azure-dev" in capability_ids
    for item in infra["dependencies"]:
        if not item["capability_id"].startswith("operations-console-"):
            continue
        assert "Vercel" not in item["provider"]
        assert "Neon" not in item["provider"]
        if item["capability_id"].endswith("-azure-dev"):
            assert item["provider"] == "TBD"
            assert item["implementation_status"] == "decision_open"
            assert item["requirement_status"] == "future"
        else:
            assert item["environment"] == "local_development"
            assert item["implementation_status"] == "implemented"
            assert item["provider"] == "local"


def test_v26_places_console_after_bron2_storage_not_instead() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "after bron 2 storage is at least capturable" in delta
    assert "not instead of Fase 2" in delta
    assert "Do not claim the console exists in code" in delta
    assert "Fase 2b — Interne operations console" in roadmap
    assert "Duurzame opslag wordt niet overgeslagen" in roadmap
    assert "Bron 2 is nog BLOCKED op duurzame immutable opslag" in handoff
    assert "deze delta claimt geen bestaande UI en implementeert de console niet" in handoff
    assert "Echte console-MVP ingest+review" in handoff
    assert "bestaat nu in code" in handoff


def test_v26_is_c5_spanning_c3_with_owner_approval_and_retrospective_review() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    assert "**Highest change class:** C5" in delta
    assert "spanning C3" in delta
    assert "Named C5 reviewers are not yet staffed" in delta
    assert "This delta is owner-approved" in delta
    assert "Retrospective independent technical and security/operations review remains due" in delta
    assert "PR #16" in delta
    assert "does not reopen GD-03" in delta
    assert "GD-03 is ESTABLISHED" in handoff
    assert "GD-03 is niet langer OPEN" in handoff
    assert "geen nieuwe protocolversie" in handoff
    assert "Er worden geen reviewers verzonnen" in handoff
    assert "G1 technische protection op `main` is ON" in handoff
