"""Extract-quality metrics hooks (Protocol v2.30 Phase 4).

Fail-closed: missing gold → cannot claim extract quality. Soft scores and a
single guideline without gold MUST NOT open a quality claim.
"""
from __future__ import annotations

from typing import Any

from src.admission_gate_v1 import admission_of, ordinary_review_queue
from src.extract_coverage_v1 import coverage_by_section
from src.passage_register_v1 import apply_passage_register, passage_register_of
from src.review_cockpit_v1 import confirmable_proposed_type


EXTRACT_QUALITY_METRICS = (
    "precision",
    "type_accuracy",
    "context_completeness",
    "coverage_vs_gold",
    "review_burden",
)


def _text_of(obj: dict[str, Any]) -> str:
    content = obj.get("content") if isinstance(obj.get("content"), dict) else {}
    return str(content.get("clean_text") or obj.get("candidate_text") or "").strip()


def _gold_passages(gold: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(gold, dict):
        return []
    rows = gold.get("passages") or []
    return [row for row in rows if isinstance(row, dict)]


def extract_quality_claim_allowed(objects: list[dict[str, Any]], gold: dict[str, Any] | None = None) -> bool:
    del objects
    return bool(_gold_passages(gold))


def _match_object(objects: list[dict[str, Any]], source_text: str) -> dict[str, Any] | None:
    needle = (source_text or "").strip()
    if not needle:
        return None
    exact = [obj for obj in objects if _text_of(obj) == needle]
    if exact:
        return exact[0]
    containing = [obj for obj in objects if needle in _text_of(obj)]
    if not containing:
        return None
    return min(containing, key=lambda obj: len(_text_of(obj)))


def _status_ok(live: str, expected: str, allowed: list[str] | None) -> bool:
    if allowed:
        return live in allowed
    return live == expected


def _type_of(obj: dict[str, Any]) -> str:
    admission = admission_of(obj)
    return str(
        obj.get("confirmed_object_type")
        or confirmable_proposed_type(obj)
        or obj.get("proposed_object_type")
        or admission.get("proposed_type")
        or obj.get("object_type")
        or ""
    ).strip()


def _context_complete(obj: dict[str, Any]) -> bool:
    admission = admission_of(obj)
    scan = admission.get("context_scan") if isinstance(admission.get("context_scan"), dict) else {}
    if scan.get("context_scan_done") or admission.get("context_scan_done"):
        return True
    before = str(admission.get("context_before") or scan.get("previous_paragraph") or "").strip()
    after = str(admission.get("context_after") or scan.get("next_paragraph") or "").strip()
    return bool(before or after)


def compute_extract_metrics(
    objects: list[dict[str, Any]],
    gold: dict[str, Any] | None = None,
    *,
    soft_scores: dict[str, Any] | None = None,
    guideline_count: int | None = None,
) -> dict[str, Any]:
    del soft_scores, guideline_count
    stamped = apply_passage_register(list(objects))
    passages = [obj for obj in stamped if obj.get("object_type") != "document"]
    gold_rows = _gold_passages(gold)
    empty = {name: None for name in EXTRACT_QUALITY_METRICS}
    if not gold_rows:
        return {
            "quality_claim_allowed": False,
            "reason": "gold_standard_required",
            **empty,
            "coverage": coverage_by_section(passages),
        }
    matched = 0
    status_hits = 0
    type_total = 0
    type_hits = 0
    selected = [obj for obj in passages if passage_register_of(obj).get("status") == "selected_as_candidate"]
    selected_gold = 0
    selected_true = 0
    for row in gold_rows:
        obj = _match_object(passages, str(row.get("source_text") or ""))
        if obj is None:
            continue
        matched += 1
        live = str(passage_register_of(obj).get("status") or "")
        expected = str(row.get("expected_register_status") or "")
        allowed = [str(item) for item in (row.get("allowed_register_statuses") or []) if str(item)]
        if _status_ok(live, expected, allowed or None):
            status_hits += 1
        if expected == "selected_as_candidate" or "selected_as_candidate" in allowed:
            selected_gold += 1
            if live == "selected_as_candidate":
                selected_true += 1
        expected_type = str(row.get("expected_type") or "").strip()
        if expected_type:
            type_total += 1
            if _type_of(obj) == expected_type:
                type_hits += 1
    context_total = len(selected) or 1
    context_hits = sum(1 for obj in selected if _context_complete(obj))
    ordinary = ordinary_review_queue(passages)
    reviewed = sum(
        1
        for obj in passages
        if ((obj.get("metadata") or {}).get("review_passage") or {}).get("suitability")
    )
    duty = max(len(ordinary), 1)
    return {
        "quality_claim_allowed": True,
        "reason": "",
        "precision": round(selected_true / selected_gold, 3) if selected_gold else round(status_hits / max(matched, 1), 3),
        "type_accuracy": round(type_hits / type_total, 3) if type_total else 0.0,
        "context_completeness": round(context_hits / context_total, 3),
        "coverage_vs_gold": round(matched / len(gold_rows), 3),
        "review_burden": round(min(1.0, len(ordinary) / duty if reviewed else len(ordinary) / max(len(passages), 1)), 3),
        "coverage": coverage_by_section(passages),
        "matched_gold_passages": matched,
        "gold_passages": len(gold_rows),
    }
