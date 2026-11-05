"""Turn probe_p1.py receipts into lane verdicts and perf numbers.

usage: python compare_p1.py <lanes-out-dir> <perf-out-dir> <evidence-dir>
Writes lanes.json and perf.json into <evidence-dir>. A lane passes only on the
rule the #974 plan names for it; a missing receipt is a failure.
"""
import json
import statistics
import sys
from pathlib import Path


def load(root, label, name):
    path = Path(root) / label / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def verdict(ok, **facts):
    return {"result": "PASS" if ok else "FAIL", **facts}


def lanes(lanes_dir, perf_dir):
    out = {}
    trunk, head = load(perf_dir, "trunk", "perf-1"), load(perf_dir, "head", "perf-1")
    if trunk and head:
        t, h = trunk["measured"], head["measured"]
        out["1-regression"] = verdict(
            t["page"]["content_sha256"] == h["page"]["content_sha256"]
            and len(t["page"]["problem_ids"]) == len(h["page"]["problem_ids"])
            and h["status"] == t["status"] == 200 and h["counters"].get("source_reconstruction_built", 0) <= 2,
            same_page=t["page"]["content_sha256"] == h["page"]["content_sha256"], problems=len(h["page"]["problem_ids"]),
            trunk_counters=t["counters"], head_counters=h["counters"])
    else:
        out["1-regression"] = verdict(False, missing="perf-1 receipts")

    def pair(name):
        return load(lanes_dir, "trunk", name), load(lanes_dir, "head", name)

    t, h = pair("rejections")
    if t and h:
        a, b = t["source_selection"], h["source_selection"]
        # /formation-problems redirects to this page; it carries the problems.
        out["2-rejections"] = verdict(a["page"]["content_sha256"] == b["page"]["content_sha256"]
                                      and sorted(a["page"]["hrefs"]) == sorted(b["page"]["hrefs"])
                                      and len(a["page"]["problem_ids"]) == len(b["page"]["problem_ids"]) > 0
                                      and a["status"] == b["status"] == 200,
                                      problems=len(b["page"]["problem_ids"]),
                                      redirect=b.get("location") or h["formation_problems"]["location"])
    t, h = pair("running")
    if h:
        s = h["source_selection"]
        out["3-running"] = verdict(s["status"] == 200 and s["page"]["progress_refresh"] and bool(s["page"]["progress_line"]),
                                   progress_line=s["page"]["progress_line"], trunk_status=t and t["source_selection"]["status"])
    t, h = pair("overview")
    if h:
        out["4-overview"] = verdict(h["source_selection"]["status"] == 200 and "source_reconstruction" not in h["phase_names"],
                                    phases=h["phase_names"])
    t, h = pair("not-named")
    if t and h:
        out["5-not-named"] = verdict(h["source_selection"]["error"] == t["source_selection"]["error"]
                                     and "reviewer_not_named_on_snapshot" in json.dumps(h["source_selection"]["error"])
                                     and h["source_selection"]["status"] == t["source_selection"]["status"],
                                     status=h["source_selection"]["status"], error=h["source_selection"]["error"])
    for name, lane in (("boom", "6-boom"), ("legacy", "7-legacy"), ("disposition", "8-disposition")):
        t, h = pair(name)
        if t and h:
            a, b = t["source_selection"], h["source_selection"]
            out[lane] = verdict(a["page"]["content_sha256"] == b["page"]["content_sha256"]
                                and sorted(a["page"]["hrefs"]) == sorted(b["page"]["hrefs"]) and a["status"] == b["status"] == 200
                                and b["error"] is None and b["outcome"] == "completed",
                                status=b["status"], same_page=a["page"]["content_sha256"] == b["page"]["content_sha256"],
                                head_counters=b["counters"], trunk_counters=a["counters"])
    t, h = pair("twice")
    if h:
        out["9-twice"] = verdict(h["first"]["counters"] == h["second"]["counters"]
                                 and h["first"]["page"]["sha256"] == h["second"]["page"]["sha256"],
                                 counters=h["first"]["counters"])
    t, h = pair("concurrent")
    if h:
        out["10-concurrent"] = verdict(h["statuses"] == [200, 200] and h["raw_problem_ids"][0] == h["raw_problem_ids"][1]
                                       and bool(h["raw_problem_ids"][0]), statuses=h["statuses"],
                                       problems=len(h["raw_problem_ids"][0]), counters=h["counters"])
    for lane in ("2-rejections", "3-running", "4-overview", "5-not-named", "6-boom", "7-legacy",
                 "8-disposition", "9-twice", "10-concurrent"):
        out.setdefault(lane, verdict(False, missing="receipt"))
    return out


def perf(perf_dir):
    rows = {"trunk": [], "head": []}
    for label in rows:
        for path in sorted((Path(perf_dir) / label).glob("perf-*.json")):
            m = json.loads(path.read_text())["measured"]
            rows[label].append({"run": path.stem, "elapsed_ms": m["elapsed_ms"],
                                "source_reconstruction_ms": (m["source_reconstruction"] or {}).get("inclusive_ms", 0.0),
                                "source_reconstruction_calls": (m["source_reconstruction"] or {}).get("calls", 0),
                                "counters": m["counters"]})

    if not rows["trunk"] or not rows["head"]:
        return {"verdict": "FAIL", "missing": "perf receipts", "runs": rows}

    def stats(label, key):
        values = [row[key] for row in rows[label]]
        return {"runs": len(values), "median": statistics.median(values), "min": min(values), "max": max(values)}

    result = {"metric": "GET /source-selection?document=<sid>, second open in a fresh process; "
                        "inclusive ms of phase source_reconstruction and request elapsed_ms",
              "runs": rows}
    for key in ("source_reconstruction_ms", "elapsed_ms"):
        result[key] = {label: stats(label, key) for label in rows}
    trunk_sr = result["source_reconstruction_ms"]["trunk"]["median"]
    head_sr = result["source_reconstruction_ms"]["head"]["median"]
    head_max = result["source_reconstruction_ms"]["head"]["max"]
    result["rule"] = "head source_reconstruction <= 1000 ms and <= 10% of trunk"
    result["head_vs_trunk_ratio"] = head_sr / trunk_sr if trunk_sr else None
    result["verdict"] = "PASS" if head_max <= 1000 and head_max <= 0.10 * trunk_sr else "FAIL"
    return result


if __name__ == "__main__":
    lanes_dir, perf_dir, evidence = sys.argv[1:4]
    Path(evidence, "lanes.json").write_text(json.dumps(lanes(lanes_dir, perf_dir), indent=1, sort_keys=True))
    Path(evidence, "perf.json").write_text(json.dumps(perf(perf_dir), indent=1, sort_keys=True))
