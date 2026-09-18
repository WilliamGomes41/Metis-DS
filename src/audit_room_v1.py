"""Audit room v1: create and inspect bounded audit records.

The room is generic; audit execution is not. ``AuditRegistry`` only stores a
small type-independent envelope plus an opaque type payload. Each audit type
constructs and renders its own payload. This keeps the MVP extensible without
introducing an AuditEngine or a universal lifecycle.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.admission_gate_v1 import blocked_audit_lane
from src.audit_semantic_safety_v1 import (
    AUDIT_LLM_MODEL_ENV,
    load_frozen_safety_suite,
    run_frozen_semantic_safety_suite,
)
from src.extract_coverage_v1 import coverage_panel_rows
from src.operations_console_v1 import ConsoleError, OperationsConsole, _atomic_write


AUDIT_TYPES: dict[str, dict[str, Any]] = {
    "experiment": {
        "label": "Experiment",
        "description": "Vergelijk twee manieren waarop Metis werkt voordat productie wordt gewijzigd.",
        "enabled": True,
    },
    "document_quality": {
        "label": "Documentkwaliteit",
        "description": "Leg een read-only momentopname vast van dekking en technische blokkades.",
        "enabled": True,
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
AUDIT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
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
    """File-per-audit storage with no knowledge of experiment or quality semantics."""

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
            if not self._valid_record(row):
                raise ConsoleError("audit_record_corrupt")
            rows.append(row)
        return sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)

    @staticmethod
    def _valid_record(row: Any) -> bool:
        return (
            isinstance(row, dict)
            and AUDIT_ID_RE.fullmatch(str(row.get("audit_id") or "")) is not None
            and AUDIT_TYPE_RE.fullmatch(str(row.get("audit_type") or "")) is not None
            and bool(str(row.get("title") or "").strip())
            and bool(str(row.get("created_by") or "").strip())
            and isinstance(row.get("payload"), dict)
        )

    def get_audit(self, audit_id: str) -> dict[str, Any] | None:
        if not AUDIT_ID_RE.fullmatch(str(audit_id or "")):
            return None
        path = self.root / f"{audit_id}.json"
        if not path.is_file():
            return None
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConsoleError("audit_record_corrupt") from exc
        if not self._valid_record(row):
            raise ConsoleError("audit_record_corrupt")
        return row

    def create(
        self,
        *,
        audit_type: str,
        title: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        safe_type = str(audit_type or "").strip()
        safe_title = " ".join(str(title or "").split())
        safe_actor = str(actor_id or "").strip()
        if not AUDIT_TYPE_RE.fullmatch(safe_type):
            raise ConsoleError("unknown_audit_type")
        if not safe_title:
            raise ConsoleError("audit_title_required")
        if not safe_actor:
            raise ConsoleError("audit_actor_required")
        if not isinstance(payload, dict):
            raise ConsoleError("audit_payload_required")
        with self._write_lock:
            for _attempt in range(3):
                audit_id = f"audit-{uuid.uuid4().hex[:16]}"
                path = self.root / f"{audit_id}.json"
                if path.exists():
                    continue
                now = _now()
                record = {
                    "audit_id": audit_id,
                    "audit_type": safe_type,
                    "title": safe_title,
                    "created_by": safe_actor,
                    "created_at": now,
                    "updated_at": now,
                    "payload": payload,
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
        rows.append(
            f"""
            <article class="doc-card">
              <p class="doc-title"><a href="/audit/{_esc(audit["audit_id"])}">{_esc(audit["title"])}</a></p>
              <p class="meta">
                <span>type <b>{_esc(audit_type.get("label") or audit.get("audit_type"))}</b></span>
                <span>aangemaakt <b>{_esc(audit.get("created_at"))}</b></span>
              </p>
            </article>
            """
        )
    return "".join(rows) or '<p class="muted">Nog geen audits aangemaakt.</p>'


def _experiment_payload(question: str) -> dict[str, Any]:
    safe_question = " ".join(str(question or "").split())
    if not safe_question:
        raise ConsoleError("audit_question_required")
    return {
        "question": safe_question,
        "baseline": dict(EXPERIMENT_BASELINE),
        "candidate": dict(EXPERIMENT_CANDIDATE),
        "state": "setup",
    }


def _document_quality_payload(console: OperationsConsole, snapshot_id: str) -> dict[str, Any]:
    safe_snapshot = str(snapshot_id or "").strip()
    objects, revision = console.snapshot_objects_and_revision(safe_snapshot)
    envelope = console._envelope(safe_snapshot)
    return {
        "snapshot_id": safe_snapshot,
        "snapshot_revision": revision,
        "document": {
            "title": envelope["title"],
            "version": envelope["version"],
            "family": envelope["family"],
            "class": envelope["class"],
        },
        "coverage": coverage_panel_rows(objects),
        "blocked_object_ids": [str(row.get("object_id") or "") for row in blocked_audit_lane(objects)],
    }


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


def _document_quality_form(console: OperationsConsole, *, error: str = "", title: str = "") -> str:
    banner = f'<div class="banner err">{_esc(error)}</div>' if error else ""
    options = ['<option value="">Kies een document</option>']
    for row in console.list_envelopes():
        label = f'{row["title"]} · {row["version"]} · {row["family"]}'
        options.append(f'<option value="{_esc(row["snapshot_id"])}">{_esc(label)}</option>')
    return f"""
      <p><a class="btn-secondary" href="/audit/new">← Terug naar audittypen</a></p>
      <h1>Nieuwe audit — Documentkwaliteit</h1>
      <p class="lead">Leg de huidige dekking en technische blokkades vast zonder het document te wijzigen.</p>
      {banner}
      <form method="post" action="/audit">
        <input type="hidden" name="audit_type" value="document_quality">
        <input type="hidden" name="question" value="">
        <label for="quality-title">Naam</label>
        <input id="quality-title" name="title" value="{_esc(title)}" required>
        <label for="quality-document">Document</label>
        <select id="quality-document" name="snapshot_id" required>{''.join(options)}</select>
        <button class="btn-primary" type="submit">Audit aanmaken</button>
      </form>
    """


def _render_experiment(audit: dict[str, Any]) -> str:
    payload = audit["payload"]
    baseline = payload.get("baseline") if isinstance(payload.get("baseline"), dict) else {}
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
    return f"""
      <p class="eyebrow">Experiment · {_esc(audit["audit_id"])}</p>
      <h1>{_esc(audit["title"])}</h1>
      <p class="lead">{_esc(payload.get("question"))}</p>
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


def _render_semantic_safety_experiment(audit: dict[str, Any]) -> str:
    payload = audit["payload"]
    report = payload.get("safety_report") if isinstance(payload.get("safety_report"), dict) else {}
    rows = []
    for result in report.get("results") or []:
        candidate = result.get("candidate") if isinstance(result, dict) and isinstance(result.get("candidate"), dict) else {}
        evaluation = candidate.get("evaluation") if isinstance(candidate.get("evaluation"), dict) else {}
        status = "PASS" if candidate.get("pass") else "REVIEW"
        details = []
        if candidate.get("kernel_reject"):
            details.append(f'kernel reject: {candidate.get("kernel_reject")}')
        if evaluation.get("missing_anchors"):
            details.append("ontbrekende bronankers: " + "; ".join(str(x) for x in evaluation["missing_anchors"]))
        if evaluation.get("broken_co_location_groups"):
            details.append("betekenisverband niet behouden")
        rows.append(
            f'<li><b>{_esc(result.get("risk_category"))}</b> · {_esc(result.get("case_id"))} '
            f'— <b>{_esc(status)}</b>'
            f'{f"<br><span class=\"muted\">{_esc(\" · \".join(details))}</span>" if details else ""}</li>'
        )
    return f"""
      <p class="eyebrow">Experiment · {_esc(audit["audit_id"])}</p>
      <h1>{_esc(audit["title"])}</h1>
      <p class="lead">Frozen semantic safety audit. Dit is machinebewijs en geen activatiebesluit.</p>
      <div class="sections">
        <div class="section">
          <h3>Suite</h3>
          <p><b>{_esc(report.get("suite_id"))}</b></p>
          <p>{_esc(report.get("case_count"))} cases · {_esc(report.get("candidate_pass_count"))} machine-pass</p>
          <p class="muted">suite hash {_esc(report.get("suite_hash"))}</p>
        </div>
        <div class="section">
          <h3>Uitvoering</h3>
          <p>model <b>{_esc(report.get("model"))}</b></p>
          <p>commit <b>{_esc(report.get("evaluated_commit"))}</b></p>
          <p><b>{"Machinecheck PASS" if report.get("machine_safety_pass") else "Menselijke beoordeling vereist"}</b></p>
        </div>
      </div>
      <h2>Veiligheidscases</h2>
      <ul>{"".join(rows)}</ul>
      <p class="muted">Menselijke beoordeling blijft vereist. Dit auditrecord activeert semantic mode niet en wijzigt geen Review- of publicatiestatus.</p>
    """


def _render_document_quality(audit: dict[str, Any]) -> str:
    payload = audit["payload"]
    document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), list) else []
    blocked = payload.get("blocked_object_ids") if isinstance(payload.get("blocked_object_ids"), list) else []
    coverage_rows = []
    for row in coverage:
        labels = row.get("labels") if isinstance(row, dict) and isinstance(row.get("labels"), dict) else {}
        detail = ", ".join(f"{label} {count}" for label, count in labels.items() if count) or "geen passages"
        coverage_rows.append(f'<li><b>{_esc(row.get("section"))}</b> — {_esc(detail)}</li>')
    return f"""
      <p class="eyebrow">Documentkwaliteit · {_esc(audit["audit_id"])}</p>
      <h1>{_esc(audit["title"])}</h1>
      <p class="lead">Read-only momentopname. Deze audit heeft het document niet gewijzigd.</p>
      <div class="sections">
        <div class="section">
          <h3>Document</h3>
          <p><b>{_esc(document.get("title"))}</b></p>
          <p>versie {_esc(document.get("version"))} · onderwerp {_esc(document.get("family"))} · klasse {_esc(document.get("class"))}</p>
          <p class="muted">Objectrevision: {_esc(payload.get("snapshot_revision"))}</p>
        </div>
        <div class="section">
          <h3>Technische blokkades</h3>
          <p><b>{len(blocked)}</b> geblokkeerde passages.</p>
        </div>
      </div>
      <h2>Dekking per brononderdeel</h2>
      <ul>{''.join(coverage_rows) or '<li>Geen dekkingsgegevens beschikbaar.</li>'}</ul>
    """


def install_audit_routes(
    app: FastAPI,
    console: OperationsConsole,
    *,
    semantic_safety_post_json: Any | None = None,
) -> None:
    """Install the bounded Audit room on the existing console app."""

    registry = AuditRegistry(console.runtime)
    suite_path = Path(__file__).resolve().parents[1] / "data" / "audit" / "semantic_passage_safety_v1.json"

    def account_for(request: Request) -> dict[str, Any]:
        return console.session_account(request.cookies.get("console_session"))

    def audit_home(request: Request) -> HTMLResponse:
        account = account_for(request)
        body = f"""
          <h1>Audit</h1>
          <p class="lead">Controleer hoe Metis werkt en leg bewijs vast. Audits veranderen geen canonieke kennis en publiceren niets.</p>
          <p><a class="btn-primary" href="/audit/new">Nieuwe audit</a> <a class="btn-secondary" href="/audit/semantic-safety">Frozen semantic safety</a> <a class="btn-secondary" href="/audit/llm-settings">LLM-instellingen</a></p>
          <h2>Audits</h2>
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
              <p class="lead">Kies wat je wilt onderzoeken.</p>
              <div class="doc-list">{_audit_type_cards()}</div>
            """
            return HTMLResponse(_chrome(console, account, body))
        config = AUDIT_TYPES.get(selected)
        if not config or not config.get("enabled"):
            return HTMLResponse(
                _chrome(console, account, '<h1>Auditvorm niet beschikbaar</h1><p><a href="/audit/new">Kies een beschikbaar type</a></p>'),
                status_code=404,
            )
        if selected == "experiment":
            return HTMLResponse(_chrome(console, account, _experiment_form()))
        if selected == "document_quality":
            return HTMLResponse(_chrome(console, account, _document_quality_form(console)))
        return HTMLResponse(_chrome(console, account, "<h1>Auditvorm niet geïmplementeerd</h1>"), status_code=501)

    def audit_create(
        request: Request,
        audit_type: str = Form(...),
        title: str = Form(...),
        question: str = Form(""),
        snapshot_id: str = Form(""),
    ) -> HTMLResponse:
        account = account_for(request)
        if "researcher" not in set(account.get("roles") or []):
            raise ConsoleError("researcher_role_required")
        config = AUDIT_TYPES.get(audit_type)
        if not config or not config.get("enabled"):
            return HTMLResponse(
                _chrome(console, account, '<h1>Auditvorm niet beschikbaar</h1><p><a href="/audit/new">Kies een beschikbaar type</a></p>'),
                status_code=400,
            )
        try:
            if audit_type == "experiment":
                payload = _experiment_payload(question)
            elif audit_type == "document_quality":
                payload = _document_quality_payload(console, snapshot_id)
            else:
                raise ConsoleError("unknown_audit_type")
            audit = registry.create(
                audit_type=audit_type,
                title=title,
                actor_id=account["account_id"],
                payload=payload,
            )
        except ConsoleError as exc:
            if exc.code == "audit_title_required":
                message = "Vul een naam voor de audit in."
            elif exc.code == "audit_question_required":
                message = "Vul een onderzoeksvraag in."
            elif exc.code == "unknown_snapshot":
                message = "Kies een bestaand document."
            else:
                raise
            form = (
                _experiment_form(error=message, title=title, question=question)
                if audit_type == "experiment"
                else _document_quality_form(console, error=message, title=title)
            )
            return HTMLResponse(_chrome(console, account, form), status_code=400)
        return RedirectResponse(f'/audit/{audit["audit_id"]}', status_code=303)

    def audit_detail(request: Request, audit_id: str) -> HTMLResponse:
        account = account_for(request)
        audit = registry.get_audit(audit_id)
        if audit is None:
            return HTMLResponse(_chrome(console, account, '<h1>Audit niet gevonden</h1><p><a href="/audit">Terug naar Audit</a></p>'), status_code=404)
        if audit["audit_type"] == "experiment":
            if (audit.get("payload") or {}).get("state") == "semantic_safety_completed":
                detail = _render_semantic_safety_experiment(audit)
            else:
                detail = _render_experiment(audit)
        elif audit["audit_type"] == "document_quality":
            detail = _render_document_quality(audit)
        else:
            detail = '<h1>Auditvorm niet ondersteund</h1>'
        return HTMLResponse(
            _chrome(
                console,
                account,
                f'<p><a class="btn-secondary" href="/audit">← Terug naar Audit</a></p>{detail}',
            )
        )

    def semantic_safety(request: Request, error: str = "") -> HTMLResponse:
        account = account_for(request)
        if "researcher" not in set(account.get("roles") or []):
            raise ConsoleError("researcher_role_required")
        from src import audit_llm_settings_v1 as llm_settings

        suite = load_frozen_safety_suite(suite_path)
        model = str(os.environ.get(AUDIT_LLM_MODEL_ENV, "") or "").strip()
        commit = str(os.environ.get("METIS_AUDIT_EVALUATED_COMMIT", "") or "").strip().lower()
        secret_status = llm_settings.AuditLLMSecretStore(console.runtime).status()
        ready = bool(model and commit == suite["evaluated_baseline_commit"] and secret_status.get("configured"))
        error_html = f'<div class="banner err">{_esc(error)}</div>' if error else ""
        readiness = (
            '<button class="btn-primary" type="submit">Frozen audit uitvoeren</button>'
            if ready
            else '<p class="muted">Run geblokkeerd: configureer Audit-key, METIS_AUDIT_LLM_MODEL en exact de frozen commit in METIS_AUDIT_EVALUATED_COMMIT.</p>'
        )
        body = f"""
          <p><a class="btn-secondary" href="/audit">← Terug naar Audit</a></p>
          <p class="eyebrow">Audit · Experiment</p>
          <h1>Frozen semantic safety</h1>
          <p class="lead">Controleer weglatingen, voorwaarden, uitzonderingen, negaties en betekenisverbanden op exact dezelfde frozen bron.</p>
          {error_html}
          <article class="doc-card">
            <p><b>Suite</b> {_esc(suite["suite_id"])}</p>
            <p><b>Frozen commit</b> {_esc(suite["evaluated_baseline_commit"])}</p>
            <p><b>Model</b> {_esc(model or "Niet geconfigureerd")}</p>
            <p><b>Cases</b> {len(suite["cases"])}</p>
          </article>
          <form method="post" action="/audit/semantic-safety/run">{readiness}</form>
          <p class="muted">Een run maakt alleen Audit-bewijs. Menselijke beoordeling blijft vereist en semantic mode wordt niet geactiveerd.</p>
        """
        return HTMLResponse(_chrome(console, account, body))

    def semantic_safety_run(request: Request) -> HTMLResponse:
        account = account_for(request)
        if "researcher" not in set(account.get("roles") or []):
            raise ConsoleError("researcher_role_required")
        from src import audit_llm_settings_v1 as llm_settings

        suite = load_frozen_safety_suite(suite_path)
        model = str(os.environ.get(AUDIT_LLM_MODEL_ENV, "") or "").strip()
        commit = str(os.environ.get("METIS_AUDIT_EVALUATED_COMMIT", "") or "").strip().lower()
        if not model:
            return semantic_safety(request, error="METIS_AUDIT_LLM_MODEL is niet geconfigureerd.")
        if commit != suite["evaluated_baseline_commit"]:
            return semantic_safety(request, error="De deployment-commit komt niet overeen met de frozen auditcommit.")
        try:
            api_key = llm_settings.AuditLLMSecretStore(console.runtime).read_api_key()
            report = run_frozen_semantic_safety_suite(
                suite,
                api_key=api_key,
                model=model,
                evaluated_commit=commit,
                post_json=semantic_safety_post_json,
            )
        except ConsoleError as exc:
            return semantic_safety(request, error=f"Audit kon niet worden uitgevoerd: {exc.code}")

        audit = registry.create(
            audit_type="experiment",
            title=f'Frozen semantic safety · {suite["suite_id"]}',
            actor_id=account["account_id"],
            payload={
                "question": "Behoudt semantic passage formation broninhoud en betekenisdragende qualifiers op de frozen safety-suite?",
                "baseline": dict(EXPERIMENT_BASELINE),
                "candidate": dict(EXPERIMENT_CANDIDATE),
                "state": "semantic_safety_completed",
                "safety_report": report,
            },
        )
        return RedirectResponse(f'/audit/{audit["audit_id"]}', status_code=303)

    app.add_api_route("/audit", audit_home, methods=["GET"], response_class=HTMLResponse, name="audit_home")
    app.add_api_route("/audit/new", audit_new, methods=["GET"], response_class=HTMLResponse, name="audit_new")
    app.add_api_route("/audit/semantic-safety", semantic_safety, methods=["GET"], response_class=HTMLResponse, name="audit_semantic_safety")
    app.add_api_route("/audit/semantic-safety/run", semantic_safety_run, methods=["POST"], response_class=HTMLResponse, name="audit_semantic_safety_run")
    app.add_api_route("/audit", audit_create, methods=["POST"], response_class=HTMLResponse, name="audit_create")
    app.add_api_route("/audit/{audit_id}", audit_detail, methods=["GET"], response_class=HTMLResponse, name="audit_detail")
