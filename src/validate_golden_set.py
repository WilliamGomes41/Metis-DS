#!/usr/bin/env python3
"""Static validation for V&VN retrieval golden sets."""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

ALLOWED_CLASSES = {"fact", "condition_score", "exception", "version_conflict", "no_answer"}
ALLOWED_BEHAVIORS = {"retrieve", "abstain", "current_published_only"}
ALLOWED_MODES = {"published_corpus", "fixture_only", "deferred"}


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


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path,required=True); ap.add_argument("--report",type=Path,required=True); a=ap.parse_args()
    data=json.loads(a.input.read_text(encoding="utf-8")); report=validate(data)
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if report["status"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
