"""Direct reviewer workspace over the existing review queues.

The assigned-document projection supplies inline document choice and opens
available work directly. No review state, priority store or assignment model
is added; explicit task links continue to use the existing review room.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import src.operations_console_app as console_ui
from src.beslisboom_path_v1 import review_path_for_klasse
from src.four_eyes_v1 import is_forbidden_reviewer
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
    regular_individual_review_queue,
)
from src.publication_readiness_v1 import source_passage_closure, review_followup_queues
from src.review_duty_v1 import review_duty_counts, reviewer_route_counts
from src.review_interaction_v1 import _is_decision_event
from src.review_ledger import read_events


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
        "Passages corrigeren",
        "Controleer passages die Metis nog niet veilig als inhoudelijke review kan aanbieden",
    ),
    "disposition": (
        "Bronpassages afhandelen",
        "Bepaal wat met de nog open bronpassages moet gebeuren",
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
    except AttributeError:
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


@dataclass(frozen=True)
class ReviewWorkInputs:
    """Disposable, already authorized inputs for one read projection.

    Consumers must not mutate these call-local values. They are never reused by
    a command or retained between requests.
    """

    objects: list[dict[str, Any]]
    bindings: list[dict[str, Any]]
    lifecycle_status: dict[str, str]
    published: bool


def review_work_item(
    console: OperationsConsole,
    *,
    account: dict[str, Any],
    envelope: dict[str, Any],
    inputs: ReviewWorkInputs | None = None,
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

    objects = inputs.objects if inputs is not None else console.snapshot_objects(snapshot_id)
    closure = source_passage_closure(objects)

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

    normal_passages = 0
    normal_batches = 0
    if isinstance(console, ProportionateReviewConsole):
        normal_passages, normal_batches = normal_risk_batch_counts(
            objects,
            review_path=review_path,
        )

    bindings: list[dict[str, Any]] | None
    if inputs is not None:
        bindings = inputs.bindings
    elif not hasattr(console, "_bindings") and not hasattr(console, "workflow_review_store"):
        bindings = None
    else:
        try:
            bindings = console.object_review_bindings(snapshot_id)
        except AttributeError:
            bindings = None

    followups = review_followup_queues(objects, review_path=review_path, bindings=bindings)
    blocked_count = len(followups["repair"])
    closure_gap_ids = [str(obj["object_id"]) for obj in followups["disposition"]]

    duty_counts = review_duty_counts(
        objects,
        review_path=review_path,
        bindings=bindings,
    )
    if bindings is None:
        route_counts = {
            "actionable_review_duties": duty_counts["review_duties"],
            "waiting_for_reviewer_duties": 0,
            "actionable_structure_duties": duty_counts["structure_review_duties"],
            "actionable_contextual_duties": duty_counts["contextual_review_duties"],
            "actionable_batch_duties": duty_counts["batch_review_duties"],
            "actionable_second_review_duties": duty_counts["second_review_duties"],
        }
    else:
        route_counts = reviewer_route_counts(
            objects,
            review_path=review_path,
            reviewer_id=account_id,
            bindings=bindings,
        )

    item = _work_item_from_counts(
        envelope=envelope,
        snapshot_id=snapshot_id,
        lifecycle_status=(inputs.lifecycle_status if inputs is not None
                          else _lifecycle_for_work_item(console, snapshot_id)),
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
    item["progress"] = console_ui._review_progress_summary(objects)
    item["has_review_decision"] = any(
        str((obj.get("governance") or {}).get("validated_by") or "").strip()
        and not is_forbidden_reviewer(str(obj["governance"]["validated_by"]))
        and (obj.get("governance") or {}).get("review_snapshot_hash")
        for obj in objects
    )
    published = inputs.published if inputs is not None else (
        console.snapshot_is_published(snapshot_id) if "decision_graph" in envelope else False
    )
    if "decision_graph" in envelope and not published:
        from src.decision_graph_v1 import publication_issues, review_target
        graph_issues = publication_issues(envelope, objects)
        target = review_target(envelope["decision_graph"], objects, envelope["review_policy"])
        actor_confirmed = any(r["reviewer_id"] == account_id and r.get("target") == target
                              for r in envelope.get("decision_graph_reviews", []))
        if graph_issues == ["decision_graph_review_incomplete"] and actor_confirmed:
            item["work_state"] = "waiting_for_reviewer"
            item["next_href"] = ""
            item["next_title"] = "Wachten op vereiste mede-review"
        elif graph_issues:
            item["work_state"] = "review"
            item["next_href"] = f"/review/decision-graph?document={quote(snapshot_id, safe='')}"
            item["next_title"] = "Beslisroutes controleren"
    return item



def review_workboard_items(
    console: OperationsConsole,
    *,
    account: dict[str, Any],
    summaries: dict[str, dict[str, Any]] | None = None,
    lifecycle_statuses: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Return only documents assigned to the current reviewer, in store order."""
    account_id = str(account.get("account_id") or "")
    summary_reader = getattr(console, "review_workboard_summaries", None)
    if account_id and (summaries is not None or callable(summary_reader)):
        if summaries is None:
            summaries = summary_reader(account_id)
        items: list[dict[str, Any]] = []
        for snapshot_id, summary in summaries.items():
            envelope = {"snapshot_id": snapshot_id, **summary["envelope"]}
            if str(envelope.get("publication_eligibility") or "") == PRE_REVIEW_BLOCKED:
                continue
            if envelope.get("review_policy"):
                item = (summary["work_item"] if "work_item" in summary else
                        review_work_item(console, envelope=envelope, account=account))
                if item is not None:
                    items.append(item)
                continue
            closure_gap_count = int(summary.get("closure_gap_count") or 0)
            closure_gap_first = str(summary.get("closure_gap_first") or "")
            closure_gap_ids = [closure_gap_first] if closure_gap_count and closure_gap_first else []
            items.append(
                _work_item_from_counts(
                    envelope=envelope,
                    snapshot_id=snapshot_id,
                    lifecycle_status=(lifecycle_statuses[snapshot_id] if lifecycle_statuses is not None
                                      else _lifecycle_for_work_item(console, snapshot_id)),
                    heading_pending=int(summary.get("heading_pending") or 0),
                    individual_pending=int(summary.get("individual_pending") or 0),
                    normal_passages=int(summary.get("normal_passages") or 0),
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
            items[-1]["summary"] = summary
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
                _work_queue_link(snapshot_id, "waiting", f"{item['waiting_for_reviewer_duties']} wacht op andere reviewer")
            )
        if item["closure_gap_count"]:
            detail_parts.append(_work_queue_link(snapshot_id, "disposition", f"{item['closure_gap_count']} bronpassages afhandelen"))
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
    detail_html += (
        f'<p><a href="/review?document={_esc(item["snapshot_id"])}&amp;task=inventory">'
        'Alle passages en hun afhandeling bekijken</a></p>'
    )

    return f'''
      <article class="doc-card{' review-document-card' if item['work_state'] == 'review' else ''}" data-workboard-document="{_esc(item['snapshot_id'])}" data-workboard-state="{_esc(item['work_state'])}" data-workflow-status="{_esc(lifecycle['workflow_status'])}" data-release-status="{_esc(lifecycle['release_status'])}" data-serving-status="{_esc(lifecycle['serving_status'])}">
        {console_ui._document_card_heading({**envelope, "meaningful_status": item["meaningful_status"]})}
        <p class="lead">{_esc(_work_summary(item))}</p>
        {detail_html}
        {next_step}
      </article>
    '''


def _review_activity_status(item: dict[str, Any], started: set[str]) -> str:
    # Display only: completion remains a projection of the existing closure/duties.
    if item["lifecycle_status"]["workflow_status"] == "closed" or (
        item["source_passage_review_complete"]
        and not item["review_duties"] and not item["closure_gap_count"]
        and not item["blocked_count"]
    ):
        return "Afgerond"
    has_human_review = (item["snapshot_id"] in started or item.get("has_review_decision")
                        or (item.get("summary") or {}).get("has_review_decision"))
    return "Gestart" if has_human_review else "Nog niet gestart"


def _workboard_page(
    console: OperationsConsole,
    *,
    account: dict[str, Any],
    snapshot_id: str = "",
    q: str = "",
    page: int = 1,
    theme: str = "",
) -> str:
    """Compact document disclosures over existing, authorized review projections."""
    if "reviewer" not in set(account.get("roles") or []):
        raise ConsoleError("reviewer_role_required")
    items = review_workboard_items(console, account=account)
    if theme:
        items = [i for i in items if i["envelope"].get("family") == theme]
    by_id = {item["snapshot_id"]: item for item in items}
    if snapshot_id and snapshot_id not in by_id:
        raise ConsoleError("reviewer_not_named_on_snapshot")
    counts = console.waiting_task_counts(str(account["account_id"]))
    visible, controls = console_ui._document_list_page(
        [item["envelope"] for item in items], q=q, page=page, path="/review",
    )
    from src.review_participation_ui_v1 import filters, roster, people
    controls = controls[controls.index('<nav '):]
    controls = controls.replace('/review?', '/review?' + _esc(urlencode({'work': 'mine', 'theme': theme})) + '&amp;')
    controls = filters(console, work='mine', theme=theme, q=q, rows=[i['envelope'] for i in items]) + controls
    reviewer_names = people(console)
    if snapshot_id and not any(row["snapshot_id"] == snapshot_id for row in visible):
        visible = [by_id[snapshot_id]["envelope"], *visible]
    ledger_path = getattr(console, "_ledger_path", None)
    events = [event for event in (read_events(ledger_path) if ledger_path is not None else [])
              if str(event.get("actor") or "").strip()
              and not is_forbidden_reviewer(str(event["actor"]))]
    started = {
        str((event.get("details") or {}).get("snapshot_id") or "")
        for event in events
        if _is_decision_event(event) or event.get("event_type") == "review_audit_evidence"
    }
    cards = []
    for envelope in visible:
        chosen = str(envelope["snapshot_id"])
        item = by_id[chosen]
        status = _review_activity_status(item, started)
        if item["lifecycle_status"]["workflow_status"] == "closed":
            dashboard = ('<h2>Jouw open werk</h2><p>' + _esc(_work_summary(item)) + '</p>'
                         f'<a href="/review?document={quote(chosen, safe="")}&amp;task=history">Besluiten en historie</a>')
        else:
            dashboard = _projected_document_dashboard(
                console, account=account, snapshot_id=chosen, counts=counts,
                summary=item.get("summary"), content_only=True,
            ) if item.get("summary") else None
            if dashboard is None:
                dashboard = console_ui._review_task_dashboard(
                    chosen, koppen=[], individual=[],
                    normal_passages=item["actionable_batch_duties"],
                    normal_batches=item["normal_batches"], blocked_count=item["blocked_count"],
                    progress=item["progress"],
                    heading_pending_override=item["actionable_structure_duties"],
                    individual_pending_override=item["actionable_contextual_duties"],
                    second_review_pending=item["actionable_second_review_duties"],
                    disposition_pending=item["closure_gap_count"],
                    waiting_pending=item["waiting_for_reviewer_duties"],
                )
        dashboard = roster(console, envelope, reviewer_names) + f'<a href="/review/trajectory?{_esc(urlencode({"document": chosen}))}">Traject en deelnemers</a>' + dashboard
        # IDs must remain unique when several workspaces share one page.
        for element_id in ("review-task-title", "review-next-title", "review-progress-title"):
            dashboard = dashboard.replace(element_id, element_id + "-" + _esc(chosen))
        context = _esc(urlencode({"q": q, "page": page}))
        dashboard = dashboard.replace(f'/review?document={_esc(chosen)}&amp;task=',
                                      f'/review?document={_esc(chosen)}&amp;{context}&amp;task=')
        opened = " open" if chosen == snapshot_id else ""
        cards.append(f'''<details class="doc-card document-disclosure review-document-card"{opened}>
          <summary>{console_ui._document_summary({**envelope, "meaningful_status": item["meaningful_status"]})}
            <span class="review-status">Review: {_esc(status)}</span>
            <span class="document-work-summary">{_esc(_work_summary(item))}</span>
          </summary>{dashboard}</details>''')
    return _page(_nav(account, "review", counts) + '<section class="room review-room"><h1>Review</h1>'
                 + console_ui._task_links("review") + controls + '<div class="doc-list">' + ''.join(cards)
                 + (('<p>Geen documenten gevonden.</p>' if q else '<p>Geen aan jou toegewezen reviewdocumenten.</p>') if not cards else '')
                 + '</div></section>', title="Review — Metis")


def _projected_document_dashboard(
    console: OperationsConsole,
    *,
    account: dict[str, Any],
    snapshot_id: str,
    counts: dict[str, int],
    summary: dict[str, Any] | None = None,
    content_only: bool = False,
) -> str | None:
    """Render the default selected-document dashboard without materializing objects."""
    if summary is None:
        summary_reader = getattr(console, "review_workboard_summaries", None)
        if not callable(summary_reader):
            return None
        account_id = str(account.get("account_id") or "")
        if not account_id:
            return None
        summary = summary_reader(account_id, snapshot_id).get(snapshot_id)
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
        normal_passages=actionable_batch,
        normal_batches=int(summary.get("normal_batches") or 0),
        blocked_count=int(summary.get("blocked_count") or 0),
        progress=progress,
        heading_pending_override=actionable_structure,
        heading_total_override=int(summary.get("heading_total") or 0),
        heading_done_override=max(int(summary.get("heading_total") or 0) - int(summary.get("heading_pending", summary.get("heading_total")) or 0), 0),
        individual_pending_override=actionable_contextual,
        individual_done_override=max(int(summary.get("individual_total") or 0) - int(summary.get("individual_pending", summary.get("individual_total")) or 0), 0),
        individual_total_override=(
            int(summary.get("contextual_review_duties") or 0)
            if "contextual_review_duties" in summary
            else int(summary.get("individual_total") or 0)
        ),
        second_review_pending=actionable_second,
        disposition_pending=int(summary.get("closure_gap_count") or 0),
        waiting_pending=int(summary.get("waiting_for_reviewer_duties") or 0),
    )
    if content_only:
        return dashboard
    heading = console_ui._document_card_heading(
        {**envelope, "status": envelope.get("state") or ""}
    )
    return _page(
        f"""
        {_nav(account, "review", counts)}
        <section class="room review-room">
          <h1>Review</h1>
          {console_ui._task_links("review")}
          <div class="doc-card review-document-card">
            <div class="review-document-card-top"><span class="review-document-kicker">Document in review</span>
              <a class="btn-secondary" href="/review">Ander document kiezen</a>
            </div>
            {heading}
          </div>
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
        q: str = "",
        page: int = 1,
        work: str = "mine",
        theme: str = "",
    ) -> str:
        account = _current_account(console, request)
        from src.review_participation_ui_v1 import overview, require_overview
        require_overview(account)
        if work not in {"mine", "all"}:
            raise ConsoleError("invalid_review_filter")
        if not document and (work == "all" or "reviewer" not in account["roles"]):
            return overview(console, account, theme=theme, q=q, page=page)
        selected = next((e for e in console.list_envelopes() if e['snapshot_id'] == document), None) if document else None
        if document and selected is None:
            raise ConsoleError("unknown_snapshot")
        if selected and account["account_id"] not in selected["named_reviewers"]:
            return RedirectResponse('/review/trajectory?' + urlencode({'document': document}), status_code=303)
        chosen = document.strip()
        chosen_task = normalize_review_task(task)
        if not chosen or (not object.strip() and not chosen_task):
            return _workboard_page(console, account=account, snapshot_id=chosen, q=q, page=page, theme=theme)
        counts = console.waiting_task_counts(str(account["account_id"]))
        rendered = _render_review_room(
            console,
            account,
            html.escape(document, quote=True),
            html.escape(object, quote=True),
            task=html.escape(chosen_task, quote=True),
            counts=counts,
        )

        back = "/review?" + urlencode({"document": chosen, "q": q, "page": page})
        return rendered.replace(
            '<a class="btn-secondary" href="/review">Ander document kiezen</a>',
            f'<a class="btn-secondary" href="{_esc(back)}">Terug naar documenten</a>',
        )

    @app.post("/review/headings/batch-confirm")
    def review_headings_batch_confirm(
        request: Request,
        snapshot_id: str = Form(...),
        object_ids: list[str] = Form(default=[]),
        snapshot_revision: str = Form(""),
        interaction_id: str = Form(""),
    ) -> Any:
        response = original_headings_batch_confirm(
            request=request,
            snapshot_id=snapshot_id,
            object_ids=object_ids,
            snapshot_revision=snapshot_revision,
            interaction_id=interaction_id,
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
