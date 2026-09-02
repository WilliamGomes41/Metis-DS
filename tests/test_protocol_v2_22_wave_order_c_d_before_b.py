from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_22_WAVE_ORDER_C_D_BEFORE_B_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_22_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v222_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.22.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_22_WAVE_ORDER_C_D_BEFORE_B_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-03"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v222_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.22.0" in delta
    assert "docs/PROTOCOL_V2_22_WAVE_ORDER_C_D_BEFORE_B_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.22.0") == 1
    assert "plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.21.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.20.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.19.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.18.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.17.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.16.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.22.0" in roadmap


def test_v222_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v222_is_bounded_supersession_of_v221_section_3_order_only() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Bounded supersession of Protocol v2.21 §3 order A then B then C then D, for next-implementation order only" in delta
    assert "Waves themselves unchanged" in delta
    assert "Historical v2.21 wave definitions remain law except the A-B-C-D next-impl order superseded here" in delta
    assert "It MAPS, and does NOT rewrite, existing law" in delta
    assert "begrensde supersessie van Protocol v2.21 §3-volgorde A daarna B daarna C daarna D, alleen voor volgende-implementatievolgorde" in root_protocol
    assert "golven zelf ongewijzigd" in root_protocol
    assert "historische v2.21-golfdefinities blijven wet" in root_protocol
    assert "begrensde supersessie van Protocol v2.21 §3-volgorde" in roadmap
    assert "golven zelf ongewijzigd" in roadmap


def test_v222_wave_a_already_on_main_and_v220_not_a_fifth_wave() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Wave A is already in code on `main` `512ffa5026d06ff804434ddf4d07a08a36c02305`" in delta
    assert "v2.20 unpublished-delete remains on main, not a fifth wave" in delta
    assert "MUST NOT rewrite v2.16–v2.21 files except index/conflict pointers" in delta
    assert "golf A staat al in code op `main` `512ffa5026d06ff804434ddf4d07a08a36c02305`" in root_protocol
    assert "v2.20 unpublished-delete blijft op main, GEEN vijfde golf" in root_protocol
    assert "512ffa5026d06ff804434ddf4d07a08a36c02305" in roadmap
    assert "GEEN vijfde golf" in roadmap


def test_v222_new_order_c_then_d_then_zip_then_b() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Wave C: finish PR #82 faults" in delta
    assert "Wave D: `/home/data` inventory, export/restore, proof that `--clean true` wipes wwwroot and MUST NOT delete runtime data" in delta
    assert "THEN one Cloud Shell / production ZIP of that controlled SHA (A+C+D), not a live-URL ingest" in delta
    assert "Ingest of a new freeze MUST be after that ZIP, not before" in delta
    assert "live still runs pre-wave-A extract until ZIP" in delta
    assert "Wave B (G2 evidence/smoke) AFTER that ZIP" in delta
    assert "G2 still BLOCKED" in delta
    assert "`publish()` still G2-BLOCKED" in delta
    assert "ZIP does not open publication" in delta
    assert "volgende implementatie MUST golf C daarna golf D" in root_protocol
    assert "DAARNA één Cloud Shell / production ZIP van die gecontroleerde SHA (A+C+D)" in root_protocol
    assert "geen live-URL-ingest" in root_protocol
    assert "ingest van een nieuwe freeze MUST NA die ZIP, niet ervoor" in root_protocol
    assert "live draait nog pre-golf-A extract tot ZIP" in root_protocol
    assert "golf B (G2-bewijs/smoke) NA die ZIP" in root_protocol
    assert "ZIP opent publicatie niet" in root_protocol
    assert "golf C daarna golf D" in roadmap
    assert "Cloud Shell / production ZIP van die gecontroleerde SHA (A+C+D)" in roadmap
    assert "golf B (G2-bewijs/smoke) NA die ZIP" in roadmap


def test_v222_wave_c_pr82_faults_and_named_test_app() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "packaging via bash or executable" in delta
    assert "ZIP MUST be fully deployable with dependencies" in delta
    assert "git-archive-only is not enough" in delta
    assert "per-env storage via app settings no secrets in Git" in delta or "per-env storage via app settings; no secrets in Git" in delta
    assert "separate test vs production deploy identities" in delta
    assert "MUST NOT activate deploy-test/deploy-production until Azure test App Service `vvn-metis-console-test` exists" in delta
    assert "Merge to `main` MUST NOT auto-deploy to a missing test app" in delta
    assert "MUST NOT start Azure test app in this protocol PR" in delta
    assert "MUST NOT implement C/D in this PR" in delta
    assert "git-archive-only is niet genoeg" in root_protocol
    assert "ZIP MUST volledig deploybaar zijn inclusief dependencies" in root_protocol
    assert "MUST NOT deploy-test/deploy-production activeren tot Azure test-App Service `vvn-metis-console-test` bestaat" in root_protocol
    assert "merge naar `main` MUST NOT automatisch deployen naar een ontbrekende test-app" in root_protocol
    assert "vvn-metis-console-test" in roadmap
    assert "MUST NOT automatisch deployen naar een ontbrekende test-app" in roadmap


def test_v222_wave_d_clean_true_wipes_wwwroot_not_runtime() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Inventory of `/home/data/metis-console`" in delta
    assert "proof that `--clean true` wipes wwwroot and MUST NOT delete runtime data" in delta
    assert "MUST NOT SSH-wipe `/home/data`" in delta
    assert "`--clean true` wist wwwroot en MUST NOT runtime-data verwijderen" in root_protocol
    assert "MUST NOT SSH-wipe van `/home/data`" in root_protocol or "MUST NOT SSH-wipe `/home/data`" in root_protocol
    assert "`--clean true`" in roadmap
    assert "wwwroot" in roadmap


def test_v222_zip_after_c_d_not_live_url_and_does_not_open_g2() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "not a live-URL ingest" in delta
    assert "ZIP does not open publication" in delta
    assert "Do not claim G2 PASS in this protocol" in delta
    assert "MUST NOT claim G2 PASS" in delta
    assert "G2 is still BLOCKED" in delta or "G2 still BLOCKED" in delta
    assert "geen live-URL-ingest" in root_protocol
    assert "ZIP opent publicatie niet" in root_protocol
    assert "claimt geen G2 PASS" in root_protocol
    assert "G2 blijft BLOCKED" in root_protocol
    assert "ZIP opent publicatie niet" in roadmap
    assert "claimt geen G2 PASS" in roadmap


def test_v222_next_implementation_is_wave_c_and_d_then_stop_for_zip() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Where this delta and Protocol v2.21 conflict on which implementation is next, this delta governs" in delta
    assert "The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/repo for wave C (finish PR #82, do not activate) AND wave D (backup/restore + deploy-persistence test)" in delta
    assert "Then stop for William Cloud Shell ZIP of that SHA, then ingest" in delta
    assert "no G2 PASS, no Blob grant" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "golf C (PR #82 afmaken, niet activeren) ÉN golf D" in root_protocol
    assert "daarna stoppen voor William Cloud Shell ZIP van die SHA, daarna ingest" in root_protocol
    assert "geen G2 PASS, geen Blob-grant" in root_protocol
    assert "golf C (PR #82 afmaken, niet activeren) ÉN golf D" in roadmap
    assert "stoppen voor William Cloud Shell ZIP" in roadmap
    assert "Protocol v2.22.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "v2.14 is not this and is not next" in changelog
    assert "Next implementation is wave C and wave D" in changelog


def test_v222_keeps_continentie_evidence_and_every_guideline_law() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`PROTOCOL.md` is every-guideline law, not Continentie-only (Protocol v2.20)" in delta
    assert "Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain" in delta
    assert "stamp words as Koppen; 2008 Inhoud cards" in delta
    assert "Those sentences are live evidence of fails, not the product identity" in delta
    assert "PROTOCOL.md is wet voor iedere richtlijn, niet Continentie-only" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in root_protocol
    assert "Inhoud (2008) / Koppen 78 op Continentie" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in roadmap


def test_v222_g2_readiness_and_pr82_stay_blocked() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "G2-readiness (PR #69) already pinned `azure-identity==1.25.3` / `azure-storage-blob==12.30.1`" in delta
    assert "PR #82 (`ci: isolated test deploy + manual production`) is OPEN and MUST NOT be activated until the four faults are fixed AND Azure test App Service `vvn-metis-console-test` exists" in delta
    assert "G2-readiness (PR #69)" in root_protocol
    assert "PR #82 is OPEN en MUST NOT worden geactiveerd" in root_protocol
    assert "PR #82 is OPEN" in roadmap


def test_v222_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (next-implementation order after wave A; isolated test/release; recoverability; ZIP does not open publication)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.22.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v222_leaves_v216_through_v221_delta_files_untouched() -> None:
    v216 = (ROOT / "docs" / "PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md").read_bytes()
    v217 = (ROOT / "docs" / "PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md").read_bytes()
    v218 = (ROOT / "docs" / "PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md").read_bytes()
    v219 = (ROOT / "docs" / "PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md").read_bytes()
    v220 = (ROOT / "docs" / "PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md").read_bytes()
    v221 = (ROOT / "docs" / "PROTOCOL_V2_21_CONTROLLED_USE_WAVES_DELTA.md").read_bytes()
    assert b"**Protocol delta version:** 2.16.0" in v216
    assert b"**Protocol delta version:** 2.17.0" in v217
    assert b"**Protocol delta version:** 2.18.0" in v218
    assert b"**Protocol delta version:** 2.19.0" in v219
    assert b"**Protocol delta version:** 2.20.0" in v220
    assert b"**Protocol delta version:** 2.21.0" in v221
    new_law = b"Bounded supersession of Protocol v2.21 §3 order A then B then C then D, for next-implementation order only"
    assert new_law not in v216
    assert new_law not in v217
    assert new_law not in v218
    assert new_law not in v219
    assert new_law not in v220
    assert new_law not in v221
    assert new_law in DELTA.read_bytes()


def test_v222_does_not_reopen_serving_typeset_stamps_chrome_duty() -> None:
    delta = _read(DELTA)
    assert "Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete, or wave A/B/C/D definitions except as already required" in delta
    assert "The v2.12 closed serving typeset remains UNCHANGED" in delta
    assert "This delta’s bar is the next-implementation order after wave A" in delta


def test_v222_out_of_scope_matches_owner_lock() -> None:
    delta = _read(DELTA)
    assert "implementing console/extract/Azure" in delta
    assert "implementing C/D" in delta
    assert "merging" in delta
    assert "G2 PASS" in delta
    assert "Protocol v2.14" in delta
    assert "LLM" in delta
    assert "nurse UI" in delta
    assert "SSH wipe" in delta
    assert "hiding fragments without extract" in delta
    assert "treating Metis / Implementation engineer / Auditor as GD-03 reviewers" in delta
    assert "starting Azure test app in this protocol PR" in delta
    assert "taking a Cloud Shell ZIP before C and D are on the controlled SHA" in delta
    assert "live-URL ingest" in delta
    assert "ingest of a new freeze before that ZIP" in delta
