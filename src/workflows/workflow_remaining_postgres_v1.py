"""PostgreSQL authority for remaining mutable Audit workspace state.

Audit records are active workflow state. Legacy encrypted Audit LLM payloads may
remain opaque in this store for rollback/recovery compatibility, but active LLM
provider configuration is deployment-owned and is never read from this module.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Mapping

from src.audit_retention_v1 import is_archived_reference, is_purging, validate_archived_record, _now
from src.operations_console_v1 import ConsoleError
from src.workflows.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore, _json_text


class WorkflowRemainingStoreError(RuntimeError):
    """Fail-closed shared workflow state error."""


@contextmanager
def audit_retention_lock(connect: Any, audit_id: str | None = None):
    """Order Blob effects across workers; a full backup excludes retention.

    Session locks cover the external Blob operation and several short database
    transactions. Closing this dedicated connection releases locks after a crash.
    The two integer key spaces are private to audit retention.
    """
    with connect() as con:
        con.autocommit = True
        if audit_id is None:
            con.execute("SELECT pg_advisory_lock(2110021, 0)")
        else:
            con.execute("SELECT pg_advisory_lock_shared(2110021, 0)")
            con.execute("SELECT pg_advisory_lock(2110022, hashtext(%s))", (audit_id,))
        yield


class PostgresWorkflowRemainingStore(PostgresWorkflowDocumentStore):
    def verify_remaining_schema(self) -> None:
        self.verify_schema()
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='workflow' AND table_name IN ('audit_records','audit_secrets')"
                ).fetchall()
                column = con.execute(
                    "SELECT 1 FROM information_schema.columns WHERE table_schema='workflow' "
                    "AND table_name='audit_records' AND column_name='retention_state'"
                ).fetchone()
        except Exception as exc:
            raise WorkflowRemainingStoreError("workflow_remaining_schema_check_failed") from exc
        present = {str(row["table_name"]) for row in rows}
        if present != {"audit_records", "audit_secrets"} or not column:
            raise WorkflowRemainingStoreError("workflow_remaining_schema_missing")

    @staticmethod
    def _payload(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return deepcopy(value)
        if isinstance(value, str):
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        raise WorkflowRemainingStoreError("workflow_remaining_payload_invalid")

    def list_audits(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT audit_id,audit_type,title,created_by,created_at,updated_at,payload "
                    "FROM workflow.audit_records WHERE retention_state='LIVE' ORDER BY created_at DESC,audit_id"
                ).fetchall()
            return [
                {
                    "audit_id": str(row["audit_id"]),
                    "audit_type": str(row["audit_type"]),
                    "title": str(row["title"]),
                    "created_by": str(row["created_by"]),
                    "created_at": row["created_at"].isoformat().replace("+00:00", "Z") if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                    "updated_at": row["updated_at"].isoformat().replace("+00:00", "Z") if hasattr(row["updated_at"], "isoformat") else str(row["updated_at"]),
                    "payload": self._payload(row["payload"]),
                }
                for row in rows
            ]
        except WorkflowRemainingStoreError:
            raise
        except Exception as exc:
            raise WorkflowRemainingStoreError("workflow_audits_read_failed") from exc

    def get_audit(self, audit_id: str) -> dict[str, Any] | None:
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT audit_id,audit_type,title,created_by,created_at,updated_at,payload "
                    "FROM workflow.audit_records WHERE audit_id=%s AND retention_state='LIVE'",
                    (audit_id,),
                ).fetchone()
            if row is None:
                return None
            return {
                "audit_id": str(row["audit_id"]),
                "audit_type": str(row["audit_type"]),
                "title": str(row["title"]),
                "created_by": str(row["created_by"]),
                "created_at": row["created_at"].isoformat().replace("+00:00", "Z") if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                "updated_at": row["updated_at"].isoformat().replace("+00:00", "Z") if hasattr(row["updated_at"], "isoformat") else str(row["updated_at"]),
                "payload": self._payload(row["payload"]),
            }
        except WorkflowRemainingStoreError:
            raise
        except Exception as exc:
            raise WorkflowRemainingStoreError("workflow_audit_read_failed") from exc

    def create_audit(self, record: Mapping[str, Any], *, archived_reference: dict[str, Any] | None = None) -> dict[str, Any]:
        # Explicit offline migration may insert an already verified archive in
        # one transaction. Startup never imports local references.
        state = "LIVE"
        payload = record["payload"]
        if archived_reference is not None:
            validate_archived_record(archived_reference, dict(record))
            state = "PURGING" if is_purging(archived_reference) else "ARCHIVED"
            payload = archived_reference
        try:
            with self._connect() as con:
                with con.transaction():
                    con.execute(
                        "INSERT INTO workflow.audit_records(audit_id,audit_type,title,created_by,created_at,updated_at,payload,retention_state) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                        (
                            record["audit_id"], record["audit_type"], record["title"], record["created_by"],
                            record["created_at"], record["updated_at"], _json_text(payload), state,
                        ),
                    )
            return deepcopy(dict(record))
        except Exception as exc:
            raise WorkflowRemainingStoreError("workflow_audit_write_failed") from exc

    def retention_lock(self, audit_id: str):
        return audit_retention_lock(self._connect, audit_id)

    @staticmethod
    def _reference(row: Mapping[str, Any]) -> dict[str, Any]:
        reference = row["payload"]
        if (not is_archived_reference(reference)
                or reference["audit_id"] != row["audit_id"]
                or is_purging(reference) != (row["retention_state"] == "PURGING")):
            raise ConsoleError("audit_archive_reference_corrupt")
        return deepcopy(reference)

    def list_archived_references(self) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT audit_id,retention_state,payload FROM workflow.audit_records "
                "WHERE retention_state <> 'LIVE' ORDER BY payload->>'archived_at' DESC,audit_id"
            ).fetchall()
        return [self._reference(row) for row in rows]

    def get_archived_reference(self, audit_id: str) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT audit_id,retention_state,payload FROM workflow.audit_records "
                "WHERE audit_id=%s AND retention_state <> 'LIVE'", (audit_id,)
            ).fetchone()
        return None if row is None else self._reference(row)

    def replace_with_archived_ref(self, audit_id: str, reference: dict[str, Any]) -> None:
        if is_purging(reference):
            raise ConsoleError("audit_purge_in_progress")
        with self._connect() as con, con.transaction():
            row = con.execute("SELECT * FROM workflow.audit_records WHERE audit_id=%s FOR UPDATE", (audit_id,)).fetchone()
            if row is None or row["retention_state"] != "LIVE":
                raise ConsoleError("audit_not_live")
            record = {key: value for key, value in row.items() if key != "retention_state"}
            for key in ("created_at", "updated_at"):
                record[key] = record[key].isoformat().replace("+00:00", "Z")
            validate_archived_record(reference, record)
            con.execute("UPDATE workflow.audit_records SET retention_state='ARCHIVED',payload=%s::jsonb WHERE audit_id=%s",
                        (_json_text(reference), audit_id))

    def replace_archived_ref_with_live(self, audit_id: str, reference: dict[str, Any], record: dict[str, Any]) -> None:
        validate_archived_record(reference, record)
        if audit_id != record["audit_id"] or is_purging(reference):
            raise ConsoleError("audit_archive_reference_changed")
        with self._connect() as con, con.transaction():
            result = con.execute(
                "UPDATE workflow.audit_records SET retention_state='LIVE',payload=%s::jsonb "
                "WHERE audit_id=%s AND retention_state='ARCHIVED' AND payload=%s::jsonb",
                (_json_text(record["payload"]), audit_id, _json_text(reference)),
            )
            if result.rowcount != 1:
                raise ConsoleError("audit_archive_reference_changed")

    def mark_purge(self, audit_id: str, reference: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
        if not is_archived_reference(reference) or not actor_id or reference["audit_id"] != audit_id:
            raise ConsoleError("audit_archive_reference_invalid")
        pending = reference if is_purging(reference) else {
            **reference, "purge_requested_at": _now(), "purge_requested_by": actor_id,
        }
        with self._connect() as con, con.transaction():
            result = con.execute(
                "UPDATE workflow.audit_records SET retention_state='PURGING',payload=%s::jsonb "
                "WHERE audit_id=%s AND retention_state IN ('ARCHIVED','PURGING') AND payload=%s::jsonb",
                (_json_text(pending), audit_id, _json_text(reference)),
            )
            if result.rowcount != 1:
                raise ConsoleError("audit_archive_reference_changed")
        return pending

    def remove_archived_ref(self, audit_id: str, reference: dict[str, Any]) -> bool:
        if not is_archived_reference(reference) or not is_purging(reference):
            raise ConsoleError("audit_purge_intent_required")
        with self._connect() as con, con.transaction():
            result = con.execute(
                "DELETE FROM workflow.audit_records WHERE audit_id=%s AND retention_state='PURGING' AND payload=%s::jsonb",
                (audit_id, _json_text(reference)),
            )
            if result.rowcount != 1:
                raise ConsoleError("audit_archive_reference_changed")
        return True

    def get_secret_payload(self, name: str) -> dict[str, Any] | None:
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT secret_payload FROM workflow.audit_secrets WHERE secret_name=%s",
                    (name,),
                ).fetchone()
            return None if row is None else self._payload(row["secret_payload"])
        except WorkflowRemainingStoreError:
            raise
        except Exception as exc:
            raise WorkflowRemainingStoreError("workflow_audit_secret_read_failed") from exc

    def set_secret_payload(self, name: str, payload: Mapping[str, Any]) -> None:
        try:
            with self._connect() as con:
                with con.transaction():
                    con.execute(
                        "INSERT INTO workflow.audit_secrets(secret_name,secret_payload,updated_at) "
                        "VALUES(%s,%s::jsonb,CURRENT_TIMESTAMP) "
                        "ON CONFLICT(secret_name) DO UPDATE SET secret_payload=EXCLUDED.secret_payload,updated_at=CURRENT_TIMESTAMP",
                        (name, _json_text(dict(payload))),
                    )
        except Exception as exc:
            raise WorkflowRemainingStoreError("workflow_audit_secret_write_failed") from exc

    def delete_secret(self, name: str) -> None:
        try:
            with self._connect() as con:
                with con.transaction():
                    con.execute("DELETE FROM workflow.audit_secrets WHERE secret_name=%s", (name,))
        except Exception as exc:
            raise WorkflowRemainingStoreError("workflow_audit_secret_write_failed") from exc
