from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_21_CONTROLLED_USE_WAVES_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_21_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v221_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.21.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_21_CONTROLLED_USE_WAVES_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-02"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v221_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.21.0" in delta
    assert "docs/PROTOCOL_V2_21_CONTROLLED_USE_WAVES_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.30.0") == 1
    assert "plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.20.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.19.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.18.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.17.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.16.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.21.0" in roadmap


def test_v221_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v221_maps_existing_law_and_does_not_rewrite_v216_v220() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "It MAPS, and does NOT rewrite, existing law" in delta
    assert "Protocol v2.16–v2.18 already forbid tiny objects, stamp-as-heading/object, truncated/trailing clauses, chrome objects, and identical `clean_text`" in delta
    assert "Protocol v2.19 is duty-queue" in delta
    assert "Protocol v2.20 unpublished-delete is already on `main` `ba3c85cec8e100e289e25e6a33fbf9440676c26e` and is NOT a fifth wave" in delta
    assert "MAPT bestaande wet, herschrijft die niet" in root_protocol
    assert "v2.20 unpublished-delete is GEEN vijfde golf" in root_protocol
    assert "MAPT bestaande wet, herschrijft die niet" in roadmap
    assert "GEEN vijfde golf" in roadmap


def test_v221_protocol_md_is_every_guideline_law_and_keeps_continentie_evidence() -> None:
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
    assert "stempels als Koppen, 2008 Inhoud-kaarten" in root_protocol
    assert "snap-ac59cf24f946088e-e402c4d3" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in roadmap


def test_v221_g2_readiness_and_pr82_stay_blocked() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "G2-readiness (PR #69) already pinned `azure-identity==1.25.3` / `azure-storage-blob==12.30.1`" in delta
    assert "G2 is still BLOCKED" in delta
    assert "`publish()` remains G2-BLOCKED" in delta
    assert "RBAC Storage Blob Data Contributor on `aidataservice/canonical-sources` for the `vvn-metis-console` managed identity is external" in delta
    assert "PR #82 (`ci: isolated test deploy + manual production`) is OPEN and MUST NOT be activated until the four faults are fixed AND an Azure test app exists" in delta
    assert "Do not claim G2 PASS in this protocol" in delta
    assert "G2-readiness (PR #69)" in root_protocol
    assert "PR #82 is OPEN en MUST NOT worden geactiveerd" in root_protocol
    assert "claimt geen G2 PASS" in root_protocol
    assert "PR #82 is OPEN" in roadmap
    assert "claimt geen G2 PASS" in roadmap


def test_v221_order_a_then_b_then_c_then_d_and_cloud_shell_off() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Order MUST be A then B then C then D" in delta
    assert "Cloud Shell / production ZIP stay off until wave A is on a controlled SHA" in delta
    assert "Owner paused Cloud Shell and locked a four-wave program" in delta
    assert "Priority: source integrity, clear knowledge objects, safe environment isolation, recoverability" in delta
    assert "volgorde MUST A daarna B daarna C daarna D" in root_protocol
    assert "Cloud Shell / production ZIP blijven uit tot golf A op een gecontroleerde SHA staat" in root_protocol
    assert "bronintegriteit, heldere kennisobjecten, veilige omgevingsscheiding, herstelbaarheid" in root_protocol
    assert "Cloud Shell / production ZIP blijven uit tot golf A op een gecontroleerde SHA staat" in roadmap
    assert "Volgorde A daarna B daarna C daarna D" in roadmap


def test_v221_wave_a_splitter_and_reject_function() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Implement a context-aware splitter plus a testable reject function" in delta
    assert "An inhoudelijk knowledge object MUST be one complete, independently readable meaning unit" in delta
    assert "It MUST have bronpassage plus locator to the freeze" in delta
    assert "It MUST NOT be only a number, label, kopwoord, nav, stamp, or sentence fragment" in delta
    assert "It MUST NOT duplicate identical `clean_text` from the same freeze" in delta
    assert "Real source headings MAY exist as `heading`, structure only, never advice, no recommendation stamp, batch-confirmable as structure" in delta
    assert "DOEN / OVERWEEG / NIET DOEN are not objects and not Koppen; they are a property of a full recommendation together with the advice sentence" in delta
    assert "attach trailing / dependent clauses to the previous meaningful sentence" in delta
    assert "attach a stamp to the immediately following advice sentence" in delta
    assert "filter chrome / nav / list numbers / loose labels / empty / too-short BEFORE object creation" in delta
    assert "prevent duplicate `clean_text` in the same snapshot" in delta
    assert "keep freeze bytes and locators exact (derived extract only)" in delta
    assert "not a standalone meaning" in delta
    assert "below a documented minimum meaning threshold" in delta
    assert "stamp / number / nav-only" in delta
    assert "grammatical continuation of the previous sentence" in delta
    assert "identical to an earlier object from the same freeze" in delta
    assert "short real definitions and official headings MUST NOT be dropped" in delta
    assert "MUST NOT treat “Inleiding” as chrome" in delta
    assert "Home / Tools / Richtlijnen / Meedenken are chrome" in delta
    assert "Inleiding as a real section title MAY remain `heading`" in delta
    assert "No infrastructure in wave A" in delta
    assert "context-bewuste splitter" in root_protocol
    assert "toetsbare reject-functie" in root_protocol
    assert "één complete, zelfstandig leesbare betekeniseenheid" in root_protocol
    assert "Inleiding is geen chrome" in root_protocol or "MUST NOT «Inleiding» als chrome behandelen" in root_protocol
    assert "Home/Tools/Richtlijnen/Meedenken zijn chrome" in root_protocol
    assert "geen infrastructuur in golf A" in root_protocol
    assert "context-bewuste splitter" in roadmap
    assert "toetsbare reject-functie" in roadmap
    assert "Inleiding is geen chrome" in roadmap or "MUST NOT «Inleiding» als chrome behandelen" in roadmap


def test_v221_wave_a_continentie_regression_fixtures() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "stamps plus advice sentence" in delta
    assert "Eventueel met hulp van de mantelzorger." in delta
    assert "list numbers" in delta
    assert "Home / Tools" in delta
    assert "duplicate samenvatting / module" in delta
    assert "short valid definitions" in delta
    assert "real headings at different levels" in delta
    assert "HTML repeated modules" in delta
    assert "PDF versus HTML difference" in delta
    assert "none of those fail patterns land as standalone inhoudelijk objects in the review duty queue" in delta
    assert "Continentie-regressiefixtures" in root_protocol
    assert "Eventueel met hulp van de mantelzorger." in root_protocol
    assert "Continentie-regressiefixtures" in roadmap
    assert "Eventueel met hulp van de mantelzorger." in roadmap


def test_v221_wave_b_g2_status_evidence() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "G2 status MUST NOT depend on a stale static JSON field" in delta
    assert "Blob container reachable" in delta
    assert "managed identity usable" in delta
    assert "required Blob role present or access actually proven" in delta
    assert "container matches the active environment" in delta
    assert "a source can be stored and read back byte-identical" in delta
    assert "Controlled SHA-256 smoke" in delta
    assert "timestamp, environment, container, SHA-256, and outcome" in delta
    assert "G2 PASS only after a successful controlled test; else BLOCKED" in delta
    assert "The publication gate MUST NOT open because an app-setting is present" in delta
    assert "G2-status MUST NOT van een stale static JSON-veld afhangen" in root_protocol
    assert "publicatiegate MUST NOT openen omdat een app-setting aanwezig is" in root_protocol
    assert "stale static JSON" in roadmap
    assert "publicatiegate MUST NOT openen omdat een app-setting aanwezig is" in roadmap


def test_v221_wave_c_pipeline_and_pr82_faults() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Finish PR #82. Do not activate until a test App Service exists" in delta
    assert "Invoke the packaging script via bash or make it executable" in delta
    assert "The Azure ZIP MUST build dependencies or the artifact MUST be fully deployable" in delta
    assert "git-archive-only is not enough" in delta
    assert "live Oryx-during-deploy caused HTTP_504 on B1" in delta
    assert "Storage account / container per environment via safe app settings; no secrets in Git" in delta
    assert "the test identity MAY only deploy to test; the production identity MAY only deploy to production" in delta
    assert "Production is manual: only a full SHA already on `main`" in delta
    assert "MUST NOT deploy runtime data from Git" in delta
    assert "MUST NOT overwrite `/home/data`" in delta
    assert "Merge to `main` MAY deploy only to test" in delta
    assert "create_azure_deploy_package.sh` invoked without bash and may not be executable" in delta
    assert "package is git archive HEAD only, no dependencies" in delta
    assert "workflows do not configure per-environment storage" in delta
    assert "one Entra app is not enough if it can deploy to both" in delta
    assert "MUST NOT create or activate a test App Service in this protocol PR" in delta
    assert "MUST NOT start Azure in waves A or B" in delta
    assert "HTTP_504 op B1" in root_protocol
    assert "git-archive-only is niet genoeg" in root_protocol
    assert "vier #82-fouten" in root_protocol or "vier bekende PR #82-fouten" in root_protocol
    assert "PR #82 afmaken" in roadmap
    assert "vier #82-fouten" in roadmap


def test_v221_wave_d_backup_recoverability() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Inventory of `/home/data/metis-console`" in delta
    assert "accounts / roles" in delta
    assert "document snapshots" in delta
    assert "review decisions and audit ledger" in delta
    assert "canonical objects" in delta
    assert "derived projections" in delta
    assert "export / backup procedure" in delta
    assert "controlled restore to a clean environment" in delta
    assert "integrity check after restore" in delta
    assert "a test proving a deployment does not delete existing runtime data" in delta
    assert "No large database migration" in delta
    assert "a managed database becomes required before multiple App Service instances or concurrent multi-reviewer writes" in delta
    assert "`/home/data/metis-console`" in root_protocol
    assert "geen grote databasemigratie" in root_protocol
    assert "migratiegrens" in root_protocol
    assert "backup/herstelbaarheid" in roadmap
    assert "`/home/data/metis-console`" in roadmap


def test_v221_next_implementation_is_wave_a_only() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Where this delta and Protocol v2.20 conflict on which implementation is next, this delta governs" in delta
    assert "The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/extract for exactly wave A only" in delta
    assert "Then B, then C, then D" in delta
    assert "Not Azure ZIP of v2.20 until A is on a controlled SHA unless the owner re-opens Cloud Shell" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "golf A only" in root_protocol
    assert "Niet Azure ZIP van v2.20 tot A op een gecontroleerde SHA staat" in root_protocol
    assert "golf A only" in roadmap
    assert "Niet Azure ZIP van v2.20 tot A op een gecontroleerde SHA staat" in roadmap
    assert "Protocol v2.21.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "v2.14 is not this and is not next" in changelog
    assert "Next implementation is wave A only" in changelog


def test_v221_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (knowledge-object bounds; G2 status MUST be live evidence not a stale static JSON field; isolated test/release; recoverability)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.21.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v221_leaves_v216_through_v220_delta_files_untouched() -> None:
    v216 = (ROOT / "docs" / "PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md").read_bytes()
    v217 = (ROOT / "docs" / "PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md").read_bytes()
    v218 = (ROOT / "docs" / "PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md").read_bytes()
    v219 = (ROOT / "docs" / "PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md").read_bytes()
    v220 = (ROOT / "docs" / "PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md").read_bytes()
    assert b"**Protocol delta version:** 2.16.0" in v216
    assert b"**Protocol delta version:** 2.17.0" in v217
    assert b"**Protocol delta version:** 2.18.0" in v218
    assert b"**Protocol delta version:** 2.19.0" in v219
    assert b"**Protocol delta version:** 2.20.0" in v220
    new_law = b"four-wave program for controlled use with real guideline sources"
    assert new_law not in v216
    assert new_law not in v217
    assert new_law not in v218
    assert new_law not in v219
    assert new_law not in v220
    assert new_law in DELTA.read_bytes()


def test_v221_does_not_reopen_serving_typeset_stamps_chrome_duty() -> None:
    delta = _read(DELTA)
    assert "Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, or unpublished-snapshot delete except as already required" in delta
    assert "The v2.12 closed serving typeset remains UNCHANGED" in delta
    assert "This delta’s bar is a four-wave controlled-use program" in delta


def test_v221_out_of_scope_matches_owner_lock() -> None:
    delta = _read(DELTA)
    assert "implementing console/extract/Azure" in delta
    assert "merging" in delta
    assert "G2 PASS" in delta
    assert "Protocol v2.14" in delta
    assert "LLM" in delta
    assert "nurse UI" in delta
    assert "SSH wipe" in delta
    assert "hiding fragments without extract" in delta
    assert "treating Metis / Implementation engineer / Auditor as GD-03 reviewers" in delta
