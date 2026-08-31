"""FastAPI HTML surface for the internal operations console.

Task-oriented researcher door over the knowledge kernel (Protocol v2.9).
Not the Product API, not a care-app frontend, and not a public website.
Chat is not a room.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.four_eyes_v1 import requires_four_eyes
from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES
from src.operations_console_v1 import (
    ALLOWED_CLASSES,
    CONSOLE_VERSION,
    ConsoleError,
    OperationsConsole,
    REPO_ROOT,
)
from src.serving_relations_v1 import CLOSED_RELATION_TYPES, proposed_relations

SERVICE_VERSION = CONSOLE_VERSION
COOKIE = "console_session"
BRAND_DIR = REPO_ROOT / "assets" / "brand"
HELP_ONCE = (
    "Interne operations console voor richtlijnonderzoekers en reviewers. "
    "Dit is niet de Product API. Niet ontworpen voor verpleegkundigen. "
    "Chat is geen kamer in deze console. Geen parallel ingestpad voor engineers "
    "als onderzoekerservaring."
)
STATUS_LABELS = {
    "captured_not_published": "ingevoerd, niet gepubliceerd",
}
BLOCKER_LABELS = {
    "second_named_reviewer_required": "Nog een andere benoemde reviewer moet goedkeuren.",
    "blocked_pending_immutable_locator": "Duurzame opslag ontbreekt; publicatie blijft geblokkeerd.",
    "object_tuple_required": "Publicatie vereist review gebonden aan object, versie, hash, bevestigd type, reviewer en besluit.",
    "four_eyes_required": "High-risk objecten vereisen four-eyes: een tweede benoemde reviewer op hetzelfde objecttupel.",
}
ERROR_COPY = {
    "not_authenticated": "Je bent niet aangemeld.",
    "invalid_credentials": "Gebruikersnaam of wachtwoord is onjuist.",
    "uploader_cannot_be_sole_required_reviewer": "De uploader mag reviewer zijn, maar niet de enige.",
    "word_not_first_wave": "Word-bestanden horen niet bij de first wave. Lever HTML of PDF in.",
    "story_html_boom_player_out_of_first_wave": "Kennisplatform-boomplayers horen niet bij de first wave.",
    "official_file_or_url_required": "Kies een HTML- of PDF-bestand, of een URL.",
    "named_reviewers_required": "Kies minstens één andere reviewer dan jezelf.",
    "publisher_role_required": "Publiceren vereist de rol publisher.",
    "reviewer_role_required": "Review vereist de rol reviewer.",
    "researcher_role_required": "Inleveren vereist de rol researcher.",
    "live_url_html_not_allowed": "Een live HTML-URL kan niet worden ingeleverd. Lever een HTML-bestand of een PDF-URL in.",
    "unknown_object_type": "Kies een type uit de gesloten set.",
    "object_type_not_confirmed": "Kies een type uit de gesloten set.",
    "unknown_role": "Alleen researcher, reviewer of publisher zijn toegestaan.",
    "forbidden_reviewer_identity": "Deze identiteit mag niet als reviewer worden aangemaakt.",
    "unknown_relation_type": "Kies alleen relaties uit de gesloten set.",
    "open_original_required": "Open eerst de bronpassage. Type bevestigen zonder het origineel is niet toegestaan.",
    "source_locator_missing": "De bronpassage ontbreekt; type bevestigen is niet toegestaan.",
    "freeze_bytes_missing": "Het geüploade origineel ontbreekt; type bevestigen is niet toegestaan.",
    "locator_kind_mismatch": "De locator past niet bij dit bestand.",
    "unsupported_locator": "Deze locator kan niet worden geopend.",
}
RELATION_LABELS = {
    "applies_if": "geldt indien",
    "except_if": "geldt niet indien",
    "defines": "definieert",
    "explains": "licht toe",
    "supported_by": "onderbouwd door",
    "supersedes": "vervangt",
    "parent": "bovenliggend",
    "child": "onderliggend",
}


def _esc(value: Any) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _status_label(state: str) -> str:
    return STATUS_LABELS.get(state, state.replace("_", " "))


def _beeldmerk() -> str:
    return (
        '<img class="beeldmerk" src="/brand/venvn-beeldmerk.png" '
        'width="94" height="32" alt="v&amp;vn">'
    )


def _page(body: str) -> str:
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>V&amp;VN Data Services — Interne operations console</title>
<link rel="stylesheet" href="/brand/console.css">
</head>
<body>
<div class="shell">
{body}
</div>
</body>
</html>
"""


def _help() -> str:
    return f"""
    <details class="help">
      <summary>Over deze console</summary>
      <p>{_esc(HELP_ONCE)}</p>
    </details>
    """


def _nav(account: dict[str, Any] | None, current: str = "", counts: dict[str, int] | None = None) -> str:
    who = (
        f'{_esc(account.get("display_name"))} · rollen: {", ".join(_esc(r) for r in account.get("roles") or [])}'
        if account
        else "niet aangemeld"
    )
    counts = counts or {}
    rooms = [
        ("ingest", "/ingest", "Inleveren", counts.get("ingest", 0)),
        ("tree", "/tree", "Documentenhiërarchie", counts.get("tree", 0)),
        ("review", "/review", "Review", counts.get("review", 0)),
        ("publish", "/publish", "Publiceren", counts.get("publish", 0)),
        ("accounts", "/accounts", "Accounts", 0),
    ]
    links = []
    for key, href, label, count in rooms:
        current_attr = ' aria-current="page"' if current == key else ""
        badge = f'<span class="badge">{count}</span>' if count else ""
        links.append(f'<a href="{href}"{current_attr}>{label}{badge}</a>')
    links.append('<a class="quiet" href="/logout">Uitloggen</a>')
    return f"""
    <header class="topbar">
      <a class="brand" href="/" aria-label="V&amp;VN Data Services">
        {_beeldmerk()}
        <span class="brand-name">Data Services</span>
      </a>
      <nav class="rooms">{"".join(links)}</nav>
      <div class="who">{who}</div>
    </header>
    """


def _class_options(selected: str = "richtlijn") -> str:
    return "".join(
        f'<option value="{_esc(name)}"{" selected" if name == selected else ""}>{_esc(name)}</option>'
        for name in ALLOWED_CLASSES
    )


def _document_options(rows: list[dict[str, Any]], selected: str = "") -> str:
    options = ['<option value="">Kies een document</option>']
    for row in rows:
        label = f'{row["title"]} · {row["version"]} · {row["family"]}'
        snap = row["snapshot_id"]
        options.append(
            f'<option value="{_esc(snap)}"{" selected" if snap == selected else ""}>{_esc(label)}</option>'
        )
    return "".join(options)


def _type_options(confirmed: str) -> str:
    placeholder_selected = " selected" if not confirmed else ""
    options = [
        f'<option value="" disabled{placeholder_selected}>nog niet bevestigd</option>'
    ]
    for name in CLOSED_OBJECT_TYPES:
        selected = " selected" if name == confirmed else ""
        options.append(f'<option value="{name}"{selected}>{name}</option>')
    return "".join(options)


def _relation_checkboxes(obj: dict[str, Any], objects: list[dict[str, Any]]) -> str:
    by_id = {row.get("object_id"): row for row in objects}
    confirmed = {
        (row.get("relation_type"), row.get("target_object_id"))
        for row in (obj.get("confirmed_relations") or [])
        if row.get("relation_type") in CLOSED_RELATION_TYPES
    }
    proposed = [
        row
        for row in proposed_relations(obj)
        if row.get("relation_type") in CLOSED_RELATION_TYPES
    ]
    if not proposed:
        return ""
    boxes = []
    for row in proposed:
        rel = row["relation_type"]
        target_id = row["target_object_id"]
        target = by_id.get(target_id) or {}
        target_text = (
            (target.get("content") or {}).get("heading")
            or (target.get("content") or {}).get("clean_text")
            or target_id
        )
        checked = " checked" if (rel, target_id) in confirmed else ""
        label = RELATION_LABELS.get(rel, rel)
        boxes.append(
            f'<label class="check">'
            f'<input type="checkbox" name="relation" value="{_esc(rel)}:{_esc(target_id)}"{checked}>'
            f'{_esc(label)} ({_esc(rel)}) → {_esc(target_text)}</label>'
        )
    return (
        '<fieldset class="relations">'
        "<legend>Voorgestelde relaties</legend>"
        f"{''.join(boxes)}"
        '<button class="btn-secondary" type="submit" form="relations-'
        f'{_esc(obj["object_id"])}">Relaties bevestigen</button>'
        "</fieldset>"
    )


def _document_card_heading(row: dict[str, Any]) -> str:
    return f"""
      <header>
        <p class="doc-title">{_esc(row["title"])}</p>
      </header>
      <p class="meta">
        <span>versie <b>{_esc(row["version"])}</b></span>
        <span>familie <b>{_esc(row["family"])}</b></span>
        <span>klasse <b>{_esc(row["class"])}</b></span>
        <span>status <b>{_esc(_status_label(row.get("status") or row.get("state") or ""))}</b></span>
      </p>
    """


def create_console_app(console: OperationsConsole | None = None) -> FastAPI:
    state = console or OperationsConsole(root=REPO_ROOT)
    app = FastAPI(
        title="V&VN Data Services Internal Operations Console",
        version=SERVICE_VERSION,
        description="Internal researcher/reviewer console. Not the Product API. Chat is not a room.",
    )
    if BRAND_DIR.is_dir():
        app.mount("/brand", StaticFiles(directory=str(BRAND_DIR)), name="brand")

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

    def _counts(account: dict[str, Any] | None) -> dict[str, int]:
        if not account:
            return {}
        return state.waiting_task_counts(account["account_id"])

    @app.exception_handler(ConsoleError)
    async def console_errors(_request: Request, exc: ConsoleError) -> HTMLResponse:
        status = 401 if exc.code in {"not_authenticated", "invalid_credentials"} else 403 if "role_required" in exc.code else 400
        message = ERROR_COPY.get(exc.code, "Deze actie is niet toegestaan.")
        body = _page(
            f"""
            {_nav(None)}
            <section class="room">
              <h1>Actie niet uitgevoerd</h1>
              <div class="banner err">{_esc(message)}</div>
              <p class="muted">{_esc(exc.code)}</p>
              <p><a href="/login">Naar aanmelden</a></p>
            </section>
            {_help()}
            """
        )
        return HTMLResponse(body, status_code=status)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request) -> str:
        account = _current(request)
        if not account:
            return _page(
                f"""
                <section class="room login-card">
                  <a class="brand" href="/login" aria-label="V&amp;VN Data Services">
                    {_beeldmerk()}
                    <span class="brand-name">Data Services</span>
                  </a>
                  <h1>Interne operations console</h1>
                  <p class="lead">Meld je aan om documenten in te leveren, te reviewen of te publiceren.</p>
                  <p><a class="btn-primary" href="/login" style="display:inline-block;text-decoration:none;">Aanmelden</a></p>
                </section>
                {_help()}
                """
            )
        return RedirectResponse("/ingest", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_form() -> str:
        return _page(
            f"""
            <section class="room login-card">
              <a class="brand" href="/login" aria-label="V&amp;VN Data Services">
                {_beeldmerk()}
                <span class="brand-name">Data Services</span>
              </a>
              <h1>Aanmelden</h1>
              <p class="lead">Meld je aan met je interne account. Geen open registratie. Geen gedeelde login.</p>
              <form method="post" action="/login">
                <label for="gebruikersnaam">Gebruikersnaam</label>
                <input id="gebruikersnaam" name="username" autocomplete="username" required>
                <label for="wachtwoord">Wachtwoord</label>
                <input id="wachtwoord" type="password" name="password" autocomplete="current-password" required>
                <button class="btn-primary" type="submit">Aanmelden</button>
              </form>
            </section>
            {_help()}
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
        documents = state.list_envelopes()
        return _page(
            f"""
            {_nav(account, "ingest", _counts(account))}
            <section class="room">
              <h1>Document inleveren</h1>
              <p class="lead">Lever een HTML-pagina of PDF in voor review. Continentie is de eerste documentfamilie op dit onderzoekerspad.</p>
              <p class="next">Daarna: het document verschijnt in de documentenhierarchie en gaat naar review. Publiceren is een later, apart besluit.</p>
              <p class="statement">Verwacht: titel, versie, familie en klasse, plus minstens één andere reviewer dan jezelf.</p>
              <form method="post" action="/ingest" enctype="multipart/form-data">
                <div class="sections">
                  <div class="section">
                    <h3>Bron</h3>
                    <label for="file">Bestand (HTML of PDF)</label>
                    <input id="file" type="file" name="file">
                    <label for="url">Of PDF-URL (exacte bytes worden direct vastgelegd)</label>
                    <input id="url" name="url" placeholder="https://...">
                  </div>
                  <div class="section">
                    <h3>Document</h3>
                    <div class="field-row">
                      <div>
                        <label for="title">Titel</label>
                        <input id="title" name="title" required>
                      </div>
                      <div>
                        <label for="version">Versie</label>
                        <input id="version" name="version" required>
                      </div>
                    </div>
                    <div class="field-row">
                      <div>
                        <label for="date">Datum</label>
                        <input id="date" name="date" placeholder="2025-04-01" required>
                      </div>
                      <div>
                        <label for="class_">Klasse</label>
                        <select id="class_" name="class_">{_class_options()}</select>
                      </div>
                    </div>
                    <label for="family">Familie</label>
                    <input id="family" name="family" value="continentie" required>
                    <label for="ingest_kind">Nieuw of nieuwe versie</label>
                    <select id="ingest_kind" name="ingest_kind">
                      <option value="new">Nieuw document</option>
                      <option value="new_version">Nieuwe versie van een bestaand document</option>
                    </select>
                    <div id="replaces-row" hidden>
                      <label for="replaces_document">Bestaand document</label>
                      <select id="replaces_document" name="replaces_document">{_document_options(documents)}</select>
                    </div>
                    <label for="live_url">Live URL (optioneel)</label>
                    <input id="live_url" name="live_url">
                  </div>
                  <div class="section">
                    <h3>Reviewers</h3>
                    <label for="named_reviewers">Benoemde reviewers</label>
                    <select id="named_reviewers" name="named_reviewers" multiple size="6">{options}</select>
                    <p class="muted">De uploader mag reviewer zijn, maar niet de enige.</p>
                  </div>
                </div>
                <button class="btn-primary" type="submit">Inleveren</button>
              </form>
            </section>
            {_help()}
            <script>
            (function () {{
              var kind = document.getElementById("ingest_kind");
              var row = document.getElementById("replaces-row");
              function sync() {{ row.hidden = kind.value !== "new_version"; }}
              kind.addEventListener("change", sync);
              sync();
            }})();
            </script>
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
        replaces_document: str = Form(""),
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
        if isinstance(named_reviewers, str):
            named_reviewers = [named_reviewers] if named_reviewers.strip() else []
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
            replaces_snapshot_id=replaces_document.strip() or None,
        )
        return _page(
            f"""
            {_nav(account, "ingest", _counts(account))}
            <section class="room">
              <h1>Document ingeleverd</h1>
              <p class="lead">Het document is vastgelegd en wacht op review.</p>
              <p class="next">Volgende stap: open Review en laat een andere benoemde reviewer het document beoordelen.</p>
              <div class="doc-card">
                {_document_card_heading({**receipt, "status": receipt["state"]})}
              </div>
              <p><a class="btn-secondary" href="/review">Naar review</a> <a class="btn-secondary" href="/tree">Naar documentenhierarchie</a></p>
            </section>
            {_help()}
            """
        )

    @app.get("/tree", response_class=HTMLResponse)
    def tree(request: Request) -> str:
        account = _require(request)
        can_move = "researcher" in account["roles"] or "publisher" in account["roles"]
        can_promote = "reviewer" in account["roles"]
        payload = state.family_tree()
        blocks: list[str] = []
        for family, node in payload["families"].items():
            cards = []
            for child in node["children"]:
                actions = []
                if can_move:
                    actions.append(
                        f"""
                        <form method="post" action="/tree/move">
                          <input type="hidden" name="snapshot_id" value="{_esc(child["snapshot_id"])}">
                          <input type="hidden" name="title" value="{_esc(child["title"])}">
                          <input type="hidden" name="version" value="{_esc(child["version"])}">
                          <input type="hidden" name="family" value="{_esc(child["family"])}">
                          <label>Nieuwe familie
                            <input name="new_family" required placeholder="familie">
                          </label>
                          <button class="btn-secondary" type="submit">Verplaatsen</button>
                        </form>
                        """
                    )
                if can_promote:
                    actions.append(
                        f"""
                        <form method="post" action="/tree/promote">
                          <input type="hidden" name="snapshot_id" value="{_esc(child["snapshot_id"])}">
                          <input type="hidden" name="title" value="{_esc(child["title"])}">
                          <input type="hidden" name="version" value="{_esc(child["version"])}">
                          <input type="hidden" name="family" value="{_esc(child["family"])}">
                          <label>Nieuwe klasse
                            <select name="new_class">{_class_options(child["class"])}</select>
                          </label>
                          <button class="btn-secondary" type="submit">Promoveren</button>
                        </form>
                        """
                    )
                cards.append(
                    f"""
                    <article class="doc-card">
                      {_document_card_heading(child)}
                      <div class="doc-actions">{"".join(actions)}</div>
                    </article>
                    """
                )
            blocks.append(
                f'<h2>Familie {_esc(family)}</h2><div class="doc-list">{"".join(cards)}</div>'
            )
        empty = '<p class="muted">Nog geen documenten. Lever eerst een document in.</p>'
        return _page(
            f"""
            {_nav(account, "tree", _counts(account))}
            <section class="room">
              <h1>Documentenhiërarchie</h1>
              <p class="lead">Bekijk documenten per familie en klasse. Verplaats een document naar een andere familie, of promoveer de klasse.</p>
              <p class="next">Verplaatsen is een curatoract (geen herhash). Promoveren vereist daarna opnieuw review.</p>
              {"".join(blocks) or empty}
            </section>
            {_help()}
            """
        )

    @app.post("/tree/move")
    def tree_move(
        request: Request,
        new_family: str = Form(...),
        snapshot_id: str = Form(""),
        title: str = Form(""),
        version: str = Form(""),
        family: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        if snapshot_id.strip():
            state.move_family(actor_id=account["account_id"], snapshot_id=snapshot_id, new_family=new_family)
        else:
            state.move_family_document(
                actor_id=account["account_id"],
                title=title,
                version=version,
                family=family,
                new_family=new_family,
            )
        return RedirectResponse("/tree", status_code=303)

    @app.post("/tree/promote")
    def tree_promote(
        request: Request,
        new_class: str = Form(...),
        snapshot_id: str = Form(""),
        title: str = Form(""),
        version: str = Form(""),
        family: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        if snapshot_id.strip():
            state.promote_class(actor_id=account["account_id"], snapshot_id=snapshot_id, new_class=new_class)
        else:
            state.promote_class_document(
                actor_id=account["account_id"],
                title=title,
                version=version,
                family=family,
                new_class=new_class,
            )
        return RedirectResponse("/tree", status_code=303)

    @app.get("/review", response_class=HTMLResponse)
    def review_get(request: Request, document: str = "") -> str:
        account = _require(request)
        chosen = document.strip()
        envelopes = state.list_envelopes()
        chosen_row = next((row for row in envelopes if row["snapshot_id"] == chosen), None)
        picker = f"""
              <form method="get" action="/review">
                <label for="document">Document</label>
                <div class="actions">
                  <select id="document" name="document">{_document_options(envelopes, chosen)}</select>
                  <button class="btn-secondary" type="submit">Openen</button>
                </div>
              </form>
        """
        cards = []
        if not chosen:
            for row in envelopes:
                cards.append(
                    f"""
                    <article class="doc-card">
                      {_document_card_heading({**row, "status": row["state"]})}
                      <p><a class="btn-secondary" href="/review?document={_esc(row["snapshot_id"])}">Reviewen</a></p>
                    </article>
                    """
                )
        objects_html = ""
        if chosen_row:
            objects_html += f'<div class="doc-card">{_document_card_heading({**chosen_row, "status": chosen_row["state"]})}</div>'
            snapshot_objects = state.snapshot_objects(chosen)
            for obj in snapshot_objects:
                heading = (obj.get("content") or {}).get("heading") or obj.get("object_type")
                text = (obj.get("content") or {}).get("clean_text") or ""
                status = (obj.get("governance") or {}).get("validation_status") or ""
                proposed = obj.get("proposed_object_type") or ""
                confirmed = obj.get("confirmed_object_type") or ""
                type_options = _type_options(confirmed)
                passage_ok = False
                passage_html = ""
                try:
                    opened = state.open_source_passage(snapshot_id=chosen, object_id=obj["object_id"])
                    passage_ok = True
                    passage_html = f"""
                  <aside class="review-card-bronpassage" aria-label="Exacte bronpassage">
                    <h4>Bronpassage</h4>
                    <pre>{_esc(opened.get("passage") or "")}</pre>
                    <p><a class="btn-secondary" href="/review/bronpassage?document={_esc(chosen)}&amp;object={_esc(obj["object_id"])}">Open bronpassage</a></p>
                  </aside>
                    """
                except ConsoleError:
                    passage_html = (
                        '<aside class="review-card-bronpassage" aria-label="Exacte bronpassage ontbreekt">'
                        '<h4>Bronpassage</h4>'
                        '<p class="muted">Bronpassage ontbreekt; type bevestigen en goedkeuren zijn '
                        'uitgeschakeld tot het origineel open kan.</p></aside>'
                    )
                type_disabled = "" if passage_ok else " disabled"
                approve_disabled = "" if passage_ok else " disabled"
                four_eyes_html = ""
                if requires_four_eyes(obj, confirmed_type=confirmed or None):
                    four_eyes_html = (
                        '<div class="banner warn">Dit object vereist four-eyes: '
                        "<b>tweede reviewer nodig</b>.</div>"
                    )
                relation_form = ""
                relation_boxes = _relation_checkboxes(obj, snapshot_objects)
                if relation_boxes:
                    relation_form = f"""
                  <form id="relations-{_esc(obj["object_id"])}" method="post" action="/review/relations">
                    <input type="hidden" name="snapshot_id" value="{_esc(chosen)}">
                    <input type="hidden" name="object_id" value="{_esc(obj["object_id"])}">
                    {relation_boxes}
                  </form>
                    """
                objects_html += f"""
                <article class="object review-card-two-column">
                  <section class="review-card-object" aria-label="Kennisobject en reviewbesluit">
                  <h3>{_esc(heading)}</h3>
                  <p class="meta"><span>status <b>{_esc(status)}</b></span><span>huidig type <b>{_esc(obj.get("object_type"))}</b></span>{"<span>voorstel <b>" + _esc(proposed) + "</b></span>" if proposed else ""}</p>
                  {four_eyes_html}
                  <p>{_esc(text)}</p>
                  {relation_form}
                  <form method="post" action="/review">
                    <input type="hidden" name="snapshot_id" value="{_esc(chosen)}">
                    <input type="hidden" name="object_id" value="{_esc(obj["object_id"])}">
                    <label for="type-{_esc(obj["object_id"])}">Bevestig type</label>
                    <select id="type-{_esc(obj["object_id"])}" name="confirmed_object_type"{type_disabled}>{type_options}</select>
                    <label for="decision-{_esc(obj["object_id"])}">Besluit</label>
                    <select id="decision-{_esc(obj["object_id"])}" name="decision">
                      <option value="approve"{approve_disabled}>Goedkeuren</option>
                      <option value="revise">Revisie vragen</option>
                      <option value="reject">Afwijzen</option>
                    </select>
                    <label for="comment-{_esc(obj["object_id"])}">Toelichting</label>
                    <textarea id="comment-{_esc(obj["object_id"])}" name="comment"></textarea>
                    <label for="correction-{_esc(obj["object_id"])}">Voorgestelde correctie</label>
                    <textarea id="correction-{_esc(obj["object_id"])}" name="proposed_correction"></textarea>
                    <button class="btn-primary" type="submit">Review vastleggen</button>
                  </form>
                  </section>
                  {passage_html}
                </article>
                """
        empty = '<p class="muted">Nog geen documenten om te reviewen.</p>' if not envelopes else ""
        return _page(
            f"""
            {_nav(account, "review", _counts(account))}
            <section class="room">
              <h1>Review</h1>
              <p class="lead">Beoordeel de objecten van een ingeleverd document. Keur goed, vraag revisie, of wijs af.</p>
              <p class="next">Een reject of correctie maakt een nieuwe objectversie of blokkeert de oude. De uploader mag niet de enige vereiste reviewer zijn.</p>
              {picker}
              {"".join(cards) if not chosen else ""}
              {objects_html or empty}
            </section>
            {_help()}
            """
        )

    @app.get("/review/bronpassage", response_class=HTMLResponse)
    def review_bronpassage(request: Request, document: str = "", object: str = "") -> str:
        account = _require(request)
        chosen = document.strip()
        object_id = object.strip()
        if not chosen or not object_id:
            raise ConsoleError("unknown_object")
        opened = state.open_source_passage(snapshot_id=chosen, object_id=object_id)
        return _page(
            f"""
            {_nav(account, "review", _counts(account))}
            <section class="room">
              <h1>Bronpassage</h1>
              <p class="lead">Open de exacte plaats in het geüploade origineel bij dit kennisobject.</p>
              <article class="object">
                <pre>{_esc(opened.get("passage") or "")}</pre>
              </article>
              <p><a class="btn-secondary" href="/review?document={_esc(chosen)}">Terug naar review</a></p>
            </section>
            {_help()}
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
        confirmed_object_type: str = Form(""),
    ) -> RedirectResponse:
        account = _require(request)
        state.review_object(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            decision=decision,
            comment=comment,
            proposed_correction=proposed_correction,
            confirmed_object_type=confirmed_object_type.strip() or None,
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
        return RedirectResponse(f"/review?document={snapshot_id}", status_code=303)

    @app.post("/review/relations")
    def review_relations_post(
        request: Request,
        snapshot_id: str = Form(...),
        object_id: str = Form(...),
        relation: list[str] = Form(default=[]),
    ) -> RedirectResponse:
        account = _require(request)
        raw = [relation] if isinstance(relation, str) else list(relation or [])
        rows = []
        for item in raw:
            rel_type, sep, target = item.partition(":")
            if not sep or not rel_type or not target:
                raise ConsoleError("unknown_relation_type")
            rows.append({"relation_type": rel_type, "target_object_id": target})
        state.confirm_relations(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            relations=rows,
        )
        return RedirectResponse(f"/review?document={snapshot_id}", status_code=303)

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
            blockers = considered.get("blockers") or []
            blocker_text = " ".join(BLOCKER_LABELS.get(code, code) for code in blockers) or "Geen extra blockers in deze kamer."
            rows.append(
                f"""
                <article class="doc-card">
                  {_document_card_heading({**envelope, "status": envelope["state"]})}
                  <div class="banner warn">{_esc(blocker_text)}</div>
                </article>
                """
            )
        return _page(
            f"""
            {_nav(account, "publish", _counts(account))}
            <section class="room">
              <h1>Publiceren</h1>
              <p class="lead">Publiceren is een apart geautoriseerd besluit over een gereviewd document.</p>
              <p class="next">Zonder duurzame, onwijzigbare opslag blijft publicatie geblokkeerd. Cutover wordt niet gefingeerd. Een telling van vastgelegde documenten is geen publicatie-autorisatie.</p>
              <div class="doc-list">{"".join(rows) or '<p class="muted">Nog geen documenten.</p>'}</div>
            </section>
            {_help()}
            """
        )

    @app.get("/accounts", response_class=HTMLResponse)
    def accounts_get(request: Request) -> str:
        account = _require(request)
        rows = []
        for row in sorted(state._accounts.values(), key=lambda item: item["username"]):
            public = state._public_account(row)
            role_boxes = "".join(
                f'<label class="check"><input type="checkbox" name="roles" value="{name}"'
                f'{" checked" if name in public["roles"] else ""}>{name}</label>'
                for name in ("researcher", "reviewer", "publisher")
            )
            role_form = ""
            if "publisher" in account["roles"]:
                role_form = f"""
                  <form method="post" action="/accounts/roles">
                    <input type="hidden" name="account_id" value="{_esc(public["account_id"])}">
                    <p>Rollen wijzigen</p>
                    {role_boxes}
                    <button class="btn-secondary" type="submit">Rollen wijzigen</button>
                  </form>
                """
            rows.append(
                f"""
                <article class="doc-card">
                  <p class="doc-title">{_esc(public["display_name"])}</p>
                  <p class="meta">
                    <span>gebruikersnaam <b>{_esc(public["username"])}</b></span>
                    <span>rollen <b>{", ".join(_esc(r) for r in public["roles"])}</b></span>
                  </p>
                  {role_form}
                </article>
                """
            )
        form = ""
        if "publisher" in account["roles"]:
            form = """
              <form method="post" action="/accounts">
                <div class="sections">
                  <div class="section">
                    <h3>Nieuwe gebruiker</h3>
                    <label for="username">Gebruikersnaam</label>
                    <input id="username" name="username" required>
                    <label for="display_name">Weergavenaam</label>
                    <input id="display_name" name="display_name" required>
                    <label for="password">Wachtwoord</label>
                    <input id="password" type="password" name="password" required>
                    <label for="roles">Rol</label>
                    <select id="roles" name="roles">
                      <option value="researcher">researcher</option>
                      <option value="reviewer">reviewer</option>
                      <option value="publisher">publisher</option>
                    </select>
                    <button class="btn-primary" type="submit">Gebruiker aanmaken</button>
                  </div>
                </div>
              </form>
            """
        return _page(
            f"""
            {_nav(account, "accounts", _counts(account))}
            <section class="room">
              <h1>Accounts</h1>
              <p class="lead">Beheer interne gebruikers. Alleen een publisher mag gebruikers aanmaken en rollen toewijzen.</p>
              <p class="next">Rollen blijven gesloten: researcher, reviewer, publisher. Geen open registratie. Geen gedeelde login.</p>
              {form}
              <div class="doc-list">{"".join(rows) or '<p class="muted">Nog geen accounts.</p>'}</div>
            </section>
            {_help()}
            """
        )

    @app.post("/accounts", response_class=HTMLResponse)
    def accounts_post(
        request: Request,
        username: str = Form(...),
        display_name: str = Form(...),
        password: str = Form(...),
        roles: str = Form(...),
    ) -> HTMLResponse:
        account = _require(request)
        state.create_managed_account(
            actor_id=account["account_id"],
            username=username,
            display_name=display_name,
            password=password,
            roles=[item.strip() for item in roles.split(",") if item.strip()],
        )
        return RedirectResponse("/accounts", status_code=303)

    @app.post("/accounts/roles")
    def accounts_roles_post(
        request: Request,
        account_id: str = Form(...),
        roles: list[str] = Form(default=[]),
    ) -> RedirectResponse:
        account = _require(request)
        chosen: list[str] = []
        if isinstance(roles, str):
            chosen = [roles]
        elif roles:
            chosen = list(roles)
        if not chosen:
            raise ConsoleError("unknown_role")
        state.assign_roles(
            actor_id=account["account_id"],
            account_id=account_id,
            roles=chosen,
        )
        return RedirectResponse("/accounts", status_code=303)

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




































