"""Run probe_review_open.py in a trunk and a head tree and judge perf or the live lanes.

    METIS_TEST_POSTGRES_DSN=... python evidence/974-p2/run_probe.py \
        --trunk <tree at origin/main> --head <tree at the PR head> --mode perf --rounds 10 --out <dir>

Each run is a fresh pytest process in that tree, so it executes that tree's code.
Rounds alternate the order (trunk first, then head first) to spread drift evenly.
"""
import argparse
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

PROBE = Path(__file__).with_name("probe_review_open.py")
TMP_NAME = "proto_974_p2_tmp.py"


def run(tree, mode, out_file):
    target = Path(tree) / "tests" / TMP_NAME
    shutil.copyfile(PROBE, target)
    try:
        started = time.monotonic()
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"tests/{TMP_NAME}"],
                                cwd=tree, env={**os.environ, "PROBE_MODE": mode, "PROBE_OUT": str(out_file)},
                                capture_output=True, text=True, timeout=900)
    finally:
        target.unlink(missing_ok=True)
    if result.returncode:
        raise SystemExit(f"probe failed in {tree}:\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
    return json.loads(Path(out_file).read_text()), round(time.monotonic() - started, 1)


def spread(values):
    ordered = sorted(values)
    q = statistics.quantiles(ordered, n=4) if len(ordered) > 1 else [ordered[0]] * 3
    return {"n": len(values), "median": round(statistics.median(values), 3), "min": ordered[0], "max": ordered[-1],
            "p25": round(q[0], 3), "p75": round(q[2], 3)}


def perf(args, out):
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    sides = {"trunk": [], "head": []}
    order_log = []
    for index in range(args.rounds):
        order = ("trunk", "head") if index % 2 == 0 else ("head", "trunk")
        for side in order:
            data, seconds = run(getattr(args, side), "perf", raw / f"perf-{side}-{index + 1:02d}.json")
            sides[side].append(data["runs"])
            order_log.append({"round": index + 1, "side": side, "process_seconds": seconds,
                              "elapsed_ms": [r["elapsed_ms"] for r in data["runs"]]})
            print(order_log[-1], flush=True)
    summary = {}
    for side, rounds in sides.items():
        every = [r["elapsed_ms"] for runs in rounds for r in runs]
        per_round = [statistics.median(r["elapsed_ms"] for r in runs) for runs in rounds]
        summary[side] = {"all_requests": spread(every), "per_round_median": spread(per_round),
                         "db_json_bytes": sorted({r["db_json_bytes"] for runs in rounds for r in runs}),
                         "statuses": sorted({r["status"] for runs in rounds for r in runs})}
    trunk = summary["trunk"]["per_round_median"]["median"]
    head = summary["head"]["per_round_median"]["median"]
    # Paired by round: both sides ran back to back, so shared drift cancels.
    ratios = [statistics.median(r["elapsed_ms"] for r in h) / statistics.median(r["elapsed_ms"] for r in t)
              for h, t in zip(sides["head"], sides["trunk"])]
    rng = random.Random(974)
    boot = sorted(statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(10000))
    low, high = (boot[249] - 1) * 100, (boot[9749] - 1) * 100
    # Pass needs the whole interval within +2 %; fail needs it wholly above; else the noise decides.
    verdict = "pass" if high <= 2 else "fail" if low > 2 else "inconclusive"
    return {"metric": "median elapsed_ms of GET /review?document=<sid>, 2,000-paragraph fixture",
            "rule": "head median <= trunk median * 1.02; verdict from a 95 % bootstrap interval "
                    "of the paired per-round head/trunk median ratio",
            "rounds": args.rounds, "requests_per_round": len(sides["head"][0]),
            "trunk": summary["trunk"], "head": summary["head"],
            "head_vs_trunk_percent": round((head / trunk - 1) * 100, 2),
            "paired_ratio_percent": {"per_round": [round((r - 1) * 100, 2) for r in ratios],
                                     "median": round((statistics.median(ratios) - 1) * 100, 2),
                                     "ci95_low": round(low, 2), "ci95_high": round(high, 2)},
            "verdict": verdict, "order": order_log,
            "attributed_request": sides["head"][-1][-1]}


def lanes(args, out):
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    trunk, _ = run(args.trunk, "lanes", raw / "lanes-trunk.json")
    head, _ = run(args.head, "lanes", raw / "lanes-head.json")
    receipts = {}

    def sums(row):
        return isinstance(row.get("db_json_bytes_by_phase"), dict) and row["by_phase_sum"] == row["db_json_bytes"]

    t, h = trunk["review-document"], head["review-document"]
    receipts["regression"] = {"trunk": t, "head": h, "pass": bool(
        t["db_json_bytes"] and abs(h["db_json_bytes"] - t["db_json_bytes"]) <= 0.01 * t["db_json_bytes"]
        and t["db_json_bytes_by_phase"] is None and isinstance(h["db_json_bytes_by_phase"], dict))}
    keys = set(h["db_json_bytes_by_phase"] or {})
    receipts["review-document"] = {"head": h, "pass": sums(h) and {
        "review_render/source_views_read_records", "document_load"} <= keys}
    receipts["formation"] = {"head": head["formation"], "pass": sums(head["formation"])}
    receipts["save"] = {"trunk": trunk.get("save"), "head": head.get("save"),
                        "pass": "status" in head.get("save", {}) and sums(head["save"])
                        and head["save"]["status"] == trunk["save"]["status"]}
    receipts["no-json"] = {"head": head["no-json"], "pass": head["no-json"]["db_json_bytes_by_phase"] == {}
                           and not head["no-json"]["db_json_bytes"]}
    error = head.get("error", {})
    receipts["error"] = {"head": error, "error-form": head.get("error-form"), "conflict": head.get("conflict"),
                         "pass": bool(error.get("error")) and isinstance(error.get("db_json_bytes_by_phase"), dict)}
    truncated = head.get("truncated", {})
    receipts["truncated"] = {"head": truncated, "pass": bool(
        truncated.get("db_json_bytes_by_phase_truncated") and truncated.get("phase_tree_truncated")
        and len(truncated["db_json_bytes_by_phase"]) <= truncated["max_tree_nodes"]
        and "<overflow>" in truncated["db_json_bytes_by_phase"] and sums(truncated))}
    receipts["privacy"] = {"head": head["privacy"],
                           "pass": not any(head["privacy"]["request_event_hits"].values())}
    receipts["concurrent"] = {"head": head["concurrent"], "pass": all(sums(row) for row in head["concurrent"])
                              and len({row["db_json_bytes"] for row in head["concurrent"]}) == 2}
    for name, receipt in receipts.items():
        (out / f"{name}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
    return {name: receipt["pass"] for name, receipt in receipts.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trunk", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--mode", choices=("perf", "lanes"), required=True)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.mode == "perf":
        result = perf(args, out)
        (out / "perf.json").write_text(json.dumps(result, indent=2, sort_keys=True))
        print(json.dumps({k: result[k] for k in ("head_vs_trunk_percent", "paired_ratio_percent", "verdict")}))
    else:
        print(json.dumps(lanes(args, out), indent=2))


if __name__ == "__main__":
    main()
