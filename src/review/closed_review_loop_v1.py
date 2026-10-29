"""Closed Review resolution loop on top of the existing console kernel.

Reuses the existing review, revision, relation and ledger stores. No parallel
workflow store or service is introduced.
"""
from __future__ import annotations

import html
from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Iterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.integrity_kernel import compute_canonical_object_hash, stamp_canonical_hashes
from src.review.review_command_state_v1 import review_bindings_view
from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.vorming.passage_register_v1 import (
    apply_register_from_review,
    passage_register_of,
    register_status_from_suitability,
)
from src.review.proportionate_review_v1 import ProportionateReviewConsole
from src.publication.publish_authorization_v1 import invalidate_for_object
from src.review.review_cockpit_v1 import broncontext_parts, map_eindoordeel
from src.review.source_discrepancy_v1 import normalize as normalize_discrepancy
from src.review.review_ledger import append_event, read_events, read_command_events
from src.serving_relations_v1 import binding_relations

REVIEW_AUDIT_EVIDENCE_EVENT = "review_audit_evidence"
REVIEW_DISPOSITION_INCONSISTENT = "review_disposition_inconsistent"
ALLOWED_FINAL_BY_SUITABILITY = {
    "ja": {"approve", "revise", "reject"},
    "mist_context": {"revise", "reject"},
    "samenvoegen": {"revise", "reject"},
    "alleen_onderbouwing": {"revise", "approve", "reject"},
    "geen_kenniseenheid": {"reject"},
}


def _norm(value: str) -> str:
    return " ".join(str(value or "").split())


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


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
    """Console policy that makes every final Review outcome explicit."""

    def batch_review_normal_risk(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Commit the selected decisions and their evidence as one command."""
        with self._atomic_snapshot_mutation(str(kwargs.get("snapshot_id") or "")):
            return super().batch_review_normal_risk(**kwargs)

    def _has_inbound_support(self, snapshot_id: str, support_object_id: str) -> bool:
        return any(
            obj.get("object_id") != support_object_id
            and any(
                rel.get("relation_type") == "supported_by"
                and rel.get("target_object_id") == support_object_id
                for rel in binding_relations(obj)
            )
            for obj in self.snapshot_objects(snapshot_id)
        )

    def _latest_review_signal(
        self, object_id: str, *, decision: str = ""
    ) -> dict[str, Any] | None:
        for event in reversed(read_command_events(self._ledger_path)):
            if event.get("event_type") != REVIEW_AUDIT_EVIDENCE_EVENT:
                continue
            if str(event.get("object_id") or "") != object_id:
                continue
            if decision and str((event.get("details") or {}).get("decision") or "") != decision:
                continue
            return event
        return None

    def _append_audit_evidence(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        target: dict[str, Any],
        decision: str,
        original_suitability: str,
        final_disposition: str,
        comment: str,
        proposed_correction: str,
        prior_passage_status: str = "",
        source_discrepancy: list[str] | None = None,
    ) -> dict[str, Any]:
        envelope = self._envelope(snapshot_id)
        actor = self._account(actor_id)
        from src.review.source_discrepancy_v1 import DETAILS_KEY, FORMATION_KEY, formation_of
        return append_event(
            self._ledger_path,
            event_type=REVIEW_AUDIT_EVIDENCE_EVENT,
            object_id=str(target.get("object_id") or ""),
            object_version=str(target.get("object_version") or ""),
            actor=actor["username"],
            details={
                **({DETAILS_KEY: list(source_discrepancy), FORMATION_KEY: formation_of(target)}
                   if source_discrepancy else {}),
                "snapshot_id": snapshot_id,
                "source_hash": str(envelope.get("sha256") or ""),
                "source_locator": _source_locator(
                    target, str(envelope.get("locator") or "")
                ),
                "review_snapshot_hash": compute_canonical_object_hash(target),
                "current_passage": str(
                    (target.get("content") or {}).get("clean_text") or ""
                ),
                "decision": decision,
                "suitability": original_suitability,
                "original_suitability": original_suitability,
                "final_disposition": final_disposition,
                "prior_passage_status": prior_passage_status,
                "comment": comment,
                "proposed_correction": proposed_correction,
            },
        )

    def _restore_original_review_input(
        self,
        *,
        snapshot_id: str,
        object_id: str,
        original_suitability: str,
        original_eindoordeel: str,
    ) -> dict[str, Any]:
        """Keep reviewer input as evidence without turning revise terminal."""
        revision = self.objects_revision(snapshot_id)
        rows = deepcopy(self._load_objects(snapshot_id, remember=False))
        live = next(
            (
                row
                for row in self.snapshot_objects(snapshot_id)
                if row.get("object_id") == object_id
            ),
            None,
        )
        if live is None:
            raise ConsoleError("unknown_object")
        version = str(live.get("object_version") or "")
        updated: dict[str, Any] | None = None
        for index in range(len(rows) - 1, -1, -1):
            row = rows[index]
            if (
                row.get("object_id") != object_id
                or str(row.get("object_version") or "") != version
            ):
                continue
            row = deepcopy(row)
            metadata = dict(row.get("metadata") or {})
            passage = dict(metadata.get("review_passage") or {})
            passage["suitability"] = original_suitability
            passage["eindoordeel"] = original_eindoordeel
            metadata["review_passage"] = passage
            row["metadata"] = metadata
            stamp_canonical_hashes(row)
            rows[index] = row
            updated = row
            break
        if updated is None:
            raise ConsoleError("unknown_object")
        return self._commit_knowledge_change(snapshot_id, live, updated,
            reason="review repair context", actor="repair-command", retain_revise=True)

    def review_object(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        if args:
            return super().review_object(*args, **kwargs)
        decision = map_eindoordeel(
            str(kwargs.get("eindoordeel") or ""),
            str(kwargs.get("decision") or ""),
        )
        original_suitability = str(kwargs.get("suitability") or "").strip()
        original_eindoordeel = str(kwargs.get("eindoordeel") or "").strip()
        snapshot_id = str(kwargs.get("snapshot_id") or "")
        object_id = str(kwargs.get("object_id") or "")
        actor_id = str(kwargs.get("actor_id") or "")

        if original_suitability:
            if decision == "later":
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
            allowed = ALLOWED_FINAL_BY_SUITABILITY.get(original_suitability)
            if allowed is None or decision not in allowed:
                raise ConsoleError("review_disposition_conflict")
            if (
                decision == "approve"
                and original_suitability == "alleen_onderbouwing"
                and not self._has_inbound_support(snapshot_id, object_id)
            ):
                raise ConsoleError("support_relation_required")

        delegated = dict(kwargs)
        if decision == "revise" and original_suitability:
            delegated["suitability"] = None
            delegated["eindoordeel"] = None
            delegated["decision"] = "revise"

        if decision == "approve":
            with self._atomic_snapshot_mutation(snapshot_id):
                return super().review_object(**delegated)
        if decision not in {"revise", "reject"}:
            return super().review_object(**delegated)

        with self._atomic_snapshot_mutation(snapshot_id):
            before = next(
                (
                    row
                    for row in self.snapshot_objects(snapshot_id)
                    if row.get("object_id") == object_id
                ),
                None,
            )
            if before is None:
                raise ConsoleError("unknown_object")
            prior_status = str(passage_register_of(before).get("status") or "")
            super().review_object(**delegated)
            if decision == "revise":
                self._restore_original_review_input(
                    snapshot_id=snapshot_id,
                    object_id=object_id,
                    original_suitability=original_suitability,
                    original_eindoordeel=original_eindoordeel,
                )
            self._append_audit_evidence(
                actor_id=actor_id,
                snapshot_id=snapshot_id,
                target=before,
                decision=decision,
                original_suitability=original_suitability,
                final_disposition=(
                    "excluded_with_reason" if decision == "reject" else "repair_required"
                ),
                prior_passage_status=prior_status,
                comment=str(kwargs.get("comment") or "").strip(),
                proposed_correction=str(
                    kwargs.get("proposed_correction") or ""
                ).strip(),
                source_discrepancy=normalize_discrepancy(kwargs.get("source_discrepancy")),
            )
            return deepcopy(self.snapshot_objects(snapshot_id))

    def _current_object(self, snapshot_id: str, object_id: str) -> dict[str, Any]:
        current = next(
            (
                row
                for row in self.snapshot_objects(snapshot_id)
                if row.get("object_id") == object_id
            ),
            None,
        )
        if current is None:
            raise ConsoleError("unknown_object")
        return current

    def _validate_source_bound_patch(
        self,
        *,
        snapshot_id: str,
        object_id: str,
        patch: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        current = self._current_object(snapshot_id, object_id)
        candidates: list[str] = []
        for op in patch.get("operations") or []:
            if op.get("op") != "set" or op.get("path") != "content.clean_text":
                continue
            candidate = _norm(str(op.get("value") or ""))
            if not candidate or candidate not in _source_context(current):
                raise ConsoleError("correction_not_source_bound")
            candidates.append(candidate)
        return current, candidates

    def correct_object(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Neutralize the legacy auto-apply call; explicit repair bypasses this."""
        if args:
            return super().correct_object(*args, **kwargs)
        snapshot_id = str(kwargs.get("snapshot_id") or "")
        object_id = str(kwargs.get("object_id") or "")
        patch = kwargs.get("patch") or {}
        current = self._current_object(snapshot_id, object_id)
        operations = list(patch.get("operations") or [])
        signal = self._latest_review_signal(object_id, decision="revise")
        proposed = _norm(
            str(((signal or {}).get("details") or {}).get("proposed_correction") or "")
        )
        if (
            proposed
            and (current.get("governance") or {}).get("validation_status") == "revise"
            and len(operations) == 1
            and operations[0].get("op") == "set"
            and operations[0].get("path") == "content.clean_text"
            and _norm(str(operations[0].get("value") or "")) == proposed
        ):
            return deepcopy(current)
        from src.vorming.decision_unit_construction_v1 import KEY
        from src.review.beslisboom_path_v1 import review_path_for_klasse
        if not (review_path_for_klasse(self._envelope(snapshot_id)["class"]) == "boom"
                and (current.get("metadata") or {}).get(KEY)):
            self._validate_source_bound_patch(
                snapshot_id=snapshot_id, object_id=object_id, patch=patch
            )
        # Constructed units are validated by the kernel against immutable source
        # fragments, including explicit merge refs unavailable in this text view.
        return super().correct_object(**kwargs)

    def _clear_pending_review_metadata(
        self, *, snapshot_id: str, object_id: str
    ) -> dict[str, Any]:
        revision = self.objects_revision(snapshot_id)
        rows = deepcopy(self._load_objects(snapshot_id, remember=False))
        live = self._current_object(snapshot_id, object_id)
        version = str(live.get("object_version") or "")
        updated: dict[str, Any] | None = None
        for index in range(len(rows) - 1, -1, -1):
            row = rows[index]
            if (
                row.get("object_id") != object_id
                or str(row.get("object_version") or "") != version
            ):
                continue
            row = deepcopy(row)
            metadata = dict(row.get("metadata") or {})
            metadata.pop("review_passage", None)
            row["metadata"] = metadata
            stamp_canonical_hashes(row)
            rows[index] = row
            updated = row
            break
        if updated is None:
            raise ConsoleError("unknown_object")
        return self._commit_knowledge_change(snapshot_id, live, updated,
            reason="clear repair context", actor="repair-command")

    def _reopen_for_review(self, snapshot_id: str, object_ids: set[str]) -> None:
        if not object_ids:
            return
        current, revision = self.snapshot_objects_and_revision(snapshot_id)
        live = {row["object_id"]: row for row in current}
        versions = {
            oid: str(live[oid]["object_version"])
            for oid in object_ids
            if oid in live
        }
        rows = deepcopy(self._load_objects(snapshot_id, remember=False))
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
                second.update(
                    {
                        "status": "pending",
                        "reviewer": None,
                        "review_date": None,
                        "snapshot_hash": None,
                    }
                )
        bindings = deepcopy(review_bindings_view(self))
        for oid in object_ids:
            bindings[snapshot_id] = invalidate_for_object(
                bindings.get(snapshot_id, []), oid
            )
        self._commit_prepared_store(
            objects=(snapshot_id, rows),
            bindings=bindings,
            expected_revision=revision,
        )

    def _mark_support_disposition(
        self, *, snapshot_id: str, support_object_id: str
    ) -> None:
        revision = self.objects_revision(snapshot_id)
        rows = deepcopy(self._load_objects(snapshot_id, remember=False))
        live = self._current_object(snapshot_id, support_object_id)
        version = str(live.get("object_version") or "")
        for index in range(len(rows) - 1, -1, -1):
            row = rows[index]
            if (
                row.get("object_id") != support_object_id
                or str(row.get("object_version") or "") != version
            ):
                continue
            row = apply_register_from_review(
                deepcopy(row), suitability="alleen_onderbouwing"
            )
            metadata = dict(row.get("metadata") or {})
            metadata.pop("review_passage", None)
            row["metadata"] = metadata
            stamp_canonical_hashes(row)
            updated = row
            break
        self._commit_knowledge_change(snapshot_id, live, updated,
            reason="support disposition context change", actor="support-command")

    def resolve_support_relation(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        support_object_id: str,
        claim_object_id: str,
        expected_revision: str = "",
    ) -> None:
        self._require_role(actor_id, "reviewer")
        envelope = self._envelope(snapshot_id)
        if actor_id not in (envelope.get("named_reviewers") or []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        if not expected_revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
        with self._atomic_snapshot_mutation(snapshot_id):
            if self.objects_revision(snapshot_id) != expected_revision:
                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
            current = {row["object_id"]: row for row in self.snapshot_objects(snapshot_id)}
            support = current.get(support_object_id)
            claim = current.get(claim_object_id)
            if support is None or claim is None or support_object_id == claim_object_id:
                raise ConsoleError("unknown_object")
            if (support.get("governance") or {}).get("validation_status") != "revise":
                raise ConsoleError("support_object_not_in_revise")
            pending = self._latest_review_signal(support_object_id, decision="revise")
            original = str(
                ((pending or {}).get("details") or {}).get("original_suitability")
                or ""
            )
            if original != "alleen_onderbouwing":
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
                    expected_revision=expected_revision,
                )
            self._reopen_for_review(snapshot_id, {support_object_id, claim_object_id})
            self._mark_support_disposition(
                snapshot_id=snapshot_id, support_object_id=support_object_id
            )
            current_support = self._current_object(snapshot_id, support_object_id)
            self._append_audit_evidence(
                actor_id=actor_id,
                snapshot_id=snapshot_id,
                target=current_support,
                decision="repair_support",
                original_suitability=original,
                final_disposition="linked_as_support",
                comment=f"support relation to {claim_object_id}",
                proposed_correction="",
            )

    def _disposition_conflicts(
        self,
        snapshot_id: str,
        *,
        objects: list[dict[str, Any]] | None = None,
        bindings: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        current_rows = (
            self.snapshot_objects(snapshot_id) if objects is None else list(objects)
        )
        current = {row["object_id"]: row for row in current_rows}
        if bindings is None:
            try:
                binding_rows = self.object_review_bindings(
                    snapshot_id, objects=current_rows
                )
            except TypeError:
                binding_rows = self.object_review_bindings(snapshot_id)
        else:
            binding_rows = list(bindings)
        conflicts: list[str] = []
        for binding in binding_rows:
            if not binding.get("valid") or binding.get("decision") != "approve":
                continue
            suitability = str(binding.get("suitability") or "").strip()
            if not suitability:
                continue
            object_id = str(binding.get("object_id") or "")
            obj = current.get(object_id)
            if obj is None:
                conflicts.append(object_id)
                continue
            try:
                expected = register_status_from_suitability(suitability)
            except ValueError:
                conflicts.append(object_id)
                continue
            if str(passage_register_of(obj).get("status") or "") != expected:
                conflicts.append(object_id)
        return list(dict.fromkeys(conflicts))

    def technical_publication_readiness(
        self,
        *,
        snapshot_id: str,
        envelope: dict[str, Any] | None = None,
        objects: list[dict[str, Any]] | None = None,
        bindings: list[dict[str, Any]] | None = None,
        fragments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        considered = super().technical_publication_readiness(
            snapshot_id=snapshot_id,
            envelope=envelope,
            objects=objects,
            bindings=bindings,
            fragments=fragments,
        )
        try:
            conflicts = self._disposition_conflicts(
                snapshot_id,
                objects=objects,
                bindings=bindings,
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            conflicts = self._disposition_conflicts(snapshot_id)
        considered["disposition_consistent"] = not conflicts
        if conflicts:
            blockers = list(considered.get("blockers") or [])
            if REVIEW_DISPOSITION_INCONSISTENT not in blockers:
                blockers.append(REVIEW_DISPOSITION_INCONSISTENT)
            considered["blockers"] = blockers
            considered["publish_allowed"] = False
            considered["disposition_conflict_object_ids"] = conflicts
        return considered

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        self._require_role(actor_id, "publisher")
        from src.publication.publication_readiness_v1 import derive_publication_readiness
        return derive_publication_readiness(self, snapshot_id)

    def select_for_question(self, *, family: str, asked_class: str) -> list[dict[str, Any]]:
        """Do not expose pending, revise or rejected objects to question selection."""
        selected = super().select_for_question(family=family, asked_class=asked_class)
        out: list[dict[str, Any]] = []
        for item in selected:
            obj = next(
                (
                    row
                    for row in self.snapshot_objects(str(item.get("snapshot_id") or ""))
                    if row.get("object_id") == item.get("object_id")
                ),
                None,
            )
            if obj is None:
                continue
            if (obj.get("governance") or {}).get("validation_status") != "approved":
                continue
            if passage_register_of(obj).get("status") in {
                "excluded_with_reason",
                "not_yet_assessed",
            }:
                continue
            out.append(item)
        return out

    def audit_review_signals(self) -> list[dict[str, Any]]:
        return [
            event
            for event in reversed(read_events(self._ledger_path))
            if event.get("event_type") == REVIEW_AUDIT_EVIDENCE_EVENT
        ]


def install_closed_review_routes(app: FastAPI, console: ClosedLoopReviewConsole) -> None:
    """Read-only Review evidence in Inzicht."""

    def account_for(request: Request) -> dict[str, Any]:
        return console.session_account(request.cookies.get("console_session"))

    def chrome(request: Request, body: str, current: str, *, title: str = "Review herstel — V&amp;VN Data Services") -> str:
        from src.operations_console_app import _nav, _page

        account = account_for(request)
        return _page(
            f"{_nav(account, current)}"
            f"<section class='room'>{body}</section>",
            title=title,
        )

    @app.get("/audit/review-signals", include_in_schema=False)
    def legacy_review_signals(request: Request) -> RedirectResponse:
        account_for(request)
        query = request.url.query
        return RedirectResponse("/inzicht/reviewsignalen" + ("?" + query if query else ""), status_code=303)

    @app.get("/inzicht/reviewsignalen", response_class=HTMLResponse)
    def audit_review_signals(request: Request) -> str:
        from src.settings.insight_v1 import insight_tabs
        account = account_for(request)
        if "researcher" not in set(account.get("roles") or []):
            raise ConsoleError("researcher_role_required")
        rows: list[str] = []
        for event in console.audit_review_signals():
            details = event.get("details") or {}
            rows.append(
                "<article class='doc-card'>"
                f"<p class='doc-title'>{_esc(details.get('current_passage') or event.get('object_id'))}</p>"
                f"<p>{_esc(details.get('decision'))} · "
                f"{_esc(details.get('original_suitability') or details.get('suitability'))} → "
                f"{_esc(details.get('final_disposition'))}</p>"
                f"<p>{_esc(details.get('comment') or '')}</p>"
                f"<p class='meta'>snapshot {_esc(details.get('snapshot_id'))} · "
                f"object {_esc(event.get('object_id'))} · versie {_esc(event.get('object_version'))}</p>"
                "</article>"
            )
        return chrome(
            request,
            insight_tabs("controles") + "<p><a href='/inzicht?tab=controles'>← Inzicht · Controles</a></p>"
            "<h1>Signalen uit Review</h1>"
            "<p class='lead'>Append-only evidence van review en herstel. "
            "Deze pagina wijzigt geen kennisobjecten.</p>"
            "<p><a class='btn-secondary' href='/review/repair'>Open herstelwerk in Review</a></p>"
            + ("".join(rows) or "<p class='muted'>Nog geen signalen.</p>"),
            "settings", title="Reviewsignalen — Inzicht — Metis",
        )
