from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_31_DIT_KLOPT_EXACT_HEADING_BIND_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_31_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v231_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.31.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_31_DIT_KLOPT_EXACT_HEADING_BIND_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-06"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v231_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.31.0" in delta
    assert "docs/PROTOCOL_V2_31_DIT_KLOPT_EXACT_HEADING_BIND_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.31.0") == 1
    assert "plus Protocol v2.30.0 plus Protocol v2.29.0 plus Protocol v2.28.0 plus Protocol v2.27.0 plus Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.30.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.29.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.28.0" not in root_protocol
    assert "Protocol v2.31.0" in roadmap


def test_v231_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v231_exact_bind_norms() -> None:
    delta = _read(DELTA)
    assert "exact" in delta.lower()
    assert "visible heading title match after normalization" in delta
    assert "trim; collapse internal whitespace" in delta
    assert "MUST NOT use substring/`in` matching" in delta
    assert "MUST NOT use partial / substring / containment matches" in delta
    assert "`last in text`" in delta
    assert "`text in last`" in delta
    assert "startswith-as-bind" in delta
    assert "MUST NOT first-hit win among substring candidates" in delta
    assert "MUST NOT silently bind a parent" in delta
    assert "Andere kop kiezen" in delta
    assert "MUST NOT invent a parent" in delta
    assert "MUST NOT guess" in delta
    assert "SUPERSEDES any reading that Dit klopt MAY bind via partial title containment" in delta


def test_v231_preventie_and_screening_regressions() -> None:
    delta = _read(DELTA)
    changelog = _read(ROOT / "CHANGELOG.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "Preventie van vallen" in delta
    assert "MUST NOT bind the prefix when the exact longer title exists" in delta
    assert "MUST NOT bind the longer title when the path’s last segment exacts only the short title" in delta
    assert "Screening en diagnostiek" in delta
    assert "substring MUST NOT decide" in delta
    assert "Preventie van vallen" in root_protocol
    assert "Preventie van vallen" in roadmap
    assert "Preventie van vallen" in changelog
    assert "Screening en diagnostiek" in changelog or "Screening" in changelog


def test_v231_keeps_v228_v230_phase14_unchanged() -> None:
    delta = _read(DELTA)
    assert "v2.28 structural validity / body-only chooser / TOC exclusion UNCHANGED" in delta
    assert "v2.30 Block B ordinary language" in delta
    assert "Gevonden onder" in delta
    assert "Dit klopt" in delta
    assert "Andere kop" in delta
    assert "Phase 1–4 admission/register UNCHANGED" in delta


def test_v231_next_code_is_forge_exact_bind_not_this_pr() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "resolve_found_under_parent" in delta
    assert "tests-before-code" in delta
    assert "MUST NOT implement Forge code in this PR" in delta or "MUST NOT implement that Forge code in this protocol PR" in delta
    assert "resolve_found_under_parent" in roadmap
    assert "tests-before-code" in roadmap
    assert "Protocol v2.31.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "resolve_found_under_parent" in changelog


def test_v231_g2_stays_blocked_publish_stays_blocked() -> None:
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


def test_v231_handoff_must_not_be_recreated() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`HANDOFF.md` MUST NOT be recreated" in delta
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in root_protocol
    assert "HANDOFF.md" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()


def test_v231_is_c3_documentpositie_bind_safety_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 review-surface / documentpositie bind safety" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.31.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / documentpositie bind safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v231_leaves_prior_deltas_untouched_except_index_conflict_pointers() -> None:
    v230 = (ROOT / "docs" / "PROTOCOL_V2_30_OBJECT_CONTRACT_HARD_ADMISSION_GATE_AND_REVIEWER_PASSAGE_FLOW_DELTA.md").read_bytes()
    v228 = (ROOT / "docs" / "PROTOCOL_V2_28_STRUCTURAL_HEADING_NAV_AND_CONFIRMED_STRENGTH_GATE_DELTA.md").read_bytes()
    v229 = (ROOT / "docs" / "PROTOCOL_V2_29_TEMPORARY_PRODUCTION_ONLY_DEPLOY_DELTA.md").read_bytes()
    assert b"**Protocol delta version:** 2.30.0" in v230
    assert b"**Protocol delta version:** 2.28.0" in v228
    assert b"tijdelijke productie-only deployment" in v229
    assert b"Index/conflict pointer: Protocol v2.31.0" in v230
    assert b"Dit klopt MAY bind via partial title containment" in v230
    assert b"Index/conflict pointer: Protocol v2.30.0" in v228


def test_v231_no_product_feature_code_in_this_pr() -> None:
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PROTOCOL_V2_31" in text or "exact_heading_bind" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"protocol-only PR must not add exact-bind product code in src/: {src_hits}"
