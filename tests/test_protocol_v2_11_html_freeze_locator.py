from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_11_HTML_FREEZE_LOCATOR_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_11_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v211_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.11.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_11_HTML_FREEZE_LOCATOR_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(DELTA)
    assert manifest["commit_sha"] == "12fe1b70bfb5aaed235201769a9ce3199bc684ce"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v211_delta_exists_and_is_a_live_baseline_component() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.11.0" in delta
    assert "docs/PROTOCOL_V2_11_HTML_FREEZE_LOCATOR_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.13.0") == 1
    assert "plus Protocol v2.12.0" in root_protocol
    assert "plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.11.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.10.0" not in root_protocol
    assert "**Geldend protocol:** v2.13.0 + v2.12.0 + v2.11.0" in handoff
    assert "**Geldend protocol:** v2.11.0" not in handoff
    assert "Protocol v2.11.0" in roadmap


def test_v211_hierarchy_points_at_combined_live_baseline() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    delta = _read(DELTA)
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.13.0") == 1
    assert "plus Protocol v2.12.0" in root_protocol
    assert "plus Protocol v2.11.0" in root_protocol
    assert "docs/PROTOCOL_V2_2.md" in root_protocol
    assert "docs/PROTOCOL_V2_3_TECHNICAL_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_4_PRODUCT_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_5_MVP_PUBLIC_REMOTE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_6_INTERNAL_OPERATIONS_CONSOLE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_7_SOURCE_API_DISTRIBUTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_8_USERS_HIERARCHY_CONSOLE_ORDER_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_9_CONSOLE_UX_BRAND_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_10_CONSOLE_NAV_ACCOUNTS_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_11_HTML_FREEZE_LOCATOR_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_12_OBJECT_TYPE_REVIEW_PROJECTION_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_13_ATOMIC_OBJECT_SEMANTICS_DELTA.md" in root_protocol
    assert (
        "v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0 and this delta jointly form normative baseline v2.11.0"
        in delta
    )


def test_v211_keeps_all_v26_through_v210_rules() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "All Protocol v2.6 room rules" in delta
    assert "all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules" in delta
    assert "all Protocol v2.8 primary-user and two-axis hierarchy rules" in delta
    assert "all Protocol v2.9 researcher-task UX and V&VN digital-brand rules" in delta
    assert "all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules remain in force" in delta
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
    assert "the console room heading MUST be Documentenhierarchie" in delta
    assert "CLOSED role set" in delta
    assert "Alle v2.6-consoleregels blijven van kracht" in root_protocol
    assert "Alle v2.7-bron-/API-/distributieregels blijven van kracht" in root_protocol
    assert "Alle v2.8-gebruikers-/hiërarchieregels blijven van kracht" in root_protocol
    assert "Alle v2.9-UX-/huisstyleregels blijven van kracht" in root_protocol
    assert "Alle v2.10-console-/nav-/accountsregels blijven van kracht" in root_protocol
    assert "Chat hoort niet in de console" in handoff
    assert "deze delta claimt geen bestaande UI en implementeert de console niet" in handoff
    assert "bestaat nu in code" in handoff


def test_v211_does_not_ban_html_entirely() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "Do NOT ban HTML entirely" in delta
    assert "The kennisplatform freeze is often HTML" in delta
    assert "Continentie first envelope would stall if HTML were banned" in delta
    assert "MUST NOT ban HTML entirely" in delta
    assert "ban HTML entirely" in delta
    assert "HTML wordt niet geheel verboden" in root_protocol
    assert "HTML wordt niet geheel verboden" in roadmap
    assert "HTML wordt niet geheel verboden" in handoff


def test_v211_requires_uploaded_html_freeze_and_rejects_live_url_html() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "Official first-wave HTML MUST be an uploaded freeze file" in delta
    assert "exact bytes" in delta
    assert "Live URL-HTML MUST be rejected at ingest" in delta
    assert "the kennisplatform page is an app shell" in delta
    assert "line locators would bind to the wrong bytes" in delta
    assert "PDF upload remains in" in delta
    assert "URL ingest of a PDF MAY remain" in delta
    assert "bytes are the PDF" in delta
    assert "URL ingest of HTML MUST NOT" in delta
    assert "File-upload HTML/PDF and immediate byte freeze of an uploaded file remain mandatory" in delta
    assert "geüploade freeze-file" in root_protocol
    assert "live URL-HTML MUST bij ingest worden geweigerd" in root_protocol
    assert "URL-ingest van een PDF MAG" in root_protocol
    assert "URL-ingest van HTML MUST NOT" in root_protocol
    assert "geüploade freeze-file" in roadmap
    assert "Live URL-HTML MUST bij ingest worden geweigerd" in roadmap
    assert "URL-ingest van een PDF MAG blijven" in roadmap
    assert "URL-ingest van HTML MUST NOT" in roadmap
    assert "geüploade freeze-file" in handoff
    assert "Live URL-HTML MUST bij ingest worden geweigerd" in handoff
    assert "URL-ingest van een PDF MAG blijven" in handoff
    assert "URL-ingest van HTML MUST NOT" in handoff


def test_v211_is_scoped_supersession_of_v27_url_ingest_for_html() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "scoped supersession" in delta
    assert "Protocol v2.7 only as it said ingest MUST accept a URL" in delta
    assert "without distinguishing HTML vs PDF" in delta
    assert "Where this delta and that sentence conflict for HTML, this delta governs" in delta
    assert "File-upload HTML/PDF and immediate byte freeze of an uploaded file remain mandatory" in delta
    assert "begrensde supersessie van v2.7" in root_protocol
    assert "zonder HTML van PDF te onderscheiden" in root_protocol
    assert "Protocol v2.11 supersedes v2.7 URL-for-official-files as to HTML" in roadmap
    assert "begrensde supersessie van Protocol v2.7" in handoff
    assert "zonder HTML van PDF te onderscheiden" in handoff


def test_v211_requires_source_locators_on_knowledge_objects() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    handoff = _read(ROOT / "HANDOFF.md")
    schema = json.loads((ROOT / "schemas" / "knowledge_object.schema.v1.2.json").read_text(encoding="utf-8"))
    fragment = schema["properties"]["provenance"]["properties"]["source_fragments"]["items"]
    locator = fragment["properties"]["source_locator"]
    assert "Knowledge objects MUST carry enough source context to return to the exact place in that hashed original" in delta
    assert "provenance.source_fragments" in delta
    assert "page, bbox, `source_locator`" in delta
    assert "PDF extract uses `page_bbox`" in delta
    assert "HTML extract uses `web_line_range` against those freeze bytes" in delta
    assert "stable only if the freeze is never reserialized" in delta
    assert "HTML line-range locators are acceptable for first wave on uploaded freeze bytes" in delta
    assert "They are not an excuse to scrape a live URL" in delta
    assert "Reserializing, pretty-printing, or re-saving the freeze bytes MUST NOT be used as ingest" in delta
    assert "source locator" in root_protocol
    assert "page_bbox" in root_protocol
    assert "web_line_range" in root_protocol
    assert "provenance.source_fragments" in root_protocol
    assert "page_bbox" in handoff
    assert "web_line_range" in handoff
    assert "source_locator" in fragment["required"]
    assert "page_bbox" in locator["properties"]["locator_type"]["enum"]
    assert "web_line_range" in locator["properties"]["locator_type"]["enum"]


def test_v211_product_api_fail_closes_supported_without_locator() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    assert "The Product API MUST NOT return `supported` if the object's source locator is missing/empty" in delta
    assert "Fail-closed" in delta
    assert "Abstain instead (catalog sentence, no LLM)" in delta
    assert "Missing or empty source locator is a retrieve-safety abstain" in delta
    assert "MUST NOT `supported` teruggeven" in root_protocol
    assert "cataloguszin" in root_protocol
    assert "geen LLM" in root_protocol
    assert "MUST NOT `supported` teruggeven" in roadmap
    assert "cataloguszin" in roadmap
    assert "MUST NOT `supported` teruggeven" in handoff
    assert "cataloguszin" in handoff
    assert "geen LLM" in handoff


def test_v211_capture_is_not_publication_and_g2_still_blocks() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Capture remains not publication" in delta
    assert "The G2 locator still required to publish" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "A captured freeze is not a published object" in delta
    assert "This does not skip durable immutable storage" in delta
    assert "Capture is geen publicatie" in handoff or "capture is geen publicatie" in handoff
    assert "G2-locator blijft de publicatieblocker" in handoff
    assert "Bron 2 is nog BLOCKED op duurzame immutable opslag" in handoff
    assert "publicatie blijft BLOCKED zonder immutable locator" in roadmap.lower() or "Publicatie blijft BLOCKED zonder immutable locator" in roadmap


def test_v211_keeps_fail_closed_exclusions_and_gitignore() -> None:
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
        "No Azure/Vercel/Neon in this delta",
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


def test_v211_is_c3_with_owner_approval_and_retrospective_review() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3" in delta
    assert "source/review/publish / retrieve safety" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "This delta is owner-approved" in delta
    assert "Retrospective independent clinical and technical review remains due" in delta
    assert "PR #26" in delta
    assert "PR #24" in delta
    assert "does not reopen GD-03" in delta
    assert "GD-03 is ESTABLISHED" in handoff
    assert "GD-03 is niet langer OPEN" in handoff
    assert "geen nieuwe protocolversie" in handoff
    assert "Er worden geen reviewers verzonnen" in handoff
    assert "Er worden geen namen verzonnen" in handoff
    assert "G1 technische protection op `main` is ON" in handoff
    assert "G0 Azure DEV blijft `BLOCKED`" in handoff
    assert "v2.11.0" in governance
    assert "heropent GD-03 niet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"
    assert gd03["protocol_version"] == "2.4.0"
    assert gd03["decision_date"] == "2026-08-27"


def test_v211_records_kernel_build_order_without_implementing_code() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    handoff = _read(ROOT / "HANDOFF.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Do not build a mockup" in delta
    assert "The next implementation after this delta MUST be the Implementation engineer on the existing kernel" in delta
    assert "reject live URL-HTML at ingest" in delta
    assert "fail-closed Product API `supported` without a source locator" in delta
    assert "This delta does not implement ingest rejection or API fail-closed" in delta
    assert "PROTOCOL → tests → code later" in delta
    assert "Do not change `src/operations_console_*.py` or `src/product_api_*.py` in this protocol change" in delta
    assert "That console follow-up remains required" in delta
    assert "Where this delta and Protocol v2.10 §8 conflict on which implementation is next, this delta governs" in delta
    assert "Implementation engineer" in roadmap
    assert "bestaande kernel" in roadmap
    assert "Geen mockup" in roadmap
    assert "VIA de console" in roadmap or "VIA die console" in roadmap
    assert "Implementation engineer" in handoff
    assert "bestaande kernel" in handoff
    assert "geen mockup" in handoff
    assert "PROTOCOL → tests → code later" in handoff
    assert "deze v2.11-delta implementeert die ingest-weigering en API-fail-closed niet" in handoff
    assert "Protocol v2.11.0" in changelog
    assert "does not implement ingest rejection or API fail-closed" in changelog


def test_v211_keeps_g1_public_mvp_and_forbids_vercel_neon_llm() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    stack = _read(ROOT / "docs" / "STACK_SETUP_BASELINE.md")
    infra = json.loads((ROOT / "config" / "infrastructure_manifest.v1.json").read_text(encoding="utf-8"))
    assert "G1 technical protection remains ON" in delta
    assert "public under Protocol v2.5" in delta
    assert "G0 Azure DEV remains BLOCKED" in delta
    assert "No Vercel, Neon, or LLM vendor" in delta
    assert "No Azure/Vercel/Neon in this delta" in delta
    assert "G1 technische protection op `main` is ON" in handoff
    assert "G0 Azure DEV blijft `BLOCKED`" in handoff
    assert "Vercel, Neon and a hosted LLM" in stack
    assert "no vendor is selected" in stack
    assert "No LLM in the MVP" in stack
    assert "RAG on kennisplatform HTML is not the product" in stack
    assert "Protocol v2.11.0" in stack
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


def test_v211_does_not_implement_console_ui_or_product_code() -> None:
    delta = _read(DELTA)
    handoff = _read(ROOT / "HANDOFF.md")
    assert "This protocol-only change does not implement UI or product code" in delta
    assert "Do not rewrite `src/operations_console_*.py` or `src/product_api_*.py` in this protocol change" in delta
    assert "This delta does not implement ingest rejection or API fail-closed" in delta
    assert "This delta does not implement the new UI" in delta
    assert "It does not:" in delta
    assert "implement ingest rejection, freeze storage, Product API fail-closed behaviour, any room rewrite, or any other product code" in delta
    assert "ban HTML entirely" in delta
    assert "authorize scraping a live URL, reserializing freeze bytes, or binding line locators to an app shell" in delta
    assert "treat capture as publication, or convert G2 to PASS" in delta
    assert "skip durable immutable storage" in delta
    assert "reopen or alter GD-03" in delta
    assert "staff named human reviewers" in delta
    assert "deze v2.11-delta implementeert die ingest-weigering en API-fail-closed niet" in handoff
    assert "Deze delta implementeert de nieuwe UI niet" in handoff
