from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_16_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v216_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.16.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-02"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v216_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.16.0" in delta
    assert "docs/PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.19.0") == 1
    assert "plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.16.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.16.0" in roadmap


def test_v216_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v216_researcher_bar_first_screen() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "The Review page is the page that MUST convince guideline researchers" in delta
    assert "Two frustrations MUST NOT remain" in delta
    assert "Within one screen the researcher MUST know: which document this is, what to do now, and why" in delta
    assert "this becomes what an EPD may say" in delta
    assert "UI copy MUST be researcher language" in delta
    assert "Primary action MUST be visually obvious" in delta
    assert "Kernel ids MUST NOT be the row title" in delta
    assert "onderzoekers overtuigen" in root_protocol
    assert "kernel-ids MUST NOT de rijtitel zijn" in root_protocol


def test_v216_one_door_beoordeel() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "MUST NOT keep two doors **Openen** plus **Reviewen**" in delta
    assert "One document card, one primary button **Beoordeel**" in delta
    assert "Openen-as-a-second-path to the same list is forbidden" in delta
    assert "één primaire knop Beoordeel" in root_protocol
    assert "Beoordeel" in roadmap


def test_v216_two_named_stacks_with_counts() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "**Koppen** — real table-of-contents / section titles from the freeze" in delta
    assert "**Inhoud** — `definition`, `explanation`, `condition`, `exception`, `recommendation`, and `unclassified` until typed" in delta
    assert "Counts MUST be visible on each stack" in delta
    assert "MUST NOT present a page of thousands of identical `unclassified` titles" in delta
    assert "There MUST NOT be a researcher control “zwaar/licht”" in delta
    assert "Headings MUST NOT be served as handelingsadvies" in delta
    assert "Koppen" in root_protocol
    assert "Inhoud" in root_protocol
    assert "Koppen" in roadmap
    assert "Inhoud" in roadmap


def test_v216_compact_rows() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "Each list row MUST be one compact line" in delta
    assert "MUST NOT stretch status / checkbox / text into disconnected columns across the viewport" in delta
    assert "MUST NOT use the type name (`unclassified`) or a kernel document id as the title" in delta
    assert "compacte rijen" in root_protocol
    assert "MUST NOT status/checkbox/tekst over de viewport spreiden" in root_protocol


def test_v216_stamps_not_objects() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "DOEN / OVERWEEG / NIET DOEN are stamps, not objects" in delta
    assert "MUST NOT invent GRADE jargon on this screen" in delta
    assert "MUST NOT add a new object type" in delta
    assert "MUST NOT be rows in Koppen" in delta
    assert "MUST NOT be standalone knowledge objects" in delta
    assert "Closed values on type `recommendation` only: `doen` | `overweeg` | `niet_doen`" in delta
    assert "This is NOT fusion of condition into recommendation" in delta
    assert "Extract MUST NOT propose `heading` for DOEN/OVERWEEG/NIET DOEN" in delta
    assert "Sterkte van de aanbeveling: DOEN — dit moet de zorgverlener doen." in delta
    assert "stempels, geen objecten" in root_protocol
    assert "`doen` | `overweeg` | `niet_doen`" in root_protocol
    assert "stempels" in roadmap


def test_v216_no_tiny_objects_and_unpublished_continentie_reextract() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Extract MUST NOT emit a knowledge object whose confirmable text is only a list number (`1.`)" in delta
    assert "A lone trailing word of a previous sentence is forbidden" in delta
    assert "Freeze source bytes and SHA-256 stay" in delta
    assert "Continentie is unpublished: a new extract of the same freeze bytes is REQUIRED" in delta
    assert "unpublished object identities MAY be replaced" in delta
    assert "MUST NOT lie in the UI by hiding stored fragments without a new extract" in delta
    assert "tiny objects" in root_protocol
    assert "nieuwe extract van dezelfde freeze-bytes is VERPLICHT" in root_protocol
    assert "unpublished Continentie" in roadmap or "unpublished Continentie-freeze" in roadmap


def test_v216_four_eyes_and_serving_law_unchanged() -> None:
    delta = _read(DELTA)
    assert "Four-eyes unchanged" in delta
    assert "The machine MUST NOT decide that something is light enough to serve" in delta
    assert "G2 remains the publication blocker" in delta
    assert "This delta does not implement `publish()` PASS" in delta
    assert "only confirmed `recommendation` MAY return as action advice" in delta or "Only confirmed `recommendation` MAY return `supported`" in delta


def test_v216_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (a messy review page biases assessment)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Protocol v2.16.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v216_records_review_page_wave_then_g2_and_does_not_implement_product_code() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Where this delta and Protocol v2.15 conflict on which implementation is next, this delta governs" in delta
    assert "one door **Beoordeel**" in delta
    assert "two named stacks with counts (Koppen / Inhoud)" in delta
    assert "compact one-line rows with source text" in delta
    assert "THEN William click-through of the running console (not screenshots)" in delta
    assert "THEN Azure ZIP of that `main` from a V&VN-trusted device" in delta
    assert "THEN G2" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "Protocol v2.16.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "v2.14 is not this and is not next" in changelog
    assert "één deur Beoordeel" in roadmap
    assert "Koppen/Inhoud" in roadmap or "Koppen / Inhoud" in roadmap
    assert "tiny objects" in roadmap
