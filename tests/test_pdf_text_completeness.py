from __future__ import annotations

from src.audit_pdf_text_completeness import audit, normalize


def _spec(text: str):
    return {
        "reviewed_by": "visual-reviewer-1",
        "reviewed_at": "2026-08-22T20:00:00Z",
        "review_status": "approved",
        "assertions": [{"anchor_id": "condition-1", "source_page": 15, "required_text": text}],
    }


def test_normalize_repairs_line_break_hyphenation():
    assert normalize("fractuurpreven-\n tie") == "fractuurpreventie"


def test_audit_passes_when_reviewed_visual_anchor_is_in_text_layer():
    rows = [{"source_page": 15, "clean_text": "Bij een cliënt van 50 jaar"}]
    report = audit(rows, _spec("cliënt van 50 jaar"))
    assert report["status"] == "PASS"
    assert report["publication_eligibility"] == "eligible_for_transform"


def test_audit_fails_closed_when_visual_anchor_is_missing():
    rows = [{"source_page": 15, "clean_text": "fractuur (≤ 2 jaar geleden)"}]
    report = audit(rows, _spec("Bij een cliënt in zorg ≥ 50 jaar"))
    assert report["status"] == "FAIL"
    assert report["publication_eligibility"] == "blocked_text_layer_incomplete"
    assert report["checks"][0]["errors"] == ["required_visual_text_absent_from_text_layer"]


def test_audit_requires_review_metadata_and_assertions():
    report = audit([], {"assertions": []})
    assert report["status"] == "FAIL"
    assert set(report["spec_errors"]) == {
        "reviewed_by_missing",
        "reviewed_at_missing",
        "visual_review_not_approved",
        "assertions_missing",
    }
