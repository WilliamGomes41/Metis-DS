"""Telemetry JSON API (authenticated, read-only); the page lives in Inzicht."""
from __future__ import annotations

import heapq
import json
import re
import time
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from src.telemetry.analysis import request_detail, summarize
from src.telemetry.hub import HUB

WINDOWS = {"15m": 900, "1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}
_FILTER_RE = {"route": r"[\x20-\x7e]{1,120}", "method": r"[A-Z]{3,7}", "status": r"[1-5]xx",
              "state": r"ok|error|aborted|running|cancelled|incomplete", "commit": r"[0-9a-zA-Z._-]{1,64}",
              "q": r"[0-9a-zA-Z_:.\-]{1,80}", "error": r"[\x20-\x7e]{1,160}"}
_REQUEST_ID = re.compile(r"[0-9a-f]{32}")
_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
# Upper bound on events one analysis holds in memory; the most recent ones are kept.
MAX_ANALYZED_EVENTS = 50_000


def _recent_events(since: float) -> tuple[list[dict[str, Any]], bool]:
    """The newest MAX_ANALYZED_EVENTS events since ``since`` (streamed, bounded memory), oldest first."""
    seen = 0

    def counted():
        nonlocal seen
        for event in HUB.events(since):
            seen += 1
            yield event
    newest = heapq.nlargest(MAX_ANALYZED_EVENTS, counted(), key=lambda event: str(event.get("ts") or ""))
    newest.reverse()
    return newest, seen > len(newest)


def _filters(request: Request) -> dict[str, str]:
    values = {}
    for name, pattern in _FILTER_RE.items():
        value = (request.query_params.get(name) or "").strip()
        if value and re.fullmatch(pattern, value):
            values[name] = value
    if values.get("q", "").startswith("snap-"):
        # Events carry a pseudonymous doc_ref, never the document id itself.
        from src.request_diagnostics_v1 import doc_ref
        values["q"] = doc_ref(values["q"]) or values["q"]
    return values


def _window(request: Request) -> tuple[str, int]:
    key = request.query_params.get("window") or "24h"
    return (key, WINDOWS[key]) if key in WINDOWS else ("24h", WINDOWS["24h"])


def install_telemetry_routes(app: FastAPI, *, require_account: Callable[[Request], dict]) -> None:
    """JSON API for the Systeem tab of /inzicht (page: ``src/insight_v1.py``)."""
    @app.get("/telemetry/api/summary")
    def telemetry_summary(request: Request) -> JSONResponse:
        require_account(request)
        key, seconds = _window(request)
        now = time.time()
        events, truncated = _recent_events(now - seconds - 3600)
        body = summarize(events, filters=_filters(request), now=now, since=now - seconds)
        body["window"]["key"] = key
        body["telemetry"].update({"store": "disk" if HUB.directory else "memory", "dropped": HUB.dropped,
                                  "truncated": truncated})
        return JSONResponse(body, headers=_HEADERS)

    @app.get("/telemetry/api/request/{request_id}")
    def telemetry_request(request: Request, request_id: str) -> JSONResponse:
        require_account(request)
        if not _REQUEST_ID.fullmatch(request_id):
            return JSONResponse({"error": "unknown_request"}, status_code=404, headers=_HEADERS)
        now = time.time()
        detail = request_detail(_recent_events(now - WINDOWS["7d"])[0], request_id, now=now)
        if detail is None:
            return JSONResponse({"error": "unknown_request"}, status_code=404, headers=_HEADERS)
        return JSONResponse(detail, headers=_HEADERS)

    @app.get("/telemetry/api/export")
    def telemetry_export(request: Request) -> Response:
        require_account(request)
        _key, seconds = _window(request)
        since = time.time() - seconds
        # Streamed one event at a time: memory stays bounded however large the window is.
        lines = (json.dumps({k: v for k, v in event.items() if not k.startswith("_")},
                            separators=(",", ":"), ensure_ascii=False) + "\n"
                 for event in HUB.events(since))
        return StreamingResponse(lines, media_type="application/x-ndjson",
                                 headers={**_HEADERS, "Content-Disposition": 'attachment; filename="metis-telemetry.jsonl"'})
