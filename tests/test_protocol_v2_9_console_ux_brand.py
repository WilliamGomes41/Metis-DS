from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_9_CONSOLE_UX_BRAND_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_9_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v29_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.9.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_9_CONSOLE_UX_BRAND_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(DELTA)
    assert manifest["commit_sha"] == "84ccb3dfc632802836ffee849c324d73a4bb8bb6"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v29_remains_an_approved_component_of_current_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.9.0" in delta
    assert "docs/PROTOCOL_V2_9_CONSOLE_UX_BRAND_DELTA.md" in root_protocol
    assert "Protocol v2.9.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.8.0" not in root_protocol
    assert "Protocol v2.9.0" in roadmap


def test_v29_hierarchy_remains_a_listed_baseline_component() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    delta = _read(DELTA)
    assert "docs/PROTOCOL_V2_2.md" in root_protocol
    assert "docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_9_CONSOLE_UX_BRAND_DELTA.md" in root_protocol
    assert (
        "v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0 and this delta jointly form normative baseline v2.9.0"
        in delta
    )


def test_v29_keeps_all_v26_v27_and_v28_rules() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "All Protocol v2.6 room rules" in delta
    assert "all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules" in delta
    assert "all Protocol v2.8 primary-user and two-axis hierarchy rules remain in force" in delta
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
    assert "the console MUST NOT be designed for nurses" in delta
    assert "Family is a hook, not a new file" in delta
    assert "Alle v2.6-consoleregels blijven van kracht" in root_protocol
    assert "Alle v2.7-bron-/API-/distributieregels blijven van kracht" in root_protocol
    assert "Alle v2.8-gebruikers-/hiërarchieregels blijven van kracht" in root_protocol


def test_v29_records_task_oriented_researcher_surface() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "The console MUST be a task-oriented researcher surface, not a dump of the kernel data model" in delta
    assert "The primary action on each room MUST be visually obvious" in delta
    assert "Visual hierarchy MUST distinguish sections and next steps" in delta
    assert "Stacked unlabeled HTML forms with equal weight MUST NOT be the console UX" in delta
    assert "MUST NOT remain the lasting researcher surface" in delta
    assert "taakgericht onderzoekersoppervlak" in root_protocol
    assert "taakgerichte onderzoeker-UX" in roadmap


def test_v29_records_copy_and_forbids_via_negativa_as_primary() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "what the researcher can do here" in delta
    assert "what happens next" in delta
    assert "what is expected of them" in delta
    assert "Via-negativa" in delta
    assert "MUST NOT be the primary on-screen copy" in delta
    assert "MAY appear once in a short help" in delta
    assert "not as the heading of every room" in delta
    assert "via-negativa mag niet de primaire on-screen copy zijn" in root_protocol


def test_v29_records_researcher_vocabulary_not_kernel_words() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "document, titel, versie, familie, klasse, status, inleveren, review, publiceren" in delta
    assert 'MUST NOT use "envelope" as a UI term' in delta
    assert "conversation metaphor only" in delta
    assert 'MUST NOT ask a researcher to type or pick a "snapshot" id' in delta
    assert "Snapshot remains an internal kernel identifier" in delta
    assert "visible document (title + version + family)" in delta
    assert "not a blank snapshot field" in delta
    assert "envelope is geen UI-term" in root_protocol
    assert "geen snapshot-id" in root_protocol
    assert "Envelope is geen UI-term" in roadmap


def test_v29_records_login_username_and_password() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Login MUST ask for gebruikersnaam AND wachtwoord" in delta
    assert "No shared login" in delta
    assert "No open registration" in delta
    assert "The password field MUST be `type=password`" in delta
    assert "gebruikersnaam én wachtwoord" in root_protocol
    assert "gebruikersnaam én wachtwoord" in roadmap


def test_v29_records_move_and_promote_as_visible_actions() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Move-between-families and promote-class MUST look like real clickable actions" in delta
    assert "not buried extra forms" in delta
    assert "without typing a kernel id" in delta
    assert "echte klikbare acties" in roadmap


def test_v29_records_venvn_digital_stylesheet() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "The console MUST use the V&VN digital stylesheet" in delta
    assert "`#E23100`" in delta
    assert "`#5D3297`" in delta
    assert "`#000000`" in delta
    assert "`#FFFFFF`" in delta
    assert "MUST NOT be used for large surfaces" in delta
    assert "`#E28080`" in delta
    assert "`#FDEFEB`" in delta
    assert "`#45AAC7`" in delta
    assert "`#EAF8F8`" in delta
    assert "`#6FA57D`" in delta
    assert "`#EDFAF0`" in delta
    assert "`#E2A659`" in delta
    assert "`#FCF8EA`" in delta
    assert "Choose only one secondary colour family per view" in delta
    assert "MUST NOT mix colour families" in delta
    assert "**HK Grotesk**" in delta
    assert "**Raleway Bold**" in delta
    assert "headlines (kopteksten)" in delta
    assert "primary buttons (primaire knoppen)" in delta
    assert "recommended path is `assets/brand/fonts/`" in delta
    assert "MUST NOT pirate fonts" in delta
    assert "MUST NOT commit the official Canva/PDF stylesheet into git" in delta
    assert "v&vn beeldmerk" in delta
    assert "not as decoration wallpaper" in delta
    assert "HK Grotesk" in root_protocol
    assert "Raleway Bold" in root_protocol
    assert "#E23100" in root_protocol
    assert "V&VN digitale stylesheet" in roadmap
    assert "Protocol v2.9.0" in changelog
    assert "V&VN digital stylesheet" in changelog


def test_v29_keeps_fail_closed_exclusions_and_gitignore() -> None:
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
        "MUST NOT be a nurse-facing care app",
        "Chat is not a room",
        "Publication remains fail-closed without G2",
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


def test_v29_is_c3_with_owner_approval_and_retrospective_review() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3" in delta
    assert "console is the human door of that loop" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "This delta is owner-approved" in delta
    assert "Retrospective independent clinical and technical review remains due" in delta
    assert "PR #21" in delta
    assert "does not reopen GD-03" in delta
    assert "v2.9.0" in governance
    assert "heropent GD-03 niet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"
    assert gd03["protocol_version"] == "2.4.0"
    assert gd03["decision_date"] == "2026-08-27"


def test_v29_records_ux_rewrite_build_order_without_skipping_g2() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Do not build a mockup" in delta
    assert "The next implementation after this delta MUST be a console UX rewrite on the existing kernel" in delta
    assert "MUST NOT invent Azure, Vercel or Neon as in-scope" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "This does not skip durable immutable storage" in delta
    assert "Do not change `src/operations_console_*.py` in this protocol change" in delta
    assert "scoped supersession" in delta
    assert "v2.8 §6" in delta
    assert "console-UX-rewrite" in roadmap
    assert "Geen mockup" in roadmap
    assert "VIA de console" in roadmap or "VIA die console" in roadmap
    assert "bestaande kernel" in roadmap


def test_v29_keeps_g1_public_mvp_and_forbids_vercel_neon_llm() -> None:
    delta = _read(DELTA)
    stack = _read(ROOT / "docs" / "STACK_SETUP_BASELINE.md")
    infra = json.loads((ROOT / "config" / "infrastructure_manifest.v1.json").read_text(encoding="utf-8"))
    assert "G1 technical protection remains ON" in delta
    assert "public under Protocol v2.5" in delta
    assert "G0 Azure DEV remains BLOCKED" in delta
    assert "No Vercel, Neon, or LLM vendor" in delta
    assert "Vercel, Neon and a hosted LLM" in stack
    assert "no vendor is selected" in stack
    assert "No LLM in the MVP" in stack
    assert "RAG on kennisplatform HTML is not the product" in stack
    assert "Protocol v2.9.0" in stack
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


def test_v29_does_not_implement_console_ui_or_product_code() -> None:
    delta = _read(DELTA)
    assert "This protocol-only change does not implement UI or product code" in delta
    assert "Do not rewrite `src/operations_console_*.py` in this protocol change" in delta
    assert "This delta does not implement the new UI" in delta
    assert "It does not:" in delta
    assert "implement the new UI, any room rewrite, any account change, or any Product API behaviour change" in delta
    assert "skip durable immutable storage or convert G2 to PASS" in delta
    assert "pirate fonts or commit unlicensed font files" in delta
