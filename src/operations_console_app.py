"""FastAPI HTML surface for the internal operations console MVP.

This is the researcher/reviewer door over the knowledge kernel. It is not the
Product API, not inspection, not a care-app frontend, and not a public website.
Chat is not a room.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from src.operations_console_v1 import CONSOLE_VERSION, ConsoleError, OperationsConsole, REPO_ROOT

SERVICE_VERSION = CONSOLE_VERSION
COOKIE = "console_session"

CONSOLE_HTML = """<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>V&amp;VN Data Services — Interne operations console</title>
<style>
:root{font-family:Inter,system-ui,sans-serif;color:#111827;background:#f3f4f6}
body{margin:0}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
.panel{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:16px}
h1{margin:0 0 8px;font-size:26px}h2{margin:0 0 12px;font-size:18px}
.muted{color:#6b7280}nav a{margin-right:12px;color:#1d4ed8;text-decoration:none;font-weight:650}
label{display:block;margin:10px 0 4px;font-weight:650}input,select,textarea{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box}
button{border:0;border-radius:8px;padding:10px 16px;background:#111827;color:#fff;font-weight:650;cursor:pointer;margin-top:12px}
.banner{padding:10px 12px;border-radius:8px;margin:12px 0;background:#ecfdf5;border:1px solid #a7f3d0}
.warn{background:#fff7ed;border-color:#fdba74}.err{background:#fef2f2;border-color:#fecaca}
.tree{font-family:ui-monospace,Menlo,monospace;font-size:13px}li{margin:6px 0}
</style>
</head>
<body><div class="wrap">
__BODY__
</div></body></html>
"""


def _page(body: str) -> str:
    return CONSOLE_HTML.replace("__BODY__", body)


def _esc(value: Any) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _nav(account: dict[str, Any] | None) -> str:
    who = f'{_esc(account.get("display_name"))} · rollen: {", ".join(_esc(r) for r in account.get("roles") or [])}' if account else "niet aangemeld"
    return f"""
    <div class="panel">
      <h1>V&amp;VN Data Services — Interne operations console</h1>
      <div class="muted">Menselijke deur over de knowledge kernel voor richtlijnonderzoekers en reviewers. Dit is niet de Product API. Niet ontworpen voor verpleegkundigen. Chat is geen kamer in deze console.</div>
      <nav>
        <a href="/ingest">Ingest (mailbox)</a>
        <a href="/tree">Familieboom</a>
        <a href="/review">Review</a>
        <a href="/publish">Publish</a>
        <a href="/logout">Uitloggen</a>
      </nav>
      <div class="muted">{who}</div>
    </div>
    """


def create_console_app(console: OperationsConsole | None = None) -> FastAPI:
    state = console or OperationsConsole(root=REPO_ROOT)
    app = FastAPI(
        title="V&VN Data Services Internal Operations Console",
        version=SERVICE_VERSION,
        description="Internal researcher/reviewer console. Not the Product API. Chat is not a room.",
    )

    def _current(request: Request) -> dict[str, Any] | None:
        token = request.cookies.get(COOKIE)
        try:
            return state.session_account(token)
        except ConsoleError:
            return None

    def _require(request: Request) -> dict[str, Any]:
        account = _current(request)
        if not account:
            raise ConsoleError("not_authenticated")
        return account

    @app.exception_handler(ConsoleError)
    async def console_errors(_request: Request, exc: ConsoleError) -> HTMLResponse:
        status = 401 if exc.code in {"not_authenticated", "invalid_credentials"} else 403 if "role_required" in exc.code else 400
        body = _page(f'{_nav(None)}<div class="panel"><div class="banner err">{_esc(exc.code)}</div><p><a href="/login">Naar login</a></p></div>')
        return HTMLResponse(body, status_code=status)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request) -> str:
        account = _current(request)
        if not account:
            return _page(
                """
                <div class="panel">
                  <h1>V&amp;VN Data Services — Interne operations console</h1>
                  <p class="muted">Interne identiteit. Geen open registratie. Chat is geen kamer.</p>
                  <p><a href="/login">Inloggen</a></p>
                </div>
                """
            )
        return RedirectResponse("/ingest", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_form() -> str:
        return _page(
            """
            <div class="panel">
              <h2>Interne login</h2>
              <p class="muted">Geen open registratie. Geen gedeelde login voor review of publish.</p>
              <form method="post" action="/login">
                <label>Gebruikersnaam</label><input name="username" required>
                <label>Wachtwoord</label><input type="password" name="password" required>
                <button type="submit">Inloggen</button>
              </form>
            </div>
            """
        )

    @app.post("/login")
    def login(username: str = Form(...), password: str = Form(...)) -> RedirectResponse:
        session = state.authenticate(username, password)
        response = RedirectResponse("/ingest", status_code=303)
        response.set_cookie(COOKIE, session["token"], httponly=True, samesite="lax")
        return response

    @app.get("/logout")
    def logout(request: Request) -> RedirectResponse:
        state.logout(request.cookies.get(COOKIE))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE)
        return response

    @app.get("/ingest", response_class=HTMLResponse)
    def ingest_get(request: Request) -> str:
        account = _require(request)
        reviewers = state.list_reviewer_accounts()
        options = "".join(
            f'<option value="{_esc(row["account_id"])}">{_esc(row["display_name"])} ({_esc(row["username"])})</option>'
            for row in reviewers
        )
        return _page(
            f"""
            {_nav(account)}
            <div class="panel">
              <h2>Ingest — mailbox</h2>
              <div class="banner">Onderzoekerspad voor Continentie bron 2: deze mailbox. Geen parallel ingestpad voor engineers als onderzoekerservaring. Officiële first-wave bestanden: HTML-pagina of PDF. Word en kennisplatform story.html-boomplayers worden geweigerd. Capture is geen publicatie.</div>
              <form method="post" action="/ingest" enctype="multipart/form-data">
                <label>Bestand (HTML of PDF)</label><input type="file" name="file">
                <label>Of URL (wordt onmiddellijk naar exacte bytes gesnapshot)</label><input name="url" placeholder="https://...">
                <label>Nieuw of nieuwe versie</label>
                <select name="ingest_kind"><option value="new">new</option><option value="new_version">new_version</option></select>
                <label>Vervangt snapshot (bij nieuwe versie)</label><input name="replaces_snapshot_id">
                <label>Titel</label><input name="title" required>
                <label>Versie</label><input name="version" required>
                <label>Datum</label><input name="date" placeholder="2025-04-01" required>
                <label>Live URL</label><input name="live_url">
                <label>Klasse</label>
                <select name="class_">
                  <option value="richtlijn">richtlijn</option>
                  <option value="handreiking">handreiking</option>
                  <option value="artikel">artikel</option>
                  <option value="transcript">transcript</option>
                  <option value="podcast">podcast</option>
                </select>
                <label>Familie (haak, geen nieuw bestand; MVP één familie per document)</label>
                <input name="family" value="continentie" required>
                <label>Benoemde reviewers (uploader mag reviewer zijn, maar MUST NOT de enige zijn)</label>
                <select name="named_reviewers" multiple size="6">{options}</select>
                <button type="submit">Envelope inleveren</button>
              </form>
            </div>
            """
        )

    @app.post("/ingest", response_class=HTMLResponse)
    async def ingest_post(
        request: Request,
        ingest_kind: str = Form(...),
        title: str = Form(...),
        version: str = Form(...),
        date: str = Form(...),
        live_url: str = Form(""),
        class_: str = Form(...),
        family: str = Form(...),
        url: str = Form(""),
        replaces_snapshot_id: str = Form(""),
        named_reviewers: list[str] = Form(default=[]),
        file: UploadFile | None = File(None),
    ) -> str:
        account = _require(request)
        filename = None
        data = None
        content_type = None
        if file is not None and file.filename:
            filename = file.filename
            data = await file.read()
            content_type = file.content_type
        receipt = state.ingest(
            actor_id=account["account_id"],
            filename=filename,
            data=data or None,
            content_type=content_type,
            url=url.strip() or None,
            ingest_kind=ingest_kind,
            title=title,
            version=version,
            date=date,
            live_url=live_url,
            class_=class_,
            family=family,
            named_reviewers=named_reviewers,
            replaces_snapshot_id=replaces_snapshot_id.strip() or None,
        )
        return _page(
            f"""
            {_nav(account)}
            <div class="panel">
              <h2>Receipt</h2>
              <div class="banner">SHA-256 {_esc(receipt["sha256"])} · locator {_esc(receipt["locator"])} · staat {_esc(receipt["state"])}. Immutable locator (G2) ontbreekt; publicatie blijft BLOCKED.</div>
              <pre>{_esc(receipt)}</pre>
            </div>
            """
        )

    @app.get("/tree", response_class=HTMLResponse)
    def tree(request: Request) -> str:
        account = _require(request)
        payload = state.family_tree()
        blocks = []
        for family, node in payload["families"].items():
            children = "".join(
                f'<li>{_esc(child["class"])} · {_esc(child["title"])} · {_esc(child["sha256"][:12])}… · parent={_esc(child["parent"])}</li>'
                for child in node["children"]
            )
            blocks.append(f"<h3>Familie {_esc(family)}</h3><ul class='tree'>{children}</ul>")
        return _page(
            f"""
            {_nav(account)}
            <div class="panel">
              <h2>Familieboom = familie × klasse</h2>
              <p class="muted">Familie is een haak, geen nieuw bestand. Een richtlijn is niet de ouder van een podcast; zij zijn siblings onder de familie. Een branch morgen toevoegen tekent de boom niet opnieuw.</p>
              {''.join(blocks) or "<p>Nog geen envelopes.</p>"}
              <form method="post" action="/tree/move">
                <h3>Verplaatsen tussen families (curatoract; geen re-hash, geen klinische herreview)</h3>
                <label>Snapshot</label><input name="snapshot_id" required>
                <label>Nieuwe familie</label><input name="new_family" required>
                <button type="submit">Verplaatsen</button>
              </form>
              <form method="post" action="/tree/promote">
                <h3>Klasse promoveren (MUST require review)</h3>
                <label>Snapshot</label><input name="snapshot_id" required>
                <label>Nieuwe klasse</label>
                <select name="new_class">
                  <option>richtlijn</option><option>handreiking</option><option>artikel</option><option>transcript</option><option>podcast</option>
                </select>
                <button type="submit">Promoveren</button>
              </form>
            </div>
            """
        )

    @app.post("/tree/move")
    def tree_move(request: Request, snapshot_id: str = Form(...), new_family: str = Form(...)) -> RedirectResponse:
        account = _require(request)
        state.move_family(actor_id=account["account_id"], snapshot_id=snapshot_id, new_family=new_family)
        return RedirectResponse("/tree", status_code=303)

    @app.post("/tree/promote")
    def tree_promote(request: Request, snapshot_id: str = Form(...), new_class: str = Form(...)) -> RedirectResponse:
        account = _require(request)
        state.promote_class(actor_id=account["account_id"], snapshot_id=snapshot_id, new_class=new_class)
        return RedirectResponse("/tree", status_code=303)

    @app.get("/review", response_class=HTMLResponse)
    def review_get(request: Request, snapshot_id: str = "") -> str:
        account = _require(request)
        envelopes = state.list_envelopes()
        options = "".join(
            f'<option value="{_esc(row["snapshot_id"])}" {"selected" if row["snapshot_id"]==snapshot_id else ""}>{_esc(row["title"])} · {_esc(row["class"])} · {_esc(row["family"])}</option>'
            for row in envelopes
        )
        objects_html = ""
        if snapshot_id:
            for obj in state.snapshot_objects(snapshot_id):
                objects_html += f"""
                <div class="panel">
                  <div><b>{_esc(obj["object_id"])}</b> · {_esc(obj["object_type"])} · {_esc(obj["governance"]["validation_status"])} · v{_esc(obj["object_version"])}</div>
                  <p>{_esc(obj["content"]["clean_text"])}</p>
                  <form method="post" action="/review">
                    <input type="hidden" name="snapshot_id" value="{_esc(snapshot_id)}">
                    <input type="hidden" name="object_id" value="{_esc(obj["object_id"])}">
                    <label>Besluit</label>
                    <select name="decision"><option>approve</option><option>revise</option><option>reject</option></select>
                    <label>Toelichting</label><textarea name="comment"></textarea>
                    <label>Proposed correction</label><textarea name="proposed_correction"></textarea>
                    <button type="submit">Review vastleggen</button>
                  </form>
                </div>
                """
        return _page(
            f"""
            {_nav(account)}
            <div class="panel">
              <h2>Review — verplichte return-loop</h2>
              <p class="muted">Geen Excel. Reviewer werkt op de exacte snapshot-objecten. Reject/correctie maakt een nieuwe objectversie of blokkeert de oude. Gepubliceerde waarheid wordt nooit stilzwijgend gewijzigd. Uploader MUST NOT de enige vereiste reviewer zijn.</p>
              <form method="get" action="/review">
                <label>Snapshot</label><select name="snapshot_id">{options}</select>
                <button type="submit">Openen</button>
              </form>
            </div>
            {objects_html}
            """
        )

    @app.post("/review")
    def review_post(
        request: Request,
        snapshot_id: str = Form(...),
        object_id: str = Form(...),
        decision: str = Form(...),
        comment: str = Form(""),
        proposed_correction: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        state.review_object(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            decision=decision,
            comment=comment,
            proposed_correction=proposed_correction,
        )
        if decision == "revise" and proposed_correction.strip():
            state.correct_object(
                actor_id=account["account_id"],
                snapshot_id=snapshot_id,
                object_id=object_id,
                patch={
                    "reason": comment or "reviewer correction",
                    "operations": [{"op": "set", "path": "content.clean_text", "value": proposed_correction.strip()}],
                },
            )
        return RedirectResponse(f"/review?snapshot_id={snapshot_id}", status_code=303)

    @app.get("/publish", response_class=HTMLResponse)
    def publish_get(request: Request) -> str:
        account = _require(request)
        rows = []
        for envelope in state.list_envelopes():
            considered = None
            try:
                considered = state.consider_publish(actor_id=account["account_id"], snapshot_id=envelope["snapshot_id"])
            except ConsoleError as exc:
                considered = {"blockers": [exc.code], "publish_allowed": False}
            rows.append(
                f"<li>{_esc(envelope['title'])} · {_esc(envelope['state'])} · blockers: {_esc(considered['blockers'])}</li>"
            )
        return _page(
            f"""
            {_nav(account)}
            <div class="panel">
              <h2>Publish — kleine derde kamer</h2>
              <div class="banner warn">Publicatie blijft BLOCKED zonder immutable locator (G2). Lokale sources/private/ is geen productie. Cutover wordt niet gefingeerd.</div>
              <ul>{''.join(rows) or "<li>Geen snapshots.</li>"}</ul>
            </div>
            """
        )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "operations-console",
            "version": SERVICE_VERSION,
            "product_api": False,
            "chat_room": False,
            "nurse_frontend": False,
        }

    return app


def create_app() -> FastAPI:
    return create_console_app()
