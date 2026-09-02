from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_18_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v218_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.18.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-02"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v218_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.18.0" in delta
    assert "docs/PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.19.0") == 1
    assert "plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.18.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.17.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.16.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.18.0" in roadmap


def test_v218_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v218_review_card_shows_freeze_sentence_once() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "The review object card MUST show the freeze sentence once" in delta
    assert "MUST NOT duplicate it as both h3/title and body" in delta
    assert "Compact row / card: one source sentence plus short status" in delta
    assert "The Protocol v2.16 compact-row bar applies to the open card, not only the list" in delta
    assert "De dubbeling is niet opgelost" in delta
    assert "Eventueel met hulp van de mantelzorger." in delta
    assert "reviewkaart MUST de freeze-zin één keer tonen" in root_protocol
    assert "MUST NOT dupliceren als zowel h3/titel als body" in root_protocol
    assert "open kaart, niet alleen de lijst" in roadmap


def test_v218_extract_must_not_split_grammatical_continuation() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Extract MUST NOT split a grammatical continuation of the previous sentence into a new object" in delta
    assert "Trailing clauses MUST stay in the same knowledge object as the sentence they complete" in delta
    assert "This restates and tightens the Protocol v2.16 truncated-sentence / tiny-object forbid" in delta
    assert "The v2.17 Continentie re-extract still failed it" in delta
    assert "Eventueel met hulp van de mantelzorger." in delta
    assert "Bijvoorbeeld" in delta
    assert "This is NOT fusion of condition into recommendation" in delta
    assert "MUST NOT een grammaticale voortzetting" in root_protocol
    assert "naloopzinnen" in root_protocol
    assert "naloopzin" in roadmap or "naloopzinnen" in roadmap


def test_v218_extract_must_not_emit_identical_clean_text_twice() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Extract MUST NOT emit a second knowledge object whose visible freeze prose (`clean_text`) is identical" in delta
    assert "Repeated HTML (samenvatting versus module) is not extra knowledge" in delta
    assert "Distinct real headings in different sections MAY remain" in delta
    assert "`1.1 Inleiding` versus `2. Inleiding` are not identical strings" in delta
    assert "indices ~92/93, 769/770, 2510/2511" in delta
    assert "MUST NOT hide stored fragments without a new extract" in delta
    assert "identieke clean_text" in root_protocol
    assert "samenvatting versus module" in root_protocol or "samenvatting vs module" in root_protocol
    assert "1.1 Inleiding" in roadmap
    assert "identieke clean_text" in roadmap


def test_v218_v217_chrome_and_slogan_held() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Chrome Tools/Home is gone (v2.17 held)" in delta
    assert "Slogan gone (v2.17 held)" in delta
    assert "This fail is duplication + truncated-sentence split" in delta
    assert "snap-ac59cf24f946088e-6538b559" in delta
    assert "3e811bf0fc9f" in delta
    assert "v2.17 gehouden" in root_protocol
    assert "v2.17 gehouden" in roadmap


def test_v218_unpublished_continentie_reextract_and_no_hiding() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "a new extract of the same freeze bytes is REQUIRED" in delta
    assert "Source hash of the freeze stays" in delta
    assert "Unpublished object identities MAY be replaced" in delta
    assert "MUST NOT hide stored fragments without a new extract" in delta
    assert "unpublished Continentie MAG opnieuw worden geëxtraheerd" in root_protocol
    assert "unpublished Continentie" in roadmap


def test_v218_four_eyes_serving_v214_azure_unchanged() -> None:
    delta = _read(DELTA)
    assert "Four-eyes unchanged" in delta
    assert "The machine MUST NOT decide that something is light enough to serve" in delta
    assert "G2 remains the publication blocker" in delta
    assert "This delta does not implement `publish()` PASS" in delta
    assert "only confirmed `recommendation` MAY return `supported`" in delta or "Only confirmed `recommendation` MAY return `supported`" in delta
    assert "Capture is not publication" in delta
    assert "This is not a GD-03 knowledge-publish" in delta
    assert "Protocol v2.14 unchanged" in delta or "Protocol v2.14 is not this file" in delta
    assert "Azure unchanged" in delta


def test_v218_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (duplicate card sentence, truncated-sentence split, and identical freeze prose as extra objects bias assessment)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Protocol v2.18.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v218_records_extract_card_wave_then_g2_and_does_not_implement_product_code() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Where this delta and Protocol v2.17 conflict on which implementation is next, this delta governs" in delta
    assert "the open review object card MUST show the freeze sentence once" in delta
    assert "extract MUST NOT split a grammatical continuation" in delta
    assert "extract MUST NOT emit a second knowledge object whose visible freeze prose (`clean_text`) is identical" in delta
    assert "re-extract unpublished Continentie" in delta
    assert "THEN William click-through of the running console (not screenshots)" in delta
    assert "THEN Azure ZIP of that `main` from a V&VN-trusted device" in delta
    assert "THEN G2" in delta
    assert "Azure ZIP is after William accepts the live Review page" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "Protocol v2.18.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "v2.14 is not this and is not next" in changelog
    assert "extract+kaart" in roadmap or "extract+card" in roadmap
    assert "één keer" in roadmap


def test_v218_non_binding_hunch_is_not_a_requirement() -> None:
    delta = _read(DELTA)
    assert "Non-binding implementer hunch" in delta
    assert "review_row_title` equals `clean_text`" in delta or "review_row_title equals `clean_text`" in delta
    assert "HTML parser splits on period / `p` tags" in delta
    assert "This hunch is not a protocol requirement" in delta
    assert "not in this protocol change" in delta
