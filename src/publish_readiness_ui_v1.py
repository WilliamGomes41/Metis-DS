"""Publisher-facing presentation of the existing publication-readiness contract.

The readiness decision remains in the domain/backend layers. This module only
turns that decision into a server-side view model and replaces the legacy GET
``/publish`` presentation. The existing POST route remains untouched and
therefore re-checks all publication gates through ``publish()``.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError, PostgresCanonicalPublicationStore
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.document_status_v1 import derive_document_status

from src.operations_console_app import (
    BLOCKER_LABELS,
    COOKIE,
    ERROR_COPY,
    _document_card_heading,
    _esc,
    _nav,
    _page,
    _task_links,
)
from src.operations_console_v1 import ConsoleError, OperationsConsole

CURATION_BLOCKER_LABELS = {
    "review_work_incomplete": (
        "Nog niet alle voorgestelde passages hebben een definitief reviewbesluit."
    ),
    "source_passage_review_incomplete": (
        "Nog niet alle inhoudelijke bronpassages zijn definitief afgehandeld."
    ),
    "review_disposition_inconsistent": (
        "De reviewuitkomst en de vastgelegde passage-afhandeling zijn niet consistent."
    ),
}
REVIEW_RECOVERY_BLOCKERS = frozenset(
    {
        "review_work_incomplete",
        "source_passage_review_incomplete",
        "review_disposition_inconsistent",
        "object_tuple_required",
        "second_named_reviewer_required",
        "four_eyes_required",
        "prepublication_schema_invalid",
    }
)


def _blocker_message(code: str) -> str:
    return (
        CURATION_BLOCKER_LABELS.get(code)
        or BLOCKER_LABELS.get(code)
        or ERROR_COPY.get(code)
        or "Publiceren is nog niet beschikbaar. De verantwoordelijke beheerder moet deze blokkade onderzoeken."
    )


def _blocker_view(code: str, snapshot_id: str) -> dict[str, Any]:
    recovery_href = None
    recovery_label = None
    if code in REVIEW_RECOVERY_BLOCKERS:
        recovery_href = f"/review?document={quote(snapshot_id, safe='')}"
        recovery_label = "Open Review"
    return {
        "code": code,
        "message": _blocker_message(code),
        "recovery_href": recovery_href,
        "recovery_label": recovery_label,
    }


def publish_readiness_view(
    *,
    snapshot_id: str,
    envelope_state: str,
    considered: dict[str, Any],
) -> dict[str, Any]:
    """Build one auditable server-side model from the Slice 4 readiness result."""
    blocker_codes = list(considered.get("blockers") or [])
    curation_codes = list(considered.get("curation_blockers") or [])
    technical_codes = list(considered.get("technical_blockers") or [])

    # Graceful fail-closed fallback for an older/error result. Normal production
    # flow carries all Slice 4 fields and therefore never needs this fallback.
    if "technical_ready" not in considered:
        technical_codes = technical_codes or blocker_codes
    technical_ready = bool(considered.get("technical_ready", False))
    curation_ready = bool(considered.get("curation_ready", not curation_codes))
    publication_ready = bool(
        considered.get("publication_ready", considered.get("publish_allowed", False))
    )

    published = (
        str(considered.get("state") or envelope_state) == "published"
        or "already_published" in technical_codes
        or "already_published" in blocker_codes
    )
    if published:
        overall_state = "published"
    elif publication_ready:
        overall_state = "ready"
    else:
        overall_state = "blocked"

    return {
        "snapshot_id": snapshot_id,
        "overall_state": overall_state,
        "publication_ready": publication_ready and not published,
        "publish_form_allowed": publication_ready and not published,
        "publishable_object_count": int(considered.get("publishable_object_count") or 0),
        "blocker_codes": blocker_codes,
        "curation_ready": curation_ready,
        "curation_blocker_codes": curation_codes,
        "curation_blockers": [_blocker_view(code, snapshot_id) for code in curation_codes],
        "unresolved_review_object_count": int(
            considered.get("unresolved_review_object_count") or 0
        ),
        "unresolved_source_passage_count": int(
            considered.get("unresolved_source_passage_count") or 0
        ),
        "technical_ready": technical_ready,
        "technical_blocker_codes": technical_codes,
        "technical_blockers": [_blocker_view(code, snapshot_id) for code in technical_codes],
    }


def _blocker_list(items: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in items:
        recovery = ""
        if item.get("recovery_href"):
            recovery = (
                f' <a class="btn-secondary" href="{_esc(item["recovery_href"])}">'
                f'{_esc(item.get("recovery_label") or "Open")}</a>'
            )
        rows.append(
            f'<li data-blocker-code="{_esc(item["code"])}">'
            f'{_esc(item["message"])}{recovery}</li>'
        )
    return f'<ul class="stack">{"".join(rows)}</ul>' if rows else ""


def _render_publish_state(view: dict[str, Any]) -> str:
    historical = {
        "withdrawn": "Ingetrokken. Deze versie is niet beschikbaar via de API.",
        "superseded": "Vervangen door een opvolgende publicatie. Deze versie is historisch.",
        "inactive": "Historisch gepubliceerd. Deze versie is niet actief beschikbaar via de API.",
        "authority_unavailable": "De actuele publicatiestatus kon niet worden gelezen. Ververs deze pagina voordat je een actie uitvoert.",
    }
    if view["overall_state"] in historical:
        return (
            f'<div class="banner warn" data-publication-state="{_esc(view["overall_state"])}">'
            f'{_esc(historical[view["overall_state"]])}</div>'
        )
    if view["overall_state"] == "published":
        banner = (
            '<div class="banner ok" data-publication-state="published">'
            "Gepubliceerd.</div>"
        )
        if not view.get("withdraw_release_id"):
            return banner
        return banner + f'''
          <form method="post" action="/publish/withdraw" class="stack" data-withdraw-form>
            <input type="hidden" name="snapshot_id" value="{_esc(view['snapshot_id'])}">
            <input type="hidden" name="expected_release_id" value="{_esc(view['withdraw_release_id'])}">
            <label>Reden voor intrekking <textarea name="reason" required></textarea></label>
            <label class="check"><input type="checkbox" name="withdraw_confirmed" value="yes" required>
              Ik bevestig intrekking van deze publicatie. Een oudere versie wordt niet opnieuw actief.</label>
            <button type="submit" class="btn-secondary">Trek publicatie in</button>
          </form>
        '''

    if view["publish_form_allowed"]:
        count = int(view["publishable_object_count"])
        noun = "kennisobject" if count == 1 else "kennisobjecten"
        reviewed = "gereviewd" if count == 1 else "gereviewde"
        return f'''
          <div class="banner ok" data-publication-state="ready">Klaar voor publicatie: {count} {reviewed} {noun}. Review en technische controles zijn afgerond.</div>
          <form method="post" action="/publish" class="stack" data-publish-form>
            <input type="hidden" name="snapshot_id" value="{_esc(view['snapshot_id'])}">
            <label class="check"><input type="checkbox" name="publish_confirmed" value="yes" required>
              Ik bevestig publicatie van deze gereviewde kennisobjecten.</label>
            <button type="submit">Publiceer document</button>
          </form>
        '''

    sections: list[str] = []
    if not view["curation_ready"]:
        counts: list[str] = []
        unresolved_review = int(view["unresolved_review_object_count"])
        unresolved_source = int(view["unresolved_source_passage_count"])
        if unresolved_review:
            counts.append(
                f"Nog {unresolved_review} kandidaatobject(en) zonder definitief reviewbesluit."
            )
        if unresolved_source:
            counts.append(
                f"Nog {unresolved_source} inhoudelijke bronpassage(s) zonder definitieve afhandeling."
            )
        count_html = "".join(f'<p class="muted">{_esc(row)}</p>' for row in counts)
        sections.append(
            '<section class="section" data-readiness-category="curation">'
            "<h3>Review en inhoud</h3>"
            f"{count_html}{_blocker_list(view['curation_blockers'])}"
            "</section>"
        )

    if not view["technical_ready"]:
        review_blockers = [item for item in view["technical_blockers"] if item.get("recovery_href")]
        sections.append(
            '<section class="section" data-readiness-category="technical">'
            '<h3>Publicatie nog niet beschikbaar</h3>'
            + _blocker_list(review_blockers)
            + ('<p>De vereiste publicatiecontroles zijn niet afgerond. Technisch beheer moet de blokkade onderzoeken.</p>'
               if len(review_blockers) < len(view["technical_blockers"]) or not review_blockers else '')
            + '</section>'
        )

    return (
        '<div class="banner warn" data-publication-state="blocked">'
        "Publicatie is nog geblokkeerd. Rond onderstaande punten af.</div>"
        f'<div class="sections" data-publication-readiness>{"".join(sections)}</div>'
    )


def _publisher_account(console: OperationsConsole, request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE)
    try:
        account = console.session_account(token)
    except ConsoleError as exc:
        raise ConsoleError("not_authenticated") from exc
    if "publisher" not in (account.get("roles") or []):
        raise ConsoleError("publisher_role_required")
    return account


def _withdrawal_retry_form(snapshot_id: str, release_id: str, reason: str) -> str:
    return f'''
      <form method="post" action="/publish/withdraw">
        <input type="hidden" name="snapshot_id" value="{_esc(snapshot_id)}">
        <input type="hidden" name="expected_release_id" value="{_esc(release_id)}">
        <input type="hidden" name="reason" value="{_esc(reason)}">
        <input type="hidden" name="withdraw_confirmed" value="yes">
        <button type="submit">Controleer en voltooi dezelfde intrekking</button>
      </form>
    '''


def install_publish_readiness_ui(app: FastAPI, console: OperationsConsole) -> None:
    """Present readiness and explicit withdrawal; keep publication POST unchanged."""
    if getattr(app.state, "publish_readiness_ui_v1", False):
        return

    retained = []
    removed = 0
    for route in app.router.routes:
        methods = set(getattr(route, "methods", set()) or set())
        if getattr(route, "path", None) == "/publish" and "GET" in methods:
            removed += 1
            continue
        retained.append(route)
    if removed != 1:
        raise RuntimeError("publish_get_route_replacement_failed")
    app.router.routes[:] = retained

    @app.get("/publish", response_class=HTMLResponse)
    def publish_get(request: Request) -> str:
        account = _publisher_account(console, request)
        rows: list[str] = []
        for envelope in console.list_envelopes():
            try:
                considered = console.consider_publish(
                    actor_id=account["account_id"],
                    snapshot_id=envelope["snapshot_id"],
                )
            except ConsoleError as exc:
                considered = {
                    "state": envelope.get("state"),
                    "publish_allowed": False,
                    "publication_ready": False,
                    "technical_ready": False,
                    "technical_blockers": [exc.code],
                    "curation_ready": True,
                    "curation_blockers": [],
                    "blockers": [exc.code],
                    "publishable_object_count": 0,
                }
            view = publish_readiness_view(
                snapshot_id=str(envelope["snapshot_id"]),
                envelope_state=str(envelope.get("state") or ""),
                considered=considered,
            )
            if isinstance(console, DurablePublicationConsole) and isinstance(
                console.canonical_publication_store, PostgresCanonicalPublicationStore,
            ):
                try:
                    release = console.canonical_publication_store.release_for_snapshot(envelope["snapshot_id"])
                    if release:
                        lifecycle = console.document_release_serving_status(envelope["snapshot_id"])
                        if lifecycle["serving_status"] == "active":
                            view["overall_state"] = "published"
                            if release.get("logical_document_id"):
                                view["withdraw_release_id"] = release["release_id"]
                        else:
                            state = lifecycle["release_status"]
                            view["overall_state"] = state if state in {"withdrawn", "superseded"} else "inactive"
                except (ConsoleError, CanonicalPublicationStoreError):
                    view["overall_state"] = "authority_unavailable"
            display_status = {
                "published": "published", "withdrawn": "Ingetrokken", "superseded": "Vervangen",
                "inactive": "Niet actief", "authority_unavailable": "Publicatiestatus onbekend",
            }.get(view["overall_state"], derive_document_status(
                envelope_state="captured_not_published",
                readiness=considered,
            ))
            rows.append(
                f'''
                <article class="doc-card" data-publish-document="{_esc(envelope['snapshot_id'])}">
                  {_document_card_heading({**envelope, "status": display_status, "meaningful_status": display_status})}
                  {_render_publish_state(view)}
                </article>
                '''
            )

        success = ""
        if request.query_params.get("published") == "yes":
            success = (
                '<div class="banner ok">Publicatie voltooid.</div>'
            )
        return _page(
            f'''
            {_nav(account, "publish")}
            <section class="room">
              <h1>Publiceren</h1>
              {_task_links("publish")}
              {success}
              <div class="doc-list">{"".join(rows) or '<p class="muted">Nog geen documenten.</p>'}</div>
            </section>
            '''
        )

    @app.post("/publish/withdraw", response_class=HTMLResponse)
    def withdraw_post(
        request: Request,
        snapshot_id: str = Form(""),
        expected_release_id: str = Form(""),
        reason: str = Form(""),
        withdraw_confirmed: str = Form(""),
    ) -> HTMLResponse:
        account = _publisher_account(console, request)
        try:
            if withdraw_confirmed != "yes":
                raise ConsoleError("withdrawal_confirmation_required")
            if not isinstance(console, DurablePublicationConsole):
                raise ConsoleError("durable_publication_store_required")
            result = console.withdraw_document(
                actor_id=account["account_id"], snapshot_id=snapshot_id,
                expected_release_id=expected_release_id, reason=reason,
            )
        except ConsoleError as exc:
            messages = {
                "withdrawal_confirmation_required": "Bevestig expliciet welke publicatie je wilt intrekken.",
                "canonical_expected_release_required": "De te bevestigen publicatie ontbreekt. Open Publiceren opnieuw.",
                "canonical_expected_release_changed": "De publicatie is gewijzigd. Er is niets ingetrokken; open Publiceren opnieuw.",
                "canonical_withdrawal_reason_required": "Vul een reden voor intrekking in.",
                "canonical_postgres_write_failed": "De uitkomst kon niet worden bevestigd. Controleer de actuele status of herhaal dezelfde intrekking.",
            }
            uncertain = exc.code == "canonical_postgres_write_failed"
            title = "Uitkomst niet bevestigd" if uncertain else "Intrekking niet uitgevoerd"
            message = messages.get(exc.code, "Intrekking is niet beschikbaar. Controleer de publicatiestatus.")
            retry = _withdrawal_retry_form(snapshot_id, expected_release_id, reason) if uncertain else ""
            return HTMLResponse(_page(
                f'<section class="room"><h1>{title}</h1><p>{_esc(message)}</p>'
                f'{retry}<p><a href="/publish">Naar Publiceren</a></p></section>'
            ), status_code=503 if uncertain else 409 if exc.code == "canonical_expected_release_changed" else 400)
        pending = result["projection_status"] == "pending"
        detail = (
            "De intrekking is vastgelegd. De Console-weergave moet nog worden ververst; herhaal dezelfde intrekking om dit opnieuw te proberen."
            if pending else "Deze publicatie is ingetrokken. Een oudere versie is niet opnieuw actief gemaakt."
        )
        # No authority reads after commit: a follow-up read failure must never
        # turn a committed withdrawal into an apparent failed command.
        retry = _withdrawal_retry_form(snapshot_id, expected_release_id, reason) if pending else ""
        return HTMLResponse(_page(
            '<section class="room"><h1>Publicatie ingetrokken</h1>'
            f'<div class="banner ok" data-withdrawal-result="{_esc(result["projection_status"])}">{_esc(detail)}</div>'
            f'{retry}<p><a href="/publish">Naar Publiceren</a></p></section>'
        ))

    app.state.publish_readiness_ui_v1 = True
