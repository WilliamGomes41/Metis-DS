"""Inzicht: one room for system telemetry, work quality, document diagnostics and checks.

Presentation and read-only projections only. Every tab reuses an existing owner:
telemetry (``src/telemetry``), the quality measurement (``quality_metrics_app_v1.
quality_view``: same capture, scope and immutable report store), processing
status and diagnostics (``OperationsConsole.processing_status``,
``processing_diagnostics_v1``). No new authority, no writes beyond the existing
quality report store.
"""
from __future__ import annotations

import time
from html import escape
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

TABS = (("systeem", "Systeem"), ("kwaliteit", "Kwaliteit & werkproces"),
        ("documenten", "Documenten"), ("controles", "Controles"))
_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
MAX_DOCUMENTS = 200
# Documents examined per request when a state filter is active; the cursor continues the scan.
MAX_SCAN = 1000
DOCUMENT_STATES = ("blocked", "errors", "retry")


def insight_tabs(current: str) -> str:
    """The shared tab bar; links so it also works on pages outside /inzicht."""
    items = "".join(
        f'<a href="/inzicht?tab={key}" data-tab="{key}" role="tab"'
        f'{" aria-selected=\"true\" aria-current=\"page\"" if key == current else " aria-selected=\"false\""}>'
        f'{escape(label)}</a>' for key, label in TABS)
    return _TAB_STYLE + f'<nav class="insight-tabs" role="tablist" aria-label="Inzicht">{items}</nav>'


# Travels with the tab bar so the shared console stylesheet stays unchanged.
_TAB_STYLE = """<style>
.insight-tabs { display:flex; gap:2px; flex-wrap:wrap; border-bottom:1px solid var(--line); margin:14px 0 18px; }
.insight-tabs a { padding:10px 16px; color:var(--muted); text-decoration:none; font-weight:600; border-bottom:3px solid transparent; margin-bottom:-1px; border-radius:8px 8px 0 0; }
.insight-tabs a:hover { color:var(--text); background:var(--water-soft); }
.insight-tabs a[aria-selected="true"] { color:var(--text); border-bottom-color:var(--water); }
.insight-tabs a:focus-visible { outline:2px solid var(--water); outline-offset:2px; }
</style>"""


def _authorized_documents(state, account) -> list[dict[str, Any]]:
    """Same rule as Technisch beheer: researchers see all, reviewers their named documents."""
    roles = set(account.get("roles") or [])
    rows = []
    for envelope in state.list_envelopes():
        if "researcher" in roles or ("reviewer" in roles and account["account_id"] in (envelope.get("named_reviewers") or [])):
            rows.append(envelope)
    return rows


def _matches_document(envelope: dict[str, Any], query: str) -> bool:
    from src.request_diagnostics_v1 import doc_ref
    sid = envelope["snapshot_id"]
    return any(query in str(value or "").lower() for value in (envelope.get("title"), sid, doc_ref(sid)))


def _telemetry_by_document(since: float) -> dict[str, dict[str, int]]:
    from src.telemetry.analysis import build_requests
    from src.telemetry.hub import HUB
    requests, _other = build_requests(list(HUB.events(since)))
    now = time.time()
    counts: dict[str, dict[str, int]] = {}
    for request in requests.values():
        if request.doc_ref and request.started >= since:
            row = counts.setdefault(request.doc_ref, {"requests": 0, "errors": 0})
            row["requests"] += 1
            row["errors"] += int(request.state(now) in ("error", "aborted"))
    return counts


def _state_matches(row: dict[str, Any], state_filter: str) -> bool:
    return (not state_filter or (state_filter == "blocked" and bool(row["blocked"]))
            or (state_filter == "errors" and bool(row["telemetry"]["errors"]))
            or (state_filter == "retry" and row["retry_allowed"]))


def documents_projection(state, account, *, query: str = "", state_filter: str = "", offset: int = 0,
                         limit: int = MAX_DOCUMENTS) -> dict[str, Any]:
    """One page of authorized documents; search and state filter run over the whole authorized list.

    ``offset`` and ``next_offset`` index the searched authorized list. Without a state
    filter ``total`` is exact; with one it is unknown until the scan reaches the end.
    """
    query = query.strip().lower()
    state_filter = state_filter if state_filter in DOCUMENT_STATES else ""
    authorized = [envelope for envelope in _authorized_documents(state, account)
                  if not query or _matches_document(envelope, query)]
    offset, limit = max(0, offset), max(1, min(limit, MAX_DOCUMENTS))
    telemetry = _telemetry_by_document(time.time() - 86400) if offset < len(authorized) else {}
    rows, position = [], offset
    scan_end = min(len(authorized), offset + (MAX_SCAN if state_filter else limit))
    while position < scan_end and len(rows) < limit:
        row = _document_row(state, account, authorized[position], telemetry)
        position += 1
        if _state_matches(row, state_filter):
            rows.append(row)
    return {"documents": rows, "total": None if state_filter else len(authorized), "offset": offset,
            "limit": limit, "next_offset": position if position < len(authorized) else None}


def _document_row(state, account, envelope: dict[str, Any], telemetry: dict[str, dict[str, int]]) -> dict[str, Any]:
    from src.processing_diagnostics_v1 import processing_diagnostics
    from src.request_diagnostics_v1 import doc_ref
    sid = envelope["snapshot_id"]
    try:
        status = state.processing_status(sid, actor_id=account["account_id"], deep=False)
    except Exception:
        status = {}
    try:
        diagnostics = processing_diagnostics(state.snapshot_objects(sid))
    except Exception:
        diagnostics = {"blocked_candidate_count": None, "by_reason_code": {}}
    ref = doc_ref(sid)
    reasons = list((diagnostics.get("by_reason_code") or {}).items())[:3]
    return {
        "snapshot_id": sid, "doc_ref": ref, "title": envelope.get("title") or sid,
        "version": envelope.get("version"), "class": envelope.get("class"),
        "state": status.get("state") or envelope.get("state"),
        "code": status.get("error_code") or status.get("reason_code"),
        "retry_allowed": bool(status.get("retry_allowed")),
        "blocked": diagnostics.get("blocked_candidate_count"),
        "reasons": [{"code": code, "count": values.get("candidate_count")} for code, values in reasons],
        "telemetry": telemetry.get(ref or "", {"requests": 0, "errors": 0}),
        "named_reviewer": account["account_id"] in (envelope.get("named_reviewers") or []),
    }


def quality_projection(view: dict[str, Any]) -> dict[str, Any]:
    from collections import Counter
    from src.request_diagnostics_v1 import doc_ref
    report = view["report"]
    changed: Counter = Counter()
    for row in report["routes"].values():
        changed.update(row.get("changed_fields") or {})
    trend = []
    # Only reports over the same cohort filters and measurement definition form one series.
    comparable = [record for record in view["history"]
                  if record["report"].get("filters") == report["filters"]
                  and record["report"].get("definition_version") == report["definition_version"]]
    for record in sorted(comparable, key=lambda r: r["report"]["as_of"])[-40:]:
        old = record["report"]
        routes = old.get("routes") or {}
        trend.append({"as_of": old["as_of"], "open_passages": old.get("open_passages"),
                      "cohort_size": old.get("cohort_size"), "calculation_id": record["calculation_id"],
                      "direct_rate": {route: (row or {}).get("direct_rate") for route, row in routes.items()}})
    return {
        "calculation_id": view["record"]["calculation_id"], "as_of": report["as_of"],
        "definition_version": report["definition_version"], "filters": report["filters"],
        "cohort_size": report["cohort_size"], "open_passages": report["open_passages"],
        "oldest_unfinished_source_days": report.get("oldest_unfinished_source_days"),
        "publication": report["publication_duration_seconds"], "burden": report["burden"],
        "routes": report["routes"], "changed_fields": dict(changed),
        "processing_runs": report.get("processing_runs") or {},
        "documents": [{**{k: doc.get(k) for k in ("title", "route", "open_passages", "source_age_days",
                                                   "processing_blocker", "interactions", "object_decisions",
                                                   "object_count", "high_risk_objects", "run_count")},
                       "snapshot_id": doc["snapshot_id"], "doc_ref": doc_ref(doc["snapshot_id"])}
                      for doc in report["documents"]],
        "definitions": report["definitions"], "limitations": report["limitations"],
        "readiness_reason": report["readiness_duration"]["reason"],
        "clinical_reason": report["clinical_errors"]["reason"],
        "trend": trend,
    }


def install_insight_routes(app: FastAPI, state, *, require_account: Callable[[Request], dict],
                           render_page: Callable[..., str], nav: Callable[..., str]) -> None:
    from src.quality_metrics_app_v1 import QualityViewError, quality_store, quality_view, validate_filters
    from src.telemetry.page import insight_body

    @app.get("/inzicht", response_class=HTMLResponse)
    def insight(request: Request) -> HTMLResponse:
        account = require_account(request)
        tab = request.query_params.get("tab") or "systeem"
        tab = tab if tab in dict(TABS) else "systeem"
        html = render_page(nav(account, "settings") + insight_body(insight_tabs(tab), tab), title="Inzicht — Metis")
        return HTMLResponse(html, headers=_HEADERS)

    @app.get("/telemetry")
    def telemetry_alias(request: Request) -> RedirectResponse:
        require_account(request)
        return RedirectResponse("/inzicht?tab=systeem", status_code=303)

    @app.get("/inzicht/api/quality")
    def insight_quality(request: Request) -> JSONResponse:
        account = require_account(request)
        store = getattr(app.state, "quality_store", None) or quality_store(state)
        try:
            filters = validate_filters(request.query_params)
            view = quality_view(state, store, account, filters, request.query_params.get("report"))
        except QualityViewError as exc:
            return JSONResponse({"error": exc.reason}, status_code=exc.status, headers=_HEADERS)
        return JSONResponse(quality_projection(view), headers=_HEADERS)

    @app.get("/inzicht/api/documents")
    def insight_documents(request: Request) -> JSONResponse:
        account = require_account(request)
        params = request.query_params
        try:
            offset, limit = int(params.get("offset") or 0), int(params.get("limit") or MAX_DOCUMENTS)
        except ValueError:
            return JSONResponse({"error": "Ongeldige pagina"}, status_code=400, headers=_HEADERS)
        page = documents_projection(state, account, query=(params.get("q") or "")[:120],
                                    state_filter=params.get("state") or "", offset=offset, limit=limit)
        return JSONResponse(page, headers=_HEADERS)
