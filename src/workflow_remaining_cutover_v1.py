"""Final opt-in workflow authority boundary before multi-instance testing.

PostgreSQL owns Audit records, encrypted Audit secret payloads and class-change
history embedded in document envelopes. Local release manifests, projections,
source freezes and JSON mirrors remain rebuildable compatibility/derived copies.
"""
from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Mapping

from cryptography.fernet import Fernet, InvalidToken

from src.audit_room_v1 import AUDIT_ID_RE, AUDIT_TYPE_RE
from src.operations_console_v1 import ConsoleError
from src.review_ledger import read_events
from src.workflow_remaining_postgres_v1 import (
    PostgresWorkflowRemainingStore,
    WorkflowRemainingStoreError,
)
from src.workflow_review_cutover_v1 import (
    PostgresReviewWorkflowAzureAuthoritativePublicationConsole,
    PostgresReviewWorkflowDurablePublicationConsole,
)

AUDIT_SECRET_MASTER_KEY_ENV = "METIS_AUDIT_SECRET_KEY"
AUDIT_LLM_SECRET_NAME = "llm_api_key"


class PostgresAuditRegistry:
    """AuditRegistry-compatible facade over the shared workflow store."""

    def __init__(self, store: PostgresWorkflowRemainingStore) -> None:
        self.store = store

    @staticmethod
    def _valid_record(row: Any) -> bool:
        return (
            isinstance(row, dict)
            and AUDIT_ID_RE.fullmatch(str(row.get("audit_id") or "")) is not None
            and AUDIT_TYPE_RE.fullmatch(str(row.get("audit_type") or "")) is not None
            and bool(str(row.get("title") or "").strip())
            and bool(str(row.get("created_by") or "").strip())
            and isinstance(row.get("payload"), dict)
        )

    def list_audits(self) -> list[dict[str, Any]]:
        rows = self.store.list_audits()
        if any(not self._valid_record(row) for row in rows):
            raise ConsoleError("audit_record_corrupt")
        return rows

    def get_audit(self, audit_id: str) -> dict[str, Any] | None:
        if not AUDIT_ID_RE.fullmatch(str(audit_id or "")):
            return None
        row = self.store.get_audit(audit_id)
        if row is not None and not self._valid_record(row):
            raise ConsoleError("audit_record_corrupt")
        return row

    def create(
        self,
        *,
        audit_type: str,
        title: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        import uuid
        from datetime import datetime, timezone

        safe_type = str(audit_type or "").strip()
        safe_title = " ".join(str(title or "").split())
        safe_actor = str(actor_id or "").strip()
        if not AUDIT_TYPE_RE.fullmatch(safe_type):
            raise ConsoleError("unknown_audit_type")
        if not safe_title:
            raise ConsoleError("audit_title_required")
        if not safe_actor:
            raise ConsoleError("audit_actor_required")
        if not isinstance(payload, dict):
            raise ConsoleError("audit_payload_required")
        for _attempt in range(3):
            audit_id = f"audit-{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            record = {
                "audit_id": audit_id,
                "audit_type": safe_type,
                "title": safe_title,
                "created_by": safe_actor,
                "created_at": now,
                "updated_at": now,
                "payload": deepcopy(payload),
            }
            try:
                return self.store.create_audit(record)
            except WorkflowRemainingStoreError as exc:
                if "workflow_audit_write_failed" not in str(exc):
                    raise ConsoleError("audit_store_unavailable", str(exc)) from exc
        raise RuntimeError("audit_id_collision")


class PostgresAuditLLMSecretStore:
    """Audit secret facade; PostgreSQL stores only the already-encrypted payload."""

    def __init__(self, store: PostgresWorkflowRemainingStore, *, environ: Mapping[str, str] | None = None) -> None:
        self.store = store
        self.environ = environ if environ is not None else os.environ

    def _fernet(self) -> Fernet:
        raw = str(self.environ.get(AUDIT_SECRET_MASTER_KEY_ENV, "") or "").strip()
        if not raw:
            raise ConsoleError("audit_secret_store_unavailable")
        try:
            return Fernet(raw.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ConsoleError("audit_secret_store_unavailable") from exc

    def status(self) -> dict[str, bool]:
        try:
            self._fernet()
            configured = self.store.get_secret_payload(AUDIT_LLM_SECRET_NAME) is not None
        except (ConsoleError, WorkflowRemainingStoreError):
            return {"available": False, "configured": False}
        return {"available": True, "configured": configured}

    def set_api_key(self, value: str) -> None:
        api_key = str(value or "").strip()
        if not api_key:
            raise ConsoleError("audit_llm_api_key_required")
        if len(api_key) > 4096:
            raise ConsoleError("audit_llm_api_key_too_long")
        payload = {
            "schema_version": 1,
            "ciphertext": self._fernet().encrypt(api_key.encode("utf-8")).decode("ascii"),
        }
        try:
            self.store.set_secret_payload(AUDIT_LLM_SECRET_NAME, payload)
        except WorkflowRemainingStoreError as exc:
            raise ConsoleError("audit_secret_store_unavailable", str(exc)) from exc

    def clear_api_key(self) -> None:
        self._fernet()
        try:
            self.store.delete_secret(AUDIT_LLM_SECRET_NAME)
        except WorkflowRemainingStoreError as exc:
            raise ConsoleError("audit_secret_store_unavailable", str(exc)) from exc

    def read_api_key(self) -> str:
        fernet = self._fernet()
        try:
            payload = self.store.get_secret_payload(AUDIT_LLM_SECRET_NAME)
            if payload is None:
                raise ConsoleError("audit_llm_api_key_missing")
            plaintext = fernet.decrypt(str(payload["ciphertext"]).encode("ascii"))
            return plaintext.decode("utf-8")
        except ConsoleError:
            raise
        except (WorkflowRemainingStoreError, KeyError, TypeError, ValueError, UnicodeError, InvalidToken) as exc:
            raise ConsoleError("audit_llm_secret_corrupt") from exc


def bind_remaining_route_backends(store: PostgresWorkflowRemainingStore) -> None:
    """Keep existing route installers; replace only their persistence constructors."""
    import src.audit_llm_settings_v1 as llm_settings
    import src.audit_room_v1 as audit_room

    audit_room.AuditRegistry = lambda _runtime: PostgresAuditRegistry(store)  # type: ignore[assignment]
    llm_settings.AuditLLMSecretStore = lambda _runtime: PostgresAuditLLMSecretStore(store)  # type: ignore[assignment]


class _PostgresRemainingWorkflowMixin:
    workflow_remaining_store: PostgresWorkflowRemainingStore

    def __init__(self, *args: Any, workflow_remaining_store: PostgresWorkflowRemainingStore, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.workflow_remaining_store = workflow_remaining_store
        self.workflow_remaining_store.verify_remaining_schema()

    def _archive_prior_objects(
        self,
        *,
        snapshot_id: str,
        rows: list[dict[str, Any]],
        from_class: str,
        to_class: str,
    ) -> dict[str, Any]:
        from src.operations_console_v1 import utc_now

        return {
            "reason": "document_class_changed",
            "from_class": from_class,
            "to_class": to_class,
            "changed_at": utc_now(),
            "object_count": len(rows),
            "object_ids": [row.get("object_id") for row in rows],
            "history_file": "",
            "objects": deepcopy(rows),
        }

    def prior_object_audit_history(self, snapshot_id: str) -> list[dict[str, Any]]:
        envelope = self._envelope(snapshot_id)
        out: list[dict[str, Any]] = []
        for record in envelope.get("prior_processing_history") or []:
            item = deepcopy(record)
            objects = item.get("objects")
            if not isinstance(objects, list):
                raise ConsoleError("workflow_class_history_cutover_not_prepared")
            item["objects"] = deepcopy(objects)
            out.append(item)
        return out

    def _local_ledger_has_release(self, release_id: str) -> bool:
        for event in read_events(self._ledger_path):
            if event.get("event_type") == "release_published" and str(
                (event.get("details") or {}).get("release_id") or ""
            ) == release_id:
                return True
        return False

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


class PostgresCompleteWorkflowDurablePublicationConsole(
    _PostgresRemainingWorkflowMixin,
    PostgresReviewWorkflowDurablePublicationConsole,
):
    pass


class PostgresCompleteWorkflowAzureAuthoritativePublicationConsole(
    _PostgresRemainingWorkflowMixin,
    PostgresReviewWorkflowAzureAuthoritativePublicationConsole,
):
    pass
