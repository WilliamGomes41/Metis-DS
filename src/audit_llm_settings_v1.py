"""Console settings for the Audit-only LLM credential."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.audit_llm_secret_v1 import AuditLLMSecretStore
from src.operations_console_v1 import ConsoleError, OperationsConsole


def install_audit_llm_settings_routes(app: FastAPI, console: OperationsConsole) -> None:
    store = AuditLLMSecretStore(console.runtime)

    def account_for(request: Request) -> dict[str, Any]:
        return console.session_account(request.cookies.get("console_session"))

    def researcher_account(request: Request) -> dict[str, Any] | None:
        account = account_for(request)
        return account if "researcher" in set(account.get("roles") or []) else None

    def forbidden(account: dict[str, Any]) -> HTMLResponse:
        from src.audit_room_v1 import _chrome

        return HTMLResponse(
            _chrome(
                console,
                account,
                '<h1>Geen toegang</h1><p>LLM-instellingen vereisen de rol researcher.</p><p><a href="/audit">Terug naar Audit</a></p>',
            ),
            status_code=403,
        )

    def render(account: dict[str, Any], *, notice: str = "", error: str = "") -> HTMLResponse:
        from src.audit_room_v1 import _chrome, _esc

        status = store.status()
        if not status["available"]:
            state = "Niet beschikbaar"
            explanation = "De deployment-secret METIS_AUDIT_SECRET_KEY ontbreekt of is ongeldig."
            form = ""
        else:
            state = "Geconfigureerd" if status["configured"] else "Niet geconfigureerd"
            explanation = "De opgeslagen API-key is write-only en wordt nooit teruggetoond."
            form = """
              <form method="post" action="/audit/llm-settings">
                <label for="audit-llm-api-key">LLM API-key</label>
                <input id="audit-llm-api-key" name="api_key" type="password" autocomplete="new-password" required>
                <button class="btn-primary" type="submit">API-key opslaan</button>
              </form>
            """
            if status["configured"]:
                form += """
                  <form method="post" action="/audit/llm-settings/delete" style="margin-top:1rem;">
                    <button class="btn-secondary" type="submit">API-key verwijderen</button>
                  </form>
                """
        notice_html = f'<div class="banner ok">{_esc(notice)}</div>' if notice else ""
        error_html = f'<div class="banner err">{_esc(error)}</div>' if error else ""
        body = f"""
          <p><a class="btn-secondary" href="/audit">← Terug naar Audit</a></p>
          <p class="eyebrow">Audit · LLM</p>
          <h1>LLM-instellingen</h1>
          <p class="lead">Beheer uitsluitend de credential voor experimentele modelcalls binnen Audit.</p>
          {notice_html}{error_html}
          <article class="doc-card">
            <p class="doc-title">API-key</p>
            <p><b>{state}</b></p>
            <p class="muted">{explanation}</p>
          </article>
          {form}
          <p class="muted">De key wordt niet opgenomen in auditrecords, frozen datasets, Kernel-state of Git.</p>
        """
        return HTMLResponse(_chrome(console, account, body))

    def settings(request: Request, saved: str = "", removed: str = "") -> HTMLResponse:
        account = researcher_account(request)
        if account is None:
            return forbidden(account_for(request))
        notice = "API-key opgeslagen." if saved else ("API-key verwijderd." if removed else "")
        return render(account, notice=notice)

    def save(request: Request, api_key: str = Form(...)) -> HTMLResponse:
        account = researcher_account(request)
        if account is None:
            return forbidden(account_for(request))
        try:
            store.set_api_key(api_key)
        except ConsoleError as exc:
            if exc.code == "audit_llm_api_key_required":
                return render(account, error="Vul een API-key in.")
            if exc.code == "audit_llm_api_key_too_long":
                return render(account, error="De API-key is te lang.")
            if exc.code == "audit_secret_store_unavailable":
                return render(account, error="De beveiligde Audit-secretopslag is niet beschikbaar.")
            raise
        return RedirectResponse("/audit/llm-settings?saved=1", status_code=303)

    def remove(request: Request) -> HTMLResponse:
        account = researcher_account(request)
        if account is None:
            return forbidden(account_for(request))
        store.clear_api_key()
        return RedirectResponse("/audit/llm-settings?removed=1", status_code=303)

    app.add_api_route("/audit/llm-settings", settings, methods=["GET"], response_class=HTMLResponse, name="audit_llm_settings")
    app.add_api_route("/audit/llm-settings", save, methods=["POST"], response_class=HTMLResponse, name="audit_llm_settings_save")
    app.add_api_route("/audit/llm-settings/delete", remove, methods=["POST"], response_class=HTMLResponse, name="audit_llm_settings_delete")
