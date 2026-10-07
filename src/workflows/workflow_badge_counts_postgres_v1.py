"""Cheap PostgreSQL-derived reads for the live workflow console.

Navigation badges, list lifecycle labels and Review workboard summaries are
read-only projections. Workflow PostgreSQL remains authority for document/review
work; canonical PostgreSQL remains publication authority.
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any

from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError
from src.document_status_v1 import derive_lifecycle_status
from src.console_performance_v1 import measure_badges
from src.publish_authorization_v1 import still_matches
from src.four_eyes_v1 import HIGH_RISK_FIELDS
from src.operations_console_v1 import CAPTURED, PRE_REVIEW_BLOCKED, ConsoleError
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.workflow_review_postgres_v1 import WorkflowReviewStoreError
from src.workflows.workflow_remaining_cutover_v1 import (
    PostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
    PostgresCompleteWorkflowDurablePublicationConsole,
)


class _PostgresBadgeCountsMixin:
    """Derive hot console reads without materializing every work-object payload."""

    _tree_publication_batch: ContextVar[
        tuple[frozenset[str], frozenset[str], frozenset[str]] | None
    ] = ContextVar("tree_publication_batch", default=None)

    def _workflow_badge_row(self, account_id: str) -> dict[str, Any]:
        try:
            with self.workflow_document_store._connect() as con:
                row = con.execute(
                    """
                    WITH current_objects AS (
                        SELECT DISTINCT ON (o.snapshot_id,o.object_id)
                               o.snapshot_id,o.object_id,o.payload
                        FROM workflow.document_objects o
                        ORDER BY o.snapshot_id,o.object_id,o.position DESC NULLS LAST
                    ),
                    document_status AS (
                        SELECT d.snapshot_id,
                               d.uploader_account_id,
                               d.state,
                               d.publication_eligibility,
                               d.clinical_rereview_required,
                               d.envelope_payload->'review_policy' IS NOT NULL AS has_explicit_policy,
                               EXISTS (
                                   SELECT 1
                                   FROM current_objects o
                                   WHERE o.snapshot_id=d.snapshot_id
                                     AND o.payload->'governance'->>'validation_status'='revise'
                               ) AS has_revise,
                               EXISTS (
                                   SELECT 1
                                   FROM current_objects o
                                   WHERE o.snapshot_id=d.snapshot_id
                                     AND o.payload->'governance'->>'validation_status'='needs_review'
                               ) AS has_needs_review
                        FROM workflow.documents d
                    )
                    SELECT COUNT(*) FILTER (
                               WHERE s.uploader_account_id=%s AND s.has_revise
                           ) AS ingest,
                           COUNT(*) FILTER (
                               WHERE r.snapshot_id IS NOT NULL
                                 AND (s.has_needs_review OR s.has_revise)
                           ) AS review,
                           COUNT(*) FILTER (
                               WHERE r.snapshot_id IS NOT NULL AND s.has_explicit_policy
                           ) AS explicit_review_documents,
                           COUNT(*) FILTER (
                               WHERE s.clinical_rereview_required
                           ) AS tree,
                           COALESCE(
                               ARRAY_AGG(s.snapshot_id) FILTER (
                                   WHERE s.state=%s
                                     AND s.publication_eligibility<>%s
                               ),
                               ARRAY[]::text[]
                           ) AS publish_snapshot_ids
                    FROM document_status s
                    LEFT JOIN workflow.document_reviewers r
                      ON r.snapshot_id=s.snapshot_id AND r.account_id=%s
                    """,
                    (account_id, CAPTURED, PRE_REVIEW_BLOCKED, account_id),
                ).fetchone()
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_badge_counts_read_failed") from exc
        if row is None:
            raise WorkflowDocumentStoreError("workflow_badge_counts_read_failed")
        return dict(row)

    def _workflow_list_status_rows(
        self,
        snapshot_ids: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        where = ""
        params: tuple[Any, ...] = ()
        if snapshot_ids is not None:
            if not snapshot_ids:
                return {}
            where = "WHERE d.snapshot_id=ANY(%s)"
            params = (snapshot_ids,)
        try:
            with self.workflow_document_store._connect() as con:
                rows = con.execute(
                    f"""
                    WITH current_objects AS (
                        SELECT DISTINCT ON (o.snapshot_id,o.object_id)
                               o.snapshot_id,o.object_id,o.payload
                        FROM workflow.document_objects o
                        ORDER BY o.snapshot_id,o.object_id,o.position DESC NULLS LAST
                    )
                    SELECT d.snapshot_id,
                           d.state,
                           d.publication_eligibility,
                           EXISTS (
                               SELECT 1
                               FROM current_objects o
                               WHERE o.snapshot_id=d.snapshot_id
                                 AND COALESCE(o.payload->>'object_type','')<>'document'
                                 AND COALESCE(
                                     o.payload->'governance'->>'validation_status',''
                                 ) NOT IN ('approved','rejected','superseded')
                           ) AS has_open_review
                    FROM workflow.documents d
                    {where}
                    ORDER BY d.acquired_at,d.snapshot_id
                    """,
                    params,
                ).fetchall()
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_list_status_read_failed") from exc
        return {str(row["snapshot_id"]): dict(row) for row in rows}

    def _canonical_list_release_rows(
        self,
        snapshot_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        if not snapshot_ids or self.canonical_publication_store is None:
            return {}
        store = self.canonical_publication_store
        try:
            with store._connect() as con:
                rows = con.execute(
                    """
                    WITH latest_release AS (
                        SELECT DISTINCT ON (ev.details->>'snapshot_id')
                               ev.details->>'snapshot_id' AS snapshot_id,
                               ev.details->>'logical_document_id' AS logical_document_id,
                               rel.release_id,
                               rel.status,
                               rel.published_at
                        FROM audit_events ev
                        JOIN publication_releases rel ON rel.release_id=ev.entity_id
                        WHERE ev.entity_type='release'
                          AND ev.event_type='release_published'
                          AND ev.details->>'snapshot_id'=ANY(%s)
                        ORDER BY ev.details->>'snapshot_id',
                                 rel.published_at DESC NULLS LAST,
                                 rel.release_id DESC
                    ),
                    release_counts AS (
                        SELECT lr.snapshot_id,
                               lr.logical_document_id,
                               lr.release_id,
                               lr.status,
                               lr.published_at,
                               COUNT(i.object_id) AS item_count,
                               COUNT(i.object_id) FILTER (
                                   WHERE r.state='active'
                                     AND r.release_id=i.release_id
                                     AND r.object_version=i.object_version
                               ) AS active_same_release,
                               COUNT(i.object_id) FILTER (
                                   WHERE r.state='active'
                                     AND r.release_id<>i.release_id
                               ) AS active_other_release
                        FROM latest_release lr
                        LEFT JOIN publication_release_items i
                          ON i.release_id=lr.release_id
                        LEFT JOIN publication_registry r
                          ON r.object_id=i.object_id
                        GROUP BY lr.snapshot_id,
                                 lr.logical_document_id,
                                 lr.release_id,
                                 lr.status,
                                 lr.published_at
                    )
                    SELECT rc.*,
                           EXISTS (
                               SELECT 1
                               FROM audit_events later_ev
                               JOIN publication_releases later_rel
                                 ON later_rel.release_id=later_ev.entity_id
                               WHERE later_ev.entity_type='release'
                                 AND later_ev.event_type='release_published'
                                 AND later_rel.release_id<>rc.release_id
                                 AND rc.logical_document_id<>''
                                 AND later_ev.details->>'logical_document_id'=
                                     rc.logical_document_id
                                 AND later_rel.published_at>rc.published_at
                           ) AS later_release
                    FROM release_counts rc
                    """,
                    (snapshot_ids,),
                ).fetchall()
        except CanonicalPublicationStoreError:
            raise
        except Exception as exc:
            raise CanonicalPublicationStoreError("canonical_list_status_read_failed") from exc
        return {str(row["snapshot_id"]): dict(row) for row in rows}

    @staticmethod
    def _release_dimensions(row: dict[str, Any] | None) -> tuple[str, str]:
        if row is None:
            return "none", "inactive"
        status = str(row.get("status") or "")
        if status == "withdrawn":
            return "withdrawn", "inactive"
        if status != "published":
            raise CanonicalPublicationStoreError("canonical_release_status_invalid")
        item_count = int(row.get("item_count") or 0)
        if item_count <= 0:
            raise CanonicalPublicationStoreError("canonical_release_items_missing")
        active_same = int(row.get("active_same_release") or 0)
        active_other = int(row.get("active_other_release") or 0)
        if active_same == item_count:
            return "published", "active"
        if active_same == 0 and (
            bool(row.get("later_release")) or active_other == item_count
        ):
            return "superseded", "inactive"
        return "published", "inactive"

    def list_document_lifecycle_statuses(
        self,
        snapshot_ids: list[str] | None = None,
    ) -> dict[str, dict[str, str]]:
        """Return fail-closed list presentation without running publish readiness."""
        try:
            workflow = self._workflow_list_status_rows(snapshot_ids)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc

        ids = list(workflow)
        try:
            releases = self._canonical_list_release_rows(ids)
        except CanonicalPublicationStoreError as exc:
            raise ConsoleError("durable_lifecycle_status_read_failed", str(exc)) from exc

        published_history = frozenset(releases)
        all_ids = frozenset(ids)
        if all_ids:
            # Reuse the same canonical history later in the request for tree delete
            # controls and publisher badge exclusion instead of opening another
            # canonical connection.
            self._tree_publication_batch.set((all_ids, published_history, all_ids))

        out: dict[str, dict[str, str]] = {}
        for snapshot_id, row in workflow.items():
            if self.canonical_publication_store is None:
                state = str(row.get("state") or "")
                if state == "withdrawn":
                    release_status, serving_status = "withdrawn", "inactive"
                elif state == "superseded":
                    release_status, serving_status = "superseded", "inactive"
                elif state == "published":
                    release_status, serving_status = "published", "active"
                else:
                    release_status, serving_status = "none", "inactive"
            else:
                try:
                    release_status, serving_status = self._release_dimensions(
                        releases.get(snapshot_id)
                    )
                except CanonicalPublicationStoreError as exc:
                    raise ConsoleError(
                        "durable_lifecycle_status_read_failed", str(exc)
                    ) from exc

            readiness: dict[str, Any] = {}
            if release_status == "none" and bool(row.get("has_open_review")):
                readiness["curation_ready"] = False
            lifecycle = derive_lifecycle_status(
                readiness=readiness,
                release_status=release_status,
                serving_status=serving_status,
            )
            # A failed pre-review is a completed, blocked attempt, not ongoing
            # processing or actionable Review. Preserve canonical release truth.
            if (
                release_status == "none"
                and row.get("publication_eligibility") == PRE_REVIEW_BLOCKED
            ):
                lifecycle["workflow_status"] = "blocked"
                lifecycle["presentation_status"] = "blocked"
            out[snapshot_id] = lifecycle
        return out

    def review_workboard_summaries(
        self, account_id: str, snapshot_id: str | None = None, *, navigation_only: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Select assigned documents; kernel projections own all review duties."""
        try:
            with self.workflow_document_store._connect() as con:
                rows = con.execute(
                    """
                    SELECT d.snapshot_id,d.envelope_payload
                    FROM workflow.documents d
                    JOIN workflow.document_reviewers r ON r.snapshot_id=d.snapshot_id
                    WHERE r.account_id=%s
                      AND d.snapshot_id=COALESCE(%s,d.snapshot_id)
                      AND d.publication_eligibility<>%s
                    ORDER BY d.snapshot_id
                    """,
                    (account_id, snapshot_id or None, PRE_REVIEW_BLOCKED),
                ).fetchall()
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_review_workboard_read_failed") from exc

        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            envelope = row.get("envelope_payload")
            if isinstance(envelope, str):
                envelope = json.loads(envelope)
            if not isinstance(envelope, dict):
                raise WorkflowDocumentStoreError("workflow_document_envelope_payload_invalid")
            snapshot_id = str(row["snapshot_id"])
            out[snapshot_id] = {
                "envelope": dict(envelope),
                "heading_total": int(row.get("heading_total") or 0),
                "heading_pending": int(row.get("heading_pending") or 0),
                "individual_total": int(row.get("individual_total") or 0),
                "individual_pending": int(row.get("individual_pending") or 0),
                "normal_passages": int(row.get("normal_passages") or 0),
                "normal_batches": int(row.get("normal_batches") or 0),
                "blocked_count": int(row.get("blocked_count") or 0),
                "closure_gap_count": int(row.get("closure_gap_count") or 0),
                "closure_gap_first": str(row.get("closure_gap_first") or ""),
                "source_passage_review_complete": int(
                    row.get("unresolved_closure_count") or 0
                ) == 0,
                "review_duties": int(row.get("review_duties") or 0),
                "first_review_duties": int(row.get("first_review_duties") or 0),
                "second_review_duties": int(row.get("second_review_duties") or 0),
                "structure_review_duties": int(
                    row.get("structure_review_duties") or 0
                ),
                "contextual_review_duties": int(
                    row.get("contextual_review_duties") or 0
                ),
                "batch_review_duties": int(row.get("batch_review_duties") or 0),
                "actionable_review_duties": int(
                    row.get("actionable_review_duties") or 0
                ),
                "waiting_for_reviewer_duties": int(
                    row.get("waiting_for_reviewer_duties") or 0
                ),
                "actionable_structure_duties": int(
                    row.get("actionable_structure_duties") or 0
                ),
                "actionable_contextual_duties": int(
                    row.get("actionable_contextual_duties") or 0
                ),
                "actionable_batch_duties": int(
                    row.get("actionable_batch_duties") or 0
                ),
                "actionable_second_review_duties": int(
                    row.get("actionable_second_review_duties") or 0
                ),
                "has_review_decision": bool(row.get("has_review_decision")),
                "progress_total": int(row.get("progress_total") or 0),
                "progress_done": int(row.get("progress_done") or 0),
                "progress_approved": int(row.get("progress_approved") or 0),
                "progress_rejected": int(row.get("progress_rejected") or 0),
                "progress_not_included": int(row.get("progress_not_included") or 0),
                "progress_context": int(row.get("progress_context") or 0),
                "progress_support": int(row.get("progress_support") or 0),
                "progress_superseded": int(row.get("progress_superseded") or 0),
                "progress_revised": int(row.get("progress_revised") or 0),
            }
        if navigation_only:
            return out
        self._enrich_review_workboard_summaries(account_id, out)
        return out

    def _enrich_review_workboard_summaries(
        self, account_id: str, summaries: dict[str, dict[str, Any]],
    ) -> None:
        """Load explicit-policy inputs together; retain the existing duty rules.

        All inputs live only for this projection. Commands still read and check
        current durable state independently. No publication gate is evaluated
        merely to display the review overview's lifecycle label.
        """
        from src.document_status_ui_v1 import current_document_lifecycle_status
        from src.review_workboard_v1 import ReviewWorkInputs, review_work_item

        # SQL aggregates remain presentation inputs. Content-duty authority is
        # recomputed from the same domain projection for every assigned document.
        ids = list(summaries)
        if not ids:
            return
        try:
            account = self._account(account_id)
            lifecycle = {sid: current_document_lifecycle_status(sid) for sid in ids}
            missing = [sid for sid in ids if lifecycle[sid] is None]
            if missing:
                # The list reader also offers a disposable tree prefetch. This
                # review projection must not leave it behind for later commands.
                token = self._tree_publication_batch.set(None)
                try:
                    lifecycle.update(self.list_document_lifecycle_statuses(missing))
                finally:
                    self._tree_publication_batch.reset(token)
            if any(lifecycle.get(sid) is None for sid in ids):
                raise ConsoleError("durable_lifecycle_status_read_failed")
            objects = self.workflow_document_store.list_current_objects_batch(ids)
            bindings = self.workflow_review_store.read_bindings(ids)
            for sid in ids:
                current = {obj["object_id"]: obj for obj in objects[sid]}
                checked = []
                for binding in bindings.get(sid, []):
                    row = dict(binding)
                    obj = current.get(row.get("object_id"))
                    row["valid"] = bool(obj) and still_matches(row, obj)
                    checked.append(row)
                status = lifecycle[sid]
                item = review_work_item(
                    self, account=account, envelope=summaries[sid]["envelope"],
                    inputs=ReviewWorkInputs(objects[sid], checked, status,
                                           status["release_status"] != "none"),
                )
                summaries[sid]["work_item"] = item
                if item:
                    summaries[sid].update({k: v for k, v in item.items() if k in summaries[sid]})
                    summaries[sid].update({"progress_" + k: v for k, v in (item.get("progress") or {}).items()})
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        except WorkflowReviewStoreError as exc:
            raise ConsoleError("workflow_review_unavailable", str(exc)) from exc

    def _navigation_review_count(self, account: dict[str, Any]) -> int:
        """Use review rules once with call-local batched inputs, not publish gates.

        Navigation needs actionable work and whether a revision is closed. The
        full publication readiness and source verification remain on their
        existing authoritative command/detail paths.
        """
        from src.review_workboard_v1 import ReviewWorkInputs, review_work_item, review_workboard_items
        try:
            summaries = self.review_workboard_summaries(account["account_id"], navigation_only=True)
            releases = self._canonical_list_release_rows(list(summaries))
            lifecycle: dict[str, dict[str, str]] = {}
            for sid, summary in summaries.items():
                if self.canonical_publication_store is None:
                    state = str(summary["envelope"].get("state") or "")
                    release_status = state if state in {"published", "withdrawn", "superseded"} else "none"
                    serving_status = "active" if release_status == "published" else "inactive"
                else:
                    release_status, serving_status = self._release_dimensions(releases.get(sid))
                lifecycle[sid] = derive_lifecycle_status(
                    readiness={}, release_status=release_status, serving_status=serving_status,
                )
            # Historical publication closes review even when stale object rows
            # still contain duties. Do not materialize those closed payloads.
            summaries = {sid: summary for sid, summary in summaries.items()
                         if lifecycle[sid]["workflow_status"] != "closed"}
            explicit_ids = list(summaries)
            objects = self.workflow_document_store.list_current_objects_batch(explicit_ids)
            bindings = self.workflow_review_store.read_bindings(explicit_ids) if explicit_ids else {}
            for sid in explicit_ids:
                current = {obj["object_id"]: obj for obj in objects[sid]}
                checked = []
                for binding in bindings.get(sid, []):
                    item = dict(binding)
                    obj = current.get(item.get("object_id"))
                    item["valid"] = bool(obj) and still_matches(item, obj)
                    checked.append(item)
                summaries[sid]["work_item"] = review_work_item(
                    self, account=account, envelope=summaries[sid]["envelope"],
                    inputs=ReviewWorkInputs(objects[sid], checked, lifecycle[sid],
                                           lifecycle[sid]["release_status"] != "none"),
                )
            items = review_workboard_items(self, account=account, summaries=summaries,
                                          lifecycle_statuses=lifecycle)
            return sum(item["work_state"] in {"review", "disposition", "technical_repair"}
                       for item in items)
        except CanonicalPublicationStoreError as exc:
            raise ConsoleError("durable_lifecycle_status_read_failed", str(exc)) from exc
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        except WorkflowReviewStoreError as exc:
            raise ConsoleError("workflow_review_unavailable", str(exc)) from exc

    def _published_snapshot_ids(self, snapshot_ids: list[str]) -> set[str]:
        if not snapshot_ids:
            return set()
        store = self.canonical_publication_store
        if store is None:
            raise ConsoleError("durable_publication_store_required")
        try:
            with store._connect() as con:
                rows = con.execute(
                    """
                    SELECT DISTINCT ev.details->>'snapshot_id' AS snapshot_id
                    FROM audit_events ev
                    WHERE ev.entity_type='release'
                      AND ev.event_type='release_published'
                      AND ev.details->>'snapshot_id'=ANY(%s)
                    """,
                    (snapshot_ids,),
                ).fetchall()
        except CanonicalPublicationStoreError:
            raise
        except Exception as exc:
            raise CanonicalPublicationStoreError("canonical_postgres_read_failed") from exc
        return {str(row["snapshot_id"]) for row in rows if row.get("snapshot_id")}

    def published_snapshot_ids(self, snapshot_ids: list[str]) -> set[str]:
        """Return publication history for many snapshots in one canonical read."""
        try:
            return self._published_snapshot_ids(snapshot_ids)
        except CanonicalPublicationStoreError as exc:
            raise ConsoleError("durable_publication_lookup_failed", str(exc)) from exc

    def family_tree(self) -> dict[str, Any]:
        """Prefetch publication history once for the existing per-card delete checks."""
        payload = super().family_tree()
        snapshot_ids = [
            str(child.get("snapshot_id") or "")
            for node in (payload.get("families") or {}).values()
            for child in (node.get("children") or [])
            if str(child.get("snapshot_id") or "")
        ]
        all_ids = frozenset(snapshot_ids)
        if not all_ids:
            self._tree_publication_batch.set(None)
            return payload
        current = self._tree_publication_batch.get()
        if current is not None and all_ids.issubset(current[0]):
            published = frozenset(snapshot_id for snapshot_id in current[1] if snapshot_id in all_ids)
            self._tree_publication_batch.set((all_ids, published, all_ids))
            return payload
        try:
            published = frozenset(self.published_snapshot_ids(list(all_ids)))
        except ConsoleError:
            # Existing delete controls fail closed when publication truth is unavailable.
            published = all_ids
        self._tree_publication_batch.set((all_ids, published, all_ids))
        return payload

    def snapshot_is_published(self, snapshot_id: str) -> bool:
        """Use the tree-prefetched publication set before falling back to lifecycle reads."""
        snapshot_id = str(snapshot_id or "")
        batch = self._tree_publication_batch.get()
        if batch is not None:
            all_ids, published, remaining = batch
            if snapshot_id in all_ids:
                next_remaining = remaining - {snapshot_id}
                self._tree_publication_batch.set(
                    None if not next_remaining else (all_ids, published, next_remaining)
                )
                return snapshot_id in published
        return super().snapshot_is_published(snapshot_id)

    @measure_badges
    def waiting_task_counts(self, account_id: str) -> dict[str, int]:
        account = self._account(account_id)
        roles = set(account.get("roles") or [])
        try:
            row = self._workflow_badge_row(account_id)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc

        publish_snapshot_ids = [str(value) for value in row.get("publish_snapshot_ids") or []]
        publish = 0
        if "publisher" in roles:
            batch = self._tree_publication_batch.get()
            candidates = set(publish_snapshot_ids)
            if batch is not None and candidates.issubset(batch[0]):
                published = set(batch[1])
            else:
                try:
                    published = self._published_snapshot_ids(publish_snapshot_ids)
                except CanonicalPublicationStoreError as exc:
                    raise ConsoleError("durable_publication_lookup_failed", str(exc)) from exc
            publish = len(candidates - published)

        review_count = int(row.get("review") or 0)
        if "reviewer" in roles:
            review_count = self._navigation_review_count(account)
        return {
            "ingest": int(row.get("ingest") or 0) if "researcher" in roles else 0,
            "tree": int(row.get("tree") or 0)
            if roles & {"researcher", "reviewer", "publisher"}
            else 0,
            "review": review_count if "reviewer" in roles else 0,
            "publish": publish,
            "accounts": 0,
        }


class FastBadgePostgresCompleteWorkflowDurablePublicationConsole(
    _PostgresBadgeCountsMixin,
    PostgresCompleteWorkflowDurablePublicationConsole,
):
    pass


class FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole(
    _PostgresBadgeCountsMixin,
    PostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
):
    pass
