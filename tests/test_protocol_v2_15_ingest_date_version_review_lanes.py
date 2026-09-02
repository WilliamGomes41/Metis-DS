from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "docs" / "PROTOCOL_V2_15_INGEST_DATE_VERSION_REVIEW_LANES_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_15_approval.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v215_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.15.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_15_INGEST_DATE_VERSION_REVIEW_LANES_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-01"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v215_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.15.0" in delta
    assert "docs/PROTOCOL_V2_15_INGEST_DATE_VERSION_REVIEW_LANES_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.21.0") == 1
    assert "plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "Protocol v2.15.0" in roadmap


def test_v215_does_not_redesign_the_four_layers_or_write_v214() -> None:
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


def test_v215_ingest_date_is_calendar_iso_required() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "The ingest date field MUST be a calendar date picker, not a free-text box" in delta
    assert "Europe/Amsterdam calendar order `DD-MM-YYYY`" in delta
    assert "MUST persist the same day as ISO `YYYY-MM-DD` (no time, no timezone)" in delta
    assert "MUST be the date printed on the freeze (colofon / publicatiedatum)" in delta
    assert "MUST NOT default to today" in delta
    assert "MUST NOT be the ingest-click timestamp" in delta
    assert "Empty MUST NOT be accepted at ingest. No date = no herleidbare bron" in delta
    assert "Display locale MUST NOT leak into stored bytes" in delta
    assert "`01-02-2026` on screen is 1 February 2026, stored `2026-02-01`" in delta
    assert "kalenderdatumkiezer" in root_protocol
    assert "YYYY-MM-DD" in root_protocol
    assert "colofon / publicatiedatum" in root_protocol


def test_v215_ingest_version_is_dotted_integer_required() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "The version field MUST NOT be free text" in delta
    assert r"`^[0-9]+(\.[0-9]+)*$`" in delta
    assert "`1`, `1.0`, `2.13`, `1.2.3`" in delta
    assert "jaartal-as-version (`2024`)" in delta
    assert "Empty MUST NOT be accepted at ingest." in delta
    assert "The machine validates; the researcher fills" in delta
    assert "dotted-integer" in root_protocol or "niet-negatieve gehele getallen" in root_protocol


def test_v215_date_and_version_are_freeze_metadata_not_object_version_or_v214() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "They are not knowledge-object `object_version` and not Protocol v2.14 `valid_from` / `valid_until`" in delta
    assert "Operators MUST NOT fuse them into recommendation condition fields" in delta
    assert "Filling them is not publication" in delta
    assert "niet knowledge-object `object_version`" in root_protocol
    assert "niet v2.14 `valid_from`/`valid_until`" in root_protocol


def test_v215_heading_proposal_is_review_lane_prerequisite() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Extract MUST propose `heading` for real source headings / TOC / structural crumbs so they do not all land as `unclassified`" in delta
    assert "this delta makes that proposal a review-lane prerequisite" in delta
    assert "Everything that is not a real heading MUST still start `unclassified`" in delta
    assert "Extract MUST NOT auto-promote ordinary text to `recommendation`" in delta
    assert "heading" in root_protocol
    assert "unclassified" in root_protocol
    assert "heading-voorstel" in roadmap


def test_v215_review_list_must_show_source_snippet_not_type_name() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "The review list MUST NOT use the type name (`unclassified`) as the row title" in delta
    assert "Each row MUST show a source-passage snippet (the freeze text of that object)" in delta
    assert "The numeric object id MAY remain secondary" in delta
    assert "bronpassage-snippet" in root_protocol
    assert "MUST NOT de typenaam" in root_protocol
    assert "bronpassage-snippet" in roadmap


def test_v215_fast_lane_batch_confirm_and_slow_lane_one_object() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "There MUST NOT be a separate researcher control “zwaar/licht” or “snel/langzaam”" in delta
    assert "Fast lane MUST support batch-confirm of proposed headings as structure, not advice, so a researcher does not open 4000 cards" in delta
    assert "Slow lane stays one-object (type + relations + high-risk four-eyes)" in delta
    assert "batch-bevestiging" in root_protocol
    assert "batch-bevestiging" in roadmap


def test_v215_four_thousand_unclassified_is_a_fail_and_does_not_resplit() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Four thousand unclassified cards on one richtlijn is a fail of this delta's review surface, not a workload to accept" in delta
    assert "MUST NOT silently re-split existing ingested objects in this protocol" in delta
    assert "Identity of already-hashed objects stays" in delta
    assert "this protocol MUST NOT re-extract existing Continentie bytes" in delta
    assert "MUST NOT rewrite Protocol v2.13 split rules" in delta
    assert "MUST NOT add new object types for page/paragraph" in delta
    assert "4000+" in delta or "4000+" in delta
    assert "vierduizend unclassified-kaarten" in root_protocol
    assert "vierduizend unclassified-kaarten" in roadmap


def test_v215_four_eyes_and_serving_law_unchanged() -> None:
    delta = _read(DELTA)
    assert "High-risk four-eyes law is unchanged" in delta
    assert "Fast-lane heading accept MUST NOT bypass four-eyes" in delta
    assert "The machine MUST NOT decide that something is “light enough to serve”" in delta
    assert "This delta does not make G2 PASS and does not implement `publish()`" in delta
    assert "Machine classification remains a proposal, never published truth" in delta


def test_v215_is_c3_spanning_ingest_provenance_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning ingest provenance validation (source date / source version / type-based review lanes)" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Protocol v2.15.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning ingest-provenance-validatie" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v215_records_console_wave_then_g2_and_does_not_implement_product_code() -> None:
    delta = _read(DELTA)
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Where this delta and the 2026-08-29 lock conflict on which implementation is next, this delta governs" in delta
    assert "ingest date calendar + ISO store + required" in delta
    assert "ingest version dotted-integer validation + required" in delta
    assert "THEN G2/Azure remains the publication blocker" in delta
    assert "Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`" in delta
    assert "The G2 locator remains the publication blocker" in delta
    assert "Protocol v2.15.0" in changelog
    assert "does not implement console or kernel" in changelog
    assert "v2.14 is not this and is not next" in changelog
    assert "ingest-datumkalender" in roadmap
    assert "heading-voorstel" in roadmap
    assert "bronpassage-snippet" in roadmap
    assert "batch-bevestiging" in roadmap
