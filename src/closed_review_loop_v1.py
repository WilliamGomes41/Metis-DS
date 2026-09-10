"""Closed Review resolution loop on top of the existing console kernel.

This module deliberately reuses the existing review, revision, relation and
ledger mechanisms. It does not introduce a second workflow store.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.integrity_kernel import compute_canonical_object_hash
from src.operations_console_v1 import ConsoleError
from src.passage_register_v1 import passage_register_of
from src.proportionate_review_v1 import ProportionateReviewConsole
from src.publish_authorization_v1 import invalidate_for_object
from src.review_cockpit_v1 import broncontext_parts, map_eindoordeel
from src.review_ledger import append_event, read_events
from src.serving_relations_v1 import binding_relations


REVIEW_AUDIT_EVIDENCE_EVENT = "review_audit_evidence"
ALLOWED_FINAL_BY_SUITABILITY = {
    "ja": {"approve", "revise", "reject"},
    "mist_context": {"revise", "reject"},
    "samenvoegen": {"revise", "reject"},
    "alleen_onderbouwing": {"revise", "approve", "reject"},
    "geen_kenniseenheid": {"reject"},
}


def _norm(value: str) -> str:
    return " ".join(str(value or "").split())


def _source_context(obj: dict[str, Any]) -> str:
    parts = broncontext_parts(obj)
    return _norm(
        " ".join(
            str(parts.get(key) or "")
            for key in ("previous_paragraph", "source_text_exact", "next_paragraph")
        )
    )


def _source_locator(obj: dict[str, Any], fallback: str = "") -> Any:
    for fragment in (obj.get("provenance") or {}).get("source_fragments") or []:
        locator = fragment.get("source_locator")
        if locator:
            return deepcopy(locator)
    return fallback


class ClosedLoopReviewConsole(ProportionateReviewConsole):
    """Active console with closed review outcomes and Audit evidence routing."""

    def waiting_task_counts(self, account_id: str) -> dict[str, int]:
        counts = super().waiting_task_counts(account_id)
        account = self._account(account_id)
        roles = set(account.get("roles") or [])
        ingest = 0
        review = 0
        for envelope in self._envelopes.values():
            current = self.snapshot_objects(envelope["snapshot_id"])
            statuses = {
                (row.get("governance") or {}).get("validation_status")
                for row in current
            }
            if (
                "researcher" in roles
                and envelope.get("uploader_account_id") == account_id
                and "revise" in statuses
            ):
                ingest += 1
            if (
                "reviewer" in roles
                and account_id in (envelope.get("named_reviewers") or [])
                and "needs_review" in statuses
            ):
                review += 1
        counts["ingest"] = ingest if "researcher" in roles else 0
        counts["review"] = review if "reviewer" in roles else 0
        return counts

    def _has_inbound_support(self, snapshot_id: str, support_object_id: str) -> bool:
        for obj in self.snapshot_objects(snapshot_id):
            if obj.get("object_id") == support_object_id:
                continue
            if any(
                rel.get("relation_type") == "supported_by"
                and rel.get("target_object_id") == support_object_id
                for rel in binding_relations(obj)
            ):
                return True
        return False

    def _append_audit_evidence(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        target: dict[str, Any],
        decision: str,
        suitability: str,
        comment: str,
        proposed_correction: str,
    ) -> None:
        envelope = self._envelope(snapshot_id)
        actor = self._account(actor_id)
        append_event(
            self._ledger_path,
            event_type=REVIEW_AUDIT_EVIDENCE_EVENT,
            object_id=str(target.get("object_id") or ""),
            object_version=str(target.get("object_version") or ""),
            actor=actor["username"],
            details={
                "snapshot_id": snapshot_id,
                "source_hash": str(envelope.get("sha256") or ""),
                "source_locator": _source_locator(target, str(envelope.get("locator") or "")),
                "review_snapshot_hash": compute_canonical_object_hash(target),
                "current_passage": str((target.get("content") or {}).get("clean_text") or ""),
                "decision": decision,
                "suitability": suitability,
                "comment": comment,
                "proposed_correction": proposed_correction,
            },
        )

    def review_object(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        if args:
            return super().review_object(*args, **kwargs)
        decision = map_eindoordeel(
            str(kwargs.get("eindoordeel") or ""),
            str(kwargs.get("decision") or ""),
        )
        suitability = str(kwargs.get("suitability") or "").strip()
        snapshot_id = str(kwargs.get("snapshot_id") or "")
        object_id = str(kwargs.get("object_id") or "")
        actor_id = str(kwargs.get("actor_id") or "")

        # Structural/batch paths without a passage disposition keep the existing
        # kernel semantics. Passage-review choices get the closed matrix.
        if suitability:
            if decision == "later":
                # Later is not a decision: do not mutate type, relation, register
                # or governance based on form choices that were not committed.
                deferred = dict(kwargs)
                for key in (
                    "suitability",
                    "eindoordeel",
                    "confirmed_object_type",
                    "recommendation_strength",
                    "documentpositie_action",
                    "found_under",
                    "parent_choice",
                    "type_action",
                ):
                    deferred[key] = None
                deferred["decision"] = "later"
                return super().review_object(**deferred)
            allowed = ALLOWED_FINAL_BY_SUITABILITY.get(suitability)
            if allowed is None or decision not in allowed:
                raise ConsoleError("review_disposition_conflict")
            if decision == "approve" and suitability == "alleen_onderbouwing":
                if not self._has_inbound_support(snapshot_id, object_id):
                    raise ConsoleError("support_relation_required")
            if decision == "reject":
                # Reject is a terminal exclusion from the active knowledge layer.
                kwargs["suitability"] = "geen_kenniseenheid"
                suitability = "geen_kenniseenheid"

        before = next(
            (row for row in self.snapshot_objects(snapshot_id) if row.get("object_id") == object_id),
            None,
        )
        updated = super().review_object(**kwargs)
        if before is not None and decision in {"revise", "reject"}:
            self._append_audit_evidence(
                actor_id=actor_id,
                snapshot_id=snapshot_id,
                target=before,
                decision=decision,
                suitability=suitability,
                comment=str(kwargs.get("comment") or "").strip(),
                proposed_correction=str(kwargs.get("proposed_correction") or "").strip(),
            )
        return updated

    def correct_object(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if args:
            return super().correct_object(*args, **kwargs)
        snapshot_id = str(kwargs.get("snapshot_id") or "")
        object_id = str(kwargs.get("object_id") or "")
        patch = kwargs.get("patch") or {}
        for op in patch.get("operations") or []:
            if op.get("op") != "set" or op.get("path") != "content.clean_text":
                continue
            candidate = _norm(str(op.get("value") or ""))
            current = next(
                (row for row in self.snapshot_objects(snapshot_id) if row.get("object_id") == object_id),
                None,
            )
            if current is None:
                raise ConsoleError("unknown_object")
            context = _source_context(current)
            if not candidate or candidate not in context:
                raise ConsoleError("correction_not_source_bound")
        return super().correct_object(**kwargs)

    def _reopen_for_review(self, snapshot_id: str, object_ids: set[str]) -> None:
        if not object_ids:
            return
        current, revision = self.snapshot_objects_and_revision(snapshot_id)
        live = {row["object_id"]: row for row in current}
        versions = {oid: str(live[oid]["object_version"]) for oid in object_ids if oid in live}
        rows = deepcopy(self._load_objects(snapshot_id))
        for row in rows:
            oid = str(row.get("object_id") or "")
            if oid not in versions or str(row.get("object_version") or "") != versions[oid]:
                continue
            governance = row.setdefault("governance", {})
            governance["validation_status"] = "needs_review"
            governance["validated_by"] = None
            governance["validation_date"] = None
            governance["review_snapshot_hash"] = None
            governance["publication_status"] = "unpublished"
            second = governance.get("second_review")
            if isinstance(second, dict) and second.get("required"):
                second["status"] = "pending"
                second["reviewer"] = None
                second["review_date"] = None
                second["snapshot_hash"] = None
        bindings = deepcopy(self._bindings)
        for oid in object_ids:
            bindings[snapshot_id] = invalidate_for_object(bindings.get(snapshot_id, []), oid)
        self._commit_prepared_store(
            objects=(snapshot_id, rows),
            bindings=bindings,
            expected_revision=revision,
        )

    def resolve_support_relation(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        support_object_id: str,
        claim_object_id: str,
    ) -> None:
        self._require_role(actor_id, "reviewer")
        current = {row["object_id"]: row for row in self.snapshot_objects(snapshot_id)}
        support = current.get(support_object_id)
        claim = current.get(claim_object_id)
        if support is None or claim is None or support_object_id == claim_object_id:
            raise ConsoleError("unknown_object")
        if (support.get("governance") or {}).get("validation_status") != "revise":
            raise ConsoleError("support_object_not_in_revise")
        if passage_register_of(support).get("status") != "linked_as_support":
            raise ConsoleError("support_disposition_required")
        relations = list(binding_relations(claim))
        if not any(
            rel.get("relation_type") == "supported_by"
            and rel.get("target_object_id") == support_object_id
            for rel in relations
        ):
            relations.append(
                {
                    "relation_type": "supported_by",
                    "target_object_id": support_object_id,
                    "confirmed": True,
                }
            )
            self.confirm_relations(
                actor_id=actor_id,
                snapshot_id=snapshot_id,
                object_id=claim_object_id,
                relations=relations,
            )
        self._reopen_for_review(snapshot_id, {support_object_id, claim_object_id})

    def audit_review_signals(self) -> list[dict[str, Any]]:
        return [
            event
            for event in reversed(read_events(self._ledger_path))
            if event.get("event_type") == REVIEW_AUDIT_EVIDENCE_EVENT
        ]


def install_closed_review_routes(app: FastAPI, console: ClosedLoopReviewConsole) -> None:
    """Expose repair work and read-only Review evidence inside Audit."""

    def account_for(request: Request) -> dict[str, Any]:
        return console.session_account(request.cookies.get("console_session"))

    def chrome(request: Request, body: str, current: str) -> str:
        from src.operations_console_app import _help, _nav, _page

        account = account_for(request)
        return _page(
            f"{_nav(account, current, console.waiting_task_counts(account['account_id']))}<section class='room'>{body}</section>{_help()}",
            title="Review herstel — V&amp;VN Data Services",
        )

    @app.get("/review/repair", response_class=HTMLResponse)
    def repair_home(request: Request) -> str:
        account = account_for(request)
        if not ({"researcher", "reviewer"} & set(account.get("roles") or [])):
            raise ConsoleError("researcher_role_required")
        cards: list[str] = []
        for envelope in console.list_envelopes():
            sid = envelope["snapshot_id"]
            for obj in console.snapshot_objects(sid):
                if (obj.get("governance") or {}).get("validation_status") != "revise":
                    continue
                text = str((obj.get("content") or {}).get("clean_text") or "")
                suit = str(passage_register_of(obj).get("suitability") or "")
                cards.append(
                    f"<article class='doc-card'><p class='doc-title'>{text}</p>"
                    f"<p>Status: herstel nodig · {suit or 'geen categorie'}</p>"
                    f"<p><a href='/review?document={sid}&object={obj['object_id']}'>Open in Review</a></p></article>"
                )
        return chrome(
            request,
            "<h1>Review — herstel nodig</h1><p class='lead'>Alleen actuele objectversies met status revise.</p>"
            + ("".join(cards) or "<p class='muted'>Geen herstelwerk.</p>")
            + "<p><a href='/audit/review-signals'>Bekijk signalen in Audit</a></p>",
            "review",
        )

    @app.post("/review/repair/source")
    def repair_source(
        request: Request,
        snapshot_id: str = Form(...),
        object_id: str = Form(...),
        corrected_text: str = Form(...),
        reason: str = Form(...),
    ) -> RedirectResponse:
        account = account_for(request)
        console.correct_object(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            patch={
                "reason": reason,
                "operations": [
                    {"op": "set", "path": "content.clean_text", "value": corrected_text}
                ],
            },
        )
        return RedirectResponse(f"/review?document={snapshot_id}&object={object_id}", status_code=303)

    @app.post("/review/repair/support")
    def repair_support(
        request: Request,
        snapshot_id: str = Form(...),
        support_object_id: str = Form(...),
        claim_object_id: str = Form(...),
    ) -> RedirectResponse:
        account = account_for(request)
        console.resolve_support_relation(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            support_object_id=support_object_id,
            claim_object_id=claim_object_id,
        )
        return RedirectResponse(f"/review?document={snapshot_id}&object={support_object_id}", status_code=303)

    @app.get("/audit/review-signals", response_class=HTMLResponse)
    def audit_review_signals(request: Request) -> str:
        account = account_for(request)
        if "researcher" not in set(account.get("roles") or []):
            raise ConsoleError("researcher_role_required")
        rows: list[str] = []
        for event in console.audit_review_signals():
            details = event.get("details") or {}
            rows.append(
                "<article class='doc-card'>"
                f"<p class='doc-title'>{details.get('current_passage') or event.get('object_id')}</p>"
                f"<p>{details.get('decision')} · {details.get('suitability')}</p>"
                f"<p>{details.get('comment') or ''}</p>"
                f"<p class='meta'>snapshot {details.get('snapshot_id')} · object {event.get('object_id')} · versie {event.get('object_version')}</p>"
                "</article>"
            )
        return chrome(
            request,
            "<p><a href='/audit'>← Terug naar Audit</a></p><h1>Signalen uit Review</h1>"
            "<p class='lead'>Append-only evidence van revise- en rejectbesluiten. Audit wijzigt geen kennisobjecten.</p>"
            + ("".join(rows) or "<p class='muted'>Nog geen signalen.</p>"),
            "audit",
        )
