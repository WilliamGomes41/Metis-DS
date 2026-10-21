#!/usr/bin/env python3
"""Synthetic payload/call benchmark; no production data or database access."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.review_workboard_v1 import review_work_item
from tests.test_console_navigation_performance import NavigationProbe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=int, default=2)
    parser.add_argument("--objects", type=int, default=100)
    parser.add_argument("--evidence-items", type=int, default=64)
    args = parser.parse_args()
    results = []
    for mode in ("previous_duplicate_route", "batched_navigation"):
        probe = NavigationProbe(args.objects, args.documents, args.evidence_items)
        start = time.perf_counter()
        if mode == "previous_duplicate_route":
            # Reproduce summary enrichment followed by workboard reconstruction.
            for env in probe.envelopes.values():
                review_work_item(probe, account=probe.account, envelope=env)
            count = probe.old_review_count()
        else:
            count = probe.waiting_task_counts(probe.account["account_id"])["review"]
        results.append({"mode": mode, "seconds": round(time.perf_counter() - start, 6),
                        "review_documents": count, "read_calls": dict(probe.calls)})
    assert results[0]["review_documents"] == results[1]["review_documents"]
    print(json.dumps({"synthetic": True, "documents": args.documents,
                      "objects_per_document": args.objects,
                      "evidence_items_per_object": args.evidence_items,
                      "limitations": "Counting fake stores; excludes actual SQL, network and full readiness cost.",
                      "results": results}, indent=2))


if __name__ == "__main__":
    main()
