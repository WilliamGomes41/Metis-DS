from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_7_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v27_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.7.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(DELTA)
    assert manifest["commit_sha"] == "337728dd76c0b5d50bdc6421b83d6a777a134a61"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v27_remains_an_approved_component_of_current_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.7.0" in delta
    assert "docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md" in root_protocol
    assert "Protocol v2.7.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.6.0" not in root_protocol
    assert "**Geldend protocol:** v2.9.0" in handoff
    assert "Protocol v2.7.0" in roadmap


def test_v27_hierarchy_remains_a_listed_baseline_component() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    delta = _read(DELTA)
    assert "docs/PROTOCOL_V2_2.md" in root_protocol
    assert "docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md" in root_protocol
    assert (
        "v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0 and this delta jointly form normative baseline v2.7.0"
        in delta
    )


def test_v27_keeps_all_v26_console_rules() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "All Protocol v2.6 console rules remain in force" in delta
    assert "The internal operations console remains authorized DS scope and remains unbuilt" in delta
    assert "four rooms that are not four buttons for one person" in delta
    assert "chat is not a room in this console" in delta
    assert "a care-app frontend" in delta
    assert "a chatbot as a product surface" in delta
    assert "an EPD/ECD UI" in delta
    assert "a public website MUST NOT live in this repository" in delta
    assert "console work MUST NOT replace Fase 2" in delta
    assert "Alle v2.6-consoleregels blijven van kracht" in root_protocol
    assert "Chat hoort niet in de console" in handoff
    assert "deze delta claimt geen bestaande UI en implementeert de console niet" in handoff
    assert "bestaat nu in code" in handoff


def test_v27_records_first_wave_source_rules() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "First-wave official files MUST be the HTML page and the PDF only" in delta
    assert "kennisplatform `story.html` boom players MUST be out of the first wave" in delta
    assert "The official file MUST be the kennisplatform freeze, not a living Word document" in delta
    assert "Ingest MUST accept a file upload or a URL" in delta
    assert "A URL MUST be snapshotted to exact bytes immediately at ingest" in delta
    assert "one trunk guideline plus hashed branch documents" in delta
    assert "researcher UX only" in delta
    assert "MUST NOT be a nurse decision tree" in delta
    assert "A new guideline version MUST create a new snapshot" in delta
    assert "object-level differential comparison" in delta
    assert "The old release MUST stay live until cutover publish" in delta
    assert "story.html" in roadmap
    assert "story.html" in handoff


def test_v27_records_object_level_retrieve_and_abstain_api() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "The Product API MUST retrieve at object level only" in delta
    assert "Unpublished branch objects MUST abstain even if the trunk is published" in delta
    assert "A `supported` result MUST carry V and VN labels" in delta
    assert "DS MUST NOT generate prose" in delta
    assert "abstain MUST be a closed sentence catalog" in delta
    assert "reviewed like a tiny guideline" in delta
    assert "No LLM in the MVP" in delta
    assert "Tenant means who MAY call the API" in delta
    assert "MUST serve all published V and VN objects" in delta
    assert "MUST NOT store hospital protocols, adoption lists, or patient data" in delta
    assert "object-level retrieve-and-abstain" in root_protocol
    assert "DS genereert geen proza" in root_protocol


def test_v27_records_live_curation_distribution() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "The DS asset is live curation" in delta
    assert "The default product MUST be a live retrieve-and-abstain subscription" in delta
    assert "Training MAY exist only as a second licence" in delta
    assert "still calls DS at question time to check published status" in delta
    assert "The first paying subscriber MUST be a Dutch EPD/ECD" in delta
    assert "Hospital or university LLM bots MAY subscribe the same way" in delta
    assert "DS MUST NOT build those bots" in delta
    assert "scoped supersession" in delta
    assert "v2.4 §10" in delta
    assert "live retrieve-and-abstain-abonnement" in handoff
    assert "Nederlands EPD/ECD" in roadmap


def test_v27_records_later_analytics_limits() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "which objects were asked" in delta
    assert "Care-impact research is out of DS" in delta
    assert "DS MUST NOT perform care-impact research" in delta
    assert "DS MUST NOT be federated learning" in delta
    assert "MUST NOT be used to tune Holdout B" in delta
    assert "Do not build analytics first" in delta
    assert "care-impact-onderzoek" in roadmap
    assert "federated learning" in roadmap


def test_v27_does_not_skip_fase2_or_claim_console_built() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "Do not skip Fase 2 bron 2 storage" in delta
    assert "The console remains approved-not-built" in delta
    assert "The next concrete task remains bron 2 storage" in delta
    assert "Do not claim the console exists in code" in delta
    assert "Duurzame opslag wordt niet overgeslagen" in roadmap
    assert "Bron 2 is nog BLOCKED op duurzame immutable opslag" in handoff
    assert "deze delta claimt geen bestaande UI en implementeert de console niet" in handoff
    assert "bestaat nu in code" in handoff


def test_v27_keeps_fail_closed_exclusions_and_gitignore() -> None:
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
        "No Vercel, Neon, or LLM vendor",
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


def test_v27_is_c5_spanning_c3_with_owner_approval_and_retrospective_review() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    assert "**Highest change class:** C5" in delta
    assert "spanning C3" in delta
    assert "Named C5 reviewers are not yet staffed" in delta
    assert "This delta is owner-approved" in delta
    assert "Retrospective independent technical and security/operations review remains due" in delta
    assert "PR #18" in delta
    assert "does not reopen GD-03" in delta
    assert "GD-03 is ESTABLISHED" in handoff
    assert "GD-03 is niet langer OPEN" in handoff
    assert "geen nieuwe protocolversie" in handoff
    assert "Er worden geen reviewers verzonnen" in handoff
    assert "G1 technische protection op `main` is ON" in handoff
    assert "G0 Azure DEV blijft `BLOCKED`" in handoff


def test_v27_keeps_g1_public_mvp_and_forbids_vercel_neon_llm() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    stack = _read(ROOT / "docs" / "STACK_SETUP_BASELINE.md")
    infra = json.loads((ROOT / "config" / "infrastructure_manifest.v1.json").read_text(encoding="utf-8"))
    assert "G1 technical protection remains ON" in delta
    assert "public under Protocol v2.5" in delta
    assert "G0 Azure DEV remains BLOCKED" in delta
    assert "No Vercel, Neon, or LLM vendor" in delta
    assert "G1 technische protection op `main` is ON" in handoff
    assert "G0 Azure DEV blijft `BLOCKED`" in handoff
    assert "Vercel, Neon and a hosted LLM" in stack
    assert "no vendor is selected" in stack
    assert "No LLM in the MVP" in stack
    capability_ids = {item["capability_id"] for item in infra["dependencies"]}
    assert "operations-console-ui-local" in capability_ids
    assert "operations-console-identity-local" in capability_ids
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
