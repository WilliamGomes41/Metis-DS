from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_28_STRUCTURAL_HEADING_NAV_AND_CONFIRMED_STRENGTH_GATE_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_28_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _block_a_text() -> str:
    """Independently readable Block A surface (delta + wired docs)."""
    return "\n".join(
        (
            _read(DELTA),
            _read(ROOT / "PROTOCOL.md"),
            _read(ROOT / "ROADMAP.md"),
            _read(ROOT / "CHANGELOG.md"),
        )
    )


def _block_b_text() -> str:
    """Independently readable Block B surface (delta + wired docs)."""
    return "\n".join(
        (
            _read(DELTA),
            _read(ROOT / "PROTOCOL.md"),
            _read(ROOT / "ROADMAP.md"),
            _read(ROOT / "CHANGELOG.md"),
        )
    )


def test_v228_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.28.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_28_STRUCTURAL_HEADING_NAV_AND_CONFIRMED_STRENGTH_GATE_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-05"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v228_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.28.0" in delta
    assert "docs/PROTOCOL_V2_28_STRUCTURAL_HEADING_NAV_AND_CONFIRMED_STRENGTH_GATE_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.30.0") == 1
    assert "plus Protocol v2.27.0 plus Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.27.0" not in root_protocol
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
    assert "Protocol v2.28.0" in roadmap


def test_v228_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v228_two_acceptance_blocks_are_independently_named() -> None:
    delta = _read(DELTA)
    assert "two separate acceptance blocks" in delta
    assert "The two blocks MUST be independently testable" in delta
    assert "A pass of Block A MUST NOT be treated as a pass of Block B" in delta
    assert "A pass of Block B MUST NOT be treated as a pass of Block A" in delta
    assert "### Block A — Structural heading / parent-list navigation" in delta
    assert "### Block B — Strength stamp gating (confirmed type only)" in delta
    assert "separate acceptance tests" in delta


# ---------------------------------------------------------------------------
# Block A — Structural heading / parent-list navigation (independently testable)
# ---------------------------------------------------------------------------


def test_v228_block_a_forbids_naive_global_numeric_sort() -> None:
    text = _block_a_text()
    assert "MUST NOT use naive global numeric sort of all headings" in text
    assert "TOC + body merge risk" in text
    assert "inhoudsopgave" in text
    assert "naive global numeric sort" in _read(ROOT / "CHANGELOG.md")


def test_v228_block_a_marks_toc_separately_and_uses_body_headings() -> None:
    text = _block_a_text()
    assert "Recognize and mark table-of-contents (inhoudsopgave) items separately from body headings" in text
    assert "Parent-choice / heading navigation list MUST primarily use headings from the **document body**" in text
    assert "document body" in _read(ROOT / "PROTOCOL.md") or "documentlichaam" in _read(ROOT / "PROTOCOL.md")
    assert "inhoudsopgave" in _read(ROOT / "ROADMAP.md")
    assert "documentlichaam" in _read(ROOT / "ROADMAP.md") or "document body" in _read(ROOT / "ROADMAP.md")


def test_v228_block_a_outline_hierarchy_and_fallback() -> None:
    text = _block_a_text()
    assert "`5` → `5.4` → `5.4.1` → `5.4.2`" in text
    assert "Source/extract order remains fallback for headings without a reliable outline number" in text
    assert "5.4.1" in _read(ROOT / "PROTOCOL.md")
    assert "5.4.1" in _read(ROOT / "ROADMAP.md")
    assert "5.4.1" in _read(ROOT / "CHANGELOG.md")


def test_v228_block_a_near_duplicates_choice_list_only() -> None:
    text = _block_a_text()
    assert "Near-duplicates MAY be removed from the **choice list only**" in text
    assert "all source anchors MUST remain in freeze/audit trail" in text
    assert "choice list" in _read(ROOT / "CHANGELOG.md") or "keuzelijst" in _read(ROOT / "CHANGELOG.md")


def test_v228_block_a_page_locator_may_distinguish() -> None:
    text = _block_a_text()
    assert "MAY show page number or source locator to distinguish same-named headings" in text


def test_v228_block_a_structural_parent_validity() -> None:
    text = _block_a_text()
    assert "a parent MUST be structurally valid" in text
    assert "heading `5.4.1` MUST NOT get heading `2` as parent merely because it was extracted nearby" in text
    assert "Invalid parent proposals MUST NOT bind / MUST NOT be offered as default structure" in text
    assert "structureel geldig" in _read(ROOT / "PROTOCOL.md") or "structurally valid" in _read(ROOT / "PROTOCOL.md")
    assert "5.4.1" in _read(ROOT / "ROADMAP.md") and "ouder" in _read(ROOT / "ROADMAP.md")


def test_v228_block_a_product_rule_is_body_structure_not_extract_order() -> None:
    text = _block_a_text()
    assert "parent list shows a deduplicated, hierarchically ordered document structure from the main text" in text
    assert "Source order kept for provenance and as fallback" in text
    assert "Current extract order is useful for provenance but unsuitable as researcher navigation" in text


# ---------------------------------------------------------------------------
# Block B — Strength stamp gating, confirmed type only (independently testable)
# ---------------------------------------------------------------------------


def test_v228_block_b_proposed_recommendation_must_not_show_sterkte() -> None:
    text = _block_b_text()
    assert "A machine proposal `recommendation` MUST NOT activate/show Sterkte" in text
    assert "Sterkte" in _read(ROOT / "PROTOCOL.md")
    assert "machinevoorstel" in _read(ROOT / "PROTOCOL.md") or "machine proposal" in _read(ROOT / "PROTOCOL.md")
    assert "Sterkte" in _read(ROOT / "ROADMAP.md")
    assert "Sterkte" in _read(ROOT / "CHANGELOG.md")


def test_v228_block_b_sterkte_only_on_stored_confirmed_type() -> None:
    text = _block_b_text()
    assert "Sterkte visible and active ONLY when **stored/confirmed** type is Aanbeveling (`recommendation`) OR an actionable boom `outcome`" in text
    assert "stored/confirmed" in _read(ROOT / "PROTOCOL.md") or "opgeslagen/bevestigd" in _read(ROOT / "PROTOCOL.md")
    assert "Aanbeveling" in _read(ROOT / "ROADMAP.md") or "recommendation" in _read(ROOT / "ROADMAP.md")
    assert "outcome" in _read(ROOT / "CHANGELOG.md")


def test_v228_block_b_live_ui_before_submit() -> None:
    text = _block_b_text()
    assert "On type change in the browser, Sterkte MUST appear/disappear **before submit** (live UI)" in text
    assert "before submit" in _read(ROOT / "PROTOCOL.md") or "vóór submit" in _read(ROOT / "PROTOCOL.md")
    assert "live UI" in _read(ROOT / "ROADMAP.md") or "live-UI" in _read(ROOT / "ROADMAP.md")


def test_v228_block_b_type_change_away_clears_active_strength() -> None:
    text = _block_b_text()
    assert "If type changes away from recommendation/actionable outcome: Sterkte disappears immediately" in text
    assert "any previously chosen strength MUST NOT be actively saved on that object" in text
    assert "old value MAY remain in audit history only" in text
    assert "audit" in _read(ROOT / "CHANGELOG.md").lower()


def test_v228_block_b_machine_may_propose_hidden_until_confirm() -> None:
    text = _block_b_text()
    assert "Machine MAY still propose a strength value, but it MUST stay hidden/inactive until the user confirms the relevant type" in text


def test_v228_block_b_supersedes_proposed_type_stamp_gate() -> None:
    text = _block_b_text()
    assert "This SUPERSEDES any reading of Protocol v2.16/v2.17 that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm" in text
    assert "v2.16/v2.17 stamp-on-recommendation law remains; the gate becomes confirmed/stored type" in text
    assert "proposed_object_type" in _read(ROOT / "PROTOCOL.md")
    assert "proposed_object_type" in _read(ROOT / "ROADMAP.md")
    assert "proposed_object_type" in _read(ROOT / "CHANGELOG.md")


# ---------------------------------------------------------------------------
# Shared protocol wiring (not a substitute for Block A or Block B)
# ---------------------------------------------------------------------------


def test_v228_first_code_wave_is_forge_blocks_a_and_b_not_this_pr() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Next code after this protocol" in delta
    assert "MUST be Forge for exactly Blocks A+B with separate acceptance tests" in delta
    assert "MUST NOT implement v2.27 delete in this protocol PR" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "Forge" in root_protocol
    assert "Block A" in root_protocol and "Block B" in root_protocol
    assert "Forge" in roadmap
    assert "Block A" in roadmap and "Block B" in roadmap
    assert "Protocol v2.28.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "Forge" in changelog


def test_v228_roadmap_states_both_next_waves() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "v2.27 delete wave may already be in flight under separate Metis GO" in delta
    assert "this delta's next Forge wave is A+B after its own GO" in delta
    assert "ROADMAP MUST state both" in delta
    assert "v2.27" in roadmap and "type-to-confirm" in roadmap
    assert "Documentenhiërarchie" in roadmap
    assert "in flight" in roadmap or "al onderweg" in roadmap
    assert "Block A" in roadmap and "Block B" in roadmap
    assert "in flight" in changelog or "al onderweg" in changelog


def test_v228_g2_stays_blocked_publish_stays_blocked() -> None:
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


def test_v228_handoff_must_not_be_recreated() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`HANDOFF.md` MUST NOT be recreated" in delta
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in root_protocol
    assert "HANDOFF.md" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()


def test_v228_keeps_v227_delete_lock_and_v226_klasse_and_v225_boom() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm remains law" in delta or "v2.27 unpublished-delete Documentenhiërarchie only + type-to-confirm remains UNCHANGED" in delta
    assert "v2.25 boom path UNCHANGED" in delta or "v2.25 boom path remains UNCHANGED" in delta
    assert "Klasse wijzigen" in root_protocol
    assert "Klasse includes beslisboom; Klasse choice selects review path" in root_protocol
    assert "type-to-confirm" in root_protocol
    assert "Klasse includes beslisboom; Klasse choice selects review path" in roadmap
    assert "Documentenhiërarchie" in roadmap


def test_v228_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (parent-choice / heading navigation MUST use a deduplicated, hierarchically ordered document-body structure, not naive global numeric sort of TOC+body; Sterkte visible and active ONLY on stored/confirmed `recommendation` or actionable boom `outcome`, not on a machine-proposed type; SUPERSEDES the v2.16/v2.17 reading that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.28.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v228_leaves_v216_through_v226_untouched_except_stamp_and_next_code_pointers() -> None:
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
    v227 = (ROOT / "docs" / "PROTOCOL_V2_27_UNPUBLISHED_DELETE_DOCUMENTENHIERARCHIE_TYPE_CONFIRM_DELTA.md").read_bytes()
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
    assert b"**Protocol delta version:** 2.27.0" in v227
    new_law = b"naive global numeric sort"
    for old in (v218, v219, v220, v221, v222, v223, v224, v225, v226):
        assert new_law not in old
        assert b"confirmed/stored type" not in old
    assert b"Index/conflict pointer: Protocol v2.28.0" in v216
    assert b"Index/conflict pointer: Protocol v2.28.0" in v217
    assert b"Index/conflict pointer: Protocol v2.28.0" in v227
    assert b"Index/conflict pointer: Protocol v2.27.0" in v220
    assert b"Index/conflict pointer: Protocol v2.27.0" in v226
    assert new_law in DELTA.read_bytes()


def test_v228_does_not_reopen_serving_typeset_delete_waves_g2_or_v226_klasse() -> None:
    delta = _read(DELTA)
    assert "Do not reopen freeze/locator (v2.11), richtlijn-path serving types (v2.12), atomic objects/relations/four-eyes except the invalid-default-parent reading superseded here (v2.13), stamps on recommendation except the proposed-type gate superseded here (v2.16), researcher surface except the proposed-type stamp-UI reading superseded here (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished-delete Documentenhiërarchie + type-to-confirm (v2.27), waves A–D / deploy split (v2.21–v2.24), the v2.25 boom path, the v2.26 Klasse wijzigen architecture, or fail-closed G2 except as already required" in delta
    assert "The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED" in delta
    assert "The v2.25 closed boom-path typeset remains UNCHANGED" in delta


def test_v228_out_of_scope_matches_owner_lock() -> None:
    delta = _read(DELTA)
    assert "implementing structural heading navigation, parent-list hierarchy, or confirmed-type Sterkte gate" in delta
    assert "implementing v2.27 Documentenhiërarchie-only delete or type-to-confirm" in delta
    assert "G2 PASS" in delta
    assert "Protocol v2.14" in delta
    assert "LLM" in delta
    assert "nurse UI" in delta
    assert "recreating `HANDOFF.md`" in delta
    assert "adding numpy/sklearn" in delta
    assert "touching Azure deploy packaging" in delta
    assert "naive global numeric sort of all headings as the parent list" in delta


def test_v228_no_product_feature_code_in_this_pr() -> None:
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PROTOCOL_V2_28" in text or "confirmed_strength_gate" in text or "structural_heading_nav" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"protocol-only PR must not add heading-nav or strength-gate product code in src/: {src_hits}"
