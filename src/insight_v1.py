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
import json
from html import escape
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit

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
    """Processing scope plus publishers' existing publication document list."""
    roles = set(account.get("roles") or [])
    if "publisher" in roles:
        from src.operations_console_v1 import ConsoleError
        try:
            state._require_role(account["account_id"], "publisher", current=True)
        except ConsoleError:
            roles.discard("publisher")
    rows = []
    for envelope in state.list_envelopes():
        if roles & {"researcher", "publisher"} or ("reviewer" in roles and account["account_id"] in (envelope.get("named_reviewers") or [])):
            rows.append(envelope)
    return rows


def _matches_document(envelope: dict[str, Any], query: str) -> bool:
    from src.request_diagnostics_v1 import doc_ref
    sid = envelope["snapshot_id"]
    return any(query in str(value or "").lower() for value in (envelope.get("title"), sid, doc_ref(sid)))


def _telemetry_by_document(since: float) -> tuple[dict[str, dict[str, int]], bool]:
    """Requests and errors per doc_ref since ``since``, and whether the bounded read was partial."""
    from src.telemetry.analysis import build_requests
    from src.telemetry.hub import recent_events
    events, partial = recent_events(since)
    requests, _other = build_requests(events)
    now = time.time()
    counts: dict[str, dict[str, int]] = {}
    for request in requests.values():
        if request.doc_ref and request.started >= since:
            row = counts.setdefault(request.doc_ref, {"requests": 0, "errors": 0})
            row["requests"] += 1
            row["errors"] += int(request.state(now) in ("error", "aborted"))
    return counts, partial


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
    telemetry, partial = _telemetry_by_document(time.time() - 86400) if offset < len(authorized) else ({}, False)
    rows, position = [], offset
    scan_end = min(len(authorized), offset + (MAX_SCAN if state_filter else limit))
    while position < scan_end and len(rows) < limit:
        row = _document_row(state, account, authorized[position], telemetry)
        position += 1
        if _state_matches(row, state_filter):
            rows.append(row)
    return {"documents": rows, "total": None if state_filter else len(authorized), "offset": offset,
            "limit": limit, "next_offset": position if position < len(authorized) else None,
            "telemetry_partial": partial}


def _document_row(state, account, envelope: dict[str, Any], telemetry: dict[str, dict[str, int]]) -> dict[str, Any]:
    from src.processing_diagnostics_v1 import processing_diagnostics
    from src.request_diagnostics_v1 import doc_ref
    sid = envelope["snapshot_id"]
    roles = set(account.get("roles") or [])
    processing_access = "researcher" in roles or ("reviewer" in roles and account["account_id"] in envelope.get("named_reviewers", []))
    try:
        status = state.processing_status(sid, actor_id=account["account_id"], deep=False) if processing_access else {}
    except Exception:
        status = {}
    try:
        diagnostics = processing_diagnostics(state.snapshot_objects(sid)) if processing_access else {"blocked_candidate_count": None, "by_reason_code": {}}
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


def processing_margins_html(report: dict[str, Any]) -> str:
    """Render only derived trace measurements, after existing processing auth."""
    def seconds(value):
        return "niet vastgelegd" if value is None else f"{value:g} s"
    states = {"running": "als actief opgeslagen", "succeeded": "technisch geslaagd",
              "failed": "mislukt", "interrupted": "onderbroken", "incomplete_budget": "gestopt op taakbudget"}
    body = '<section id="verwerkingsmarges"><h3>Verwerkingsmarges · waargenomen gegevens</h3>'
    body += '<p>Gemeten op ' + escape(str(report['observed_at'] or 'onbekend')) + '. Alleen de bewaarde pogingen van dit document.</p>'
    counts = report['counts']
    body += f'<p>Bewaard: {int(counts["retained"])} pogingen; {int(counts["retry_links_observed"])} retry-verwijzingen, waarvan {int(counts["retry_gaps_measured"])} met meetbare tussentijd.</p>'
    if not report['attempts']:
        body += '<p>Geen vastgelegde pogingen; geen uitspraak over gezondheid of herstelbaarheid mogelijk.</p>'
    if report['omitted_attempts']:
        body += f'<p>{int(report["omitted_attempts"])} oudere pogingen ontbreken in deze begrensde weergave.</p>'
    for row in report['attempts']:
        body += ('<details open>' if row['signals'] else '<details>') + '<summary>Poging ' + escape(str(row['attempt_id'] or 'zonder identiteit')) + ' · ' + escape(states.get(row['stored_state'], 'status onbekend')) + '</summary><dl>'
        for label, key in (("Wachttijd vóór claim (bij open werk: tot meetmoment)", "queue_wait_seconds"),
                           ("Uitvoertijd sinds claim", "execution_seconds"),
                           ("Resterende opgeslagen pogingstijd", "deadline_remaining_seconds"),
                           ("Tijd beschikbaar bij claim", "budget_at_claim_seconds"),
                           ("Tijd sinds laatst bewaard checkpoint (bij afgerond werk: tot einde)", "checkpoint_age_seconds"),
                           ("Tussen einde voorganger en deze retry", "retry_gap_seconds")):
            body += '<dt>' + label + '</dt><dd>' + seconds(row[key]) + '</dd>'
        body += '</dl><p>Laatst bewaarde fase: ' + escape(str(row['last_checkpoint_phase'] or 'niet vastgelegd')) + '</p>'
        if row['reference']:
            ref = row['reference']
            body += f'<p>Vergelijking vóór deze claim: mediaan {seconds(ref["execution_p50_seconds"])} uitvoertijd in {int(ref["samples"])} technisch geslaagde pogingen met dezelfde bron, configuratie, uitvoerversie en pogingsoort.</p>'
        elif row['stored_state'] == 'running':
            body += '<p>Onvoldoende vergelijkbaar bewijs voor een historische uitvoertijd.</p>'
        if 'claim_budget_below_observed_duration' in row['signals']:
            body += '<p role="status">Bij de claim bleef minder pogingstijd over dan de eerder waargenomen mediane uitvoertijd. De verwerking kan daardoor haar opgeslagen deadline bereiken. Dit bewijst geen toekomstige storing.</p>'
        if 'stored_deadline_elapsed' in row['signals']:
            body += '<p role="status">De opgeslagen deadline is verstreken; de poging staat nog als actief opgeslagen. Alleen de bestaande verwerking bepaalt de actuele toestand en het toegestane herstel.</p>'
        if row['signals']:
            body += '<p>Controleer de actuele verwerkingsstatus, dispatcher en afhankelijkheden voordat u via Bronselectie een toegestane vervolgstap kiest.</p>'
        if row['evidence_issues']:
            body += '<p>Meetgegevens ontbreken, zijn onvolledig of spreken elkaar tegen; ontbrekende tijden tellen niet als nul.</p>'
        body += '</details>'
    return body + '<p>Een oud checkpoint bewijst geen stilstand. Pogingaantallen bepalen geen retryrechten. Een tijdsmarge garandeert geen veilige handeltijd; technisch succes bewijst geen volledige bronverwerking of publicatiegereedheid.</p></section>'


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
        if tab == "kwaliteit" and request.query_params.get("view") == "table":
            return app.state.insight_quality_table(request)
        html = render_page(nav(account, "settings") + insight_body(insight_tabs(tab), tab), title="Inzicht — Metis")
        return HTMLResponse(html, headers=_HEADERS)

    @app.get("/inzicht/document", response_class=HTMLResponse)
    @state.source_selection_read_scope()
    def document_diagnosis(request: Request, document: str = "") -> HTMLResponse:
        from src.operations_console_app import ERROR_COPY, _processing_diagnostics_html, _coverage_panel
        from src.review_interaction_v1 import review_burden_projection
        from src.review_ledger import read_events

        account = require_account(request)
        if not document:
            from src.operations_console_v1 import ConsoleError
            raise ConsoleError("unknown_document")
        roles = set(account.get("roles") or [])
        envelope = state._envelope(document)
        reviewer = "reviewer" in roles and account["account_id"] in envelope.get("named_reviewers", [])
        processing_access = "researcher" in roles or reviewer
        # Publishers already have release-evidence access, not processing access.
        # Every processing read still goes through the existing owner's guard.
        if processing_access or "publisher" not in roles:
            processing = state.processing_status(document, actor_id=account["account_id"])
        else:
            state._require_role(account["account_id"], "publisher", current=True)
            processing = {}
        query = escape(urlencode({"document": document}), quote=True)
        code = ("source_formation_incomplete" if processing.get("formation_incomplete")
                else processing.get("error_code") or processing.get("reason_code") or "")
        controls = ""
        if processing.get("resume_allowed") or processing.get("retry_allowed"):
            controls += f'<p><a class="btn-primary" href="/source-selection?{query}">Naar Bronselectie voor Starten of Hervatten</a></p>'
        if ("publisher" in roles
                and (account["account_id"] in envelope.get("named_reviewers", [])
                     or account["account_id"] == envelope.get("uploader_account_id"))
                and processing.get("reason_code") == "processing_attempt_limit_reached"
                and not envelope.get("processing_recovery")):
            controls += f'''<form method="post" action="/tree/processing-recovery">
              <input type="hidden" name="snapshot_id" value="{escape(document, quote=True)}">
              <label>Reden voor eenmalig herstel<input name="reason" required maxlength="1000"></label>
              <button type="submit">Een herstelpoging autoriseren</button></form>'''
        margins_html = ""
        if processing_access:
            from src.processing_trace_v1 import processing_trace
            margins_html = processing_margins_html(processing_trace(envelope)["processing_margins"])
        progress = processing.get("formation_progress") or {}
        progress_html = ""
        if progress.get("planned_task_count"):
            progress_html = (f'<p>Vormingstaken: {int(progress.get("terminal_task_count") or 0)} van '
                             f'{int(progress["planned_task_count"])} afgehandeld; '
                             f'{int(progress.get("pending_task_count") or 0)} nog open.</p>')
        attempts = (envelope.get("processing_attempts") or []) if processing_access else []
        diagnostic = (attempts[-1].get("diagnostic") or {}) if attempts else {}
        pages = [str(page) for page in diagnostic.get("unverified_pages") or [] if type(page) is int]
        pages_html = f'<p>Pagina’s zonder verwerkbare brontekst: {escape(", ".join(pages))}</p>' if pages else ""
        detail = escape(json.dumps(diagnostic, ensure_ascii=False, indent=2))
        passages = '<p>Passagediagnostiek en passage-exports zijn beschikbaar voor de aangewezen reviewer.</p>'
        passage_exports = ""
        source_exports = (f'<li><a href="/inzicht/document/verwerkingsspoor?{query}">Verwerkingsspoor (JSON)</a></li>'
                          if processing_access else "")
        publication_export = (f'<li><a href="/inzicht/document/publicatiebewijs?{query}">Publicatiebewijs (JSON)</a></li>'
                              if "publisher" in roles else "")
        if reviewer:
            objects = state.snapshot_objects(document)
            burden = review_burden_projection(read_events(state._ledger_path), snapshot_id=document)
            passages = (_processing_diagnostics_html(objects) + _coverage_panel(objects)
                + f'<details><summary>Reviewinteracties</summary><p>{int(burden["review_interactions"])} gemeten menselijke interacties voor '
                  f'{int(burden["object_decisions"])} objectbesluiten. Historische besluiten zonder meting: '
                  f'{int(burden["legacy_unmeasured_decisions"])}.</p></details>'
                + f'<p><a href="/review?{query}&amp;task=repair">Passages corrigeren in Review</a></p>')
            passage_exports = f'''<li>Bronpassages: <a href="/inzicht/document/passages?{query}&amp;format=csv">CSV</a> ·
              <a href="/inzicht/document/passages?{query}&amp;format=json">JSON</a></li>
              <li><a href="/inzicht/document/diagnostiek?{query}">Diagnostiek (JSON)</a></li>
              <li><a href="/inzicht/document/detaildiagnostiek?{query}">Detaildiagnostiek (JSON)</a></li>
              <li><a href="/inzicht/document/verwerkingsbewijs?{query}">Verwerkingsbewijs als CSV-pakket</a></li>'''
        processing_html = f'''
          <section id="verwerking"><h2>Verwerking</h2>
            <p>{escape(ERROR_COPY.get(code, "Controleer de actuele verwerking."))}</p>
            <p>Status: {escape(str(processing.get("state") or "niet vastgelegd"))}</p>
            <p>Code: <code>{escape(str(code))}</code></p>{pages_html}{progress_html}
            <p>Een technisch geslaagde poging bewijst niet dat bronverwerking, review of publicatievoorwaarden volledig zijn afgerond.</p>
            <p>Nieuwe poging vanaf: {escape(str(processing.get("retry_not_before") or "niet van toepassing"))}</p>
            {margins_html}{controls}<details><summary>Laatste verwerkingspoging ({len(attempts)} opgeslagen)</summary><pre>{detail}</pre></details>
            <p><a href="/inzicht/document/blokkade?{query}">Blokkade en bewijs per verwerkingspoging onderzoeken</a></p>
          </section>''' if processing_access else '<section id="verwerking"><h2>Verwerking</h2><p>Verwerkingsdiagnostiek is beschikbaar voor onderzoekers en aangewezen reviewers.</p></section>'
        body = f'''{nav(account, "settings")}<section class="room">
          {insight_tabs("documenten")}
          <p><a href="/inzicht?tab=documenten">← Alle documentdiagnoses</a></p>
          <h1>Documentdiagnose: {escape(str(envelope.get("title") or document))}</h1>
          <p>Bronversie {escape(str(envelope.get("version") or ""))}</p>
          <nav aria-label="Documentdiagnose"><a href="#verwerking">Verwerking</a> ·
            <a href="#passages">Passages en brondekking</a> · <a href="#bewijs">Bewijs en downloads</a></nav>
          {processing_html}
          <section id="passages"><h2>Passages en brondekking</h2>{passages}</section>
          <section id="bewijs"><h2>Bewijs en downloads</h2><ul class="export-options">
            {source_exports}{publication_export}{passage_exports}</ul></section></section>'''
        return HTMLResponse(render_page(body, title="Documentdiagnose — Inzicht — Metis"), headers=_HEADERS)

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


def install_insight_legacy_routes(app: FastAPI, require_account: Callable[[Request], dict]) -> None:
    """Old GET addresses navigate to the same authorized owner, preserving context."""
    destinations = {
        "/settings/technical/processing": "/inzicht/document",
        "/source-selection/processing-trace": "/inzicht/document/verwerkingsspoor",
        "/source-selection/publication-evidence": "/inzicht/document/publicatiebewijs",
        "/source-selection/blockage": "/inzicht/document/blokkade",
        "/review/passages-export": "/inzicht/document/passages",
        "/review/processing-evidence-export": "/inzicht/document/verwerkingsbewijs",
        "/review/processing-diagnostics": "/inzicht/document/diagnostiek",
        "/review/processing-diagnostics-detail": "/inzicht/document/detaildiagnostiek",
        "/review/processing-diagnostic-replay": "/inzicht/document/poging",
        "/settings/quality": "/inzicht?tab=kwaliteit&view=table",
        "/settings/quality/compare": "/inzicht/routevergelijking",
    }

    def redirect_to(target: str):
        def legacy(request: Request) -> RedirectResponse:
            require_account(request)
            destination = urlsplit(target)
            fixed = parse_qsl(destination.query)
            reserved = {key for key, _ in fixed}
            context = [(key, value) for key, value in request.query_params.multi_items() if key not in reserved]
            query = urlencode(fixed + context)
            return RedirectResponse(destination.path + ("?" + query if query else ""), status_code=303, headers=_HEADERS)
        return legacy

    for old, target in destinations.items():
        app.add_api_route(old, redirect_to(target), methods=["GET"], include_in_schema=False)

    @app.get("/settings/technical/exports", include_in_schema=False)
    def legacy_exports(request: Request) -> RedirectResponse:
        require_account(request)
        query = request.url.query
        if request.query_params.get("document"):
            return RedirectResponse("/inzicht/document?" + query + "#bewijs", status_code=303, headers=_HEADERS)
        return redirect_to("/inzicht?tab=documenten")(request)

    @app.get("/settings/quality/compare/{comparison_id}", include_in_schema=False)
    def legacy_comparison(request: Request, comparison_id: str) -> RedirectResponse:
        from urllib.parse import quote
        target = "/inzicht/routevergelijking/" + quote(comparison_id, safe="")
        return redirect_to(target)(request)
