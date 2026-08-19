#!/usr/bin/env python3
"""Prepare validated V&VN knowledge objects for authoritative storage.

This step deliberately does NOT create embeddings. It validates the publication gate:
only objects with governance.validation_status == 'approved' and a reviewer/date
are eligible for storage in the approved dataset.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
    return rows


def is_publishable(obj: dict[str, Any]) -> tuple[bool, str]:
    gov = obj.get("governance") or {}
    if gov.get("validation_status") != "approved":
        return False, "status_not_approved"
    if not gov.get("validated_by"):
        return False, "missing_validated_by"
    if not gov.get("validation_date"):
        return False, "missing_validation_date"
    if not obj.get("object_id") or not obj.get("document_id"):
        return False, "missing_identity"
    return True, "approved"


def partition(rows: Iterable[dict[str, Any]]):
    approved, blocked = [], []
    for obj in rows:
        ok, reason = is_publishable(obj)
        if ok:
            approved.append(obj)
        else:
            blocked.append({
                "object_id": obj.get("object_id"),
                "reason": reason,
                "validation_status": (obj.get("governance") or {}).get("validation_status"),
            })
    return approved, blocked


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--approved-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    rows = read_jsonl(args.input)
    approved, blocked = partition(rows)
    write_jsonl(args.approved_out, approved)

    report = {
        "input_objects": len(rows),
        "approved_objects": len(approved),
        "blocked_objects": len(blocked),
        "embedding_ready": bool(approved),
        "blocked": blocked,
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["input_objects", "approved_objects", "blocked_objects", "embedding_ready"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
