"""Direct reviewer workspace over the existing review queues.

The assigned-document projection supplies inline document choice and opens
available work directly. No review state, priority store or assignment model
is added; explicit task links continue to use the existing review room.
"""
from __future__ import annotations

from src.request_diagnostics_v1 import diagnostic_phase

import html
import re
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
)
from src.publication_readiness_v1 import source_passage_closure, review_followup_queues
from src.review_duty_v1 import review_work_projection
from src.review_interaction_v1 import _is_decision_event
from src.review_ledger import read_events
from src.knowledge_materialisation_v1 import source_reconstruction_scope


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


@diagnostic_phase("authorization")
def _current_account(console: OperationsConsole, request: Request) -> dict[str, Any]:
    scoped = getattr(request.state, 'view_check_account', None)
    if scoped is not None:
        return scoped
    token = request.cookies.get(COOKIE)
    try:
        return console.session_account(token)
    except ConsoleError as exc:
        raise ConsoleError("not_authenticated") from exc


def _assigned_to_reviewer(envelope: dict[str, Any], account_id: str) -> bool:
    return account_id in set(envelope.get("named_reviewers") or [])


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
    workplace = '/source-selection' if next_task == 'repair' or (next_task == 'structure' and _review_path_of(envelope) != 'boom') else '/review'
    next_href = (
        f"{workplace}?document={quote(snapshot_id, safe='')}&task={quote(next_task, safe='')}"
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


@source_reconstruction_scope(reuse_existing=True)
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
    bindings: list[dict[str, Any]] | None
    if inputs is not None:
        bindings = inputs.bindings
    else:
        try:
            bindings = console.object_review_bindings(snapshot_id)
        except AttributeError:
            bindings = None

    fragments = console.review_source_fragments(snapshot_id, envelope=envelope)
    if fragments is not None:
        from src.prepared_source_views_v1 import prepare
        fragments = prepare(fragments).fragments

    review_path = review_path_for_klasse(str(envelope.get("class") or ""))
    headings, _ = review_stacks(objects, review_path=review_path)
    open_headings = [row for row in headings if not _review_is_final(row)]
    heading_pending = len(open_headings)

    duties, duty_counts, route_counts = review_work_projection(
        objects, review_path=review_path, reviewer_id=account_id,
        bindings=bindings, fragments=fragments)
    from src.operations_console_v1 import slow_review_kind
    from src.object_taxonomy_v1 import review_priority_rank
    if review_path == 'boom':
        duty = slow_review_duty(objects, review_path=review_path, bindings=bindings, fragments=fragments)
        regular_individual = []
    else:
        duty = sorted([obj for obj in objects if obj['object_id'] in duties
                       and slow_review_kind(obj, review_path=review_path)], key=review_priority_rank)
        regular_individual = sorted([obj for obj in objects if obj['object_id'] in duties
            and duties[obj['object_id']]['lane'] != 'batch'
            and not slow_review_kind(obj, review_path=review_path)], key=review_priority_rank)
    individual = [*duty, *regular_individual]
    open_individual = [row for row in individual if not _review_is_final(row)]
    individual_pending = len(open_individual)

    normal_passages = 0
    normal_batches = 0
    if isinstance(console, ProportionateReviewConsole):
        from collections import Counter
        from src.proportionate_review_v1 import _section_key, _batch_type, NORMAL_RISK_BATCH_MAX
        groups = Counter((_section_key(obj), _batch_type(obj)) for obj in objects
            if review_path != 'boom' and obj['object_id'] in duties
            and duties[obj['object_id']]['stage'] == 'first_review'
            and duties[obj['object_id']]['lane'] == 'batch')
        normal_passages = sum(groups.values())
        normal_batches = sum((n + NORMAL_RISK_BATCH_MAX - 1) // NORMAL_RISK_BATCH_MAX
                             for n in groups.values())

    from src.source_containers_v1 import source_accountability
    projection = source_accountability(objects, review_path=review_path, bindings=bindings, fragments=fragments)
    closure = source_passage_closure(objects, projection=projection)
    followups = review_followup_queues(objects, review_path=review_path, projection=projection)
    blocked_count = len(followups["repair"])
    closure_gap_ids = [str(obj["object_id"]) for obj in followups["disposition"]]

    if bindings is None:
        route_counts = {
            "actionable_review_duties": duty_counts["review_duties"],
            "waiting_for_reviewer_duties": 0,
            "actionable_structure_duties": duty_counts["structure_review_duties"],
            "actionable_contextual_duties": duty_counts["contextual_review_duties"],
            "actionable_batch_duties": duty_counts["batch_review_duties"],
            "actionable_second_review_duties": duty_counts["second_review_duties"],
        }
    if review_path != "boom":
        # Koppen stay a structure check. They are not content-review duties.
        route_counts["actionable_structure_duties"] = heading_pending

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
    item["heading_total"] = len(headings)
    item["individual_total"] = console_ui._lane_total(
        objects, review_path=review_path, lane="contextual", open_rows=individual)
    item["progress"] = console_ui._review_progress_summary(objects)
    item["knowledge_progress"] = console_ui.knowledge_progress(objects, review_path=review_path)
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



@diagnostic_phase("review_work_items")
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
            if "work_item" in summary or envelope.get("review_policy"):
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
        for envelope in console.list_document_cards()
        if (item := review_work_item(console, account=account, envelope=envelope)) is not None
    ]


def _personal_review_view(item: dict[str, Any]) -> dict[str, Any]:
    """Disposable landing presentation; existing duties/routes remain authority."""
    closed = item['lifecycle_status']['workflow_status'] == 'closed'
    opened = 0 if closed else int(item.get('actionable_review_duties') or 0)
    second = 0 if closed else int(item.get('actionable_second_review_duties') or 0)
    href = ''
    graph = str(item.get('next_href') or '').startswith('/review/decision-graph?')
    if not closed and graph and item['work_state'] == 'review':
        href = item['next_href']
    elif opened:
        # Preserve the existing relative lane order; prose headings belong to Vorming.
        tasks = []
        if _review_path_of(item['envelope']) == 'boom':
            tasks.append(('structure', int(item.get('actionable_structure_duties') or 0)))
        tasks.extend([
            ('contextual', int(item.get('actionable_contextual_duties') or 0)),
            ('batch', int(item.get('actionable_batch_duties') or 0)),
            ('second_review', second),
        ])
        task = next((name for name, count in tasks if count), '')
        if task:
            href = '/review?' + urlencode({'document': item['snapshot_id'], 'task': task})
    if href:
        state = 'review'
    elif not closed and (int(item.get('review_duties') or 0)
                         or item['work_state'] == 'waiting_for_reviewer'):
        state = 'waiting'
    else:
        state = 'complete'
    return dict(state=state, opened=opened, first=opened - second, second=second, href=href, graph=graph)


def _workboard_card(item: dict[str, Any], *, started: bool = False,
                    observed_at: str = '', q: str = '', page: int = 1) -> str:
    """One visible personal action over one existing actor-specific work item."""
    envelope, lifecycle = item['envelope'], item['lifecycle_status']
    view = _personal_review_view(item)
    sid = str(item['snapshot_id'])
    if view['href']:
        href = view['href'] + '&' + urlencode({'q': q, 'page': page})
        title = 'Verder beoordelen' if started else 'Beginnen'
        action = f'<a class="btn-primary" data-personal-review-action href="{_esc(href)}">{title}</a>'
    else:
        action = '<a href="/review?' + _esc(urlencode({'document': sid, 'task': 'history'})) + '">Beoordelingen inzien</a>'
    if view['state'] == 'waiting':
        summary = '<p class="lead">Wachten op een andere reviewer.</p>'
    elif view['state'] == 'complete':
        summary = '<p class="lead">Geen open beoordeling voor jou.</p>'
    elif view['graph'] and not view['opened']:
        summary = '<p class="lead">De beslisroutes vragen jouw beoordeling.</p>'
    else:
        summary = ('<p class="lead">Voor jou open: <b data-personal-open>' + str(view['opened']) + '</b></p>'
                   '<p>Eerste beoordeling: <b data-personal-first>' + str(view['first']) + '</b> · '
                   'Tweede beoordeling: <b data-personal-second>' + str(view['second']) + '</b></p>')
    evidence_href = '/inzicht/document?' + urlencode({'document': sid})
    evidence = f'<p><a href="{_esc(evidence_href)}">Verklaring en bewijs in Inzicht</a></p>'
    scope = console_ui.count_scope_label(envelope.get('version'), observed_at=observed_at or _observed_at())
    return ('<article class="doc-card" data-workboard-document="' + _esc(sid) +
            '" data-personal-state="' + view['state'] + '" data-workflow-status="' + _esc(lifecycle['workflow_status']) + '">'
            '<h2>' + _esc(str(envelope.get('title') or 'Document')) + '</h2>'
            '<p class="muted" data-count-scope>' + _esc(scope) + '</p>' + summary + action + evidence + '</article>')


@diagnostic_phase("review_render")
def _workboard_page(console: OperationsConsole, *, account: dict[str, Any],
                    snapshot_id: str = '', q: str = '', page: int = 1, theme: str = '') -> str:
    """Personal visible-page inventory over the existing authorized read path."""
    if 'reviewer' not in set(account.get('roles') or []):
        raise ConsoleError('reviewer_role_required')
    summary_reader = getattr(console, 'review_workboard_summaries', None)
    enrich = getattr(console, '_enrich_review_workboard_summaries', None)
    summaries = None
    if callable(summary_reader) and callable(enrich):
        summaries = summary_reader(account['account_id'], metadata_only=True)
        envelopes = [summary['envelope'] for summary in summaries.values()]
        items = []
    else:
        items = review_workboard_items(console, account=account)
        envelopes = [item['envelope'] for item in items]
    if theme:
        envelopes = [row for row in envelopes if row.get('family') == theme]
    by_envelope = {row['snapshot_id']: row for row in envelopes}
    if snapshot_id and snapshot_id not in by_envelope:
        raise ConsoleError('reviewer_not_named_on_snapshot')
    visible, controls = console_ui._document_list_page(envelopes, q=q, page=page, path='/review')
    from src.review_participation_ui_v1 import filters
    controls = controls[controls.index('<nav '):]
    controls = controls.replace('/review?', '/review?' + _esc(urlencode({'work': 'mine', 'theme': theme})) + '&amp;')
    controls = filters(console, work='mine', theme=theme, q=q, rows=envelopes) + controls
    if snapshot_id and not any(row['snapshot_id'] == snapshot_id for row in visible):
        visible = [by_envelope[snapshot_id], *visible]
    if summaries is not None:
        selected = {row['snapshot_id']: summaries[row['snapshot_id']] for row in visible}
        enrich(account['account_id'], selected)
        items = review_workboard_items(console, account=account, summaries=selected)
    by_id = {item['snapshot_id']: item for item in items}
    ledger_path = getattr(console, '_ledger_path', None)
    reader = getattr(getattr(console, 'workflow_review_store', None), 'read_events_for_snapshots', None)
    history = (reader([row['snapshot_id'] for row in visible]) if callable(reader) else
               read_events(ledger_path) if ledger_path is not None else [])
    started = set()
    for event in history:
        if not (_is_decision_event(event) or event.get('event_type') == 'review_audit_evidence'):
            continue
        details = event.get('details') or {}
        reviewer = str(details.get('reviewer_id') or details.get('reviewer_account_id') or '')
        actor = str(event.get('actor') or '').strip()
        own = (reviewer == account['account_id'] if reviewer else
               actor in {account['account_id'], account.get('username')})
        if own and not is_forbidden_reviewer(actor):
            started.add(str(details.get('snapshot_id') or ''))
    groups = {'review': [], 'waiting': [], 'complete': []}
    observed = _observed_at()
    for envelope in visible:
        sid = str(envelope['snapshot_id'])
        item = by_id[sid]
        state = _personal_review_view(item)['state']
        groups[state].append(_workboard_card(item, started=sid in started, observed_at=observed, q=q, page=page))
    body = ''
    if not groups['review']:
        body += '<p class="review-empty" data-personal-empty>Op deze pagina heb je geen uitvoerbare beoordelingen.</p>'
    for state, title in [('review', 'Jouw open beoordelingen'), ('waiting', 'Wachten op anderen'),
                         ('complete', 'Geen open werk voor jou')]:
        if groups[state]:
            body += '<section data-personal-group="' + state + '"><h2>' + title + '</h2><div class="doc-list">' + ''.join(groups[state]) + '</div></section>'
    if not visible:
        body += ('<p class="review-empty">Geen documenten gevonden.</p>' if q else
                 '<p class="review-empty">Geen aan jou toegewezen reviewdocumenten. Nieuw werk verschijnt hier zodra iemand je als reviewer kiest.</p>')
    return _page(_nav(account, 'review') + '<section class="room review-room"><h1>Review</h1>' +
                 console_ui._task_links('review') + controls + body + '</section>', title='Review — Metis')


def _review_path_of(envelope: dict[str, Any]) -> str:
    try:
        return review_path_for_klasse(str(envelope.get("class") or ""))
    except ValueError:
        return "richtlijn"


def _observed_at() -> str:
    import src.operations_console_v1 as console_kernel
    return console_kernel.utc_now()


def install_review_workboard(app: FastAPI, console: OperationsConsole) -> None:
    """Install the Review workboard and its post-heading navigation."""
    if getattr(app.state, "review_workboard_v1", False):
        return

    retained = []
    headings_post_route = None
    for route in app.router.routes:
        methods = set(getattr(route, "methods", set()) or set())
        path = getattr(route, "path", None)
        if path == "/review" and "GET" in methods:
            raise RuntimeError("review_get_route_already_registered")
        if path == "/review/headings/batch-confirm" and "POST" in methods:
            if headings_post_route is not None:
                raise RuntimeError("review_headings_route_replacement_ambiguous")
            headings_post_route = route
            continue
        retained.append(route)
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
        context_target: str = "",
        context_mode: str = "",
        context_saved: str = "",
        context_page: int = 0,
        context_q: str = "",
        queue_page: int = 1,
    ) -> str:
        account = _current_account(console, request)
        from src.review_participation_ui_v1 import overview, require_overview
        require_overview(account)
        if work not in {"mine", "all"}:
            raise ConsoleError("invalid_review_filter")
        if not document and (work == "all" or "reviewer" not in account["roles"]):
            return overview(console, account, theme=theme, q=q, page=page)
        if document and object.strip() and (context_target or context_mode == 'source'):
            # Historical editor bookmarks only navigate; context commands live
            # on Vorming and still enforce their original kernel permissions.
            if account['account_id'] not in console._envelope(document)['named_reviewers']:
                return RedirectResponse('/review/trajectory?' + urlencode({'document': document}), status_code=303)
            params = {'document': document, 'object': object.strip(),
                      'context_target': context_target, 'context_mode': context_mode,
                      'context_page': context_page, 'context_q': context_q}
            return RedirectResponse('/source-selection?' + urlencode(params) + '#passage-context',
                                    status_code=303)
        chosen_task = normalize_review_task(task)
        if document and chosen_task == 'repair':
            if 'reviewer' not in account.get('roles', []) or account['account_id'] not in console._envelope(document)['named_reviewers']:
                raise ConsoleError('reviewer_not_named_on_snapshot')
            return RedirectResponse('/source-selection?' + urlencode(dict(document=document, object=object, task='repair')), status_code=303)
        read_inputs = None
        if document and object.strip() and chosen_task != 'history':
            from src.review_passage_read_v1 import read_review_passage
            try:
                read_inputs = read_review_passage(console, account, document, object.strip(),
                    context_target=context_target, choice_page=max(context_page, 0), choice_query=context_q)
            except ConsoleError as exc:
                if exc.code == 'reviewer_not_named_on_snapshot':
                    return RedirectResponse('/review/trajectory?' + urlencode({'document': document}), status_code=303)
                raise
            selected = read_inputs.envelope
        elif document and chosen_task and chosen_task not in {'history', 'structure'}:
            from src.review_passage_read_v1 import read_review_document
            try:
                read_inputs = read_review_document(console, account, document)
            except ConsoleError as exc:
                if exc.code == 'reviewer_not_named_on_snapshot':
                    return RedirectResponse('/review/trajectory?' + urlencode({'document': document}), status_code=303)
                raise
            selected = read_inputs.envelope
        else:
            selected = console._envelope(document) if document else None
        if document and selected is None:
            raise ConsoleError("unknown_snapshot")
        if selected and account["account_id"] not in selected["named_reviewers"]:
            return RedirectResponse('/review/trajectory?' + urlencode({'document': document}), status_code=303)
        if (selected and not object.strip() and chosen_task == 'structure'
                and review_path_for_klasse(selected['class']) != 'boom'):
            params = {'document': document, 'task': 'structure'}
            if q or page != 1:
                params.update(q=q, page=page)
            return RedirectResponse('/source-selection?' + urlencode(params), status_code=303)
        chosen = document.strip()
        chosen_task = normalize_review_task(task)
        if not chosen or (not object.strip() and not chosen_task):
            return _workboard_page(console, account=account, snapshot_id=chosen, q=q, page=page, theme=theme)
        rendered = _render_review_room(
            console,
            account,
            html.escape(document, quote=True),
            html.escape(object, quote=True),
            task=html.escape(chosen_task, quote=True),
            context_target=context_target,
            context_mode=context_mode,
            context_saved=context_saved == "yes",
            read_inputs=read_inputs,
            queue_page=queue_page,
        )

        back = "/review?" + urlencode({"document": chosen, "q": q, "page": page})
        if theme:
            back += '&' + urlencode({'theme': theme})
        if q or page != 1 or theme:
            suffix = _esc(urlencode({'q': q, 'page': page, 'theme': theme}))
            # Match each complete attribute once; overlapping wildcards around
            # queue_page can backtrack quadratically on an unterminated href.
            rendered = re.sub(r'href="(/review\?[^"\n]*)"',
                lambda match: (f'href="{match[1]}&amp;{suffix}"'
                               if 'queue_page=' in match[1] else match[0]), rendered)
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
            if response.headers['location'].startswith('/source-selection?'):
                return response
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
