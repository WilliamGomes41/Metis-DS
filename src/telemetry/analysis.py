"""Turn hub events into understanding: requests, trends, error groups, correlations.

Pure functions over event dicts; no I/O. Requests are rebuilt from their
``request_started`` / ``request_running`` / ``request_finished`` events. A request
without a finish whose heartbeats stopped is reported as aborted (worker crash,
timeout kill or restart), the one failure no single event can show.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from src.telemetry.hub import parse_ts

HEARTBEAT_SECONDS = 15
ABORTED_AFTER_SECONDS = 3 * HEARTBEAT_SECONDS + 5
NICE_BUCKETS = (60, 300, 900, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 86400)
SLOW_PERCENTILE = 95


@dataclass
class Request:
    request_id: str
    started: float
    route: str = "?"
    method: str = "GET"
    commit: str = "unknown"
    pid: int | None = None
    trace_id: str | None = None
    attempt_id: str | None = None
    doc_ref: str | None = None
    finished: dict | None = None
    last_seen: float = 0.0
    last_phase: str | None = None
    heartbeats: int = 0
    events: list = field(default_factory=list)

    def state(self, now: float) -> str:
        if self.finished is not None:
            outcome = self.finished.get("outcome") or "completed"
            status = self.finished.get("status") or 0
            if outcome == "exception" or (isinstance(status, int) and status >= 500):
                return "error"
            if outcome in ("cancelled", "incomplete"):
                return outcome
            return "ok"
        return "aborted" if now - self.last_seen > ABORTED_AFTER_SECONDS else "running"

    def responded(self) -> bool:
        """A response was completed: only these durations are response times."""
        return self.finished is not None and (self.finished.get("outcome") or "completed") == "completed"

    def duration_ms(self) -> float:
        if self.finished is not None and isinstance(self.finished.get("elapsed_ms"), (int, float)):
            return float(self.finished["elapsed_ms"])
        return max(0.0, (self.last_seen - self.started) * 1000)

    @property
    def status(self) -> int | None:
        value = (self.finished or {}).get("status")
        return value if isinstance(value, int) else None

    @property
    def error(self) -> dict | None:
        value = (self.finished or {}).get("error")
        return value if isinstance(value, dict) else None

    def phases(self) -> dict:
        value = (self.finished or {}).get("phases")
        return value if isinstance(value, dict) else {}

    def db(self) -> dict:
        value = (self.finished or {}).get("db")
        return value if isinstance(value, dict) else {}


def build_requests(events: Iterable[dict]) -> tuple[dict[str, Request], list[dict]]:
    """Requests by id, plus every non-request event (logs, errors, process, domain)."""
    requests: dict[str, Request] = {}
    other: list[dict] = []
    for event in events:
        stamp = parse_ts(event.get("ts") or event.get("timestamp"))
        if stamp is None:
            continue
        event["_t"] = stamp
        name = event.get("event")
        rid = event.get("request_id")
        if name in ("request_started", "request_running", "request_finished") and isinstance(rid, str):
            request = requests.get(rid)
            if request is None:
                request = requests[rid] = Request(rid, stamp)
            request.started = min(request.started, stamp)
            request.last_seen = max(request.last_seen, stamp)
            for key in ("route", "method", "trace_id", "attempt_id", "doc_ref", "commit", "pid"):
                value = event.get(key)
                if value and (key != "route" or name == "request_finished" or request.route == "?"):
                    setattr(request, key, value)
            if name == "request_running":
                request.heartbeats += 1
                request.last_phase = event.get("phase")
            elif name == "request_finished":
                request.finished = event
            request.events.append(event)
        else:
            other.append(event)
    return requests, other


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return round(ordered[rank], 1)


def bucket_seconds(window: float) -> int:
    target = max(60.0, window / 48)
    return next((size for size in NICE_BUCKETS if size >= target), NICE_BUCKETS[-1])


def matches(request: Request, filters: dict[str, str], now: float) -> bool:
    if filters.get("route") and request.route != filters["route"]:
        return False
    if filters.get("method") and request.method != filters["method"]:
        return False
    if filters.get("commit") and request.commit != filters["commit"]:
        return False
    state = filters.get("state")
    if state and request.state(now) != state:
        return False
    status_class = filters.get("status")
    if status_class:
        status = request.status
        if status is None or str(status)[0] != status_class[0]:
            return False
    fingerprint = filters.get("error")
    if fingerprint and group_key(request, now) != fingerprint:
        return False
    query = (filters.get("q") or "").strip().lower()
    if query:
        haystack = [request.request_id, request.trace_id, request.attempt_id, request.doc_ref,
                    (request.error or {}).get("fingerprint"), (request.error or {}).get("code")]
        if not any(isinstance(value, str) and query in value.lower() for value in haystack):
            return False
    return True


def group_key(request: Request, now: float) -> str | None:
    """Error group of a request: exception fingerprint, handled code or abort."""
    state = request.state(now)
    error = request.error
    if error and error.get("fingerprint"):
        return str(error["fingerprint"])
    if error and error.get("code"):
        return "code:" + str(error["code"])
    if state == "aborted":
        return "aborted:" + request.route
    if state == "error":
        return f"status:{request.status or 'none'}:{request.route}"
    return None


def summarize(events: list[dict], *, filters: dict[str, str] | None = None, now: float,
              since: float) -> dict[str, Any]:
    from src.telemetry.playbook import guidance_for_group, insights
    filters = filters or {}
    requests_by_id, other = build_requests(events)
    all_requests = [r for r in requests_by_id.values() if r.started >= since]
    requests = [r for r in all_requests if matches(r, filters, now)]
    durations = [r.duration_ms() for r in requests if r.responded()]
    errored = [r for r in requests if r.state(now) in ("error", "aborted")]
    size = bucket_seconds(max(60.0, now - since))
    start_bucket = int(since // size) * size
    buckets = {start_bucket + i * size: [] for i in range(int((now - start_bucket) // size) + 1)}
    for request in requests:
        key = int(request.started // size) * size
        buckets.setdefault(key, []).append(request)
    series = []
    for key in sorted(buckets):
        items = buckets[key]
        times = [r.duration_ms() for r in items if r.responded()]
        series.append({"t": key, "count": len(items),
                       "errors": sum(r.state(now) in ("error", "aborted") for r in items),
                       "p50": percentile(times, 50), "p95": percentile(times, 95)})
    slow_threshold = percentile(durations, SLOW_PERCENTILE)
    lock_waits = [float(r.phases().get("store_lock_wait", {}).get("inclusive_ms", 0))
                  for r in requests if "store_lock_wait" in r.phases()]
    # Standalone logs and crashes follow the same window, and under request filters only
    # those of the matched requests remain (a fingerprint filter also keeps its own group).
    standalone = [event for event in other if event["_t"] >= since]
    active = {key: value for key, value in filters.items() if value}
    if active:
        matched = {request.request_id for request in requests}
        standalone = [event for event in standalone if event.get("request_id") in matched
                      or (set(active) == {"error"} and _standalone_key(event) == active["error"])]
    groups = _error_groups(requests, standalone, now, size, start_bucket, len(series))
    for group in groups:
        group["guidance"] = guidance_for_group(group)
    routes = _routes(requests, now)
    phases = _phases(requests)
    commits = _commits(requests, now)
    correlations = _correlations(requests, now, slow_threshold)
    summary = {
        "window": {"since": since, "until": now, "bucket_seconds": size},
        "filters": filters,
        "kpis": {
            "requests": len(requests),
            "errors": len(errored),
            "error_rate": round(len(errored) / len(requests), 4) if requests else 0.0,
            "p50_ms": percentile(durations, 50), "p95_ms": percentile(durations, 95),
            "p99_ms": percentile(durations, 99),
            "aborted": sum(r.state(now) == "aborted" for r in requests),
            "running": sum(r.state(now) == "running" for r in requests),
            "lock_wait_p95_ms": percentile(lock_waits, 95),
            "slow_threshold_ms": slow_threshold,
        },
        "series": series,
        "routes": routes,
        "phases": phases,
        "errors": groups,
        "commits": commits,
        "correlations": correlations,
        "options": {
            "routes": sorted({r.route for r in all_requests}),
            "commits": [c["commit"] for c in commits],
        },
        "requests": [_request_row(r, now) for r in
                     sorted(requests, key=lambda r: r.started, reverse=True)[:200]],
        "slowest": [_request_row(r, now) for r in
                    sorted(requests, key=lambda r: r.duration_ms(), reverse=True)[:10]],
        "process": _process_events(other, since),
        "telemetry": {"events": sum(1 for event in events if event.get("_t", 0) >= since)},
    }
    summary["insights"] = insights(summary)
    return summary


def _request_row(request: Request, now: float) -> dict[str, Any]:
    error = request.error or {}
    return {"request_id": request.request_id, "started": request.started, "route": request.route,
            "method": request.method, "status": request.status, "state": request.state(now),
            "duration_ms": round(request.duration_ms(), 1), "commit": request.commit,
            "doc_ref": request.doc_ref, "attempt_id": request.attempt_id,
            "trace_id": request.trace_id, "error_type": error.get("type"),
            "error_code": error.get("code"), "group": group_key(request, now),
            "db_queries": request.db().get("db_queries"), "last_phase": request.last_phase}


def _routes(requests: list[Request], now: float) -> list[dict[str, Any]]:
    by_route: dict[str, list[Request]] = defaultdict(list)
    for request in requests:
        by_route[request.route].append(request)
    rows = []
    for route, items in by_route.items():
        times = [r.duration_ms() for r in items if r.responded()]
        exclusive: Counter = Counter()
        for request in items:
            for name, values in request.phases().items():
                if isinstance(values, dict):
                    exclusive[name] += float(values.get("exclusive_ms") or 0)
        queries = [r.db().get("db_queries") for r in items if isinstance(r.db().get("db_queries"), int)]
        errors = sum(r.state(now) in ("error", "aborted") for r in items)
        rows.append({"route": route, "method": Counter(r.method for r in items).most_common(1)[0][0],
                     "count": len(items), "errors": errors,
                     "error_rate": round(errors / len(items), 4),
                     "p50_ms": percentile(times, 50), "p95_ms": percentile(times, 95),
                     "p99_ms": percentile(times, 99), "max_ms": round(max(times), 1) if times else None,
                     "top_phase": exclusive.most_common(1)[0][0] if exclusive else None,
                     "avg_db_queries": round(sum(queries) / len(queries), 1) if queries else None})
    return sorted(rows, key=lambda row: (row["errors"], row["p95_ms"] or 0), reverse=True)


def _phases(requests: list[Request]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"exclusive_ms": 0.0, "calls": 0, "requests": 0})
    inclusive: dict[str, list[float]] = defaultdict(list)
    for request in requests:
        for name, values in request.phases().items():
            if not isinstance(values, dict):
                continue
            totals[name]["exclusive_ms"] += float(values.get("exclusive_ms") or 0)
            totals[name]["calls"] += int(values.get("calls") or 0)
            totals[name]["requests"] += 1
            inclusive[name].append(float(values.get("inclusive_ms") or 0))
    grand = sum(item["exclusive_ms"] for item in totals.values()) or 1.0
    rows = [{"phase": name, "exclusive_ms": round(item["exclusive_ms"], 1),
             "share": round(item["exclusive_ms"] / grand, 4), "calls": item["calls"],
             "requests": item["requests"], "p95_inclusive_ms": percentile(inclusive[name], 95)}
            for name, item in totals.items()]
    return sorted(rows, key=lambda row: row["exclusive_ms"], reverse=True)


def _standalone_key(event: dict) -> str | None:
    """Group key of a WARNING+ log or an unhandled exception; None for other events."""
    error = event.get("error") if isinstance(event.get("error"), dict) else None
    if event.get("kind") == "log" and event.get("level") in ("ERROR", "CRITICAL", "WARNING"):
        message = str(event.get("message") or "")[:80]
        template = message.split(" ", 1)[0] if message else "log"
        return (error or {}).get("fingerprint") or f"log:{event.get('logger')}:{template}"
    if event.get("event") == "unhandled_exception" and error:
        return error.get("fingerprint") or "unhandled"
    return None


def _error_groups(requests: list[Request], other: list[dict], now: float, size: int,
                  start_bucket: float, bucket_count: int) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    def group(key: str, *, label: str, kind: str, error: dict | None) -> dict[str, Any]:
        if key not in groups:
            groups[key] = {"key": key, "label": label, "kind": kind, "count": 0,
                           "first_seen": None, "last_seen": None, "routes": Counter(),
                           "commits": Counter(), "examples": [], "frames": [],
                           "error_type": (error or {}).get("type"), "code": (error or {}).get("code"),
                           "spark": [0] * max(1, bucket_count), "handled": bool((error or {}).get("handled"))}
        return groups[key]

    def add(item: dict[str, Any], stamp: float, route: str | None, commit: str | None,
            example: str | None, frames: list | None) -> None:
        item["count"] += 1
        item["first_seen"] = stamp if item["first_seen"] is None else min(item["first_seen"], stamp)
        item["last_seen"] = stamp if item["last_seen"] is None else max(item["last_seen"], stamp)
        if route:
            item["routes"][route] += 1
        if commit:
            item["commits"][commit] += 1
        if example and len(item["examples"]) < 8:
            item["examples"].append(example)
        if frames:
            item["frames"] = list(frames)
        index = int((stamp - start_bucket) // size)
        if 0 <= index < len(item["spark"]):
            item["spark"][index] += 1

    for request in requests:
        key = group_key(request, now)
        if key is None:
            continue
        error = request.error
        state = request.state(now)
        if state == "aborted":
            label, kind = f"Afgebroken: {request.route}", "aborted"
        elif error and error.get("handled"):
            label, kind = f"Afgehandeld: {error.get('code')}", "handled"
        elif error:
            label = f"{error.get('type')}" + (f" ({error.get('code')})" if error.get("code") else "")
            kind = "exception"
        else:
            label, kind = f"HTTP {request.status or '—'} op {request.route}", "status"
        add(group(key, label=label, kind=kind, error=error), request.started, request.route,
            request.commit, request.request_id, (error or {}).get("frames"))
    for event in other:
        key = _standalone_key(event)
        if key is None:
            continue
        error = event.get("error") if isinstance(event.get("error"), dict) else None
        if event.get("kind") == "log":
            message = str(event.get("message") or "")[:80]
            template = message.split(" ", 1)[0] if message else "log"
            item = group(key, label=f"Log {event.get('level')}: {template}", kind="log", error=error)
            add(item, event["_t"], None, event.get("commit"), event.get("request_id"), (error or {}).get("frames"))
        else:
            item = group(key, label=f"Onafgevangen ({event.get('origin')}): {error.get('type')}",
                         kind="unhandled", error=error)
            add(item, event["_t"], None, event.get("commit"), None, error.get("frames"))
    rows = []
    for item in groups.values():
        item["routes"] = [route for route, _ in item["routes"].most_common(3)]
        commits = item["commits"]
        item["commits"] = [commit for commit, _ in commits.most_common(5)]
        rows.append(item)
    severity = {"aborted": 0, "unhandled": 0, "exception": 1, "status": 1, "log": 2, "handled": 3}
    return sorted(rows, key=lambda row: (severity.get(row["kind"], 4), -row["count"]))


def _commits(requests: list[Request], now: float) -> list[dict[str, Any]]:
    by_commit: dict[str, list[Request]] = defaultdict(list)
    for request in requests:
        by_commit[request.commit or "unknown"].append(request)
    rows = []
    for commit, items in by_commit.items():
        times = [r.duration_ms() for r in items if r.responded()]
        errors = sum(r.state(now) in ("error", "aborted") for r in items)
        rows.append({"commit": commit, "requests": len(items), "errors": errors,
                     "error_rate": round(errors / len(items), 4), "p95_ms": percentile(times, 95),
                     "first_seen": min(r.started for r in items), "last_seen": max(r.last_seen for r in items)})
    rows.sort(key=lambda row: row["first_seen"])
    for previous, current in zip(rows, rows[1:]):
        current["delta_error_rate"] = round(current["error_rate"] - previous["error_rate"], 4)
        if previous["p95_ms"] and current["p95_ms"]:
            current["delta_p95_ratio"] = round(current["p95_ms"] / previous["p95_ms"], 2)
    return rows


def _correlations(requests: list[Request], now: float, slow_threshold: float | None) -> list[dict[str, Any]]:
    """Which route, commit or dominant phase is over-represented in failures and slowness."""
    findings: list[dict[str, Any]] = []
    if len(requests) < 5:
        return findings
    outcomes = {
        "fout": [r for r in requests if r.state(now) in ("error", "aborted")],
        "traag": [r for r in requests if slow_threshold and r.state(now) == "ok" and r.duration_ms() >= slow_threshold],
    }
    for outcome, subset in outcomes.items():
        if len(subset) < 3:
            continue
        base_rate = len(subset) / len(requests)
        for dimension, extract in (("route", lambda r: r.route), ("commit", lambda r: r.commit),
                                   ("fase", _dominant_phase)):
            totals = Counter(extract(r) for r in requests)
            hits = Counter(extract(r) for r in subset)
            for value, hit in hits.items():
                if value is None or hit < 3:
                    continue
                rate = hit / totals[value]
                lift = rate / base_rate if base_rate else 0
                if lift >= 1.5:
                    findings.append({"outcome": outcome, "dimension": dimension, "value": value,
                                     "rate": round(rate, 3), "base_rate": round(base_rate, 3),
                                     "lift": round(lift, 2), "support": hit})
        for metric, extract in (("db_queries", lambda r: r.db().get("db_queries")),
                                ("store_lock_wait_ms", lambda r: (r.phases().get("store_lock_wait") or {}).get("inclusive_ms"))):
            inside = [v for v in (extract(r) for r in subset) if isinstance(v, (int, float))]
            outside = [v for v in (extract(r) for r in requests if r not in subset) if isinstance(v, (int, float))]
            if len(inside) >= 3 and outside:
                mean_in, mean_out = sum(inside) / len(inside), sum(outside) / len(outside)
                if mean_out > 0 and mean_in / mean_out >= 1.5:
                    findings.append({"outcome": outcome, "dimension": "meting", "value": metric,
                                     "mean_in": round(mean_in, 1), "mean_out": round(mean_out, 1),
                                     "lift": round(mean_in / mean_out, 2), "support": len(inside)})
    return sorted(findings, key=lambda row: (row["lift"], row["support"]), reverse=True)[:12]


def _dominant_phase(request: Request) -> str | None:
    best, best_ms = None, 0.0
    for name, values in request.phases().items():
        value = float((values or {}).get("exclusive_ms") or 0) if isinstance(values, dict) else 0.0
        if value > best_ms:
            best, best_ms = name, value
    return best


def _process_events(other: list[dict], since: float) -> list[dict[str, Any]]:
    rows = [{"t": event["_t"], "event": event.get("event"), "pid": event.get("pid"),
             "commit": event.get("commit"), "instance": event.get("instance")}
            for event in other if event.get("kind") == "process" and event["_t"] >= since]
    return sorted(rows, key=lambda row: row["t"], reverse=True)[:50]


def request_detail(events: list[dict], request_id: str, *, now: float) -> dict[str, Any] | None:
    from src.telemetry.playbook import guidance_for_group
    requests, other = build_requests(events)
    request = requests.get(request_id)
    if request is None:
        return None
    tree = (request.finished or {}).get("phase_tree")
    nodes = []
    if isinstance(tree, dict):
        for path, values in sorted(tree.items()):
            if isinstance(values, dict):
                nodes.append({"path": path, "name": path.rsplit("/", 1)[-1], "depth": path.count("/"),
                              "calls": values.get("calls"), "inclusive_ms": values.get("inclusive_ms"),
                              "exclusive_ms": values.get("exclusive_ms")})
    related = [{"t": event["_t"], "event": event.get("event"), "kind": event.get("kind"),
                "level": event.get("level"), "logger": event.get("logger"),
                "message": event.get("message"), "error": event.get("error")}
               for event in other if event.get("request_id") == request_id]
    timeline = [{"t": event["_t"], "event": event.get("event"), "phase": event.get("phase"),
                 "elapsed_ms": event.get("elapsed_ms"), "status": event.get("status")}
                for event in sorted(request.events, key=lambda e: e["_t"])]
    row = _request_row(request, now)
    group = {"key": row["group"], "kind": "aborted" if row["state"] == "aborted" else
             ("handled" if (request.error or {}).get("handled") else "exception" if request.error else "status"),
             "code": (request.error or {}).get("code"), "error_type": (request.error or {}).get("type"),
             "frames": (request.error or {}).get("frames") or [], "routes": [request.route],
             "count": 1, "commits": [request.commit]} if row["group"] else None
    return {"request": row, "phases": request.phases(), "tree": nodes, "db": request.db(),
            "error": request.error, "timeline": timeline, "related": related,
            "guidance": guidance_for_group(group) if group else None,
            "same_trace": [r.request_id for r in requests.values()
                           if r.trace_id and r.trace_id == request.trace_id and r.request_id != request_id][:20],
            "same_snapshot": [_request_row(r, now) for r in requests.values()
                              if request.doc_ref and r.doc_ref == request.doc_ref
                              and r.request_id != request_id][:20]}
