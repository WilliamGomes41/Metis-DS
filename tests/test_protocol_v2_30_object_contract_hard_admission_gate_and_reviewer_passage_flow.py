from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_30_OBJECT_CONTRACT_HARD_ADMISSION_GATE_AND_REVIEWER_PASSAGE_FLOW_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_30_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _delta_sections_titled(block_label: str) -> str:
    """Return only delta headings whose title names this acceptance block.

    Numbered ``## N. Block A/B`` sections keep their ``###`` subsections.
    A ``### Block A/B`` purpose heading is closed by the next named block
    heading or by ``##`` — so Block B is not the rest of the file.
    """
    chunks: list[str] = []
    current: list[str] = []
    keep = False
    in_numbered_block_section = False
    for line in _read(DELTA).splitlines(keepends=True):
        if line.startswith("## "):
            if keep and current:
                chunks.append("".join(current))
            current = [line]
            keep = block_label in line
            in_numbered_block_section = keep
        elif line.startswith("### "):
            names_block = "Block A" in line or "Block B" in line
            if names_block:
                if keep and current:
                    chunks.append("".join(current))
                current = [line]
                keep = block_label in line
                in_numbered_block_section = False
            elif keep and in_numbered_block_section:
                current.append(line)
            else:
                if keep and current:
                    chunks.append("".join(current))
                current = []
                keep = False
                in_numbered_block_section = False
        elif keep:
            current.append(line)
    if keep and current:
        chunks.append("".join(current))
    text = "".join(chunks)
    assert text.strip(), f"delta has no bounded {block_label} sections"
    return text


def _block_a_text() -> str:
    """Block A norms from Block A delta sections only — not the full corpus."""
    return _delta_sections_titled("Block A")


def _block_b_text() -> str:
    """Block B norms from Block B delta sections only — not the full corpus."""
    return _delta_sections_titled("Block B")


def test_v230_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.30.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_30_OBJECT_CONTRACT_HARD_ADMISSION_GATE_AND_REVIEWER_PASSAGE_FLOW_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-05"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v230_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.30.0" in delta
    assert "docs/PROTOCOL_V2_30_OBJECT_CONTRACT_HARD_ADMISSION_GATE_AND_REVIEWER_PASSAGE_FLOW_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.30.0") == 1
    assert "plus Protocol v2.29.0 plus Protocol v2.28.0 plus Protocol v2.27.0 plus Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.29.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.28.0" not in root_protocol
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
    assert "Protocol v2.30.0" in roadmap


def test_v230_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v230_two_acceptance_blocks_are_independently_named() -> None:
    delta = _read(DELTA)
    assert "two separate acceptance blocks" in delta
    assert "The two blocks MUST be independently testable" in delta
    assert "A pass of Block A MUST NOT be treated as a pass of Block B" in delta
    assert "A pass of Block B MUST NOT be treated as a pass of Block A" in delta
    assert "### Block A — Hard admission gate, object contract, reason codes" in delta
    assert "### Block B — Reviewer passage-flow, documentpositie, real open-source context" in delta
    block_a = _block_a_text()
    block_b = _block_b_text()
    assert block_a != block_b
    assert "### Block B —" not in block_a
    assert "### Block A —" not in block_b
    assert "actor_of_scope" in block_a
    assert "actor_of_scope" not in block_b
    assert "Review opslaan en volgende" in block_b
    assert "Review opslaan en volgende" not in block_a


# ---------------------------------------------------------------------------
# Block A — Hard admission gate / object contract / reason codes
# ---------------------------------------------------------------------------


def test_v230_block_a_hard_gate_literal_source_not_soft_scores() -> None:
    text = _block_a_text()
    assert "A knowledge object MAY be proposed ONLY when all required fields for the proposed type are filled with literal localizable source text" in text or "MAY be proposed ONLY when all required fields" in text
    assert "gate_result=blocked" in text or "`gate_result=blocked`" in text
    assert "Soft scores" in text
    assert "MUST NOT open the hard gate" in text
    assert "impliciet" in text


def test_v230_block_a_no_tradeoff_ui_polish_must_not_excuse_bad_candidates() -> None:
    text = _block_a_text()
    assert "There MUST be NO tradeoff" in text
    assert "UI polish MUST NOT excuse bad candidates" in text
    assert "~5/10" in text
    assert "volume" in text and "ship then fix" in text and "MUST NOT open the hard gate" in text
    assert "Blocked candidates MUST NOT enter the ordinary review queue" in text
    assert "ship then fix" in text
    assert "volume" in text


def test_v230_block_a_required_candidate_fields_and_admission() -> None:
    text = _block_a_text()
    for field in (
        "candidate_id",
        "document_id",
        "document_version",
        "source_hash",
        "section_path",
        "source_locator_start",
        "source_locator_end",
        "source_text_exact",
        "candidate_text",
        "subject_span",
        "predicate_span",
        "proposed_type",
        "type_evidence_spans",
        "context_before",
        "context_after",
        "conditions_detected",
        "exceptions_detected",
        "comparison_markers",
        "comparison_targets",
        "references_detected",
        "references_resolved",
        "abbreviations_detected",
        "abbreviations_resolved",
        "related_candidates",
        "gate_result",
        "reason_codes",
    ):
        assert field in text
    assert "allowed" in text and "blocked" in text
    assert "full carrying sentence" in text
    assert "type_contract" in text
    assert "context scan done" in text


def test_v230_block_a_type_contracts_named() -> None:
    text = _block_a_text()
    assert "Aanbeveling" in text
    assert "actor_of_scope" in text
    assert "recommended_action" in text
    assert "action_object_or_goal" in text
    assert "recommendation_evidence_span" in text
    assert "Definitie" in text
    assert "Voorwaarde" in text
    assert "Uitzondering" in text
    assert "Feitelijke constatering" in text
    assert "Toelichting" in text
    assert "not independently publishable by default" in text


def test_v230_block_a_richtlijn_scope_does_not_break_v225_boom() -> None:
    text = _block_a_text()
    assert "richtlijn inhoudelijke candidates" in text or "richtlijn-path" in text or "richtlijn path" in text
    assert "path" in text and "node" in text and "outcome" in text
    assert "separate boom-gate GO" in text
    assert "MUST NOT force boom candidates through the six richtlijn contracts" in text or "MUST NOT force boom candidates" in text
    assert "MUST NOT invent" in text and "boom" in text
    assert "type_contract_incomplete" in text
    assert "v2.25" in text


def test_v230_block_a_phase1_must_not_empty_queue_with_context_scan_not_done() -> None:
    text = _block_a_text()
    assert "Phase-1 admission set" in text or "Phase-1" in text
    assert "minimal" in text
    assert "context_before" in text and "context_after" in text
    assert "MUST NOT treat `context_scan_not_done` as a universal hard block" in text or "MUST NOT empty the ordinary review queue with `context_scan_not_done`" in text
    assert "MUST NOT be a Phase-1 admission prerequisite" in text
    assert "passage-register" in text or "passage register" in text


def test_v230_block_a_factual_finding_confirms_as_explanation() -> None:
    text = _block_a_text()
    assert "Confirm → `explanation`" in text or "confirm → `explanation`" in text or "MUST map to existing closed serving type `explanation`" in text or "MUST be the existing closed type `explanation`" in text
    assert "MUST NOT invent a seventh closed serving type" in text
    assert "MUST NOT serve that object as recommendation / handelingsadvies" in text or "MUST NOT be served as recommendation / handelingsadvies" in text
    assert "confirmed_object_type=factual_finding" in text


def test_v230_block_a_hard_reason_codes_named() -> None:
    text = _block_a_text()
    for code in (
        "incomplete_sentence",
        "subject_missing",
        "predicate_missing",
        "unresolved_reference",
        "comparison_target_missing",
        "abbreviation_unresolved",
        "table_of_contents_entry",
        "editorial_transition_only",
        "recommendation_evidence_missing",
        "condition_target_missing",
        "exception_target_missing",
        "supported_object_missing",
        "no_independent_claim",
        "duplicates",
        "source_fidelity_failure",
    ):
        assert code in text


def test_v230_block_a_djg_regression_reason_codes() -> None:
    text = _block_a_text()
    assert "De dJG wordt in Nederland vaker gebruikt." in text
    assert "MUST NOT enter the ordinary queue as Aanbeveling" in text or "MUST NOT enter ordinary queue as Aanbeveling" in text
    assert "recommendation_evidence_missing" in text
    assert "comparison_target_missing" in text
    assert "abbreviation_unresolved" in text


def test_v230_block_a_also_regresses_named_cases() -> None:
    text = _block_a_text()
    assert "one-word" in text
    assert "unresolved ref" in text
    assert "incomplete comparison" in text
    assert "false recommendation" in text
    assert "adviseert" in text
    assert "lone exception" in text
    assert "recommendation+exception" in text


def test_v230_block_a_context_scan_atomicity_passage_register() -> None:
    text = _block_a_text()
    assert "candidate paragraph" in text
    assert "previous paragraph" in text or "prev/next paragraph" in text
    assert "ancestor headings" in text
    assert "MUST NOT claim that context is unnecessary without recording" in text or "MUST NOT claim context is unnecessary without recording" in text
    assert "NOT always one word" in text
    assert "MUST NOT split into broken fragments" in text
    assert "selected_as_candidate" in text
    assert "used_as_context" in text
    assert "linked_as_support" in text
    assert "excluded_with_reason" in text
    assert "not_yet_assessed" in text
    assert "MUST NOT silently drop passages" in text
    assert "no duty to objectify every sentence" in text or "No duty to objectify every sentence" in text


# ---------------------------------------------------------------------------
# Block B — Reviewer passage-flow / documentpositie / real open-source context
# ---------------------------------------------------------------------------


def test_v230_block_b_documentpositie_ordinary_language() -> None:
    text = _block_b_text()
    assert "Gevonden onder" in text
    assert "Dit klopt" in text
    assert "Andere kop kiezen" in text
    assert "Relatie bevestigen" in text
    assert "ordinary language only" in text


def test_v230_block_b_visibility_and_no_parent_jargon_on_primary() -> None:
    text = _block_b_text()
    assert "if the reviewer need not act → do not show" in text or "if reviewer need not act → do not show" in text
    assert "one clear action in ordinary language" in text
    assert "No ouder/kind/parent/confirmed relation on the primary surface" in text or "no ouder/kind/parent/confirmed relation on the primary surface" in text
    assert "body headings only" in text
    assert "TOC excluded" in text


def test_v230_block_b_open_bron_real_surrounding_context() -> None:
    text = _block_b_text()
    assert "Open volledige richtlijn" in text
    assert "MUST NOT merely enlarge the same truncated card sentence" in text
    assert "surrounding page/paragraph context" in text
    assert "exact span marked" in text
    assert "real open-source context" in text or "Real open-source context" in text


def test_v230_block_b_review_ui_order_one_save() -> None:
    text = _block_b_text()
    assert "Review opslaan en volgende" in text
    assert "mist context" in text
    assert "samenvoegen" in text
    assert "alleen onderbouwing" in text
    assert "geen kenniseenheid" in text
    assert "Type wijzigen" in text
    assert "MUST NOT start from only “nog niet bevestigd”" in text or 'MUST NOT start from only "nog niet bevestigd"' in text
    assert "Goedkeuren na correctie" in text
    assert "Later beoordelen" in text
    assert "v2.28 Sterkte-on-confirmed-type remains" in text


# ---------------------------------------------------------------------------
# Shared protocol wiring (not a substitute for Block A or Block B)
# ---------------------------------------------------------------------------


def test_v230_wired_docs_repeat_block_norms() -> None:
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    for surface in (root_protocol, roadmap, changelog):
        assert "There MUST be NO tradeoff" in surface
        assert "UI polish MUST NOT excuse bad candidates" in surface
        assert "~5/10" in surface
        assert "blocked candidates MUST NOT enter the ordinary review queue" in surface or "Blocked candidates MUST NOT enter the ordinary review queue" in surface
        assert "ship then fix" in surface
        assert "Gevonden onder" in surface
        assert "De dJG wordt in Nederland vaker gebruikt." in surface
        assert "recommendation_evidence_missing" in surface or "context_scan_not_done" in surface
    assert "Open volledige richtlijn" in root_protocol
    assert "Open volledige richtlijn" in roadmap
    assert "truncated card sentence" in changelog or "afgekapte kaartzin" in changelog
    assert "boom" in root_protocol.lower() and "v2.25" in root_protocol
    assert "context_scan_not_done" in roadmap
    assert "explanation" in changelog
    assert "Aanbeveling" in root_protocol or "aanbeveling" in root_protocol


def test_v230_roadmap_states_four_forge_phases_not_this_pr() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "four Forge phases after separate Metis GOs" in delta
    assert "fields + contracts + hard gate + reason codes + dJG regression" in delta
    assert "context / refs / abbrev / comparisons / expand-merge" in delta
    assert "review UI + open-bron real context + collapsed document position" in delta
    assert "passage register + coverage + gold + metrics" in delta
    assert "MUST NOT implement Forge phases" in delta or "MUST NOT implement those phases" in delta
    assert "Forge" in root_protocol
    assert "dJG" in roadmap
    assert "Forge" in roadmap
    assert "fase 1" in roadmap.lower() or "phase 1" in roadmap.lower() or "velden + contracten" in roadmap
    assert "Protocol v2.30.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "Forge" in changelog


def test_v230_g2_stays_blocked_publish_stays_blocked() -> None:
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


def test_v230_handoff_must_not_be_recreated() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`HANDOFF.md` MUST NOT be recreated" in delta
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in root_protocol
    assert "HANDOFF.md" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()


def test_v230_keeps_prior_locks() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "v2.28 Sterkte-on-confirmed-type remains" in delta
    assert "v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm remains law" in delta or "v2.27 unpublished-delete Documentenhiërarchie only + type-to-confirm remains UNCHANGED" in delta
    assert "v2.25 boom path UNCHANGED" in delta or "v2.25 boom path remains UNCHANGED" in delta
    assert "v2.29 temporary production-only deploy remains" in delta or "v2.29 temporary production-only deploy remains UNCHANGED" in delta
    assert "Klasse wijzigen" in root_protocol
    assert "Klasse includes beslisboom; Klasse choice selects review path" in root_protocol
    assert "type-to-confirm" in root_protocol
    assert "Klasse includes beslisboom; Klasse choice selects review path" in roadmap
    assert "Documentenhiërarchie" in roadmap


def test_v230_is_c3_spanning_extract_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning extract/review-surface / retrieve-safety" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.30.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning extract/review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v230_leaves_prior_deltas_untouched_except_index_conflict_pointers() -> None:
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
    v228 = (ROOT / "docs" / "PROTOCOL_V2_28_STRUCTURAL_HEADING_NAV_AND_CONFIRMED_STRENGTH_GATE_DELTA.md").read_bytes()
    v229 = (ROOT / "docs" / "PROTOCOL_V2_29_TEMPORARY_PRODUCTION_ONLY_DEPLOY_DELTA.md").read_bytes()
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
    assert b"**Protocol delta version:** 2.28.0" in v228
    assert b"tijdelijke productie-only deployment" in v229
    new_law = b"De dJG wordt in Nederland vaker gebruikt."
    for old in (v218, v220, v221, v222, v223, v224, v225, v226, v227, v229):
        assert new_law not in old
    assert b"Index/conflict pointer: Protocol v2.30.0" in v216
    assert b"Index/conflict pointer: Protocol v2.30.0" in v217
    assert b"Index/conflict pointer: Protocol v2.30.0" in v219
    assert b"Index/conflict pointer: Protocol v2.30.0" in v228
    assert b"Index/conflict pointer: Protocol v2.28.0" in v216
    assert b"Index/conflict pointer: Protocol v2.28.0" in v217
    assert b"Index/conflict pointer: Protocol v2.28.0" in v227
    assert new_law in DELTA.read_bytes()


def test_v230_does_not_reopen_sterkte_delete_boom_klasse_g2_or_v229() -> None:
    delta = _read(DELTA)
    assert "v2.28 Sterkte-on-confirmed-type remains" in delta
    assert "The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED" in delta
    assert "The v2.25 closed boom-path typeset remains UNCHANGED" in delta
    assert "v2.29 temporary production-only deploy remains UNCHANGED" in delta or "v2.29 temporary production-only deploy remains law" in delta


def test_v230_metrics_and_gold_required_by_protocol() -> None:
    delta = _read(DELTA)
    assert "precision" in delta
    assert "type accuracy" in delta
    assert "context completeness" in delta
    assert "coverage vs gold" in delta
    assert "review burden" in delta
    assert "gold standard is required before claiming extract quality" in delta or "A gold standard is required before claiming extract quality" in delta


def test_v230_out_of_scope_matches_owner_lock() -> None:
    delta = _read(DELTA)
    assert "implementing Forge phases 1–4" in delta
    assert "G2 PASS" in delta
    assert "Protocol v2.14" in delta
    assert "LLM" in delta
    assert "nurse UI" in delta
    assert "recreating `HANDOFF.md`" in delta
    assert "adding numpy/sklearn" in delta
    assert "touching Azure deploy packaging" in delta
    assert "filling missing required fields with “impliciet” prose" in delta or 'filling missing required fields with "impliciet" prose' in delta
    assert "ship then fix" in delta
    assert "UI polish" in delta
    assert "blocked candidates enter the ordinary review queue" in delta


def test_v230_no_product_feature_code_in_this_pr() -> None:
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PROTOCOL_V2_30" in text or "hard_admission_gate" in text or "reason_codes" in text and "v2_30" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"protocol-only PR must not add admission-gate product code in src/: {src_hits}"
