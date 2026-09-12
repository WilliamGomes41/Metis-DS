"""PostgreSQL authority for remaining mutable Audit workspace state.

Audit records and the encrypted Audit LLM secret move off local runtime files.
The encrypted secret payload stays opaque; this module never decrypts it.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping

from src.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore, _json_text


class WorkflowRemainingStoreError(RuntimeError):
    """Fail-closed shared workflow state error."""


class PostgresWorkflowRemainingStore(PostgresWorkflowDocumentStore):
    def verify_remaining_schema(self) -> None:
        self.verify_schema()
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='workflow' AND table_name IN ('audit_records','audit_secrets')"
                ).fetchall()
        except Exception as exc:
            raise WorkflowRemainingStoreError("workflow_remaining_schema_check_failed") from exc
        present = {str(row["table_name"]) for row in rows}
        if present != {"audit_records", "audit_secrets"}:
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
                    "FROM workflow.audit_records ORDER BY created_at DESC,audit_id"
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
                    "FROM workflow.audit_records WHERE audit_id=%s",
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

    def create_audit(self, record: Mapping[str, Any]) -> dict[str, Any]:
        try:
            with self._connect() as con:
                with con.transaction():
                    con.execute(
                        "INSERT INTO workflow.audit_records(audit_id,audit_type,title,created_by,created_at,updated_at,payload) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)",
                        (
                            record["audit_id"], record["audit_type"], record["title"], record["created_by"],
                            record["created_at"], record["updated_at"], _json_text(record["payload"]),
                        ),
                    )
            return deepcopy(dict(record))
        except Exception as exc:
            raise WorkflowRemainingStoreError("workflow_audit_write_failed") from exc

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
