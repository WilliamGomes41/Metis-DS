"""Protocol v2.33 proportionate review on top of the existing console kernel.

This module adds no new review store or governance state. It reuses
``OperationsConsole.review_object`` so every object in one human batch action
still receives its own exact-hash review, ledger event and publish tuple.
"""
from __future__ import annotations

from typing import Any, Iterable

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, admission_of
from src.beslisboom_path_v1 import review_path_for_klasse
from src.four_eyes_v1 import requires_four_eyes
from src.operations_console_v1 import (
    ConsoleError,
    OperationsConsole,
    is_slow_review_duty,
    review_lane,
)
from src.review_cockpit_v1 import confirmable_proposed_type


NORMAL_RISK_BATCH_TYPES = frozenset({"definition", "explanation"})


def _section_key(obj: dict[str, Any]) -> tuple[str, ...]:
    admission = admission_of(obj)
    path = admission.get("section_path") or (obj.get("structure") or {}).get("section_path") or []
    return tuple(str(part).strip() for part in path if str(part).strip())


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
    if confirmable_proposed_type(obj) not in NORMAL_RISK_BATCH_TYPES:
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
        """Approve one coherent normal-risk batch with per-object review records.

        The whole selection is preflighted before the first mutation. A batch
        cannot sweep in high-risk, blocked, action-bearing or mixed-section
        content. Each included object then travels through ``review_object``.
        """
        reviewer = self._require_role(actor_id, "reviewer")
        envelope = self._envelope(snapshot_id)
        if actor_id not in envelope["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        ids = list(dict.fromkeys(str(object_id).strip() for object_id in object_ids if str(object_id).strip()))
        if not ids:
            raise ConsoleError("normal_risk_batch_required")
        review_path = review_path_for_klasse(envelope["class"])
        current = {row["object_id"]: row for row in self.snapshot_objects(snapshot_id)}
        selected: list[dict[str, Any]] = []
        for object_id in ids:
            target = current.get(object_id)
            if target is None:
                raise ConsoleError("unknown_object")
            if not normal_risk_batch_eligible(target, review_path=review_path):
                raise ConsoleError("normal_risk_batch_ineligible")
            selected.append(target)
        sections = {_section_key(obj) for obj in selected}
        if len(selected) > 1 and (len(sections) != 1 or not next(iter(sections), ())):
            raise ConsoleError("normal_risk_batch_mixed_section")
        # Fail before any write if one source passage cannot be opened.
        for target in selected:
            self._require_open_original(snapshot_id, str(target["object_id"]))

        updated: list[dict[str, Any]] = []
        pin = expected_revision
        for target in selected:
            object_id = str(target["object_id"])
            confirmed_type = confirmable_proposed_type(target)
            self.review_object(
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
            if pin is not None:
                pin = self.objects_revision(snapshot_id)
            refreshed = next(row for row in self.snapshot_objects(snapshot_id) if row["object_id"] == object_id)
            updated.append(refreshed)
        _ = reviewer
        return updated


def install_proportionate_review_routes(app: FastAPI, console: ProportionateReviewConsole) -> None:
    """Expose the normal-risk batch action without replacing the existing app."""

    async def batch_confirm(
        request: Request,
        snapshot_id: str = Form(...),
        object_ids: list[str] = Form(default=[]),
        snapshot_revision: str = Form(""),
    ) -> RedirectResponse:
        token = request.cookies.get("console_session")
        account = console.session_account(token)
        raw = [object_ids] if isinstance(object_ids, str) else list(object_ids or [])
        console.batch_review_normal_risk(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            object_ids=raw,
            expected_revision=snapshot_revision.strip() or None,
        )
        return RedirectResponse(f"/review?document={snapshot_id}", status_code=303)

    app.add_api_route(
        "/review/normal-risk/batch-confirm",
        batch_confirm,
        methods=["POST"],
        response_class=RedirectResponse,
        name="review_normal_risk_batch_confirm",
    )
