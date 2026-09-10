"""Audit room v1: create and inspect bounded audit records.

Audit is a broad inspection room, not a generic workflow engine. Audit types are
configured as a closed list; only the passage-formation experiment is enabled in
this first slice. Each audit is stored as its own JSON record under the console
runtime so creating one audit does not rewrite a shared registry file.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.operations_console_v1 import ConsoleError, OperationsConsole, _atomic_write


AUDIT_TYPES: dict[str, dict[str, Any]] = {
    "experiment": {
        "label": "Experiment",
        "description": "Vergelijk twee manieren waarop Metis werkt voordat productie wordt gewijzigd.",
        "enabled": True,
    },
    "document_quality": {
        "label": "Documentkwaliteit",
        "description": "Controleer brontrouw, dekking en geblokkeerde passages.",
        "enabled": False,
    },
    "publication": {
        "label": "Publicatiecontrole",
        "description": "Controleer review- en publicatievoorwaarden zonder te publiceren.",
        "enabled": False,
    },
    "technical_release": {
        "label": "Techniek & release",
        "description": "Controleer opslag, toegang, integriteit en releasebewijs.",
        "enabled": False,
    },
}

AUDIT_ID_RE = re.compile(r"^audit-[0-9a-f]{16}$")
EXPERIMENT_BASELINE = {
    "id": "production_passage_formation",
    "label": "Huidige productiepassagevorming",
}
EXPERIMENT_CANDIDATE = {
    "id": "source_bound_semantic_passage_formation",
    "label": "Brongebonden semantische passagevorming",
}
DEFAULT_EXPERIMENT_QUESTION = (
    "Kan brongebonden semantische passagevorming betere kennisobjectvoorstellen maken "
    "dan de huidige passagevorming zonder brontrouw of publicatieveiligheid te verliezen?"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class AuditRegistry:
    """Small file-per-audit registry for the current single-instance MVP."""

    def __init__(self, runtime: Path) -> None:
        self.root = Path(runtime) / "audits"
        self.root.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()

    def list_audits(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.root.glob("audit-*.json"):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ConsoleError("audit_record_corrupt") from exc
            if not isinstance(row, dict) or not AUDIT_ID_RE.fullmatch(str(row.get("audit_id") or "")):
                raise ConsoleError("audit_record_corrupt")
            rows.append(row)
        return sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)

    def get_audit(self, audit_id: str) -> dict[str, Any] | None:
        if not AUDIT_ID_RE.fullmatch(str(audit_id or "")):
            return None
        return next((row for row in self.list_audits() if row.get("audit_id") == audit_id), None)

    def create_experiment(self, *, title: str, question: str, actor_id: str) -> dict[str, Any]:
        safe_title = " ".join(str(title or "").split())
        safe_question = " ".join(str(question or "").split())
        if not safe_title:
            raise ConsoleError("audit_title_required")
        if not safe_question:
            raise ConsoleError("audit_question_required")
        with self._write_lock:
            for _attempt in range(3):
                audit_id = f"audit-{uuid.uuid4().hex[:16]}"
                path = self.root / f"{audit_id}.json"
                if path.exists():
                    continue
                now = _now()
                record = {
                    "audit_id": audit_id,
                    "audit_type": "experiment",
                    "title": safe_title,
                    "created_by": actor_id,
                    "created_at": now,
                    "updated_at": now,
                    "experiment": {
                        "question": safe_question,
                        "baseline": dict(EXPERIMENT_BASELINE),
                        "candidate": dict(EXPERIMENT_CANDIDATE),
                        "state": "setup",
                    },
                }
                _atomic_write(path, record)
                return record
        raise RuntimeError("audit_id_collision")


def _esc(value: Any) -> str:
    from src.operations_console_app import _esc as console_esc

    return console_esc(value)


def _chrome(console: OperationsConsole, account: dict[str, Any], body: str) -> str:
    from src.operations_console_app import _help, _nav, _page

    counts = console.waiting_task_counts(account["account_id"])
    return _page(
        f"""
        {_nav(account, "audit", counts)}
        <section class="room">
          {body}
        </section>
        {_help()}
        """,
        title="Audit — V&amp;VN Data Services",
    )


def _audit_type_cards() -> str:
    cards: list[str] = []
    for audit_type, config in AUDIT_TYPES.items():
        enabled = bool(config["enabled"])
        action = (
            f'<a class="btn-primary" href="/audit/new?type={_esc(audit_type)}">Kies dit type</a>'
            if enabled
            else '<span class="muted">Later beschikbaar</span>'
        )
        cards.append(
            f"""
            <article class="doc-card">
              <p class="doc-title">{_esc(config["label"])}</p>
              <p>{_esc(config["description"])}</p>
              {action}
            </article>
            """
        )
    return "".join(cards)


def _audit_rows(registry: AuditRegistry) -> str:
    rows = []
    for audit in registry.list_audits():
        audit_type = AUDIT_TYPES.get(str(audit.get("audit_type") or ""), {})
        experiment = audit.get("experiment") if isinstance(audit.get("experiment"), dict) else {}
        state = experiment.get("state") or ""
        status = "Opzetten" if state == "setup" else str(state).replace("_", " ")
        rows.append(
            f"""
            <article class="doc-card">
              <p class="doc-title"><a href="/audit/{_esc(audit["audit_id"])}">{_esc(audit["title"])}</a></p>
              <p class="meta">
                <span>type <b>{_esc(audit_type.get("label") or audit.get("audit_type"))}</b></span>
                <span>status <b>{_esc(status)}</b></span>
                <span>aangemaakt <b>{_esc(audit.get("created_at"))}</b></span>
              </p>
            </article>
            """
        )
    return "".join(rows) or '<p class="muted">Nog geen audits aangemaakt.</p>'


def _experiment_form(*, error: str = "", title: str = "", question: str = DEFAULT_EXPERIMENT_QUESTION) -> str:
    banner = f'<div class="banner err">{_esc(error)}</div>' if error else ""
    return f"""
      <p><a class="btn-secondary" href="/audit/new">← Terug naar audittypen</a></p>
      <h1>Nieuwe audit — Experiment</h1>
      <p class="lead">Maak de audit aan. De dataset wordt in de volgende stap vastgezet.</p>
      {banner}
      <form method="post" action="/audit">
        <input type="hidden" name="audit_type" value="experiment">
        <div class="sections">
          <div class="section">
            <h3>Onderzoek</h3>
            <label for="audit-title">Naam</label>
            <input id="audit-title" name="title" value="{_esc(title)}" required>
            <label for="audit-question">Onderzoeksvraag</label>
            <textarea id="audit-question" name="question" required>{_esc(question)}</textarea>
          </div>
          <div class="section">
            <h3>Vergelijking</h3>
            <p><b>Baseline</b><br>{_esc(EXPERIMENT_BASELINE["label"])}</p>
            <p><b>Kandidaat</b><br>{_esc(EXPERIMENT_CANDIDATE["label"])}</p>
            <p class="muted">Beide routes gebruiken in het experiment dezelfde deterministische harde gates.</p>
          </div>
        </div>
        <button class="btn-primary" type="submit">Audit aanmaken</button>
      </form>
    """


def install_audit_routes(app: FastAPI, console: OperationsConsole) -> None:
    """Install the first bounded Audit room on the existing console app."""

    registry = AuditRegistry(console.runtime)

    def account_for(request: Request) -> dict[str, Any]:
        return console.session_account(request.cookies.get("console_session"))

    def audit_home(request: Request) -> HTMLResponse:
        account = account_for(request)
        body = f"""
          <h1>Audit</h1>
          <p class="lead">Controleer hoe Metis werkt en leg bewijs vast. Audits veranderen geen canonieke kennis en publiceren niets.</p>
          <p><a class="btn-primary" href="/audit/new">Nieuwe audit</a></p>
          <h2>Lopende audits</h2>
          <div class="doc-list">{_audit_rows(registry)}</div>
          <h2>Auditvormen</h2>
          <div class="doc-list">{_audit_type_cards()}</div>
        """
        return HTMLResponse(_chrome(console, account, body))

    def audit_new(request: Request, type: str = "") -> HTMLResponse:
        account = account_for(request)
        selected = str(type or "").strip()
        if not selected:
            body = f"""
              <p><a class="btn-secondary" href="/audit">← Terug naar Audit</a></p>
              <h1>Nieuwe audit</h1>
              <p class="lead">Kies wat je wilt onderzoeken. Alleen Experiment is in deze eerste slice actief.</p>
              <div class="doc-list">{_audit_type_cards()}</div>
            """
            return HTMLResponse(_chrome(console, account, body))
        config = AUDIT_TYPES.get(selected)
        if not config or not config.get("enabled"):
            return HTMLResponse(
                _chrome(console, account, '<h1>Auditvorm niet beschikbaar</h1><p><a href="/audit/new">Kies een beschikbaar type</a></p>'),
                status_code=404,
            )
        if selected != "experiment":
            return HTMLResponse(_chrome(console, account, "<h1>Auditvorm niet geïmplementeerd</h1>"), status_code=501)
        return HTMLResponse(_chrome(console, account, _experiment_form()))

    def audit_create(
        request: Request,
        audit_type: str = Form(...),
        title: str = Form(...),
        question: str = Form(...),
    ) -> HTMLResponse:
        account = account_for(request)
        if "researcher" not in set(account.get("roles") or []):
            raise ConsoleError("researcher_role_required")
        config = AUDIT_TYPES.get(audit_type)
        if not config or not config.get("enabled") or audit_type != "experiment":
            return HTMLResponse(
                _chrome(console, account, _experiment_form(error="Dit audittype kan nog niet worden aangemaakt.", title=title, question=question)),
                status_code=400,
            )
        try:
            audit = registry.create_experiment(
                title=title,
                question=question,
                actor_id=account["account_id"],
            )
        except ConsoleError as exc:
            if exc.code == "audit_title_required":
                message = "Vul een naam voor de audit in."
            elif exc.code == "audit_question_required":
                message = "Vul een onderzoeksvraag in."
            else:
                raise
            return HTMLResponse(
                _chrome(console, account, _experiment_form(error=message, title=title, question=question)),
                status_code=400,
            )
        return RedirectResponse(f'/audit/{audit["audit_id"]}', status_code=303)

    def audit_detail(request: Request, audit_id: str) -> HTMLResponse:
        account = account_for(request)
        audit = registry.get_audit(audit_id)
        if audit is None:
            return HTMLResponse(_chrome(console, account, '<h1>Audit niet gevonden</h1><p><a href="/audit">Terug naar Audit</a></p>'), status_code=404)
        experiment = audit.get("experiment") if isinstance(audit.get("experiment"), dict) else {}
        baseline = experiment.get("baseline") if isinstance(experiment.get("baseline"), dict) else {}
        candidate = experiment.get("candidate") if isinstance(experiment.get("candidate"), dict) else {}
        body = f"""
          <p><a class="btn-secondary" href="/audit">← Terug naar Audit</a></p>
          <p class="eyebrow">Experiment · {_esc(audit["audit_id"])}</p>
          <h1>{_esc(audit["title"])}</h1>
          <p class="lead">{_esc(experiment.get("question"))}</p>
          <div class="sections">
            <div class="section">
              <h3>Status</h3>
              <p><b>Opzetten</b></p>
              <p class="muted">De audit is aangemaakt. Er is nog geen dataset vastgezet of modelroute uitgevoerd.</p>
            </div>
            <div class="section">
              <h3>Vergelijking</h3>
              <p><b>Baseline</b><br>{_esc(baseline.get("label"))}</p>
              <p><b>Kandidaat</b><br>{_esc(candidate.get("label"))}</p>
            </div>
          </div>
          <h2>Volgende stap</h2>
          <article class="doc-card">
            <p class="doc-title">Dataset vastzetten</p>
            <p>Kies in de volgende implementatieslice representatieve passages en leg bron, locator, hash en baseline-commit vast.</p>
            <span class="muted">Nog niet beschikbaar</span>
          </article>
        """
        return HTMLResponse(_chrome(console, account, body))

    app.add_api_route("/audit", audit_home, methods=["GET"], response_class=HTMLResponse, name="audit_home")
    app.add_api_route("/audit/new", audit_new, methods=["GET"], response_class=HTMLResponse, name="audit_new")
    app.add_api_route("/audit", audit_create, methods=["POST"], response_class=HTMLResponse, name="audit_create")
    app.add_api_route("/audit/{audit_id}", audit_detail, methods=["GET"], response_class=HTMLResponse, name="audit_detail")
