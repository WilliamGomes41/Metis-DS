"""Final closure hardening for deterministic Review repair.

Keeps one writable Review -> resolve path. Legacy free-text repair remains
unavailable, repair evidence is reconstructable, and old persisted ``revise``
records are safely reopened for the new Review flow at startup.
"""
from __future__ import annotations

import html
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from typing import Any, Iterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from src.closed_review_loop_v1 import (
    REVIEW_AUDIT_EVIDENCE_EVENT,
    _source_locator,
)
from src.deterministic_review_repair_v1 import (
    REPAIR_CLASSIFICATION,
    REPAIR_MERGE_OBJECTS,
    REPAIR_SOURCE_UNITS,
    REPAIR_SUPPORT_RELATION,
    DeterministicRepairReviewConsole,
)
from src.integrity_kernel import compute_canonical_object_hash, schema_errors, stamp_canonical_hashes
from src.operations_console_v1 import ConsoleError
from src.publication_readiness_v1 import PublicationReadinessMixin
from src.review.review_ledger import append_event

LEGACY_REVISE_REOPENED_EVENT = "legacy_revise_reopened"
PUBLISHED_WORKING_REVISION_IMMUTABLE = "published_working_revision_immutable"
_REPAIR_EVIDENCE: ContextVar[dict[str, Any] | None] = ContextVar(
    "metis_repair_evidence", default=None
)
_LEGACY_REPAIR_PATHS = frozenset(
    {"/review/repair", "/review/repair/source", "/review/repair/support"}
)


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


@contextmanager
def _repair_evidence(spec: dict[str, Any]) -> Iterator[None]:
    token = _REPAIR_EVIDENCE.set(deepcopy(spec))
    try:
        yield
    finally:
        _REPAIR_EVIDENCE.reset(token)


class ReviewClosureConsole(PublicationReadinessMixin, DeterministicRepairReviewConsole):
    """One-path Review repair with migration and reconstructable evidence."""

    def repair_source(self, **_kwargs: Any) -> dict[str, Any]:
        """The old free-text canonical repair path is permanently disabled."""
        raise ConsoleError("legacy_free_text_repair_disabled")

    def _require_mutable_working_revision(self, snapshot_id: str) -> None:
        """Published work is historical input, never current review work."""
        if snapshot_id and self.snapshot_is_published(snapshot_id):
            raise ConsoleError(PUBLISHED_WORKING_REVISION_IMMUTABLE)

    @staticmethod
    def _changed_snapshot_ids(
        current: dict[str, Any], prepared: dict[str, Any]
    ) -> set[str]:
        keys = set(current) | set(prepared)
        return {
            str(key)
            for key in keys
            if current.get(key) != prepared.get(key)
        }

    def _guard_prepared_working_revision_mutation(
        self,
        *,
        envelopes: dict[str, Any] | None,
        bindings: dict[str, Any] | None,
        objects: tuple[str, list[dict[str, Any]]] | None,
        snapshot_id: str | None,
    ) -> None:
        """Seal every curation commit, not only named Review entry points.

        File-backed and Azure-without-workflow-Postgres topologies otherwise let
        direct helpers such as ``confirm_object_type`` and ``confirm_relations``
        reach the generic commit boundary without passing through ``review_object``.
        """
        candidates: set[str] = set()
        if snapshot_id:
            candidates.add(str(snapshot_id))
        if objects is not None:
            candidates.add(str(objects[0]))
        if envelopes is not None:
            candidates.update(
                self._changed_snapshot_ids(
                    dict(getattr(self, "_envelopes", {})), envelopes
                )
            )
        if bindings is not None:
            candidates.update(
                self._changed_snapshot_ids(
                    dict(getattr(self, "_bindings", {})), bindings
                )
            )

        for candidate in sorted(value for value in candidates if value):
            try:
                self._require_mutable_working_revision(candidate)
            except ConsoleError as exc:
                # A brand-new ingest is not a mutation of an existing
                # WorkingRevision and may reach the commit boundary before the
                # envelope exists in the current store.
                if exc.code == "unknown_snapshot":
                    continue
                raise

    def _commit_prepared_store(
        self,
        *,
        envelopes: dict[str, Any] | None = None,
        bindings: dict[str, Any] | None = None,
        objects: tuple[str, list[dict[str, Any]]] | None = None,
        expected_revision: str | None = None,
        ledger_fn: Any | None = None,
        snapshot_id: str | None = None,
    ) -> None:
        self._guard_prepared_working_revision_mutation(
            envelopes=envelopes,
            bindings=bindings,
            objects=objects,
            snapshot_id=snapshot_id,
        )
        return super()._commit_prepared_store(
            envelopes=envelopes,
            bindings=bindings,
            objects=objects,
            expected_revision=expected_revision,
            ledger_fn=ledger_fn,
            snapshot_id=snapshot_id,
        )

    @contextmanager
    def _atomic_snapshot_mutation(self, snapshot_id: str) -> Iterator[None]:
        self._require_mutable_working_revision(snapshot_id)
        with super()._atomic_snapshot_mutation(snapshot_id):
            yield

    def review_object(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        snapshot_id = str(kwargs.get("snapshot_id") or "")
        self._require_mutable_working_revision(snapshot_id)
        return super().review_object(*args, **kwargs)

    def correct_object(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        snapshot_id = str(kwargs.get("snapshot_id") or "")
        self._require_mutable_working_revision(snapshot_id)
        return super().correct_object(*args, **kwargs)

    def repair_kind_for_submission(self, submission: dict[str, Any]) -> str:
        suitability = str(submission.get("suitability") or "")
        if suitability == "samenvoegen":
            return REPAIR_MERGE_OBJECTS
        if suitability == "alleen_onderbouwing":
            return REPAIR_SUPPORT_RELATION
        if suitability != "ja":
            return REPAIR_SOURCE_UNITS

        snapshot_id = str(submission.get("snapshot_id") or "")
        object_id = str(submission.get("object_id") or "")
        current = self._current_object(snapshot_id, object_id)
        current_type = str(
            current.get("confirmed_object_type")
            or current.get("object_type")
            or ""
        )
        requested_type = str(submission.get("confirmed_object_type") or "")
        type_change = (
            submission.get("type_action") == "type_wijzigen"
            and bool(requested_type)
            and requested_type != current_type
        )

        requested_parent = str(submission.get("parent_choice") or "")
        current_parent = str(current.get("parent_object_id") or "")
        position_change = (
            submission.get("documentpositie_action") == "andere_kop"
            and bool(requested_parent)
            and requested_parent != current_parent
        )

        requested_strength = str(submission.get("recommendation_strength") or "")
        current_strength = str(current.get("confirmed_recommendation_strength") or "")
        strength_change = bool(requested_strength) and requested_strength != current_strength

        if type_change or position_change or strength_change:
            return REPAIR_CLASSIFICATION
        return REPAIR_SOURCE_UNITS

    def _finalize_source_provenance(
        self,
        *,
        snapshot_id: str,
        object_id: str,
        source_refs: list[dict[str, Any]],
        repair_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Update source refs without replacing the revision engine's patch hash."""
        _ = repair_spec
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
            row.setdefault("provenance", {})["source_fragments"] = deepcopy(source_refs)
            stamp_canonical_hashes(row)
            errors = schema_errors(row, self.schema_path)
            if errors:
                raise ConsoleError("revision_schema_invalid", " | ".join(errors))
            rows[index] = row
            updated = row
            break
        if updated is None:
            raise ConsoleError("unknown_object")
        self._commit_prepared_store(
            objects=(snapshot_id, rows), expected_revision=revision
        )
        return deepcopy(updated)

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
    ) -> dict[str, Any]:
        envelope = self._envelope(snapshot_id)
        actor = self._account(actor_id)
        details: dict[str, Any] = {
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
        }
        repair_spec = _REPAIR_EVIDENCE.get()
        if repair_spec:
            details["repair_spec"] = deepcopy(repair_spec)
        return append_event(
            self._ledger_path,
            event_type=REVIEW_AUDIT_EVIDENCE_EVENT,
            object_id=str(target.get("object_id") or ""),
            object_version=str(target.get("object_version") or ""),
            actor=actor["username"],
            details=details,
        )

    def submit_review_resolution(self, **kwargs: Any) -> dict[str, Any]:
        snapshot_id = str(kwargs.get("snapshot_id") or "")
        self._require_mutable_working_revision(snapshot_id)
        repair_kind = str(kwargs.get("repair_kind") or "")
        spec: dict[str, Any] = {"repair_kind": repair_kind}
        if repair_kind == REPAIR_SOURCE_UNITS:
            object_id = str(kwargs.get("object_id") or "")
            units = self.source_units(snapshot_id=snapshot_id, object_id=object_id)
            by_id = {row["unit_id"]: row for row in units}
            selected = list(
                dict.fromkeys(
                    str(value).strip()
                    for value in (kwargs.get("source_unit_ids") or [])
                    if str(value).strip()
                )
            )
            spec["source_units"] = [
                {
                    "unit_id": unit_id,
                    "fragment_id": by_id[unit_id]["fragment_id"],
                    "fragment_hash": by_id[unit_id]["fragment_hash"],
                }
                for unit_id in selected
                if unit_id in by_id
            ]
        elif repair_kind == REPAIR_MERGE_OBJECTS:
            spec["merge_object_ids"] = list(
                dict.fromkeys(str(value).strip() for value in (kwargs.get("merge_object_ids") or []) if str(value).strip())
            )
        elif repair_kind == REPAIR_SUPPORT_RELATION:
            spec["claim_object_id"] = str(kwargs.get("claim_object_id") or "")
        elif repair_kind == REPAIR_CLASSIFICATION:
            spec.update(
                {
                    "confirmed_object_type": str(kwargs.get("confirmed_object_type") or ""),
                    "recommendation_strength": str(kwargs.get("recommendation_strength") or ""),
                    "parent_choice": str(kwargs.get("parent_choice") or ""),
                }
            )
        with _repair_evidence(spec):
            return super().submit_review_resolution(**kwargs)

    def migrate_legacy_revise_to_review(self) -> int:
        """Reopen legacy revise work, but never reopen a published WorkingRevision."""
        migrated = 0
        for envelope in self.list_envelopes():
            snapshot_id = str(envelope.get("snapshot_id") or "")
            if self.snapshot_is_published(snapshot_id):
                continue
            current = self.snapshot_objects(snapshot_id)
            object_ids = {
                str(row.get("object_id") or "")
                for row in current
                if (row.get("governance") or {}).get("validation_status") == "revise"
            }
            object_ids.discard("")
            if not object_ids:
                continue
            with self._atomic_snapshot_mutation(snapshot_id):
                self._reopen_for_review(snapshot_id, object_ids)
                for object_id in sorted(object_ids):
                    self._clear_pending_review_metadata(
                        snapshot_id=snapshot_id, object_id=object_id
                    )
                    current_obj = self._current_object(snapshot_id, object_id)
                    append_event(
                        self._ledger_path,
                        event_type=LEGACY_REVISE_REOPENED_EVENT,
                        object_id=object_id,
                        object_version=str(current_obj.get("object_version") or ""),
                        actor="migration",
                        details={
                            "snapshot_id": snapshot_id,
                            "reason": "structured_review_repair_required",
                        },
                    )
                    migrated += 1
        return migrated


def harden_legacy_repair_routes(app: FastAPI, console: ReviewClosureConsole) -> None:
    """Remove legacy repair forms/writes and replace them with read-only recovery."""
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if str(getattr(route, "path", "")) not in _LEGACY_REPAIR_PATHS
    ]

    @app.get("/review/repair", response_class=HTMLResponse)
    def review_recovery(request: Request) -> str:
        account = console.session_account(request.cookies.get("console_session"))
        roles = set(account.get("roles") or [])
        if not ({"researcher", "reviewer"} & roles):
            raise ConsoleError("researcher_role_required")
        cards: list[str] = []
        for envelope in console.list_envelopes():
            snapshot_id = str(envelope.get("snapshot_id") or "")
            allowed = (
                "researcher" in roles
                and envelope.get("uploader_account_id") == account["account_id"]
            ) or (
                "reviewer" in roles
                and account["account_id"] in (envelope.get("named_reviewers") or [])
            )
            if not allowed:
                continue
            for obj in console.snapshot_objects(snapshot_id):
                if (obj.get("governance") or {}).get("validation_status") != "revise":
                    continue
                object_id = str(obj.get("object_id") or "")
                text = str((obj.get("content") or {}).get("clean_text") or object_id)
                cards.append(
                    "<article class='doc-card'>"
                    f"<p class='doc-title'>{_esc(text)}</p>"
                    "<p>Legacy herstelstatus. Dit object moet opnieuw via Review worden beoordeeld.</p>"
                    f"<p><a href='/review?document={_esc(snapshot_id)}&amp;object={_esc(object_id)}'>Open in Review</a></p>"
                    "</article>"
                )
        from src.operations_console_app import _nav, _page

        body = (
            f"{_nav(account, 'review', console.waiting_task_counts(account['account_id']))}"
            "<section class='room'><h1>Review — herstelstatus</h1>"
            "<p class='lead'>Alleen read-only herstelzicht. Canonieke correcties lopen uitsluitend via Review → correctie specificeren.</p>"
            + ("".join(cards) or "<p class='muted'>Geen achtergebleven herstelwerk.</p>")
            + "</section>"
        )
        return _page(body, title="Review herstel — V&amp;VN Data Services")
