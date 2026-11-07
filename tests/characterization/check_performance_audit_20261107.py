"""Recompute the published audit aggregates from its retained observations.

Run with: python tests/characterization/check_performance_audit_20261107.py
This checks the audit artifact, not runtime performance or production recovery.
"""
# release-control-evidence: scope/belofte retained observations reproduce claims
# release-control-evidence: slop one canonical plan and no runtime implementation
# release-control-evidence: releasebewijs reproducible artifact check, not deployment

import json
import math
from pathlib import Path
import re
from statistics import median


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/performance-audit-2026-11-07"


def check():
    ko4 = json.loads((EVIDENCE / "ko4-recomputed.json").read_text())
    observations = ko4["observations"]
    summary = ko4["summary"]
    assert len(observations) == summary["raw_observations"] == 80
    assert summary["threshold_ms"] == 5000
    groups = {(row["side"], row["operation"]) for row in observations}
    assert groups == {(group["side"], group["operation"]) for group in summary["groups"]}
    for group in summary["groups"]:
        rows = [row for row in observations
                if (row["side"], row["operation"]) == (group["side"], group["operation"])]
        durations = sorted(row["wall_ms"] for row in rows)
        assert len(rows) == group["n"] == 20
        assert sum(value > 5000 for value in durations) == group["over_5s"]
        expected = {"median_ms": median(durations), "min_ms": durations[0],
                    "max_ms": durations[-1], "p95_ms": durations[math.ceil(.95 * len(rows)) - 1]}
        for field, value in expected.items():
            assert math.isclose(value, group[field], rel_tol=1e-12), field
        for field, source in [("statuses", "status"), ("queries", "db_queries"),
                              ("connections", "physical_connections")]:
            assert sorted({row[source] for row in rows}) == group[field], field

    reuse = json.loads((EVIDENCE / "source-reuse-current.json").read_text())
    samples = [run["resume"]["seconds"] for run in reuse["raw_runs"]]
    assert len(samples) == reuse["repeats"] == 5
    assert samples == reuse["resume_seconds"]["samples"]
    for field, value in [("median", median(samples)), ("min", min(samples)), ("max", max(samples))]:
        assert math.isclose(value, reuse["resume_seconds"][field], rel_tol=1e-12)
    assert reuse["external_provider_calls"] == 0
    for run in reuse["raw_runs"]:
        assert run["tasks"] == 130
        assert run["provider_calls"] == reuse["provider_calls_per_run"] == 131
        assert run["first_committed_task_reused"] and run["first_result_hash_unchanged"]

    plan = ROOT / "docs/change-contracts/959-performance-implementation-plan-2026-11-07.md"
    text = plan.read_text()
    for prefix, count in [("A", 6), ("R", 12)]:
        for number in range(1, count + 1):
            assert re.search(r"\b" + prefix + str(number) + r"\b", text)
    for link in re.findall(r"\]\(([^)]+)\)", text):
        if not link.startswith(("https://", "http://", "#")):
            assert (plan.parent / link.split("#", 1)[0]).resolve().is_file(), link
    pointer = (ROOT / "docs/architecture/performance-implementation-plan-2026-11-07.md").read_text()
    assert "../change-contracts/" + plan.name in pointer
    print("PASS: 80 KO4 observations, 5 resume runs, all audit IDs and canonical plan links.")


if __name__ == "__main__":
    check()
