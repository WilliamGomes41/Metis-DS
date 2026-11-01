"""PostgreSQL authority for mutable console documents and work objects.

Complete envelopes and object snapshots are authoritative in PostgreSQL. Local
workflow files are unused in this topology. Two processes on one instance share the store
lock and use optimistic object revisions; multiple App Service instances remain
outside the supported topology.
"""
from __future__ import annotations

from src.request_diagnostics_v1 import diagnostic_phase

from src.review.revision_workflow import current_revisions, validate_revision_write

import hashlib
import json
import logging
import re
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator, Mapping

from src.operations_console_v1 import (
    ConsoleError,
    SNAPSHOT_OBJECT_WRITE_CONFLICT,
    _objects_jsonl_bytes,
)
from src.workflows.workflow_documents_postgres_v1 import (
    PostgresWorkflowDocumentStore,
    WorkflowDocumentStoreError,
    _json_text,
    _read_legacy_runtime,
)
from src.workflows.workflow_identity_postgres_v1 import (
    PostgresIdentityAzureAuthoritativePublicationConsole,
    PostgresIdentityDurablePublicationConsole,
)
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores, workflow_transaction, workflow_transaction_active
from src.workflows.workflow_transaction_v1 import WorkflowTransactionError, _config_identity

REVIEW_STORE_REQUIRED_FOR_DOCUMENT_STORE = "workflow_review_store_required_for_document_store"


# Shared compact card shape; every consumer retains the same metadata checks.
_DOCUMENT_CARD_COLUMNS = """d.snapshot_id,d.document_id,d.source_id,d.title,d.class,d.state,
                           to_char(d.source_date,'YYYY-MM-DD') AS date,
                           d.replaces_snapshot_id,
                           d.source_version AS version,d.source_sha256 AS sha256,
                           d.publication_eligibility,d.uploader_account_id,
                           d.topic_id,t.display_name AS family,
                           d.envelope_payload->'is_live_capture' AS is_live_capture,
                           d.envelope_payload->>'acquired_at' AS acquired_at,
                           (SELECT jsonb_object_agg(k,d.envelope_payload->k)
                            FROM unnest(ARRAY['review_policy','processing_blocker','source_declaration',
                                             'review_configuration','configuration_source']) k
                            WHERE d.envelope_payload ? k) AS details,
                           d.envelope_payload->'named_reviewers' AS named_reviewers,
                           (SELECT COALESCE(jsonb_agg(v ORDER BY v),'[]'::jsonb)
                            FROM jsonb_array_elements(COALESCE(d.envelope_payload->'named_reviewers','[]'::jsonb)) v)
                           = (SELECT COALESCE(jsonb_agg(r.account_id ORDER BY r.account_id),'[]'::jsonb)
                              FROM workflow.document_reviewers r WHERE r.snapshot_id=d.snapshot_id) AS reviewers_consistent"""

def _document_cards_from_rows(rows):
    if any(not row['topic_id'] or not row['family'] for row in rows):
        raise WorkflowDocumentStoreError("workflow_topic_identity_not_prepared")
    if any(not row['reviewers_consistent'] for row in rows):
        raise WorkflowDocumentStoreError('workflow_document_reviewers_authority_mismatch')
    return [{**{key: value for key, value in row.items() if key not in {'details', 'reviewers_consistent'}},
             **(row['details'] or {})} for row in rows]


from src.workflows.operational_document_inputs_v1 import OperationalDocumentInputs


class PostgresWorkflowDocumentRuntimeStore(OperationalDocumentInputs, PostgresWorkflowDocumentStore):
    """Runtime operations added on top of the migration-only document store."""

    def review_command_quality_input(self, snapshot_id: str, object_ids: list[str]) -> list[dict[str, Any]]:
        """Existing review-evidence context, without other runs or candidates.

        review_evidence uses the latest run and the first matching candidate.
        Keep that order and its original fingerprint/origin; source fragments
        and processing history are not command inputs.
        """
        envelope=self.get_envelope(snapshot_id)
        if envelope is not None and '_document_inputs' in envelope:
            ref=envelope['_document_inputs']['quality']
            if ref is None:
                return []
            from src.workflows.formation_task_store_v1 import FormationTaskStore
            parts=FormationTaskStore(self).read_archive_inputs(ref,envelope=envelope,roles=('meta','candidate'),object_ids=object_ids)
            meta=next(v for r,_,v in parts if r=='meta')
            return [{'run_id':meta.get('run_id'),'candidates':[v for r,_,v in parts if r=='candidate']}]
        try:
            with self._connect() as con:
                row = con.execute("""
                    WITH latest AS (
                      SELECT envelope_payload->'quality_processing_runs'->-1 AS run
                      FROM workflow.documents WHERE snapshot_id=%s
                    ) SELECT CASE WHEN run IS NULL OR run='null'::jsonb THEN '[]'::jsonb
                      ELSE jsonb_build_array(jsonb_build_object('run_id',run->'run_id',
                        'candidates',COALESCE((SELECT jsonb_agg(candidate ORDER BY ordinal)
                          FROM jsonb_array_elements(COALESCE(NULLIF(run->'candidates','null'::jsonb),
                            '[]'::jsonb)) WITH ORDINALITY AS candidates(candidate,ordinal)
                          WHERE candidate->>'object_id'=ANY(%s)), '[]'::jsonb))) END AS runs
                    FROM latest
                    """, (snapshot_id, object_ids)).fetchone()
            if row is None:
                raise WorkflowDocumentStoreError('unknown_snapshot')
            return row['runs']
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_document_read_failed') from exc

    def review_document_input(self, snapshot_id: str, *, command: bool = False) -> tuple[dict[str, Any], str]:
        """Source/authorization inputs without replay and historical attempts."""
        try:
            with self._connect() as con:
                columns = _DOCUMENT_CARD_COLUMNS.replace('d.envelope_payload', 'd.review_envelope')
                projection = "d.envelope_payload - ARRAY['semantic_replay','processing_attempts','quality_processing_runs']"
                has_read_records = con.execute("SELECT to_regclass('workflow.source_read_roots') AS available").fetchone()['available']
                if command or has_read_records:
                    projection = ("(" + projection + " - 'prepared_source_extraction') || CASE "
                        "WHEN d.envelope_payload ? 'prepared_source_extraction' THEN "
                        "jsonb_build_object('prepared_source_extraction',"
                        "(d.envelope_payload->'prepared_source_extraction') - ARRAY['fragments','docling_record']) "
                        "ELSE '{}'::jsonb END")
                notice = ("jsonb_build_object('provider_evidence',jsonb_build_object('formation_incomplete',"
                          "d.envelope_payload#>'{semantic_replay,provider_evidence,formation_incomplete}'))")
                replay = "COALESCE(d.envelope_payload->'semantic_replay' NOT IN ('null'::jsonb,'{}'::jsonb),false)"
                if has_read_records:
                    projection = f"COALESCE(d.review_read_envelope,({projection}))"
                    notice = f"COALESCE(d.review_read_envelope->'_review_formation_notice',({notice}))"
                    replay = f"COALESCE((d.review_read_envelope->>'_review_has_replay')::boolean,({replay}))"
                projection=projection.replace('d.envelope_payload','workflow.current_document_envelope(d)')
                notice=notice.replace('d.envelope_payload','workflow.current_document_envelope(d)')
                replay=replay.replace('d.envelope_payload','workflow.current_document_envelope(d)')
                # Derive the physical columns from the existing owned card
                # projection. Do not materialize d.* and its raw source archive.
                physical = (set(re.findall(r'\bd\.([a-z_][a-z_0-9]*)', columns)) - {'review_envelope'}) | {
                    'object_generation','revision','topic_id','snapshot_id'}
                if has_read_records:
                    physical.add('review_source_ref')
                selected = ','.join('d.' + name for name in sorted(physical))
                row = con.execute(
                    "WITH selected AS MATERIALIZED ("
                    f"SELECT {selected}, {projection} AS review_envelope, {notice} AS formation_notice, "
                    f"{replay} AS has_replay FROM workflow.documents d WHERE snapshot_id=%s) "
                    f"SELECT {columns}, d.object_generation, d.revision, d.review_envelope, "
                    + ("d.review_source_ref, " if has_read_records else "NULL::jsonb AS review_source_ref, ") +
                    "d.formation_notice,d.has_replay, "
                    "(SELECT p.payload->'processing_attempts'->0->>'state' "
                    "FROM workflow.processing_document_summaries p WHERE p.snapshot_id=d.snapshot_id) AS latest_processing_state "
                    "FROM selected d LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id", (snapshot_id,),
                ).fetchone()
            if row is None:
                raise WorkflowDocumentStoreError('unknown_snapshot')
            envelope = dict(row['review_envelope'])
            envelope.pop('_review_formation_notice', None)
            envelope.pop('_review_has_replay', None)
            if row['review_source_ref'] is not None:
                envelope['_review_source_ref'] = row['review_source_ref']
            from src.vorming.recoverable_formation_v1 import incomplete
            # A negative prefilter only: uncertain/open formation still runs
            # the existing complete check, including current source closure.
            envelope['_review_check_formation'] = incomplete({'semantic_replay': row['formation_notice']}) or (
                envelope.get('processing_storage') == 'task-v1' and (
                    not row['has_replay'] or row['latest_processing_state'] not in {'succeeded', 'incomplete_budget'}))
            card = _document_cards_from_rows([row])[0]
            envelope.update({k: v for k, v in card.items()
                             if k not in {'review_envelope', 'object_generation', 'revision',
                                          'formation_notice', 'has_replay', 'latest_processing_state', 'review_source_ref'}})
            return envelope, f"{int(row['revision'])}:{int(row['object_generation'])}"
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_document_read_failed') from exc

    def review_source_extraction(self, snapshot_id: str, record_hash: str) -> dict[str, Any]:
        """Explicit legacy source read without decoding unrelated replay/history."""
        envelope=self.get_envelope(snapshot_id)
        if envelope is not None and '_document_inputs' in envelope:
            if envelope['_document_inputs']['extraction_hash']!=record_hash:
                raise WorkflowDocumentStoreError('source_extraction_identity_mismatch')
            from src.workflows.formation_task_store_v1 import FormationTaskStore
            return FormationTaskStore(self).retained_extraction(envelope,record_hash)
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT envelope_payload->'prepared_source_extraction' AS extraction "
                    "FROM workflow.documents WHERE snapshot_id=%s "
                    "AND envelope_payload#>>'{prepared_source_extraction,record_hash}'=%s",
                    (snapshot_id, record_hash)).fetchone()
            if row is None:
                raise WorkflowDocumentStoreError('source_extraction_identity_mismatch')
            return row['extraction']
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_document_read_failed') from exc

    def review_object_histories(self, snapshot_id: str, object_ids: list[str]) -> list[dict[str, Any]]:
        """Retain lineage validation, but fetch only the requested identities."""
        if not object_ids:
            return []
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT payload FROM workflow.document_objects WHERE snapshot_id=%s "
                    "AND object_id=ANY(%s) ORDER BY position", (snapshot_id, object_ids),
                ).fetchall()
            return current_revisions([dict(row['payload']) for row in rows], snapshot_id=snapshot_id)
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_document_objects_read_failed') from exc

    def review_neighbor_ids(self, snapshot_id: str, object_ids: list[str], block_ids: list[str]) -> list[str]:
        """Current incoming dependencies, from keys derived by the object owner.

        Full histories are subsequently loaded for lineage validation. Old
        edges cannot make unrelated current objects passage dependencies.
        The lookup never detoasts unrelated candidate content.
        """
        probes = [json.dumps({'objects': [oid]}) for oid in dict.fromkeys(object_ids)]
        probes.extend(json.dumps({'blocks': [bid]}) for bid in dict.fromkeys(block_ids))
        if not probes:
            return []
        try:
            with self._connect() as con:
                rows = con.execute("""
                    SELECT DISTINCT d.object_id FROM workflow.document_objects d
                    WHERE d.snapshot_id=%s AND d.review_dependency_keys @> ANY(%s::jsonb[])
                      AND d.position=(SELECT max(latest.position)
                          FROM workflow.document_objects latest
                          WHERE latest.snapshot_id=d.snapshot_id AND latest.object_id=d.object_id)
                    """, (snapshot_id, probes)).fetchall()
            return [str(row['object_id']) for row in rows]
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_review_context_read_failed') from exc

    def review_context_choices(self, snapshot_id, object_ids):
        """Current display choices; never a substitute for lineage-checked input."""
        if not object_ids:
            return ()
        from src.review.review_passage_read_v1 import PassageContextChoice
        try:
            with self._connect() as con:
                rows = con.execute("""
                    SELECT d.payload FROM workflow.document_objects d
                    WHERE d.snapshot_id=%s AND d.object_id=ANY(%s)
                      AND d.position=(SELECT max(latest.position)
                          FROM workflow.document_objects latest
                          WHERE latest.snapshot_id=d.snapshot_id AND latest.object_id=d.object_id)
                    ORDER BY d.position
                """, (snapshot_id, object_ids)).fetchall()
            return tuple(PassageContextChoice.from_object(row['payload']) for row in rows)
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_review_context_read_failed') from exc

    def review_heading_ids(self, snapshot_id: str) -> list[str]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT DISTINCT object_id FROM workflow.document_objects WHERE snapshot_id=%s "
                    "AND payload @> ANY(ARRAY['{\"object_type\":\"heading\"}', "
                    "'{\"object_type\":\"path\"}']::jsonb[])", (snapshot_id,),
                ).fetchall()
            return [str(row['object_id']) for row in rows]
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_review_context_read_failed') from exc

    def review_choice_ids(self, snapshot_id: str, object_id: str, *, query: str, page: int):
        """A bounded context picker, separate from opening the passage."""
        try:
            with self._connect() as con:
                # Empty-query browsing needs only identity/position columns.
                # Inspect payloads for a text search only when the user asks.
                search = ("AND EXISTS (SELECT 1 FROM workflow.document_objects p WHERE p.snapshot_id=%s "
                          "AND p.object_id=latest.object_id AND p.position=latest.position "
                          "AND COALESCE(p.payload->'content'->>'clean_text','') ILIKE %s) " if query.strip() else '')
                params = [snapshot_id, snapshot_id, object_id]
                if query.strip():
                    params += [snapshot_id, '%' + query.strip() + '%']
                params.append((max(page, 1)-1)*25)
                rows = con.execute("""
                    WITH latest AS (
                      SELECT DISTINCT ON (object_id) object_id,position
                      FROM workflow.document_objects WHERE snapshot_id=%s
                      ORDER BY object_id,position DESC
                    ), structural AS MATERIALIZED (
                      SELECT s.object_id FROM workflow.document_objects s
                      WHERE s.snapshot_id=%s AND s.payload @> ANY(ARRAY[
                        '{"object_type":"document"}', '{"object_type":"heading"}',
                        '{"object_type":"path"}']::jsonb[])
                      AND s.position=(SELECT position FROM latest WHERE object_id=s.object_id)
                    ), matches AS MATERIALIZED (SELECT object_id,position FROM latest
                    WHERE object_id<>%s AND object_id NOT IN (SELECT object_id FROM structural)
                    """ + search + """), selected AS (
                      SELECT object_id,position FROM matches ORDER BY position LIMIT 25 OFFSET %s
                    ) SELECT selected.object_id,(SELECT count(*) FROM matches) AS total
                    FROM (SELECT 1) AS one LEFT JOIN selected ON true ORDER BY selected.position
                    """, tuple(params)).fetchall()
            return [str(row['object_id']) for row in rows if row['object_id'] is not None], int(rows[0]['total'])
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_review_context_read_failed') from exc

    def verify_cutover_schema(self) -> None:
        try:
            with self._connect() as con:
                self._verify_schema_connection(con)
                rows = con.execute(
                    "SELECT table_name,column_name,is_generated,generation_expression FROM information_schema.columns "
                    "WHERE table_schema='workflow' AND "
                    "((table_name='documents' AND column_name IN ('envelope_payload','processing_storage_version','object_generation','document_storage_version')) OR "
                    "(table_name='document_objects' AND column_name IN ('position','review_dependency_keys')))"
                ).fetchall()
                present = {(str(row["table_name"]), str(row["column_name"])) for row in rows}
                required = {("documents", "envelope_payload"), ("document_objects", "position"),
                            ("document_objects", "review_dependency_keys"),
                            ("documents","processing_storage_version"),("documents","object_generation"),("documents","document_storage_version")}
                if present != required:
                    raise WorkflowDocumentStoreError("workflow_document_cutover_schema_missing")
                dependency = next(row for row in rows if row['table_name']=='document_objects'
                                  and row['column_name']=='review_dependency_keys')
                if (dependency.get('is_generated') != 'ALWAYS'
                        or (dependency.get('generation_expression') or '').replace(' ', '').replace('workflow.', '')
                        != 'review_dependency_keys(payload)'):
                    raise WorkflowDocumentStoreError('workflow_review_dependency_schema_invalid')
                task_tables = {str(r["tablename"]) for r in con.execute(
                    "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='workflow'").fetchall()}
                if not {"processing_attempts","processing_document_summaries","processing_checkpoints",
                        "prepared_extraction_versions","formation_inputs","formation_contexts",
                        "formation_task_results","formation_task_findings","formation_task_result_history","formation_task_plans","formation_source_views"} <= task_tables:
                    raise WorkflowDocumentStoreError("workflow_formation_task_schema_missing")
                try:
                    unresolved = con.execute(
                        "SELECT COUNT(*) AS n FROM workflow.documents d "
                        "LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id "
                        "WHERE d.topic_id IS NULL OR t.topic_id IS NULL"
                    ).fetchone()
                except WorkflowDocumentStoreError:
                    raise
                except Exception as exc:
                    raise WorkflowDocumentStoreError("workflow_topic_identity_check_failed") from exc
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_cutover_schema_check_failed") from exc
        if unresolved and int(unresolved["n"]):
            raise WorkflowDocumentStoreError("workflow_topic_identity_not_prepared")

    @staticmethod
    def _payload(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value  # psycopg decoded this JSON for this read only
        if isinstance(value, str):
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        raise WorkflowDocumentStoreError("workflow_document_envelope_payload_invalid")

    def _reviewers(self, con: Any, snapshot_id: str) -> list[str]:
        return [
            str(row["account_id"])
            for row in con.execute(
                "SELECT account_id FROM workflow.document_reviewers "
                "WHERE snapshot_id=%s ORDER BY account_id",
                (snapshot_id,),
            ).fetchall()
        ]

    def _envelope_from_row(self, con: Any, row: Mapping[str, Any], *, include_processing=True) -> dict[str, Any]:
        if row.get("envelope_payload") is None:
            raise WorkflowDocumentStoreError("workflow_document_cutover_not_prepared")
        topic_id = str(row.get("topic_id") or "")
        display_name = str(row.get("display_name") or "")
        if not topic_id or not display_name:
            raise WorkflowDocumentStoreError("workflow_topic_identity_not_prepared")
        envelope = self._payload(row["envelope_payload"])
        snapshot_id = str(row["snapshot_id"])
        if str(envelope.get("snapshot_id") or "") != snapshot_id:
            raise WorkflowDocumentStoreError("workflow_document_envelope_identity_mismatch")
        reviewers = self._reviewers(con, snapshot_id)
        payload_reviewers = sorted(str(x) for x in envelope.get("named_reviewers") or [])
        if reviewers != payload_reviewers:
            raise WorkflowDocumentStoreError("workflow_document_reviewers_authority_mismatch")
        envelope["topic_id"] = topic_id
        envelope["family"] = display_name
        if include_processing and envelope.get("processing_storage") == "task-v1" and "_document_inputs" not in envelope:
            from src.workflows.formation_task_store_v1 import FormationTaskStore
            envelope["processing_attempts"] = FormationTaskStore.attempts(con, snapshot_id,include_versions=True)
        return envelope

    @diagnostic_phase('document_store_read')
    def list_envelopes(self):
        """Only stored metadata, including during constructor and map refresh."""
        with self._connect() as con:
            rows=con.execute('SELECT d.snapshot_id,d.topic_id,CASE WHEN d.document_storage_version=1 THEN workflow.current_document_envelope(d) '
                "ELSE COALESCE(CASE WHEN d.class<>'beslisboom' THEN d.review_read_envelope END,workflow.document_scalar_envelope(d)||jsonb_build_object("
                "'named_reviewers',ARRAY(SELECT account_id FROM workflow.document_reviewers WHERE snapshot_id=d.snapshot_id ORDER BY account_id),"
                "'_metadata_header_unprepared',true)) END AS envelope_payload,t.display_name "
                'FROM workflow.documents d LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id '
                'ORDER BY d.acquired_at,d.snapshot_id').fetchall()
            result=[]
            for row in rows:
                if row['envelope_payload'] is None:
                    raise WorkflowDocumentStoreError('workflow_document_header_unprepared')
                envelope=self._envelope_from_row(con,row,include_processing=False)
                envelope.pop('_review_formation_notice',None)
                envelope.pop('_review_has_replay',None)
                if '_document_inputs' not in envelope:
                    envelope['_document_header_only']=True
                result.append(envelope)
            return result

    def list_processing_history_inputs(self):
        return [self.processing_history_input(h['snapshot_id']) for h in self.list_envelopes()]

    def list_document_cards(self, snapshot_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """List/chooser data, without replay, extraction, attempts or object rows."""
        if snapshot_ids == []:
            return []
        try:
            with self._connect() as con:
                rows = con.execute(f"""
                    SELECT {_DOCUMENT_CARD_COLUMNS.replace('d.envelope_payload','workflow.current_document_envelope(d)')}
                    FROM workflow.documents d LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id
                """ + (" WHERE d.snapshot_id=ANY(%s)" if snapshot_ids is not None else "")
                    + " ORDER BY d.acquired_at,d.snapshot_id",
                    ((snapshot_ids,) if snapshot_ids is not None else ())).fetchall()
            return _document_cards_from_rows(rows)
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_cards_read_failed") from exc

    def list_document_summaries(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """Metadata only; status history is selected separately for the visible page."""
        try:
            with self._connect() as con:
                rows = con.execute("""
                    SELECT d.snapshot_id,d.title,d.source_version AS version,d.class,d.state,
                           d.publication_eligibility,
                           workflow.current_document_envelope(d)->>'processing_blocker' AS processing_blocker,
                           CASE WHEN d.processing_storage_version=1 THEN
                               (SELECT p.payload->'processing_attempts'->0->>'state' FROM workflow.processing_document_summaries p WHERE p.snapshot_id=d.snapshot_id)
                               ELSE workflow.current_document_envelope(d)->'processing_attempts'->-1->>'state' END AS latest_processing_state,
                           CASE WHEN d.processing_storage_version=1 THEN
                               (SELECT p.payload->'processing_attempts'->0->>'expires_at' FROM workflow.processing_document_summaries p WHERE p.snapshot_id=d.snapshot_id)
                               ELSE workflow.current_document_envelope(d)->'processing_attempts'->-1->>'expires_at' END AS latest_processing_expires_at,
                           ARRAY(SELECT r.account_id FROM workflow.document_reviewers r
                                 WHERE r.snapshot_id=d.snapshot_id ORDER BY r.account_id) AS named_reviewers,
                           (SELECT COALESCE(jsonb_agg(v ORDER BY v),'[]'::jsonb)
                            FROM jsonb_array_elements(COALESCE(workflow.current_document_envelope(d)->'named_reviewers','[]'::jsonb)) v)
                           = (SELECT COALESCE(jsonb_agg(r.account_id ORDER BY r.account_id),'[]'::jsonb)
                              FROM workflow.document_reviewers r WHERE r.snapshot_id=d.snapshot_id) AS reviewers_consistent
                    FROM workflow.documents d ORDER BY d.acquired_at,d.snapshot_id
                """ + (" LIMIT %s" if limit is not None else ""), ((limit,) if limit is not None else ())).fetchall()
            if any(not row['reviewers_consistent'] for row in rows):
                raise WorkflowDocumentStoreError("workflow_document_reviewers_authority_mismatch")
            return [dict(row) for row in rows]
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_summaries_read_failed") from exc

    def document_processing_inputs(self, snapshot_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Stored retry/status fields only for the selected authorized page."""
        if not snapshot_ids:
            return {}
        try:
            with self._connect() as con:
                rows = con.execute("""
                    SELECT d.snapshot_id, d.title, d.source_version AS version,
                           d.class, d.state, d.publication_eligibility,
                           d.source_sha256 AS sha256,
                           workflow.current_document_envelope(d)->>'processing_blocker' AS processing_blocker,
                           COALESCE(workflow.current_document_envelope(d)->'review_passes', '{}'::jsonb)<>'{}'::jsonb AS has_review_passes,
                           jsonb_strip_nulls(jsonb_build_object('consumed_by', workflow.current_document_envelope(d)->'processing_recovery'->'consumed_by',
                               'source_hash', workflow.current_document_envelope(d)->'processing_recovery'->'source_hash',
                               'source_version', workflow.current_document_envelope(d)->'processing_recovery'->'source_version')) AS processing_recovery,
                           CASE WHEN d.processing_storage_version=1 THEN
                               COALESCE((SELECT jsonb_agg(p.payload-'diagnostic' ORDER BY p.started_at,p.attempt_id)
                                   FROM workflow.processing_attempts p WHERE p.snapshot_id=d.snapshot_id),'[]'::jsonb)
                           ELSE COALESCE((SELECT jsonb_agg(jsonb_build_object(
                               'state', a->'state', 'kind', a->'kind',
                               'attempt_id', a->'attempt_id', 'expires_at', a->'expires_at',
                               'error_code', a->'error_code', 'retry_not_before', a->'retry_not_before',
                               'formation_progress_made', a->'formation_progress_made',
                               'limits', jsonb_strip_nulls(jsonb_build_object('max_attempts', a->'limits'->'max_attempts')),
                               'transport', jsonb_build_object('external_cancellation', a->'transport'->'external_cancellation')
                           ) ORDER BY n)
                             FROM jsonb_array_elements(COALESCE(workflow.current_document_envelope(d)->'processing_attempts', '[]'::jsonb))
                                  WITH ORDINALITY AS attempts(a,n)), '[]'::jsonb) END AS processing_attempts,
                           ARRAY(SELECT r.account_id FROM workflow.document_reviewers r
                                 WHERE r.snapshot_id=d.snapshot_id ORDER BY r.account_id) AS named_reviewers
                    FROM workflow.documents d WHERE d.snapshot_id=ANY(%s) ORDER BY d.acquired_at,d.snapshot_id
                """, (snapshot_ids,)).fetchall()
            return {str(row["snapshot_id"]): dict(row) for row in rows}
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_summaries_read_failed") from exc

    def document_diagnostic_inputs(self, snapshot_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Small stored-admission projection; no source/candidate text or hashing."""
        if not snapshot_ids:
            return {}
        try:
            with self._connect() as con:
                invalid = con.execute(
                    "SELECT 1 FROM workflow.document_objects WHERE snapshot_id=ANY(%s) AND position IS NULL LIMIT 1",
                    (snapshot_ids,)).fetchone()
                if invalid:
                    raise WorkflowDocumentStoreError("workflow_document_cutover_not_prepared")
                rows = con.execute("""
                    WITH latest AS (
                        SELECT DISTINCT ON (snapshot_id,object_id)
                               snapshot_id,object_id,payload
                        FROM workflow.document_objects WHERE snapshot_id=ANY(%s)
                        ORDER BY snapshot_id,object_id,position DESC NULLS LAST
                    )
                    SELECT snapshot_id,object_id,
                           jsonb_build_object('gate_result',payload->'metadata'->'admission'->'gate_result',
                                              'reason_codes',payload->'metadata'->'admission'->'reason_codes') AS admission
                    FROM latest ORDER BY snapshot_id,object_id
                """, (snapshot_ids,)).fetchall()
                bindings = con.execute(
                    "SELECT DISTINCT snapshot_id FROM workflow.publish_authorizations WHERE snapshot_id=ANY(%s)",
                    (snapshot_ids,)).fetchall()
            result = {sid: {"objects": [], "has_bindings": False} for sid in snapshot_ids}
            for row in rows:
                result[str(row["snapshot_id"])]["objects"].append({
                    "object_id": row["object_id"], "metadata": {"admission": row["admission"] or {}}})
            for row in bindings:
                result[str(row["snapshot_id"])]["has_bindings"] = True
            return result
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_diagnostics_read_failed") from exc

    def list_source_selection_summaries(self) -> list[dict[str, Any]]:
        """Read only the atomically maintained, versioned overview projection.

        Never fall back to the large envelope during staged migration. The
        original payload remains authoritative; its writers update this derived
        column in the same database transaction through migration 020's trigger.
        """
        try:
            with self._connect() as con:
                rows = con.execute("""
                    SELECT d.snapshot_id,d.title,d.source_version AS version,d.class,d.content_kind,
                           d.publication_eligibility,(d.source_selection_summary || COALESCE(p.payload,'{}'::jsonb)) AS summary,
                           ARRAY(SELECT r.account_id FROM workflow.document_reviewers r
                                 WHERE r.snapshot_id=d.snapshot_id ORDER BY r.account_id)
                           = ARRAY(SELECT jsonb_array_elements_text(COALESCE(
                               d.source_selection_summary->'named_reviewers','[]'::jsonb)) ORDER BY 1)
                           AS reviewers_consistent
                    FROM workflow.documents d
                    LEFT JOIN workflow.processing_document_summaries p ON p.snapshot_id=d.snapshot_id
                    ORDER BY d.acquired_at,d.snapshot_id
                """).fetchall()
            if any(not isinstance(row['summary'], dict)
                   or type(row['summary'].get('schema_version')) is not int
                   or row['summary'].get('schema_version') != 1 for row in rows):
                raise WorkflowDocumentStoreError('workflow_source_summary_backfill_required')
            if any(not row['reviewers_consistent'] for row in rows):
                raise WorkflowDocumentStoreError('workflow_document_reviewers_authority_mismatch')
            return [{**{k: v for k, v in row.items() if k not in {'summary', 'reviewers_consistent'}},
                     **{k: v for k, v in row['summary'].items()
                        if k != 'schema_version' and k not in row}} for row in rows]
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_source_summaries_read_failed") from exc

    def dispatched_snapshot_ids(self, *, clock, limit=None, after_snapshot=None) -> list[str]:
        """Bound discovery to pending work and expiry candidates, never claimed live work."""
        if limit is not None and limit <= 0:
            return []
        try:
            with self._connect() as con:
                rows = con.execute("""
                    SELECT d.snapshot_id FROM workflow.documents d
                    WHERE (d.processing_storage_version=1 AND EXISTS (
                        SELECT 1 FROM workflow.processing_attempts a WHERE a.snapshot_id=d.snapshot_id
                        AND a.payload->>'state'='running' AND a.payload->'dispatch' IS NOT NULL
                        AND (a.payload->'dispatch'->>'state'='pending' OR (a.payload->>'expires_at')::timestamptz<=%s
                            OR (a.payload->'dispatch'->>'version' IN ('source-dispatch-v2','source-dispatch-v3') AND
                                ((a.payload->'dispatch'->>'lease_expires_at')::timestamptz<=%s
                                 OR (a.payload->'dispatch'->>'budget_expires_at')::timestamptz<=%s)))))
                    OR (d.processing_storage_version IS NULL AND EXISTS (SELECT 1 FROM jsonb_array_elements(
                        COALESCE(NULLIF(d.envelope_payload->'processing_attempts','null'::jsonb),'[]'::jsonb)) AS a
                        WHERE a->>'state'='running' AND a->'dispatch' IS NOT NULL
                          AND (a->'dispatch'->>'state'='pending' OR (a->>'expires_at')::timestamptz<=%s)))
                    ORDER BY CASE WHEN (d.acquired_at,d.snapshot_id) <=
                        (SELECT p.acquired_at,p.snapshot_id FROM workflow.documents p WHERE p.snapshot_id=%s)
                        THEN 1 ELSE 0 END, d.acquired_at,d.snapshot_id
                """ + (" LIMIT %s" if limit is not None else ""),
                    ((clock, clock, clock, clock, after_snapshot, limit) if limit is not None else (clock, clock, clock, clock, after_snapshot))).fetchall()
            return [str(row["snapshot_id"]) for row in rows]
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_dispatch_discovery_failed") from exc

    def get_envelope(self, snapshot_id: str) -> dict[str, Any] | None:
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT d.snapshot_id,d.topic_id,workflow.current_document_envelope(d) AS envelope_payload,t.display_name "
                    "FROM workflow.documents d "
                    "LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id "
                    "WHERE d.snapshot_id=%s",
                    (snapshot_id,),
                ).fetchone()
                return self._envelope_from_row(con, row) if row else None
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_read_failed") from exc

    def list_document_objects(self, snapshot_id: str) -> list[dict[str, Any]]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT position,payload FROM workflow.document_objects WHERE snapshot_id=%s ORDER BY position",
                    (snapshot_id,),
                ).fetchall()
            if any(row["position"] is None for row in rows):
                raise WorkflowDocumentStoreError("workflow_document_cutover_not_prepared")
            return [
                dict(row["payload"]) if isinstance(row["payload"], dict) else json.loads(row["payload"])
                for row in rows
            ]
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_objects_read_failed") from exc

    def list_current_objects_batch(self, snapshot_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        """Read current object versions once, preserving the existing position order."""
        if not snapshot_ids:
            return {}
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT snapshot_id,position,payload FROM workflow.document_objects "
                    "WHERE snapshot_id=ANY(%s) ORDER BY snapshot_id,position",
                    (snapshot_ids,),
                ).fetchall()
            histories = {sid: [] for sid in snapshot_ids}
            for row in rows:
                if row["position"] is None:
                    raise WorkflowDocumentStoreError("workflow_document_cutover_not_prepared")
                obj = dict(row["payload"]) if isinstance(row["payload"], dict) else json.loads(row["payload"])
                histories[str(row["snapshot_id"])].append(obj)
            return {sid: current_revisions(objects, snapshot_id=sid) for sid, objects in histories.items()}
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_objects_read_failed") from exc

    @staticmethod
    def _revision(rows: list[dict[str, Any]]) -> str:
        return hashlib.sha256(_objects_jsonl_bytes(rows)).hexdigest()

    def revision_for_rows(self, rows: list[dict[str, Any]]) -> str:
        """Return the optimistic-concurrency token represented by these rows."""
        return self._revision(rows)

    def _objects_locked(self, con: Any, snapshot_id: str) -> list[dict[str, Any]]:
        rows = con.execute(
            "SELECT position,payload FROM workflow.document_objects WHERE snapshot_id=%s "
            "ORDER BY position FOR UPDATE",
            (snapshot_id,),
        ).fetchall()
        if any(row["position"] is None for row in rows):
            raise WorkflowDocumentStoreError("workflow_document_cutover_not_prepared")
        return [
            dict(row["payload"]) if isinstance(row["payload"], dict) else json.loads(row["payload"])
            for row in rows
        ]

    def _write_objects_locked(
        self, con: Any, snapshot_id: str, current: list[dict[str, Any]], following: list[dict[str, Any]],
    ) -> None:
        """Store ``following`` as the snapshot's object list, writing only the difference.

        The result equals deleting every row and inserting ``following`` at
        positions 0..n-1, but unchanged rows are not touched, so the cost (and the
        per-row ``advance_object_generation`` trigger) follows the change, not the
        document size (MET-36). The caller holds the document row lock.
        """
        before = {(str(row["object_id"]), str(row["object_version"])): row for row in current}
        stored = {
            (row["object_id"], row["object_version"]): row["position"]
            for row in con.execute(
                "SELECT object_id,object_version,position FROM workflow.document_objects WHERE snapshot_id=%s",
                (snapshot_id,),
            ).fetchall()
        }
        kept = {(str(obj["object_id"]), str(obj["object_version"])) for obj in following}
        for object_id, object_version in sorted(set(stored) - kept):
            con.execute(
                "DELETE FROM workflow.document_objects WHERE snapshot_id=%s AND object_id=%s AND object_version=%s",
                (snapshot_id, object_id, object_version),
            )
        for position, obj in enumerate(following):
            identity = (str(obj["object_id"]), str(obj["object_version"]))
            if identity not in stored:
                con.execute(
                    "INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,position) "
                    "VALUES(%s,%s,%s,%s::jsonb,%s)",
                    (snapshot_id, *identity, _json_text(obj), position),
                )
            # Compare the stored text, not Python equality: 1 == 1.0 in Python but
            # not in the stored JSON or the revision hash.
            elif identity not in before or _json_text(before[identity]) != _json_text(obj):
                con.execute(
                    "UPDATE workflow.document_objects SET payload=%s::jsonb,position=%s,revision=revision+1,"
                    "updated_at=CURRENT_TIMESTAMP WHERE snapshot_id=%s AND object_id=%s AND object_version=%s",
                    (_json_text(obj), position, snapshot_id, *identity),
                )
            elif stored[identity] != position:
                con.execute(
                    "UPDATE workflow.document_objects SET position=%s "
                    "WHERE snapshot_id=%s AND object_id=%s AND object_version=%s",
                    (position, snapshot_id, *identity),
                )

    def objects_revision(self, snapshot_id: str) -> str:
        return self._revision(self.list_document_objects(snapshot_id))

    def _write_envelope_locked(self, con: Any, envelope: Mapping[str, Any], *, document_storage_admission=False) -> None:
        if document_storage_admission and "_document_inputs" in envelope:
            raise WorkflowDocumentStoreError("document_inputs_existing_document_requires_explicit_preparation")
        if self._write_operational_envelope_locked(con,envelope):
            return
        topic = self._resolve_topic_locked(con, str(envelope.get("family") or ""))
        stored_envelope = deepcopy(dict(envelope))
        stored_envelope["topic_id"] = topic["topic_id"]
        stored_envelope["family"] = topic["display_name"]
        task_storage = stored_envelope.get("processing_storage") == "task-v1"
        attempts = stored_envelope.pop("processing_attempts", []) if task_storage else []
        if task_storage:
            if isinstance(stored_envelope.get('semantic_replay'), dict):
                from src.workflows.formation_evidence_v1 import activation_replay
                stored_envelope['semantic_replay'] = activation_replay(stored_envelope['semantic_replay'])
        values = self._document_values(stored_envelope)
        topic_values = (*values[:5], topic["topic_id"], *values[5:])
        snapshot_id = str(stored_envelope["snapshot_id"])
        existing = con.execute(
            "SELECT snapshot_id,envelope_payload,processing_storage_version FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
            (snapshot_id,),
        ).fetchone()
        if document_storage_admission and existing is not None:
            raise WorkflowDocumentStoreError('document_inputs_existing_document_requires_explicit_preparation')
        unchanged = bool(task_storage and existing is not None
            and self._payload(existing["envelope_payload"]) == stored_envelope
            and self._reviewers(con,snapshot_id) == sorted(set(stored_envelope.get("named_reviewers") or [])))
        if existing is None:
            con.execute(
                "INSERT INTO workflow.documents("
                "snapshot_id,source_id,document_id,title,family,topic_id,class,state,publication_eligibility,content_kind,"
                "ingest_kind,source_version,source_date,source_sha256,source_locator,immutable_storage_locator,"
                "live_url,uploader_account_id,replaces_snapshot_id,object_diff,clinical_rereview_required,"
                "acquired_at,console_version,envelope_payload) VALUES("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb)",
                (*topic_values, _json_text(stored_envelope)),
            )
        elif not unchanged:
            con.execute(
                "UPDATE workflow.documents SET "
                "source_id=%s,document_id=%s,title=%s,family=%s,topic_id=%s,class=%s,state=%s,publication_eligibility=%s,"
                "content_kind=%s,ingest_kind=%s,source_version=%s,source_date=%s,source_sha256=%s,source_locator=%s,"
                "immutable_storage_locator=%s,live_url=%s,uploader_account_id=%s,replaces_snapshot_id=%s,"
                "object_diff=%s::jsonb,clinical_rereview_required=%s,acquired_at=%s,console_version=%s,"
                "envelope_payload=%s::jsonb,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE snapshot_id=%s",
                (*topic_values[1:], _json_text(stored_envelope), snapshot_id),
            )
        if not unchanged:
            con.execute("DELETE FROM workflow.document_reviewers WHERE snapshot_id=%s", (snapshot_id,))
            for reviewer in sorted(set(str(x) for x in stored_envelope.get("named_reviewers") or [])):
                con.execute(
                    "INSERT INTO workflow.document_reviewers(snapshot_id,account_id) VALUES(%s,%s)",
                    (snapshot_id, reviewer),
                )
        if task_storage:
            from src.workflows.formation_task_store_v1 import FormationTaskStore
            if existing is None or existing["processing_storage_version"] != 1:
                con.execute("UPDATE workflow.documents SET processing_storage_version=1 WHERE snapshot_id=%s", (snapshot_id,))
            FormationTaskStore.save_attempts(con, snapshot_id, attempts)
        if document_storage_admission:
            self.admit_new_document_locked(con,snapshot_id)

    def write_bundle(
        self,
        *,
        envelope: Mapping[str, Any],
        objects: list[dict[str, Any]] | None = None,
        expected_revision: str | None = None,
        review_card_preparation=None,
        formation_activation_ref=None,
        document_storage_admission=False,
    ) -> str:
        snapshot_id = str(envelope.get("snapshot_id") or "")
        if not snapshot_id:
            raise WorkflowDocumentStoreError("workflow_document_metadata_incomplete")
        if formation_activation_ref is not None and objects is None:
            raise WorkflowDocumentStoreError('formation_evidence_activation_objects_required')
        try:
            with self._connect() as con:
                with con.transaction():
                    exists = con.execute(
                        "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                        (snapshot_id,),
                    ).fetchone()
                    current_objects: list[dict[str, Any]] = []
                    if exists is not None:
                        current_objects = self._objects_locked(con, snapshot_id)
                        if expected_revision is not None and self._revision(current_objects) != expected_revision:
                            raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                    elif expected_revision not in (None, ""):
                        raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)

                    if objects is not None:
                        from src.workflows.formation_task_store_v1 import FormationTaskStore
                        FormationTaskStore.assert_activation(con,envelope,formation_activation_ref)
                    self._write_envelope_locked(con, envelope,document_storage_admission=document_storage_admission)
                    from src.workflows.review_card_inputs_postgres_v1 import publish_preparation
                    publish_preparation(self, con, snapshot_id, review_card_preparation)
                    next_objects = current_objects if objects is None else objects
                    identities = [
                        (str(row.get("object_id") or ""), str(row.get("object_version") or ""))
                        for row in next_objects
                    ]
                    if any(not a or not b for a, b in identities) or len(set(identities)) != len(identities):
                        raise WorkflowDocumentStoreError("workflow_object_identity_invalid")
                    if objects is not None:
                        validate_revision_write(current_objects, next_objects, snapshot_id=snapshot_id)
                        self._write_objects_locked(con, snapshot_id, current_objects, next_objects)
                        from src.workflows.review_card_inputs_postgres_v1 import maintain
                        maintain(self, con, snapshot_id, next_objects, complete=True, preparation=review_card_preparation)
            return self._revision(next_objects)
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_bundle_write_failed") from exc

    def delete_document(self, snapshot_id: str) -> None:
        """Delete one mutable workflow document while preserving review-ledger history."""
        try:
            with self._connect() as con:
                with con.transaction():
                    row = con.execute(
                        "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                        (snapshot_id,),
                    ).fetchone()
                    if row is None:
                        raise WorkflowDocumentStoreError("workflow_document_delete_missing")
                    successor = con.execute(
                        "SELECT snapshot_id FROM workflow.documents WHERE replaces_snapshot_id=%s LIMIT 1",
                        (snapshot_id,),
                    ).fetchone()
                    if successor is not None:
                        raise WorkflowDocumentStoreError("workflow_document_delete_has_successor")
                    con.execute(
                        "UPDATE workflow.review_events SET snapshot_id=NULL WHERE snapshot_id=%s",
                        (snapshot_id,),
                    )
                    con.execute(
                        "DELETE FROM workflow.documents WHERE snapshot_id=%s",
                        (snapshot_id,),
                    )
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_delete_failed") from exc

    def prepare_legacy_cutover(self, runtime: Path) -> dict[str, int]:
        """Backfill full envelope and original object order after exact migration proof."""
        bundles = _read_legacy_runtime(Path(runtime))
        prepared = 0
        try:
            for bundle in bundles:
                envelope = bundle["envelope"]
                objects = bundle["objects"]
                snapshot_id = str(envelope["snapshot_id"])
                with self._connect() as con:
                    with con.transaction():
                        row = con.execute(
                            "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                            (snapshot_id,),
                        ).fetchone()
                        if row is None:
                            raise WorkflowDocumentStoreError("workflow_document_cutover_requires_migration")
                        self._assert_existing_matches(con, envelope, objects)
                        con.execute(
                            "UPDATE workflow.documents SET envelope_payload=%s::jsonb WHERE snapshot_id=%s",
                            (_json_text(envelope), snapshot_id),
                        )
                        for position, obj in enumerate(objects):
                            con.execute(
                                "UPDATE workflow.document_objects SET position=%s "
                                "WHERE snapshot_id=%s AND object_id=%s AND object_version=%s",
                                (position, snapshot_id, obj["object_id"], obj["object_version"]),
                            )
                prepared += 1
            return {"documents": len(bundles), "prepared": prepared}
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_cutover_prepare_failed") from exc


class _PostgresWorkflowDocumentsMixin:
    workflow_document_store: PostgresWorkflowDocumentRuntimeStore

    def __init__(
        self,
        *args: Any,
        workflow_document_store: PostgresWorkflowDocumentRuntimeStore,
        **kwargs: Any,
    ) -> None:
        self._require_review_authority()
        super().__init__(*args, **kwargs)
        self.workflow_document_store = workflow_document_store
        self.workflow_document_store.verify_cutover_schema()
        self.refresh_workflow_documents()

    def _require_review_authority(self) -> None:
        """Naad B: only classes that carry the PostgreSQL review mixin may construct."""
        if not getattr(type(self), "_metis_workflow_review_authority", False):
            raise RuntimeError(REVIEW_STORE_REQUIRED_FOR_DOCUMENT_STORE)

    def _require_review_store_configured(self) -> None:
        """Naad C (#665): documents writes need a PG review store on the same database (compared only, NOOIT logged)."""
        review_store = getattr(self, "workflow_review_store", None)
        try:
            same_database = isinstance(review_store, PostgresWorkflowReviewStore) and _config_identity(
                review_store) == _config_identity(getattr(self, "workflow_document_store", None))
        except WorkflowTransactionError:
            same_database = False
        if not same_database:
            raise RuntimeError(REVIEW_STORE_REQUIRED_FOR_DOCUMENT_STORE)

    def refresh_workflow_documents(self) -> None:
        try:
            envelopes = self.workflow_document_store.list_envelopes()
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        self._envelopes = {str(row["snapshot_id"]): row for row in envelopes}

    @diagnostic_phase("document_list")
    def list_envelopes(self) -> list[dict[str, Any]]:
        """Read the authoritative list instead of a process-local startup cache."""
        reads = self._document_reads()
        if reads is not None:
            return [self._receipt(row) for row in self._scoped_envelopes(reads).values()]
        try:
            return [self._receipt(self.workflow_document_store.get_envelope(row['snapshot_id'])
                if row.get('_metadata_header_unprepared') else row)
                for row in self.workflow_document_store.list_envelopes()]
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc

    def _scoped_envelopes(self, reads) -> dict[str, dict[str, Any]]:
        """Populate automatically; earlier single-document snapshots keep ownership."""
        if not reads.listed:
            try:
                rows = self.workflow_document_store.list_envelopes()
            except WorkflowDocumentStoreError as exc:
                raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
            existing = reads.envelopes
            reads.envelopes = {str(row["snapshot_id"]): existing.get(str(row["snapshot_id"]), row) for row in rows}
            # A document removed after its first read is still part of this operation.
            reads.envelopes.update({sid: row for sid, row in existing.items() if sid not in reads.envelopes})
            reads.listed = True
        return reads.envelopes

    @diagnostic_phase("document_list")
    def source_selection_documents(self, *, actor_id: str, document: str = "") -> list[dict[str, Any]]:
        from src.workflows.workflow_transaction_v1 import workflow_read_transaction
        from src.vorming.source_selection_v1 import authorize_account
        actor = self._account(actor_id, current=True)
        if actor.get("retirement"):
            raise ConsoleError("not_authenticated")
        try:
            with workflow_read_transaction(self.workflow_document_store):
                documents = self.workflow_document_store.list_source_selection_summaries()
            # Full payload decoding and detail authorization must not leave the
            # bounded overview transaction idle before its next SQL statement.
            selected = self._envelope(document) if document else None
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable") from exc
        if selected is not None:
            authorize_account(actor, selected)
        visible = []
        for row in documents:
            try:
                authorize_account(actor, row)
            except ConsoleError as exc:
                if exc.code not in {"reviewer_not_named_on_snapshot", "researcher_role_required"}:
                    raise
            else:
                visible.append(row)
        return visible

    @diagnostic_phase("document_list")
    def list_document_cards(self) -> list[dict[str, Any]]:
        reads = self._document_reads()
        try:
            if reads is None:
                return self.workflow_document_store.list_document_cards()
            if reads.cards is None:
                reads.cards = self.workflow_document_store.list_document_cards()
            # Public list callers keep their own small mutable output.
            return deepcopy(reads.cards)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc

    @diagnostic_phase("document_load")
    def _envelope(self, snapshot_id: str) -> dict[str, Any]:
        from src.review.review_command_state_v1 import active_review_command
        command = active_review_command(self, snapshot_id)
        if command is not None:
            return deepcopy(command.envelope)
        reads = self._document_reads()
        if reads is not None and snapshot_id in reads.envelopes and not reads.envelopes[snapshot_id].get('_document_header_only'):
            from src.request_diagnostics_v1 import diagnostic_count
            diagnostic_count("document_snapshot_reused")
            return reads.envelopes[snapshot_id]
        if reads is not None and reads.listed and snapshot_id not in reads.envelopes:
            raise ConsoleError("unknown_snapshot")
        try:
            envelope = self.workflow_document_store.get_envelope(snapshot_id)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        if envelope is None:
            raise ConsoleError("unknown_snapshot")
        # The store already returns caller-owned decoded JSON. No process mirror,
        # no second/third defensive copy. Commands still reload under their lock.
        if reads is not None:
            reads.envelopes[snapshot_id] = envelope
        return envelope

    def _load_objects(self, snapshot_id: str, *, remember: bool = True) -> list[dict[str, Any]]:
        from src.review.review_command_state_v1 import active_review_command
        command = active_review_command(self, snapshot_id)
        if command is not None:
            return deepcopy(command.histories)
        reads = self._document_reads() if not remember else None
        if reads is not None and snapshot_id in reads.objects:
            return reads.objects[snapshot_id][0]
        try:
            rows = self.workflow_document_store.list_document_objects(snapshot_id)
            revision = self.workflow_document_store.revision_for_rows(rows) if remember else None
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        if remember:
            self._objects_expected_revs()[snapshot_id] = revision
        elif reads is not None:
            reads.objects[snapshot_id] = (rows, revision)
        return rows

    @diagnostic_phase("objects_read")
    def snapshot_objects_and_revision(
        self,
        snapshot_id: str,
        include_blocked: bool = False,
    ) -> tuple[list[dict[str, Any]], str]:
        """Read authoritative PostgreSQL objects once and derive their revision."""
        self._envelope(snapshot_id)
        rows = self._load_objects(snapshot_id, remember=False)
        reads = self._document_reads()
        revision = (self.objects_revision(snapshot_id) if reads is not None
                    else self.workflow_document_store.revision_for_rows(rows))
        if include_blocked:
            return deepcopy(rows), revision
        return deepcopy(current_revisions(rows, snapshot_id=snapshot_id)), revision

    def objects_revision(self, snapshot_id: str) -> str:
        from src.review.review_command_state_v1 import active_review_command
        command = active_review_command(self, snapshot_id)
        if command is not None:
            return command.revision
        reads = self._document_reads()
        if reads is not None:
            self._load_objects(snapshot_id, remember=False)
            rows, revision = reads.objects[snapshot_id]
            if revision is None:
                revision = self.workflow_document_store.revision_for_rows(rows)
                reads.objects[snapshot_id] = (rows, revision)
            return revision
        try:
            return self.workflow_document_store.objects_revision(snapshot_id)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc

    def refresh_objects_expected_revision(self, snapshot_id: str, revision: str | None = None) -> str:
        current = revision or self.objects_revision(snapshot_id)
        self._objects_expected_revs()[snapshot_id] = current
        return current



    def _save_objects(
        self,
        snapshot_id: str,
        rows: list[dict[str, Any]],
        *,
        expected_revision: str | None = None,
    ) -> None:
        self._require_review_store_configured()
        pinned = expected_revision if expected_revision is not None else self._objects_expected_revs().get(snapshot_id)
        envelope = self._envelope(snapshot_id)
        try:
            revision = self.workflow_document_store.write_bundle(
                envelope=envelope,
                objects=rows,
                expected_revision=pinned,
            )
        except WorkflowDocumentStoreError as exc:
            if str(exc) == SNAPSHOT_OBJECT_WRITE_CONFLICT:
                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=self.objects_revision(snapshot_id)) from exc
            raise ConsoleError("workflow_document_write_failed", str(exc)) from exc
        self._objects_expected_revs()[snapshot_id] = revision

    def _delete_unpublished_snapshot_authority(self, snapshot_id: str) -> None:
        self._require_review_store_configured()
        try:
            self.workflow_document_store.delete_document(snapshot_id)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_delete_failed", str(exc)) from exc
        self._envelopes.pop(snapshot_id, None)
        self._objects_expected_revs().pop(snapshot_id, None)


    def _delete_unpublished_snapshot_locked(
        self, *, actor_id: str, token: str, account: dict[str, Any], confirm_title: str,
    ) -> dict[str, Any]:
        self._require_review_store_configured()
        if workflow_transaction_active():
            raise ConsoleError("unpublished_delete_requires_independent_transaction")
        bind_workflow_stores(self.workflow_document_store, self.workflow_review_store)
        try:
            with workflow_transaction(self.workflow_document_store):
                return super()._delete_unpublished_snapshot_locked(
                    actor_id=actor_id, token=token, account=account, confirm_title=confirm_title)
        except Exception as exc:
            self._refresh_after_rollback(token, exc)
            raise

    def _save_envelopes(self) -> None:
        self._require_review_store_configured()
        payload = getattr(self, "_prepared_envelopes", None)
        source = self._envelopes if payload is None else payload
        try:
            headers={h['snapshot_id']:h for h in self.workflow_document_store.list_envelopes()}
            for envelope in source.values():
                if envelope==headers.get(envelope['snapshot_id']):
                    continue
                if envelope.get('_document_header_only'):
                    current=self.workflow_document_store.get_envelope(envelope['snapshot_id'])
                    if current is None:
                        raise WorkflowDocumentStoreError('unknown_snapshot')
                    current.update({k:v for k,v in envelope.items() if k!='_document_header_only'})
                    envelope=current
                self.workflow_document_store.write_bundle(envelope=envelope)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_write_failed", str(exc)) from exc
        self._envelopes = deepcopy(source)

    def _reload_store_locked(self) -> None:
        self.refresh_workflow_documents()

    def _apply_release_state(self, release: dict[str, Any], projection: list[dict[str, Any]]) -> None:
        """Persist the existing envelope/event effects without filesystem copies."""
        self._require_review_store_configured()
        snapshot_id = str(release["snapshot_id"])
        current = self._release_envelope(release)
        # Preserve the existing event/envelope split after canonical commit.
        # Startup reconciliation repairs either incomplete projection from PG.
        self._record_release_publication(release, current)
        try:
            self.workflow_document_store.write_bundle(envelope=current)
        except Exception as exc:
            raise ConsoleError("workflow_document_write_failed", str(exc)) from exc
        self.refresh_workflow_documents()

    def _commit_prepared_store(
        self,
        *,
        envelopes: dict[str, Any] | None = None,
        bindings: dict[str, Any] | None = None,
        objects: tuple[str, list[dict[str, Any]]] | None = None,
        expected_revision: str | None = None,
        ledger_fn: Any | None = None,
        snapshot_id: str | None = None,
        review_card_preparation=None,
        formation_activation_ref=None,
        document_storage_admission=False,
    ) -> None:
        self._require_review_store_configured()
        if formation_activation_ref is not None and objects is None:
            raise ConsoleError('formation_evidence_activation_objects_required')
        if envelopes is None and objects is None:
            # The review mixin owns the native transaction. Do not enter the
            # file-store rollback boundary for bindings/event-only commands.
            with self._store_write_lock():
                self._reload_store_locked()
                if bindings is not None and snapshot_id:
                    bindings = self._rebase_snapshot_map(self._bindings, bindings, snapshot_id)
                self._guard_prepared_working_revision_mutation(
                    envelopes=None, bindings=bindings, objects=None, snapshot_id=snapshot_id)
                if bindings is not None:
                    self._prepared_bindings = bindings
                    try:
                        self._save_bindings()
                    finally:
                        self._prepared_bindings = None
                if ledger_fn is not None:
                    ledger_fn()
            return
        with self._store_write_lock():
            # The review mixin extends this reload with authoritative bindings.
            # Refresh after taking the process-shared file lock so a stale worker
            # cannot replace another worker's already-committed snapshot maps.
            self._reload_store_locked()
            sid = snapshot_id or (objects[0] if objects is not None else None)
            if sid is None:
                raise ConsoleError("unknown_snapshot")
            # Unchanged documents remain owned by the command's freshly loaded
            # map. Only the submitted snapshot crosses a mutation/copy boundary.
            target_envelopes = dict(self._envelopes)
            if envelopes is None:
                target_envelopes[sid]=self.workflow_document_store.get_envelope(sid)
            if envelopes is not None:
                if sid in envelopes:
                    target_envelopes[sid] = deepcopy(envelopes[sid])
                else:
                    target_envelopes.pop(sid, None)
            target_bindings = deepcopy(self._bindings)
            if bindings is not None:
                target_bindings = self._rebase_snapshot_map(self._bindings, bindings, sid)
            self._guard_prepared_working_revision_mutation(
                envelopes=target_envelopes, bindings=target_bindings, objects=objects, snapshot_id=sid)
            # #665: no copy-write or ledger truncation; the native transaction rolls
            # PostgreSQL back; the review mixin refreshes only disposable process state.
            if bindings is not None:
                self._prepared_bindings = target_bindings
                try:
                    self._save_bindings()
                finally:
                    self._prepared_bindings = None
            if ledger_fn is not None:
                ledger_fn()
            envelope = target_envelopes.get(sid)
            if envelope is None:
                raise ConsoleError("unknown_snapshot")
            try:
                pinned_revision = expected_revision
                if objects is not None and pinned_revision is None:
                    pinned_revision = self._objects_expected_revs().get(sid)
                revision = self.workflow_document_store.write_bundle(
                    envelope=envelope,
                    objects=objects[1] if objects is not None else None,
                    expected_revision=pinned_revision if objects is not None else None,
                    review_card_preparation=review_card_preparation,
                    formation_activation_ref=formation_activation_ref,
                    document_storage_admission=document_storage_admission,
                )
                canonical_envelope = self.workflow_document_store.get_envelope(sid)
                if canonical_envelope is None:
                    raise ConsoleError("workflow_document_write_failed")
                target_envelopes[sid] = canonical_envelope
            except WorkflowDocumentStoreError as exc:
                if str(exc) == SNAPSHOT_OBJECT_WRITE_CONFLICT:
                    raise ConsoleError(
                        SNAPSHOT_OBJECT_WRITE_CONFLICT,
                        current_revision=self.objects_revision(sid),
                    ) from exc
                raise ConsoleError("workflow_document_write_failed", str(exc)) from exc
            self._bindings = target_bindings
            self._envelopes = target_envelopes
            if objects is not None:
                self._objects_expected_revs()[sid] = revision

    @contextmanager
    def _reprocessing_transaction(self, snapshot_id: str) -> Iterator[None]:
        """Serialize retry reservation/activation against every document writer."""
        self._require_review_store_configured()
        with self._store_write_lock():
            with workflow_transaction(self.workflow_document_store) as connection:
                connection.execute("SELECT set_config('metis.document_storage_writer','v1',true)")
                self.workflow_review_store._lock_authorizations(connection)
                row = connection.execute(
                    "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                    (snapshot_id,),
                ).fetchone()
                if row is None:
                    raise ConsoleError("unknown_snapshot")
                self._reload_store_locked()
                yield

    @contextmanager
    def _heading_batch_mutation(self, snapshot_id: str) -> Iterator[None]:
        """Lock and validate before the batch; rollback only through PostgreSQL."""
        self._require_review_store_configured()
        with self._store_write_lock():
            bind_workflow_stores(
                self.workflow_document_store,
                self.workflow_identity_store,
                getattr(self, "workflow_review_store", None),
            )
            try:
                with super()._heading_batch_mutation(snapshot_id):
                    with workflow_transaction(self.workflow_document_store) as connection:
                        review_store = getattr(self, "workflow_review_store", None)
                        if review_store is not None:
                            # Ordinary review writes take this lock before the document row.
                            review_store._lock_authorizations(connection)
                        row = connection.execute(
                            "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                            (snapshot_id,),
                        ).fetchone()
                        if row is None:
                            raise ConsoleError("unknown_snapshot")
                        self._reload_store_locked()
                        self._require_mutable_working_revision(snapshot_id)
                        yield
            finally:
                # The native transaction has completed or rolled back. Refresh
                # disposable state without changing its outcome or original error.
                try:
                    self._reload_store_locked()
                    self.refresh_objects_expected_revision(snapshot_id)
                except Exception:
                    logging.getLogger(__name__).warning("heading_batch_document_refresh_failed")

    @contextmanager
    def _atomic_snapshot_mutation(self, snapshot_id: str) -> Iterator[None]:
        """#665 (I7): the review mixin owns this context; NOOIT a rollback path here, refused before yield."""
        raise RuntimeError(REVIEW_STORE_REQUIRED_FOR_DOCUMENT_STORE)
        yield  # pragma: no cover - keeps this a generator-based context manager


class PostgresWorkflowDurablePublicationConsole(
    _PostgresWorkflowDocumentsMixin,
    PostgresIdentityDurablePublicationConsole,
):
    pass


class PostgresWorkflowAzureAuthoritativePublicationConsole(
    _PostgresWorkflowDocumentsMixin,
    PostgresIdentityAzureAuthoritativePublicationConsole,
):
    pass
