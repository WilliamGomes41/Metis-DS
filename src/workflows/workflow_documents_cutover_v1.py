"""PostgreSQL authority for mutable console documents and work objects.

Complete envelopes and object snapshots are authoritative in PostgreSQL. Local
workflow files are unused in this topology. Two processes on one instance share the store
lock and use optimistic object revisions; multiple App Service instances remain
outside the supported topology.
"""
from __future__ import annotations

from src.request_diagnostics_v1 import diagnostic_phase

from src.revision_workflow import current_revisions, validate_revision_write

import hashlib
import json
import logging
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


class PostgresWorkflowDocumentRuntimeStore(PostgresWorkflowDocumentStore):
    """Runtime operations added on top of the migration-only document store."""

    def verify_cutover_schema(self) -> None:
        self.verify_schema()
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema='workflow' AND "
                    "((table_name='documents' AND column_name='envelope_payload') OR "
                    "(table_name='document_objects' AND column_name='position'))"
                ).fetchall()
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_cutover_schema_check_failed") from exc
        present = {(str(row["table_name"]), str(row["column_name"])) for row in rows}
        required = {("documents", "envelope_payload"), ("document_objects", "position")}
        if present != required:
            raise WorkflowDocumentStoreError("workflow_document_cutover_schema_missing")
        try:
            with self._connect() as con:
                unresolved = con.execute(
                    "SELECT COUNT(*) AS n FROM workflow.documents d "
                    "LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id "
                    "WHERE d.topic_id IS NULL OR t.topic_id IS NULL"
                ).fetchone()
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_topic_identity_check_failed") from exc
        if unresolved and int(unresolved["n"]):
            raise WorkflowDocumentStoreError("workflow_topic_identity_not_prepared")

    @staticmethod
    def _payload(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return deepcopy(value)
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

    def _envelope_from_row(self, con: Any, row: Mapping[str, Any]) -> dict[str, Any]:
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
        return envelope

    @diagnostic_phase("document_store_read")
    def list_envelopes(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT d.snapshot_id,d.topic_id,d.envelope_payload,t.display_name "
                    "FROM workflow.documents d "
                    "LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id "
                    "ORDER BY d.acquired_at,d.snapshot_id"
                ).fetchall()
                return [self._envelope_from_row(con, row) for row in rows]
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_documents_read_failed") from exc

    def get_envelope(self, snapshot_id: str) -> dict[str, Any] | None:
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT d.snapshot_id,d.topic_id,d.envelope_payload,t.display_name "
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

    def objects_revision(self, snapshot_id: str) -> str:
        return self._revision(self.list_document_objects(snapshot_id))

    def _write_envelope_locked(self, con: Any, envelope: Mapping[str, Any]) -> None:
        topic = self._resolve_topic_locked(con, str(envelope.get("family") or ""))
        stored_envelope = deepcopy(dict(envelope))
        stored_envelope["topic_id"] = topic["topic_id"]
        stored_envelope["family"] = topic["display_name"]
        values = self._document_values(stored_envelope)
        topic_values = (*values[:5], topic["topic_id"], *values[5:])
        snapshot_id = str(stored_envelope["snapshot_id"])
        existing = con.execute(
            "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
            (snapshot_id,),
        ).fetchone()
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
        else:
            con.execute(
                "UPDATE workflow.documents SET "
                "source_id=%s,document_id=%s,title=%s,family=%s,topic_id=%s,class=%s,state=%s,publication_eligibility=%s,"
                "content_kind=%s,ingest_kind=%s,source_version=%s,source_date=%s,source_sha256=%s,source_locator=%s,"
                "immutable_storage_locator=%s,live_url=%s,uploader_account_id=%s,replaces_snapshot_id=%s,"
                "object_diff=%s::jsonb,clinical_rereview_required=%s,acquired_at=%s,console_version=%s,"
                "envelope_payload=%s::jsonb,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE snapshot_id=%s",
                (*topic_values[1:], _json_text(stored_envelope), snapshot_id),
            )
        con.execute("DELETE FROM workflow.document_reviewers WHERE snapshot_id=%s", (snapshot_id,))
        for reviewer in sorted(set(str(x) for x in stored_envelope.get("named_reviewers") or [])):
            con.execute(
                "INSERT INTO workflow.document_reviewers(snapshot_id,account_id) VALUES(%s,%s)",
                (snapshot_id, reviewer),
            )

    def write_bundle(
        self,
        *,
        envelope: Mapping[str, Any],
        objects: list[dict[str, Any]] | None = None,
        expected_revision: str | None = None,
    ) -> str:
        snapshot_id = str(envelope.get("snapshot_id") or "")
        if not snapshot_id:
            raise WorkflowDocumentStoreError("workflow_document_metadata_incomplete")
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

                    self._write_envelope_locked(con, envelope)
                    next_objects = current_objects if objects is None else objects
                    identities = [
                        (str(row.get("object_id") or ""), str(row.get("object_version") or ""))
                        for row in next_objects
                    ]
                    if any(not a or not b for a, b in identities) or len(set(identities)) != len(identities):
                        raise WorkflowDocumentStoreError("workflow_object_identity_invalid")
                    if objects is not None:
                        validate_revision_write(current_objects, next_objects, snapshot_id=snapshot_id)
                        con.execute("DELETE FROM workflow.document_objects WHERE snapshot_id=%s", (snapshot_id,))
                        for position, obj in enumerate(next_objects):
                            con.execute(
                                "INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,position) "
                                "VALUES(%s,%s,%s,%s::jsonb,%s)",
                                (snapshot_id, obj["object_id"], obj["object_version"], _json_text(obj), position),
                            )
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

    def _startup_local_mirror_is_authority(self, path: Path) -> bool:
        if path.name == "envelopes.json":
            return False
        return super()._startup_local_mirror_is_authority(path)

    def refresh_workflow_documents(self) -> None:
        try:
            envelopes = self.workflow_document_store.list_envelopes()
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        self._envelopes = {str(row["snapshot_id"]): row for row in envelopes}

    @diagnostic_phase("document_list")
    def list_envelopes(self) -> list[dict[str, Any]]:
        """Read the authoritative list instead of a process-local startup cache."""
        reads = self._source_selection_reads()
        if reads is not None:
            if reads["envelopes"] is None:
                try:
                    rows = self.workflow_document_store.list_envelopes()
                except WorkflowDocumentStoreError as exc:
                    raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
                reads["envelopes"] = {str(row["snapshot_id"]): row for row in rows}
            return [self._receipt(row) for row in reads["envelopes"].values()]
        self.refresh_workflow_documents()
        return [self._receipt(row) for row in self._envelopes.values()]

    def list_snapshot_ids(self) -> list[str]:
        """PR-a: the same authoritative read as list_envelopes, without per-row receipts."""
        reads = self._source_selection_reads()
        if reads is not None:
            if reads["envelopes"] is None:
                self.refresh_workflow_documents()
                reads["envelopes"] = self._envelopes
            return list(reads["envelopes"])
        self.refresh_workflow_documents()
        return list(self._envelopes)

    @diagnostic_phase("document_load")
    def _envelope(self, snapshot_id: str) -> dict[str, Any]:
        reads = self._source_selection_reads()
        if reads is not None and reads["envelopes"] is not None:
            if snapshot_id not in reads["envelopes"]:
                raise ConsoleError("unknown_snapshot")
            return reads["envelopes"][snapshot_id]
        try:
            envelope = self.workflow_document_store.get_envelope(snapshot_id)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        if envelope is None:
            raise ConsoleError("unknown_snapshot")
        self._envelopes[snapshot_id] = deepcopy(envelope)
        return deepcopy(envelope)

    def _load_objects(self, snapshot_id: str, *, remember: bool = True) -> list[dict[str, Any]]:
        reads = self._source_selection_reads() if not remember else None
        if reads is not None and snapshot_id in reads["objects"]:
            return reads["objects"][snapshot_id][0]
        try:
            rows = self.workflow_document_store.list_document_objects(snapshot_id)
            revision = self.workflow_document_store.revision_for_rows(rows)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        if remember:
            self._objects_expected_revs()[snapshot_id] = revision
        elif reads is not None:
            reads["objects"][snapshot_id] = (rows, revision)
        return rows

    @diagnostic_phase("objects_read")
    def snapshot_objects_and_revision(
        self,
        snapshot_id: str,
        include_blocked: bool = False,
    ) -> tuple[list[dict[str, Any]], str]:
        """Read authoritative PostgreSQL objects once and derive their revision."""
        self._envelope(snapshot_id)
        try:
            rows = self.workflow_document_store.list_document_objects(snapshot_id)
            revision = self.workflow_document_store.revision_for_rows(rows)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        if include_blocked:
            return deepcopy(rows), revision
        return deepcopy(current_revisions(rows, snapshot_id=snapshot_id)), revision

    def objects_revision(self, snapshot_id: str) -> str:
        reads = self._source_selection_reads()
        if reads is not None:
            self._load_objects(snapshot_id, remember=False)
            return reads["objects"][snapshot_id][1]
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
            for envelope in source.values():
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
    ) -> None:
        self._require_review_store_configured()
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
            current = deepcopy(self._envelopes)
            target_envelopes = current if envelopes is None else self._rebase_snapshot_map(current, envelopes, sid)
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
