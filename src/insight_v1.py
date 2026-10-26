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
import logging
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
DIAGNOSTIC_BATCH_SIZE = 50
NOTICE_TIME_BUDGET_SECONDS = 4.0
LOG = logging.getLogger(__name__)
DOCUMENT_STATES = ("blocked", "errors", "retry", "attention")


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


# Documentdiagnose (#854): presentation only, over projections the handler already read.
_DIAGNOSIS_STYLE = """<style>
.document-diagnosis { overflow-wrap:anywhere; }
.document-diagnosis section { margin-top:28px; }
.document-diagnosis a, .document-diagnosis summary, .document-diagnosis button { min-height:44px; }
.document-diagnosis a { display:inline-flex; align-items:center; }
.document-diagnosis summary { display:flex; align-items:center; cursor:pointer; }
.diagnosis-verdict { border:1px solid var(--line); border-radius:12px; padding:16px; background:var(--water-soft); }
.diagnosis-verdict[data-state="blocked"] { border:2px solid #5D3297; background:#F3EEF9; color:#1C1724; }
.diagnosis-label { font-weight:700; text-transform:uppercase; letter-spacing:.04em; margin:0 0 8px; }
.diagnosis-verdict[data-state="blocked"] .diagnosis-label, .diagnosis-steps li.blocked .diagnosis-status { color:#4A2679; }
.diagnosis-icon { display:inline-flex; align-items:center; justify-content:center; width:1.4em; height:1.4em; border-radius:50%; font-weight:700; text-transform:none; vertical-align:middle; }
.diagnosis-icon.is-blocked { background:#5D3297; color:#FFFFFF; }
.diagnosis-icon.is-running { color:#45AAC7; }
.diagnosis-icon.is-info { border:2px solid #45AAC7; color:#45AAC7; font-style:normal; }
.diagnosis-facts { display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:8px; margin:12px 0; }
.diagnosis-facts div { background:var(--surface, #fff); border:1px solid var(--line); border-radius:8px; padding:8px 12px; }
.diagnosis-facts dt { font-size:.85em; color:var(--muted); }
.diagnosis-facts dd { margin:0; font-size:1.4em; font-weight:700; font-variant-numeric:tabular-nums; }
.diagnosis-buttons { display:flex; flex-wrap:wrap; gap:8px; }
.diagnosis-steps { list-style:none; padding:0; }
.diagnosis-steps li { border-left:3px solid var(--line); padding:4px 0 12px 16px; }
.diagnosis-steps li.blocked { border:2px solid #5D3297; border-radius:8px; background:#F3EEF9; color:#1C1724; padding:12px 16px; }
.diagnosis-steps h3 { margin:0; font-size:1em; }
.diagnosis-status { font-weight:600; font-size:.9em; }
.diagnosis-table { width:100%; border-collapse:collapse; }
.diagnosis-table th, .diagnosis-table td { text-align:left; padding:8px; border-bottom:1px solid var(--line); }
.diagnosis-table .num { text-align:right; font-variant-numeric:tabular-nums; }
.diagnosis-family { border:1px solid var(--line); border-radius:8px; padding:12px 16px; margin:12px 0; }
.diagnosis-family h3 { margin:0 0 4px; font-size:1em; }
.diagnosis-cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:12px; }
.diagnosis-card { border:1px solid var(--line); border-radius:8px; padding:12px 16px; min-width:0; }
.diagnosis-summary { display:grid; grid-template-columns:auto 1fr; gap:4px 12px; }
.diagnosis-summary dd { margin:0; }
@media (max-width:640px) {
  .diagnosis-table thead { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }
  .diagnosis-table, .diagnosis-table tbody, .diagnosis-table tr, .diagnosis-table th, .diagnosis-table td { display:block; width:auto; }
  .diagnosis-table tr { border-bottom:1px solid var(--line); padding:8px 0; }
  .diagnosis-table td { border:0; padding:2px 0; }
  .diagnosis-table td[data-label]::before { content:attr(data-label) ": "; font-weight:600; }
  .diagnosis-table .num { text-align:left; }
}
</style>"""

# Concept texts (Metis #854 answer 3); Vignet reviews house style before merge.
_DIAGNOSIS_FAMILY_COPY = {
    "semantic_contract": ("Zorg dat elke passage zegt wat hij bedoelt en welke soort tekst het is",
                          "De bedoeling van de passage is niet duidelijk",
                          "Metis kan niet vaststellen wat voor tekst een passage is (een aanbeveling, uitleg of definitie) of welke kern erin staat."),
    "unit_completeness": ("Maak passages zelfstandig leesbaar", "De passage is niet los te lezen",
                          "De passage bevat geen zelfstandige bewering, of verwijst naar iets dat er niet in staat. Los gelezen is hij niet te begrijpen."),
    "dependency_resolution": ("Voeg ontbrekende context toe of koppel de juiste passage", "Er ontbreekt context",
                              "De passage heeft andere tekst nodig om te kloppen, en die is nog niet gevonden of gekoppeld."),
    "source_binding": ("Koppel de passage aan de juiste plek in de bron", "De passage is niet goed aan de bron gekoppeld",
                       "Metis vindt de passage of de onderbouwing niet terug op de aangegeven plek in de bron."),
    "processing_completeness": ("Rond de contextcontrole af", "De controle van de passage is niet afgerond",
                                "Metis heeft voor deze passage nog niet vastgelegd of er andere tekst nodig is om hem te begrijpen."),
    "unclassified": ("Controleer de punten die nog niet zijn ingedeeld", "Punten die nog niet zijn ingedeeld",
                     "Metis heeft deze punten nog niet aan een soort gekoppeld. De codes staan bij de technische details."),
}

_DIAGNOSIS_STEPS = ("Bron ingelezen en verwerkt", "Tekst opgedeeld in taken", "Passages gemaakt",
                    "Passages gecontroleerd", "Publicatie")


def _diagnosis_families(diagnostics: dict | None) -> list[tuple[str, dict]]:
    """Families with the most check points first; ties keep the projection's order."""
    rows = list(((diagnostics or {}).get("by_family") or {}).items())
    return sorted(rows, key=lambda row: -int(row[1]["issue_occurrence_count"]))


def _diagnosis_icon(label: str) -> str:
    """Purple '!' only for a block; neutral Water icons otherwise (Vignet, #854)."""
    if label == "Niet publiceerbaar":
        return '<span class="diagnosis-icon is-blocked" aria-hidden="true">!</span>'
    if label == "Verwerking loopt":
        return ('<span class="diagnosis-icon is-running" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" '
                'fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/>'
                '<path d="M12 7v5l3 2"/></svg></span>')
    return '<span class="diagnosis-icon is-info" aria-hidden="true">i</span>'


# Existing trace/checkpoint phases -> UI stages; extraction, model work, control.
# No persisted phase independently denotes human publication. Presentation only.
_DIAGNOSIS_PHASE_STEP = {
    "reserved": 1, "extraction_started": 1, "extraction_finished": 1,
    "extraction_checkpoint": 1, "extraction_reused": 1,
    "source_reconstructed": 1, "source_views_pinned": 1,
    "task_plan_pinned": 2, "worker_claimed": 2, "worker_handover": 2, "model_request": 2,
    "response_received": 2, "model_response": 2, "proposal_parsed": 2,
    "proposal_received": 2, "task_rejected": 2, "budget_exhausted": 2,
    "validation_started": 4, "validation_rejected": 4, "proposal_gate_rejected": 4,
    "evidence_resolved": 4, "formation_accounted": 4, "joint_validation_rejected": 4,
}


def _diagnosis_failed_step(diagnostic: dict) -> int:
    """The step where the failure is recorded; else the first step after the last reached one; else 1."""
    phase = diagnostic.get("phase")
    if phase in _DIAGNOSIS_PHASE_STEP:
        return _DIAGNOSIS_PHASE_STEP[phase]
    reached = [_DIAGNOSIS_PHASE_STEP[row.get("phase")] for row in diagnostic.get("checkpoints") or []
               if isinstance(row, dict) and row.get("phase") in _DIAGNOSIS_PHASE_STEP]
    return min(max(reached) + 1, len(_DIAGNOSIS_STEPS)) if reached else 1


def _diagnosis_active_step(diagnostic: dict) -> int:
    """Current recorded phase, otherwise the most recent known checkpoint."""
    phase = diagnostic.get("phase")
    if phase in _DIAGNOSIS_PHASE_STEP:
        return _DIAGNOSIS_PHASE_STEP[phase]
    for row in reversed(diagnostic.get("checkpoints") or []):
        if isinstance(row, dict) and row.get("phase") in _DIAGNOSIS_PHASE_STEP:
            return _DIAGNOSIS_PHASE_STEP[row["phase"]]
    return 1


def _diagnosis_steps_html(processing: dict, code: str, progress: dict, diagnostics: dict | None,
                          diagnostic: dict | None = None, *, admission_blocked: bool = False) -> str:
    blocked = int((diagnostics or {}).get("blocked_candidate_count") or 0)
    pending = int(progress.get("pending_task_count") or 0)
    running = processing.get("state") == "running"
    active = _diagnosis_active_step(diagnostic or {}) if running else None
    reached = {_DIAGNOSIS_PHASE_STEP.get(row.get("phase"))
               for row in (diagnostic or {}).get("checkpoints") or [] if isinstance(row, dict)}
    if code == "source_formation_incomplete":
        stop = 2 if pending else 4
    elif running:
        stop = None
    elif code:
        stop = _diagnosis_failed_step(diagnostic or {})
    elif blocked or admission_blocked:
        stop = 4
    else:
        stop = None
    items = []
    for number, title in enumerate(_DIAGNOSIS_STEPS, start=1):
        detail = ""
        if number == 2 and progress.get("planned_task_count"):
            detail = (f'Vormingstaken: {int(progress.get("terminal_task_count") or 0)} van '
                      f'{int(progress["planned_task_count"])} afgehandeld; {pending} nog open.')
        if number == 4:
            detail = (f'{int(diagnostics["issue_occurrence_count"])} controlepunten bij {blocked} passages. '
                      'Een controlepunt is geen inhoudelijk oordeel: een reviewer beslist.'
                      if diagnostics is not None else 'De uitkomst per passage is zichtbaar voor de aangewezen reviewer.')
        if running:
            if number < active:
                status, css = ("Eerder bereikt" if number in reached else "Geen fase vastgelegd"), ""
            elif number == active:
                status, css = "Bezig", ""
            else:
                status, css = f"Wacht op stap {active}", "waiting"
        elif stop is None:
            status, css = ("Geen blokkade vastgelegd", "") if number == 5 else ("Klaar", "")
        elif number < stop:
            status, css = "Klaar", ""
        elif number == stop:
            status, css = "Hier stopt het", "blocked"
        else:
            status, css = f"Wacht op stap {stop}", "waiting"
        css_attr = f' class="{css}"' if css else ""
        items.append(f'<li{css_attr}><h3>{number}. {escape(title)}</h3>'
                     f'<p class="diagnosis-status">{escape(status)}</p>{f"<p>{escape(detail)}</p>" if detail else ""}</li>')
    return (f'<section aria-labelledby="proces"><h2 id="proces">Wat Metis met dit document deed</h2>'
            f'<ol class="diagnosis-steps">{"".join(items)}</ol></section>')


def _diagnosis_actions_html(diagnostics: dict | None, repair: str) -> str:
    families = _diagnosis_families(diagnostics)
    if not families:
        return ""
    rows = "".join(
        f'<tr><td data-label="Volgorde">{index}</td>'
        f'<td data-label="Actie">{escape(_DIAGNOSIS_FAMILY_COPY.get(family, (family,))[0])}</td>'
        f'<td data-label="Passages" class="num">{int(values["candidate_count"])}</td>'
        f'<td data-label="Punten" class="num">{int(values["issue_occurrence_count"])}</td>'
        f'<td><a class="btn-secondary" href="{repair}">Open in Review</a></td></tr>'
        for index, (family, values) in enumerate(families, start=1))
    return ('<p>Begin bovenaan: daar zitten de meeste controlepunten.</p>'
            '<table class="diagnosis-table"><caption>Acties, op volgorde van aantal controlepunten</caption>'
            '<thead><tr><th scope="col">#</th><th scope="col">Actie</th><th scope="col" class="num">Passages</th>'
            '<th scope="col" class="num">Punten</th><th scope="col">Openen</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


def _diagnosis_findings_html(diagnostics: dict) -> str:
    from src.operations_console_app import _PROCESSING_FAMILY_LABELS
    if not int(diagnostics.get("blocked_candidate_count") or 0):
        return "<p>De controle vond geen geblokkeerde passages.</p>"
    articles = "".join(
        f'<article class="diagnosis-family"><h3>{escape(_DIAGNOSIS_FAMILY_COPY.get(family, ("", family, ""))[1])}</h3>'
        f'<p class="muted">{escape(_PROCESSING_FAMILY_LABELS.get(family, family))} · {int(values["candidate_count"])} passages · '
        f'{int(values["issue_occurrence_count"])} punten</p>'
        f'<p>{escape(_DIAGNOSIS_FAMILY_COPY.get(family, ("", "", ""))[2])}</p></article>'
        for family, values in _diagnosis_families(diagnostics))
    without = int(diagnostics.get("blocked_without_reason_count") or 0)
    anomaly = (f'<p>{without} geblokkeerde passage(s) hebben geen code. Meld dit bij de beheerder.</p>' if without else "")
    from src.processing_diagnostics_v1 import processing_issue_family
    codes = "".join(
        f'<tr><td><code>{escape(code)}</code></td>'
        f'<td>{escape(_PROCESSING_FAMILY_LABELS.get(processing_issue_family(code), processing_issue_family(code)))}</td>'
        f'<td class="num">{int(values["candidate_count"])}</td><td class="num">{int(values["issue_occurrence_count"])}</td></tr>'
        for code, values in diagnostics["by_reason_code"].items())
    return (f'{articles}{anomaly}<details><summary>Technische details: alle codes en aantallen</summary>'
            '<table class="diagnosis-table"><caption>Controlecodes</caption><thead><tr><th scope="col">Code</th>'
            '<th scope="col">Soort</th><th scope="col" class="num">Passages</th><th scope="col" class="num">Keer</th></tr></thead>'
            f'<tbody>{codes}</tbody></table></details>')


def _diagnosis_coverage_html(objects: list[dict]) -> str:
    from src.extract_coverage_v1 import DUTCH_STATUS_LABELS, coverage_panel_rows
    rows = coverage_panel_rows(objects)
    if not rows:
        return ""
    labels = list(DUTCH_STATUS_LABELS.values())
    head = "".join(f'<th scope="col" class="num">{escape(label)}</th>' for label in labels)
    body = "".join(
        f'<tr><th scope="row">{escape(str(row["section"]))}</th>'
        + "".join(f'<td data-label="{escape(label, quote=True)}" class="num">{int((row.get("labels") or {}).get(label) or 0)}</td>'
                  for label in labels) + "</tr>"
        for row in rows)
    return ('<details><summary>Controleoverzicht per kop</summary>'
            '<table class="diagnosis-coverage diagnosis-table"><caption>Status van de passages per kop van de bron</caption>'
            f'<thead><tr><th scope="col">Kop</th>{head}</tr></thead><tbody>{body}</tbody></table></details>')

def _authorized_documents(state, account, documents) -> list[dict[str, Any]]:
    """Processing scope plus publishers' existing publication document list."""
    roles = set(account.get("roles") or [])
    rows = []
    for envelope in documents:
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
    return (not state_filter or (state_filter == "blocked" and (bool(row["blocked"]) or row.get("processing_blocked")))
            or (state_filter == "errors" and bool(row["telemetry"]["errors"]))
            or (state_filter == "retry" and row["retry_allowed"])
            or (state_filter == "attention" and (row.get("processing_blocked") or (row.get("processing_access") and row["blocked"] is None)
                or bool(row["blocked"]) or bool(row["telemetry"]["errors"]))))


def documents_projection(state, account, *, query: str = "", state_filter: str = "", offset: int = 0,
                         limit: int = MAX_DOCUMENTS, scan_limit: int | None = None, partial_on_error: bool = False) -> dict[str, Any]:
    """One page of authorized documents; search and state filter run over the whole authorized list.

    ``offset`` and ``next_offset`` index the searched authorized list. Without a state
    filter ``total`` is exact; with one it is unknown until the scan reaches the end.
    """
    from src.console_read_operations_v1 import document_overview_operation
    from src.workflows.workflow_transaction_v1 import workflow_read_transaction
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    started = time.monotonic()
    with document_overview_operation(state, account, scan_limit=scan_limit) as (actor, inputs):
        window = _document_window(inputs, actor, query, state_filter, offset, limit)
        authorized, offset, limit, scan_end = window
        if not partial_on_error:
            try:
                with workflow_read_transaction(state.workflow_document_store):
                    inputs.select([e["snapshot_id"] for e in authorized[offset:scan_end]
                                   if _processing_access(actor, e)])
            except WorkflowDocumentStoreError as exc:
                from src.operations_console_v1 import ConsoleError
                raise ConsoleError('workflow_document_unavailable') from exc
    # Canonical storage and telemetry run after workflow SQL closes.
    if not partial_on_error:
        inputs.select_publication([e["snapshot_id"] for e in authorized[offset:scan_end]
                                   if _processing_access(actor, e)])
    if partial_on_error:
        return _notice_documents_page(inputs, actor, window=window, state_filter=state_filter,
                                      deadline=started + NOTICE_TIME_BUDGET_SECONDS)
    return _documents_page(inputs, actor, state_filter=state_filter, window=window)


def _processing_access(account, envelope):
    roles = set(account.get("roles") or [])
    return "researcher" in roles or ("reviewer" in roles and account["account_id"] in (envelope.get("named_reviewers") or []))


def _document_window(inputs, account, query, state_filter, offset, limit):
    query = query.strip().lower()
    authorized = [e for e in _authorized_documents(inputs.state, account, inputs.documents)
                  if not query or _matches_document(e, query)]
    offset, limit = max(0, offset), max(1, min(limit, MAX_DOCUMENTS))
    scan_end = min(len(authorized), offset + (MAX_SCAN if state_filter in DOCUMENT_STATES else limit))
    return authorized, offset, limit, scan_end


def _documents_page(inputs, account, *, query="", state_filter="", offset=0, limit=MAX_DOCUMENTS, window=None):
    authorized, offset, limit, scan_end = window or _document_window(inputs, account, query, state_filter, offset, limit)
    state_filter = state_filter if state_filter in DOCUMENT_STATES else ""
    telemetry, partial = _telemetry_by_document(time.time() - 86400) if offset < len(authorized) else ({}, False)
    rows, position = [], offset
    while position < scan_end and len(rows) < limit:
        envelope = authorized[position]
        position += 1
        if envelope["snapshot_id"] in getattr(inputs, "missing_snapshots", set()):
            continue
        row = _document_row(inputs, account, envelope, telemetry)
        if _state_matches(row, state_filter):
            rows.append(row)
    return {"documents": rows, "total": None if state_filter or inputs.metadata_partial else len(authorized), "offset": offset,
            "limit": limit, "next_offset": position if position < len(authorized) else None,
            "telemetry_partial": partial, "metadata_partial": inputs.metadata_partial}


def _notice_documents_page(inputs, account, *, window, state_filter, deadline):
    """Independent bounded SQL batches, with external work between transactions.

    Earlier successful batches survive a failed/expired batch. next_offset points
    to the first unexamined row, so failure never masquerades as an empty success.
    Each batch has its own SQL snapshot; no cross-batch atomicity is claimed.
    """
    from src.workflows.workflow_transaction_v1 import workflow_read_transaction
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    authorized, offset, limit, scan_end = window
    position, rows = offset, []
    telemetry, telemetry_partial = None, False
    diagnostic_partial = False
    while position < scan_end and len(rows) < limit:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            diagnostic_partial = True
            LOG.warning("document_diagnostic_budget_exhausted")
            break
        batch = authorized[position:min(scan_end, position + DIAGNOSTIC_BATCH_SIZE)]
        ids = [e["snapshot_id"] for e in batch if _processing_access(account, e)]
        try:
            if ids:
                with workflow_read_transaction(inputs.state.workflow_document_store) as con:
                    # Lower the existing statement limit to this operation's remainder.
                    con.execute("SELECT set_config('statement_timeout', %s, true)",
                                (str(max(1, min(5000, int(remaining * 1000)))),))
                    inputs.select(ids)
        except WorkflowDocumentStoreError:
            diagnostic_partial = True
            LOG.warning("document_diagnostic_batch_unavailable")
            break
        inputs.select_publication(ids)
        if telemetry is None:
            telemetry, telemetry_partial = _telemetry_by_document(time.time() - 86400)
        for envelope in batch:
            position += 1
            if envelope["snapshot_id"] in inputs.missing_snapshots:
                continue
            row = _document_row(inputs, account, envelope, telemetry)
            if _state_matches(row, state_filter):
                rows.append(row)
                if len(rows) >= limit:
                    break
    return {"documents": rows, "total": None, "offset": offset, "limit": limit,
            "next_offset": position if diagnostic_partial or position < len(authorized) else None,
            "telemetry_partial": telemetry_partial, "metadata_partial": inputs.metadata_partial,
            "diagnostic_partial": diagnostic_partial}


def _document_row(inputs, account, envelope: dict[str, Any], telemetry: dict[str, dict[str, int]]) -> dict[str, Any]:
    from src.operations_console_v1 import stored_processing_blocked
    from src.request_diagnostics_v1 import doc_ref
    sid = envelope["snapshot_id"]
    roles = set(account.get("roles") or [])
    processing_access = "researcher" in roles or ("reviewer" in roles and account["account_id"] in envelope.get("named_reviewers", []))
    if processing_access:
        status, diagnostics = inputs.status_and_diagnostics(envelope)
    else:
        status, diagnostics = {}, {"blocked_candidate_count": None, "by_reason_code": {}}
    ref = doc_ref(sid)
    reasons = list((diagnostics.get("by_reason_code") or {}).items())[:3]
    return {
        "snapshot_id": sid, "doc_ref": ref, "title": envelope.get("title") or sid,
        "version": envelope.get("version"), "class": envelope.get("class"),
        "state": status.get("state") or envelope.get("state"),
        "code": status.get("error_code") or status.get("reason_code"),
        "retry_allowed": bool(status.get("retry_allowed")),
        "blocked": diagnostics.get("blocked_candidate_count"),
        "processing_access": processing_access,
        "processing_blocked": stored_processing_blocked(envelope),
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
        if tab == "kwaliteit" and request.query_params.get("view") == "table":
            return app.state.insight_quality_table(request)
        html = render_page(nav(account, "settings") + insight_body(insight_tabs(tab), tab), title="Inzicht — Metis")
        return HTMLResponse(html, headers=_HEADERS)

    @app.get("/inzicht/document", response_class=HTMLResponse)
    def document_diagnosis(request: Request, document: str = "") -> HTMLResponse:
        from src.domain_dimensions_v1 import processing_issue_objects
        from src.operations_console_app import ERROR_COPY
        from src.processing_diagnostics_v1 import processing_diagnostics
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
        progress = processing.get("formation_progress") or {}
        attempts = (envelope.get("processing_attempts") or []) if processing_access else []
        diagnostic = (attempts[-1].get("diagnostic") or {}) if attempts else {}
        pages = [str(page) for page in diagnostic.get("unverified_pages") or [] if type(page) is int]
        pages_html = f'<p>Pagina’s zonder verwerkbare brontekst: {escape(", ".join(pages))}</p>' if pages else ""
        pages_html += _source_pages_html(envelope, diagnostic, document) if processing_access else ""
        passages = '<p>Passagediagnostiek en passage-exports zijn beschikbaar voor de aangewezen reviewer.</p>'
        passage_exports = ""
        source_exports = (f'<li><a href="/inzicht/document/verwerkingsspoor?{query}">Verwerkingsspoor (JSON)</a></li>'
                          if processing_access else "")
        publication_export = (f'<li><a href="/inzicht/document/publicatiebewijs?{query}">Publicatiebewijs (JSON)</a></li>'
                              if "publisher" in roles else "")
        repair = f'/review?{query}&amp;task=repair'
        diagnostics = None
        admission_blocked = False
        if processing_access:
            # Reuse the existing request-owned object reader and its captured inputs.
            # Researchers may see the aggregate block, never reviewer-only details.
            objects = state._read_current_objects(document)
            if reviewer:
                diagnostics = processing_diagnostics(objects)
                admission_blocked = bool(diagnostics["blocked_candidate_count"])
            else:
                admission_blocked = bool(processing_issue_objects(objects))
        if reviewer:
            burden = review_burden_projection(read_events(state._ledger_path), snapshot_id=document)
            passages = (_diagnosis_findings_html(diagnostics) + _diagnosis_coverage_html(objects)
                + f'<details><summary>Reviewinteracties</summary><p>{int(burden["review_interactions"])} gemeten menselijke interacties voor '
                  f'{int(burden["object_decisions"])} objectbesluiten. Historische besluiten zonder meting: '
                  f'{int(burden["legacy_unmeasured_decisions"])}.</p></details>'
                + f'<p><a class="btn-secondary" href="{repair}">Passages corrigeren in Review</a></p>')
            passage_exports = f'''<li>Bronpassages: <a href="/inzicht/document/passages?{query}&amp;format=csv">CSV</a> ·
              <a href="/inzicht/document/passages?{query}&amp;format=json">JSON</a></li>
              <li><a href="/inzicht/document/diagnostiek?{query}">Diagnostiek (JSON)</a></li>
              <li><a href="/inzicht/document/detaildiagnostiek?{query}">Detaildiagnostiek (JSON)</a></li>
              <li><a href="/inzicht/document/verwerkingsbewijs?{query}">Verwerkingsbewijs als CSV-pakket</a></li>'''
        if processing_access:
            label = ("Verwerking loopt" if processing.get("state") == "running"
                     else "Niet publiceerbaar" if code or admission_blocked
                     else "Geen blokkade vastgelegd")
            facts = []
            if progress.get("planned_task_count"):
                facts.append(("Vormingstaken klaar", f'{int(progress.get("terminal_task_count") or 0)}/{int(progress["planned_task_count"])}'))
            if diagnostics is not None:
                facts += [("Passages met controlepunten", int(diagnostics["blocked_candidate_count"])),
                          ("Controlepunten", int(diagnostics["issue_occurrence_count"]))]
            facts.append(("Opgeslagen pogingen", len(attempts)))
            facts_html = "".join(f"<div><dt>{escape(name)}</dt><dd>{escape(str(value))}</dd></div>" for name, value in facts)
            review_button = (f'<p class="diagnosis-buttons"><a class="btn-primary" href="{repair}">Passages corrigeren in Review</a>'
                             '<a class="btn-secondary" href="#acties">Bekijk wat er moet gebeuren</a></p>' if reviewer else "")
            attempt_rows = "".join(
                f'<dt>{escape(name)}</dt><dd><code>{escape(str(diagnostic[key]))}</code></dd>'
                for key, name in (("outcome", "Uitkomst laatste poging"), ("reason_code", "Reden laatste poging"),
                                  ("recovery_advice", "Advies laatste poging")) if diagnostic.get(key))
            verdict = f'''<div class="diagnosis-verdict"{' data-state="blocked"' if label == "Niet publiceerbaar" else ""} role="status">
              <p class="diagnosis-label">{_diagnosis_icon(label)} {escape(label)}</p>
              <p class="lead">{escape(ERROR_COPY.get(code, "Controleer de actuele verwerking."))}</p>
              <p>Een technisch geslaagde poging bewijst niet dat bronverwerking, review of publicatievoorwaarden volledig zijn afgerond.</p>
              <dl class="diagnosis-facts">{facts_html}</dl>{review_button}
              <details><summary>Technische details</summary><dl class="diagnosis-summary">
                <dt>Status</dt><dd><code>{escape(str(processing.get("state") or "niet vastgelegd"))}</code></dd>
                <dt>Code</dt><dd><code>{escape(str(code))}</code></dd>{attempt_rows}</dl></details></div>'''
            processing_html = (f'''<section id="verwerking" aria-labelledby="oordeel"><h2 id="oordeel">Oordeel</h2>{verdict}</section>
          {_diagnosis_steps_html(processing, code, progress, diagnostics, diagnostic, admission_blocked=admission_blocked)}
          <section id="acties"><h2>Wat er nu moet gebeuren</h2>
            {_diagnosis_actions_html(diagnostics, repair)}{controls}{pages_html}</section>''')
        else:
            processing_html = ('<section id="verwerking" aria-labelledby="oordeel"><h2 id="oordeel">Oordeel</h2>'
                               '<div class="diagnosis-verdict" role="status"><p class="diagnosis-label">Geen verwerkingsinzage</p>'
                               '<p>Verwerkingsdiagnostiek is beschikbaar voor onderzoekers en aangewezen reviewers.</p></div></section>')
        attempt_card = (f'''<div class="diagnosis-card"><h3>Laatste verwerkingspoging</h3><dl class="diagnosis-summary">
              <dt>Opgeslagen pogingen</dt><dd>{len(attempts)}</dd>
              <dt>Bronversie</dt><dd>{escape(str(envelope.get("version") or ""))}</dd>
              <dt>Nieuwe poging vanaf</dt><dd>{escape(str(processing.get("retry_not_before") or "niet van toepassing"))}</dd></dl>
              <p><a href="/inzicht/document/blokkade?{query}">Blokkade en bewijs per verwerkingspoging onderzoeken</a></p></div>'''
                        if processing_access else "")
        from src.view_check import panel as view_check_panel
        view_checks = view_check_panel(app, state, account, document, request.query_params.get('attempt', ''))
        body = f'''{nav(account, "settings")}{_DIAGNOSIS_STYLE}<section class="room document-diagnosis">
          {insight_tabs("documenten")}
          <p><a href="/inzicht?tab=documenten">← Alle documentdiagnoses</a></p>
          <h1>Documentdiagnose: {escape(str(envelope.get("title") or document))}</h1>
          <p>Bronversie {escape(str(envelope.get("version") or ""))}</p>
          <nav aria-label="Documentdiagnose"><a href="#verwerking">Oordeel</a> ·
            <a href="#passages">Passages en brondekking</a> · <a href="#bewijs">Bewijs</a></nav>
          {processing_html}
          <section id="passages"><h2>Wat de controle vond</h2>{passages}</section>
          {view_checks}
          <section id="bewijs"><h2>Bewijs en downloads</h2><div class="diagnosis-cards">{attempt_card}
            <div class="diagnosis-card"><h3>Downloads</h3><ul class="export-options">
            {source_exports}{publication_export}{passage_exports}</ul></div></div></section></section>'''
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


def _source_pages_html(envelope: dict, diagnostic: dict, document: str) -> str:
    """Per page: problem, repair action and the accounting form; never source text."""
    from src.docling_contract_v1 import DoclingError, set_aside_pages
    from src.operations_console_app import PAGE_FINDING_COPY
    from src.operations_console_v1 import ConsoleError, SOURCE_PAGE_ACCOUNTING_CATEGORIES
    parts = []
    findings = diagnostic.get("page_findings") or []
    if findings:
        options = "".join(f'<option value="{escape(key)}">{escape(label)}</option>'
                          for key, label in SOURCE_PAGE_ACCOUNTING_CATEGORIES.items())
        rows = []
        for row in findings:
            copy = [PAGE_FINDING_COPY.get(code, (code, "Meld dit bij de beheerder.")) for code in row.get("reasons") or []]
            problem = " ".join(problem for problem, _ in copy)
            action = " ".join(dict.fromkeys(action for _, action in copy))
            accounted = any(done["page"] == row["page"] and done["reasons"] == row.get("reasons")
                            and done["source_sha256"] == envelope.get("sha256")
                            for done in envelope.get("source_page_accountings") or [])
            if accounted:
                rows.append(f'<tr><td>{int(row["page"])}</td><td>{escape(problem)}</td><td>{escape(action)}</td>'
                            '<td>Verantwoord; start de verwerking opnieuw.</td></tr>')
                continue
            rows.append(f'''<tr><td>{int(row["page"])}</td><td>{escape(problem)}</td><td>{escape(action)}</td>
              <td><form method="post" action="/inzicht/document/pagina-verantwoorden">
                <input type="hidden" name="snapshot_id" value="{escape(document, quote=True)}">
                <input type="hidden" name="page" value="{int(row["page"])}">
                <label>Reden<select name="category" required>{options}</select></label>
                <label>Toelichting<input name="note" required minlength="10" maxlength="500"></label>
                <button type="submit">Pagina verantwoorden</button></form></td></tr>''')
        parts.append('<section id="paginas"><h3>Onopgeloste pagina’s</h3>'
                     '<p>Verantwoord alleen een pagina zonder kennisinhoud. Start daarna de verwerking opnieuw.</p>'
                     '<table><thead><tr><th>Pagina</th><th>Probleem</th><th>Herstelactie</th><th>Verantwoorden</th></tr></thead>'
                     f'<tbody>{"".join(rows)}</tbody></table></section>')
    try:
        left_out = set_aside_pages(envelope)
    except (DoclingError, ConsoleError):
        left_out = []
    if left_out:
        labels = {"pdf_page_without_content": "leeg volgens de PDF", "recorded_accounting": "verantwoord"}
        listed = "; ".join(f'pagina {int(row["page"])} ({labels.get(row.get("basis"), "onbekend")})' for row in left_out)
        parts.append(f'<p>Buiten de bron gelaten pagina’s: {escape(listed)}.</p>')
    accountings = envelope.get("source_page_accountings") or []
    if accountings:
        items = "".join(f'<li>Pagina {int(row["page"])}: {escape(SOURCE_PAGE_ACCOUNTING_CATEGORIES.get(row["category"], row["category"]))}'
                        f' — {escape(row["note"])} ({escape(row["recorded_at"][:10])})</li>' for row in accountings)
        parts.append(f'<details><summary>Vastgelegde verantwoordingen ({len(accountings)})</summary><ul>{items}</ul></details>')
    return "".join(parts)
