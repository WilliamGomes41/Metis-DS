"""PostgreSQL authority for mutable console documents and work objects.

Complete envelopes and object snapshots are authoritative in PostgreSQL. Local
files are compatibility mirrors. Two processes on one instance share the store
lock and use optimistic object revisions; multiple App Service instances remain
outside the supported topology.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager, suppress
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator, Mapping

from src.operations_console_v1 import (
    ConsoleError,
    SNAPSHOT_OBJECT_WRITE_CONFLICT,
    _atomic_replace_bytes,
    _atomic_write,
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
from src.workflows.workflow_transaction_v1 import bind_workflow_stores, workflow_transaction


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
        envelope = self._payload(row["envelope_payload"])
        snapshot_id = str(row["snapshot_id"])
        if str(envelope.get("snapshot_id") or "") != snapshot_id:
            raise WorkflowDocumentStoreError("workflow_document_envelope_identity_mismatch")
        reviewers = self._reviewers(con, snapshot_id)
        payload_reviewers = sorted(str(x) for x in envelope.get("named_reviewers") or [])
        if reviewers != payload_reviewers:
            raise WorkflowDocumentStoreError("workflow_document_reviewers_authority_mismatch")
        return envelope

    def list_envelopes(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT snapshot_id,envelope_payload FROM workflow.documents ORDER BY acquired_at,snapshot_id"
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
                    "SELECT snapshot_id,envelope_payload FROM workflow.documents WHERE snapshot_id=%s",
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
        values = self._document_values(envelope)
        snapshot_id = str(envelope["snapshot_id"])
        existing = con.execute(
            "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
            (snapshot_id,),
        ).fetchone()
        if existing is None:
            con.execute(
                "INSERT INTO workflow.documents("
                "snapshot_id,source_id,document_id,title,family,class,state,publication_eligibility,content_kind,"
                "ingest_kind,source_version,source_date,source_sha256,source_locator,immutable_storage_locator,"
                "live_url,uploader_account_id,replaces_snapshot_id,object_diff,clinical_rereview_required,"
                "acquired_at,console_version,envelope_payload) VALUES("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb)",
                (*values, _json_text(dict(envelope))),
            )
        else:
            con.execute(
                "UPDATE workflow.documents SET "
                "source_id=%s,document_id=%s,title=%s,family=%s,class=%s,state=%s,publication_eligibility=%s,"
                "content_kind=%s,ingest_kind=%s,source_version=%s,source_date=%s,source_sha256=%s,source_locator=%s,"
                "immutable_storage_locator=%s,live_url=%s,uploader_account_id=%s,replaces_snapshot_id=%s,"
                "object_diff=%s::jsonb,clinical_rereview_required=%s,acquired_at=%s,console_version=%s,"
                "envelope_payload=%s::jsonb,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE snapshot_id=%s",
                (
                    values[1], values[2], values[3], values[4], values[5], values[6], values[7], values[8],
                    values[9], values[10], values[11], values[12], values[13], values[14], values[15], values[16],
                    values[17], values[18], values[19], values[20], values[21], _json_text(dict(envelope)), snapshot_id,
                ),
            )
        con.execute("DELETE FROM workflow.document_reviewers WHERE snapshot_id=%s", (snapshot_id,))
        for reviewer in sorted(set(str(x) for x in envelope.get("named_reviewers") or [])):
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
        super().__init__(*args, **kwargs)
        self.workflow_document_store = workflow_document_store
        self.workflow_document_store.verify_cutover_schema()
        self.refresh_workflow_documents()
        self._mirror_envelopes()

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

    def list_envelopes(self) -> list[dict[str, Any]]:
        """Read the authoritative list instead of a process-local startup cache."""
        self.refresh_workflow_documents()
        return [self._receipt(row) for row in self._envelopes.values()]

    def _envelope(self, snapshot_id: str) -> dict[str, Any]:
        try:
            envelope = self.workflow_document_store.get_envelope(snapshot_id)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        if envelope is None:
            raise ConsoleError("unknown_snapshot")
        self._envelopes[snapshot_id] = deepcopy(envelope)
        return deepcopy(envelope)

    def _load_objects(self, snapshot_id: str, *, remember: bool = True) -> list[dict[str, Any]]:
        try:
            rows = self.workflow_document_store.list_document_objects(snapshot_id)
            revision = self.workflow_document_store.revision_for_rows(rows)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc
        if remember:
            self._objects_expected_revs()[snapshot_id] = revision
        return rows

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
        current: dict[str, dict[str, Any]] = {}
        for row in rows:
            current[row["object_id"]] = row
        return deepcopy(list(current.values())), revision

    def objects_revision(self, snapshot_id: str) -> str:
        try:
            return self.workflow_document_store.objects_revision(snapshot_id)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_unavailable", str(exc)) from exc

    def refresh_objects_expected_revision(self, snapshot_id: str, revision: str | None = None) -> str:
        current = revision or self.objects_revision(snapshot_id)
        self._objects_expected_revs()[snapshot_id] = current
        return current

    def _mirror_objects(self, snapshot_id: str, rows: list[dict[str, Any]]) -> None:
        with suppress(OSError):
            _atomic_replace_bytes(self._objects_path(snapshot_id), _objects_jsonl_bytes(rows))

    def _mirror_envelopes(self) -> None:
        with suppress(OSError):
            _atomic_write(self._envelopes_path, self._envelopes)

    def _save_objects(
        self,
        snapshot_id: str,
        rows: list[dict[str, Any]],
        *,
        expected_revision: str | None = None,
    ) -> None:
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
        self._mirror_objects(snapshot_id, rows)

    def _delete_unpublished_snapshot_authority(self, snapshot_id: str) -> None:
        try:
            self.workflow_document_store.delete_document(snapshot_id)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_delete_failed", str(exc)) from exc
        self._envelopes.pop(snapshot_id, None)
        self._objects_expected_revs().pop(snapshot_id, None)
        self._mirror_envelopes()
        with suppress(OSError):
            self._objects_path(snapshot_id).unlink()

    def _delete_unpublished_snapshot_locked(
        self,
        *,
        actor_id: str,
        token: str,
        account: dict[str, Any],
        confirm_title: str,
    ) -> dict[str, Any]:
        envelope = deepcopy(self._envelope(token))
        objects_path = self._objects_path(token)
        freeze_raw = str(envelope.get("binary_path") or "")
        freeze_path = Path(freeze_raw) if freeze_raw else None
        prior_objects = objects_path.read_bytes() if objects_path.exists() else None
        prior_envelopes_file = (
            self._envelopes_path.read_bytes() if self._envelopes_path.exists() else None
        )
        prior_bindings_file = (
            self._bindings_path.read_bytes() if self._bindings_path.exists() else None
        )
        prior_ledger_file = (
            self._ledger_path.read_bytes() if self._ledger_path.exists() else None
        )
        prior_freeze = (
            freeze_path.read_bytes()
            if freeze_path is not None and freeze_path.is_file()
            else None
        )
        prior_envelopes = deepcopy(self._envelopes)
        prior_bindings = deepcopy(self._bindings)
        prior_bindings_baseline = deepcopy(
            getattr(self, "_bindings_baseline", None)
        )
        expected_revs = self._objects_expected_revs()
        prior_expected_revision = expected_revs.get(token)

        participants = [self.workflow_document_store]
        review_store = getattr(self, "workflow_review_store", None)
        if review_store is not None:
            participants.append(review_store)
        bind_workflow_stores(*participants)

        try:
            with workflow_transaction(self.workflow_document_store):
                return super()._delete_unpublished_snapshot_locked(
                    actor_id=actor_id,
                    token=token,
                    account=account,
                    confirm_title=confirm_title,
                )
        except Exception:
            self._envelopes = prior_envelopes
            self._bindings = prior_bindings
            if prior_bindings_baseline is not None:
                self._bindings_baseline = prior_bindings_baseline
            if prior_expected_revision is None:
                expected_revs.pop(token, None)
            else:
                expected_revs[token] = prior_expected_revision

            restore_files = (
                (objects_path, prior_objects),
                (self._envelopes_path, prior_envelopes_file),
                (self._bindings_path, prior_bindings_file),
                (self._ledger_path, prior_ledger_file),
            )
            for path, prior in restore_files:
                if prior is None:
                    with suppress(OSError):
                        path.unlink()
                else:
                    _atomic_replace_bytes(path, prior)
            if freeze_path is not None:
                if prior_freeze is None:
                    with suppress(OSError):
                        freeze_path.unlink()
                else:
                    _atomic_replace_bytes(freeze_path, prior_freeze)
            raise

    def _save_envelopes(self) -> None:
        payload = getattr(self, "_prepared_envelopes", None)
        source = self._envelopes if payload is None else payload
        try:
            for envelope in source.values():
                self.workflow_document_store.write_bundle(envelope=envelope)
        except WorkflowDocumentStoreError as exc:
            raise ConsoleError("workflow_document_write_failed", str(exc)) from exc
        self._envelopes = deepcopy(source)
        self._mirror_envelopes()

    def _reload_store_locked(self) -> None:
        self.refresh_workflow_documents()
        loaded = self._load_map(self._bindings_path)
        self._bindings = {key: list(value) for key, value in loaded.items()}

    def _apply_local_release_copy(self, release: dict[str, Any], projection: list[dict[str, Any]]) -> None:
        """Maintain local copies, then persist the envelope in PostgreSQL authority."""
        super()._apply_local_release_copy(release, projection)
        snapshot_id = str(release["snapshot_id"])
        current = deepcopy(self._envelopes[snapshot_id])
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
        if envelopes is None and objects is None:
            return super()._commit_prepared_store(
                bindings=bindings,
                ledger_fn=ledger_fn,
                snapshot_id=snapshot_id,
            )
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
            prior_bindings = deepcopy(self._bindings)
            prior_ledger = self._ledger_path.stat().st_size if self._ledger_path.exists() else 0
            try:
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
                except WorkflowDocumentStoreError as exc:
                    if str(exc) == SNAPSHOT_OBJECT_WRITE_CONFLICT:
                        raise ConsoleError(
                            SNAPSHOT_OBJECT_WRITE_CONFLICT,
                            current_revision=self.objects_revision(sid),
                        ) from exc
                    raise ConsoleError("workflow_document_write_failed", str(exc)) from exc
            except Exception:
                if bindings is not None:
                    _atomic_write(self._bindings_path, prior_bindings)
                if self._ledger_path.exists() and self._ledger_path.stat().st_size > prior_ledger:
                    with self._ledger_path.open("r+b") as handle:
                        handle.truncate(prior_ledger)
                raise
            self._bindings = target_bindings
            self._envelopes = target_envelopes
            if objects is not None:
                self._objects_expected_revs()[sid] = revision
                self._mirror_objects(sid, objects[1])
            self._mirror_envelopes()

    @contextmanager
    def _atomic_snapshot_mutation(self, snapshot_id: str) -> Iterator[None]:
        """Preserve current rollback behavior while documents/objects are PostgreSQL-backed."""
        with self._store_write_lock():
            self._reload_store_locked()
            before_envelope = deepcopy(self._envelope(snapshot_id))
            before_objects = deepcopy(self._load_objects(snapshot_id, remember=False))
            before_bindings = deepcopy(self._bindings)
            before_ledger = self._ledger_path.stat().st_size if self._ledger_path.exists() else 0
            try:
                yield
            except Exception:
                with suppress(Exception):
                    self.workflow_document_store.write_bundle(
                        envelope=before_envelope,
                        objects=before_objects,
                    )
                self._bindings = before_bindings
                _atomic_write(self._bindings_path, before_bindings)
                if self._ledger_path.exists() and self._ledger_path.stat().st_size > before_ledger:
                    with self._ledger_path.open("r+b") as handle:
                        handle.truncate(before_ledger)
                self.refresh_workflow_documents()
                self.refresh_objects_expected_revision(snapshot_id)
                raise


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