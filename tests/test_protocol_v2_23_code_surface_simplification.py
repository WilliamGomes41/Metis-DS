from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_23_CODE_SURFACE_SIMPLIFICATION_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_23_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v223_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.23.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_23_CODE_SURFACE_SIMPLIFICATION_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-03"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v223_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.23.0" in delta
    assert "docs/PROTOCOL_V2_23_CODE_SURFACE_SIMPLIFICATION_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.23.0") == 1
    assert "plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
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
    assert "Protocol v2.23.0" in roadmap


def test_v223_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v223_first_delete_cut_then_one_zip_of_that_sha() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "first DELETE cut, then one ZIP of that SHA" in delta
    assert "MUST NOT ZIP `a566af56` if that forces a second ZIP after cleanup" in delta
    assert "Two Cloud Shell ZIPs is refused" in delta
    assert "happens on main BEFORE any Cloud Shell ZIP" in delta
    assert "Then ONE Cloud Shell ZIP of that resulting SHA" in delta
    assert "A+C+D already on main, plus v2.20 delete control, plus the first DELETE cut" in delta
    assert "Wave B still after that one ZIP + ingest" in delta or "Wave B (G2 evidence/smoke) AFTER that one ZIP + ingest" in delta
    assert "This protocol PR is not that ZIP" in delta
    assert "MUST NOT treat this protocol PR as Azure ZIP" in delta
    assert "PR #82 stays closed/unmerged" in delta
    assert "eerste DELETE-snede, daarna één ZIP van die SHA" in root_protocol
    assert "MUST NOT a566af56 ZIP-pen als dat een tweede ZIP forceert" in root_protocol
    assert "Twee Cloud Shell ZIPs zijn geweigerd" in root_protocol
    assert "PR #82 blijft gesloten/ongemerged" in root_protocol
    assert "a566af56c8c88e76cb4de7fa51642b408705da02" in roadmap
    assert "eerste DELETE-snede, daarna één ZIP van die SHA" in roadmap
    assert "MUST NOT a566af56 ZIP-pen als dat een tweede ZIP forceert" in roadmap
    assert "Twee Cloud Shell ZIPs zijn geweigerd" in roadmap
    assert "first DELETE cut, then one ZIP of that SHA" in changelog
    assert "MUST NOT ZIP a566af56 if that forces a second ZIP" in changelog
    assert "Two Cloud Shell ZIPs is refused" in changelog


def test_v223_auditor_verdict_is_request_simplification_not_gd03() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Auditor verdict: **REQUEST SIMPLIFICATION**" in delta
    assert "This is not GD-03" in delta
    assert "This is not publication" in delta
    assert "G2 remains BLOCKED" in delta or "G2 is still BLOCKED" in delta
    assert "Auditor-oordeel REQUEST SIMPLIFICATION" in root_protocol
    assert "geen GD-03, geen publicatie" in root_protocol
    assert "G2 blijft BLOCKED" in root_protocol
    assert "REQUEST SIMPLIFICATION" in roadmap
    assert "geen GD-03" in roadmap


def test_v223_first_delete_cut_is_zero_caller_src_modules_only() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "first DELETE cut, zero-caller src/ modules only" in delta
    for name in (
        "extract_pdf.py",
        "semantic_transform.py",
        "validation_workflow.py",
        "build_second_review_queue.py",
        "pre_step5_gate.py",
        "import_expert_validation.py",
        "reconcile_legacy_review.py",
        "evaluate_safe_retrieval.py",
        "build_retrieval_document.py",
    ):
        assert name in delta
        assert name in root_protocol
        assert name in roadmap
    assert "eerste DELETE-snede, zero-caller src/-modules only" in root_protocol
    assert "first DELETE cut" in changelog


def test_v223_does_not_delete_v20_lock_canonical_store_or_two_products() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "still subprocess-locked by `tests/test_protocol_v2.py`" in delta
    assert "src/semantic_transform_v2.py" in delta
    assert "src/prepublication_gate_v2.py" in delta
    assert "src/validation_workflow_v2.py" in delta
    assert "src/apply_second_review.py" in delta
    assert "Do NOT delete `src/canonical_store.py`" in delta
    assert "`service_app.py` AND `product_api_v1.py` are two products" in delta
    assert "two products, not leftovers" in delta
    assert "MUST NOT `src/semantic_transform_v2.py` verwijderen" in root_protocol
    assert "MUST NOT `src/canonical_store.py` verwijderen" in root_protocol
    assert "service_app.py EN product_api_v1.py blijven" in root_protocol
    assert "twee producten, geen leftovers" in root_protocol
    assert "canonical_store.py" in roadmap
    assert "service_app.py" in roadmap
    assert "product_api_v1.py" in roadmap


def test_v223_keeps_console_split_wave_a_and_both_test_families() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`operations_console_v1.py` versus `operations_console_app.py` split remains" in delta
    assert "no template engine" in delta
    assert "Wave A splitter + `reject_candidate` remain" in delta
    assert "`test_protocol_v2_*` and `test_v2*` both kept" in delta
    assert "New eligibility rules go only in `eligibility_policy`" in delta
    assert "MUST NOT split high-CC fail-closed functions" in delta
    assert "live ingest uses `extract_pdf_v2`, `extract_html_v1`, `semantic_transform_generic_v1`, `prepublication_gate_v3`" in delta
    assert "operations_console_v1.py versus operations_console_app.py split blijft" in root_protocol
    assert "geen template-engine" in root_protocol
    assert "golf A splitter + reject_candidate blijven" in root_protocol
    assert "test_protocol_v2_* en test_v2* blijven beide" in root_protocol
    assert "eligibility_policy" in roadmap
    assert "reject_candidate" in roadmap


def test_v223_integrity_sprint_and_dual_review_queue_are_planned_not_silent_delete() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "point `scripts/run_integrity_sprint.sh` at committed fixtures instead of `python -m src.semantic_transform_v21`" in delta
    assert "Do not merge v2/v21/generic in that PR" in delta
    assert "CLI `review-queue` (`build_review_queue_v3`) versus console `review_stacks` / `slow_review_duty`" in delta
    assert "Console is the researcher duty queue" in delta
    assert "plan, do not silent-delete" in delta
    assert "scripts/run_integrity_sprint.sh MAG in dezelfde of de volgende wijziging naar committed fixtures wijzen" in root_protocol
    assert "MUST NOT v2/v21/generic mergen in die PR" in root_protocol
    assert "CLI review-queue versus console review_stacks / slow_review_duty is dual live path" in root_protocol
    assert "Console is de onderzoeker-plichtwachtrij" in root_protocol
    assert "plan, MUST NOT stilzwijgend verwijderen" in root_protocol
    assert "run_integrity_sprint.sh" in roadmap
    assert "review-queue" in roadmap


def test_v223_next_implementation_is_one_deletion_pr_before_one_zip() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "The next **code** implementation MUST be one deletion PR on the existing kernel/repo (first DELETE cut plus integrity-sprint fixture retarget)" in delta
    assert "on main BEFORE any Cloud Shell ZIP" in delta
    assert "existing pytest only" in delta
    assert "MUST NOT touch the splitter or console in that PR" in delta
    assert "Implementation MUST re-prove no live callers before each delete" in delta
    assert "If a named file still has a live caller, leave it and report" in delta
    assert "MUST NOT implement the deletion PR in this PR" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "volgende implementatie VÓÓR die ZIP is één deletion-PR" in root_protocol
    assert "bestaande pytest only" in root_protocol
    assert "MUST NOT splitter of console in die PR raken" in root_protocol
    assert "Implementation MUST opnieuw bewijzen dat er geen live callers zijn vóór iedere delete" in root_protocol
    assert "één deletion-PR" in roadmap
    assert "volgende implementatie VÓÓR die ZIP is één deletion-PR" in roadmap
    assert "Protocol v2.23.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "v2.14 is not this and is not next" in changelog
    assert "Next implementation is one deletion PR on main BEFORE any Cloud Shell ZIP" in changelog


def test_v223_handoff_must_not_be_recreated() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`HANDOFF.md` MUST NOT be recreated" in delta
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in root_protocol
    assert "HANDOFF.md" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()


def test_v223_keeps_continentie_evidence_and_every_guideline_law() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`PROTOCOL.md` is every-guideline law, not Continentie-only (Protocol v2.20)" in delta
    assert "Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain" in delta
    assert "PROTOCOL.md is wet voor iedere richtlijn, niet Continentie-only" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in roadmap


def test_v223_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (Auditor REQUEST SIMPLIFICATION after A+C+D on main; first DELETE cut, then one ZIP of that SHA; MUST NOT ZIP a566af56 if that forces a second ZIP)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.23.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v223_leaves_v216_through_v222_delta_files_untouched() -> None:
    v216 = (ROOT / "docs" / "PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md").read_bytes()
    v217 = (ROOT / "docs" / "PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md").read_bytes()
    v218 = (ROOT / "docs" / "PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md").read_bytes()
    v219 = (ROOT / "docs" / "PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md").read_bytes()
    v220 = (ROOT / "docs" / "PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md").read_bytes()
    v221 = (ROOT / "docs" / "PROTOCOL_V2_21_CONTROLLED_USE_WAVES_DELTA.md").read_bytes()
    v222 = (ROOT / "docs" / "PROTOCOL_V2_22_WAVE_ORDER_C_D_BEFORE_B_DELTA.md").read_bytes()
    assert b"**Protocol delta version:** 2.16.0" in v216
    assert b"**Protocol delta version:** 2.17.0" in v217
    assert b"**Protocol delta version:** 2.18.0" in v218
    assert b"**Protocol delta version:** 2.19.0" in v219
    assert b"**Protocol delta version:** 2.20.0" in v220
    assert b"**Protocol delta version:** 2.21.0" in v221
    assert b"**Protocol delta version:** 2.22.0" in v222
    new_law = b"first DELETE cut, zero-caller src/ modules only"
    live_path = b"first DELETE cut, then one ZIP of that SHA"
    for old in (v216, v217, v218, v219, v220, v221, v222):
        assert new_law not in old
        assert live_path not in old
    assert new_law in DELTA.read_bytes()
    assert live_path in DELTA.read_bytes()


def test_v223_does_not_reopen_serving_typeset_stamps_chrome_duty() -> None:
    delta = _read(DELTA)
    assert "Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete, or wave A/B/C/D definitions except as already required" in delta
    assert "The v2.12 closed serving typeset remains UNCHANGED" in delta
    assert "This delta’s bar is the first DELETE cut, then one ZIP of that SHA" in delta


def test_v223_out_of_scope_matches_owner_lock() -> None:
    delta = _read(DELTA)
    assert "implementing console/extract/Azure" in delta
    assert "implementing the deletion PR" in delta
    assert "merging product code" in delta
    assert "G2 PASS" in delta
    assert "Protocol v2.14" in delta
    assert "LLM" in delta
    assert "nurse UI" in delta
    assert "SSH wipe" in delta
    assert "hiding fragments without extract" in delta
    assert "treating Metis / Implementation engineer / Auditor as GD-03 reviewers" in delta
    assert "taking this protocol PR as the Cloud Shell ZIP" in delta
    assert "live-URL ingest" in delta
    assert "merging PR #82" in delta
    assert "recreating `HANDOFF.md`" in delta
