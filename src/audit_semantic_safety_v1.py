"""Frozen semantic passage safety audit.

This module evaluates the existing deterministic passage formation and the
source-bound semantic candidate on the same frozen source cases. It has no
persistence and no write path into Review, publication or serving state.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.context_aware_split_v1 import split_context_aware_units
from src.operations_console_v1 import ConsoleError
from src.review.pre_review_semantic_v1 import PostJson, semantic_units_before_review
from src.semantic_passage_v1 import SELECTION_ORIGIN_COVERAGE, SELECTION_ORIGIN_PROPOSAL


SUITE_SCHEMA_VERSION = 1
REQUIRED_RISK_CATEGORIES = frozenset(
    {"omission", "condition", "exception", "negation", "meaning_distortion"}
)
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _norm(value: str) -> str:
    return " ".join(str(value or "").split())


def _validate_case(case: Any) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise ConsoleError("semantic_safety_case_invalid")
    case_id = str(case.get("case_id") or "").strip()
    category = str(case.get("risk_category") or "").strip()
    snapshot_id = str(case.get("snapshot_id") or "").strip()
    source_text = str(case.get("source_text") or "")
    source_hash = str(case.get("source_hash") or "").strip().lower()
    source_locator = case.get("source_locator")
    must_preserve = case.get("must_preserve")
    must_co_locate = case.get("must_co_locate")

    if not case_id or not snapshot_id or category not in REQUIRED_RISK_CATEGORIES:
        raise ConsoleError("semantic_safety_case_invalid")
    if not source_text or _SHA256_RE.fullmatch(source_hash) is None:
        raise ConsoleError("semantic_safety_case_invalid")
    if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != source_hash:
        raise ConsoleError("semantic_safety_source_hash_mismatch")
    if not isinstance(source_locator, dict) or not source_locator:
        raise ConsoleError("semantic_safety_case_invalid")
    if not isinstance(must_preserve, list) or not all(
        isinstance(anchor, str) and _norm(anchor) for anchor in must_preserve
    ):
        raise ConsoleError("semantic_safety_case_invalid")
    if not isinstance(must_co_locate, list):
        raise ConsoleError("semantic_safety_case_invalid")

    normalized_source = _norm(source_text)
    anchors = [_norm(anchor) for anchor in must_preserve]
    if any(anchor not in normalized_source for anchor in anchors):
        raise ConsoleError("semantic_safety_anchor_not_in_source")

    groups: list[list[str]] = []
    for raw_group in must_co_locate:
        if not isinstance(raw_group, list) or len(raw_group) < 2:
            raise ConsoleError("semantic_safety_case_invalid")
        group = [_norm(anchor) for anchor in raw_group]
        if any(not anchor or anchor not in normalized_source for anchor in group):
            raise ConsoleError("semantic_safety_anchor_not_in_source")
        groups.append(group)

    return {
        "case_id": case_id,
        "risk_category": category,
        "snapshot_id": snapshot_id,
        "source_hash": source_hash,
        "source_locator": deepcopy(source_locator),
        "source_text": source_text,
        "must_preserve": anchors,
        "must_co_locate": groups,
    }


def load_frozen_safety_suite(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConsoleError("semantic_safety_suite_invalid") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != SUITE_SCHEMA_VERSION:
        raise ConsoleError("semantic_safety_suite_invalid")

    suite_id = str(raw.get("suite_id") or "").strip()
    status = str(raw.get("status") or "").strip()
    baseline_commit = str(raw.get("evaluated_baseline_commit") or "").strip().lower()
    raw_cases = raw.get("cases")
    if (
        not suite_id
        or status != "frozen_before_first_live_evaluation"
        or _COMMIT_RE.fullmatch(baseline_commit) is None
        or not isinstance(raw_cases, list)
        or not raw_cases
    ):
        raise ConsoleError("semantic_safety_suite_invalid")

    cases = [_validate_case(case) for case in raw_cases]
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ConsoleError("semantic_safety_case_duplicate")
    categories = {case["risk_category"] for case in cases}
    if not REQUIRED_RISK_CATEGORIES.issubset(categories):
        raise ConsoleError("semantic_safety_categories_incomplete")

    return {
        "schema_version": SUITE_SCHEMA_VERSION,
        "suite_id": suite_id,
        "status": status,
        "evaluated_baseline_commit": baseline_commit,
        "cases": cases,
        "suite_hash": _stable_hash(
            {
                "schema_version": SUITE_SCHEMA_VERSION,
                "suite_id": suite_id,
                "status": status,
                "evaluated_baseline_commit": baseline_commit,
                "cases": cases,
            }
        ),
    }


def _fragment(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "fragment_id": case["case_id"],
        "fragment_hash": case["source_hash"],
        "raw_text": case["source_text"],
        "clean_text": case["source_text"],
        "section_path": ["Frozen semantic safety audit"],
        "source_locator": deepcopy(case["source_locator"]),
    }


def _text_of(unit: dict[str, Any]) -> str:
    return _norm(str(unit.get("text") or unit.get("clean_text") or ""))


def _semantic_texts(
    units: list[dict[str, Any]],
    origin: str,
) -> list[str]:
    out: list[str] = []
    for unit in units:
        metadata = unit.get("semantic_passage")
        if isinstance(metadata, dict) and metadata.get("selection_origin") == origin:
            text = _text_of(unit)
            if text:
                out.append(text)
    return out


def _evaluate(case: dict[str, Any], texts: list[str]) -> dict[str, Any]:
    missing = [
        anchor
        for anchor in case["must_preserve"]
        if not any(anchor in text for text in texts)
    ]
    broken_groups = [
        group
        for group in case["must_co_locate"]
        if not any(all(anchor in text for anchor in group) for text in texts)
    ]
    return {
        "pass": not missing and not broken_groups,
        "missing_anchors": missing,
        "broken_co_location_groups": broken_groups,
    }


def run_frozen_semantic_safety_suite(
    suite: dict[str, Any],
    *,
    api_key: str,
    model: str,
    evaluated_commit: str,
    post_json: PostJson | None = None,
) -> dict[str, Any]:
    safe_commit = str(evaluated_commit or "").strip().lower()
    if _COMMIT_RE.fullmatch(safe_commit) is None:
        raise ConsoleError("semantic_safety_evaluated_commit_invalid")
    safe_model = str(model or "").strip()
    if not safe_model:
        raise ConsoleError("semantic_safety_model_required")

    results: list[dict[str, Any]] = []
    for case in suite["cases"]:
        fragment = _fragment(case)
        baseline_units = split_context_aware_units(
            [fragment],
            document_id=f'audit-baseline-{case["case_id"]}',
        )
        baseline_texts = [_text_of(unit) for unit in baseline_units if _text_of(unit)]
        baseline_evaluation = _evaluate(case, baseline_texts)

        candidate_units: list[dict[str, Any]] = []
        kernel_reject = ""
        try:
            candidate_units = semantic_units_before_review(
                [fragment],
                document_id=f'audit-semantic-{case["case_id"]}',
                api_key=api_key,
                model=safe_model,
                post_json=post_json,
            )
        except ConsoleError as exc:
            kernel_reject = exc.code

        selected_texts = _semantic_texts(candidate_units, SELECTION_ORIGIN_PROPOSAL)
        coverage_texts = _semantic_texts(candidate_units, SELECTION_ORIGIN_COVERAGE)
        candidate_evaluation = _evaluate(case, selected_texts)
        case_pass = not kernel_reject and bool(candidate_evaluation["pass"])

        results.append(
            {
                "case_id": case["case_id"],
                "risk_category": case["risk_category"],
                "source_hash": case["source_hash"],
                "source_locator": deepcopy(case["source_locator"]),
                "baseline": {
                    "texts": baseline_texts,
                    "evaluation": baseline_evaluation,
                },
                "candidate": {
                    "selected_texts": selected_texts,
                    "coverage_remainders": coverage_texts,
                    "evaluation": candidate_evaluation,
                    "kernel_reject": kernel_reject or None,
                    "pass": case_pass,
                },
            }
        )

    passed = sum(1 for row in results if row["candidate"]["pass"])
    rejects = sum(1 for row in results if row["candidate"]["kernel_reject"])
    return {
        "schema_version": 1,
        "audit_kind": "frozen_semantic_passage_safety",
        "suite_id": suite["suite_id"],
        "suite_hash": suite["suite_hash"],
        "suite_baseline_commit": suite["evaluated_baseline_commit"],
        "evaluated_commit": safe_commit,
        "model": safe_model,
        "case_count": len(results),
        "candidate_pass_count": passed,
        "kernel_reject_count": rejects,
        "machine_safety_pass": passed == len(results),
        "requires_human_review": True,
        "results": results,
    }
