from __future__ import annotations

import json
from pathlib import Path

from src.integrity_kernel import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_12_OBJECT_TYPE_REVIEW_PROJECTION_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_12_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v212_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.12.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_12_OBJECT_TYPE_REVIEW_PROJECTION_DELTA.md"
    assert manifest["protocol_sha256"] == sha256_file(DELTA)
    assert manifest["commit_sha"] == "2f12c26fe20d8742b820ab8cc70014dd32d724aa"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v212_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.12.0" in delta
    assert "docs/PROTOCOL_V2_12_OBJECT_TYPE_REVIEW_PROJECTION_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.26.0") == 1
    assert "plus Protocol v2.12.0" in root_protocol
    assert "plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.10.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.11.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.12.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.12.0" in roadmap


def test_v212_hierarchy_points_at_combined_live_version_without_rewriting_v212_delta() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    delta = _read(DELTA)
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.26.0") == 1
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
    assert "docs/PROTOCOL_V2_15_INGEST_DATE_VERSION_REVIEW_LANES_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md" in root_protocol
    assert "docs/PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md" in root_protocol
    assert (
        "v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0 and this delta jointly form normative baseline v2.12.0"
        in delta
    )
    assert "Protocol v2.11 is not live baseline" in delta
    assert "PR #27" in delta


def test_v212_keeps_all_v26_through_v210_rules() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
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


def test_v212_does_not_redesign_the_four_layers() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Do not redesign the four layers (source/evidence → canonical knowledge → governance → product)" in delta
    assert "The problem is semantic classification and the hard binding of review, publication and serving" in delta
    assert "The four layers remain source/evidence → canonical knowledge → governance → product" in delta
    assert "This delta MUST NOT invent a fifth layer" in delta
    assert "vier lagen" in root_protocol
    assert "bron/evidence" in root_protocol
    assert "canonieke kennis" in root_protocol
    assert "vier lagen" in roadmap


def test_v212_extraction_is_structure_and_provenance_only() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Extraction MUST determine structure and provenance only, NOT the meaning of a passage" in delta
    assert "A heading MAY become object_type `heading`" in delta
    assert "Everything that is not a heading MUST default to `unclassified`" in delta
    assert "The machine MAY propose a type" in delta
    assert "A human reviewer MUST confirm the definitive `object_type` before publication" in delta
    assert "An unconfirmed proposal MUST NOT be treated as published type" in delta
    assert "Extractie MUST alleen structuur en provenance bepalen" in root_protocol
    assert "unclassified" in root_protocol
    assert "niet de betekenis" in root_protocol
    assert "Extractie MUST alleen structuur en provenance bepalen" in roadmap
    assert "unclassified" in roadmap


def test_v212_closed_object_type_set_does_not_invent_types() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`" in delta
    assert "Operators MUST NOT invent types in the MVP" in delta
    assert "`unclassified` is the default, not a sixth advice type" in delta
    assert "`unclassified` MUST NOT be treated as a published type" in delta
    assert "Operators MUST NOT types verzinnen" in root_protocol
    assert "geen zesde advies-type" in root_protocol
    assert "gesloten object-typeset" in roadmap
    assert "geen zesde advies-type" in roadmap


def test_v212_answerability_joins_question_type_and_object_type() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Answerability MUST join question type × object type" in delta
    assert 'MUST NOT be "only recommendations are supported"' in delta
    assert "supported when the available, reviewed object type is suitable for the claimed question" in delta
    assert "Only `recommendation` MAY return as action advice (`handelingsadvies`)" in delta
    assert "a `definition` MAY answer a definition question" in delta
    assert "`explanation` MAY support explanation" in delta
    assert "`condition` and `exception` MAY bound advice" in delta
    assert "Those other types MUST NOT receive advice-weight" in delta
    assert "A podcast/article still cannot fill a missing guideline (v2.8 class axis unchanged)" in delta
    assert "`unclassified` MUST NOT be `supported`" in delta
    assert "vraagtype × objecttype" in root_protocol
    assert "niet alleen recommendations" in root_protocol
    assert "handelingsadvies" in root_protocol
    assert "geen advies-gewicht" in root_protocol
    assert "vraagtype × objecttype" in roadmap
    assert "handelingsadvies" in roadmap


def test_v212_publish_binds_object_tuple_not_envelope_tick() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Cutover/publish MUST NOT trust envelope `review_passes` alone" in delta
    assert "`object_id` + `object_version` + `canonical_object_hash` + `confirmed_object_type` + `reviewer` + `decision`" in delta
    assert "Independence rule unchanged (uploader MUST NOT be the only required reviewer)" in delta
    assert "High-risk still needs the required review track" in delta
    assert "Future `publish()` (still G2-blocked) MUST check this tuple, not an envelope tick" in delta
    assert "Review MUST be bound to that exact object version and that exact `canonical_object_hash`" in delta
    assert "review_passes" in root_protocol
    assert "object_id" in root_protocol
    assert "canonical_object_hash" in root_protocol
    assert "confirmed_object_type" in root_protocol
    assert "review_passes" in roadmap
    assert "canonical_object_hash" in roadmap


def test_v212_serving_uses_atomic_published_projection() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "The Product API remains a derived read-only layer" in delta
    assert "Serving MUST use a validated published projection" in delta
    assert "Publish, withdraw and supersede MUST replace that projection atomically" in delta
    assert "The API MUST read only the current published projection" in delta
    assert "It MUST NOT reconstruct live governance per query" in delta
    assert "A stale projection after withdraw is a protocol failure" in delta
    assert "Capture is not publication" in delta
    assert "G2 still blocks actual publish" in delta
    assert "MUST apply to any fixture/real projection already in the API" in delta
    assert "afgeleide read-only laag" in root_protocol
    assert "gevalideerde gepubliceerde projectie" in root_protocol
    assert "atomair" in root_protocol
    assert "verouderde projectie" in root_protocol
    assert "gevalideerde gepubliceerde projectie" in roadmap
    assert "atomair" in roadmap


def test_v212_delta_keeps_historical_pr27_lock_while_wiring_lists_v211_live() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Ingest URL-HTML remains the v2.11 lock (PR #27, not this file)" in delta
    assert "live URL-HTML MUST NOT be a publishable source" in delta
    assert "uploaded freeze-HTML MAY" in delta
    assert "PDF via URL MAY if exact received bytes are stored and hashed immediately" in delta
    assert "v2.12 MUST NOT treat #27 as a substitute for this semantic delta" in delta
    assert "Do not duplicate v2.11 as if it were already on main" in delta
    assert "Protocol v2.11 is not live baseline" in delta
    assert "This delta MUST NOT merge, edit or close PR #27" in delta
    assert "docs/PROTOCOL_V2_11_HTML_FREEZE_LOCATOR_DELTA.md" in root_protocol
    assert "plus Protocol v2.11.0" in root_protocol
    assert "Protocol v2.11.0" in roadmap
    assert "De geldende normatieve baseline is Protocol v2.11.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.11.0" not in roadmap
    assert "niet de live baseline" not in root_protocol
    assert "niet de live baseline" not in roadmap


def test_v212_keeps_fail_closed_exclusions_and_gitignore() -> None:
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
        "no locator implementation, no Blob, no claiming G2 PASS",
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


def test_v212_is_c3_spanning_c5_with_owner_approval_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 (retrieve-safety / answerability) spanning C5 (review/publish authorization binding)" in delta
    assert "C5 applies only as review/publish authorization binding" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "This delta is owner-approved" in delta
    assert "Retrospective independent clinical and technical review remains due" in delta
    assert "PR #26" in delta
    assert "PR #24" in delta
    assert "does not reopen GD-03" in delta
    assert "v2.12.0" in governance
    assert "heropent GD-03 niet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"
    assert gd03["protocol_version"] == "2.4.0"
    assert gd03["decision_date"] == "2026-08-27"


def test_v212_records_kernel_build_order_without_implementing_code_or_starting_azure() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Do not build a mockup" in delta
    assert "The next implementation after this protocol (not this PR) MUST be the Implementation engineer on the existing kernel" in delta
    assert "object taxonomy default `unclassified` + proposal/confirm" in delta
    assert "answerability × type" in delta
    assert "review bound to exact object version + hash" in delta
    assert "atomic published projection and correct withdrawal/supersede" in delta
    assert "THEN G2/Azure" in delta
    assert "Do not start Azure in this change" in delta
    assert "This protocol-only change does not implement extract/API/console changes" in delta
    assert "PROTOCOL → tests → code later" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change" in delta
    assert "That console follow-up remains required" in delta
    assert "Where this delta and Protocol v2.10 §8 conflict on which implementation is next, this delta governs" in delta
    assert "Implementation engineer" in roadmap
    assert "bestaande kernel" in roadmap
    assert "Geen mockup" in roadmap
    assert "VIA de console" in roadmap or "VIA die console" in roadmap
    assert "Protocol v2.12.0" in changelog
    assert "does not implement extract, API or console changes" in changelog


def test_v212_keeps_g1_public_mvp_and_forbids_azure_g2_vercel_neon_llm() -> None:
    delta = _read(DELTA)
    stack = _read(ROOT / "docs" / "STACK_SETUP_BASELINE.md")
    infra = json.loads((ROOT / "config" / "infrastructure_manifest.v1.json").read_text(encoding="utf-8"))
    assert "G1 technical protection remains ON" in delta
    assert "public under Protocol v2.5" in delta
    assert "G0 Azure DEV remains BLOCKED" in delta
    assert "No Vercel, Neon, or LLM vendor" in delta
    assert "No Azure/Vercel/Neon in this delta" in delta
    assert "Azure/G2 MUST stay out of this delta" in delta
    assert "Vercel, Neon and a hosted LLM" in stack
    assert "no vendor is selected" in stack
    assert "No LLM in the MVP" in stack
    assert "RAG on kennisplatform HTML is not the product" in stack
    assert "Protocol v2.12.0" in stack
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


def test_v212_does_not_implement_extract_api_or_console_code() -> None:
    delta = _read(DELTA)
    assert "This protocol-only change does not implement extract, API or console changes" in delta
    assert "Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change" in delta
    assert "This delta does not implement extract, API or console changes" in delta
    assert "This delta does not implement the new UI" in delta
    assert "It does not:" in delta
    assert "implement extract, taxonomy, proposal/confirm, answerability, review-binding, projection, Product API, console or any other product code" in delta
    assert "redesign the four layers (source/evidence → canonical knowledge → governance → product)" in delta
    assert "treat PR #27 / Protocol v2.11 as live baseline, or duplicate v2.11 as if it were already on main" in delta
    assert "merge, edit or close PR #27" in delta
    assert "treat capture as publication, or convert G2 to PASS" in delta
    assert "implement locators, freeze storage, ingest rejection, Azure Blob, or any G2 claim" in delta
    assert "skip durable immutable storage" in delta
    assert "reopen or alter GD-03" in delta
    assert "staff named human reviewers" in delta
