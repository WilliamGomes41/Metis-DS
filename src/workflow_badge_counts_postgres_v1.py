"""Cheap PostgreSQL-derived navigation badge counts for the live workflow console.

Badge integers are derived read state only. Workflow PostgreSQL remains authority
for document/review work; canonical PostgreSQL remains publication authority.
"""
from __future__ import annotations

from typing import Any

from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError
from src.operations_console_v1 import CAPTURED, ConsoleError
from src.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflow_remaining_cutover_v1 import (
    PostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
    PostgresCompleteWorkflowDurablePublicationConsole,
)


class _PostgresBadgeCountsMixin:
    """Derive nav counts without materializing every work-object payload in Python."""

    def _workflow_badge_row(self, account_id: str) -> dict[str, Any]:
        try:
            with self.workflow_document_store._connect() as con:
                row = con.execute(
                    """
                    WITH document_status AS (
                        SELECT d.snapshot_id,
                               d.uploader_account_id,
                               d.state,
                               d.clinical_rereview_required,
                               EXISTS (
                                   SELECT 1
                                   FROM workflow.document_objects o
                                   WHERE o.snapshot_id=d.snapshot_id
                                     AND o.payload->'governance'->>'validation_status'='revise'
                               ) AS has_revise,
                               EXISTS (
                                   SELECT 1
                                   FROM workflow.document_objects o
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
                               WHERE s.clinical_rereview_required
                           ) AS tree,
                           COALESCE(
                               ARRAY_AGG(s.snapshot_id) FILTER (WHERE s.state=%s),
                               ARRAY[]::text[]
                           ) AS publish_snapshot_ids
                    FROM document_status s
                    LEFT JOIN workflow.document_reviewers r
                      ON r.snapshot_id=s.snapshot_id AND r.account_id=%s
                    """,
                    (account_id, CAPTURED, account_id),
                ).fetchone()
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_badge_counts_read_failed") from exc
        if row is None:
            raise WorkflowDocumentStoreError("workflow_badge_counts_read_failed")
        return dict(row)

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
            try:
                published = self._published_snapshot_ids(publish_snapshot_ids)
            except CanonicalPublicationStoreError as exc:
                raise ConsoleError("durable_publication_lookup_failed", str(exc)) from exc
            publish = len(set(publish_snapshot_ids) - published)

        return {
            "ingest": int(row.get("ingest") or 0) if "researcher" in roles else 0,
            "tree": int(row.get("tree") or 0)
            if roles & {"researcher", "reviewer", "publisher"}
            else 0,
            "review": int(row.get("review") or 0) if "reviewer" in roles else 0,
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
