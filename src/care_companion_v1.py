"""Raad: a read-only page companion for signed-in console pages.

It explains the current page and visible errors, lists existing diagnostics
(``/inzicht/api/documents``) and starts the existing view check. It owns no
durable state: every action goes through the existing routes and their
authorization; a report is composed in the browser and never stored here.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
from pathlib import Path
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from src.operations_console_v1 import ConsoleError

SCRIPT = Path(__file__).resolve().parents[1] / "assets" / "brand" / "care-companion.js"
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
STATES = ("queued", "running", "completed", "failed", "cancelled")

OWL = (
    '<svg class="care-owl" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
    '<path class="care-owl-body" d="M14 22 L18 8 L26 16 Q32 14 38 16 L46 8 L50 22 '
    'Q56 34 52 46 Q46 58 32 58 Q18 58 12 46 Q8 34 14 22 Z"/>'
    '<ellipse class="care-owl-belly" cx="32" cy="44" rx="11" ry="10"/>'
    '<circle class="care-owl-eye" cx="24" cy="30" r="7"/><circle class="care-owl-eye" cx="40" cy="30" r="7"/>'
    '<circle class="care-owl-pupil" cx="24" cy="30" r="3"/><circle class="care-owl-pupil" cx="40" cy="30" r="3"/>'
    '<path class="care-owl-beak" d="M29 36 L35 36 L32 41 Z"/>'
    '<path class="care-owl-cross" d="M45 44 h6 M48 41 v6"/>'
    '</svg>'
)


def _script_url() -> str:
    # Static files keep fixed mtimes in the deploy package; version by content.
    try:
        return "/brand/care-companion.js?v=" + sha256(SCRIPT.read_bytes()).hexdigest()[:16]
    except OSError:
        return "/brand/care-companion.js"


def markup(current: str = "") -> str:
    """Companion shell for authenticated navigation; content is built client side."""
    from src.request_diagnostics_v1 import deployed_commit, current_request_id
    room = escape(current or "page", quote=True)
    commit = escape(deployed_commit() or "", quote=True)
    return f'''<div class="care-companion" data-care-companion data-room="{room}" data-commit="{commit}" data-request-id="{escape(current_request_id() or "", quote=True)}">
  <div class="care-panel" id="care-panel" role="dialog" aria-modal="false" aria-labelledby="care-title" hidden>
    <div class="care-panel-head">
      <strong id="care-title">Raad</strong>
      <button class="care-close quiet" type="button" data-care-close aria-label="Sluit Raad">×</button>
    </div>
    <div class="care-panel-body" data-care-body></div>
  </div>
  <button class="care-toggle" type="button" data-care-toggle aria-expanded="false" aria-controls="care-panel"
          aria-label="Open Raad: hulp, meldingen en weergavecontrole">{OWL}<span class="care-dot" data-care-dot hidden></span></button>
</div>
<script src="/brand/page-readiness.js?v={sha256((SCRIPT.parent / "page-readiness.js").read_bytes()).hexdigest()[:16]}" defer></script>
<script src="{_script_url()}" defer></script>'''


def _check_summary(row: dict) -> dict:
    result = row.get("result") or {}
    verdicts = [check.get("verdict") for check in result.get("checks") or []]
    return {
        "id": row["id"], "state": row["state"] if row["state"] in STATES else "failed",
        "created_at": str(row.get("created_at") or ""),
        "reason": str(result.get("reason") or ""),
        "passed": verdicts.count("pass"), "differences": verdicts.count("fail"),
        "not_established": verdicts.count("not_established"),
        "evidence": bool(result.get("evidence")),
    }


def install(app, state, require) -> None:
    @app.get("/raad/meldingen")
    def companion_notices(request: Request, offset: int = 0) -> JSONResponse:
        from src.insight_v1 import MAX_SCAN, documents_projection
        page = documents_projection(state, require(request), state_filter="attention", limit=8, scan_limit=MAX_SCAN, offset=offset, partial_on_error=True)
        return JSONResponse({"documents": page["documents"],
                             "complete": page["next_offset"] is None and not page["telemetry_partial"] and not page["metadata_partial"] and not page["diagnostic_partial"],
                             "next_offset": page["next_offset"]}, headers=HEADERS)

    @app.get("/raad/weergavecontrole")
    def companion_view_check(request: Request, document: str = "", attempt: str = "") -> JSONResponse:
        from src.view_check import ViewCheckAccessDenied, authorize, context
        account = require(request)
        if not document or len(document) > 200 or len(attempt) > 200:
            return JSONResponse({"available": False, "reason": "no_document"}, headers=HEADERS)
        service = getattr(app.state, "view_checks", None)
        if service is None:
            return JSONResponse({"available": False, "reason": "not_configured"}, headers=HEADERS)
        try:
            authorize(state, account["account_id"], document)
        except ViewCheckAccessDenied:
            return JSONResponse({"available": False, "reason": "not_named_reviewer"}, headers=HEADERS)
        except ConsoleError:
            return JSONResponse({"available": False, "reason": "not_available"}, headers=HEADERS)
        body: dict = {"available": True, "document": document, "attempt": attempt, "form": None}
        try:
            pinned = context(state, account["account_id"], document, attempt)
        except (ValueError, ConsoleError):
            body["reason"] = "not_supported"
        else:
            body["form"] = {"document": document, "attempt": attempt,
                            "expected_revision": pinned["revision"], "request_key": uuid4().hex}
        body["checks"] = [_check_summary(row) for row in service.store.history(document)[:5]]
        return JSONResponse(body, headers=HEADERS)
