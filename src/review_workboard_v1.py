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

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import src.operations_console_app as console_ui
from src.domain_dimensions_v1 import processing_issue_objects
from src.beslisboom_path_v1 import review_path_for_klasse
from src.document_status_ui_v1 import current_document_lifecycle_status
from src.operations_console_app import (
    COOKIE,
    REVIEW_TASKS,
    normalize_review_task,
    _esc,
    _nav,
    _page,
    _render_review_room,
    _review_is_final,
)
from src.operations_console_v1 import PRE_REVIEW_BLOCKED, ConsoleError, OperationsConsole, review_stacks, slow_review_duty
from src.proportionate_review_v1 import (
    ProportionateReviewConsole,
    normal_risk_batch_counts,
    normal_risk_batch_queue,
    regular_individual_review_queue,
)
from src.publication_readiness_v1 import source_passage_closure
from src.review_duty_v1 import review_duty_counts, reviewer_route_counts


_TASK_COPY = {
    "structure": ("Structuur beoordelen", "Controleer koppen en documentstructuur"),
    "contextual": (
        "In samenhang beoordelen",
        "Beoordeel passages die inhoudelijke of relationele context nodig hebben",
    ),
    "batch": (
        "Vergelijkbare passages beoordelen",
        "Beoordeel onafhankelijke vergelijkbare passages in overzichtelijke groepen",
    ),
    "second_review": (
        "Tweede beoordeling",
        "Beoordeel onafhankelijk exact dezelfde goedgekeurde objectversie",
    ),
    "repair": (
        "Technisch herstel nodig",
        "Controleer passages die Metis nog niet veilig als inhoudelijke review kan aanbieden",
    ),
    "disposition": (
        "Bronpassages afhandelen",
        "Rond nog open source-passage disposition af",
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


def _fallback_lifecycle_status() -> dict[str, str]:
    return {
        "workflow_status": "processing",
        "release_status": "none",
        "serving_status": "inactive",
        "presentation_status": "processing",
    }


def _lifecycle_for_work_item(
    console: OperationsConsole,
    snapshot_id: str,
) -> dict[str, str]:
    cached = current_document_lifecycle_status(snapshot_id)
    if cached is not None:
        return cached
    try:
        return dict(console.document_lifecycle_status(snapshot_id))  # type: ignore[attr-defined]
    except (AttributeError, ConsoleError):
        return _fallback_lifecycle_status()


def _work_item_from_counts(
    *,
    envelope: dict[str, Any],
    snapshot_id: str,
    lifecycle_status: dict[str, str],
    heading_pending: int,
    individual_pending: int,
    normal_passages: int,
    normal_batches: int,
    blocked_count: int,
    closure_gap_ids: list[str],
    closure_gap_count: int,
    source_passage_review_complete: bool,
    review_duties: int,
    first_review_duties: int,
    second_review_duties: int,
    structure_review_duties: int,
    contextual_review_duties: int,
    batch_review_duties: int,
    actionable_review_duties: int | None = None,
    waiting_for_reviewer_duties: int = 0,
    actionable_structure_duties: int | None = None,
    actionable_contextual_duties: int | None = None,
    actionable_batch_duties: int | None = None,
    actionable_second_review_duties: int = 0,
) -> dict[str, Any]:
    remaining = review_duties

    effective_actionable = (
        review_duties
        if actionable_review_duties is None
        else actionable_review_duties
    )
    task_counts = (
        ("structure", structure_review_duties if actionable_structure_duties is None else actionable_structure_duties),
        ("contextual", contextual_review_duties if actionable_contextual_duties is None else actionable_contextual_duties),
        ("batch", batch_review_duties if actionable_batch_duties is None else actionable_batch_duties),
        ("second_review", actionable_second_review_duties),
    )
    next_task = next((task for task, pending in task_counts if pending), "")
    if not next_task and closure_gap_count:
        next_task = "disposition"
    if not next_task and blocked_count:
        next_task = "repair"

    meaningful_status = str(lifecycle_status["presentation_status"])
    if lifecycle_status["workflow_status"] == "closed":
        # Historical release truth wins over stale reviewer rows. Repair 2/2b
        # makes this WorkingRevision immutable, so the workboard must not offer
        # a continuation into review even if legacy rows remain unresolved.
        work_state = "complete"
        next_task = ""
    elif effective_actionable:
        work_state = "review"
    elif review_duties and waiting_for_reviewer_duties:
        work_state = "waiting_for_reviewer"
    elif closure_gap_count:
        work_state = "disposition"
    elif blocked_count:
        work_state = "technical_repair"
    elif meaningful_status == "blocked":
        work_state = "publication_blocked"
    else:
        work_state = "complete"

    next_title, next_description = _TASK_COPY.get(next_task, ("", ""))
    if next_task == "disposition" and closure_gap_ids:
        next_href = (
            f"/review?document={quote(snapshot_id, safe='')}"
            f"&object={quote(closure_gap_ids[0], safe='')}"
        )
    else:
        next_href = (
            f"/review?document={quote(snapshot_id, safe='')}&task={quote(next_task, safe='')}"
            if next_task
            else ""
        )

    return {
        "snapshot_id": snapshot_id,
        "envelope": envelope,
        "lifecycle_status": lifecycle_status,
        "meaningful_status": meaningful_status,
        "work_state": work_state,
        "remaining_review_items": remaining,
        "review_duties": review_duties,
        "first_review_duties": first_review_duties,
        "second_review_duties": second_review_duties,
        "structure_review_duties": structure_review_duties,
        "contextual_review_duties": contextual_review_duties,
        "batch_review_duties": batch_review_duties,
        "actionable_review_duties": (
            review_duties
            if actionable_review_duties is None
            else actionable_review_duties
        ),
        "waiting_for_reviewer_duties": waiting_for_reviewer_duties,
        "actionable_structure_duties": (
            structure_review_duties
            if actionable_structure_duties is None
            else actionable_structure_duties
        ),
        "actionable_contextual_duties": (
            contextual_review_duties
            if actionable_contextual_duties is None
            else actionable_contextual_duties
        ),
        "actionable_batch_duties": (
            batch_review_duties
            if actionable_batch_duties is None
            else actionable_batch_duties
        ),
        "actionable_second_review_duties": actionable_second_review_duties,
        "disposition_duties": closure_gap_count,
        "repair_duties": blocked_count,
        "heading_pending": heading_pending,
        "individual_pending": individual_pending,
        "normal_passages": normal_passages,
        "normal_batches": normal_batches,
        "blocked_count": blocked_count,
        "closure_gap_ids": closure_gap_ids,
        "closure_gap_count": closure_gap_count,
        "source_passage_review_complete": source_passage_review_complete,
        "next_task": next_task,
        "next_title": next_title,
        "next_description": next_description,
        "next_href": next_href,
    }


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
    if str(envelope.get("publication_eligibility") or "") == PRE_REVIEW_BLOCKED:
        return None

    snapshot_id = str(envelope.get("snapshot_id") or "")
    if not snapshot_id:
        return None

    objects = console.snapshot_objects(snapshot_id)
    closure = source_passage_closure(objects)
    unresolved_closure_ids = list(closure["unresolved_source_passage_ids"])
    unresolved_closure_set = set(unresolved_closure_ids)

    review_path = review_path_for_klasse(str(envelope.get("class") or ""))
    headings, _ = review_stacks(objects, review_path=review_path)
    open_headings = [row for row in headings if not _review_is_final(row)]
    heading_pending = len(open_headings)

    duty = slow_review_duty(objects, review_path=review_path)
    regular_individual = (
        regular_individual_review_queue(objects, review_path=review_path)
        if review_path != "boom"
        else []
    )
    individual = [*duty, *regular_individual]
    open_individual = [row for row in individual if not _review_is_final(row)]
    individual_pending = len(open_individual)

    normal_rows: list[dict[str, Any]] = []
    normal_passages = 0
    normal_batches = 0
    if isinstance(console, ProportionateReviewConsole):
        normal_rows = normal_risk_batch_queue(objects, review_path=review_path)
        normal_passages, normal_batches = normal_risk_batch_counts(
            objects,
            review_path=review_path,
        )

    blocked = (
        [
            row
            for row in processing_issue_objects(objects)
            if str(row.get("object_id") or "") in unresolved_closure_set
        ]
        if review_path != "boom"
        else []
    )
    blocked_count = len(blocked)

    represented_ids = {
        str(row.get("object_id") or "")
        for row in [*open_individual, *normal_rows, *blocked]
        if str(row.get("object_id") or "")
    }
    closure_gap_ids = [
        object_id
        for object_id in unresolved_closure_ids
        if object_id not in represented_ids
    ]

    bindings = console.object_review_bindings(snapshot_id)
    duty_counts = review_duty_counts(
        objects,
        review_path=review_path,
        bindings=bindings,
    )
    route_counts = reviewer_route_counts(
        objects,
        review_path=review_path,
        reviewer_id=account_id,
        bindings=bindings,
    )

    return _work_item_from_counts(
        envelope=envelope,
        snapshot_id=snapshot_id,
        lifecycle_status=_lifecycle_for_work_item(console, snapshot_id),
        heading_pending=heading_pending,
        individual_pending=individual_pending,
        normal_passages=normal_passages,
        normal_batches=normal_batches,
        blocked_count=blocked_count,
        closure_gap_ids=closure_gap_ids,
        closure_gap_count=len(closure_gap_ids),
        source_passage_review_complete=bool(closure["source_passage_review_complete"]),
        **duty_counts,
        **route_counts,
    )


def review_workboard_items(
    console: OperationsConsole,
    *,
    account: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return only documents assigned to the current reviewer, in store order."""
    account_id = str(account.get("account_id") or "")
    summary_reader = getattr(console, "review_workboard_summaries", None)
    if account_id and callable(summary_reader):
        summaries = summary_reader(account_id)
        items: list[dict[str, Any]] = []
        for snapshot_id, summary in summaries.items():
            envelope = dict(summary["envelope"])
            if str(envelope.get("publication_eligibility") or "") == PRE_REVIEW_BLOCKED:
                continue
            closure_gap_count = int(summary.get("closure_gap_count") or 0)
            closure_gap_first = str(summary.get("closure_gap_first") or "")
            closure_gap_ids = [closure_gap_first] if closure_gap_count and closure_gap_first else []
            items.append(
                _work_item_from_counts(
                    envelope=envelope,
                    snapshot_id=snapshot_id,
                    lifecycle_status=_lifecycle_for_work_item(console, snapshot_id),
                    heading_pending=int(summary.get("heading_pending") or 0),
                    individual_pending=int(summary.get("individual_pending") or 0),
                    normal_passages=actionable_batch,
                    normal_batches=int(summary.get("normal_batches") or 0),
                    blocked_count=int(summary.get("blocked_count") or 0),
                    closure_gap_ids=closure_gap_ids,
                    closure_gap_count=closure_gap_count,
                    source_passage_review_complete=bool(
                        summary.get("source_passage_review_complete")
                    ),
                    review_duties=(
                        int(summary.get("review_duties") or 0)
                        if "review_duties" in summary
                        else int(summary.get("heading_pending") or 0)
                        + int(summary.get("individual_pending") or 0)
                        + int(summary.get("normal_passages") or 0)
                    ),
                    first_review_duties=(
                        int(summary.get("first_review_duties") or 0)
                        if "first_review_duties" in summary
                        else int(summary.get("heading_pending") or 0)
                        + int(summary.get("individual_pending") or 0)
                        + int(summary.get("normal_passages") or 0)
                    ),
                    second_review_duties=int(summary.get("second_review_duties") or 0),
                    structure_review_duties=(
                        int(summary.get("structure_review_duties") or 0)
                        if "structure_review_duties" in summary
                        else int(summary.get("heading_pending") or 0)
                    ),
                    contextual_review_duties=(
                        int(summary.get("contextual_review_duties") or 0)
                        if "contextual_review_duties" in summary
                        else int(summary.get("individual_pending") or 0)
                    ),
                    batch_review_duties=(
                        int(summary.get("batch_review_duties") or 0)
                        if "batch_review_duties" in summary
                        else int(summary.get("normal_passages") or 0)
                    ),
                    actionable_review_duties=(
                        int(summary.get("actionable_review_duties") or 0)
                        if "actionable_review_duties" in summary
                        else None
                    ),
                    waiting_for_reviewer_duties=int(
                        summary.get("waiting_for_reviewer_duties") or 0
                    ),
                    actionable_structure_duties=(
                        int(summary.get("actionable_structure_duties") or 0)
                        if "actionable_structure_duties" in summary
                        else None
                    ),
                    actionable_contextual_duties=(
                        int(summary.get("actionable_contextual_duties") or 0)
                        if "actionable_contextual_duties" in summary
                        else None
                    ),
                    actionable_batch_duties=(
                        int(summary.get("actionable_batch_duties") or 0)
                        if "actionable_batch_duties" in summary
                        else None
                    ),
                    actionable_second_review_duties=int(
                        summary.get("actionable_second_review_duties") or 0
                    ),
                )
            )
        return items

    return [
        item
        for envelope in console.list_envelopes()
        if (item := review_work_item(console, account=account, envelope=envelope)) is not None
    ]


def _work_summary(item: dict[str, Any]) -> str:
    state = item["work_state"]
    review_duties = int(item.get("review_duties") or 0)
    actionable = int(item.get("actionable_review_duties") or 0)
    waiting = int(item.get("waiting_for_reviewer_duties") or 0)
    if state == "review":
        return (
            f"{review_duties} inhoudelijke beoordeling"
            f"{'' if review_duties == 1 else 'en'} open; {actionable} voor jou uitvoerbaar."
        )
    if state == "waiting_for_reviewer":
        return (
            f"{waiting} beoordeling"
            f"{'' if waiting == 1 else 'en'} wacht op een andere onafhankelijke reviewer."
        )
    if state == "disposition":
        count = int(item.get("disposition_duties") or 0)
        return f"Geen inhoudelijke review open; {count} bronpassage{' ' if count == 1 else 's '}nog afhandelen."
    if state == "technical_repair":
        blocked = int(item.get("blocked_count") or 0)
        noun = "passage vereist" if blocked == 1 else "passages vereisen"
        return f"Geen inhoudelijke review open; {blocked} {noun} technisch herstel."
    if state == "publication_blocked":
        return "Review afgerond; publicatie is technisch geblokkeerd."
    if item["meaningful_status"] == "published":
        return "Review afgerond; deze release wordt actief gepubliceerd."
    if item["meaningful_status"] == "published_inactive":
        return "Review afgerond; deze release is gepubliceerd maar niet actief."
    if item["meaningful_status"] == "superseded":
        return "Review afgerond; deze release is vervangen door nieuwere publicatie."
    if item["meaningful_status"] == "withdrawn":
        return "Review afgerond; deze release is ingetrokken."
    if item["meaningful_status"] == "ready_for_publication":
        return "Review afgerond; document is klaar voor publicatie."
    return "Geen open reviewplicht."


def _work_queue_link(snapshot_id: str, task: str, label: str) -> str:
    """Link one visible non-empty work bucket to its existing Review task."""
    snap = quote(snapshot_id, safe="")
    safe_task = quote(task, safe="")
    return (
        f'<a class="review-work-queue-link" data-work-queue="{_esc(task)}" '
        f'href="/review?document={snap}&amp;task={safe_task}">{_esc(label)}</a>'
    )


def _workboard_card(item: dict[str, Any]) -> str:
    envelope = item["envelope"]
    lifecycle = item["lifecycle_status"]
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
    if lifecycle["workflow_status"] != "closed":
        snapshot_id = str(item["snapshot_id"])
        for task, count, label in (
            ("structure", int(item.get("actionable_structure_duties") or 0), "structuur"),
            ("contextual", int(item.get("actionable_contextual_duties") or 0), "in samenhang"),
            ("batch", int(item.get("actionable_batch_duties") or 0), "vergelijkbaar"),
            ("second_review", int(item.get("actionable_second_review_duties") or 0), "tweede beoordeling"),
        ):
            if count:
                detail_parts.append(_work_queue_link(snapshot_id, task, f"{count} {label}"))
        if item.get("waiting_for_reviewer_duties"):
            detail_parts.append(
                _esc(f"{item['waiting_for_reviewer_duties']} wacht op andere reviewer")
            )
        if item["closure_gap_count"]:
            detail_parts.append(_esc(f"{item['closure_gap_count']} bronpassage disposition"))
        if item["blocked_count"]:
            detail_parts.append(
                _work_queue_link(
                    snapshot_id,
                    "repair",
                    f"{item['blocked_count']} technisch herstel",
                )
            )
    detail_html = (
        f'<p class="muted review-work-queues">{" · ".join(detail_parts)}</p>'
        if detail_parts
        else ""
    )

    return f'''
      <article class="doc-card" data-workboard-document="{_esc(item['snapshot_id'])}" data-workboard-state="{_esc(item['work_state'])}" data-workflow-status="{_esc(lifecycle['workflow_status'])}" data-release-status="{_esc(lifecycle['release_status'])}" data-serving-status="{_esc(lifecycle['serving_status'])}">
        {console_ui._document_card_heading({**envelope, "meaningful_status": item["meaningful_status"]})}
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
    waiting = [row for row in items if row["work_state"] == "waiting_for_reviewer"]
    disposition = [row for row in items if row["work_state"] == "disposition"]
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
    if waiting:
        sections.append(
            '<section class="review-workboard-section" aria-labelledby="review-wait-title">'
            f'<h2 id="review-wait-title">Wacht op andere reviewer ({len(waiting)})</h2>'
            '<p>Deze documenten hebben nog reviewplicht, maar de open tweede beoordeling moet door een andere reviewer worden uitgevoerd.</p>'
            f'<div class="doc-list">{"".join(_workboard_card(row) for row in waiting)}</div>'
            '</section>'
        )
    if disposition:
        sections.append(
            '<section class="review-workboard-section" aria-labelledby="review-disposition-title">'
            f'<h2 id="review-disposition-title">Bronpassages afhandelen ({len(disposition)})</h2>'
            f'<div class="doc-list">{"".join(_workboard_card(row) for row in disposition)}</div>'
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
    elif not active and not waiting and not disposition and not technical and not done:
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
        '''
    )


def _projected_document_dashboard(
    console: OperationsConsole,
    *,
    account: dict[str, Any],
    snapshot_id: str,
    counts: dict[str, int],
) -> str | None:
    """Render the default selected-document dashboard without materializing objects."""
    summary_reader = getattr(console, "review_workboard_summaries", None)
    if not callable(summary_reader):
        return None
    account_id = str(account.get("account_id") or "")
    if not account_id:
        return None
    summaries = summary_reader(account_id, snapshot_id)
    summary = summaries.get(snapshot_id)
    if not isinstance(summary, dict):
        return None
    envelope = summary.get("envelope")
    if not isinstance(envelope, dict):
        return None

    progress_total = int(summary.get("progress_total") or 0)
    progress_done = int(summary.get("progress_done") or 0)
    progress = {
        "total": progress_total,
        "done": progress_done,
        "open": max(progress_total - progress_done, 0),
        "approved": int(summary.get("progress_approved") or 0),
        "rejected": int(summary.get("progress_rejected") or 0),
        "not_included": int(summary.get("progress_not_included") or 0),
        "context": int(summary.get("progress_context") or 0),
        "support": int(summary.get("progress_support") or 0),
        "superseded": int(summary.get("progress_superseded") or 0),
        "revised": int(summary.get("progress_revised") or 0),
    }
    actionable_structure = (
        int(summary.get("actionable_structure_duties") or 0)
        if "actionable_structure_duties" in summary
        else int(summary.get("heading_pending") or 0)
    )
    actionable_contextual = (
        int(summary.get("actionable_contextual_duties") or 0)
        if "actionable_contextual_duties" in summary
        else int(summary.get("individual_pending") or 0)
    )
    actionable_batch = (
        int(summary.get("actionable_batch_duties") or 0)
        if "actionable_batch_duties" in summary
        else int(summary.get("normal_passages") or 0)
    )
    actionable_second = int(summary.get("actionable_second_review_duties") or 0)
    dashboard = console_ui._review_task_dashboard(
        snapshot_id,
        koppen=[],
        individual=[],
        normal_passages=int(summary.get("actionable_batch_duties") or 0),
        normal_batches=int(summary.get("normal_batches") or 0),
        blocked_count=int(summary.get("blocked_count") or 0),
        progress=progress,
        heading_pending_override=actionable_structure,
        heading_total_override=int(summary.get("heading_total") or 0),
        individual_pending_override=actionable_contextual,
        individual_total_override=int(summary.get("contextual_review_duties") or 0),
        second_review_pending=actionable_second,
    )
    picker = f"""
      <div class="review-document-context">
        <span>Document</span>
        <b>{_esc(envelope.get("title") or "")}</b>
        <span>versie {_esc(envelope.get("version") or "")}</span>
        <span>onderwerp {_esc(envelope.get("family") or "")}</span>
        <span>klasse {_esc(envelope.get("class") or "")}</span>
        <a href="/review">Ander document kiezen</a>
      </div>
    """
    heading = console_ui._document_card_heading(
        {**envelope, "status": envelope.get("state") or ""}
    )
    return _page(
        f"""
        {_nav(account, "review", counts)}
        <section class="room">
          <h1>Review</h1>
          <p class="lead">Beoordeel passages stap voor stap, met de oorspronkelijke bron als uitgangspunt.</p>
          {picker}
          <div class="doc-card">{heading}</div>
          {dashboard}
        </section>
        """
    )


def install_review_workboard(app: FastAPI, console: OperationsConsole) -> None:
    """Install the Review workboard and its post-heading navigation."""
    if getattr(app.state, "review_workboard_v1", False):
        return

    retained = []
    removed_get = 0
    headings_post_route = None
    for route in app.router.routes:
        methods = set(getattr(route, "methods", set()) or set())
        path = getattr(route, "path", None)
        if path == "/review" and "GET" in methods:
            removed_get += 1
            continue
        if path == "/review/headings/batch-confirm" and "POST" in methods:
            if headings_post_route is not None:
                raise RuntimeError("review_headings_route_replacement_ambiguous")
            headings_post_route = route
            continue
        retained.append(route)
    if removed_get != 1:
        raise RuntimeError("review_get_route_replacement_failed")
    if headings_post_route is None:
        raise RuntimeError("review_headings_route_replacement_failed")
    original_headings_batch_confirm = headings_post_route.endpoint
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
            counts = console.waiting_task_counts(str(account["account_id"]))
            chosen_task = normalize_review_task(task)
            if not object.strip() and not chosen_task:
                projected = _projected_document_dashboard(
                    console,
                    account=account,
                    snapshot_id=chosen,
                    counts=counts,
                )
                if projected is not None:
                    return projected
            return _render_review_room(
                console,
                account,
                html.escape(document, quote=True),
                html.escape(object, quote=True),
                task=html.escape(chosen_task, quote=True),
                counts=counts,
            )
        return _workboard_page(console, account=account)

    @app.post("/review/headings/batch-confirm")
    def review_headings_batch_confirm(
        request: Request,
        snapshot_id: str = Form(...),
        object_ids: list[str] = Form(default=[]),
        snapshot_revision: str = Form(""),
    ) -> Any:
        response = original_headings_batch_confirm(
            request=request,
            snapshot_id=snapshot_id,
            object_ids=object_ids,
            snapshot_revision=snapshot_revision,
        )
        if isinstance(response, RedirectResponse) and response.status_code == 303:
            envelope = console._envelope(snapshot_id)
            item = review_work_item(
                console,
                account=_current_account(console, request),
                envelope=envelope,
            )
            if item and int(item.get("actionable_structure_duties") or 0):
                return RedirectResponse(
                    console_ui._review_location(
                        console,
                        snapshot_id,
                        task="structure",
                    ),
                    status_code=303,
                )
            return RedirectResponse(
                console_ui._review_location(console, snapshot_id),
                status_code=303,
            )
        return response

    app.state.review_workboard_v1 = True
