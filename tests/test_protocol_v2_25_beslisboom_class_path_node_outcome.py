from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_25_BESLISBOOM_CLASS_PATH_NODE_OUTCOME_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_25_approval.json"

UNQUALIFIED_OUT_PATTERNS = (
    "boom players MUST be out of the first wave",
    "boom players MUST stay entirely out of the MVP",
    "`story.html`-boomplayers vallen buiten de first wave",
    "story.html`-boomplayers vallen buiten de first wave",
    "story.html-boomplayers vallen buiten de first wave",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v225_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.25.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_25_BESLISBOOM_CLASS_PATH_NODE_OUTCOME_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-04"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v225_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.25.0" in delta
    assert "docs/PROTOCOL_V2_25_BESLISBOOM_CLASS_PATH_NODE_OUTCOME_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.25.0") == 1
    assert "plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
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
    assert "Protocol v2.25.0" in roadmap


def test_v225_mentions_beslisboom_path_node_outcome() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "beslisboom" in delta
    assert "`path`" in delta
    assert "`node`" in delta
    assert "`outcome`" in delta
    assert "pad / node / uitkomst" in delta or "pad / node / uitkomst" in root_protocol
    assert "beslisboom" in root_protocol
    assert "`path`" in root_protocol or "path" in root_protocol
    assert "`node`" in root_protocol or "node" in root_protocol
    assert "`outcome`" in root_protocol or "outcome" in root_protocol
    assert re.search(r"\bpath\b", root_protocol)
    assert re.search(r"\bnode\b", root_protocol)
    assert re.search(r"\boutcome\b", root_protocol)
    assert "beslisboom" in roadmap
    assert "path" in roadmap and "node" in roadmap and "outcome" in roadmap
    assert "beslisboom" in changelog
    assert "path" in changelog and "node" in changelog and "outcome" in changelog


def test_v225_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v225_supersedes_v27_boom_out_of_mvp_as_knowledge_class() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "kennisplatform `story.html` boom players MUST stay entirely out of the MVP / first console **as a knowledge class**" in delta
    assert "beslisboom class is in the MVP for researcher ingest+review" in delta
    assert "Storyline **player package** is not the Product API surface" in delta
    assert "MUST NOT be the nurse console" in delta
    assert "only MVP document classes are guideline HTML/PDF without a boom path" in delta
    assert "v2.25" in root_protocol
    assert "boom-in-MVP" in root_protocol or "beslisboom-klasse hoort in het MVP" in root_protocol
    assert "v2.7" in root_protocol
    assert "story.html" in root_protocol or "Storyline" in root_protocol
    assert "beslisboom-klasse hoort in het MVP" in root_protocol
    assert "v2.25" in roadmap
    assert "beslisboom" in roadmap
    assert "v2.7" in changelog or "Protocol v2.7" in changelog
    assert "story.html" in changelog or "Storyline" in changelog


def test_v225_no_unqualified_claim_story_html_wholly_out_of_mvp() -> None:
    """Law lock: no live steering doc may claim story.html boom stays wholly
    out of MVP without the v2.25 supersession pointer."""
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")

    assert "as a knowledge class" in delta
    assert "player package" in delta.lower() or "Storyline **player package**" in delta
    assert "v2.25" in root_protocol
    assert "beslisboom" in root_protocol

    steering = (
        ("PROTOCOL.md", root_protocol),
        ("ROADMAP.md", roadmap),
        ("CHANGELOG.md", changelog),
        ("docs/GOVERNANCE.md", governance),
    )
    for label, text in steering:
        for pattern in UNQUALIFIED_OUT_PATTERNS:
            if pattern not in text:
                continue
            for match in re.finditer(re.escape(pattern), text):
                start = max(0, match.start() - 400)
                end = min(len(text), match.end() + 400)
                window = text[start:end]
                assert "v2.25" in window or "Protocol v2.25" in window or "SUPERSEDE" in window or "supersessie" in window, (
                    f"{label} still claims {pattern!r} without a v2.25 supersession pointer nearby"
                )


def test_v225_klasse_includes_beslisboom_and_selects_review_path() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "SUPERSEDES any reading that Inleveren needs a separate path control distinct from Klasse" in delta
    assert "Closed Klasse set MUST include `beslisboom`" in delta
    assert "Operators MUST NOT invent other Klasse values" in delta
    assert "Choosing Klasse = `beslisboom` MUST select the boom review path (`path` / `node` / `outcome`)" in delta
    assert "Choosing Klasse = `richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` MUST select the existing non-boom (richtlijn-style) review path / stacks for that document" in delta
    assert "MUST NOT invent boom types on those classes" in delta
    assert "Klasse includes beslisboom; Klasse choice selects review path" in delta
    assert "At Inleveren the researcher MUST choose **Klasse** from the closed set" in delta
    assert "Operators MUST NOT add a second chooser labeled “path”" in delta
    assert "`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` | `beslisboom`" in delta
    assert "Family × class remains" in delta
    assert "Paths MAY differ for the same family" in delta
    assert "Klasse-keuze selecteert het reviewpad" in root_protocol
    assert "MUST NOT een aparte tweede kiezer «pad»" in root_protocol
    assert "gesloten set" in root_protocol and "beslisboom" in root_protocol
    assert "Inleveren" in root_protocol
    assert "Klasse includes beslisboom; Klasse choice selects review path" in root_protocol
    assert "Klasse includes beslisboom; Klasse choice selects review path" in roadmap
    assert "Klasse-keuze selecteert het reviewpad" in roadmap
    assert "MUST NOT een aparte tweede kiezer «pad»" in roadmap
    assert "Klasse includes beslisboom; Klasse choice selects review path" in changelog
    assert "separate path control distinct from Klasse" in changelog


def test_v225_closed_boom_types_and_scorelist_choice() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "`path` — ordered reviewable branch/route through the boom" in delta
    assert "`node` — decision point / question / branch choice" in delta
    assert "`outcome` — terminal advice text for a path/node combination" in delta
    assert "Operators MUST NOT invent others" in delta or "Operators MUST NOT invent other boom types" in delta
    assert "scorelist item MAY be modeled as a `node`" in delta
    assert "MUST NOT add a fourth closed boom type" in delta
    assert "Prefer `node` + metadata" in delta
    assert "path" in root_protocol and "node" in root_protocol and "outcome" in root_protocol
    assert "scorelist" in root_protocol


def test_v225_richtlijn_path_keeps_v212_types() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED" in delta
    assert "`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`" in delta
    assert "MUST NOT require boom types on the richtlijn path" in delta
    assert "richtlijnpad" in root_protocol or "richtlijn-pad" in root_protocol or "richtlijn path" in root_protocol.lower()
    assert "heading" in root_protocol
    assert "recommendation" in root_protocol


def test_v225_relations_applies_if_and_no_silent_fusion() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "`outcome` MUST bind to the `node` / `path` conditions via `applies_if`" in delta
    assert "MUST NOT silently fuse condition into outcome as the only representation" in delta
    assert "Cross-guideline references in outcome bodies" in delta
    assert "SHOULD become `supported_by` / `explains` targets" in delta
    assert "MUST NOT remain body-only forever as the sole link" in delta
    assert "applies_if" in root_protocol
    assert "supported_by" in root_protocol


def test_v225_review_functions_and_empty_outcomes() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Confirm `path` as structure (batch OK)" in delta
    assert "Confirm `node` (slow if it gates advice)" in delta
    assert "Confirm `outcome` as advice" in delta
    assert "DOEN / OVERWEEG / NIET DOEN" in delta or "DOEN/OVERWEEG/NIET DOEN" in delta
    assert "geen actie nodig" in delta
    assert "MUST NOT be served as positive advice" in delta
    assert "Split multi-bullet outcomes into atomic outcomes OR reject until split" in delta
    assert "Empty/placeholder outcomes" in delta
    assert "`UitkomstX_Y_titel`" in delta
    assert "MUST NOT pass review" in delta
    assert "vitamine D 800IE" in delta
    assert "four-eyes" in delta
    assert "Bronpassage + open-original remain required" in delta
    assert "geen actie nodig" in root_protocol
    assert "UitkomstX_Y_titel" in root_protocol or "placeholder" in root_protocol
    assert "path" in roadmap


def test_v225_freeze_locator_and_not_live_rest_as_sole_truth() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "hashed freeze of the canonical boom knowledge" in delta
    assert "node text + outcome text at minimum" in delta
    assert "MUST NOT treat live kennisplatform REST (`/wp-json/beslisboom/v1/outcomes`) as the sole source of truth" in delta
    assert "Live URL-HTML Storyline `story.html` alone remains insufficient" in delta
    assert "byte-freeze + locators + SHA-256" in delta
    assert "Exact packaging format for boom freeze" in delta
    assert "MAY be left to the implementation PR" in delta
    assert "SHA-256" in root_protocol
    assert "beslisboom/v1" in root_protocol or "wp-json/beslisboom" in root_protocol
    assert "SHA-256" in changelog


def test_v225_class_axis_lighter_than_richtlijn() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "lighter/derived class than `richtlijn`" in delta
    assert "Heavier class MUST NOT be filled by lighter class" in delta
    assert "Promoting or substituting boom `outcome`s for unpublished or missing guideline `recommendation`s MUST NOT happen silently" in delta
    assert "MUST outrank a `beslisboom` `outcome`" in delta
    assert "lichtere/afgeleide klasse" in root_protocol or "lichter/afgeleid" in root_protocol
    assert "MUST NOT stilzwijgend" in root_protocol or "stilzwijgend" in root_protocol
    assert "lichtere/afgeleide klasse" in roadmap or "lichter" in roadmap


def test_v225_console_not_nurse_tree_player_reviewing_allowed() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "MUST NOT become a nurse-facing interactive tree player" in delta
    assert "still true for console UX" in delta
    assert "Reviewing beslisboom objects as researchers is allowed" in delta
    assert "nurse" in root_protocol.lower() or "verpleegkundige" in root_protocol
    assert "verpleegkundige" in roadmap or "nurse" in roadmap


def test_v225_next_code_is_forge_beslisboom_path_not_this_pr() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "The next **code** MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** the beslisboom path wave" in delta
    assert "Klasse includes beslisboom; Klasse choice selects review path" in delta
    assert "MUST NOT activate Product API boom serving in that first code wave unless separately GO’d" in delta or "MUST NOT activate Product API boom serving in that first code wave unless separately GO'd" in delta
    assert "MUST NOT open G2/`publish()`" in delta
    assert "no Cloud Shell ZIP required for this delta alone" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "MUST NOT implement ingest UI, extract, Storyline parser, or API scraper in this PR" in delta
    assert "Forge" in root_protocol
    assert "beslisboom-pad" in root_protocol or "beslisboom path" in root_protocol
    assert "Forge" in roadmap
    assert "Protocol v2.25.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "Forge" in changelog


def test_v225_g2_stays_blocked_publish_stays_blocked() -> None:
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


def test_v225_handoff_must_not_be_recreated() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`HANDOFF.md` MUST NOT be recreated" in delta
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in root_protocol
    assert "HANDOFF.md" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()


def test_v225_keeps_continentie_evidence_and_every_guideline_law() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain" in delta
    assert "PROTOCOL.md is every-guideline law" in delta or "PROTOCOL.md is wet voor iedere richtlijn" in root_protocol
    assert "PROTOCOL.md is wet voor iedere richtlijn, niet Continentie-only" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in roadmap


def test_v225_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (MVP beslisboom document class with closed boom types `path` / `node` / `outcome`; closed Klasse set includes `beslisboom`; Klasse choice selects review path; boom freeze+locator; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family; console remains not a nurse tree player; no Forge code; no G2 PASS; `publish()` stays G2-BLOCKED)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.25.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v225_leaves_v216_through_v224_delta_files_untouched_except_v224_pointer() -> None:
    v216 = (ROOT / "docs" / "PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md").read_bytes()
    v217 = (ROOT / "docs" / "PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md").read_bytes()
    v218 = (ROOT / "docs" / "PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md").read_bytes()
    v219 = (ROOT / "docs" / "PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md").read_bytes()
    v220 = (ROOT / "docs" / "PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md").read_bytes()
    v221 = (ROOT / "docs" / "PROTOCOL_V2_21_CONTROLLED_USE_WAVES_DELTA.md").read_bytes()
    v222 = (ROOT / "docs" / "PROTOCOL_V2_22_WAVE_ORDER_C_D_BEFORE_B_DELTA.md").read_bytes()
    v223 = (ROOT / "docs" / "PROTOCOL_V2_23_CODE_SURFACE_SIMPLIFICATION_DELTA.md").read_bytes()
    v224 = (ROOT / "docs" / "PROTOCOL_V2_24_CONSOLE_RETRIEVAL_DEPLOY_SPLIT_DELTA.md").read_bytes()
    assert b"**Protocol delta version:** 2.16.0" in v216
    assert b"**Protocol delta version:** 2.17.0" in v217
    assert b"**Protocol delta version:** 2.18.0" in v218
    assert b"**Protocol delta version:** 2.19.0" in v219
    assert b"**Protocol delta version:** 2.20.0" in v220
    assert b"**Protocol delta version:** 2.21.0" in v221
    assert b"**Protocol delta version:** 2.22.0" in v222
    assert b"**Protocol delta version:** 2.23.0" in v223
    assert b"**Protocol delta version:** 2.24.0" in v224
    new_law = b"MVP beslisboom document class"
    for old in (v216, v217, v218, v219, v220, v221, v222, v223):
        assert new_law not in old
        assert b"UitkomstX_Y_titel" not in old
    assert b"Index/conflict pointer: Protocol v2.25.0" in v224
    assert new_law in DELTA.read_bytes()


def test_v225_does_not_reopen_serving_typeset_stamps_waves_g2() -> None:
    delta = _read(DELTA)
    assert "Do not reopen freeze/locator (v2.11), richtlijn-path serving types (v2.12), atomic objects/relations/four-eyes (v2.13), stamps on recommendation (v2.16), researcher surface (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished delete (v2.20), waves A–D / deploy split (v2.21–v2.24), or fail-closed G2 except as already required" in delta
    assert "The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED" in delta


def test_v225_owner_evidence_four_storyline_booms() -> None:
    delta = _read(DELTA)
    assert "Valrisico (tree 4)" in delta
    assert "Fractuurpreventie (tree 2)" in delta
    assert "Mantelzorg (tree 3)" in delta
    assert "Eenzaamheid (tree 1)" in delta
    assert "multifactor modules + scorelist" in delta
    assert "Adviseer/Overweeg" in delta
    assert "Bespreek-heavy" in delta
    assert "Verwijs / geen actie" in delta
    assert "/wp-json/beslisboom/v1/*" in delta
    assert "path-fused conditions" in delta
    assert "multi-bullet outcomes" in delta
    assert "Continentie, Depressie, Medicatietrouw" in delta


def test_v225_out_of_scope_matches_owner_lock() -> None:
    delta = _read(DELTA)
    assert "implementing ingest UI, extract, Storyline parser, or API scraper" in delta
    assert "G2 PASS" in delta
    assert "Protocol v2.14" in delta
    assert "LLM" in delta
    assert "nurse UI" in delta
    assert "recreating `HANDOFF.md`" in delta
    assert "adding numpy/sklearn" in delta
    assert "touching Azure deploy packaging" in delta
    assert "activating Product API boom serving" in delta


def test_v225_no_product_feature_code_in_this_pr() -> None:
    src_hits = []
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PROTOCOL_V2_25" in text or "object_type_path_node_outcome" in text:
            src_hits.append(path.name)
    assert src_hits == [], f"protocol-only PR must not add boom product code in src/: {src_hits}"
