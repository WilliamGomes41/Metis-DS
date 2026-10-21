from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_32_DOCUMENTEN_UI_ROOM_NAME_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_32_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v232_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.32.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_32_DOCUMENTEN_UI_ROOM_NAME_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-06"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"
    assert manifest["repository"] == "WilliamGomes41/VENVN-DS"


def test_v232_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.32.0" in delta
    assert "docs/PROTOCOL_V2_32_DOCUMENTEN_UI_ROOM_NAME_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.32.0") == 1
    assert "plus Protocol v2.31.0 plus Protocol v2.30.0 plus Protocol v2.29.0 plus Protocol v2.28.0 plus Protocol v2.27.0 plus Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.31.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.30.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.29.0" not in root_protocol
    assert "Protocol v2.32.0" in roadmap


def test_v232_does_not_redesign_the_four_layers_or_write_v214() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "This delta MUST NOT invent a fifth layer" in delta
    assert "MUST NOT collapse those four" in delta
    assert "frozen source → source passage → knowledge object → human review → published projection" in delta
    assert "A knowledge object MUST NOT replace the brondocument" in delta
    assert "This file is not Protocol v2.14" in delta
    assert "This delta MUST NOT write Protocol v2.14" in delta
    assert "vier lagen" in root_protocol
    assert "Protocol v2.14 wordt in deze delta niet geschreven" in root_protocol
    assert "LOCKED als het volgende protocol (v2.14), niet deze PR" in roadmap
    assert "MUST NOT Protocol v2.14 worden geschreven" in roadmap


def test_v232_documenten_ui_room_name_norms() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "MUST be **Documenten**" in delta
    assert "ordinary Dutch, singular room name" in delta
    assert "MUST NOT use **Documentenhiërarchie**, **Documentenhierarchie**, or **Familieboom**" in delta
    assert "The kernel model remains family × class" in delta
    assert "This is UI vocabulary only" in delta
    assert "same pattern as Protocol v2.26 renaming Promoveren → Klasse wijzigen" in delta
    assert "**Documenten**" in root_protocol
    assert "MUST **Documenten** zijn" in root_protocol
    assert "**Documenten**" in roadmap
    assert "MUST **Documenten** zijn" in roadmap
    assert "Protocol v2.32.0" in changelog
    assert "**Documenten**" in changelog


def test_v232_supersedes_only_the_ui_name_not_delete_surface() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "SUPERSEDES only the UI name in Protocol v2.10" in delta or "SUPERSEDES only the UI name in v2.10" in delta
    assert "do NOT reopen delete surface to Review/Inleveren" in delta
    assert "Protocol v2.27 unpublished-delete remains ONE place only" in delta
    assert "type-to-confirm exact title" in delta
    assert "MUST NOT reopen delete surface to Review/Inleveren" in delta or "MUST NOT reopen delete to Review/Inleveren" in delta
    assert "MUST NOT delete heropenen naar Review/Inleveren" in root_protocol
    assert "MUST NOT delete heropenen naar Review/Inleveren" in roadmap
    assert "type-to-confirm" in root_protocol
    assert "type-to-confirm" in roadmap


def test_v232_historical_delta_filenames_may_keep_path() -> None:
    delta = _read(DELTA)
    assert "Historical delta filenames" in delta
    assert "PROTOCOL_V2_27_UNPUBLISHED_DELETE_DOCUMENTENHIERARCHIE_TYPE_CONFIRM_DELTA.md" in delta
    assert (ROOT / "docs" / "PROTOCOL_V2_27_UNPUBLISHED_DELETE_DOCUMENTENHIERARCHIE_TYPE_CONFIRM_DELTA.md").is_file()


def test_v232_landing_sketch_b_is_out_of_this_pr() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Landing-page sketch B" in delta
    assert "centered sparse home" in delta
    assert "Bron inleveren" in delta
    assert "OUT of this protocol PR" in delta
    assert "separate Metis GO" in delta
    assert "MUST NOT implement the console rename or landing-page sketch B in this PR" in delta or "MUST NOT implement landing-page sketch B in this PR" in delta
    assert "landing sketch B" in roadmap.lower() or "Landing-page sketch B" in roadmap
    assert "Bron inleveren" in roadmap
    assert "aparte Metis GO" in roadmap
    assert "Landing-page sketch B" in changelog
    assert "does not implement console, extract or Azure" in changelog


def test_v232_g2_stays_blocked_publish_stays_blocked() -> None:
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


def test_v232_handoff_must_not_be_recreated() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`HANDOFF.md` MUST NOT be recreated" in delta
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in root_protocol
    assert "HANDOFF.md" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()


def test_v232_is_c3_ui_vocabulary_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 review-surface / UI vocabulary" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.32.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / UI vocabulary" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v232_leaves_prior_deltas_untouched_except_index_conflict_pointers() -> None:
    v231 = (ROOT / "docs" / "PROTOCOL_V2_31_DIT_KLOPT_EXACT_HEADING_BIND_DELTA.md").read_bytes()
    v230 = (ROOT / "docs" / "PROTOCOL_V2_30_OBJECT_CONTRACT_HARD_ADMISSION_GATE_AND_REVIEWER_PASSAGE_FLOW_DELTA.md").read_bytes()
    v227 = (ROOT / "docs" / "PROTOCOL_V2_27_UNPUBLISHED_DELETE_DOCUMENTENHIERARCHIE_TYPE_CONFIRM_DELTA.md").read_bytes()
    assert b"**Protocol delta version:** 2.31.0" in v231
    assert b"**Protocol delta version:** 2.30.0" in v230
    assert b"**Protocol delta version:** 2.27.0" in v227
    assert b"Index/conflict pointer: Protocol v2.32.0" in v231
    assert b"heading MUST be Documentenhierarchie" in v231
    assert b"Index/conflict pointer: Protocol v2.31.0" in v230


def test_v232_no_product_feature_code_in_this_pr() -> None:
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PROTOCOL_V2_32" in text or "documenten_ui_room_name" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"protocol-only PR must not add Documenten rename product code in src/: {src_hits}"
