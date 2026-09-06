"""Extract-quality metrics (ROADMAP wave 4).

Precision counts false positives in the denominator. context_completeness
requires captured neighbor context and MUST NOT treat context_scan_done
alone as completeness. A quality claim requires independent/representative
gold — Phase-4 fixture gold and any non-empty fixture MUST NOT open it.

Read-mostly: this module does not write gold or metric files. Metric runs
are idempotent. Old extract-gold schema stays readable; unsupported
schema fail-closed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.admission_gate_v1 import (
    GATE_ALLOWED,
    GATE_BLOCKED,
    admission_of,
    admit_candidate,
    build_candidate_record,
    ordinary_review_queue,
)
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

SUPPORTED_EXTRACT_GOLD_VERSIONS = frozenset({"0.1"})
FIXTURE_GOLD_STATUSES = frozenset(
    {
        "fixture_gold",
        "development",
        "preliminary_pending_clinical_publication",
        "language_variation",
    }
)
INDEPENDENT_GOLD_STATUSES = frozenset({"independent_representative", "locked_holdout"})
GOLD_POSITIVE_ROLES = frozenset({"missed_knowledge", "true_positive_expected"})
GOLD_NEGATIVE_ROLES = frozenset({"false_admit", "true_negative"})
GOLD_NEGATIVE_CLASSES = frozenset({"false_admit", "excluded"})


class ExtractGoldError(ValueError):
    """Fail-closed gold load (truncated, non-JSON, or not an object)."""

    def __init__(self, code: str = "gold_unreadable") -> None:
        self.code = code
        super().__init__(code)


def _text_of(obj: dict[str, Any]) -> str:
    content = obj.get("content") if isinstance(obj.get("content"), dict) else {}
    return str(content.get("clean_text") or obj.get("candidate_text") or "").strip()


def _gold_passages(gold: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(gold, dict):
        return []
    rows = gold.get("passages") or []
    return [row for row in rows if isinstance(row, dict)]


def gold_schema_supported(gold: dict[str, Any] | None) -> bool:
    if not isinstance(gold, dict):
        return False
    kind = str(gold.get("kind") or "").strip()
    if kind and kind != "extract_quality":
        return False
    version = str(gold.get("version") or "0.1").strip()
    return version in SUPPORTED_EXTRACT_GOLD_VERSIONS


def _is_gold_positive(row: dict[str, Any]) -> bool:
    role = str(row.get("role") or "").strip()
    cls = str(row.get("class") or "").strip()
    if role in GOLD_NEGATIVE_ROLES or cls == "false_admit":
        return False
    if role in GOLD_POSITIVE_ROLES or cls == "missed":
        return True
    expected = str(row.get("expected_register_status") or "")
    allowed = [str(item) for item in (row.get("allowed_register_statuses") or []) if str(item)]
    if expected == "selected_as_candidate" or "selected_as_candidate" in allowed:
        return True
    return False


def _is_gold_negative(row: dict[str, Any]) -> bool:
    role = str(row.get("role") or "").strip()
    cls = str(row.get("class") or "").strip()
    if role in GOLD_NEGATIVE_ROLES or cls in GOLD_NEGATIVE_CLASSES:
        return True
    return str(row.get("expected_register_status") or "") == "excluded_with_reason"


def _has_missed_knowledge(passages: Iterable[dict[str, Any]]) -> bool:
    return any(
        str(row.get("role") or "") == "missed_knowledge" or str(row.get("class") or "") == "missed"
        for row in passages
    )


def _has_false_admit(passages: Iterable[dict[str, Any]]) -> bool:
    return any(
        str(row.get("role") or "") == "false_admit" or str(row.get("class") or "") == "false_admit"
        for row in passages
    )


def _source_count(gold: dict[str, Any]) -> int:
    sources = gold.get("sources")
    if isinstance(sources, list) and sources:
        return len(sources)
    fixtures = gold.get("source_fixtures")
    if isinstance(fixtures, list) and fixtures:
        return len(fixtures)
    if str(gold.get("source_fixture") or "").strip():
        return 1
    return 0


def gold_supports_independent_quality_claim(gold: dict[str, Any] | None) -> bool:
    if not gold_schema_supported(gold) or not isinstance(gold, dict):
        return False
    status = str(gold.get("status") or "").strip()
    if status in FIXTURE_GOLD_STATUSES:
        return False
    passages = _gold_passages(gold)
    if not passages:
        return False
    independence = gold.get("independence") if isinstance(gold.get("independence"), dict) else {}
    rules = gold.get("rules") if isinstance(gold.get("rules"), dict) else {}
    flagged = (
        independence.get("independent") is True
        and independence.get("representative") is True
    ) or rules.get("independent_quality_claim") is True
    if not flagged and status not in INDEPENDENT_GOLD_STATUSES:
        return False
    if _source_count(gold) < 2:
        return False
    return _has_missed_knowledge(passages) and _has_false_admit(passages)


def extract_quality_claim_allowed(objects: list[dict[str, Any]], gold: dict[str, Any] | None = None) -> bool:
    del objects
    return gold_supports_independent_quality_claim(gold)


def load_extract_gold(path: Path | str) -> dict[str, Any]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtractGoldError("gold_unreadable") from exc
    if not isinstance(data, dict):
        raise ExtractGoldError("gold_unreadable")
    return data


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


def _match_gold_row(rows: list[dict[str, Any]], text: str) -> dict[str, Any] | None:
    needle = (text or "").strip()
    if not needle:
        return None
    exact = [row for row in rows if str(row.get("source_text") or "").strip() == needle]
    if exact:
        return exact[0]
    containing = [row for row in rows if needle in str(row.get("source_text") or "")]
    if containing:
        return min(containing, key=lambda row: len(str(row.get("source_text") or "")))
    contained = [row for row in rows if str(row.get("source_text") or "").strip() in needle]
    if not contained:
        return None
    return min(contained, key=lambda row: len(str(row.get("source_text") or "")))


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
    """Captured neighbor context. ``context_scan_done`` alone is not enough."""
    admission = admission_of(obj)
    scan = admission.get("context_scan") if isinstance(admission.get("context_scan"), dict) else {}
    if scan.get("necessary_context_disposition") == "block":
        return False
    before = str(admission.get("context_before") or scan.get("previous_paragraph") or "").strip()
    after = str(admission.get("context_after") or scan.get("next_paragraph") or "").strip()
    return bool(before or after)


def _empty_metrics(*, reason: str) -> dict[str, Any]:
    return {
        "quality_claim_allowed": False,
        "reason": reason,
        **{name: None for name in EXTRACT_QUALITY_METRICS},
        "true_positives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "coverage": {"objectify_every_sentence": False, "duty": "normative_application_critical", "sections": {}},
    }


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
    if gold is not None and not gold_schema_supported(gold):
        empty = _empty_metrics(reason="gold_schema_unsupported")
        empty["coverage"] = coverage_by_section(passages)
        return empty
    if not gold_rows:
        empty = _empty_metrics(reason="gold_standard_required")
        empty["coverage"] = coverage_by_section(passages)
        return empty

    selected = [obj for obj in passages if passage_register_of(obj).get("status") == "selected_as_candidate"]
    gold_positives = [row for row in gold_rows if _is_gold_positive(row)]
    matched_positive: set[str] = set()
    true_positives = 0
    false_positives = 0
    for obj in selected:
        row = _match_gold_row(gold_rows, _text_of(obj))
        if row is not None and _is_gold_positive(row):
            true_positives += 1
            matched_positive.add(str(row.get("id") or _text_of(obj)))
        else:
            false_positives += 1
    false_negatives = 0
    for row in gold_positives:
        key = str(row.get("id") or row.get("source_text") or "")
        if key in matched_positive:
            continue
        obj = _match_object(selected, str(row.get("source_text") or ""))
        if obj is None:
            false_negatives += 1

    matched = 0
    status_hits = 0
    type_total = 0
    type_hits = 0
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
        expected_type = str(row.get("expected_type") or "").strip()
        if expected_type:
            type_total += 1
            if _type_of(obj) == expected_type:
                type_hits += 1

    context_total = len(selected)
    context_hits = sum(1 for obj in selected if _context_complete(obj))
    ordinary = ordinary_review_queue(passages)
    reviewed = sum(
        1
        for obj in passages
        if ((obj.get("metadata") or {}).get("review_passage") or {}).get("suitability")
    )
    duty = max(len(ordinary), 1)
    claim = gold_supports_independent_quality_claim(gold)
    if claim:
        reason = ""
    elif not gold_schema_supported(gold):
        reason = "gold_schema_unsupported"
    else:
        reason = "independent_representative_gold_required"
    del status_hits  # status agreement is not precision
    predicted = true_positives + false_positives
    return {
        "quality_claim_allowed": claim,
        "reason": reason,
        "precision": round(true_positives / predicted, 3) if predicted else 0.0,
        "type_accuracy": round(type_hits / type_total, 3) if type_total else 0.0,
        "context_completeness": round(context_hits / context_total, 3) if context_total else 0.0,
        "coverage_vs_gold": round(matched / len(gold_rows), 3),
        "review_burden": round(min(1.0, len(ordinary) / duty if reviewed else len(ordinary) / max(len(passages), 1)), 3),
        "coverage": coverage_by_section(passages),
        "matched_gold_passages": matched,
        "gold_passages": len(gold_rows),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def _candidate_from_case(case: dict[str, Any]) -> dict[str, Any]:
    text = str(case.get("source_text") or case.get("candidate_text") or "")
    return build_candidate_record(
        candidate_id=str(case.get("id") or "case"),
        document_id="doc-lang",
        document_version="1.0",
        source_hash="c" * 64,
        section_path=["2 Aanbevelingen"],
        source_locator_start="lines:1-1",
        source_locator_end="lines:1-1",
        source_text_exact=text,
        candidate_text=text,
        proposed_type=str(case.get("proposed_type") or "recommendation"),
        context_before=str(case.get("context_before") or "Vorige alinea over de doelgroep."),
        context_after=str(case.get("context_after") or "Volgende alinea over vervolgonderzoek."),
    )


def _outcome(live: str | None, expected: str) -> str:
    if live == GATE_ALLOWED and expected == GATE_ALLOWED:
        return "true_admit"
    if live == GATE_ALLOWED and expected == GATE_BLOCKED:
        return "false_admit"
    if live != GATE_ALLOWED and expected == GATE_ALLOWED:
        return "miss"
    return "true_block"


def measure_admission_language_variation(
    cases: Iterable[dict[str, Any]] | None = None,
    *,
    gold: dict[str, Any] | None = None,
    objects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Measure false admits and misses on language-variation cases.

    Tied to ``admission_gate_v1`` (direct ``admit_candidate``) and, when
    ``objects`` is supplied, to the extract/admission path.
    """
    rows = [dict(row) for row in (cases or [])]
    if not rows and gold:
        rows = [dict(row) for row in _gold_passages(gold)]

    report_cases: list[dict[str, Any]] = []
    buckets: dict[str, list[dict[str, Any]]] = {
        "true_admit": [],
        "false_admit": [],
        "miss": [],
        "true_block": [],
    }
    stamped = apply_passage_register(list(objects)) if objects is not None else None
    for row in rows:
        expected = str(row.get("expected_gate") or GATE_BLOCKED)
        if stamped is not None:
            obj = _match_object(stamped, str(row.get("source_text") or ""))
            live = str(admission_of(obj).get("gate_result") or "") if obj is not None else ""
            if not live and obj is not None and passage_register_of(obj).get("status") == "selected_as_candidate":
                live = GATE_ALLOWED
            codes = list(admission_of(obj).get("reason_codes") or []) if obj is not None else ["not_extracted"]
        else:
            admitted = admit_candidate(_candidate_from_case(row))
            live = str(admitted.get("gate_result") or "")
            codes = list(admitted.get("reason_codes") or [])
        outcome = _outcome(live or None, expected)
        item = {
            **row,
            "live_gate": live or GATE_BLOCKED,
            "outcome": outcome,
            "reason_codes": codes,
        }
        report_cases.append(item)
        buckets[outcome].append(item)

    true_admits = buckets["true_admit"]
    false_admits = buckets["false_admit"]
    misses = buckets["miss"]
    true_blocks = buckets["true_block"]
    tp = len(true_admits)
    fp = len(false_admits)
    fn = len(misses)
    return {
        "cases": report_cases,
        "true_admits": true_admits,
        "false_admits": false_admits,
        "misses": misses,
        "true_blocks": true_blocks,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(tp / (tp + fp), 3) if (tp + fp) else 0.0,
        "recall": round(tp / (tp + fn), 3) if (tp + fn) else 0.0,
    }
