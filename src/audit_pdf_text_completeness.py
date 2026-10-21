#!/usr/bin/env python3
"""Fail-closed audit of PDF text-layer completeness against reviewed anchors."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def normalize(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def audit(rows: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    pages: dict[int, list[str]] = {}
    for row in rows:
        page = row.get("source_page")
        if isinstance(page, int):
            pages.setdefault(page, []).append(str(row.get("clean_text", "")))

    checks = []
    for assertion in spec.get("assertions", []):
        page = assertion.get("source_page")
        anchor_id = str(assertion.get("anchor_id", "")).strip()
        text = str(assertion.get("required_text", "")).strip()
        errors = []
        if not anchor_id:
            errors.append("anchor_id_missing")
        if not isinstance(page, int) or page < 1:
            errors.append("source_page_invalid")
        if not text:
            errors.append("required_text_missing")
        page_text = normalize("\n".join(pages.get(page, []))) if isinstance(page, int) else ""
        found = not errors and normalize(text) in page_text
        checks.append(
            {
                "anchor_id": anchor_id,
                "source_page": page,
                "status": "PASS" if found else "FAIL",
                "errors": errors or ([] if found else ["required_visual_text_absent_from_text_layer"]),
            }
        )

    spec_errors = []
    if not spec.get("reviewed_by"):
        spec_errors.append("reviewed_by_missing")
    if not spec.get("reviewed_at"):
        spec_errors.append("reviewed_at_missing")
    if spec.get("review_status") != "approved":
        spec_errors.append("visual_review_not_approved")
    if not checks:
        spec_errors.append("assertions_missing")

    failed = sum(check["status"] == "FAIL" for check in checks)
    passed = len(checks) - failed
    status = "PASS" if not spec_errors and not failed else "FAIL"
    return {
        "audit_version": "pdf-text-completeness-v1.0.0",
        "status": status,
        "publication_eligibility": "eligible_for_transform" if status == "PASS" else "blocked_text_layer_incomplete",
        "summary": {"total": len(checks), "passed": passed, "failed": failed},
        "spec_errors": spec_errors,
        "checks": checks,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fragments", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(_read_jsonl(args.fragments), json.loads(args.spec.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
