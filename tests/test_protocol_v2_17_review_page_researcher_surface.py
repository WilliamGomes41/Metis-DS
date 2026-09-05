from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_17_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v217_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.17.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-02"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v217_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.17.0" in delta
    assert "docs/PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.29.0") == 1
    assert "plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.17.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.16.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.17.0" in roadmap


def test_v217_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v217_researcher_copy_no_slogans() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "UI copy MUST be researcher language" in delta
    assert "MUST NOT be slogans" in delta
    assert "MUST NOT say “wat een EPD MAG zeggen”" in delta
    assert "The entire sentence “Dit wordt wat een EPD MAG zeggen.” MAG weg" in delta
    assert "Keep this forbid; do not weaken it" in delta
    assert "MUST NOT claim a single subscriber class" in delta
    assert "Beoordeel **Koppen** as structure, **Inhoud** as knowledge objects" in delta
    assert "The Protocol v2.16 “why it matters (this becomes what an EPD may say)” reading is superseded" in delta
    assert "geen slogans" in root_protocol
    assert "wat een EPD MAG zeggen" in root_protocol
    assert "Beoordeel Koppen als structuur" in root_protocol


def test_v217_no_via_negativa_on_researcher_rooms() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "via-negativa MUST NOT appear on researcher rooms at all, including collapsed help" in delta
    assert "Collapsed help titled “Over deze console”" in delta
    assert "Protocol v2.9 §4" in delta
    assert "MAY appear once in a short help" in delta
    assert "is superseded for researcher rooms" in delta
    assert "via-negativa MUST NOT op onderzoekerspagina's" in root_protocol


def test_v217_empty_onderwerp_on_fresh_ingest() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "Onderwerp (researcher label for kernel family) MUST be empty on a fresh new ingest" in delta
    assert "MUST NOT prefill `continentie`" in delta
    assert "This is not browser cache" in delta
    assert "this delta MUST NOT expand scope to class" in delta
    assert "Class MAY still default to `richtlijn`" in delta
    assert "Onderwerp/familie MUST leeg zijn" in root_protocol


def test_v217_bronpassage_is_readable_prose_not_raw_html() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "The researcher right column MUST show the same readable sentence as the knowledge object" in delta
    assert "MUST NOT show raw HTML freeze slices" in delta
    assert "Protocol v2.11 freeze bytes and locators stay exact" in delta
    assert "MUST NOT reserialize, pretty-print, or re-save the freeze" in delta
    assert "visible prose derived from that locator, not the raw tag soup" in delta
    assert "Open-origineel remains required before type confirm" in delta
    assert "Strip tags only for display; locators stay on freeze bytes" in delta
    assert "bronpassage" in root_protocol
    assert "leesbare zin" in root_protocol
    assert "bronpassage" in roadmap


def test_v217_site_chrome_must_not_be_objects_or_koppen() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Extract MUST NOT emit kennisplatform chrome as knowledge objects" in delta
    assert "MUST NOT land that chrome in Koppen" in delta
    assert "Home, Richtlijnen, Meedenken, Kennisinstituut V&VN, Tools, Veelgestelde vragen" in delta
    assert "Koppen MUST be real guideline TOC / section titles of the richtlijn body, not site nav" in delta
    assert "Chrome MUST NOT become `heading`" in delta
    assert "Chrome MUST NOT become `unclassified`" in delta
    assert "kennisplatform-chrome" in root_protocol
    assert "kennisplatform-chrome" in roadmap


def test_v217_unclassified_bar_unchanged_and_unpublished_continentie_reextract() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "2641 unclassified on one richtlijn remains a fail of the review surface" in delta
    assert "The Protocol v2.15 / v2.16 bar is unchanged" in delta
    assert "a new extract of the same freeze bytes is REQUIRED" in delta
    assert "Source hash of the freeze stays" in delta
    assert "Unpublished object identities MAY be replaced" in delta
    assert "MUST NOT hide stored fragments without a new extract" in delta
    assert "2641 unclassified" in root_protocol
    assert "unpublished Continentie" in roadmap


def test_v217_four_eyes_and_serving_law_unchanged() -> None:
    delta = _read(DELTA)
    assert "Four-eyes unchanged" in delta
    assert "The machine MUST NOT decide that something is light enough to serve" in delta
    assert "G2 remains the publication blocker" in delta
    assert "This delta does not implement `publish()` PASS" in delta
    assert "only confirmed `recommendation` MAY return `supported`" in delta or "Only confirmed `recommendation` MAY return `supported`" in delta
    assert "Capture is not publication" in delta
    assert "This is not a GD-03 knowledge-publish" in delta


def test_v217_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (slogan copy, via-negativa help, raw-HTML bronpassage, site chrome as objects, stamp UI on non-recommendation, and stretched relation checkboxes bias assessment)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Protocol v2.17.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v217_records_researcher_surface_wave_then_g2_and_does_not_implement_product_code() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Where this delta and Protocol v2.16 conflict on which implementation is next, this delta governs" in delta
    assert "researcher copy without slogans" in delta
    assert "empty Onderwerp on a fresh ingest" in delta
    assert "bronpassage readable prose" in delta
    assert "no chrome objects" in delta
    assert "re-extract unpublished Continentie" in delta
    assert "THEN William click-through of the running console (not screenshots)" in delta
    assert "THEN Azure ZIP of that `main` from a V&VN-trusted device" in delta
    assert "THEN G2" in delta
    assert "Azure ZIP is after William accepts the live Review page" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "Protocol v2.17.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "v2.14 is not this and is not next" in changelog
    assert "leeg Onderwerp" in roadmap
    assert "bronpassage" in roadmap
    assert "kennisplatform-chrome" in roadmap
    assert "recommendation-strength UI only on `recommendation`" in delta
    assert "compact relation checkboxes with label adjacent to the checkbox" in delta
    assert "bronpassage readable prose on every object" in delta
    assert "one-word Tools/Home/Richtlijnen/Meedenken" in delta


def test_v217_one_word_site_chrome_must_not_be_an_object() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "One-word site chrome MUST NOT be an object" in delta
    assert "One-word chrome remains a fail under Protocol v2.16 tiny-objects **and** this chrome rule" in delta
    assert "Tools, Home, Richtlijnen, Meedenken and the rest of kennisplatform nav MUST NOT be knowledge objects" in delta
    assert "Je krijgt soms nogsteeds 1 woord" in delta
    assert "a review card titled **Tools**, unclassified, snippet the single word Tools" in delta
    assert "één-woord Tools" in root_protocol
    assert "één-woord Tools" in roadmap
    assert "Tools/Home/Richtlijnen/Meedenken MUST NOT objecten zijn" in root_protocol


def test_v217_recommendation_strength_ui_only_on_recommendation() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Recommendation-strength UI (**Sterkte van de aanbeveling**, the DOEN/OVERWEEG/NIET DOEN picker) MUST NOT appear except on type `recommendation`" in delta
    assert "A nav word MUST NOT get a recommendation-strength control" in delta
    assert "Stamps exist only on type `recommendation`" in delta
    assert "Showing that picker on unclassified **Tools** is forbidden" in delta
    assert "stempel-UI" in root_protocol
    assert "MUST NOT verschijnen behalve op type `recommendation`" in root_protocol
    assert "stempel-UI alleen op recommendation" in roadmap


def test_v217_relation_checkbox_and_label_must_be_adjacent() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "The relation label MUST sit immediately next to its checkbox" in delta
    assert "MUST NOT stretch checkbox and target title to opposite edges of the viewport" in delta
    assert "That bar MUST also bind relation checkboxes on the object card" in delta
    assert "vinkje and Inleiding still lie very far apart" in delta
    assert "relatielabel MUST direct naast het vinkje zitten" in root_protocol
    assert "MUST NOT checkbox en doeltitel naar tegenoverliggende randen van de viewport spreiden" in root_protocol
    assert "compacte relatiecheckboxes" in roadmap


def test_v217_bronpassage_prose_rule_is_per_object_whole_freeze() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "This bronpassage prose rule is **per-object / whole freeze**, not a one-off on one card" in delta
    assert "Same law for every object and every section" in delta
    assert "Researcher bronpassage MUST be the readable sentence, never tags" in delta
    assert "Recorded answer: **NO**" in delta
    assert "Is dat hoe het definitief eruit gaat zien?" in delta
    assert "ieder object / de hele freeze" in root_protocol
    assert "opgenomen antwoord op «Is dat hoe het definitief eruit gaat zien?» is NEE" in root_protocol
    assert "ieder object / de hele freeze" in roadmap


def test_v217_inleiding_doel_doelgroep_aanleiding_are_examples_not_a_closed_list() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "**Inleiding**, **Doel**, **Doelgroep** and **Aanleiding** are examples of sections the law covers, not a closed list" in delta
    assert "These rules (no slogans, no one-word chrome, compact relation checkboxes, bronpassage prose not HTML, recommendation-strength UI only on `recommendation`) apply to the **whole freeze / every object / every section**" in delta
    assert "Ik zie inleiding, doel, doelgroep en aanleiding vaker voorkomen" in delta
    assert "Operators MUST NOT treat a later section as exempt because the photo was of Tools, Inleiding, or doelgroep" in delta
    assert "Inleiding, Doel, Doelgroep, Aanleiding zijn voorbeelden, geen gesloten lijst" in root_protocol
    assert "Inleiding, Doel, Doelgroep en Aanleiding zijn voorbeelden, geen gesloten lijst" in roadmap
    assert "hele freeze / ieder object / iedere sectie" in root_protocol
    assert "hele freeze / ieder object / iedere sectie" in roadmap
