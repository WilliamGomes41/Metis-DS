from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_13_ATOMIC_OBJECT_SEMANTICS_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_13_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v213_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.13.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_13_ATOMIC_OBJECT_SEMANTICS_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "8cfe9dc37a8f3f0bf3548a40abff41acb4fb39ce"
    assert manifest["approval_date"] == "2026-08-28"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v213_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.13.0" in delta
    assert "docs/PROTOCOL_V2_13_ATOMIC_OBJECT_SEMANTICS_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.25.0") == 1
    assert "plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.12.0" not in root_protocol
    assert "Protocol v2.13.0" in roadmap


def test_v213_does_not_redesign_the_four_layers_or_invent_a_fifth() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "This delta MUST NOT invent a fifth layer" in delta
    assert "MUST NOT collapse those four" in delta
    assert "source/evidence → canonical knowledge → governance → product" in delta
    assert "vier lagen" in root_protocol


def test_v213_architecture_principle_is_law() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "One knowledge object MUST be one confirmable meaning" in delta
    assert "Context MUST live in reviewed relations, not in a blob" in delta
    assert "The canonical store MUST be the only source of truth" in delta
    assert "Retrieval index, embeddings and projections MUST be derived and disposable" in delta
    assert "MUST NOT reverse that direction" in delta
    assert "één bevestigbare betekeniseenheid" in root_protocol
    assert "canonieke store" in root_protocol
    assert "wegwerpbaar" in root_protocol
    assert "canonieke store" in roadmap


def test_v213_atomic_objects_forbid_token_budget_identity_and_fusion() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    extraction = _read(ROOT / "docs" / "extraction_rules_v0.1.md")
    assert "Extraction MUST split at meaning boundaries, not token budgets" in delta
    assert "Token-budget chunking" in delta
    assert "MUST NOT define object identity" in delta
    assert "300–700 / 1000-token" in delta
    assert "A recommendation MUST NOT contain its condition, exception, negation, or qualifier as undifferentiated text" in delta
    assert "Fusion of condition into recommendation is the default FORBIDDEN pattern" in delta
    assert "MUST NOT split when splitting would break a single grammatical claim" in delta
    assert "`parent`/`child` is structural (heading tree)" in delta
    assert "MUST NOT be used to dump siblings into one blob" in delta
    assert "A new object version is required when bytes, extract, confirmed type, or confirmed relations change" in delta
    assert "Metadata-only changes MUST NOT silently reuse a reviewed semantic version" in delta
    assert "tokenbudget-chunking MUST NOT objectidentiteit definiëren" in root_protocol
    assert "fusion van condition in recommendation is het verboden defaultpatroon" in root_protocol
    assert "Protocol v2.13 supersedes this file" in extraction
    assert "MUST NOT be MVP serving types" in extraction
    assert "MUST NOT define object identity" in extraction
    assert "preserve clinical wording" in extraction
    assert "keep `raw_text` beside `clean_text`" in extraction
    assert "do not invent headings" in extraction
    assert "do not change numeric thresholds" in extraction


def test_v213_closed_serving_typeset_is_unchanged_and_historical_types_must_not_serve() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`" in delta
    assert "The v2.12 closed serving typeset is UNCHANGED" in delta
    assert "Operators MUST NOT invent types" in delta
    assert "Adding a type is a new protocol change" in delta
    assert "`score_rule`" in delta
    assert "`decision`" in delta
    assert "`action`" in delta
    assert "`table`" in delta
    assert "`background`" in delta
    assert "`patient_information`" in delta
    assert "are not a licence to serve those types" in delta
    assert "There is NO `score_rule` serving type in MVP" in delta
    assert "Historische types" in root_protocol
    assert "MUST NOT MVP-servingtypes zijn" in root_protocol


def test_v213_per_type_classification_rules_and_human_judgement() -> None:
    delta = _read(DELTA)
    assert "Machine classification is a proposal, never truth" in delta
    assert "Unconfirmed proposals MUST NOT be published type and MUST NOT be `supported`" in delta
    assert "MUST NOT answer as advice, definition or explanation" in delta
    assert "MAY be `supported` for a definition question. MUST NOT receive advice-weight" in delta
    assert "MAY be `supported` for an explanation question. MUST NOT receive advice-weight" in delta
    assert "MAY bound advice only via confirmed `applies_if`. MUST NOT receive advice-weight" in delta
    assert "MAY bound advice only via confirmed `except_if`. MUST NOT receive advice-weight" in delta
    assert "ALWAYS high-risk (four-eyes)" in delta
    assert "ONLY type that MAY return as action advice" in delta
    assert "MUST NOT be served as action advice" in delta
    assert "tables/figures (do not auto-type; leave unclassified)" in delta
    assert "any score/threshold/dose/age boundary" in delta


def test_v213_open_original_is_review_law_without_a_new_locator_scheme() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "From every knowledge object the reviewer MUST be able to open the exact source passage" in delta
    assert "Type confirmation without that flow is not acceptable" in delta
    assert "this delta MUST NOT invent a locator scheme" in delta
    assert "exacte bronpassage" in root_protocol
    assert "open-origineel" in roadmap


def test_v213_closed_relations_are_serving_law() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    for name in (
        "`applies_if`",
        "`except_if`",
        "`defines`",
        "`explains`",
        "`supported_by`",
        "`supersedes`",
        "`parent` / `child`",
    ):
        assert name in delta
    assert "operators MUST NOT invent relation types" in delta
    assert "Schema v1.2 names" in delta
    assert "are not the serving law" in delta
    assert "Unconfirmed relations MUST NOT be treated as binding" in delta
    assert "A changed confirmed relation set MUST invalidate prior publish authorization" in delta
    assert "a published recommendation MUST be served together with its published `applies_if` / `except_if` targets" in delta
    assert "Serving the recommendation without those bounds is a protocol failure" in delta
    assert "Operators MUST NOT fuse objects to preserve context" in delta
    assert "they MUST NOT give advice-weight" in delta
    assert "applies_if" in root_protocol
    assert "except_if" in root_protocol
    assert "supported_by" in root_protocol


def test_v213_high_risk_four_eyes_is_authorization() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "uploader MUST NOT be the only required reviewer" in delta
    assert "AI / Grok Bot / Metis / Implementation engineer / Auditor MUST NOT count as required reviewers" in delta
    assert "confirmed type is `exception`" in delta
    assert "`risk_level` is high" in delta
    assert "`age_boundary`" in delta
    assert "`dosage`" in delta
    assert "`contraindication`" in delta
    assert "Envelope `review_passes` still MUST NOT authorize publish" in delta
    assert "it is an additional required reviewer on that tuple" in delta
    assert "G2 still blocks actual `publish()`" in delta
    assert "four-eyes" in root_protocol


def test_v213_is_c3_spanning_c5_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 (retrieve-safety / answerability / knowledge model) spanning C5 (high-risk four-eyes review/publish authorization)" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "PR #29" in delta
    assert "Protocol v2.13.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning C5 four-eyes-autorisatie" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v213_records_kernel_then_g2_and_does_not_write_v214() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Where this delta and Protocol v2.12 §10 conflict on which implementation is next, this delta governs" in delta
    assert "atomic split" in delta
    assert "closed relations" in delta
    assert "per-type confirm" in delta
    assert "high-risk four-eyes" in delta
    assert "THEN G2/Azure" in delta
    assert "Do not start Azure in this change" in delta
    assert "This delta MUST NOT write Protocol v2.14" in delta
    assert "PROTOCOL → tests → code later" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "Vastgestelde architectuurclusters" in roadmap
    assert "LOCKED nu" in roadmap
    assert "LOCKED als het volgende protocol (v2.14), niet deze PR" in roadmap
    assert "MUST NOT Protocol v2.14 worden geschreven" in roadmap
    assert "Protocol v2.13.0" in changelog
    assert "does not implement extract, relations, open-original, schema or publish()" in changelog
    assert "v2.14 is not next" in changelog


def test_v213_roadmap_locks_seven_clusters_and_maps_ten_epics() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "de zeven clusters zijn de lock en de sequentie" in roadmap
    assert "De tien architectuurepics zijn de kaart" in roadmap
    assert "Semantisch kennismodel (Protocol v2.13, deze PR)" in roadmap
    assert "Open-origineel" in roadmap
    assert "Levenscyclus + geldigheid in tijd" in roadmap
    assert "Release, atomaire publicatie, rollback, schema-migratie" in roadmap
    assert "Tabellen/figuren" in roadmap
    assert "Kwaliteitsevaluatie" in roadmap
    assert "Security, IAM, secrets, omgevingsscheiding" in roadmap
    assert "Epic 10 (Immutable storage / G2)" in roadmap
    assert "blijft de publicatieblocker" in roadmap
    assert "False support is een Fase-3-meetlat, geen stille extra gate in Protocol v2.13" in roadmap
    assert "MUST NOT vannacht tot protocol worden gemaakt" in roadmap


def test_v213_does_not_implement_product_code_or_skip_g2() -> None:
    delta = _read(DELTA)
    assert "It does not:" in delta
    assert "implement extract, relations, console “open original”, schema, Product API, or `publish()`" in delta
    assert "convert G2 to PASS" in delta
    assert "skip durable immutable storage" in delta
    assert "staff named reviewers" in delta
    assert "write Protocol v2.14" in delta
    assert "invent a locator scheme" in delta
    assert "silently add a new quality metric as a protocol gate" in delta
