"""Bounded, experimental comparisons of observed requests; no I/O or decisions.

Reference and evaluation windows never overlap. Findings describe sustained
changes in observed completed work, not probabilities, causes or forecasts.
"""
from __future__ import annotations

from collections import defaultdict
import math
from statistics import median

from src.telemetry.hub import parse_ts

BIN_SECONDS = 300
REFERENCE_BINS = 12
EVALUATION_BINS = 3
MIN_SAMPLES = 5
MAX_COHORTS = 30
MAX_FINDINGS = 20


def _number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def historical_deviations(requests, *, now, filters, quality):
    start = now - (REFERENCE_BINS + EVALUATION_BINS) * BIN_SECONDS
    split = now - EVALUATION_BINS * BIN_SECONDS
    result = {
        "version": "median_mad_v1", "mode": "experimental_observation",
        "status": "insufficient", "reason": "insufficient_history",
        "reference": {"since": start, "until": split},
        "evaluation": {"since": split, "until": now},
        "bin_seconds": BIN_SECONDS, "minimum_samples_per_bin": MIN_SAMPLES,
        "coverage": "not_established", "evaluated_metrics": 0,
        "eligible_cohorts": 0, "unsupported_cohorts": 0, "omitted_cohorts": 0,
        "omitted_findings": 0, "excluded_requests": 0,
        "unsupported_phase_metrics": 0, "findings": [],
        "uncertainty": "Alleen waargenomen afgeronde verzoeken; meetdekking, documentmix en configuratie-effecten zijn niet vastgesteld. Samenhang bewijst geen oorzaak.",
    }
    if not quality or quality.get("status") != "no_known_loss":
        result["reason"] = "measurement_quality"
        return result
    if any(filters.get(k) for k in ("q", "error", "state", "status")):
        result["reason"] = "selection_bias"
        return result
    cohorts = defaultdict(list)
    invalid_cohorts = set()
    for request in requests:
        if any(filters.get(k) and getattr(request, k) != filters[k]
               for k in ("route", "method", "commit")):
            continue
        finish = request.finished or {}
        stamp = parse_ts(finish.get("ts") or finish.get("timestamp"))
        if stamp is None or not start <= stamp < now:
            continue
        key = (request.route, request.method, request.commit)
        elapsed = finish.get("elapsed_ms")
        starts = [parse_ts(e.get("ts") or e.get("timestamp")) for e in request.events
                  if e.get("event") == "request_started"]
        if (not request.responded() or not _number(elapsed) or not starts
                or any(t is None or t > stamp for t in starts)
                or request.route == "?" or request.commit in ("unknown", "", None)):
            result["excluded_requests"] += 1
            invalid_cohorts.add(key)
            continue
        index = min(REFERENCE_BINS + EVALUATION_BINS - 1,
                    int((stamp - start) // BIN_SECONDS))
        cohorts[key].append((index, float(elapsed), finish))
    keys = sorted(cohorts, key=lambda k: (-len(cohorts[k]), k))
    result["omitted_cohorts"] = max(0, len(keys) - MAX_COHORTS)
    for key in keys[:MAX_COHORTS]:
        rows = cohorts[key]
        bins = [[] for _ in range(REFERENCE_BINS + EVALUATION_BINS)]
        for index, elapsed, finish in rows:
            bins[index].append((elapsed, finish))
        if key in invalid_cohorts or any(len(b) < MIN_SAMPLES for b in bins):
            result["unsupported_cohorts"] += 1
            continue
        result["eligible_cohorts"] += 1
        metrics = {
            "latency_p50_ms": ([median([e for e, _ in b]) for b in bins], 25.0, "ms"),
            "latency_spread_ms": ([_spread([e for e, _ in b]) for b in bins], 20.0, "ms"),
        }
        phase_names = sorted({name for _, _, f in rows
                              if isinstance(f.get("phases"), dict)
                              for name in f["phases"] if isinstance(name, str)})
        for name in phase_names:
            values = []
            for b in bins:
                fractions = []
                for elapsed, finish in b:
                    phases = finish.get("phases")
                    phase = phases.get(name) if isinstance(phases, dict) else None
                    value = phase.get("exclusive_ms") if isinstance(phase, dict) else None
                    if (not finish.get("phase_tree_truncated") and elapsed > 0
                            and _number(value) and value <= elapsed):
                        fractions.append(value / elapsed)
                if len(fractions) != len(b):
                    break
                values.append(median(fractions))
            if len(values) == len(bins):
                metrics["phase_share:" + name] = (values, 0.10, "fraction")
            else:
                result["unsupported_phase_metrics"] += 1
        for metric, (values, floor, unit) in metrics.items():
            result["evaluated_metrics"] += 1
            reference = values[:REFERENCE_BINS]
            observed = values[REFERENCE_BINS:]
            center = median(reference)
            mad = median([abs(v - center) for v in reference])
            threshold = max(floor, 0.25 * center, 4 * 1.4826 * mad)
            # Three consecutive elevated bins are required, not one pooled spike.
            if not all(v > center + threshold for v in observed):
                continue
            result["findings"].append({
                "cohort": dict(zip(("route", "method", "commit"), key)),
                "metric": metric, "unit": unit, "baseline": round(center, 4),
                "baseline_mad": round(mad, 4), "minimum_change": round(threshold, 4),
                "observed": round(median(observed), 4),
                "evaluation_values": [round(v, 4) for v in observed],
                "reference_samples": sum(len(b) for b in bins[:REFERENCE_BINS]),
                "evaluation_samples": sum(len(b) for b in bins[REFERENCE_BINS:]),
                "samples_per_bin": [len(b) for b in bins],
                "consequence": "Aanhoudende verschuiving kan de verwerkingsmarge verkleinen; een operationele grens is niet vastgesteld.",
                "action": "Controleer verzoekdetails, documentmix, configuratie en afhankelijkheden voor deze route en commit voordat u ingrijpt.",
                "time_to_limit_seconds": None, "actionable_lead_seconds": None,
            })
    count = len(result["findings"])
    result["findings"] = result["findings"][:MAX_FINDINGS]
    result["omitted_findings"] = max(0, count - MAX_FINDINGS)
    if result["evaluated_metrics"]:
        result["status"] = "observed_deviation" if count else "no_sustained_deviation_observed"
        result["reason"] = None
    return result


def _spread(values):
    ordered = sorted(values)
    return ordered[math.ceil(0.9 * len(ordered)) - 1] - median(ordered)
