"""Route comparison under Inzicht controls, outside normal Review.

The comparison measured the retired deterministic formation route against the
semantic route. New comparisons are refused and the deterministic arm never
runs again; recorded comparisons stay readable and can still be assessed,
analysed, closed or cancelled.
"""
from __future__ import annotations

from html import escape
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from src.route_comparison_v1 import (
    ComparisonError, ComparisonStore, analyze, assess, blind_view, cancel,
    claim_arm, close, fail_arm, finish_arm,
)
from src.llm_provider_v1 import load_llm_provider_config
from src.pre_review_semantic_v1 import semantic_units_before_review

LOG = logging.getLogger(__name__)
RETIRED = "comparison_route_retired"


def _units(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for unit in units:
        if unit.get("object_type") in {"heading", "path", "document"}:
            continue
        text = str(unit.get("clean_text") or unit.get("text") or "").strip()
        if text:
            out.append({"text": text, "type": unit.get("proposed_object_type") or unit.get("object_type"),
                        "source_fragment_ids": list(unit.get("source_fragment_ids") or [])})
    return out


def execute_arm(row: dict[str, Any], route: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Call the semantic pre-Review formation on frozen fragments (the only arm that runs)."""
    fragments = row["fragments"]
    document_id = "experiment-" + row["comparison_id"]
    if route != "semantic":
        raise ComparisonError("comparison_route_invalid")
    config = load_llm_provider_config(os.environ)
    if not config.configured or config.model != row["semantic_model"]:
        raise ComparisonError("comparison_model_configuration_changed")
    units = semantic_units_before_review(
        fragments, document_id=document_id, api_key=config.api_key, model=config.model
    )
    return _units(units), {"strategy": route, "model": config.model,
                           "code_version": row["code_version"]}


def install_route_comparison_routes(app, state, require, page) -> None:
    owner = getattr(state, "workflow_document_store", None)
    connect = getattr(owner, "_metis_workflow_original_connect", None) or (owner._connect if owner else None)
    store = ComparisonStore(state.runtime / "route_comparisons", connect=connect)

    def scope(account: dict[str, Any]) -> dict[str, dict[str, Any]]:
        # Match the existing Quality & workprocess account boundary.
        with state._store_write_lock():
            state._reload_store_locked()
            aid = account["account_id"]
            return {e["snapshot_id"]: e for e in state.list_envelopes()
                    if e.get("uploader_account_id") == aid or aid in (e.get("named_reviewers") or [])}

    def current(request: Request, comparison_id: str):
        account = require(request)
        allowed = scope(account)
        row = store.get(comparison_id, allowed_scope=set(allowed))
        if row is None:
            raise ComparisonError("comparison_not_found")
        return account, allowed, row

    def render(request: Request, body: str, *, status: int = 200) -> HTMLResponse:
        from src.insight_v1 import insight_tabs
        from src.operations_console_app import _nav
        account = require(request)
        return HTMLResponse(page(_nav(account, "settings") + '<section class="room">' + insight_tabs("controles")
                                 + '<p><a href="/inzicht?tab=controles">← Inzicht · Controles</a></p>'
                                 + body + '</section>', title="Routevergelijking — Metis"), status_code=status)

    def error(request: Request, exc: Exception) -> HTMLResponse:
        code = exc.args[0] if isinstance(exc, ComparisonError) else "comparison_unavailable"
        status = 404 if code == "comparison_not_found" else 409 if code in {
            "comparison_stale_version", "comparison_arm_running", "comparison_stale_attempt",
            "comparison_transition_forbidden", "comparison_assessment_locked",
        } else 400 if isinstance(exc, ComparisonError) else 503
        if not isinstance(exc, ComparisonError):
            LOG.exception("Route comparison unavailable")
        return render(request, '<h1>Routevergelijking</h1><p>De handeling is niet uitgevoerd: '
                      + escape(str(code)) + '</p>', status=status)

    def redirect(comparison_id: str) -> RedirectResponse:
        return RedirectResponse("/inzicht/routevergelijking/" + comparison_id, status_code=303)

    @app.get("/inzicht/routevergelijking", response_class=HTMLResponse)
    def home(request: Request):
        account = require(request)
        allowed = scope(account)
        rows = store.list(owner=account["account_id"], allowed_scope=set(allowed))
        listing = ''.join(f'<li><a href="/inzicht/routevergelijking/{escape(r["comparison_id"])}">'
                          f'{escape(r["title"])} · {escape(r["state"])}</a></li>' for r in rows)
        return render(request, '<h1>Routevergelijking</h1><p>Experimentele meting op dezelfde bron; '
                      'gewone verwerking en Review blijven gescheiden.</p>'
                      '<p>De deterministische route bestaat niet meer; nieuwe vergelijkingen worden '
                      'niet gestart. Vastgelegde vergelijkingen blijven hieronder leesbaar.</p>'
                      '<ul>' + listing + '</ul>')

    @app.post("/settings/quality/compare", include_in_schema=False)
    @app.post("/inzicht/routevergelijking")
    async def create(request: Request):
        try:
            require(request)
            raise ComparisonError(RETIRED)
        except Exception as exc:
            return error(request, exc)

    @app.get("/inzicht/routevergelijking/{comparison_id}", response_class=HTMLResponse)
    def detail(request: Request, comparison_id: str):
        try:
            account, allowed, row = current(request, comparison_id)
            aid, version = account["account_id"], row["version"]
            owner_view = aid == row["owner_account_id"]
            action = f'/inzicht/routevergelijking/{comparison_id}'
            body = f'<h1>{escape(row["title"])}</h1><p>Status: {escape(row["state"])} · versie {version}</p>'
            if row["state"] == "draft":
                body += '<p>Deze vergelijking is nooit vastgezet en kan niet meer starten.</p>'
            elif row["state"] in {"frozen", "running", "blocked"}:
                body += '<p>Beide routes krijgen exact de vastgezette bronfragmenten.</p>'
                if owner_view:
                    for route, arm in row["arms"].items():
                        body += f'<p>{escape(route)}: {escape(arm["status"])}'
                        if route == "deterministic" and arm["status"] != "succeeded":
                            body += ' (route bestaat niet meer; annuleer deze vergelijking)'
                        elif arm["status"] in {"pending", "failed", "running"}:
                            button = "Opnieuw proberen na onderbreking" if arm["status"] == "running" else "Uitvoeren"
                            body += f' <form method="post" action="{action}/run/{route}"><input type="hidden" name="version" value="{version}"><button>{button}</button></form>'
                        body += '</p>'
            elif row["state"] in {"output_ready", "assessing", "assessed"}:
                view = blind_view(row)
                body += '<p>De routenamen blijven verborgen totdat beide beoordelingen vaststaan.</p>'
                body += '<h2>Brontekst</h2>' + ''.join('<p>' + escape(t) + '</p>' for t in view["source_text"])
                for label, units in view["arms"].items():
                    body += f'<h2>Voorstel {label}</h2>'
                    if label in row["assessments"]:
                        body += '<p>Beoordeling vastgezet.</p>'
                        continue
                    body += f'<form method="post" action="{action}/assess/{label}"><input type="hidden" name="version" value="{version}">'
                    for i, unit in enumerate(units):
                        body += '<p>' + escape(unit["text"]) + '</p><label>Oordeel <select name="choice_' + str(i) + '">'
                        body += ''.join(f'<option value="{v}">{v}</option>' for v in ("direct", "repair", "unusable", "unassessable"))
                        body += '</select></label>'
                    body += '<p>Dekking van de bron <select name="coverage">'
                    body += ''.join(f'<option value="{v}">{v}</option>' for v in ("complete", "partial", "missing", "unassessable"))
                    body += '</select></p><p>Problemen (optioneel): '
                    for value in ("missing_qualifier", "unsupported_addition", "wrong_relation", "fragmentation", "other"):
                        body += f'<label><input type="checkbox" name="problem" value="{value}">{value}</label> '
                    body += '</p><label>Aantal handelingen <input name="actions" type="number" min="0" value="0"></label>'
                    body += '<button>Beoordeling vastzetten</button></form>'
                if row["state"] == "assessed" and owner_view:
                    body += f'<form method="post" action="{action}/analyze"><input type="hidden" name="version" value="{version}"><button>Analyse berekenen</button></form>'
            if row["state"] in {"analyzed", "closed"}:
                report = row["analyses"][-1]
                body += '<h2>Resultaten per route</h2><table><tr><th>Route</th><th>Direct</th><th>Herstel</th><th>Onbruikbaar</th><th>Dekking</th><th>Handelingen</th></tr>'
                for route, result in report["results"].items():
                    body += f'<tr><td>{route}</td><td>{result["direct"]}/{result["candidate_count"]}</td><td>{result["repair"]}</td><td>{result["unusable"]}</td><td>{result["coverage"]}</td><td>{result["actions"]}</td></tr>'
                body += '</table><p>' + escape(report["limits"]) + '</p>'
                if row["state"] == "analyzed" and owner_view:
                    body += f'<form method="post" action="{action}/close"><input type="hidden" name="version" value="{version}"><select name="decision">'
                    body += ''.join(f'<option value="{v}">{v}</option>' for v in ("inconclusive", "more_cases", "implementation_proposal"))
                    body += '</select><button>Afsluiten</button></form>'
            if row["state"] not in {"closed", "cancelled"} and owner_view:
                body += f'<form method="post" action="{action}/cancel"><input type="hidden" name="version" value="{version}">'
                body += '<input name="reason" required placeholder="Reden annulering"><button>Annuleren</button></form>'
            return render(request, body)
        except Exception as exc:
            return error(request, exc)

    async def mutate(request: Request, comparison_id: str, operation):
        account, allowed, row = current(request, comparison_id)
        form = await request.form()
        try:
            version = int(str(form.get("version")))
        except (TypeError, ValueError):
            raise ComparisonError("comparison_version_required")
        return account, allowed, row, form, store.change(
            comparison_id, owner=row["owner_account_id"], allowed_scope=set(allowed),
            expected_version=version, operation=lambda target: operation(target, account, form))

    @app.post("/settings/quality/compare/{comparison_id}/run/{route}", include_in_schema=False)
    @app.post("/inzicht/routevergelijking/{comparison_id}/run/{route}")
    async def run(request: Request, comparison_id: str, route: str):
        try:
            account, allowed, row, form, claimed = await mutate(
                request, comparison_id, lambda target, actor, form:
                    claim_arm(target, actor=actor["account_id"], route=route))
            frozen, attempt = claimed
            if not attempt:
                return redirect(comparison_id)
            try:
                marker = Path(__file__).resolve().parents[1] / "config" / "deployed_commit.txt"
                running_code = marker.read_text().strip() if marker.exists() else "local-unversioned"
                if running_code != frozen["code_version"]:
                    raise ComparisonError("comparison_code_version_changed")
                output, execution = await run_in_threadpool(execute_arm, frozen, route)
                latest = store.get(comparison_id, allowed_scope=set(scope(account)))
                if latest is None:
                    raise ComparisonError("comparison_not_found")
                store.change(comparison_id, owner=account["account_id"], allowed_scope=set(allowed),
                             expected_version=latest["version"],
                             operation=lambda target: finish_arm(target, actor=account["account_id"],
                                                                 route=route, attempt_id=attempt,
                                                                 output=output, execution=execution))
            except Exception as exc:
                code = str(exc) if isinstance(exc, ComparisonError) else type(exc).__name__
                latest = store.get(comparison_id, allowed_scope=set(scope(account)))
                if latest is None:
                    raise ComparisonError("comparison_not_found") from exc
                store.change(comparison_id, owner=account["account_id"], allowed_scope=set(allowed),
                             expected_version=latest["version"],
                             operation=lambda target: fail_arm(target, actor=account["account_id"],
                                                               route=route, attempt_id=attempt, error_code=code))
            return redirect(comparison_id)
        except Exception as exc:
            return error(request, exc)

    @app.post("/settings/quality/compare/{comparison_id}/assess/{label}", include_in_schema=False)
    @app.post("/inzicht/routevergelijking/{comparison_id}/assess/{label}")
    async def assess_route(request: Request, comparison_id: str, label: str):
        try:
            def operation(target, actor, form):
                if label not in {"A", "B"}:
                    raise ComparisonError("comparison_label_invalid")
                count = len(blind_view(target)["arms"][label])
                try:
                    actions = int(str(form.get("actions") or "-1"))
                except ValueError as exc:
                    raise ComparisonError("comparison_assessment_invalid") from exc
                assess(target, actor=actor["account_id"], label=label,
                       choices=[str(form.get("choice_" + str(i)) or "") for i in range(count)],
                       coverage=str(form.get("coverage") or ""), problems=list(form.getlist("problem")),
                       actions=actions)
            await mutate(request, comparison_id, operation)
            return redirect(comparison_id)
        except Exception as exc:
            return error(request, exc)

    @app.post("/settings/quality/compare/{comparison_id}/analyze", include_in_schema=False)
    @app.post("/inzicht/routevergelijking/{comparison_id}/analyze")
    async def analyze_route(request: Request, comparison_id: str):
        try:
            await mutate(request, comparison_id, lambda target, actor, form:
                         analyze(target, actor=actor["account_id"]))
            return redirect(comparison_id)
        except Exception as exc:
            return error(request, exc)

    @app.post("/settings/quality/compare/{comparison_id}/close", include_in_schema=False)
    @app.post("/inzicht/routevergelijking/{comparison_id}/close")
    async def close_route(request: Request, comparison_id: str):
        try:
            await mutate(request, comparison_id, lambda target, actor, form:
                         close(target, actor=actor["account_id"], decision=str(form.get("decision") or "")))
            return redirect(comparison_id)
        except Exception as exc:
            return error(request, exc)

    @app.post("/settings/quality/compare/{comparison_id}/cancel", include_in_schema=False)
    @app.post("/inzicht/routevergelijking/{comparison_id}/cancel")
    async def cancel_route(request: Request, comparison_id: str):
        try:
            await mutate(request, comparison_id, lambda target, actor, form:
                         cancel(target, actor=actor["account_id"], reason=str(form.get("reason") or "")))
            return redirect(comparison_id)
        except Exception as exc:
            return error(request, exc)
