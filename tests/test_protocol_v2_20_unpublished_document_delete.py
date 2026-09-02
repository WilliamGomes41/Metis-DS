from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_20_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v220_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.20.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-02"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v220_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.20.0" in delta
    assert "docs/PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.22.0") == 1
    assert "plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.20.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.19.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.18.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.17.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.16.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.20.0" in roadmap


def test_v220_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v220_protocol_is_every_guideline_law_not_continentie_only() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`PROTOCOL.md` is the law of V&VN Data Services for every guideline, not a Continentie-only protocol" in delta
    assert "Continentie appears in Protocol v2.16–v2.19 as live evidence of fails" in delta
    assert "stamp words as Koppen; 2008 Inhoud cards" in delta
    assert "Those historical evidence sentences MUST remain. This delta MUST NOT strip them." in delta
    assert "The next freeze MUST NOT have to be Continentie" in delta
    assert "PROTOCOL.md is de wet van V&VN Data Services voor iedere richtlijn, niet Continentie-only" in root_protocol
    assert "historische bewijszinnen MUST blijven" in root_protocol
    assert "de volgende freeze MUST NOT Continentie hoeven zijn" in root_protocol
    assert "niet Continentie-only" in roadmap
    assert "volgende freeze MUST NOT Continentie" in roadmap


def test_v220_does_not_strip_v216_v219_continentie_evidence() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain" in delta
    assert "Those sentences are live evidence of fails, not the product identity" in delta
    assert "Inhoud (2008) / Koppen 78 op Continentie" in root_protocol
    assert "stempels als Koppen, 2008 Inhoud-kaarten" in root_protocol
    assert "snap-ac59cf24f946088e-e402c4d3" in root_protocol


def test_v220_unpublished_snapshots_may_be_deleted_by_console_operator() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Unpublished captured snapshots MAY be removed from the operations console by an authorized console operator" in delta
    assert "named researcher or reviewer account, not a secret engineer path" in delta
    assert "This is owner-authorized cleanup of unpublished capture, not publication, not G2" in delta
    assert "unpublished captured snapshots MAGEN van de operations console worden verwijderd" in root_protocol
    assert "benoemd researcher/reviewer-account, geen geheim engineer-pad" in root_protocol
    assert "eigenaarsgeautoriseerde opruiming" in roadmap


def test_v220_must_have_real_delete_control_with_confirm() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "MUST have a real delete control on the document card / Review chooser for unpublished snapshots only" in delta
    assert "The label MUST be researcher Dutch, for example **Verwijder unpublished document**" in delta
    assert "The control MUST confirm before it runs. Delete is destructive." in delta
    assert "MUST een echte verwijdercontrole op de documentkaart / Review-chooser" in root_protocol
    assert "Verwijder unpublished document" in root_protocol
    assert "MUST bevestigen vóór uitvoering (destructief)" in root_protocol
    assert "Verwijder unpublished document" in roadmap
    assert "bevestigen vóór uitvoering" in roadmap


def test_v220_after_delete_lists_objects_envelope_audit() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "that snapshot MUST NOT appear on Inleveren, Review or Documentenhierarchie lists" in delta
    assert "Stored objects and the envelope for that `snapshot_id` are gone" in delta
    assert "Freeze bytes of that unpublished source MAY be removed with it" in delta
    assert "MUST NOT touch other snapshots" in delta
    assert "MUST NOT touch `/home/data` globally" in delta
    assert "MUST append an audit ledger row: who, when, `snapshot_id`, source SHA-256, title" in delta
    assert "MUST de snapshot NOT verschijnen op Inleveren/Review/Documentenhierarchie-lijsten" in root_protocol
    assert "opgeslagen objecten+envelope voor die snapshot_id zijn weg" in root_protocol
    assert "audit-ledgerrij" in root_protocol
    assert "audit-ledger" in roadmap


def test_v220_must_not_delete_published_or_hide_fragments() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "MUST NOT delete a published projection or anything that has been published" in delta
    assert "`publish()` stays G2-BLOCKED" in delta
    assert "There is no published Continentie" in delta
    assert "MUST NOT use this to hide selected objects inside a freeze that stays in Review" in delta
    assert "Protocol v2.16 hide-fragments-without-extract remains" in delta
    assert "This delete is the whole unpublished snapshot only" in delta
    assert "MUST NOT een gepubliceerde projectie of iets dat is gepubliceerd verwijderen" in root_protocol
    assert "er is geen gepubliceerde Continentie" in root_protocol
    assert "v2.16 hide-fragments-without-extract blijft" in root_protocol
    assert "geen gepubliceerde Continentie" in roadmap


def test_v220_must_not_ssh_wipe_home_data() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "MUST NOT SSH or wipe `/home/data` as the product path" in delta
    assert "The console action is the path" in delta
    assert "MUST NOT SSH/wipe van `/home/data` als productpad" in root_protocol
    assert "de console-actie is het pad" in root_protocol
    assert "SSH/wipe" in roadmap or "SSH/wipe van `/home/data`" in roadmap


def test_v220_four_eyes_not_required_for_unpublished_delete() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Four-eyes is not required to delete unpublished capture" in delta
    assert "The uploader MAY delete unpublished they captured" in delta
    assert "A second named reviewer is not required for delete. Delete is not type-confirm." in delta
    assert "four-eyes is niet vereist om unpublished capture te verwijderen" in root_protocol
    assert "de uploader MAG unpublished die zij captureden verwijderen" in root_protocol
    assert "delete is geen type-bevestiging" in root_protocol
    assert "four-eyes is niet vereist" in roadmap


def test_v220_four_eyes_serving_v214_azure_unchanged() -> None:
    delta = _read(DELTA)
    assert "Four-eyes unchanged for type-confirm and high-risk" in delta
    assert "The machine MUST NOT decide that something is light enough to serve" in delta
    assert "G2 remains the publication blocker" in delta
    assert "This delta does not implement `publish()` PASS" in delta
    assert "only confirmed `recommendation` MAY return `supported`" in delta or "Only confirmed `recommendation` MAY return `supported`" in delta
    assert "Capture is not publication" in delta or "capture is not publication" in delta
    assert "This is not a GD-03 knowledge-publish" in delta
    assert "Protocol v2.14 unchanged" in delta or "Protocol v2.14 is not this file" in delta
    assert "Azure unchanged" in delta


def test_v220_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (PROTOCOL.md is every-guideline law, not Continentie-only; unpublished captured snapshots MAY be removed from the operations console by an authorized operator)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Protocol v2.20.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v220_records_unpublished_delete_wave_then_g2_and_does_not_implement_product_code() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Where this delta and Protocol v2.19 conflict on which implementation is next, this delta governs" in delta
    assert "MUST a real delete control on the document card / Review chooser for unpublished snapshots only" in delta
    assert "THEN William MAY remove live unpublished Continentie from the console and ingest another HTML freeze" in delta
    assert "THEN William click-through of the running console (not screenshots)" in delta
    assert "THEN Azure ZIP of that `main` from a V&VN-trusted device" in delta
    assert "THEN G2" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "Protocol v2.20.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "v2.14 is not this and is not next" in changelog
    assert "unpublished-delete" in roadmap
    assert "Verwijder unpublished document" in roadmap


def test_v220_does_not_reopen_serving_typeset_stamps_chrome_duty() -> None:
    delta = _read(DELTA)
    assert "Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, or review-duty / queue presentation except as already required" in delta
    assert "The v2.12 closed serving typeset remains UNCHANGED" in delta
    assert "This delta’s bar is every-guideline law plus unpublished-snapshot delete, not a new object type" in delta


def test_v220_beoordeel_timeout_is_out_of_scope() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Beoordeel timeout / performance" in delta
    assert "MUST NOT fold that into this delta" in delta
    assert "Beoordeel-timeout/performance is een apart issue" in root_protocol
    assert "Beoordeel timeout" in changelog


def test_v220_leaves_v216_through_v219_delta_files_untouched() -> None:
    v216 = (ROOT / "docs" / "PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md").read_bytes()
    v217 = (ROOT / "docs" / "PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md").read_bytes()
    v218 = (ROOT / "docs" / "PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md").read_bytes()
    v219 = (ROOT / "docs" / "PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md").read_bytes()
    assert b"**Protocol delta version:** 2.16.0" in v216
    assert b"**Protocol delta version:** 2.17.0" in v217
    assert b"**Protocol delta version:** 2.18.0" in v218
    assert b"**Protocol delta version:** 2.19.0" in v219
    new_law = b"`PROTOCOL.md` is the law of V&VN Data Services for every guideline"
    assert new_law not in v216
    assert new_law not in v217
    assert new_law not in v218
    assert new_law not in v219
    assert new_law in DELTA.read_bytes()
