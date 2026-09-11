"""Closed Review resolution loop on top of the existing console kernel.

Reuses the existing review, revision, relation and ledger stores. No parallel
workflow store or service is introduced.
"""
from __future__ import annotations

import html
from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Iterator
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.integrity_kernel import compute_canonical_object_hash, stamp_canonical_hashes
from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.passage_register_v1 import (
    apply_register_from_review,
    passage_register_of,
    register_status_from_suitability,
)
from src.proportionate_review_v1 import ProportionateReviewConsole
from src.publish_authorization_v1 import invalidate_for_object
from src.review_cockpit_v1 import broncontext_parts, map_eindoordeel
from src.review_ledger import append_event, read_events
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


def _review_url(snapshot_id: str, object_id: str = "") -> str:
    target = f"/review?document={quote(snapshot_id, safe='')}"
    if object_id:
        target += f"&object={quote(object_id, safe='')}"
    return target


class ClosedLoopReviewConsole(ProportionateReviewConsole):
    """Console policy that makes every final Review outcome explicit."""

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
                and ("needs_review" in statuses or "revise" in statuses)
            ):
                review += 1
        counts["ingest"] = ingest if "researcher" in roles else 0
        counts["review"] = review if "reviewer" in roles else 0
        return counts

    @contextmanager
    def _atomic_snapshot_mutation(self, snapshot_id: str) -> Iterator[None]:
        """Rollback object/binding/envelope writes together with ledger evidence."""
        with self._store_write_lock():
            path = self._objects_path(snapshot_id)
            prior_objects = path.read_bytes() if path.exists() else None
            prior_envelopes = deepcopy(self._envelopes)
            prior_bindings = deepcopy(self._bindings)
            prior_ledger = self._ledger_path.stat().st_size if self._ledger_path.exists() else 0
            try:
                yield
            except Exception:
                self._rollback_store_files(
                    objects_snapshot=(snapshot_id, prior_objects),
                    envelopes=prior_envelopes,
                    bindings=prior_bindings,
                    ledger_size=prior_ledger,
                )
                self._envelopes = prior_envelopes
                self._bindings = prior_bindings
                self.refresh_objects_expected_revision(snapshot_id)
                raise

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
        for event in reversed(read_events(self._ledger_path)):
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
    ) -> dict[str, Any]:
        envelope = self._envelope(snapshot_id)
        actor = self._account(actor_id)
        return append_event(
            self._ledger_path,
            event_type=REVIEW_AUDIT_EVIDENCE_EVENT,
            object_id=str(target.get("object_id") or ""),
            object_version=str(target.get("object_version") or ""),
            actor=actor["username"],
            details={
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
        self._commit_prepared_store(
            objects=(snapshot_id, rows), expected_revision=revision
        )
        return deepcopy(updated)

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
        elif decision == "reject" and original_suitability:
            delegated["suitability"] = "geen_kenniseenheid"

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
        self._validate_source_bound_patch(
            snapshot_id=snapshot_id, object_id=object_id, patch=patch
        )
        return super().correct_object(**kwargs)

    def _require_repair_access(
        self, *, actor_id: str, snapshot_id: str
    ) -> dict[str, Any]:
        account = self._account(actor_id)
        roles = set(account.get("roles") or [])
        envelope = self._envelope(snapshot_id)
        allowed = (
            "researcher" in roles
            and envelope.get("uploader_account_id") == actor_id
        ) or (
            "reviewer" in roles
            and actor_id in (envelope.get("named_reviewers") or [])
        )
        if not allowed:
            raise ConsoleError("correction_role_required")
        return account

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
        self._commit_prepared_store(
            objects=(snapshot_id, rows), expected_revision=revision
        )
        return deepcopy(updated)

    def repair_source(
        self,
        *,
        actor_id: str,
        snapshot_id: str,
        object_id: str,
        corrected_text: str,
        reason: str,
        expected_revision: str,
    ) -> dict[str, Any]:
        self._require_repair_access(actor_id=actor_id, snapshot_id=snapshot_id)
        if not expected_revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
        patch = {
            "reason": reason.strip(),
            "operations": [
                {"op": "set", "path": "content.clean_text", "value": corrected_text}
            ],
        }
        with self._atomic_snapshot_mutation(snapshot_id):
            if self.objects_revision(snapshot_id) != expected_revision:
                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
            current, _ = self._validate_source_bound_patch(
                snapshot_id=snapshot_id, object_id=object_id, patch=patch
            )
            if (current.get("governance") or {}).get("validation_status") != "revise":
                raise ConsoleError("repair_object_not_in_revise")
            revised = super().correct_object(
                actor_id=actor_id,
                snapshot_id=snapshot_id,
                object_id=object_id,
                patch=patch,
            )
            revised = self._clear_pending_review_metadata(
                snapshot_id=snapshot_id, object_id=object_id
            )
            signal = self._latest_review_signal(object_id, decision="revise")
            original = str(
                ((signal or {}).get("details") or {}).get("original_suitability")
                or ""
            )
            self._append_audit_evidence(
                actor_id=actor_id,
                snapshot_id=snapshot_id,
                target=revised,
                decision="repair",
                original_suitability=original,
                final_disposition="needs_review",
                comment=reason.strip(),
                proposed_correction="",
            )
            return deepcopy(revised)

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
        bindings = deepcopy(self._bindings)
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
            rows[index] = row
            break
        self._commit_prepared_store(
            objects=(snapshot_id, rows), expected_revision=revision
        )

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

    def _disposition_conflicts(self, snapshot_id: str) -> list[str]:
        objects = {row["object_id"]: row for row in self.snapshot_objects(snapshot_id)}
        conflicts: list[str] = []
        for binding in self.object_review_bindings(snapshot_id):
            if not binding.get("valid") or binding.get("decision") != "approve":
                continue
            suitability = str(binding.get("suitability") or "").strip()
            if not suitability:
                continue
            object_id = str(binding.get("object_id") or "")
            obj = objects.get(object_id)
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

    def consider_publish(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        considered = super().consider_publish(actor_id=actor_id, snapshot_id=snapshot_id)
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
    """Revision-pinned repair routes plus read-only Review evidence in Audit."""

    def account_for(request: Request) -> dict[str, Any]:
        return console.session_account(request.cookies.get("console_session"))

    def chrome(request: Request, body: str, current: str) -> str:
        from src.operations_console_app import _help, _nav, _page

        account = account_for(request)
        return _page(
            f"{_nav(account, current, console.waiting_task_counts(account['account_id']))}"
            f"<section class='room'>{body}</section>{_help()}",
            title="Review herstel — V&amp;VN Data Services",
        )

    @app.get("/review/repair", response_class=HTMLResponse)
    def repair_home(request: Request, document: str = "", object: str = "") -> str:
        account = account_for(request)
        roles = set(account.get("roles") or [])
        if not ({"researcher", "reviewer"} & roles):
            raise ConsoleError("researcher_role_required")
        cards: list[str] = []
        for envelope in console.list_envelopes():
            sid = str(envelope["snapshot_id"])
            if document and sid != document:
                continue
            allowed = (
                "researcher" in roles
                and envelope.get("uploader_account_id") == account["account_id"]
            ) or (
                "reviewer" in roles
                and account["account_id"] in (envelope.get("named_reviewers") or [])
            )
            if not allowed:
                continue
            current, revision = console.snapshot_objects_and_revision(sid)
            for obj in current:
                oid = str(obj.get("object_id") or "")
                if object and oid != object:
                    continue
                if (obj.get("governance") or {}).get("validation_status") != "revise":
                    continue
                text = str((obj.get("content") or {}).get("clean_text") or "")
                signal = console._latest_review_signal(oid, decision="revise")
                details = (signal or {}).get("details") or {}
                suitability = str(
                    details.get("original_suitability")
                    or details.get("suitability")
                    or ""
                )
                proposed = str(details.get("proposed_correction") or "")
                comment = str(details.get("comment") or "")
                if suitability == "alleen_onderbouwing":
                    options = []
                    for claim in current:
                        claim_id = str(claim.get("object_id") or "")
                        if (
                            not claim_id
                            or claim_id == oid
                            or claim.get("object_type") == "document"
                            or (claim.get("governance") or {}).get("validation_status")
                            == "rejected"
                        ):
                            continue
                        claim_text = str(
                            (claim.get("content") or {}).get("clean_text") or claim_id
                        )
                        options.append(
                            f'<option value="{_esc(claim_id)}">'
                            f'{_esc(claim_text[:180])}</option>'
                        )
                    action = (
                        '<form method="post" action="/review/repair/support">'
                        f'<input type="hidden" name="snapshot_id" value="{_esc(sid)}">'
                        f'<input type="hidden" name="support_object_id" value="{_esc(oid)}">'
                        f'<input type="hidden" name="snapshot_revision" value="{_esc(revision)}">'
                        '<label>Koppel als onderbouwing aan kennisobject'
                        f'<select name="claim_object_id" required>{"".join(options)}</select></label>'
                        '<button class="btn-primary" type="submit">Onderbouwing koppelen</button>'
                        '</form>'
                    ) if options else (
                        '<p class="muted">Geen geschikt kennisobject beschikbaar om aan te koppelen.</p>'
                    )
                else:
                    action = (
                        '<form method="post" action="/review/repair/source">'
                        f'<input type="hidden" name="snapshot_id" value="{_esc(sid)}">'
                        f'<input type="hidden" name="object_id" value="{_esc(oid)}">'
                        f'<input type="hidden" name="snapshot_revision" value="{_esc(revision)}">'
                        '<label>Herstelde, brongebonden passage'
                        f'<textarea name="corrected_text" required>{_esc(proposed)}</textarea></label>'
                        '<label>Reden voor herstel'
                        f'<textarea name="reason" required>{_esc(comment)}</textarea></label>'
                        '<button class="btn-primary" type="submit">Herstel uitvoeren</button>'
                        '</form>'
                    )
                cards.append(
                    "<article class='doc-card'>"
                    f"<p class='doc-title'>{_esc(text)}</p>"
                    f"<p>Status: herstel nodig · {_esc(suitability or 'geen categorie')}</p>"
                    f"{action}"
                    f"<p><a href='{_esc(_review_url(sid, oid))}'>Terug naar Review</a></p>"
                    "</article>"
                )
        return chrome(
            request,
            "<h1>Review — herstel nodig</h1>"
            "<p class='lead'>Voorgestelde correcties worden hier pas expliciet uitgevoerd. "
            "Elk formulier is gebonden aan de getoonde snapshot-revisie.</p>"
            + ("".join(cards) or "<p class='muted'>Geen herstelwerk.</p>")
            + "<p><a href='/audit/review-signals'>Bekijk signalen in Audit</a></p>",
            "review",
        )

    @app.post("/review/repair/source")
    def repair_source_route(
        request: Request,
        snapshot_id: str = Form(...),
        object_id: str = Form(...),
        corrected_text: str = Form(...),
        reason: str = Form(...),
        snapshot_revision: str = Form(...),
    ) -> RedirectResponse:
        account = account_for(request)
        console.repair_source(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            corrected_text=corrected_text,
            reason=reason,
            expected_revision=snapshot_revision.strip(),
        )
        return RedirectResponse("/review/repair", status_code=303)

    @app.post("/review/repair/support")
    def repair_support_route(
        request: Request,
        snapshot_id: str = Form(...),
        support_object_id: str = Form(...),
        claim_object_id: str = Form(...),
        snapshot_revision: str = Form(...),
    ) -> RedirectResponse:
        account = account_for(request)
        console.resolve_support_relation(
            actor_id=account["account_id"],
            snapshot_id=snapshot_id,
            support_object_id=support_object_id,
            claim_object_id=claim_object_id,
            expected_revision=snapshot_revision.strip(),
        )
        return RedirectResponse("/review/repair", status_code=303)

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
            "<p><a href='/audit'>← Terug naar Audit</a></p>"
            "<h1>Signalen uit Review</h1>"
            "<p class='lead'>Append-only evidence van review en herstel. "
            "Audit wijzigt geen kennisobjecten.</p>"
            "<p><a class='btn-secondary' href='/review/repair'>Open herstelwerk in Review</a></p>"
            + ("".join(rows) or "<p class='muted'>Nog geen signalen.</p>"),
            "audit",
        )