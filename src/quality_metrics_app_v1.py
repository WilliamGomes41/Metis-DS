"""Authorized quality table and report history in Inzicht; no workflow authority."""
from copy import deepcopy
from datetime import date
from html import escape
import logging
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse

from src.quality_evidence_v1 import instant
from src.quality_metrics_v1 import build_report
from src.quality_metrics_store_v1 import QualityReportStore
from src.review_ledger import read_events
from src.workflows.workflow_transaction_v1 import workflow_read_transaction

LOG = logging.getLogger(__name__)


def _quality_documents(cards, account_id):
    return [row for row in cards if row.get("uploader_account_id") == account_id
            or account_id in (row.get("named_reviewers") or [])]


def current_quality_scope(state, account):
    """Fresh post-calculation access check; no repeated source/object capture."""
    with state.document_read_operation(), workflow_read_transaction(state.workflow_document_store):
        cards = state.list_document_cards()
    return {row["snapshot_id"] for row in _quality_documents(cards, account["account_id"])}


def capture(state, account):
    """Own metadata, then freeze assigned SQL inputs before external work.

    Metadata and detail capture are independent SQL snapshots. No consumer or
    source computation runs with an open read transaction.
    """
    owner = state.workflow_document_store
    with state.document_read_operation():
        with workflow_read_transaction(owner):
            cards = state.list_document_cards()
        owned = _quality_documents(cards, account["account_id"])
        with workflow_read_transaction(owner):
            envelopes = [state._envelope(e["snapshot_id"]) for e in owned]
            # Capture native rows only. Revision validation and detached copies may
            # be CPU-heavy and belong after the transaction, just like source I/O.
            reads = state._document_reads()
            for envelope in envelopes:
                state._load_objects(envelope["snapshot_id"], remember=False)
            ids = [e["snapshot_id"] for e in envelopes]
            from src.operations_console_v1 import ConsoleError
            from src.workflows.workflow_review_postgres_v1 import WorkflowReviewStoreError
            try:
                bindings = state.workflow_review_store.read_bindings(ids)
            except WorkflowReviewStoreError as exc:
                raise ConsoleError("workflow_review_unavailable", str(exc)) from exc
            reads.bindings.update({sid: bindings.get(sid, []) for sid in ids})
            # Attribution needs IDs only; never fetch another source's object payloads.
            with owner._connect() as con:
                object_ids = con.execute("SELECT DISTINCT snapshot_id,object_id FROM workflow.document_objects").fetchall()
        ownership = {e["snapshot_id"]: {e["snapshot_id"]} for e in cards}
        for obj in object_ids:
            ownership.setdefault(obj["object_id"], set()).add(obj["snapshot_id"])
        # Source verification/reconstruction may touch disk/Blob or extract data.
        # Ledger dispatch may also be file-backed. Neither belongs in a SQL read.
        docs = [{"envelope": state._receipt(e), "objects": state.snapshot_objects(e["snapshot_id"]),
                 "events": [], "bindings": state.object_review_bindings(e["snapshot_id"]),
                 "fragments": None} for e in envelopes]
        by_id = {d["envelope"]["snapshot_id"]: d for d in docs}
        for doc in docs:
            doc["fragments"] = state.review_source_fragments(doc["envelope"]["snapshot_id"], envelope=doc["envelope"])
        for event in read_events(state._ledger_path):
            payload = event.get("details") or {}
            sid = payload.get("snapshot_id") or (payload.get("review_interaction") or {}).get("snapshot_id")
            if not sid:
                candidates = ownership.get(event.get("object_id"), set())
                sid = next(iter(candidates)) if len(candidates) == 1 else None
            if sid in by_id:
                by_id[sid]["events"].append(deepcopy(event))
        return {"documents": docs, "observed_at": instant()}


class QualityViewError(Exception):
    """A quality view that cannot be shown; ``status`` and a Dutch reason only."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


def validate_filters(query) -> dict:
    filters = {k: query[k] for k in ("from", "to", "kind", "ingest", "route") if query.get(k)}
    try:
        for k in ("from", "to"):
            if k in filters:
                date.fromisoformat(filters[k])
        if filters.get("from", "") > filters.get("to", "9999-12-31"):
            raise ValueError("date_order")
    except ValueError as exc:
        raise QualityViewError(400, "Ongeldige periode") from exc
    return filters


def quality_view(state, store, account, filters, requested_id=None):
    """The one quality measurement for both the table page and Inzicht charts.

    Same capture, authorization scope and immutable report store as before.
    """
    try:
        inputs = capture(state, account)
        inputs["filters"] = filters
        inputs["observation_day"] = inputs["observed_at"][:10]
        if requested_id:
            scope = {d["envelope"]["snapshot_id"] for d in inputs["documents"]}
            available = store.history(owner=account["account_id"], allowed_scope=scope)
            record = next((r for r in available if r["calculation_id"] == requested_id), None)
            if record is None:
                raise QualityViewError(404, "Dit rapport is niet beschikbaar voor jou.")
        else:
            record = store.calculate(owner=account["account_id"], inputs=inputs,
                build=lambda i: build_report(i["documents"], as_of=i["observed_at"], filters=i["filters"]))
        allowed = current_quality_scope(state, account)
        if not set(record["report"]["scope"]) <= allowed:
            raise QualityViewError(409, "Toegang is gewijzigd. Vernieuw de pagina.")
        history = store.history(owner=account["account_id"], allowed_scope=allowed)
    except QualityViewError:
        raise
    except Exception as exc:
        LOG.exception("Quality report unavailable")
        raise QualityViewError(503, "De meting is niet beschikbaar. Je werk blijft behouden. Vernieuw de pagina om opnieuw te proberen; eerdere rapporten blijven bewaard.") from exc
    return {"record": record, "report": record["report"], "history": history}


def quality_store(state):
    owner = getattr(state, "workflow_document_store", None)
    connect = getattr(owner, "_metis_workflow_original_connect", None) or (owner._connect if owner else None)
    return QualityReportStore(state.runtime / "quality_reports", connect=connect)


def install_quality_routes(app, state, require, page, *, tabs=lambda current: ""):
    store = quality_store(state)
    app.state.quality_store = store

    def quality(request: Request):
        from src.operations_console_app import _nav
        account = require(request)
        context = {k: v for k, v in request.query_params.items() if k not in {"tab", "view"}}
        graph_url = escape('/inzicht?' + urlencode({**context, 'tab': 'kwaliteit'}), quote=True)
        body = (_nav(account, "settings") + '<section class="room">' + tabs("kwaliteit") + '<h1>Kwaliteit &amp; werkproces</h1>'
                '<p>Automatisch afgeleid uit bestaande verwerking en review, voor bronnen waarvan je uploader of aangewezen reviewer bent.</p>'
                f'<nav aria-label="Kwaliteitsweergave"><a href="{graph_url}">Grafieken</a> · <strong aria-current="page">Tabel en rapporthistorie</strong></nav>')
        try:
            filters = validate_filters(request.query_params)
            view = quality_view(state, store, account, filters, request.query_params.get("report"))
        except QualityViewError as exc:
            if exc.status == 400:
                return HTMLResponse(page('<h1>Ongeldige periode</h1><a href="/inzicht?tab=kwaliteit&amp;view=table">Terug</a>'), status_code=400)
            return HTMLResponse(page(body + f'<p>{escape(exc.reason)}</p></section>'), status_code=exc.status)
        report, history = view["report"], view["history"]
        filters = report["filters"]
        esc = lambda value: escape(str(value))
        body += '<form method="get" action="/inzicht"><input type="hidden" name="tab" value="kwaliteit"><input type="hidden" name="view" value="table"><p>Ingestcohort (UTC; activiteit tot gegevensgrens)</p>'
        for key, label, typ in (("from", "Vanaf", "date"), ("to", "Tot en met", "date"), ("kind", "Inhoudstype", "text"), ("ingest", "Ingesttype", "text")):
            body += f'<label>{label} <input type="{typ}" name="{key}" value="{esc(filters.get(key, ""))}"></label> '
        body += '<label>Verwerkingsroute <select name="route">'
        for value, label in (("", "Alle routes"), ("deterministic", "Deterministisch"), ("semantic", "Semantisch"), ("mixed", "Gemengd"), ("remainder", "Resterende bronpassages"), ("unknown", "Onbekend")):
            selected = " selected" if filters.get("route", "") == value else ""
            body += f'<option value="{value}"{selected}>{label}</option>'
        body += '</select></label> <button>Toon meting</button></form>'
        body += f'<p>Beschikbaar · gegevensgrens {esc(report["as_of"])} · definitie {esc(report["definition_version"])} · {report["cohort_size"]} bronnen</p>'
        body += '<h2>Hoe vaak zijn voorstellen direct bruikbaar?</h2><table><thead><tr><th>Route van het voorstel</th><th>Direct / eerste besluiten</th><th>Vergelijkbaar</th><th>Percentage</th><th>Herstelverzoeken</th><th>Correcties</th></tr></thead><tbody>'
        labels = {"deterministic": "Deterministisch", "semantic": "Semantisch", "remainder": "Resterende bronpassages", "unknown": "Onbekend"}
        for route, row in report["routes"].items():
            rate = f'{row["direct_rate"]:.0%}' if row["direct_rate"] is not None else 'Niet volledig meetbaar'
            body += f'<tr><td>{labels[route]}</td><td>{row["direct"]} / {row["first_decisions"]}</td><td>{row["known_comparisons"]} / {row["first_decisions"]}</td><td>{rate}</td><td>{row["repair_requests"]}</td><td>{row["corrections"]}</td></tr>'
        burden = report["burden"]
        body += f'</tbody></table><h2>Menselijke handelingen</h2><p>{burden["review_interactions"]} vastgelegde beslisinteracties; {burden["object_decisions"]} objectbesluiten. Legacy-besluiten zonder interactiebewijs: {burden["legacy_unmeasured_decisions"]}. Een batch telt als één interactie.</p>'
        body += '<h2>Waar blijft werk liggen?</h2><table><thead><tr><th>Bron</th><th>Route</th><th>Open passages</th><th>Leeftijd onafgehandelde bron</th><th>Verwerkingsblokkade</th></tr></thead><tbody>'
        for doc in report["documents"]:
            age = f'{doc["source_age_days"]:.1f} dagen' if doc["source_age_days"] is not None else 'Niet van toepassing / onbekend'
            body += f'<tr><td>{esc(doc["title"])}</td><td>{esc(doc["route"])}</td><td>{doc["open_passages"]}</td><td>{age}</td><td>{esc(doc["processing_blocker"] or "—")}</td></tr>'
        body += '</tbody></table><h2>Doorlooptijd en inhoudelijke problemen</h2>'
        duration = report["publication_duration_seconds"]
        body += f'<p>Ingest tot eerste publicatie: {duration["samples"]} waarnemingen. Mediaan: {round(duration["median"] / 86400, 1) if duration["median"] is not None else "onbekend"} dagen.</p>'
        body += '<table><thead><tr><th>Route</th><th>Afwijzingen</th><th>Correcties na goedkeuring</th><th>Gewijzigde inhoud</th></tr></thead><tbody>'
        field_labels = {"text": "tekst", "type": "type", "relations": "relaties", "semantics": "aanbevelingsbetekenis"}
        for route, row in report["routes"].items():
            changes = ', '.join(f'{field_labels.get(k, k)}: {v}' for k, v in row['changed_fields'].items()) or 'Geen vastgelegd verschil'
            body += f'<tr><td>{labels[route]}</td><td>{row["rejections"]}</td><td>{row["corrections_after_approval"]}</td><td>{esc(changes)}</td></tr>'
        body += '</tbody></table><p>Dit zijn waargenomen review- en herstelsignalen. Een wijziging bewijst op zichzelf geen inhoudelijke fout.</p>'
        body += '<p>' + esc(report["readiness_duration"]["reason"]) + '</p><p>' + esc(report["clinical_errors"]["reason"]) + '</p>'
        discrepancies = report.get("source_discrepancies")  # absent in reports of definition 1.0.0
        if discrepancies is not None:
            from src.source_discrepancy_v1 import CATEGORIES
            body += ('<h2>Gemelde discrepanties met de originele tekst</h2>'
                     f'<p>{discrepancies["reports"]} gemelde discrepanties, waarvan {discrepancies["critical"]} kritiek '
                     '(tekst of bronplek wijkt af). Melden is optioneel; geen melding bewijst geen overeenstemming.</p>'
                     '<table><thead><tr><th>Soort</th><th>Meldingen</th></tr></thead><tbody>')
            for code, label in CATEGORIES.items():
                body += f'<tr><td>{esc(label)}</td><td>{discrepancies["categories"].get(code, 0)}</td></tr>'
            body += '</tbody></table><table><thead><tr><th>Vormingsroute</th><th>Model</th><th>Meldingen</th></tr></thead><tbody>'
            for row in discrepancies["by_formation"]:
                body += f'<tr><td>{esc(row["formation_mode"])}</td><td>{esc(row["model"])}</td><td>{row["reports"]}</td></tr>'
            body += '</tbody></table>'
        body += '<details><summary>Meetdefinities en beperkingen</summary>' + ''.join('<p>' + esc(v) + '</p>' for v in [*report["definitions"].values(), *report["limitations"]]) + '</details>'
        body += '<h2>Rapporthistorie</h2><p>Eerdere beschikbare metingen blijven ongewijzigd bewaard.</p><ul>'
        for old in history[:20]:
            r = old["report"]
            body += f'<li><a href="/inzicht?tab=kwaliteit&amp;view=table&amp;report={esc(old["calculation_id"])}">{esc(r["as_of"])}</a> · {esc(r["definition_version"])} · {r["cohort_size"]} bronnen · {r["open_passages"]} open passages · {len(old["attempts"])} poging(en)</li>'
        body += '</ul>'
        return HTMLResponse(page(body + '</section>', title='Kwaliteit & werkproces — Inzicht — Metis'), headers={"Cache-Control": "no-store"})

    app.state.insight_quality_table = quality
