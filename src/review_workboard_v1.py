"""Reviewer workboard over the existing review queues.

This slice adds no review state, priority store, assignment model or mutation.
It only summarizes the queues already used by the in-document Review dashboard
and replaces the empty `/review` landing page. Selecting a document continues
to use the existing review room unchanged.
"""
from __future__ import annotations

import html
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

import src.operations_console_app as console_ui
from src.admission_gate_v1 import blocked_audit_lane
from src.beslisboom_path_v1 import review_path_for_klasse
from src.operations_console_app import (
    COOKIE,
    REVIEW_TASKS,
    _esc,
    _help,
    _nav,
    _page,
    _render_review_room,
    _review_is_final,
)
from src.operations_console_v1 import ConsoleError, OperationsConsole, review_stacks, slow_review_duty
from src.proportionate_review_v1 import (
    ProportionateReviewConsole,
    normal_risk_batch_counts,
    regular_individual_review_queue,
)


_TASK_COPY = {
    "headings": ("Koppen controleren", "Controleer de indeling van het document"),
    "individual": (
        "Belangrijke passages beoordelen",
        "Beoordeel advies, voorwaarden, uitzonderingen en passages die extra aandacht vragen",
    ),
    "together": (
        "Vergelijkbare passages samen beoordelen",
        "Beoordeel passages uit hetzelfde brononderdeel in overzichtelijke groepen",
    ),
    "control": (
        "Technisch herstel nodig",
        "Controleer passages die Metis nog niet veilig als gewone reviewtaak kan aanbieden",
    ),
}


def _current_account(console: OperationsConsole, request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE)
    try:
        return console.session_account(token)
    except ConsoleError as exc:
        raise ConsoleError("not_authenticated") from exc


def _assigned_to_reviewer(envelope: dict[str, Any], account_id: str) -> bool:
    return account_id in set(envelope.get("named_reviewers") or [])


def _pending_count(rows: list[dict[str, Any]]) -> int:
    return sum(not _review_is_final(row) for row in rows)


def review_work_item(
    console: OperationsConsole,
    *,
    account: dict[str, Any],
    envelope: dict[str, Any],
) -> dict[str, Any] | None:
    """Summarize one assigned document using the existing Review queues."""
    account_id = str(account.get("account_id") or "")
    if not account_id or not _assigned_to_reviewer(envelope, account_id):
        return None

    snapshot_id = str(envelope.get("snapshot_id") or "")
    if not snapshot_id:
        return None

    objects = console.snapshot_objects(snapshot_id)
    review_path = review_path_for_klasse(str(envelope.get("class") or ""))
    headings, _ = review_stacks(objects, review_path=review_path)
    heading_pending = _pending_count(headings)

    duty = slow_review_duty(objects, review_path=review_path)
    regular_individual = (
        regular_individual_review_queue(objects, review_path=review_path)
        if review_path != "boom"
        else []
    )
    individual = [*duty, *regular_individual]
    individual_pending = _pending_count(individual)

    normal_passages = 0
    normal_batches = 0
    if isinstance(console, ProportionateReviewConsole):
        normal_passages, normal_batches = normal_risk_batch_counts(
            objects,
            review_path=review_path,
        )

    blocked_count = len(blocked_audit_lane(objects)) if review_path != "boom" else 0
    remaining = heading_pending + individual_pending + normal_passages

    task_counts = (
        ("headings", heading_pending),
        ("individual", individual_pending),
        ("together", normal_passages),
    )
    next_task = next((task for task, pending in task_counts if pending), "")
    if not next_task and blocked_count:
        next_task = "control"

    try:
        meaningful_status = str(console.document_status(snapshot_id))  # type: ignore[attr-defined]
    except (AttributeError, ConsoleError):
        meaningful_status = "processing"

    if remaining:
        work_state = "review"
    elif blocked_count:
        work_state = "technical_repair"
    elif meaningful_status == "blocked":
        work_state = "publication_blocked"
    else:
        work_state = "complete"

    next_title, next_description = _TASK_COPY.get(next_task, ("", ""))
    next_href = (
        f"/review?document={quote(snapshot_id, safe='')}&task={quote(next_task, safe='')}"
        if next_task
        else ""
    )

    return {
        "snapshot_id": snapshot_id,
        "envelope": envelope,
        "meaningful_status": meaningful_status,
        "work_state": work_state,
        "remaining_review_items": remaining,
        "heading_pending": heading_pending,
        "individual_pending": individual_pending,
        "normal_passages": normal_passages,
        "normal_batches": normal_batches,
        "blocked_count": blocked_count,
        "next_task": next_task,
        "next_title": next_title,
        "next_description": next_description,
        "next_href": next_href,
    }


def review_workboard_items(
    console: OperationsConsole,
    *,
    account: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return only documents assigned to the current reviewer, in store order."""
    return [
        item
        for envelope in console.list_envelopes()
        if (item := review_work_item(console, account=account, envelope=envelope)) is not None
    ]


def _work_summary(item: dict[str, Any]) -> str:
    state = item["work_state"]
    remaining = int(item["remaining_review_items"])
    blocked = int(item["blocked_count"])
    if state == "review":
        noun = "reviewtaak" if remaining == 1 else "reviewtaken"
        return f"Nog {remaining} {noun}."
    if state == "technical_repair":
        noun = "passage vereist" if blocked == 1 else "passages vereisen"
        return f"Geen gewone reviewtaak; {blocked} {noun} technisch herstel."
    if state == "publication_blocked":
        return "Review afgerond; publicatie is technisch geblokkeerd."
    if item["meaningful_status"] == "published":
        return "Review afgerond; document is gepubliceerd."
    if item["meaningful_status"] == "ready_for_publication":
        return "Review afgerond; document is klaar voor publicatie."
    return "Geen open reviewtaak."


def _workboard_card(item: dict[str, Any]) -> str:
    envelope = item["envelope"]
    next_step = ""
    if item["next_task"]:
        next_step = f'''
          <div class="review-next-step" data-next-task="{_esc(item['next_task'])}">
            <p class="eyebrow">Volgende stap</p>
            <h3>{_esc(item['next_title'])}</h3>
            <p>{_esc(item['next_description'])}.</p>
            <a class="btn-primary" href="{_esc(item['next_href'])}">Ga verder</a>
          </div>
        '''
    else:
        next_step = (
            '<p class="muted" data-next-task="none">Voor dit document is geen reviewactie nodig.</p>'
        )

    detail_parts: list[str] = []
    if item["heading_pending"]:
        detail_parts.append(f"{item['heading_pending']} kop/pad")
    if item["individual_pending"]:
        detail_parts.append(f"{item['individual_pending']} individueel")
    if item["normal_passages"]:
        detail_parts.append(
            f"{item['normal_passages']} samen in {item['normal_batches']} groep(en)"
        )
    if item["blocked_count"]:
        detail_parts.append(f"{item['blocked_count']} technisch herstel")
    details = " · ".join(detail_parts)
    detail_html = f'<p class="muted">{_esc(details)}</p>' if details else ""

    return f'''
      <article class="doc-card" data-workboard-document="{_esc(item['snapshot_id'])}" data-workboard-state="{_esc(item['work_state'])}">
        {console_ui._document_card_heading({**envelope, "status": envelope.get("state", "")})}
        <p class="lead">{_esc(_work_summary(item))}</p>
        {detail_html}
        {next_step}
      </article>
    '''


def _workboard_page(
    console: OperationsConsole,
    *,
    account: dict[str, Any],
) -> str:
    if "reviewer" not in set(account.get("roles") or []):
        raise ConsoleError("reviewer_role_required")

    items = review_workboard_items(console, account=account)
    active = [row for row in items if row["work_state"] == "review"]
    technical = [row for row in items if row["work_state"] == "technical_repair"]
    done = [
        row
        for row in items
        if row["work_state"] in {"publication_blocked", "complete"}
    ]

    sections: list[str] = []
    if active:
        sections.append(
            '<section class="review-workboard-section" aria-labelledby="review-work-title">'
            f'<h2 id="review-work-title">Nu te reviewen ({len(active)})</h2>'
            '<p>Ga verder met de eerstvolgende bestaande reviewtaak per document.</p>'
            f'<div class="doc-list">{"".join(_workboard_card(row) for row in active)}</div>'
            '</section>'
        )
    if technical:
        sections.append(
            '<section class="review-workboard-section" aria-labelledby="review-tech-title">'
            f'<h2 id="review-tech-title">Technisch herstel ({len(technical)})</h2>'
            '<p>Deze documenten hebben geen gewone inhoudelijke vervolgstap totdat het technische herstel is bekeken.</p>'
            f'<div class="doc-list">{"".join(_workboard_card(row) for row in technical)}</div>'
            '</section>'
        )
    if done:
        sections.append(
            '<details class="review-workboard-complete">'
            f'<summary>Geen reviewactie nodig ({len(done)})</summary>'
            f'<div class="doc-list">{"".join(_workboard_card(row) for row in done)}</div>'
            '</details>'
        )
    if not items:
        sections.append('<p class="muted">Geen aan jou toegewezen reviewdocumenten.</p>')
    elif not active and not technical and not done:
        sections.append('<p class="muted">Geen open reviewtaken.</p>')

    counts = console.waiting_task_counts(str(account["account_id"]))
    return _page(
        f'''
        {_nav(account, "review", counts)}
        <section class="room review-workboard" data-review-workboard>
          <h1>Review</h1>
          <p class="lead">Bekijk waar jouw reviewwerk staat en ga direct verder met de eerstvolgende taak.</p>
          {"".join(sections)}
        </section>
        {_help(room="review")}
        '''
    )


def install_review_workboard(app: FastAPI, console: OperationsConsole) -> None:
    """Replace only GET /review; all existing review mutations stay unchanged."""
    if getattr(app.state, "review_workboard_v1", False):
        return

    retained = []
    removed = 0
    for route in app.router.routes:
        methods = set(getattr(route, "methods", set()) or set())
        if getattr(route, "path", None) == "/review" and "GET" in methods:
            removed += 1
            continue
        retained.append(route)
    if removed != 1:
        raise RuntimeError("review_get_route_replacement_failed")
    app.router.routes[:] = retained

    @app.get("/review", response_class=HTMLResponse)
    def review_get(
        request: Request,
        document: str = "",
        object: str = "",
        task: str = "",
    ) -> str:
        account = _current_account(console, request)
        chosen = document.strip()
        if chosen:
            return _render_review_room(
                console,
                account,
                html.escape(document, quote=True),
                html.escape(object, quote=True),
                task=html.escape(task, quote=True) if task.strip() in REVIEW_TASKS else "",
                counts=console.waiting_task_counts(str(account["account_id"])),
            )
        return _workboard_page(console, account=account)

    app.state.review_workboard_v1 = True
