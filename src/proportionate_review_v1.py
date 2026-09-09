"""Protocol v2.33 proportionate review on top of the existing console kernel.

This module adds no new review store or governance state. It reuses
``OperationsConsole.review_object`` so every object in one human batch action
still receives its own exact-hash review, ledger event and publish tuple.
"""
from __future__ import annotations

from collections import defaultdict
from html import escape
from typing import Any, Iterable

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, admission_of
from src.beslisboom_path_v1 import review_path_for_klasse
from src.four_eyes_v1 import requires_four_eyes
from src.operations_console_v1 import (
    ConsoleError,
    OperationsConsole,
    SNAPSHOT_OBJECT_WRITE_CONFLICT,
    is_slow_review_duty,
    review_lane,
)
from src.review_cockpit_v1 import confirmable_proposed_type


NORMAL_RISK_BATCH_TYPES = frozenset({"definition", "explanation"})
NORMAL_RISK_BATCH_MAX = 20


def _batch_type(obj: dict[str, Any]) -> str:
    """Human/stored classification wins over an obsolete machine proposal."""
    if obj.get("confirmed_object_type"):
        return str(obj["confirmed_object_type"])
    if obj.get("object_type") not in {None, "unclassified"}:
        return str(obj["object_type"])
    return confirmable_proposed_type(obj)


def _section_key(obj: dict[str, Any]) -> tuple[str, ...]:
    admission = admission_of(obj)
    path = admission.get("section_path") or (obj.get("structure") or {}).get("section_path") or []
    return tuple(str(part).strip() for part in path if str(part).strip())


def _object_text(obj: dict[str, Any]) -> str:
    content = obj.get("content") if isinstance(obj.get("content"), dict) else {}
    return str(content.get("clean_text") or obj.get("candidate_text") or "").strip()


def regular_review_queue(
    objects: Iterable[dict[str, Any]],
    *,
    review_path: str,
) -> list[dict[str, Any]]:
    """All ordinary reviewable content; priority is not eligibility.

    Boom keeps its established hand-duty semantics. For the richtlijn path,
    every admission-allowed non-structure object has a regular review route.
    Admission-blocked content stays visible as open disposition work but is
    not approvable until corrected.
    """
    rows = list(objects)
    if review_path == "boom":
        return [obj for obj in rows if is_slow_review_duty(obj, review_path=review_path)]
    return [
        obj
        for obj in rows
        if obj.get("object_type") != "document"
        and review_lane(obj, review_path=review_path) != "fast"
        and admission_of(obj).get("gate_result") == GATE_ALLOWED
    ]


def normal_risk_batch_eligible(obj: dict[str, Any], *, review_path: str) -> bool:
    if review_path == "boom" or obj.get("object_type") == "document":
        return False
    if review_lane(obj, review_path=review_path) == "fast":
        return False
    admission = admission_of(obj)
    if admission.get("gate_result") in {None, GATE_BLOCKED}:
        return False
    if admission.get("gate_result") != GATE_ALLOWED:
        return False
    if _batch_type(obj) not in NORMAL_RISK_BATCH_TYPES:
        return False
    if not _section_key(obj):
        return False
    uncertainty = obj.get("uncertainty") if isinstance(obj.get("uncertainty"), dict) else {}
    if bool(uncertainty.get("has_uncertainty")):
        return False
    risk = obj.get("risk") if isinstance(obj.get("risk"), dict) else {}
    if risk.get("level") == "high" or bool(risk.get("requires_second_review")):
        return False
    if requires_four_eyes(obj, confirmed_type=obj.get("confirmed_object_type") or None):
        return False
    governance = obj.get("governance") if isinstance(obj.get("governance"), dict) else {}
    if governance.get("validation_status") not in {None, "needs_review"}:
        return False
    return True


def normal_risk_batch_queue(
    objects: Iterable[dict[str, Any]],
    *,
    review_path: str,
) -> list[dict[str, Any]]:
    return [obj for obj in objects if normal_risk_batch_eligible(obj, review_path=review_path)]


def normal_risk_batch_counts(
    objects: Iterable[dict[str, Any]],
    *,
    review_path: str,
) -> tuple[int, int]:
    """Return pending passage and bounded batch counts for task navigation."""
    groups: dict[tuple[tuple[str, ...], str], int] = defaultdict(int)
    for obj in normal_risk_batch_queue(objects, review_path=review_path):
        groups[(_section_key(obj), _batch_type(obj))] += 1
    passages = sum(groups.values())
    batches = sum((count + NORMAL_RISK_BATCH_MAX - 1) // NORMAL_RISK_BATCH_MAX for count in groups.values())
    return passages, batches


def regular_individual_review_queue(
    objects: Iterable[dict[str, Any]],
    *,
    review_path: str,
) -> list[dict[str, Any]]:
    """Allowed passages that need their own review instead of a batch."""
    rows = list(objects)
    batch_ids = {
        str(obj.get("object_id") or "")
        for obj in normal_risk_batch_queue(rows, review_path=review_path)
    }
    return [
        obj
        for obj in rows
        if obj.get("object_type") != "document"
        and review_lane(obj, review_path=review_path) != "fast"
        and not is_slow_review_duty(obj, review_path=review_path)
        and admission_of(obj).get("gate_result") == GATE_ALLOWED
        and str(obj.get("object_id") or "") not in batch_ids
    ] if review_path != "boom" else []


def render_normal_risk_batch_panel(
    console: "ProportionateReviewConsole", snapshot_id: str,
    *, snapshot: tuple[list[dict[str, Any]], str] | None = None,
    selected_ids: Iterable[str] = (),
    include_individual: bool = True,
) -> str:
    """Render reachable normal-risk review work in bounded coherent batches."""
    envelope = console._envelope(snapshot_id)
    review_path = review_path_for_klasse(envelope["class"])
    objects, revision = snapshot if snapshot is not None else console.snapshot_objects_and_revision(snapshot_id)
    all_objects = objects
    queue = normal_risk_batch_queue(all_objects, review_path=review_path)
    if not queue:
        return ""
    groups: dict[tuple[tuple[str, ...], str], list[dict[str, Any]]] = defaultdict(list)
    for obj in queue:
        proposed = _batch_type(obj)
        groups[(_section_key(obj), proposed)].append(obj)
    revision = escape(revision, quote=True)
    safe_snapshot = escape(snapshot_id, quote=True)
    selected = set(selected_ids)
    panels: list[str] = [
        '<section class="review-normal-risk" aria-labelledby="normal-risk-title">',
        '<h2 id="normal-risk-title">Samen beoordelen</h2>',
        '<p><span class="info-tip" tabindex="0" aria-label="Deze passages staan in dezelfde sectie en zijn van hetzelfde soort.">ⓘ'
        '<span class="info-tip-text">Deze passages staan in dezelfde sectie en zijn van hetzelfde soort.</span></span> '
        'Deze passages staan in dezelfde sectie en zijn van hetzelfde soort. '
        'Lees ze als groep en bevestig alleen de passages waarover je zeker bent. '
        f'Een groep bevat maximaal {NORMAL_RISK_BATCH_MAX} passages; batches van maximaal {NORMAL_RISK_BATCH_MAX} '
        'houden de controle overzichtelijk.</p>',
    ]
    batch_index = 0
    for (section, proposed), group_objects in groups.items():
        label = escape(" › ".join(section))
        type_label = "Definitie" if proposed == "definition" else "Toelichting"
        for start in range(0, len(group_objects), NORMAL_RISK_BATCH_MAX):
            batch = group_objects[start : start + NORMAL_RISK_BATCH_MAX]
            batch_index += 1
            panels.append(
                f'<form method="post" action="/review/normal-risk/batch-confirm" class="normal-risk-batch">'
                f'<input type="hidden" name="snapshot_id" value="{safe_snapshot}">'
                f'<input type="hidden" name="snapshot_revision" value="{revision}">'
                f'<fieldset><legend>{escape(section[-1])} — {type_label} ({len(batch)})</legend>'
                f'<details class="review-source-path"><summary>Volledig bronpad</summary><p>{label}</p></details>'
                '<button class="btn-secondary" type="button" data-select-review-batch>Alles in deze groep selecteren</button>'
            )
            for obj in batch:
                object_id = escape(str(obj.get("object_id") or ""), quote=True)
                text = escape(_object_text(obj))
                checked = " checked" if str(obj.get("object_id")) in selected else ""
                panels.append(
                    '<div class="normal-risk-row">'
                    '<label class="normal-risk-item">'
                    f'<input type="checkbox" name="object_ids" value="{object_id}"{checked}> '
                    f'<strong>{type_label}</strong> — {text}'
                    '</label>'
                    f' <a href="/review?document={safe_snapshot}&amp;object={object_id}&amp;task=together">Afzonderlijk beoordelen</a>'
                    f' <a href="/review/bronpassage?document={safe_snapshot}&amp;object={object_id}">Bronpassage</a>'
                    '</div>'
                )
            panels.append(
                '</fieldset><button class="btn-primary" type="submit">Bevestig geselecteerde passages</button>'
                f'<span class="sr-only">Batch {batch_index}</span></form>'
            )
    if include_individual:
        individual = regular_individual_review_queue(all_objects, review_path=review_path)
        if individual:
            panels.append(
                '<details class="review-normal-risk-individual">'
                f'<summary>Overige inhoud afzonderlijk bekijken ({len(individual)})</summary>'
                '<p>Deze passages kunnen niet veilig samen worden bevestigd. '
                'Open iedere passage om de bron en het voorstel te beoordelen.</p><ul>'
            )
            for obj in individual:
                object_id = escape(str(obj.get("object_id") or ""), quote=True)
                panels.append(
                    f'<li><a href="/review?document={safe_snapshot}&amp;object={object_id}">'
                    f'{escape(_object_text(obj))}</a></li>'
                )
            panels.append('</ul></details>')
    panels.append("</section>")
    return "".join(panels)


class ProportionateReviewConsole(OperationsConsole):
    """Existing console plus the bounded v2.33 review operations."""

    def next_review_object_id(self, snapshot_id: str, object_id: str) -> str:
        envelope = self._envelope(snapshot_id)
        path = review_path_for_klasse(envelope["class"])
        ids = [
            str(obj.get("object_id") or "")
            for obj in regular_review_queue(self.snapshot_objects(snapshot_id), review_path=path)
            if obj.get("object_id")
        ]
        if object_id in ids:
            index = ids.index(object_id)
            if index + 1 < len(ids):
                return ids[index + 1]
        return ""

    def batch_review_normal_risk(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_ids: Iterable[str],
        expected_revision: str | None = None,
    ) -> list[dict[str, Any]]:
        """Approve one bounded coherent normal-risk batch per object.

        The whole selection is preflighted before the first mutation. A batch
        contains at most ``NORMAL_RISK_BATCH_MAX`` objects and cannot sweep in
        mixed types, high-risk, blocked, ambiguous, action-bearing or
        mixed-section content. Each included object then travels through
        ``review_object``.
        """
        self._require_role(actor_id, "reviewer")
        envelope = self._envelope(snapshot_id)
        if actor_id not in envelope["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        ids = list(dict.fromkeys(str(object_id).strip() for object_id in object_ids if str(object_id).strip()))
        if not ids:
            raise ConsoleError("normal_risk_batch_required")
        if len(ids) > NORMAL_RISK_BATCH_MAX:
            raise ConsoleError("normal_risk_batch_too_large")
        review_path = review_path_for_klasse(envelope["class"])
        objects, revision = self.snapshot_objects_and_revision(snapshot_id)
        if expected_revision is not None and revision != expected_revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=revision)
        current = {row["object_id"]: row for row in objects}
        selected: list[dict[str, Any]] = []
        for object_id in ids:
            target = current.get(object_id)
            if target is None:
                raise ConsoleError("unknown_object")
            if not normal_risk_batch_eligible(target, review_path=review_path):
                raise ConsoleError("normal_risk_batch_ineligible")
            selected.append(target)
        sections = {_section_key(obj) for obj in selected}
        if len(sections) != 1 or not next(iter(sections), ()):
            raise ConsoleError("normal_risk_batch_mixed_section")
        types = {_batch_type(obj) for obj in selected}
        if len(types) != 1:
            raise ConsoleError("normal_risk_batch_mixed_type")
        # Fail before any write if one source passage cannot be opened.
        for target in selected:
            self._require_open_original(snapshot_id, str(target["object_id"]))

        updated: list[dict[str, Any]] = []
        pin = revision
        for target in selected:
            current_revision = self.objects_revision(snapshot_id)
            if current_revision != pin:
                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=current_revision)
            object_id = str(target["object_id"])
            confirmed_type = _batch_type(target)
            rows = self.review_object(
                actor_id=actor_id,
                snapshot_id=snapshot_id,
                object_id=object_id,
                decision="approve",
                confirmed_object_type=confirmed_type,
                suitability="ja",
                eindoordeel="goedkeuren",
                type_action="dit_klopt",
                expected_revision=pin,
            )
            # _save_objects records this call's committed revision in thread-local
            # state. Never adopt a later writer's revision between batch members.
            pin = self._objects_expected_revs()[snapshot_id]
            refreshed = next(row for row in rows if row["object_id"] == object_id)
            updated.append(refreshed)
        return updated


def install_proportionate_review_routes(app: FastAPI, console: ProportionateReviewConsole) -> None:
    """Expose and render the bounded normal-risk batch workflow."""

    def batch_confirm(
        request: Request,
        snapshot_id: str = Form(...),
        object_ids: list[str] = Form(default=[]),
        snapshot_revision: str = Form(""),
    ) -> Response:
        token = request.cookies.get("console_session")
        account = console.session_account(token)
        raw = [object_ids] if isinstance(object_ids, str) else list(object_ids or [])
        if not snapshot_revision.strip():
            raise ConsoleError("snapshot_revision_required")
        try:
            console.batch_review_normal_risk(
                actor_id=account["account_id"],
                snapshot_id=snapshot_id,
                object_ids=raw,
                expected_revision=snapshot_revision.strip(),
            )
        except ConsoleError as exc:
            if exc.code != SNAPSHOT_OBJECT_WRITE_CONFLICT:
                raise
            from src.operations_console_app import _render_review_room

            return HTMLResponse(
                _render_review_room(
                    console,
                    account,
                    snapshot_id,
                    task="together",
                    conflict=True,
                    batch_selection=raw,
                ),
                status_code=409,
            )
        return RedirectResponse(f"/review?document={snapshot_id}&task=together", status_code=303)

    app.add_api_route(
        "/review/normal-risk/batch-confirm",
        batch_confirm,
        methods=["POST"],
        response_class=RedirectResponse,
        name="review_normal_risk_batch_confirm",
    )
