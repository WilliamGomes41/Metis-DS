from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_10_CONSOLE_NAV_ACCOUNTS_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_10_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v210_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.10.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_10_CONSOLE_NAV_ACCOUNTS_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(DELTA)
    assert manifest["commit_sha"] == "48fc309032a693b9efcebbf4a7bbe9774cba51fa"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v210_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.10.0" in delta
    assert "docs/PROTOCOL_V2_10_CONSOLE_NAV_ACCOUNTS_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.10.0") == 1
    assert "De geldende normatieve baseline is Protocol v2.9.0" not in root_protocol
    assert "**Geldend protocol:** v2.10.0" in handoff
    assert "Protocol v2.10.0" in roadmap


def test_v210_hierarchy_points_at_one_live_version() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    delta = _read(DELTA)
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.10.0") == 1
    assert "docs/PROTOCOL_V2_2.md" in root_protocol
    assert "docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_9_CONSOLE_UX_BRAND_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_10_CONSOLE_NAV_ACCOUNTS_DELTA.md" in root_protocol
    assert (
        "v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0 and this delta jointly form normative baseline v2.10.0"
        in delta
    )


def test_v210_keeps_all_v26_v27_v28_and_v29_rules() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "All Protocol v2.6 room rules" in delta
    assert "all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules" in delta
    assert "all Protocol v2.8 primary-user and two-axis hierarchy rules" in delta
    assert "all Protocol v2.9 researcher-task UX and V&VN digital-brand rules remain in force" in delta
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
    assert "The console MUST be a task-oriented researcher surface" in delta
    assert "via-negativa MUST NOT be the primary on-screen copy" in delta
    assert "the console MUST use the V&VN digital stylesheet" in delta
    assert "Alle v2.6-consoleregels blijven van kracht" in root_protocol
    assert "Alle v2.7-bron-/API-/distributieregels blijven van kracht" in root_protocol
    assert "Alle v2.8-gebruikers-/hiërarchieregels blijven van kracht" in root_protocol
    assert "Alle v2.9-UX-/huisstyleregels blijven van kracht" in root_protocol
    assert "Chat hoort niet in de console" in handoff
    assert "deze delta claimt geen bestaande UI en implementeert de console niet" in handoff
    assert "bestaat nu in code" in handoff


def test_v210_renames_familieboom_to_documentenhierarchie() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert 'The console room currently labelled "Familieboom" MUST be renamed **Documentenhierarchie**' in delta
    assert "Documentenhierarchie is ordinary Dutch" in delta
    assert "The kernel model remains family × class" in delta
    assert "Family remains a hook, not a new file" in delta
    assert "This is UI vocabulary only" in delta
    assert "MUST NOT invent a new file, a new object type, or a third hierarchy axis" in delta
    assert '"Familieboom" MUST NOT remain the lasting top-nav heading' in delta
    assert "Researchers MUST NOT be asked for snapshot ids" in delta
    assert "Snapshot remains an internal kernel identifier" in delta
    assert "Documentenhierarchie" in root_protocol
    assert "niet Familieboom" in root_protocol
    assert "familie blijft een haak, geen nieuw bestand" in root_protocol
    assert "Documentenhierarchie" in roadmap
    assert "niet Familieboom" in roadmap
    assert "Documentenhierarchie" in handoff
    assert "Familieboom" in handoff
    assert "geen snapshot-id" in root_protocol
    assert "snapshot-id" in handoff


def test_v210_records_waiting_task_badges_as_real_kernel_work() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "Each top nav heading MUST show a visible waiting-task badge" in delta
    assert 'a count, for example "1"' in delta
    assert "when that room has work for the current user" in delta
    assert "The badge MUST be absent or zero-hidden when nothing waits" in delta
    assert "Counts MUST be real kernel work, not decoration" in delta
    assert 'A painted number, a static "0", or a badge that does not match a kernel queue MUST NOT be used' in delta
    assert "Badges are per current user" in delta
    assert "**Review** = objects or documents in `needs_review` assigned to this reviewer" in delta
    assert "or waiting on named reviewers including this user" in delta
    assert "**Publish** = captured documents this publisher can consider" in delta
    assert "The Publish badge MUST NOT imply that publication passed G2" in delta
    assert "A countable queue of captured documents is not a publication authorization" in delta
    assert "**Ingest** = drafts or returns waiting on this researcher if such a queue exists, else 0" in delta
    assert "**Documentenhierarchie** MAY badge documents awaiting family/class action for this curator" in delta
    assert "**Accounts** has no waiting-task queue in the MVP" in delta
    assert "A badge MUST NOT be used to claim that G2, G0 Azure DEV, G7 or G8 has passed" in delta
    assert "wachttaak-badges" in root_protocol
    assert "echte kernelwachtrijen" in root_protocol
    assert "zero-hidden" in root_protocol
    assert "Publish-badge impliceert geen G2-PASS" in root_protocol
    assert "wachttaak-badge" in roadmap
    assert "counts MUST geen decoratie zijn" in roadmap
    assert "wachttaak-badge" in handoff
    assert "geen decoratie" in handoff
    assert "MUST NOT impliceren dat publicatie G2 passeerde" in handoff


def test_v210_records_accounts_room_with_closed_role_set() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "The console MUST include an **Accounts** room" in delta
    assert "Accounts is identity administration" in delta
    assert "It is not chat" in delta
    assert "It is not a fifth clinical room replacing ingest, review or publish" in delta
    assert "The four clinical rooms remain ingest, review, publish, and analytics last" in delta
    assert "create a user (username, display name, password)" in delta
    assert "assign roles" in delta
    assert "change role assignment" in delta
    assert "The role set remains **CLOSED**: `researcher`, `reviewer`, `publisher` only" in delta
    assert "Operators MUST NOT invent new role types in the MVP" in delta
    assert "not a free-form RBAC editor" in delta
    assert "The Accounts room MUST NOT be a role-type editor" in delta
    assert "No open registration" in delta
    assert "No shared login" in delta
    assert "Login still username AND password" in delta
    assert "AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT be creatable as required reviewers" in delta
    assert "MUST NOT be created as accounts that can serve as required reviewers" in delta
    assert "The uploader MUST NOT be the only required reviewer" in delta
    assert "Who may manage accounts: an actor with the **publisher** role" in delta
    assert "internal identity admin for the MVP" in delta
    assert "Other roles MUST NOT create users or change role assignment" in delta
    assert "First bootstrap via the existing CLI `console-account` remains valid" in delta
    assert "Accounts-kamer" in root_protocol
    assert "geen vijfde klinische kamer" in root_protocol
    assert "rollenset blijft GESLOTEN" in root_protocol
    assert "geen open registratie" in root_protocol
    assert "geen gedeelde login" in root_protocol
    assert "Accounts-kamer" in roadmap
    assert "GESLOTEN" in roadmap
    assert "console-account" in roadmap
    assert "Accounts-kamer" in handoff
    assert "GESLOTEN" in handoff
    assert "console-account" in handoff
    assert "geen vijfde klinische kamer" in handoff
    assert "publisher-rol" in handoff


def test_v210_keeps_promote_review_and_family_move_without_rereview() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "Promoting class still MUST require a new review" in delta
    assert "already Protocol v2.8" in delta
    assert "Family move still MUST NOT require clinical re-review" in delta
    assert "That move remains a curator act" in delta
    assert "The console tree remains family × class" in delta
    assert "Klasse promoveren MUST een nieuwe review vereisen" in root_protocol
    assert "familiemove MUST NOT klinische herreview vereisen" in root_protocol
    assert "Klasse promoveren MUST review" in roadmap
    assert "familiemove MUST NOT klinische herreview" in roadmap
    assert "Klasse promoveren MUST een nieuwe review vereisen" in handoff
    assert "Familiemove MUST NOT klinische herreview vereisen" in handoff


def test_v210_keeps_fail_closed_exclusions_and_gitignore() -> None:
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


def test_v210_is_c5_spanning_c3_with_owner_approval_and_retrospective_review() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C5" in delta
    assert "spanning C3" in delta
    assert "console rooms/nav" in delta
    assert "Named C5 reviewers are not yet staffed" in delta
    assert "This delta is owner-approved" in delta
    assert "Retrospective independent technical and security/operations review remains due" in delta
    assert "PR #21" in delta
    assert "PR #24" in delta
    assert "does not reopen GD-03" in delta
    assert "GD-03 is ESTABLISHED" in handoff
    assert "GD-03 is niet langer OPEN" in handoff
    assert "geen nieuwe protocolversie" in handoff
    assert "Er worden geen reviewers verzonnen" in handoff
    assert "Er worden geen namen verzonnen" in handoff
    assert "G1 technische protection op `main` is ON" in handoff
    assert "G0 Azure DEV blijft `BLOCKED`" in handoff
    assert "v2.10.0" in governance
    assert "heropent GD-03 niet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"
    assert gd03["protocol_version"] == "2.4.0"
    assert gd03["decision_date"] == "2026-08-27"


def test_v210_records_console_followup_build_order_without_skipping_g2() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "Do not build a mockup" in delta
    assert "The next implementation after this delta MUST be a console follow-up on the v2.9 UX" in delta
    assert "open PR #25 if still open" in delta
    assert 'rename the console room "Familieboom" to "Documentenhierarchie"' in delta
    assert "waiting-task badges as in section 4" in delta
    assert "Accounts room as in section 5" in delta
    assert "MUST NOT invent Azure, Vercel or Neon as in-scope" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "This does not skip durable immutable storage" in delta
    assert "Do not change `src/operations_console_*.py` in this protocol change" in delta
    assert "scoped supersession" in delta
    assert "v2.9 §10" in delta
    assert "console-vervolg" in roadmap
    assert "Geen mockup" in roadmap
    assert "VIA de console" in roadmap or "VIA die console" in roadmap
    assert "bestaande kernel" in roadmap
    assert "PR #25" in roadmap
    assert "console-vervolg" in handoff
    assert "geen mockup" in handoff
    assert "PR #25" in handoff
    assert "Bron 2 is nog BLOCKED op duurzame immutable opslag" in handoff
    assert "G2-locator blijft de publicatieblocker" in handoff
    assert "Echte console-MVP ingest+review" in handoff
    assert "bestaat nu in code" in handoff


def test_v210_keeps_g1_public_mvp_and_forbids_vercel_neon_llm() -> None:
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
    assert "Protocol v2.10.0" in stack
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


def test_v210_does_not_implement_console_ui_or_product_code() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "This protocol-only change does not implement UI or product code" in delta
    assert "Do not rewrite `src/operations_console_*.py` in this protocol change" in delta
    assert "This delta does not implement the new UI" in delta
    assert "It does not:" in delta
    assert "implement the new UI, any room rewrite, any account store change, or any Product API behaviour change" in delta
    assert "replace ingest, review or publish with Accounts, or treat Accounts as a fifth clinical room" in delta
    assert "open the role set or allow operators to invent new role types" in delta
    assert "allow open registration or shared login" in delta
    assert "let AI, Grok Bot, Metis, the Implementation engineer or the Auditor be created as required reviewers" in delta
    assert "let the uploader be the only required reviewer" in delta
    assert "require clinical re-review for a family move" in delta
    assert "waive review when promoting class" in delta
    assert "skip durable immutable storage or convert G2 to PASS" in delta
    assert "reopen or alter GD-03" in delta
    assert "staff named human reviewers" in delta
    assert "deze v2.10-delta implementeert die follow-up niet" in handoff
    assert "Deze delta implementeert de nieuwe UI niet" in handoff
    assert "Protocol v2.10.0" in changelog
    assert "does not implement the UI follow-up" in changelog
