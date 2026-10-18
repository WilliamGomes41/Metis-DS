"""Semantic safety tests as a standalone check under Inzicht › Controles.

Runs the frozen suite (``audit_semantic_safety_v1``) on demand and shows the
result directly. Nothing is persisted: no audit record, no review, publication
or semantic-mode state. A run leaves one content-free telemetry event with
counts only. Old Audit addresses redirect here or to Controles.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.audit_semantic_safety_v1 import load_frozen_safety_suite, run_frozen_semantic_safety_suite
from src.llm_provider_v1 import load_llm_provider_config
from src.operations_console_v1 import ConsoleError, OperationsConsole

SAFETY_PATH = "/inzicht/veiligheidstests"
CONTROLS_PATH = "/inzicht?tab=controles"
DEPLOY_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_DEPLOY_COMMIT_MARKER = Path(__file__).resolve().parents[1] / "config" / "deployed_commit.txt"
SUITE_PATH = Path(__file__).resolve().parents[1] / "data" / "audit" / "semantic_passage_safety_v1.json"
# Retired Audit room addresses; explicit so /audit/review-signals stays its own route.
RETIRED_AUDIT_PATHS = {"/audit": CONTROLS_PATH, "/audit/new": CONTROLS_PATH,
                       "/audit/archive": CONTROLS_PATH, "/audit/semantic-safety": SAFETY_PATH}


def _esc(value: Any) -> str:
    from src.operations_console_app import _esc as console_esc

    return console_esc(value)


def _chrome(account: dict[str, Any], body: str) -> str:
    from src.operations_console_app import _nav, _page

    return _page(f'{_nav(account, "settings")}<section class="room">{body}</section>',
                 title="Semantische veiligheidstests — Metis")


def _result_html(report: dict[str, Any]) -> str:
    rows = []
    for result in report.get("results") or []:
        candidate = result.get("candidate") if isinstance(result, dict) and isinstance(result.get("candidate"), dict) else {}
        evaluation = candidate.get("evaluation") if isinstance(candidate.get("evaluation"), dict) else {}
        details = []
        if candidate.get("kernel_reject"):
            details.append(f'kernel reject: {candidate.get("kernel_reject")}')
        if evaluation.get("missing_anchors"):
            details.append("ontbrekende bronankers: " + "; ".join(str(x) for x in evaluation["missing_anchors"]))
        if evaluation.get("broken_co_location_groups"):
            details.append("betekenisverband niet behouden")
        details_html = f'<br><span class="muted">{_esc(" · ".join(details))}</span>' if details else ""
        rows.append(f'<li><b>{_esc(result.get("risk_category"))}</b> · {_esc(result.get("case_id"))} '
                    f'— <b>{"PASS" if candidate.get("pass") else "REVIEW"}</b>{details_html}</li>')
    verdict = ("Alle automatische testcriteria zijn gehaald; menselijke beoordeling blijft vereist."
               if report.get("machine_safety_pass") else
               "Niet alle testcriteria zijn gehaald. Onderzoek de gevallen met REVIEW. Een geblokkeerd voorstel kan een "
               "ingreep van de beveiliging zijn; het is geen geslaagd verwerkingsresultaat.")
    return f"""
      <h2>Uitkomst</h2>
      <p class="lead">{_esc(report.get("candidate_pass_count"))} van {_esc(report.get("case_count"))} veiligheidstests geslaagd. Dit beoordeelt vaste testgevallen, niet je ingeleverde documenten. Dit is geen activatiebesluit.</p>
      <p>{verdict}</p>
      <details><summary>Technische testdetails</summary>
        <p>suite <b>{_esc(report.get("suite_id"))}</b> · hash {_esc(report.get("suite_hash"))}</p>
        <p>model <b>{_esc(report.get("model"))}</b> · baseline <b>{_esc(report.get("suite_baseline_commit"))}</b> · deployment <b>{_esc(report.get("deployed_commit"))}</b></p>
        <p><b>{"Machinecheck PASS" if report.get("machine_safety_pass") else "Menselijke beoordeling vereist"}</b></p>
      </details>
      <h2>Veiligheidscases</h2>
      <ul>{"".join(rows)}</ul>
      <p class="muted">De uitkomst wordt niet bewaard. Voer de tests opnieuw uit om een actuele uitkomst te zien.</p>
    """


def install_semantic_safety_routes(
    app: FastAPI,
    console: OperationsConsole,
    *,
    post_json: Any | None = None,
    deployed_commit_path: Path | None = None,
) -> None:
    commit_path = Path(deployed_commit_path or DEFAULT_DEPLOY_COMMIT_MARKER)

    def deployed_commit() -> str:
        try:
            commit = commit_path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            return ""
        return commit if DEPLOY_COMMIT_RE.fullmatch(commit) else ""

    def researcher(request: Request) -> dict[str, Any]:
        account = console.session_account(request.cookies.get("console_session"))
        if "researcher" not in set(account.get("roles") or []):
            raise ConsoleError("researcher_role_required")
        return account

    def page(account: dict[str, Any], *, error: str = "", result: str = "") -> HTMLResponse:
        suite = load_frozen_safety_suite(SUITE_PATH)
        provider = load_llm_provider_config()
        commit = deployed_commit()
        blockers = [text for missing, text in ((not provider.api_key, "METIS_LLM_API_KEY ontbreekt"),
                                               (not provider.model, "METIS_LLM_MODEL ontbreekt"),
                                               (not commit, "geldige packaged deployment-commit ontbreekt")) if missing]
        action = ('<button class="btn-primary" type="submit">Veiligheidstests uitvoeren</button>' if not blockers
                  else f'<p class="muted">Run geblokkeerd: {_esc("; ".join(blockers))}.</p>')
        error_html = f'<div class="banner err">{_esc(error)}</div>' if error else ""
        body = f"""
          <p><a href="{CONTROLS_PATH}">← Inzicht · Controles</a></p>
          <h1>Semantische veiligheidstests</h1>
          <p class="lead">Controleer weglatingen, voorwaarden, uitzonderingen, negaties en betekenisverbanden op exact dezelfde vaste bron.</p>
          {error_html}
          <article class="doc-card">
            <p><b>Suite</b> {_esc(suite["suite_id"])}</p>
            <p><b>Vaste baseline</b> {_esc(suite["evaluated_baseline_commit"])}</p>
            <p><b>Deployment</b> {_esc(commit or "Niet beschikbaar")}</p>
            <p><b>Model</b> {_esc(provider.model or "Niet geconfigureerd")}</p>
            <p><b>Cases</b> {len(suite["cases"])}</p>
          </article>
          <form method="post" action="{SAFETY_PATH}/run">{action}</form>
          <p class="muted">Een run wijzigt geen document-, review- of publicatiestatus en activeert semantic mode niet.</p>
          {result}
        """
        return HTMLResponse(_chrome(account, body), headers={"Cache-Control": "no-store"})

    @app.get(SAFETY_PATH, response_class=HTMLResponse)
    def semantic_safety(request: Request) -> HTMLResponse:
        return page(researcher(request))

    @app.post(SAFETY_PATH + "/run", response_class=HTMLResponse)
    def semantic_safety_run(request: Request) -> HTMLResponse:
        from src.telemetry import record_event

        account = researcher(request)
        provider = load_llm_provider_config()
        commit = deployed_commit()
        if not provider.api_key:
            return page(account, error="METIS_LLM_API_KEY is niet geconfigureerd.")
        if not provider.model:
            return page(account, error="METIS_LLM_MODEL is niet geconfigureerd.")
        if not commit:
            return page(account, error="Geen geldige packaged deployment-commit beschikbaar.")
        try:
            report = run_frozen_semantic_safety_suite(load_frozen_safety_suite(SUITE_PATH), api_key=provider.api_key,
                                                      model=provider.model, deployed_commit=commit, post_json=post_json)
        except ConsoleError as exc:
            record_event("semantic_safety_run", kind="controle", outcome="error", code=exc.code)
            return page(account, error=f"De tests konden niet worden uitgevoerd: {exc.code}")
        record_event("semantic_safety_run", kind="controle", outcome="ok",
                     case_count=report.get("case_count"), pass_count=report.get("candidate_pass_count"),
                     machine_safety_pass=bool(report.get("machine_safety_pass")))
        return page(account, result=_result_html(report))

    def redirect_to(target: str):
        def retired(request: Request) -> RedirectResponse:
            console.session_account(request.cookies.get("console_session"))
            return RedirectResponse(target, status_code=303)
        return retired

    for old, new in RETIRED_AUDIT_PATHS.items():
        app.add_api_route(old, redirect_to(new), methods=["GET"], include_in_schema=False,
                          name=f"retired_{old.strip('/').replace('/', '_')}")
