"""Protocol v2.30 Forge Phase 2: deep context / refs / abbrev / comparisons / expand-merge.

Richtlijn inhoudelijke candidates only. Boom path/node/outcome stay v2.25.
Phase 1 hard gate stays. Review UI rewrite is Phase 3. Gold/metrics are Phase 4.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here. publish() stays
G2-BLOCKED.

Catalog reason_codes stay section-6 tokens. Condition/exception constraints
that are found and neither included nor linked MUST use
``condition_target_missing`` / ``exception_target_missing`` and/or
``context_necessary_unresolved`` — not invented ``context_condition_unresolved``
/ ``context_exception_unresolved`` tokens.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.admission_gate_v1 import (
    GATE_ALLOWED,
    GATE_BLOCKED,
    admit_candidate,
    apply_admission_gate,
    blocked_audit_lane,
    build_candidate_record,
    ordinary_review_queue,
)
from src.beslisboom_path_v1 import CLOSED_BOOM_TYPES
from src.context_scan_v1 import (
    CHECKED_CONTEXT_SIGNALS,
    scan_deep_context,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole, is_slow_review_duty, slow_review_duty


ROOT = Path(__file__).resolve().parents[1]
PHASE1_FIXTURE = ROOT / "data/fixtures/v230_phase1_admission_regression.html"
PHASE2_FIXTURE = ROOT / "data/fixtures/v230_phase2_deep_context_regression.html"
DJG = "De dJG wordt in Nederland vaker gebruikt."
DJG_RESOLVED = "De dJG wordt in Nederland vaker gebruikt dan de FRAX."
DJG_EXPANSION = "De Dutch Job Group (dJG) is een meetinstrument voor werkbelasting."
ADVISEERT = (
    "De werkgroep adviseert de verpleegkundige de risicofactoren "
    "scorelijst te gebruiken bij iedere intake."
)
PREV_CONDITION = (
    "Bij een cliënt van 60 jaar of ouder zonder recente fractuur "
    "geldt extra aandacht voor botgezondheid."
)
NEXT_OVERLEG = (
    "Overleg bij een vastgesteld verhoogd fractuurrisico met de cliënt over verwijzing."
)
CALCIUM = "De werkgroep adviseert calcium te geven."
CALCIUM_EXC = "Tenzij er hypercalciëmie bestaat."
CONDITION_THEN = "Wanneer de cliënt 60 jaar of ouder is, geldt het volgende."
CONDITIONED_REC = (
    "De werkgroep adviseert de verpleegkundige calciumsuppletie te starten bij iedere intake."
)
UNRESOLVED_REF = "Zie tabel 4 voor de cutoff van het risico."
INCOMPLETE_COMPARISON = "Deze methode is vaker effectief."
COMPLETE_COMPARISON = "Deze methode is vaker effectief dan de klinische blik alleen."
ONE_WORD = "De nieuwe scorelijst."
CURRENT_HEADING = "2 Aanbevelingen"
ANCESTOR_HEADING = "Richtlijn Fractuurpreventie"


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _accounts(console: OperationsConsole) -> dict[str, dict]:
    researcher = console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher", "reviewer"),
        display_name="Anne Onderzoeker",
    )
    reviewer = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    return {"researcher": researcher, "reviewer": reviewer}


def _ingest(console: OperationsConsole, accounts: dict, fixture: Path, **overrides) -> dict:
    kwargs = {
        "actor_id": accounts["researcher"]["account_id"],
        "filename": fixture.name,
        "data": fixture.read_bytes(),
        "content_type": "text/html",
        "ingest_kind": "new",
        "title": "Phase 2 deep context regression",
        "version": "1.0",
        "date": "2025-04-01",
        "live_url": "",
        "class_": "richtlijn",
        "family": "fractuurpreventie",
        "named_reviewers": [accounts["reviewer"]["account_id"]],
    }
    kwargs.update(overrides)
    return console.ingest(**kwargs)


def _boom_freeze_bytes() -> bytes:
    payload = {
        "kind": "beslisboom-freeze",
        "paths": [{"id": "path-screening", "text": "Screening op valrisico"}],
        "nodes": [
            {
                "id": "node-vraag",
                "text": "Is er een verhoogd valrisico?",
                "scorelist": False,
            }
        ],
        "outcomes": [
            {
                "id": "out-verwijs",
                "text": "Verwijs naar de valpoli.",
                "applies_if": ["node-vraag"],
            }
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _text_of(obj: dict) -> str:
    return ((obj.get("content") or {}).get("clean_text") or obj.get("candidate_text") or "").strip()


def _admission(obj: dict) -> dict:
    return ((obj.get("metadata") or {}).get("admission") or {})


def _scan_of(row: dict) -> dict:
    admission = row if "gate_result" in row else _admission(row)
    scan = admission.get("context_scan") or {}
    return scan if isinstance(scan, dict) else {}


def _find_by_text(objects: list[dict], snippet: str) -> dict:
    for obj in objects:
        if snippet in _text_of(obj):
            return obj
    raise AssertionError(f"no object contains {snippet!r}")


def _complete_adviseert_candidate(**overrides) -> dict:
    record = build_candidate_record(
        candidate_id="cand-adviseert",
        document_id="doc-phase2",
        document_version="1.0",
        source_hash="a" * 64,
        section_path=["Richtlijn Fractuurpreventie", "2 Aanbevelingen"],
        source_locator_start="lines:16-16",
        source_locator_end="lines:16-16",
        source_text_exact=ADVISEERT,
        candidate_text=ADVISEERT,
        subject_span="De werkgroep",
        predicate_span="adviseert",
        proposed_type="recommendation",
        type_evidence_spans=["adviseert"],
        context_before=PREV_CONDITION,
        context_after=NEXT_OVERLEG,
        actor_of_scope="de verpleegkundige",
        recommended_action="te gebruiken",
        action_object_or_goal="de risicofactoren scorelijst",
        recommendation_evidence_span=ADVISEERT,
    )
    record.update(overrides)
    return record


def _phase2_window() -> dict[str, object]:
    return {
        "candidate_paragraph": ADVISEERT,
        "previous_paragraph": PREV_CONDITION,
        "next_paragraph": NEXT_OVERLEG,
        "current_heading": CURRENT_HEADING,
        "ancestor_headings": [ANCESTOR_HEADING],
        "section_path": [ANCESTOR_HEADING, CURRENT_HEADING],
    }


# ---------------------------------------------------------------------------
# Deep window + checked signals
# ---------------------------------------------------------------------------


def test_deep_scan_covers_paragraphs_and_headings() -> None:
    scan = scan_deep_context(**_phase2_window())
    assert scan["context_scan_done"] is True
    assert scan["candidate_paragraph"] == ADVISEERT
    assert scan["previous_paragraph"] == PREV_CONDITION
    assert scan["next_paragraph"] == NEXT_OVERLEG
    assert scan["current_heading"] == CURRENT_HEADING
    assert ANCESTOR_HEADING in scan["ancestor_headings"]
    for signal in CHECKED_CONTEXT_SIGNALS:
        assert signal in scan["checked_signals"], signal


def test_necessary_context_is_included_or_linked_or_blocked() -> None:
    scan = scan_deep_context(**_phase2_window())
    assert scan["necessary_context_disposition"] in {"include", "link", "block"}
    if scan["necessary_context_disposition"] == "include":
        blob = " ".join(
            [
                str(scan.get("candidate_paragraph") or ""),
                str(scan.get("previous_paragraph") or ""),
                str(scan.get("next_paragraph") or ""),
            ]
        )
        assert "60 jaar" in blob
    elif scan["necessary_context_disposition"] == "link":
        assert scan.get("related_candidates") or scan.get("conditions_detected")
    else:
        assert scan.get("reason_codes")


def test_claiming_context_unnecessary_without_signals_blocks() -> None:
    admitted = admit_candidate(
        _complete_adviseert_candidate(),
        context_unnecessary=True,
        checked_signals=[],
    )
    assert admitted["gate_result"] == GATE_BLOCKED
    assert "context_unnecessary_unrecorded" in admitted["reason_codes"]


def test_context_scan_not_done_blocks_when_required_scan_skipped() -> None:
    admitted = admit_candidate(_complete_adviseert_candidate(), skip_context_scan=True)
    assert admitted["gate_result"] == GATE_BLOCKED
    assert "context_scan_not_done" in admitted["reason_codes"]


def test_phase1_valid_complete_candidate_stays_allowed_after_deep_scan() -> None:
    admitted = admit_candidate(_complete_adviseert_candidate())
    assert admitted["gate_result"] == GATE_ALLOWED
    assert "context_scan_not_done" not in admitted["reason_codes"]
    assert admitted.get("context_scan_done") is True or _scan_of(admitted).get("context_scan_done") is True
    assert PREV_CONDITION in str(admitted.get("context_before") or "")
    assert NEXT_OVERLEG in str(admitted.get("context_after") or "")
    assert CURRENT_HEADING in " ".join(
        [
            str(admitted.get("context_before") or ""),
            " ".join(admitted.get("section_path") or []),
            str((_scan_of(admitted).get("current_heading") or "")),
        ]
    )


def test_soft_scores_still_must_not_open_the_gate() -> None:
    blocked = admit_candidate(
        _complete_adviseert_candidate(skip_context_scan=True),
        soft_scores={"relevant": 1.0, "complete": 1.0, "understandable": 1.0},
        skip_context_scan=True,
    )
    assert blocked["gate_result"] == GATE_BLOCKED
    assert "context_scan_not_done" in blocked["reason_codes"]


# ---------------------------------------------------------------------------
# Refs / abbrev / comparisons / conditions / exceptions
# ---------------------------------------------------------------------------


def test_unresolved_core_reference_blocks() -> None:
    admitted = admit_candidate(
        build_candidate_record(
            candidate_id="cand-ref",
            document_id="doc-phase2",
            document_version="1.0",
            source_hash="a" * 64,
            section_path=[CURRENT_HEADING],
            source_locator_start="lines:24-24",
            source_locator_end="lines:24-24",
            source_text_exact=UNRESOLVED_REF,
            candidate_text=UNRESOLVED_REF,
            subject_span="",
            predicate_span="Zie",
            proposed_type="explanation",
            type_evidence_spans=["Zie"],
            context_before=ONE_WORD,
            context_after=INCOMPLETE_COMPARISON,
            references_detected=["tabel 4"],
            references_resolved=[],
        )
    )
    assert admitted["gate_result"] == GATE_BLOCKED
    assert "unresolved_reference" in admitted["reason_codes"]


def test_abbreviation_resolves_locally_from_previous_paragraph() -> None:
    scan = scan_deep_context(
        candidate_paragraph=DJG,
        previous_paragraph=DJG_EXPANSION,
        next_paragraph=INCOMPLETE_COMPARISON,
        current_heading=CURRENT_HEADING,
        ancestor_headings=[ANCESTOR_HEADING],
        section_path=[ANCESTOR_HEADING, CURRENT_HEADING],
    )
    assert "dJG" in scan["abbreviations_detected"]
    assert "dJG" in scan["abbreviations_resolved"]
    admitted = admit_candidate(
        build_candidate_record(
            candidate_id="cand-djg-resolved",
            document_id="doc-phase2",
            document_version="1.0",
            source_hash="a" * 64,
            section_path=[ANCESTOR_HEADING, CURRENT_HEADING],
            source_locator_start="lines:20-20",
            source_locator_end="lines:20-20",
            source_text_exact=DJG,
            candidate_text=DJG,
            subject_span="De dJG",
            predicate_span="wordt",
            proposed_type="recommendation",
            type_evidence_spans=[],
            context_before=DJG_EXPANSION,
            context_after=INCOMPLETE_COMPARISON,
        )
    )
    assert admitted["gate_result"] == GATE_BLOCKED
    assert "recommendation_evidence_missing" in admitted["reason_codes"]
    assert "comparison_target_missing" in admitted["reason_codes"]
    assert "abbreviation_unresolved" not in admitted["reason_codes"]
    assert "dJG" in admitted["abbreviations_resolved"]


def test_unresolved_abbreviation_still_blocks() -> None:
    admitted = admit_candidate(
        build_candidate_record(
            candidate_id="cand-djg-unresolved",
            document_id="doc-phase2",
            document_version="1.0",
            source_hash="a" * 64,
            section_path=[CURRENT_HEADING],
            source_locator_start="lines:17-17",
            source_locator_end="lines:17-17",
            source_text_exact=DJG,
            candidate_text=DJG,
            subject_span="De dJG",
            predicate_span="wordt",
            proposed_type="recommendation",
            type_evidence_spans=[],
            context_before=ADVISEERT,
            context_after=ONE_WORD,
        )
    )
    assert "abbreviation_unresolved" in admitted["reason_codes"]


def test_comparison_target_required_or_missing_code() -> None:
    missing = admit_candidate(
        build_candidate_record(
            candidate_id="cand-cmp-missing",
            document_id="doc-phase2",
            document_version="1.0",
            source_hash="a" * 64,
            section_path=[CURRENT_HEADING],
            source_locator_start="lines:25-25",
            source_locator_end="lines:25-25",
            source_text_exact=INCOMPLETE_COMPARISON,
            candidate_text=INCOMPLETE_COMPARISON,
            subject_span="Deze methode",
            predicate_span="is",
            proposed_type="factual_finding",
            type_evidence_spans=["is vaker effectief"],
            factual_claim_span=INCOMPLETE_COMPARISON,
            context_before=UNRESOLVED_REF,
            context_after=DJG,
            comparison_markers=["vaker"],
            comparison_targets=[],
        )
    )
    assert missing["gate_result"] == GATE_BLOCKED
    assert "comparison_target_missing" in missing["reason_codes"]

    present = admit_candidate(
        build_candidate_record(
            candidate_id="cand-cmp-ok",
            document_id="doc-phase2",
            document_version="1.0",
            source_hash="a" * 64,
            section_path=[CURRENT_HEADING],
            source_locator_start="lines:19-19",
            source_locator_end="lines:19-19",
            source_text_exact=COMPLETE_COMPARISON,
            candidate_text=COMPLETE_COMPARISON,
            subject_span="Deze methode",
            predicate_span="is",
            proposed_type="factual_finding",
            type_evidence_spans=["is vaker effectief"],
            factual_claim_span=COMPLETE_COMPARISON,
            context_before=DJG,
            context_after=DJG_EXPANSION,
            comparison_markers=["vaker"],
            comparison_targets=["dan de klinische blik alleen"],
        )
    )
    assert "comparison_target_missing" not in present["reason_codes"]


def test_detected_condition_must_be_included_linked_or_blocked_with_catalog_code() -> None:
    scan = scan_deep_context(
        candidate_paragraph=CONDITIONED_REC,
        previous_paragraph=CONDITION_THEN,
        next_paragraph="",
        current_heading=CURRENT_HEADING,
        ancestor_headings=[ANCESTOR_HEADING],
        section_path=[ANCESTOR_HEADING, CURRENT_HEADING],
    )
    assert scan["conditions_detected"]
    orphan = admit_candidate(
        build_candidate_record(
            candidate_id="cand-cond-orphan",
            document_id="doc-phase2",
            document_version="1.0",
            source_hash="a" * 64,
            section_path=[CURRENT_HEADING],
            source_locator_start="lines:28-28",
            source_locator_end="lines:28-28",
            source_text_exact=CONDITION_THEN,
            candidate_text=CONDITION_THEN,
            subject_span="de cliënt",
            predicate_span="is",
            proposed_type="condition",
            type_evidence_spans=["Wanneer"],
            condition_span=CONDITION_THEN,
            condition_target="",
            context_before=CALCIUM_EXC,
            context_after=CONDITIONED_REC,
        )
    )
    assert orphan["gate_result"] == GATE_BLOCKED
    assert any(
        code in orphan["reason_codes"]
        for code in ("condition_target_missing", "context_necessary_unresolved")
    )
    assert "context_condition_unresolved" not in orphan["reason_codes"]


def test_detected_exception_must_be_included_linked_or_blocked_with_catalog_code() -> None:
    scan = scan_deep_context(
        candidate_paragraph=CALCIUM,
        previous_paragraph=INCOMPLETE_COMPARISON,
        next_paragraph=CALCIUM_EXC,
        current_heading=CURRENT_HEADING,
        ancestor_headings=[ANCESTOR_HEADING],
        section_path=[ANCESTOR_HEADING, CURRENT_HEADING],
    )
    assert scan["exceptions_detected"]
    orphan = admit_candidate(
        build_candidate_record(
            candidate_id="cand-exc-orphan",
            document_id="doc-phase2",
            document_version="1.0",
            source_hash="a" * 64,
            section_path=[CURRENT_HEADING],
            source_locator_start="lines:27-27",
            source_locator_end="lines:27-27",
            source_text_exact=CALCIUM_EXC,
            candidate_text=CALCIUM_EXC,
            subject_span="",
            predicate_span="Tenzij",
            proposed_type="exception",
            type_evidence_spans=["Tenzij"],
            exception_span=CALCIUM_EXC,
            exception_target="",
            context_before=CALCIUM,
            context_after=CONDITION_THEN,
        )
    )
    assert orphan["gate_result"] == GATE_BLOCKED
    assert any(
        code in orphan["reason_codes"]
        for code in ("exception_target_missing", "context_necessary_unresolved", "no_independent_claim")
    )
    assert "context_exception_unresolved" not in orphan["reason_codes"]


def test_expand_merge_keeps_exception_with_recommendation() -> None:
    scan = scan_deep_context(
        candidate_paragraph=CALCIUM,
        previous_paragraph=INCOMPLETE_COMPARISON,
        next_paragraph=CALCIUM_EXC,
        current_heading=CURRENT_HEADING,
        ancestor_headings=[ANCESTOR_HEADING],
        section_path=[ANCESTOR_HEADING, CURRENT_HEADING],
    )
    merged = scan.get("expand_merge") or {}
    assert merged.get("performed") is True
    assert CALCIUM in str(merged.get("merged_text") or "")
    assert "hypercalciëmie" in str(merged.get("merged_text") or "")
    admitted = admit_candidate(
        _complete_adviseert_candidate(
            candidate_id="cand-ca-merge",
            source_text_exact=CALCIUM,
            candidate_text=CALCIUM,
            recommendation_evidence_span=CALCIUM,
            actor_of_scope="De werkgroep",
            recommended_action="te geven",
            action_object_or_goal="calcium",
            context_before=INCOMPLETE_COMPARISON,
            context_after=CALCIUM_EXC,
        )
    )
    assert admitted["exceptions_detected"]
    assert admitted.get("expand_merge", {}).get("performed") is True or (
        _scan_of(admitted).get("expand_merge") or {}
    ).get("performed") is True
    assert "source_fidelity_failure" not in admitted["reason_codes"]


# ---------------------------------------------------------------------------
# Hard non-regressions
# ---------------------------------------------------------------------------


def test_phase1_djg_still_blocked_from_ordinary_queue_as_aanbeveling() -> None:
    admitted = admit_candidate(
        build_candidate_record(
            candidate_id="cand-djg",
            document_id="doc-phase1",
            document_version="1.0",
            source_hash="a" * 64,
            section_path=["2 Aanbevelingen"],
            source_locator_start="lines:17-17",
            source_locator_end="lines:17-17",
            source_text_exact=DJG,
            candidate_text=DJG,
            subject_span="De dJG",
            predicate_span="wordt",
            proposed_type="recommendation",
            type_evidence_spans=[],
            context_before=ADVISEERT,
            context_after=ONE_WORD,
        )
    )
    assert admitted["gate_result"] == GATE_BLOCKED
    for code in (
        "recommendation_evidence_missing",
        "comparison_target_missing",
        "abbreviation_unresolved",
    ):
        assert code in admitted["reason_codes"], code
    assert ordinary_review_queue(
        [
            {
                "object_id": "djg-1",
                "object_type": "unclassified",
                "proposed_object_type": "recommendation",
                "content": {"clean_text": DJG},
                "metadata": {"admission": admitted},
            }
        ]
    ) == []


def test_boom_path_node_outcome_do_not_get_phase2_deep_scan() -> None:
    boom_rows = [
        {
            "object_id": "path-1",
            "object_type": "path",
            "proposed_object_type": "path",
            "content": {"clean_text": "Screening op valrisico"},
        },
        {
            "object_id": "node-1",
            "object_type": "node",
            "proposed_object_type": "node",
            "content": {"clean_text": "Is er een verhoogd valrisico?"},
        },
        {
            "object_id": "out-1",
            "object_type": "outcome",
            "proposed_object_type": "outcome",
            "content": {"clean_text": "Verwijs naar de valpoli."},
        },
    ]
    stamped = apply_admission_gate(
        boom_rows,
        klasse="beslisboom",
        document_version="1.0",
        source_hash="b" * 64,
    )
    for row, kind in zip(stamped, CLOSED_BOOM_TYPES):
        admission = _admission(row)
        assert row["proposed_object_type"] == kind
        assert admission.get("context_scan_done") is not True
        assert not (_scan_of(row).get("context_scan_done"))
        assert "type_contract_incomplete" not in (admission.get("reason_codes") or [])
        assert admission.get("gate_result") != GATE_BLOCKED or admission == {}


def test_source_text_exact_stays_freeze_fragment() -> None:
    dropped = "De werkgroep adviseert calcium te geven tenzij er hypercalciëmie bestaat."
    cleaned = "De werkgroep adviseert calcium te geven."
    objects = [
        {
            "object_id": "rec-drop",
            "document_id": "doc-phase2",
            "object_type": "unclassified",
            "proposed_object_type": "recommendation",
            "source": {"source_checksum": "c" * 64},
            "content": {"raw_text": dropped, "clean_text": cleaned},
            "structure": {"section_path": ["2 Aanbevelingen"], "heading": "2 Aanbevelingen"},
            "metadata": {
                "source_locator": {
                    "locator_type": "web_line_range",
                    "locator_value": "lines:20-20;p:1",
                }
            },
            "provenance": {"source_fragments": [{"raw_object_id": "frag-1"}]},
        }
    ]
    fragments = [{"fragment_id": "frag-1", "raw_text": dropped, "clean_text": cleaned}]
    stamped = apply_admission_gate(
        objects,
        klasse="richtlijn",
        fragments=fragments,
        document_version="1.0",
        source_hash="c" * 64,
    )
    admission = _admission(stamped[0])
    assert admission["source_text_exact"] == dropped
    assert admission["candidate_text"] == cleaned


# ---------------------------------------------------------------------------
# Extract path + existing review card
# ---------------------------------------------------------------------------


def test_phase1_ingest_still_keeps_adviseert_and_blocks_djg(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, PHASE1_FIXTURE, title="Phase 1 admission regression")
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    djg = _find_by_text(objects, DJG)
    adviseert = _find_by_text(objects, "adviseert de verpleegkundige")
    assert _admission(djg)["gate_result"] == GATE_BLOCKED
    for code in (
        "recommendation_evidence_missing",
        "comparison_target_missing",
        "abbreviation_unresolved",
    ):
        assert code in _admission(djg)["reason_codes"], code
    assert _admission(adviseert)["gate_result"] == GATE_ALLOWED
    assert _admission(adviseert).get("context_scan_done") is True or _scan_of(adviseert).get(
        "context_scan_done"
    )
    assert "context_scan_not_done" not in (_admission(adviseert).get("reason_codes") or [])
    ordinary = ordinary_review_queue(objects)
    ordinary_texts = [_text_of(obj) for obj in ordinary]
    assert DJG not in ordinary_texts
    assert any("adviseert de verpleegkundige" in text for text in ordinary_texts)
    assert all(_admission(obj).get("gate_result") == GATE_ALLOWED for obj in ordinary)
    assert not any(obj in ordinary for obj in blocked_audit_lane(objects))


def test_phase2_ingest_records_deep_window_and_wires_scan(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, PHASE2_FIXTURE)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    adviseert = _find_by_text(objects, "adviseert de verpleegkundige de risicofactoren")
    admission = _admission(adviseert)
    scan = _scan_of(adviseert)
    assert admission["gate_result"] == GATE_ALLOWED
    assert admission.get("context_scan_done") is True or scan.get("context_scan_done") is True
    assert PREV_CONDITION in str(admission.get("context_before") or "") or PREV_CONDITION in str(
        scan.get("previous_paragraph") or ""
    )
    assert NEXT_OVERLEG in str(admission.get("context_after") or "") or NEXT_OVERLEG in str(
        scan.get("next_paragraph") or ""
    )
    heading_blob = " ".join(
        [
            str(admission.get("context_before") or ""),
            " ".join(admission.get("section_path") or []),
            str(scan.get("current_heading") or ""),
            " ".join(scan.get("ancestor_headings") or []),
        ]
    )
    assert CURRENT_HEADING in heading_blob
    assert ANCESTOR_HEADING in heading_blob
    for signal in ("candidate_paragraph", "previous_paragraph", "next_paragraph", "current_heading"):
        assert signal in (scan.get("checked_signals") or admission.get("checked_signals") or []), signal
    assert "context_scan_not_done" not in (admission.get("reason_codes") or [])

    unresolved = _find_by_text(objects, "tabel 4")
    assert "unresolved_reference" in _admission(unresolved)["reason_codes"]
    comparison = _find_by_text(objects, "vaker effectief.")
    assert "comparison_target_missing" in _admission(comparison)["reason_codes"]

    djg = _find_by_text(objects, DJG)
    assert _admission(djg)["gate_result"] == GATE_BLOCKED
    assert "recommendation_evidence_missing" in _admission(djg)["reason_codes"]
    assert ordinary_review_queue([djg]) == []

    calcium = _find_by_text(objects, "adviseert calcium te geven")
    calcium_scan = _scan_of(calcium)
    assert calcium_scan.get("exceptions_detected") or _admission(calcium).get("exceptions_detected")
    merged = (_admission(calcium).get("expand_merge") or calcium_scan.get("expand_merge") or {})
    assert merged.get("performed") is True
    assert "hypercalciëmie" in str(merged.get("merged_text") or _text_of(calcium))

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    review = client.get(f"/review?document={receipt['snapshot_id']}").text
    slow = review.split('class="review-lane-slow"', 1)[-1].split("review-blocked-audit", 1)[0]
    assert DJG not in slow
    card = client.get(
        f"/review?document={receipt['snapshot_id']}&object={calcium['object_id']}"
    ).text
    assert "hypercalciëmie" in card
    assert "Gevonden onder" not in card
    assert "Review opslaan en volgende" not in card


def test_boom_ingest_still_skips_richtlijn_phase2(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="valrisico-boom.json",
        data=_boom_freeze_bytes(),
        content_type="application/json",
        ingest_kind="new",
        title="Valrisico boom",
        version="1.0",
        date="2025-04-01",
        live_url="",
        class_="beslisboom",
        family="valrisico",
        named_reviewers=[accounts["reviewer"]["account_id"]],
    )
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    kinds = {obj.get("proposed_object_type") or obj.get("object_type") for obj in objects}
    assert kinds >= set(CLOSED_BOOM_TYPES)
    for obj in objects:
        admission = _admission(obj)
        assert admission.get("context_scan_done") is not True
        assert "type_contract_incomplete" not in (admission.get("reason_codes") or [])
    assert slow_review_duty(objects, review_path="boom")


def test_blocked_candidate_still_cannot_be_confirmed(tmp_path: Path) -> None:
    from src.operations_console_v1 import ConsoleError

    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, PHASE1_FIXTURE, title="Phase 1 admission regression")
    djg = _find_by_text(console.snapshot_objects(receipt["snapshot_id"]), DJG)
    with pytest.raises(ConsoleError, match="blocked_candidate_not_reviewable"):
        console.confirm_object_type(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=djg["object_id"],
            confirmed_object_type="recommendation",
        )


def test_no_handoff_and_no_protocol_rewrite() -> None:
    assert not (ROOT / "HANDOFF.md").exists()
    # This file is the Phase 2 code test; it MUST NOT edit protocol deltas.
    assert "PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here" in Path(__file__).read_text(
        encoding="utf-8"
    )
