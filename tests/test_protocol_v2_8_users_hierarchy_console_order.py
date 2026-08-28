from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_8_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v28_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.8.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(DELTA)
    assert manifest["commit_sha"] == "d61aed6553503772df3fab16c4f12247966fc161"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v28_remains_an_approved_component_of_current_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.8.0" in delta
    assert "docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md" in root_protocol
    assert "Protocol v2.8.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.7.0" not in root_protocol
    assert "**Geldend protocol:** v2.11.0" in handoff
    assert "Protocol v2.8.0" in roadmap


def test_v28_hierarchy_remains_a_listed_baseline_component() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    delta = _read(DELTA)
    assert "docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_2.md" in root_protocol
    assert "docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md" in root_protocol
    assert (
        "v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0 and this delta jointly form normative baseline v2.8.0"
        in delta
    )


def test_v28_keeps_all_v26_and_v27_rules() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "All Protocol v2.6 console rules and all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules remain in force" in delta
    assert "The internal operations console remains authorized DS scope and remains unbuilt" in delta
    assert "four rooms that are not four buttons for one person" in delta
    assert "chat is not a room in this console" in delta
    assert "a care-app frontend" in delta
    assert "a chatbot as a product surface" in delta
    assert "an EPD/ECD UI" in delta
    assert "a public website MUST NOT live in this repository" in delta
    assert "engineers MUST NOT submit sources through the ingest room" in delta
    assert "first-wave official files MUST be the HTML page and the PDF only" in delta
    assert "The Product API MUST retrieve at object level only" in delta
    assert "unpublished branch objects MUST abstain even if the trunk is published" in delta
    assert "No LLM in the MVP" in delta
    assert "Alle v2.6-consoleregels blijven van kracht" in root_protocol
    assert "Alle v2.7-bron-/API-/distributieregels blijven van kracht" in root_protocol
    assert "Chat hoort niet in de console" in handoff
    assert "deze delta claimt geen bestaande UI en implementeert de console niet" in handoff
    assert "bestaat nu in code" in handoff


def test_v28_records_primary_users_not_nurses() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "guideline researchers, who use the console" in delta
    assert "B2B subscribers: an EPD, an institution, or their bot" in delta
    assert "Nurses are not primary users of DS" in delta
    assert "The console MUST NOT be designed for nurses" in delta
    assert "MUST NOT be a nurse decision tree" in delta
    assert "richtlijnonderzoekers (console)" in root_protocol
    assert "B2B-abonnees" in root_protocol
    assert "Verpleegkundigen zijn geen primaire DS-gebruikers" in root_protocol
    assert "ontwerp de console niet voor verpleegkundigen" in roadmap
    assert "ontwerp de console niet voor verpleegkundigen" in handoff


def test_v28_records_two_axis_source_hierarchy() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "Heavier class MUST NOT be filled by lighter class" in delta
    assert "`richtlijn` > `handreiking` > `artikel` > `transcript` / `podcast`" in delta
    assert "A podcast MUST NOT replace a guideline in the API even in the same family" in delta
    assert "A lower class MAY be `supported` only with its class label" in delta
    assert "A lower class MUST NOT fill a gap left by a missing higher class on the same question if a higher class exists in the published corpus" in delta
    assert "Family is a hook, not a new file" in delta
    assert "the ingest researcher MUST set family" in delta
    assert "Adding a branch tomorrow MUST NOT redraw the tree" in delta
    assert "Moving a source between families MUST NOT require clinical re-review" in delta
    assert "That move is a curator act" in delta
    assert "Promoting class (for example transcript to richtlijn) MUST require review" in delta
    assert "that is a new protocol change, not a silent extra review" in delta
    assert "The console tree MUST be family × class" in delta
    assert "Each file MUST keep its own hash" in delta
    assert "only what was asked" in delta
    assert "Unpublished branches MUST abstain" in delta
    assert "klasse/gewicht" in roadmap
    assert "familie × klasse" in roadmap
    assert "podcast MUST NOT een richtlijn" in handoff


def test_v28_clarifies_rag_is_not_the_product() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "RAG on kennisplatform HTML is not the product" in delta
    assert "DS is the owned live curated switch, not a scrape" in delta
    assert "Train-ready structured objects plus a live published-check remain the B2B offer" in delta
    assert "RAG op kennisplatform-HTML is niet het product" in root_protocol
    assert "geen scrape" in root_protocol
    assert "live gecureerde schakel" in handoff
    assert "Train-ready gestructureerde objecten plus live publicatiestatuscheck" in handoff


def test_v28_records_real_console_mvp_build_order_without_skipping_storage() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "Do not build a mockup" in delta
    assert 'Do not wait for Azure or a finished "DS" before researchers have a real console' in delta
    assert "The next implementation after this delta MUST be a real console MVP, not a mockup" in delta
    assert "wired to the existing kernel" in delta
    assert "local `sources/private/` as the G0 local store" in delta
    assert "Continentie bron 2 MUST enter through that console" in delta
    assert "Bron 2 MUST NOT enter via a parallel engineer-only path as the researcher experience" in delta
    assert "The Product API already exists; do not rebuild it first" in delta
    assert "Azure DEV remains BLOCKED under G0" in delta
    assert "Analytics remains later" in delta
    assert "This does not skip durable immutable storage" in delta
    assert "The local store is the console stand-in until G0 Azure DEV" in delta
    assert "Publication remains BLOCKED without an immutable locator, as in existing G2 rules" in delta
    assert "The next concrete task after this delta is the real console MVP on the existing kernel, with bron 2 as the first envelope" in delta
    assert "scoped supersession" in delta
    assert "v2.6 §7" in delta
    assert "v2.7 §2" in delta
    assert "echte console-MVP" in roadmap
    assert "Geen mockup" in roadmap
    assert "VIA de console" in roadmap or "VIA die console" in roadmap
    assert "Echte console-MVP ingest+review" in handoff
    assert "geen mockup" in handoff
    assert "Bron 2 is nog BLOCKED op duurzame immutable opslag" in handoff
    assert "deze delta claimt geen bestaande UI en implementeert de console niet" in handoff
    assert "Echte console-MVP ingest+review" in handoff
    assert "bestaat nu in code" in handoff
    assert "Do not claim the console exists in code" in delta


def test_v28_keeps_fail_closed_exclusions_and_gitignore() -> None:
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


def test_v28_is_c5_spanning_c3_with_owner_approval_and_retrospective_review() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    assert "**Highest change class:** C5" in delta
    assert "spanning C3" in delta
    assert "Named C5 reviewers are not yet staffed" in delta
    assert "This delta is owner-approved" in delta
    assert "Retrospective independent technical and security/operations review remains due" in delta
    assert "PR #19" in delta
    assert "does not reopen GD-03" in delta
    assert "GD-03 is ESTABLISHED" in handoff
    assert "GD-03 is niet langer OPEN" in handoff
    assert "geen nieuwe protocolversie" in handoff
    assert "Er worden geen reviewers verzonnen" in handoff
    assert "Er worden geen namen verzonnen" in handoff
    assert "G1 technische protection op `main` is ON" in handoff
    assert "G0 Azure DEV blijft `BLOCKED`" in handoff


def test_v28_keeps_g1_public_mvp_and_forbids_vercel_neon_llm() -> None:
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
    assert "RAG on kennisplatform HTML is not the product" in stack
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


def test_v28_does_not_implement_console_or_product_code() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    assert "This protocol-only change does not implement UI or product code" in delta
    assert "Do not implement the console in this protocol change" in delta
    assert "It does not:" in delta
    assert "implement the console, any room, any account, or any Product API behaviour change" in delta
    assert "authorize a mockup as the next implementation" in delta
    assert "skip durable immutable storage or convert G2 to PASS" in delta
    assert "design the console for nurses" in delta
    assert "deze delta claimt geen bestaande UI en implementeert de console niet" in handoff
