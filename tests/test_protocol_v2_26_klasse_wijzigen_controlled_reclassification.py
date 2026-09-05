from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_26_KLASSE_WIJZIGEN_CONTROLLED_RECLASSIFICATION_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_26_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v226_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.26.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_26_KLASSE_WIJZIGEN_CONTROLLED_RECLASSIFICATION_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-05"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v226_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.26.0" in delta
    assert "docs/PROTOCOL_V2_26_KLASSE_WIJZIGEN_CONTROLLED_RECLASSIFICATION_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.29.0") == 1
    assert "De geldende normatieve baseline is Protocol v2.26.0" not in root_protocol
    assert "plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
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
    assert "Protocol v2.26.0" in roadmap


def test_v226_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v226_core_rule_supersedes_promote_class_total_wipe() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "A document class change MUST invalidate only what that class change substantively affects" in delta
    assert "MUST NOT be a silent total wipe of all review state as the only story" in delta
    assert "current `promote_class` reset" in delta
    assert "SUPERSEDED for the target architecture" in delta
    assert "temporary safe full re-review" in delta or "temporary safe **full** re-review" in delta
    assert "selectieve invalidatie" in root_protocol or "selective invalidation" in root_protocol
    assert "promote_class" in root_protocol
    assert "promote_class" in roadmap
    assert "promote_class" in changelog
    assert "silent total wipe" in changelog or "stille total wipe" in changelog


def test_v226_source_unchanged() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Class change MUST NOT alter freeze bytes, SHA-256, title, version, or provenance of the source" in delta
    assert "Class is how Metis interprets the document, not what the source is" in delta
    assert "SHA-256" in root_protocol
    assert "provenance" in root_protocol or "provenance" in changelog
    assert "SHA-256" in changelog


def test_v226_object_review_model_distinction() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "**richtlijn-path Klassen**" in delta or "richtlijn-path Klassen" in delta
    assert "`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast`" in delta
    assert "**beslisboom-path Klasse**" in delta or "beslisboom-path Klasse" in delta
    assert "`path` / `node` / `outcome`" in delta
    assert "Cross-model" in delta or "cross-model" in delta
    assert "boom vs non-boom" in delta or "boom vs niet-boom" in root_protocol
    assert "beslisboom" in root_protocol
    assert "beslisboom" in roadmap


def test_v226_transition_matrix() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "transcript → artikel" in delta
    assert "artikel → handreiking" in delta
    assert "handreiking → richtlijn" in delta
    assert "richtlijn → artikel" in delta
    assert "richtlijn → beslisboom" in delta
    assert "beslisboom → richtlijn" in delta
    assert "any non-boom ↔ beslisboom" in delta or "any non-boom ↔ `beslisboom`" in delta
    assert "beslisboom → other non-boom" in delta
    assert "MUST NOT direct class change / re-label objects across models" in delta
    assert "MUST block direct change and REQUIRE re-extract from the same freeze" in delta
    assert "Prior object set MUST remain as audit history of prior processing" in delta
    assert "re-extract" in root_protocol
    assert "cross-model" in root_protocol.lower() or "Cross-model" in root_protocol
    assert "re-extract" in changelog
    assert "transcript" in changelog and "artikel" in changelog


def test_v226_same_model_keeps_objects_selective_invalidation() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "keep objects, locators, fragment bounds, content hashes, class-independent relations" in delta
    assert "Re-open only class-dependent confirmations" in delta or "re-open only class-dependent confirmations" in delta
    assert "Target architecture = selective invalidation" in delta or "target architecture = selective invalidation" in delta
    assert "selectieve invalidatie" in root_protocol
    assert "selectieve invalidatie" in roadmap


def test_v226_review_history_auditability() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "MUST NOT conceptually wipe `validated_by` / `validation_date` / `review_snapshot_hash` alone" in delta
    assert "document_class_changed" in delta
    assert "keep prior review reconstructible" in delta
    assert "auditability of prior review + invalidation reason/time" in delta
    assert "document_class_changed" in root_protocol
    assert "document_class_changed" in changelog


def test_v226_published_never_rewritten() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "MUST NOT mutate the live published release back to unpublished" in delta
    assert "MUST create a new draft candidate version" in delta
    assert "published v1 remains until v2 is published" in delta
    assert "does not open `publish()`" in delta or "does not open publish()" in delta
    assert "unpublished" in root_protocol
    assert "published-candidate" in roadmap or "draft-kandidaat" in root_protocol
    assert "published" in changelog.lower()


def test_v226_ux_rename_promoveren_to_klasse_wijzigen() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Rename console action **Promoveren** → **Klasse wijzigen**" in delta or "Rename the console action **Promoveren** → **Klasse wijzigen**" in delta
    assert "Before confirm, MUST show consequence" in delta or "before confirm, MUST show consequence" in delta
    assert "source unchanged" in delta
    assert "same-model vs cross-model" in delta
    assert "objects kept vs re-extract required" in delta
    assert "Klasse wijzigen" in root_protocol
    assert "Promoveren" in root_protocol
    assert "Klasse wijzigen" in roadmap
    assert "Promoveren" in roadmap
    assert "Klasse wijzigen" in changelog
    assert "Promoveren" in changelog
    assert "Klasse promoveren MUST review" in roadmap
    assert "Klasse promoveren MUST een nieuwe review vereisen" in root_protocol


def test_v226_first_code_wave_is_forge_klasse_wijzigen_not_this_pr() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Rename **Promoveren** → **Klasse wijzigen**" in delta
    assert "Enforce the matrix" in delta or "Enforce matrix" in delta
    assert "block direct change + require re-extract on the same freeze" in delta
    assert "keep the existing safe **full** re-review" in delta or "keep the existing safe full re-review" in delta
    assert "Show consequence before confirm" in delta or "show consequence" in delta
    assert "Record class change as an audit-event" in delta or "audit-event" in delta
    assert "Source / SHA unchanged" in delta or "Source/SHA unchanged" in delta or "source/SHA unchanged" in delta
    assert "MUST NOT implement selective invalidation, published-candidate fork, or full `previous_review` schema in that first code wave unless separately GO’d" in delta or "MUST NOT implement selective invalidation, published-candidate fork, or full `previous_review` schema in that first code wave unless separately GO'd" in delta
    assert "ROADMAP MUST mark selective invalidation + published-candidate as next after the narrow wave" in delta or "ROADMAP MUST mark selective + published-candidate as next after the narrow wave" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "Forge" in root_protocol
    assert "Klasse-wijzigen" in root_protocol or "Klasse wijzigen" in root_protocol
    assert "Forge" in roadmap
    assert "selectieve invalidatie + published-candidate" in roadmap
    assert "Protocol v2.26.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "Forge" in changelog


def test_v226_g2_stays_blocked_publish_stays_blocked() -> None:
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


def test_v226_handoff_must_not_be_recreated() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`HANDOFF.md` MUST NOT be recreated" in delta
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in root_protocol
    assert "HANDOFF.md" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()


def test_v226_keeps_v225_boom_path_and_continentie_evidence() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "v2.25 boom path UNCHANGED" in delta or "v2.25 boom path remains UNCHANGED" in delta or "Protocol v2.25 UNCHANGED" in delta
    assert "Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain" in delta
    assert "PROTOCOL.md is wet voor iedere richtlijn, niet Continentie-only" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in roadmap
    assert "Klasse includes beslisboom; Klasse choice selects review path" in root_protocol
    assert "Klasse includes beslisboom; Klasse choice selects review path" in roadmap


def test_v226_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (controlled Klasse wijzigen / reclassification; a document class change MUST invalidate only what that class change substantively affects; current `promote_class` silent total wipe SUPERSEDED for the target architecture; temporary safe full re-review allowed in the first implementation wave; source freeze bytes / SHA-256 / title / version / provenance MUST NOT change; same-model vs cross-model matrix; published never rewritten; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.26.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v226_leaves_v216_through_v224_delta_files_untouched_except_v225_pointer() -> None:
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
    new_law = b"Klasse wijzigen / controlled reclassification"
    for old in (v216, v217, v218, v219, v220, v221, v222, v223, v224):
        assert new_law not in old
        assert b"document_class_changed" not in old
    assert b"Index/conflict pointer: Protocol v2.26.0" in v225
    assert new_law in DELTA.read_bytes()


def test_v226_does_not_reopen_serving_typeset_stamps_waves_g2_or_v225_boom() -> None:
    delta = _read(DELTA)
    assert "Do not reopen freeze/locator (v2.11), richtlijn-path serving types (v2.12), atomic objects/relations/four-eyes (v2.13), stamps on recommendation (v2.16), researcher surface (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished delete (v2.20), waves A–D / deploy split (v2.21–v2.24), the v2.25 boom path, or fail-closed G2 except as already required" in delta
    assert "The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED" in delta
    assert "The v2.25 closed boom-path typeset remains UNCHANGED" in delta


def test_v226_out_of_scope_matches_owner_lock() -> None:
    delta = _read(DELTA)
    assert "implementing Klasse wijzigen, the transition matrix, selective invalidation, published-candidate fork, or full `previous_review` schema" in delta
    assert "G2 PASS" in delta
    assert "Protocol v2.14" in delta
    assert "LLM" in delta
    assert "nurse UI" in delta
    assert "recreating `HANDOFF.md`" in delta
    assert "adding numpy/sklearn" in delta
    assert "touching Azure deploy packaging" in delta
    assert "mutating a live published release back to unpublished" in delta
    assert "re-labelling objects across review models" in delta


def test_v226_no_product_feature_code_in_this_pr() -> None:
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PROTOCOL_V2_26" in text or "klasse_wijzigen_controlled_reclassification" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"protocol-only PR must not add Klasse wijzigen product code in src/: {src_hits}"
