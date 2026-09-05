from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_27_UNPUBLISHED_DELETE_DOCUMENTENHIERARCHIE_TYPE_CONFIRM_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_27_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v227_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.27.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_27_UNPUBLISHED_DELETE_DOCUMENTENHIERARCHIE_TYPE_CONFIRM_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-05"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v227_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.27.0" in delta
    assert "docs/PROTOCOL_V2_27_UNPUBLISHED_DELETE_DOCUMENTENHIERARCHIE_TYPE_CONFIRM_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.27.0") == 1
    assert "plus Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.26.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.25.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.24.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.23.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.22.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.21.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.20.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.19.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.18.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.17.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.16.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.27.0" in roadmap


def test_v227_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v227_single_place_is_documentenhierarchie() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Unpublished document delete MUST be available from **exactly one** console place: **Documentenhiërarchie**" in delta
    assert "MUST NOT offer Verwijder unpublished document (or equivalent delete control) from Inleveren, Review, Publiceren, Accounts, or any other room" in delta
    assert "MUST NOT invent a separate Delete room/kamer" in delta
    assert "Documentenhiërarchie" in root_protocol
    assert "Inleveren" in root_protocol and "Publiceren" in root_protocol and "Accounts" in root_protocol
    assert "Documentenhiërarchie" in roadmap
    assert "Documentenhiërarchie" in changelog
    assert "Inleveren" in changelog and "Review" in changelog and "Publiceren" in changelog and "Accounts" in changelog


def test_v227_type_to_confirm_exact_title() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "the operator MUST type the **exact document title** into a confirmation field (type-to-confirm)" in delta
    assert "The console MUST show the title clearly so the operator can copy/read it" in delta
    assert "safety measure against accidental/fast delete, not a puzzle" in delta
    assert "Without an exact title match, delete MUST NOT run" in delta
    assert "type-to-confirm" in delta
    assert "type-to-confirm" in root_protocol
    assert "exacte documenttitel" in root_protocol or "exacte titel" in root_protocol
    assert "type-to-confirm" in roadmap
    assert "type-to-confirm" in changelog
    assert "exact" in changelog.lower()


def test_v227_supersedes_v220_document_card_review_chooser_surfaces() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "SUPERSEDES any reading of Protocol v2.20 that delete MUST appear on the document card / Review-chooser as alternative surfaces" in delta
    assert "Replace with: Documentenhiërarchie only + type-to-confirm exact title" in delta or "Documentenhiërarchie only + type-to-confirm" in delta
    assert "documentkaart / Review-chooser" in root_protocol
    assert "SUPERSEDEERT" in root_protocol
    assert "documentkaart / Review-chooser" in roadmap
    assert "SUPERSEDEERT" in roadmap or "supersedes" in changelog.lower()
    assert "Review-chooser" in changelog or "Review chooser" in changelog


def test_v227_keeps_v220_unpublished_only_audit_no_published_no_ssh() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Only unpublished captured snapshots MAY be deleted by an authorized console operator" in delta
    assert "MUST write an audit-ledger row" in delta or "MUST write an audit-ledger row:" in delta
    assert "MUST NOT delete a published projection" in delta
    assert "MUST NOT treat SSH/wipe of `/home/data` as the product path" in delta
    assert "Four-eyes NOT required for unpublished capture delete" in delta or "Four-eyes is NOT required for unpublished capture delete" in delta
    assert "unpublished captured snapshots MAGEN van de operations console worden verwijderd" in root_protocol
    assert "audit-ledgerrij" in root_protocol
    assert "MUST NOT een gepubliceerde projectie" in root_protocol
    assert "MUST NOT SSH/wipe van `/home/data` als productpad" in root_protocol
    assert "four-eyes is niet vereist" in roadmap


def test_v227_protocol_is_every_guideline_law_not_continentie_only() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`PROTOCOL.md` is the law of V&VN Data Services for every guideline, not a Continentie-only protocol" in delta
    assert "Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain" in delta
    assert "PROTOCOL.md is wet voor iedere richtlijn, niet Continentie-only" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in roadmap


def test_v227_first_code_wave_is_forge_delete_surface_not_this_pr() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Remove delete controls from every surface except Documentenhiërarchie" in delta
    assert "Add type-to-confirm field requiring exact document title (title shown)" in delta
    assert "Keep existing unpublished-only / audit-ledger / no published delete / confirmation" in delta
    assert "Tests (tests-before-code)" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "MUST NOT implement selective invalidation, published-candidate fork, full `previous_review` schema, or further Klasse wijzigen work in that first code wave" in delta
    assert "Forge" in root_protocol
    assert "Documentenhiërarchie" in root_protocol
    assert "type-to-confirm" in root_protocol
    assert "Forge" in roadmap
    assert "type-to-confirm" in roadmap
    assert "Protocol v2.27.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "Forge" in changelog


def test_v227_g2_stays_blocked_publish_stays_blocked() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "G2 remains BLOCKED" in delta or "G2 stays BLOCKED" in delta
    assert "`publish()` stays G2-BLOCKED" in delta or "`publish()` remains G2-BLOCKED" in delta
    assert "This protocol does not claim G2 PASS" in delta
    assert "MUST NOT claim GD-03 or publication" in delta or "Do not claim GD-03" in delta
    assert "G2 blijft BLOCKED" in root_protocol
    assert "publish()" in root_protocol
    assert "G2 blijft BLOCKED" in roadmap
    assert "G2 remains BLOCKED" in changelog or "G2 blijft BLOCKED" in changelog


def test_v227_handoff_must_not_be_recreated() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`HANDOFF.md` MUST NOT be recreated" in delta
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in root_protocol
    assert "HANDOFF.md" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()


def test_v227_keeps_v226_klasse_wijzigen_and_v225_boom_path() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "v2.26 Klasse wijzigen first wave is already on `main` (PR #97)" in delta or "That wave is already on `main` (PR #97)" in delta
    assert "v2.25 boom path UNCHANGED" in delta or "v2.25 boom path remains UNCHANGED" in delta
    assert "Klasse wijzigen" in root_protocol
    assert "Klasse includes beslisboom; Klasse choice selects review path" in root_protocol
    assert "Klasse includes beslisboom; Klasse choice selects review path" in roadmap
    assert "selectieve invalidatie + published-candidate" in roadmap


def test_v227_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (unpublished document delete MUST be available from exactly one console place: Documentenhiërarchie; type-to-confirm exact document title; SUPERSEDES v2.20 document-card / Review-chooser alternative surfaces; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.27.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v227_leaves_v216_through_v225_untouched_except_v220_and_v226_pointers() -> None:
    v216 = (ROOT / "docs" / "PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md").read_bytes()
    v217 = (ROOT / "docs" / "PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md").read_bytes()
    v218 = (ROOT / "docs" / "PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md").read_bytes()
    v219 = (ROOT / "docs" / "PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md").read_bytes()
    v220 = (ROOT / "docs" / "PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md").read_bytes()
    v221 = (ROOT / "docs" / "PROTOCOL_V2_21_CONTROLLED_USE_WAVES_DELTA.md").read_bytes()
    v222 = (ROOT / "docs" / "PROTOCOL_V2_22_WAVE_ORDER_C_D_BEFORE_B_DELTA.md").read_bytes()
    v223 = (ROOT / "docs" / "PROTOCOL_V2_23_CODE_SURFACE_SIMPLIFICATION_DELTA.md").read_bytes()
    v224 = (ROOT / "docs" / "PROTOCOL_V2_24_CONSOLE_RETRIEVAL_DEPLOY_SPLIT_DELTA.md").read_bytes()
    v225 = (ROOT / "docs" / "PROTOCOL_V2_25_BESLISBOOM_CLASS_PATH_NODE_OUTCOME_DELTA.md").read_bytes()
    v226 = (ROOT / "docs" / "PROTOCOL_V2_26_KLASSE_WIJZIGEN_CONTROLLED_RECLASSIFICATION_DELTA.md").read_bytes()
    assert b"**Protocol delta version:** 2.16.0" in v216
    assert b"**Protocol delta version:** 2.17.0" in v217
    assert b"**Protocol delta version:** 2.18.0" in v218
    assert b"**Protocol delta version:** 2.19.0" in v219
    assert b"**Protocol delta version:** 2.20.0" in v220
    assert b"**Protocol delta version:** 2.21.0" in v221
    assert b"**Protocol delta version:** 2.22.0" in v222
    assert b"**Protocol delta version:** 2.23.0" in v223
    assert b"**Protocol delta version:** 2.24.0" in v224
    assert b"**Protocol delta version:** 2.25.0" in v225
    assert b"**Protocol delta version:** 2.26.0" in v226
    new_law = b"type-to-confirm"
    for old in (v216, v217, v218, v219, v221, v222, v223, v224, v225):
        assert new_law not in old
        assert b"exactly one console place" not in old
    assert b"Index/conflict pointer: Protocol v2.27.0" in v220
    assert b"Index/conflict pointer: Protocol v2.27.0" in v226
    assert new_law in DELTA.read_bytes()


def test_v227_does_not_reopen_serving_typeset_stamps_waves_g2_or_v226_klasse() -> None:
    delta = _read(DELTA)
    assert "Do not reopen freeze/locator (v2.11), richtlijn-path serving types (v2.12), atomic objects/relations/four-eyes (v2.13), stamps on recommendation (v2.16), researcher surface (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished-delete except the surface / type-to-confirm lock here (v2.20), waves A–D / deploy split (v2.21–v2.24), the v2.25 boom path, the v2.26 Klasse wijzigen architecture, or fail-closed G2 except as already required" in delta
    assert "The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED" in delta
    assert "The v2.25 closed boom-path typeset remains UNCHANGED" in delta


def test_v227_out_of_scope_matches_owner_lock() -> None:
    delta = _read(DELTA)
    assert "implementing Documentenhiërarchie-only delete, type-to-confirm, or removal of existing delete controls" in delta
    assert "G2 PASS" in delta
    assert "Protocol v2.14" in delta
    assert "LLM" in delta
    assert "nurse UI" in delta
    assert "recreating `HANDOFF.md`" in delta
    assert "adding numpy/sklearn" in delta
    assert "touching Azure deploy packaging" in delta
    assert "inventing a separate Delete room/kamer" in delta
    assert "selective class-change work" in delta


def test_v227_no_product_feature_code_in_this_pr() -> None:
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PROTOCOL_V2_27" in text or "documentenhierarchie_type_confirm" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"protocol-only PR must not add unpublished-delete surface product code in src/: {src_hits}"
