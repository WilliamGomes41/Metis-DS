#!/usr/bin/env python3
"""Apply first-line clinical review without mutating reviewed clinical content.

The workflow is fail-closed. A review only applies when the review snapshot still
matches the current canonical candidate. Proposed corrections create a revise
state; they are never applied automatically.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ALLOWED = {"", "approve", "revise", "reject"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def read_reviews(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    return {r["object_id"].strip(): r for r in rows if r.get("object_id", "").strip()}


def norm(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.endswith(".0"):
        try:
            return str(int(float(s)))
        except ValueError:
            pass
    return s


def current_review_fields(obj: dict[str, Any]) -> dict[str, str]:
    operator = threshold = unit = score_points = ""
    logic = obj.get("logic") or {}
    predicates = logic.get("predicates") or []
    if obj["object_type"] == "score_rule" and predicates:
        p = predicates[0]
        operator = norm(p.get("operator")); threshold = norm(p.get("threshold")); unit = norm(p.get("unit"))
        score_points = norm(logic.get("score_points"))
    elif logic.get("result_threshold"):
        r = logic["result_threshold"]
        operator = norm(r.get("operator")); threshold = norm(r.get("threshold")); unit = norm(r.get("unit"))
    return {
        "reviewed_text": norm(obj["content"]["clean_text"]),
        "reviewed_operator": operator,
        "reviewed_threshold": threshold,
        "reviewed_unit": unit,
        "reviewed_score_points": score_points,
    }


def review_snapshot_hash(fields: dict[str, str]) -> str:
    payload = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compare_snapshot(obj: dict[str, Any], review: dict[str, str]) -> tuple[bool, dict[str, Any]]:
    current = current_review_fields(obj)
    reviewed = {k: norm(review.get(k, "")) for k in current}
    mismatches = {k: {"reviewed": reviewed[k], "current": current[k]} for k in current if reviewed[k] != current[k]}
    return not mismatches, {"current": current, "reviewed": reviewed, "mismatches": mismatches}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--review", type=Path, required=True)
    ap.add_argument("--schema", type=Path, required=True)
    ap.add_argument("--reviewed-out", type=Path, required=True)
    ap.add_argument("--revise-out", type=Path, required=True)
    ap.add_argument("--rejected-out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--default-reviewer", default="")
    ap.add_argument("--default-date", default=str(date.today()))
    args = ap.parse_args()

    objects = read_jsonl(args.input)
    reviews = read_reviews(args.review)
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    reviewed_out: list[dict[str, Any]] = []
    revise_out: list[dict[str, Any]] = []
    rejected_out: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    stats = {"approved": 0, "revise": 0, "rejected": 0, "pending_clinical": 0, "pending_technical": 0, "snapshot_mismatch": 0}

    object_ids = {o["object_id"] for o in objects}
    for obj in objects:
        x = json.loads(json.dumps(obj))
        oid = x["object_id"]
        track = x["governance"]["review_track"]
        review = reviews.get(oid)
        if review is None:
            if track == "clinical":
                stats["pending_clinical"] += 1
                errors.append({"object_id": oid, "error": "missing_clinical_review_row"})
            else:
                stats["pending_technical"] += 1
            reviewed_out.append(x)
            continue

        decision = norm(review.get("review_decision", "")).lower()
        if decision not in ALLOWED:
            errors.append({"object_id": oid, "error": f"invalid_decision:{decision}"})
            reviewed_out.append(x); continue
        if track != "clinical":
            # Expert workbook is not allowed to approve technical-control objects.
            if decision:
                errors.append({"object_id": oid, "error": "clinical_workbook_cannot_review_technical_object"})
            stats["pending_technical"] += 1
            reviewed_out.append(x); continue
        if not decision:
            stats["pending_clinical"] += 1
            reviewed_out.append(x); continue

        snapshot_ok, detail = compare_snapshot(x, review)
        if not snapshot_ok:
            stats["snapshot_mismatch"] += 1
            errors.append({"object_id": oid, "error": "review_snapshot_mismatch", "details": detail["mismatches"]})
            reviewed_out.append(x); continue

        reviewer = norm(review.get("reviewer")) or args.default_reviewer
        review_date = norm(review.get("review_date")) or args.default_date
        if not reviewer:
            errors.append({"object_id": oid, "error": "missing_reviewer"}); reviewed_out.append(x); continue
        snap_hash = review_snapshot_hash(detail["current"])
        comment = norm(review.get("review_comment"))
        correction = norm(review.get("proposed_correction"))

        if decision == "approve":
            x["governance"]["validation_status"] = "approved"
            x["governance"]["validated_by"] = reviewer
            x["governance"]["validation_date"] = review_date
            x["governance"]["review_snapshot_hash"] = snap_hash
            # High-risk objects remain second-review pending.
            if x["risk"]["requires_second_review"]:
                x["governance"]["second_review"]["status"] = "pending"
            stats["approved"] += 1
        elif decision == "revise":
            if not correction and not comment:
                errors.append({"object_id": oid, "error": "revise_requires_correction_or_comment"})
                reviewed_out.append(x); continue
            x["governance"]["validation_status"] = "revise"
            x["governance"]["validated_by"] = reviewer
            x["governance"]["validation_date"] = review_date
            x["governance"]["review_snapshot_hash"] = snap_hash
            revise_out.append({"object": x, "proposed_correction": correction, "review_comment": comment})
            stats["revise"] += 1
        elif decision == "reject":
            if not comment:
                errors.append({"object_id": oid, "error": "reject_requires_comment"})
                reviewed_out.append(x); continue
            x["governance"]["validation_status"] = "rejected"
            x["governance"]["validated_by"] = reviewer
            x["governance"]["validation_date"] = review_date
            x["governance"]["review_snapshot_hash"] = snap_hash
            rejected_out.append(x)
            stats["rejected"] += 1

        verr = [e.message for e in validator.iter_errors(x)]
        if verr:
            errors.append({"object_id": oid, "error": "schema_error_after_review", "details": verr})
        reviewed_out.append(x)

    extras = sorted(set(reviews) - object_ids)
    if extras:
        errors.append({"error": "review_rows_without_object", "object_ids": extras})

    write_jsonl(args.reviewed_out, reviewed_out)
    args.revise_out.parent.mkdir(parents=True, exist_ok=True)
    args.revise_out.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in revise_out), encoding="utf-8")
    write_jsonl(args.rejected_out, rejected_out)
    report = {
        "input_objects": len(objects),
        "review_rows": len(reviews),
        "stats": stats,
        "errors": errors,
        "clinical_first_review_complete": stats["pending_clinical"] == 0 and stats["snapshot_mismatch"] == 0,
        "risk_objects_await_second_review": sum(
            1 for o in reviewed_out
            if o["governance"]["validation_status"] == "approved" and o["risk"]["requires_second_review"] and o["governance"]["second_review"]["status"] != "approved"
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not [e for e in errors if e.get("error") not in {"missing_clinical_review_row"}] else 2


if __name__ == "__main__":
    raise SystemExit(main())
