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
from src.four_eyes_v1 import HIGH_RISK_FIELDS
from src.operations_console_v1 import CAPTURED, PRE_REVIEW_BLOCKED, ConsoleError
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
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
            out[snapshot_id] = derive_lifecycle_status(
                readiness=readiness,
                release_status=release_status,
                serving_status=serving_status,
            )
        return out

    def review_workboard_summaries(
        self,
        account_id: str,
        snapshot_id: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Summarize assigned Review work in one set-based workflow query."""
        try:
            with self.workflow_document_store._connect() as con:
                rows = con.execute(
                    """
                    WITH assigned AS (
                        SELECT d.snapshot_id,d.class,d.envelope_payload
                        FROM workflow.documents d
                        JOIN workflow.document_reviewers r
                          ON r.snapshot_id=d.snapshot_id
                        WHERE r.account_id=%s
                          AND d.snapshot_id=COALESCE(%s,d.snapshot_id)
                          AND d.publication_eligibility<>%s
                    ),
                    current_objects AS (
                        SELECT DISTINCT ON (o.snapshot_id,o.object_id)
                               o.snapshot_id,o.object_id,o.payload
                        FROM workflow.document_objects o
                        JOIN assigned a ON a.snapshot_id=o.snapshot_id
                        ORDER BY o.snapshot_id,o.object_id,o.position DESC NULLS LAST
                    ),
                    authorization_counts AS (
                        SELECT o.snapshot_id,
                               o.object_id,
                               COUNT(DISTINCT pa.reviewer_account_id) FILTER (
                                   WHERE pa.valid
                                     AND pa.decision='approve'
                                     AND pa.object_version=COALESCE(
                                         o.payload->>'object_version',''
                                     )
                                     AND pa.canonical_object_hash=COALESCE(
                                         o.payload->'provenance'->>'canonical_object_hash',''
                                     )
                                     AND pa.confirmed_object_type=COALESCE(
                                         o.payload->>'confirmed_object_type',''
                                     )
                                     AND LOWER(COALESCE(ra.username,'')) NOT IN (
                                         'ai','grok bot','grok','metis',
                                         'implementation engineer','auditor'
                                     )
                                     AND LOWER(COALESCE(ra.display_name,'')) NOT IN (
                                         'ai','grok bot','grok','metis',
                                         'implementation engineer','auditor'
                                     )
                               ) AS exact_approver_count,
                               COALESCE(
                                   BOOL_OR(
                                       pa.reviewer_account_id=%s
                                       AND pa.valid
                                       AND pa.decision='approve'
                                       AND pa.object_version=COALESCE(
                                           o.payload->>'object_version',''
                                       )
                                       AND pa.canonical_object_hash=COALESCE(
                                           o.payload->'provenance'->>'canonical_object_hash',''
                                       )
                                       AND pa.confirmed_object_type=COALESCE(
                                           o.payload->>'confirmed_object_type',''
                                       )
                                       AND LOWER(COALESCE(ra.username,'')) NOT IN (
                                           'ai','grok bot','grok','metis',
                                           'implementation engineer','auditor'
                                       )
                                       AND LOWER(COALESCE(ra.display_name,'')) NOT IN (
                                           'ai','grok bot','grok','metis',
                                           'implementation engineer','auditor'
                                       )
                                   ),
                                   FALSE
                               ) AS reviewer_has_approved
                        FROM current_objects o
                        LEFT JOIN workflow.publish_authorizations pa
                          ON pa.snapshot_id=o.snapshot_id
                         AND pa.object_id=o.object_id
                        LEFT JOIN workflow.accounts ra
                          ON ra.account_id=pa.reviewer_account_id
                        GROUP BY o.snapshot_id,o.object_id
                    ),
                    base AS (
                        SELECT a.snapshot_id,
                               a.class,
                               a.envelope_payload,
                               o.object_id,
                               o.payload,
                               COALESCE(o.payload->>'object_type','') AS object_type,
                               COALESCE(o.payload->>'confirmed_object_type','') AS confirmed_type,
                               COALESCE(o.payload->>'proposed_object_type','') AS proposed_type,
                               COALESCE(
                                   NULLIF(BTRIM(o.payload->>'confirmed_object_type'),''),
                                   CASE
                                       WHEN BTRIM(COALESCE(o.payload->>'object_type',''))
                                            NOT IN ('','unclassified')
                                       THEN BTRIM(o.payload->>'object_type')
                                   END,
                                   NULLIF(BTRIM(o.payload->>'proposed_object_type'),''),
                                   ''
                               ) AS review_type,
                               COALESCE(
                                   o.payload->'metadata'->'admission'->>'proposed_type',
                                   o.payload->>'proposed_object_type',
                                   ''
                               ) AS admission_proposed_type,
                               COALESCE(
                                   o.payload->'governance'->>'validation_status',''
                               ) AS validation_status,
                               COALESCE(
                                   o.payload->'metadata'->'passage_register'->>'status',''
                               ) AS register_status,
                               COALESCE(
                                   o.payload->'metadata'->'passage_register'->>'source',''
                               ) AS register_source,
                               COALESCE(
                                   o.payload->'metadata'->'admission'->>'gate_result',''
                               ) AS gate_result,
                               COALESCE(ac.exact_approver_count,0) AS exact_approver_count,
                               COALESCE(ac.reviewer_has_approved,FALSE) AS reviewer_has_approved,
                               CASE
                                   WHEN jsonb_typeof(
                                       o.payload->'metadata'->'admission'->'section_path'
                                   )='array'
                                   AND jsonb_array_length(
                                       o.payload->'metadata'->'admission'->'section_path'
                                   )>0
                                   THEN o.payload->'metadata'->'admission'->'section_path'
                                   ELSE COALESCE(
                                       o.payload->'structure'->'section_path','[]'::jsonb
                                   )
                               END AS section_path
                        FROM assigned a
                        JOIN current_objects o
                          ON o.snapshot_id=a.snapshot_id
                        LEFT JOIN authorization_counts ac
                          ON ac.snapshot_id=o.snapshot_id
                         AND ac.object_id=o.object_id
                    ),
                    classified AS (
                        SELECT b.*,
                               CASE
                                   WHEN b.confirmed_type<>'' THEN b.confirmed_type
                                   WHEN b.object_type NOT IN ('','unclassified')
                                   THEN b.object_type
                                   WHEN b.admission_proposed_type='factual_finding'
                                   THEN 'explanation'
                                   ELSE b.admission_proposed_type
                               END AS batch_type,
                               (b.class='beslisboom') AS boom,
                               CASE
                                   WHEN b.class='beslisboom' THEN b.review_type='path'
                                   ELSE b.review_type='heading'
                               END AS queue_fast,
                               CASE
                                   WHEN b.review_type IN ('path','node','outcome')
                                        OR b.proposed_type IN ('path','node','outcome')
                                   THEN b.review_type='path'
                                   ELSE b.review_type='heading'
                               END AS closure_fast,
                               b.validation_status IN (
                                   'approved','rejected','superseded'
                               ) AS review_final,
                               (
                                   (b.validation_status='superseded' AND b.register_status IN (
                                       'selected_as_candidate','used_as_context','linked_as_support',
                                       'excluded_with_reason','not_yet_assessed'
                                   ))
                                   OR (
                                       b.register_status IN (
                                           'used_as_context',
                                           'linked_as_support',
                                           'excluded_with_reason'
                                       )
                                       AND (
                                           b.register_source<>'review'
                                           OR b.validation_status IN ('approved','rejected')
                                       )
                                   )
                                   OR (
                                       b.register_status='selected_as_candidate'
                                       AND b.validation_status IN ('approved','rejected')
                                   )
                               ) AS disposition_final,
                               COALESCE((
                                   b.confirmed_type='exception'
                                   OR COALESCE(
                                       NULLIF(b.payload->'risk'->>'risk_level',''),
                                       b.payload->'metadata'->>'risk_level',''
                                   )='high'
                                   OR (b.payload->'risk'->'risk_fields') ?| %s::text[]
                                   OR (b.payload->'logic'->'score_points' IS NOT NULL
                                       AND b.payload->'logic'->'score_points'<>'null'::jsonb)
                                   OR (b.payload->'logic'->'result_threshold'->'threshold' IS NOT NULL
                                       AND b.payload->'logic'->'result_threshold'->'threshold'<>'null'::jsonb)
                                   OR COALESCE(b.payload->'logic'->'result_threshold'->>'operator','')<>''
                                   OR COALESCE(b.payload->'logic'->'result_threshold'->>'unit','')<>''
                                   OR EXISTS (
                                       SELECT 1 FROM jsonb_array_elements(
                                           COALESCE(NULLIF(b.payload->'logic'->'predicates','null'::jsonb),'[]'::jsonb)
                                       ) predicate
                                       WHERE COALESCE(predicate->>'operator','')<>''
                                          OR COALESCE(predicate->>'unit','')<>''
                                          OR position('age' in COALESCE(predicate->>'field',''))>0
                                          OR position('dose' in COALESCE(predicate->>'field',''))>0
                                          OR position('dosering' in COALESCE(predicate->>'field',''))>0
                                   )
                                   OR EXISTS (
                                       SELECT 1 FROM unnest(%s::text[]) field
                                       WHERE b.payload->'metadata'->field NOT IN
                                           ('null'::jsonb,'""'::jsonb,'false'::jsonb,'0'::jsonb,'[]'::jsonb)
                                   )
                               ), FALSE) AS four_eyes
                        FROM base b
                    ),
                    routed AS (
                        SELECT c.*,
                               (
                                   c.object_type<>'document'
                                   AND NOT c.queue_fast
                                   AND (
                                       (
                                           c.boom
                                           AND (
                                               c.four_eyes
                                               OR c.confirmed_type IN ('node','outcome')
                                               OR c.object_type IN ('node','outcome')
                                               OR c.proposed_type IN ('node','outcome')
                                           )
                                       )
                                       OR (
                                           NOT c.boom
                                           AND c.gate_result<>'blocked'
                                           AND (
                                               c.four_eyes
                                               OR c.confirmed_type IN (
                                                   'recommendation','condition','exception'
                                               )
                                               OR c.object_type IN (
                                                   'recommendation','condition','exception'
                                               )
                                               OR c.proposed_type IN (
                                                   'recommendation','condition','exception'
                                               )
                                           )
                                       )
                                   )
                               ) AS slow_duty,
                               (
                                   NOT c.boom
                                   AND c.object_type<>'document'
                                   AND NOT c.queue_fast
                                   AND c.gate_result='allowed'
                                   AND c.review_type IN ('definition','explanation')
                                   AND jsonb_typeof(c.section_path)='array'
                                   AND jsonb_array_length(c.section_path)>0
                                   AND EXISTS (
                                       SELECT 1 FROM jsonb_array_elements_text(c.section_path) part
                                       WHERE BTRIM(part)<>''
                                   )
                                   AND COALESCE(
                                       c.payload->'uncertainty'->>'has_uncertainty','false'
                                   )<>'true'
                                   AND COALESCE(c.payload->'risk'->>'level','')<>'high'
                                   AND COALESCE(
                                       c.payload->'risk'->>'requires_second_review','false'
                                   )<>'true'
                                   AND NOT c.four_eyes
                               ) AS batch_eligible,
                               (
                                   c.object_type<>'document'
                                   AND NOT c.closure_fast
                                   AND NOT c.disposition_final
                               ) AS unresolved_closure
                        FROM classified c
                    ),
                    final_rows AS (
                        SELECT r.*,
                               (
                                   NOT r.boom
                                   AND r.object_type<>'document'
                                   AND NOT r.queue_fast
                                   AND NOT r.slow_duty
                                   AND r.gate_result='allowed'
                                   AND NOT r.batch_eligible
                               ) AS regular_individual,
                               (
                                   r.object_type<>'document'
                                   AND r.validation_status NOT IN (
                                       'rejected','superseded','revise'
                                   )
                                   AND (
                                       r.boom OR r.review_type='heading'
                                       OR r.gate_result='allowed'
                                       OR (BTRIM(r.confirmed_type)<>'' AND r.gate_result='')
                                   )
                                   AND r.exact_approver_count=0
                               ) AS first_review_open,
                               (
                                   r.object_type<>'document'
                                   AND r.validation_status NOT IN (
                                       'rejected','superseded','revise'
                                   )
                                   AND (
                                       r.boom OR r.review_type='heading'
                                       OR r.gate_result='allowed'
                                       OR (BTRIM(r.confirmed_type)<>'' AND r.gate_result='')
                                   )
                                   AND r.four_eyes
                                   AND r.exact_approver_count=1
                               ) AS second_review_open,
                               COALESCE(
                                   (
                                       jsonb_typeof(
                                           r.payload->'proposed_knowledge_relations'
                                       )='array'
                                       AND jsonb_array_length(
                                           r.payload->'proposed_knowledge_relations'
                                       )>0
                                   )
                                   OR (
                                       jsonb_typeof(
                                           r.payload->'confirmed_knowledge_relations'
                                       )='array'
                                       AND jsonb_array_length(
                                           r.payload->'confirmed_knowledge_relations'
                                       )>0
                                   ),
                                   FALSE
                               ) AS relation_review_required
                        FROM routed r
                    ),
                    duty_rows AS (
                        SELECT f.*,
                               (
                                   f.first_review_open OR f.second_review_open
                               ) AS review_duty_open,
                               (
                                   f.first_review_open
                                   OR (
                                       f.second_review_open
                                       AND NOT f.reviewer_has_approved
                                   )
                               ) AS actionable_review_duty,
                               (
                                   f.second_review_open
                                   AND f.reviewer_has_approved
                               ) AS waiting_for_reviewer_duty,
                               (
                                   f.first_review_open AND f.queue_fast
                               ) AS structure_review_duty,
                               (
                                   f.second_review_open
                                   OR (
                                       f.first_review_open
                                       AND NOT f.queue_fast
                                       AND (
                                           f.review_type IN (
                                               'recommendation','condition','exception',
                                               'node','outcome'
                                           )
                                           OR f.four_eyes
                                           OR f.relation_review_required
                                           OR NOT f.batch_eligible
                                       )
                                   )
                               ) AS contextual_review_duty,
                               (
                                   f.first_review_open
                                   AND NOT f.queue_fast
                                   AND f.batch_eligible
                                   AND NOT f.relation_review_required
                               ) AS batch_review_duty
                        FROM final_rows f
                    ),
                    counts AS (
                        SELECT snapshot_id,
                               COUNT(*) FILTER (
                                   WHERE queue_fast
                               ) AS heading_total,
                               COUNT(*) FILTER (
                                   WHERE queue_fast AND NOT review_final
                               ) AS heading_pending,
                               COUNT(*) FILTER (
                                   WHERE (slow_duty OR regular_individual)
                               ) AS individual_total,
                               COUNT(*) FILTER (
                                   WHERE (slow_duty OR regular_individual)
                                     AND NOT review_final
                               ) AS individual_pending,
                               COUNT(*) FILTER (
                                   WHERE batch_eligible
                               ) AS normal_passages,
                               COUNT(*) FILTER (
                                   WHERE NOT boom
                                     AND gate_result='blocked'
                                     AND unresolved_closure
                                     AND NOT review_duty_open
                               ) AS blocked_count,
                               COUNT(*) FILTER (
                                   WHERE unresolved_closure
                                     AND NOT (
                                         review_duty_open
                                         OR (NOT boom AND gate_result='blocked')
                                     )
                               ) AS closure_gap_count,
                               MIN(object_id) FILTER (
                                   WHERE unresolved_closure
                                     AND NOT (
                                         review_duty_open
                                         OR (NOT boom AND gate_result='blocked')
                                     )
                               ) AS closure_gap_first,
                               COUNT(*) FILTER (
                                   WHERE unresolved_closure
                               ) AS unresolved_closure_count,
                               COUNT(*) FILTER (
                                   WHERE review_duty_open
                               ) AS review_duties,
                               COUNT(*) FILTER (
                                   WHERE first_review_open
                               ) AS first_review_duties,
                               COUNT(*) FILTER (
                                   WHERE second_review_open
                               ) AS second_review_duties,
                               COUNT(*) FILTER (
                                   WHERE structure_review_duty
                               ) AS structure_review_duties,
                               COUNT(*) FILTER (
                                   WHERE contextual_review_duty
                               ) AS contextual_review_duties,
                               COUNT(*) FILTER (
                                   WHERE batch_review_duty
                               ) AS batch_review_duties,
                               COUNT(*) FILTER (
                                   WHERE actionable_review_duty
                               ) AS actionable_review_duties,
                               COUNT(*) FILTER (
                                   WHERE waiting_for_reviewer_duty
                               ) AS waiting_for_reviewer_duties,
                               COUNT(*) FILTER (
                                   WHERE first_review_open
                                     AND structure_review_duty
                               ) AS actionable_structure_duties,
                               COUNT(*) FILTER (
                                   WHERE first_review_open
                                     AND contextual_review_duty
                               ) AS actionable_contextual_duties,
                               COUNT(*) FILTER (
                                   WHERE first_review_open
                                     AND batch_review_duty
                               ) AS actionable_batch_duties,
                               COUNT(*) FILTER (
                                   WHERE second_review_open
                                     AND NOT reviewer_has_approved
                               ) AS actionable_second_review_duties,
                               COUNT(*) FILTER (
                                   WHERE object_type<>'document'
                               ) AS progress_total,
                               COUNT(*) FILTER (
                                   WHERE object_type<>'document'
                                     AND disposition_final
                               ) AS progress_done,
                               COUNT(*) FILTER (
                                   WHERE object_type<>'document'
                                     AND disposition_final
                                     AND validation_status='rejected'
                               ) AS progress_rejected,
                               COUNT(*) FILTER (
                                   WHERE object_type<>'document'
                                     AND disposition_final
                                     AND validation_status<>'rejected'
                                     AND register_status='selected_as_candidate'
                                     AND validation_status='approved'
                               ) AS progress_approved,
                               COUNT(*) FILTER (
                                   WHERE object_type<>'document'
                                     AND disposition_final
                                     AND validation_status<>'rejected'
                                     AND register_status='excluded_with_reason'
                               ) AS progress_not_included,
                               COUNT(*) FILTER (
                                   WHERE object_type<>'document'
                                     AND disposition_final
                                     AND validation_status<>'rejected'
                                     AND register_status='used_as_context'
                               ) AS progress_context,
                               COUNT(*) FILTER (
                                   WHERE object_type<>'document'
                                     AND disposition_final
                                     AND validation_status<>'rejected'
                                     AND register_status='linked_as_support'
                               ) AS progress_support,
                               COUNT(*) FILTER (
                                   WHERE object_type<>'document'
                                     AND disposition_final
                                     AND validation_status='superseded'
                               ) AS progress_superseded,
                               COUNT(*) FILTER (
                                   WHERE object_type<>'document'
                                     AND validation_status='needs_review'
                                     AND COALESCE(
                                         payload->'provenance'->>'previous_object_version',''
                                     )<>''
                               ) AS progress_revised
                        FROM duty_rows
                        GROUP BY snapshot_id
                    ),
                    batch_groups AS (
                        SELECT snapshot_id,section_path,batch_type,COUNT(*) AS n
                        FROM duty_rows
                        WHERE batch_review_duty
                          AND actionable_review_duty
                        GROUP BY snapshot_id,section_path,batch_type
                    ),
                    batch_counts AS (
                        SELECT snapshot_id,
                               COALESCE(SUM((n + 19) / 20),0) AS normal_batches
                        FROM batch_groups
                        GROUP BY snapshot_id
                    )
                    SELECT a.snapshot_id,
                           a.envelope_payload,
                           COALESCE(c.heading_total,0) AS heading_total,
                           COALESCE(c.heading_pending,0) AS heading_pending,
                           COALESCE(c.individual_total,0) AS individual_total,
                           COALESCE(c.individual_pending,0) AS individual_pending,
                           COALESCE(c.normal_passages,0) AS normal_passages,
                           COALESCE(bc.normal_batches,0) AS normal_batches,
                           COALESCE(c.blocked_count,0) AS blocked_count,
                           COALESCE(c.closure_gap_count,0) AS closure_gap_count,
                           c.closure_gap_first,
                           COALESCE(c.unresolved_closure_count,0) AS unresolved_closure_count,
                           COALESCE(c.review_duties,0) AS review_duties,
                           COALESCE(c.first_review_duties,0) AS first_review_duties,
                           COALESCE(c.second_review_duties,0) AS second_review_duties,
                           COALESCE(c.structure_review_duties,0) AS structure_review_duties,
                           COALESCE(c.contextual_review_duties,0) AS contextual_review_duties,
                           COALESCE(c.batch_review_duties,0) AS batch_review_duties,
                           COALESCE(c.actionable_review_duties,0) AS actionable_review_duties,
                           COALESCE(c.waiting_for_reviewer_duties,0) AS waiting_for_reviewer_duties,
                           COALESCE(c.actionable_structure_duties,0) AS actionable_structure_duties,
                           COALESCE(c.actionable_contextual_duties,0) AS actionable_contextual_duties,
                           COALESCE(c.actionable_batch_duties,0) AS actionable_batch_duties,
                           COALESCE(c.actionable_second_review_duties,0) AS actionable_second_review_duties,
                           COALESCE(c.progress_total,0) AS progress_total,
                           COALESCE(c.progress_done,0) AS progress_done,
                           COALESCE(c.progress_rejected,0) AS progress_rejected,
                           COALESCE(c.progress_approved,0) AS progress_approved,
                           COALESCE(c.progress_not_included,0) AS progress_not_included,
                           COALESCE(c.progress_context,0) AS progress_context,
                           COALESCE(c.progress_support,0) AS progress_support,
                           COALESCE(c.progress_superseded,0) AS progress_superseded,
                           COALESCE(c.progress_revised,0) AS progress_revised
                    FROM assigned a
                    LEFT JOIN counts c ON c.snapshot_id=a.snapshot_id
                    LEFT JOIN batch_counts bc ON bc.snapshot_id=a.snapshot_id
                    ORDER BY a.snapshot_id
                    """,
                    (account_id, snapshot_id or None, PRE_REVIEW_BLOCKED, account_id,
                     list(HIGH_RISK_FIELDS), list(HIGH_RISK_FIELDS)),
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
        return out

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
