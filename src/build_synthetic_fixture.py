#!/usr/bin/env python3
"""Build the explicit synthetic retrieval fixture used by local demos/tests.

This utility never writes canonical or published state. It takes the current
semantic objects, copies them in memory, marks the copies as approved solely for
fixture projection, clears unresolved uncertainty on those copies, and wraps
all records in the release id SYNTHETIC-TEST-ONLY.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from .retrieval_projection_v2 import build_projection, write_jsonl


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build(objects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    envelopes = []
    for obj in objects:
        o = copy.deepcopy(obj)
        o["governance"]["validation_status"] = "approved"
        o["uncertainty"] = {"has_uncertainty": False, "items": []}
        envelopes.append({
            "knowledge_object": o,
            "publication": {
                "release_id": "SYNTHETIC-TEST-ONLY",
                "release_version": "fixture-v2",
                "published_at": "2026-08-19T00:00:00Z",
            },
        })
    return build_projection(envelopes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    rows, blocked = build(read_jsonl(args.input))
    write_jsonl(rows, args.out)
    report = {
        "status": "PASS" if not blocked else "BLOCKED",
        "synthetic_fixture": True,
        "release_id": "SYNTHETIC-TEST-ONLY",
        "input_objects": len(read_jsonl(args.input)),
        "retrieval_records": len(rows),
        "blocked": blocked,
        "warning": "Fixture records are not approved or published V&VN knowledge.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not blocked else 2


if __name__ == "__main__":
    raise SystemExit(main())
