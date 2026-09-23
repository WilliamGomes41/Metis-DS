#!/usr/bin/env python3
"""Static validation for V&VN retrieval golden sets."""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

ALLOWED_CLASSES = {"fact", "condition_score", "exception", "version_conflict", "no_answer"}
ALLOWED_BEHAVIORS = {"retrieve", "abstain", "current_published_only"}
ALLOWED_MODES = {"published_corpus", "fixture_only", "deferred"}
EXTRACT_GOLD_KIND = "extract_quality"
EXTRACT_GOLD_CLASSES = {
    "normative",
    "support",
    "excluded",
    "context",
    "heading",
    "missed",
    "false_admit",
}
EXTRACT_GOLD_ROLES = {
    "missed_knowledge",
    "false_admit",
    "true_positive_expected",
    "true_negative",
}
INDEPENDENT_EXTRACT_GOLD_STATUSES = {"independent_representative", "locked_holdout"}
EXTRACT_REGISTER_STATUSES = {
    "selected_as_candidate",
    "used_as_context",
    "linked_as_support",
    "excluded_with_reason",
    "not_yet_assessed",
}


def validate(data: dict) -> dict:
    errors=[]; warnings=[]
    qs=data.get("questions") or []
    ids=[q.get("id") for q in qs]
    if len(ids)!=len(set(ids)): errors.append("duplicate_question_ids")
    for i,q in enumerate(qs):
        prefix=f"questions[{i}]"
        if q.get("class") not in ALLOWED_CLASSES: errors.append(f"{prefix}:invalid_class")
        if q.get("expected_behavior") not in ALLOWED_BEHAVIORS: errors.append(f"{prefix}:invalid_behavior")
        if q.get("execution_mode") not in ALLOWED_MODES: errors.append(f"{prefix}:invalid_execution_mode")
        if not str(q.get("question") or "").strip(): errors.append(f"{prefix}:question_missing")
        if q.get("class")=="no_answer" and q.get("expected_behavior")!="abstain": errors.append(f"{prefix}:no_answer_must_abstain")
        if q.get("expected_behavior")=="retrieve" and not q.get("expected_object_ids"): errors.append(f"{prefix}:retrieve_requires_expected_object")
    counts=Counter(q.get("class") for q in qs)
    total=len(qs)
    if total:
        no_answer_share=counts["no_answer"]/total
        if no_answer_share < .20: warnings.append("no_answer_share_below_20_percent")
    return {
        "status":"PASS" if not errors else "BLOCKED",
        "questions":total,
        "class_counts":dict(counts),
        "no_answer_share":round(counts["no_answer"]/total,3) if total else 0,
        "errors":errors,
        "warnings":warnings,
    }


def validate_extract_gold(data: dict) -> dict:
    errors = []
    warnings = []
    if (data.get("kind") or "").strip() != EXTRACT_GOLD_KIND:
        errors.append("kind_must_be_extract_quality")
    sources = data.get("sources") if isinstance(data.get("sources"), list) else []
    if not data.get("source_fixture") and not sources:
        errors.append("source_fixture_missing")
    rules = data.get("rules") if isinstance(data.get("rules"), dict) else {}
    if rules.get("gold_required_before_quality_claim") is not True:
        errors.append("gold_required_before_quality_claim")
    if rules.get("soft_scores_must_not_claim_quality") is not True:
        errors.append("soft_scores_must_not_claim_quality")
    passages = data.get("passages") or []
    ids = [row.get("id") for row in passages]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_passage_ids")
    for i, row in enumerate(passages):
        prefix = f"passages[{i}]"
        if row.get("class") not in EXTRACT_GOLD_CLASSES:
            errors.append(f"{prefix}:invalid_class")
        role = row.get("role")
        if role and role not in EXTRACT_GOLD_ROLES:
            errors.append(f"{prefix}:invalid_role")
        if not str(row.get("source_text") or "").strip():
            errors.append(f"{prefix}:source_text_missing")
        if not str(row.get("section") or "").strip():
            errors.append(f"{prefix}:section_missing")
        status = row.get("expected_register_status")
        if status not in EXTRACT_REGISTER_STATUSES:
            errors.append(f"{prefix}:invalid_register_status")
        allowed = row.get("allowed_register_statuses") or []
        if any(item not in EXTRACT_REGISTER_STATUSES for item in allowed):
            errors.append(f"{prefix}:invalid_allowed_register_status")
    gold_status = str(data.get("status") or "")
    if gold_status in INDEPENDENT_EXTRACT_GOLD_STATUSES:
        if len(sources) < 2:
            errors.append("independent_gold_requires_multiple_sources")
        roles = {str(row.get("role") or row.get("class") or "") for row in passages}
        if "missed_knowledge" not in roles and "missed" not in roles:
            errors.append("independent_gold_requires_missed_knowledge")
        if "false_admit" not in roles:
            errors.append("independent_gold_requires_false_admits")
    return {
        "status": "PASS" if not errors else "BLOCKED",
        "passages": len(passages),
        "errors": errors,
        "warnings": warnings,
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path,required=True); ap.add_argument("--report",type=Path,required=True); a=ap.parse_args()
    data=json.loads(a.input.read_text(encoding="utf-8")); report=validate(data)
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if report["status"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
