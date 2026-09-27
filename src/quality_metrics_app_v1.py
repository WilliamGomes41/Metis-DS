"""Authorized, passive quality reporting in Settings; no workflow authority."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import date
from html import escape
import logging

from fastapi import Request
from fastapi.responses import HTMLResponse

from src.quality_evidence_v1 import instant
from src.quality_metrics_v1 import build_report
from src.quality_metrics_store_v1 import QualityReportStore
from src.review_ledger import read_events
from src.workflows.workflow_transaction_v1 import workflow_transaction

LOG = logging.getLogger(__name__)


def capture(state, account):
    """Freeze only explicitly assigned/owned sources under existing store lock."""
    owner = getattr(state, "workflow_document_store", None)
    with state._store_write_lock():
        with workflow_transaction(owner) if owner else nullcontext() as con:
            if con is not None:
                con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            state._reload_store_locked()
            aid = account["account_id"]
            envelopes = [e for e in state.list_envelopes()
                         if e.get("uploader_account_id") == aid or aid in (e.get("named_reviewers") or [])]
            docs = [{"envelope": deepcopy(e), "objects": state.snapshot_objects(e["snapshot_id"]),
                     "events": [], "bindings": state.object_review_bindings(e["snapshot_id"])} for e in envelopes]
            by_id = {d["envelope"]["snapshot_id"]: d for d in docs}
            # Legacy events are attributed only when their object ID is unique globally.
            ownership = {}
            for e in state.list_envelopes():
                sid = e["snapshot_id"]
                ownership.setdefault(sid, set()).add(sid)
                for obj in state.snapshot_objects(sid):
                    ownership.setdefault(obj["object_id"], set()).add(sid)
            for event in read_events(state._ledger_path):
                payload = event.get("details") or {}
                sid = payload.get("snapshot_id") or (payload.get("review_interaction") or {}).get("snapshot_id")
                if not sid:
                    candidates = ownership.get(event.get("object_id"), set())
                    sid = next(iter(candidates)) if len(candidates) == 1 else None
                if sid in by_id:
                    by_id[sid]["events"].append(deepcopy(event))
            return {"documents": docs, "observed_at": instant()}


def install_quality_routes(app, state, require, page):
    owner = getattr(state, "workflow_document_store", None)
    connect = getattr(owner, "_metis_workflow_original_connect", None) or (owner._connect if owner else None)
    store = QualityReportStore(state.runtime / "quality_reports", connect=connect)

    @app.get("/settings/quality", response_class=HTMLResponse)
    def quality(request: Request):
        account = require(request)
        filters = {k: request.query_params[k] for k in ("from", "to", "kind", "ingest", "route") if request.query_params.get(k)}
        try:
            for k in ("from", "to"):
                if k in filters:
                    date.fromisoformat(filters[k])
            if filters.get("from", "") > filters.get("to", "9999-12-31"):
                raise ValueError("date_order")
        except ValueError:
            return HTMLResponse(page('<h1>Ongeldige periode</h1><a href="/settings/quality">Terug</a>'), status_code=400)
        body = '<p><a href="/settings">← Instellingen</a></p><h1>Kwaliteit &amp; werkproces</h1><p>Automatisch afgeleid uit bestaande verwerking en review, voor bronnen waarvan je uploader of aangewezen reviewer bent.</p>'
        try:
            inputs = capture(state, account)
            inputs["filters"] = filters
            inputs["observation_day"] = inputs["observed_at"][:10]
            requested_id = request.query_params.get("report")
            if requested_id:
                scope = {d["envelope"]["snapshot_id"] for d in inputs["documents"]}
                available = store.history(owner=account["account_id"], allowed_scope=scope)
                record = next((r for r in available if r["calculation_id"] == requested_id), None)
                if record is None:
                    return HTMLResponse(page(body + '<p>Dit rapport is niet beschikbaar voor jou.</p>'), status_code=404)
            else:
                record = store.calculate(owner=account["account_id"], inputs=inputs,
                    build=lambda i: build_report(i["documents"], as_of=i["observed_at"], filters=i["filters"]))
            report = record["report"]
            filters = report["filters"]
            current = capture(state, account)
            allowed = {d["envelope"]["snapshot_id"] for d in current["documents"]}
            if not set(report["scope"]) <= allowed:
                return HTMLResponse(page(body + '<p>Toegang is gewijzigd. Vernieuw de pagina.</p>'), status_code=409)
            history = store.history(owner=account["account_id"], allowed_scope=allowed)
        except Exception:
            LOG.exception("Quality report unavailable")
            return HTMLResponse(page(body + '<p>De meting is niet beschikbaar. Je werk blijft behouden. Vernieuw de pagina om opnieuw te proberen; eerdere rapporten blijven bewaard.</p>'), status_code=503)
        esc = lambda value: escape(str(value))
        body += '<form method="get"><p>Ingestcohort (UTC; activiteit tot gegevensgrens)</p>'
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
        body += '<details><summary>Meetdefinities en beperkingen</summary>' + ''.join('<p>' + esc(v) + '</p>' for v in [*report["definitions"].values(), *report["limitations"]]) + '</details>'
        body += '<h2>Rapporthistorie</h2><p>Eerdere beschikbare metingen blijven ongewijzigd bewaard.</p><ul>'
        for old in history[:20]:
            r = old["report"]
            body += f'<li><a href="/settings/quality?report={esc(old["calculation_id"])}">{esc(r["as_of"])}</a> · {esc(r["definition_version"])} · {r["cohort_size"]} bronnen · {r["open_passages"]} open passages · {len(old["attempts"])} poging(en)</li>'
        body += '</ul>'
        return page('<section class="room">' + body + '</section>', title='Kwaliteit & werkproces — Metis')
