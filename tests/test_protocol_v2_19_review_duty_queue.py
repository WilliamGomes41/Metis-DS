from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_19_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v219_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.19.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-02"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v219_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.19.0" in delta
    assert "docs/PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.28.0") == 1
    assert "plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.18.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.17.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.16.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.19.0" in roadmap


def test_v219_does_not_redesign_the_four_layers_or_write_v214() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "This delta MUST NOT invent a fifth layer" in delta
    assert "MUST NOT collapse those four" in delta
    assert "source/evidence → canonical knowledge → governance → product" in delta
    assert "This file is not Protocol v2.14" in delta
    assert "This delta MUST NOT write Protocol v2.14" in delta
    assert "vier lagen" in root_protocol
    assert "Protocol v2.14 wordt in deze delta niet geschreven" in root_protocol
    assert "LOCKED als het volgende protocol (v2.14), niet deze PR" in roadmap
    assert "MUST NOT Protocol v2.14 worden geschreven" in roadmap


def test_v219_researchers_must_not_open_2008_inhoud_cards() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Researchers MUST NOT be required to open 2008 Inhoud cards one by one" in delta
    assert "That is the same fail as 4000 unclassified: fatigue, not assurance" in delta
    assert "Koppen 78 / Inhoud 2008" in delta
    assert "zet dat in protocol" in delta
    assert "4ebfdbb88cdb" in delta
    assert "snap-ac59cf24f946088e-e402c4d3" in delta
    assert "MUST NOT verplicht worden 2008 Inhoud-kaarten één voor één te openen" in root_protocol
    assert "Inhoud (2008)" in root_protocol
    assert "Koppen 78" in root_protocol
    assert "zet dat in protocol" in roadmap
    assert "Inhoud 2008" in roadmap


def test_v219_koppen_batch_confirm_as_structure() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Koppen MAY and MUST be batch-confirmable as structure, never as advice" in delta
    assert "Protocol v2.15 / v2.16 on this point are unchanged" in delta
    assert "There MUST NOT be a researcher control “zwaar/licht” or “snel/langzaam”" in delta
    assert "Koppen MAGEN en MUSTEN batch-bevestigbaar blijven als structuur" in root_protocol
    assert "Koppen-batch blijft" in roadmap


def test_v219_slow_review_is_recommendation_condition_exception_high_risk() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "The researcher-required slow review on a freeze is: proposed `recommendation`, plus `condition` / `exception` / any high-risk object" in delta
    assert "Those bound the advice. That is what they MUST do by hand" in delta
    assert "MUST NOT auto-confirm types" in delta
    assert "MUST NOT auto-promote ordinary text to `recommendation`" in delta
    assert "Machine classification remains a proposal, never published type" in delta
    assert "voorgestelde `recommendation`" in root_protocol
    assert "`condition` / `exception`" in root_protocol
    assert "trage baan is voorgestelde recommendation + condition/exception/high-risk" in roadmap


def test_v219_remaining_unclassified_must_not_be_presented_duty() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Remaining `unclassified` MUST NOT be presented as equal one-by-one work of thousands of cards" in delta
    assert "Unclassified is never served (`supported` / handelingsadvies), so 2000 clicks on it do not add assurance" in delta
    assert "`definition` / `explanation` MAY exist and MAY later answer non-advice questions once confirmed" in delta
    assert "they are NOT the MVP researcher 2000-card duty for handelingsadvies" in delta
    assert "Extract SHOULD still get coarser" in delta
    assert "this delta’s bar is review DUTY and queue presentation, not a new object type" in delta
    assert "resterende `unclassified` MUST NOT" in root_protocol
    assert "2000 klikken" in root_protocol
    assert "duizenden resterende unclassified MUST NOT de gepresenteerde plicht zijn" in roadmap


def test_v219_v218_held_and_2008_remains_a_fail() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Protocol v2.16 tiny-objects, Protocol v2.17 chrome, and Protocol v2.18 no-duplicate-sentence / trailing-clause / identical `clean_text` stay in force" in delta
    assert "2008 unclassified/Inhoud cards on one richtlijn remains a fail of this review surface" in delta
    assert "it looks better" in delta
    assert "v2.16 tiny-objects, v2.17 chrome, v2.18 geen-dubbele-zin" in root_protocol
    assert "2008 unclassified/Inhoud-kaarten" in root_protocol
    assert "2008 Inhoud blijft een fail" in roadmap


def test_v219_unpublished_continentie_reextract_and_no_hiding() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "unpublished Continentie MAY be re-extracted after this law" in delta
    assert "source SHA-256 stays" in delta or "Source SHA-256 stays" in delta
    assert "unpublished identities MAY be replaced" in delta
    assert "MUST NOT hide stored fragments without a new extract" in delta
    assert "unpublished Continentie MAG na deze wet opnieuw worden geëxtraheerd" in root_protocol or "unpublished Continentie MAG opnieuw worden geëxtraheerd" in root_protocol
    assert "unpublished Continentie" in roadmap


def test_v219_four_eyes_serving_v214_azure_unchanged() -> None:
    delta = _read(DELTA)
    assert "Four-eyes unchanged" in delta
    assert "The machine MUST NOT decide that something is light enough to serve" in delta
    assert "G2 remains the publication blocker" in delta
    assert "This delta does not implement `publish()` PASS" in delta
    assert "only confirmed `recommendation` MAY return `supported`" in delta or "Only confirmed `recommendation` MAY return `supported`" in delta or "only confirmed `recommendation` MAY be `supported`" in delta
    assert "Capture is not publication" in delta or "capture is not publication" in delta
    assert "This is not a GD-03 knowledge-publish" in delta
    assert "Protocol v2.14 unchanged" in delta or "Protocol v2.14 is not this file" in delta
    assert "Azure unchanged" in delta


def test_v219_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (presenting thousands of unclassified/Inhoud cards as the researcher-required one-by-one duty is fatigue, not assurance)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Protocol v2.19.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v219_records_queue_duty_wave_then_g2_and_does_not_implement_product_code() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Where this delta and Protocol v2.18 conflict on which implementation is next, this delta governs" in delta
    assert "Koppen batch stays" in delta
    assert "slow lane is proposed `recommendation` plus `condition` / `exception` / any high-risk object" in delta
    assert "thousands of leftover `unclassified` MUST NOT be the presented duty" in delta
    assert "THEN William click-through of the running console (not screenshots)" in delta
    assert "THEN Azure ZIP of that `main` from a V&VN-trusted device" in delta
    assert "THEN G2" in delta
    assert "Azure ZIP is after William accepts the live Review page" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "Protocol v2.19.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "v2.14 is not this and is not next" in changelog
    assert "wachtrij/plicht" in roadmap
    assert "Koppen-batch blijft" in roadmap


def test_v219_does_not_reopen_serving_typeset_stamps_chrome_slogans() -> None:
    delta = _read(DELTA)
    assert "Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, or relation-checkbox adjacency except as already required" in delta
    assert "The v2.12 closed serving typeset remains UNCHANGED" in delta
    assert "This delta’s bar is review DUTY and queue presentation, not a new object type" in delta


def test_v219_non_binding_hunch_is_not_a_requirement() -> None:
    delta = _read(DELTA)
    assert "Non-binding implementer hunch" in delta
    assert "Inhoud stack currently enumerates every leftover unclassified object" in delta
    assert "This hunch is not a protocol requirement" in delta
    assert "not in this protocol change" in delta
