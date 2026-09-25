"""D2b2-B: sentence completeness is independent from predicate evidence.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from src.admission_gate_v1 import (
    GATE_ALLOWED,
    GATE_BLOCKED,
    admit_candidate,
    apply_admission_gate,
    build_candidate_record,
)


COMPLETE_DISTINGUISHES = (
    "De wetenschappelijke literatuur onderscheidt verschillende vormen van eenzaamheid."
)
COMPLETE_REDUCES = "Sociale steun vermindert gevoelens van eenzaamheid."
TRUNCATED = (
    "De wetenschappelijke literatuur onderscheidt verschillende vormen van eenzaamheid"
)
SHORT = "Steun helpt."


def _factual_candidate(text: str, *, predicate_span: str) -> dict:
    subject = (
        "De wetenschappelijke literatuur"
        if text.startswith("De wetenschappelijke")
        else "Sociale steun"
        if text.startswith("Sociale steun")
        else "Steun"
    )
    evidence = predicate_span or "onderscheidt"
    return build_candidate_record(
        candidate_id="cand-d2b2b",
        document_id="doc-d2b2b",
        document_version="1.0",
        source_hash="a" * 64,
        section_path=["3. Vaststellen van eenzaamheid"],
        source_locator_start="page:1;bbox:1,1,2,2",
        source_locator_end="page:1;bbox:1,1,2,2",
        source_text_exact=text,
        candidate_text=text,
        subject_span=subject,
        predicate_span=predicate_span,
        proposed_type="factual_finding",
        type_evidence_spans=[evidence],
        context_before="",
        context_after="",
        factual_claim_span=text,
    )


def test_complete_sentence_with_non_whitelist_predicate_is_not_incomplete() -> None:
    admitted = admit_candidate(
        _factual_candidate(
            COMPLETE_DISTINGUISHES,
            predicate_span="onderscheidt",
        )
    )

    assert admitted["gate_result"] == GATE_ALLOWED
    assert "incomplete_sentence" not in admitted["reason_codes"]
    assert "predicate_missing" not in admitted["reason_codes"]


def test_second_complete_non_whitelist_predicate_remains_complete() -> None:
    admitted = admit_candidate(
        _factual_candidate(
            COMPLETE_REDUCES,
            predicate_span="vermindert",
        )
    )

    assert admitted["gate_result"] == GATE_ALLOWED
    assert "incomplete_sentence" not in admitted["reason_codes"]


def test_missing_predicate_blocks_without_relabeling_complete_sentence() -> None:
    admitted = admit_candidate(
        _factual_candidate(
            COMPLETE_DISTINGUISHES,
            predicate_span="",
        )
    )

    assert admitted["gate_result"] == GATE_BLOCKED
    assert "predicate_missing" in admitted["reason_codes"]
    assert "incomplete_sentence" not in admitted["reason_codes"]


def test_missing_terminal_boundary_is_still_incomplete() -> None:
    admitted = admit_candidate(
        _factual_candidate(
            TRUNCATED,
            predicate_span="onderscheidt",
        )
    )

    assert admitted["gate_result"] == GATE_BLOCKED
    assert "incomplete_sentence" in admitted["reason_codes"]


def test_short_fragment_stays_incomplete_and_non_independent() -> None:
    admitted = admit_candidate(
        _factual_candidate(
            SHORT,
            predicate_span="helpt",
        )
    )

    assert admitted["gate_result"] == GATE_BLOCKED
    assert "incomplete_sentence" in admitted["reason_codes"]
    assert "no_independent_claim" in admitted["reason_codes"]


def test_extract_admission_path_keeps_predicate_missing_separate() -> None:
    objects = [
        {
            "object_id": "obj-d2b2b",
            "document_id": "doc-d2b2b",
            "object_type": "unclassified",
            "proposed_object_type": "factual_finding",
            "source": {"source_checksum": "b" * 64},
            "content": {
                "raw_text": COMPLETE_DISTINGUISHES,
                "clean_text": COMPLETE_DISTINGUISHES,
            },
            "structure": {
                "section_path": ["3. Vaststellen van eenzaamheid"],
            },
            "metadata": {
                "source_locator": {
                    "locator_type": "page_bbox",
                    "locator_value": "page:1;bbox:1,1,2,2",
                }
            },
        }
    ]

    stamped = apply_admission_gate(
        objects,
        klasse="richtlijn",
        document_version="1.0",
        source_hash="b" * 64,
    )
    admission = stamped[0]["metadata"]["admission"]

    assert admission["gate_result"] == GATE_BLOCKED
    assert "predicate_missing" in admission["reason_codes"]
    assert "incomplete_sentence" not in admission["reason_codes"]
