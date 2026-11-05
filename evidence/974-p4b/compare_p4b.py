"""Summarise probe_p4b.py receipts: median (min to max) per side, read counts, page hashes.

usage: python compare_p4b.py <receipts-dir> > perf.json
"""
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
ROUTES = ("post_review", "get_repair")


def receipts(label):
    return [json.loads(p.read_text()) for p in sorted((root / label).glob("perf-[0-9]*.json"))]


def spread(values):
    return {"median": round(statistics.median(values), 1), "min": round(min(values), 1),
            "max": round(max(values), 1), "runs": len(values)}


def side(label):
    rows = receipts(label)
    out = {}
    for route in ROUTES:
        measured = [r[route]["measured"] for r in rows]
        calls = [m["calls"] for m in measured]
        out[route] = {
            "request_elapsed_ms": spread([m["elapsed_ms"] for m in measured]),
            "render_ms": spread([c["render_ms"][0] for c in calls]),
            "request_db_queries": sorted({m["db"]["db_queries"] for m in measured}),
            "render_db_queries": sorted({c["render_db_queries"][0] for c in calls}),
            "render_db_json_bytes": sorted({c["render_db_json_bytes"][0] for c in calls}),
            "render_calls": sorted({json.dumps(c["render"], sort_keys=True) for c in calls}),
            "payload_copy_calls": sorted({(m["phases"].get("payload_copy") or {}).get("calls", 0) for m in measured}),
            "page_sha256": sorted({m["page_sha256"] for m in measured}),
            "options": sorted({m["options"] for m in measured}),
        }
    return out


result = {label: side(label) for label in ("trunk", "head")}
result["page_identical"] = {route: result["trunk"][route]["page_sha256"] == result["head"][route]["page_sha256"]
                            and len(result["head"][route]["page_sha256"]) == 1 for route in ROUTES}
json.dump(result, sys.stdout, indent=1, sort_keys=True)
print()
