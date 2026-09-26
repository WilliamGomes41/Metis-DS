"""Audit retention lifecycle for LIVE, ARCHIVED and successful PURGE.

Audit meaning remains orthogonal to retention location. Archive and restore
preserve the complete audit record byte-semantically; purge is allowed only from
ARCHIVED and removes both the Azure record and compact local reference.
"""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, ContextManager, Protocol

from src.audit_archive_store_v1 import AuditArchiveStore, AuditArchiveStoreError
from src.operations_console_v1 import ConsoleError


AUDIT_ID_RE = re.compile(r"^audit-[0-9a-f]{16}$")
AUDIT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ARCHIVE_REFERENCE_SCHEMA_VERSION = 1
ARCHIVE_REFERENCE_KIND = "archived_audit_ref"


class LiveAuditStore(Protocol):
    def get_audit(self, audit_id: str) -> dict[str, Any] | None: ...

    def get_archived_reference(self, audit_id: str) -> dict[str, Any] | None: ...

    def list_archived_references(self) -> list[dict[str, Any]]: ...

    def retention_lock(self, audit_id: str) -> ContextManager[Any]: ...

    def mark_purge(self, audit_id: str, reference: dict[str, Any], *, actor_id: str) -> dict[str, Any]: ...

    def replace_with_archived_ref(
        self,
        audit_id: str,
        reference: dict[str, Any],
    ) -> None: ...

    def replace_archived_ref_with_live(
        self,
        audit_id: str,
        reference: dict[str, Any],
        record: dict[str, Any],
    ) -> None: ...

    def remove_archived_ref(
        self,
        audit_id: str,
        reference: dict[str, Any],
    ) -> bool: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_audit_bytes(record: dict[str, Any]) -> bytes:
    return json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def valid_audit_record(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and AUDIT_ID_RE.fullmatch(str(record.get("audit_id") or "")) is not None
        and AUDIT_TYPE_RE.fullmatch(str(record.get("audit_type") or "")) is not None
        and bool(str(record.get("title") or "").strip())
        and bool(str(record.get("created_by") or "").strip())
        and bool(str(record.get("created_at") or "").strip())
        and isinstance(record.get("payload"), dict)
        and record.get("record_kind") != ARCHIVE_REFERENCE_KIND
    )


def is_archived_reference(row: Any) -> bool:
    return (
        isinstance(row, dict)
        and row.get("record_kind") == ARCHIVE_REFERENCE_KIND
        and row.get("schema_version") == ARCHIVE_REFERENCE_SCHEMA_VERSION
        and AUDIT_ID_RE.fullmatch(str(row.get("audit_id") or "")) is not None
        and AUDIT_TYPE_RE.fullmatch(str(row.get("audit_type") or "")) is not None
        and bool(str(row.get("title") or "").strip())
        and bool(str(row.get("created_at") or "").strip())
        and bool(str(row.get("archived_at") or "").strip())
        and bool(str(row.get("archived_by") or "").strip())
        and bool(str(row.get("archive_locator") or "").strip())
        and SHA256_RE.fullmatch(str(row.get("checksum_sha256") or "")) is not None
        and "payload" not in row
        and (not {"purge_requested_at", "purge_requested_by"}.intersection(row) or (
            bool(str(row.get("purge_requested_at") or "").strip())
            and bool(str(row.get("purge_requested_by") or "").strip())
        ))
    )


def is_purging(reference: dict[str, Any]) -> bool:
    return bool(reference.get("purge_requested_at"))


def validate_archived_record(reference: dict[str, Any], record: dict[str, Any]) -> None:
    if not is_archived_reference(reference) or not valid_audit_record(record):
        raise ConsoleError("audit_archive_record_invalid")
    if any(reference[key] != record[key] for key in ("audit_id", "audit_type", "title", "created_at")):
        raise ConsoleError("audit_archive_record_mismatch")
    if hashlib.sha256(canonical_audit_bytes(record)).hexdigest() != reference["checksum_sha256"]:
        raise ConsoleError("audit_archive_record_mismatch")


class AuditArchiveIndex:
    """Read the compact archived-reference projection from audit record paths."""

    def __init__(self, runtime: Path) -> None:
        self.root = Path(runtime) / "audits"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, audit_id: str) -> Path:
        safe_id = str(audit_id or "").strip()
        if AUDIT_ID_RE.fullmatch(safe_id) is None:
            raise ConsoleError("audit_archive_id_invalid")
        return self.root / f"{safe_id}.json"

    def get(self, audit_id: str) -> dict[str, Any] | None:
        path = self._path(audit_id)
        if not path.is_file():
            return None
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConsoleError("audit_archive_reference_corrupt") from exc
        if is_archived_reference(row):
            return row
        return None

    def list(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.root.glob("audit-*.json"):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ConsoleError("audit_archive_reference_corrupt") from exc
            if row.get("record_kind") == ARCHIVE_REFERENCE_KIND:
                if not is_archived_reference(row):
                    raise ConsoleError("audit_archive_reference_corrupt")
                rows.append(row)
        return sorted(
            rows,
            key=lambda row: str(row.get("archived_at") or ""),
            reverse=True,
        )


class AuditRetentionService:
    """Own fail-closed audit retention transitions."""

    def __init__(
        self,
        *,
        live_store: LiveAuditStore,
        archive_store: AuditArchiveStore,
        runtime: Path,
        write_lock: Callable[[], ContextManager[Any]] | None = None,
    ) -> None:
        self.live_store = live_store
        self.archive_store = archive_store
        self._write_lock = write_lock or nullcontext

    def list_archived(self) -> list[dict[str, Any]]:
        return self.live_store.list_archived_references()

    def get_archived_index(self, audit_id: str) -> dict[str, Any] | None:
        return self.live_store.get_archived_reference(audit_id)

    def load_archived(self, audit_id: str) -> dict[str, Any] | None:
        row = self.get_archived_index(audit_id)
        if row is None:
            return None
        if is_purging(row):
            raise ConsoleError("audit_purge_in_progress")
        try:
            data = self.archive_store.load_verified(
                str(row["archive_locator"]),
                expected_sha256=str(row["checksum_sha256"]),
            )
        except AuditArchiveStoreError as exc:
            raise ConsoleError("audit_archive_unavailable") from exc
        try:
            record = json.loads(data.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ConsoleError("audit_archive_record_invalid") from exc
        validate_archived_record(row, record)
        return record

    def restore(self, audit_id: str, *, actor_id: str) -> dict[str, Any]:
        safe_id = str(audit_id or "").strip()
        safe_actor = str(actor_id or "").strip()
        if AUDIT_ID_RE.fullmatch(safe_id) is None:
            raise ConsoleError("audit_archive_id_invalid")
        if not safe_actor:
            raise ConsoleError("audit_actor_required")

        with self._write_lock(), self.live_store.retention_lock(safe_id):
            active = self.live_store.get_audit(safe_id)
            reference = self.get_archived_index(safe_id)

            if active is not None:
                if reference is not None:
                    raise ConsoleError("audit_retention_state_ambiguous")
                try:
                    self.archive_store.delete_audit(safe_id)
                except AuditArchiveStoreError as exc:
                    raise ConsoleError("audit_restore_cleanup_pending") from exc
                return active

            if reference is None:
                raise ConsoleError("unknown_audit")

            record = self.load_archived(safe_id)
            if record is None:
                raise ConsoleError("audit_archive_record_missing")

            self.live_store.replace_archived_ref_with_live(
                safe_id,
                reference,
                record,
            )

            try:
                self.archive_store.delete_verified(reference["archive_locator"])
            except AuditArchiveStoreError as exc:
                # The verified LIVE record has committed. Do not reverse that
                # durable outcome because cleanup failed (or its ACK was lost).
                raise ConsoleError("audit_restore_cleanup_pending") from exc
            return record

    def purge(
        self,
        audit_id: str,
        *,
        actor_id: str,
        confirm_title: str,
    ) -> dict[str, Any]:
        safe_id = str(audit_id or "").strip()
        safe_actor = str(actor_id or "").strip()
        confirmation = str(confirm_title or "").strip()
        if AUDIT_ID_RE.fullmatch(safe_id) is None:
            raise ConsoleError("audit_archive_id_invalid")
        if not safe_actor:
            raise ConsoleError("audit_actor_required")

        with self._write_lock(), self.live_store.retention_lock(safe_id):
            active = self.live_store.get_audit(safe_id)
            reference = self.get_archived_index(safe_id)

            if active is not None:
                raise ConsoleError("audit_purge_requires_archived")

            if reference is None:
                # Duplicate execution after a completed purge is an idempotent
                # no-op. Do not blindly delete Azure by id without a local
                # archived reference proving that this command owns that blob.
                return {"audit_id": safe_id, "purged": True}

            if confirmation != str(reference.get("title") or ""):
                raise ConsoleError("audit_purge_confirmation_mismatch")

            reference = self.live_store.mark_purge(safe_id, reference, actor_id=safe_actor)

            try:
                self.archive_store.delete_verified(reference["archive_locator"])
            except AuditArchiveStoreError as exc:
                raise ConsoleError("audit_purge_archive_delete_failed") from exc

            try:
                self.live_store.remove_archived_ref(safe_id, reference)
            except ConsoleError:
                raise
            except Exception as exc:
                raise ConsoleError("audit_purge_local_delete_failed") from exc

            return {"audit_id": safe_id, "purged": True}

    def archive(self, audit_id: str, *, actor_id: str) -> dict[str, Any]:
        safe_id = str(audit_id or "").strip()
        safe_actor = str(actor_id or "").strip()
        if AUDIT_ID_RE.fullmatch(safe_id) is None:
            raise ConsoleError("audit_archive_id_invalid")
        if not safe_actor:
            raise ConsoleError("audit_actor_required")

        with self._write_lock(), self.live_store.retention_lock(safe_id):
            active = self.live_store.get_audit(safe_id)
            existing = self.get_archived_index(safe_id)

            if active is None:
                if existing is not None:
                    if is_purging(existing):
                        raise ConsoleError("audit_purge_in_progress")
                    return existing
                raise ConsoleError("unknown_audit")
            if existing is not None:
                raise ConsoleError("audit_retention_state_ambiguous")
            if not valid_audit_record(active):
                raise ConsoleError("audit_record_corrupt")

            data = canonical_audit_bytes(active)
            checksum = hashlib.sha256(data).hexdigest()
            try:
                locator = self.archive_store.store_verified(
                    audit_id=safe_id,
                    data=data,
                    sha256=checksum,
                )
                readback = self.archive_store.load_verified(
                    locator,
                    expected_sha256=checksum,
                )
            except AuditArchiveStoreError as exc:
                raise ConsoleError("audit_archive_store_failed") from exc
            if readback != data:
                raise ConsoleError("audit_archive_readback_mismatch")

            reference = {
                "record_kind": ARCHIVE_REFERENCE_KIND,
                "schema_version": ARCHIVE_REFERENCE_SCHEMA_VERSION,
                "audit_id": safe_id,
                "title": str(active["title"]),
                "audit_type": str(active["audit_type"]),
                "created_at": str(active["created_at"]),
                "archived_at": _now(),
                "archived_by": safe_actor,
                "archive_locator": locator,
                "checksum_sha256": checksum,
            }
            if not is_archived_reference(reference):
                raise ConsoleError("audit_archive_reference_invalid")

            try:
                self.live_store.replace_with_archived_ref(safe_id, reference)
            except Exception:
                # A failed response does not prove the commit failed. Resolve
                # authority while still holding the per-audit lock. If the DB
                # cannot answer, retain the Blob for a safe retry.
                try:
                    committed = self.get_archived_index(safe_id)
                    if committed == reference:
                        return committed
                    if committed is None and self.live_store.get_audit(safe_id) == active:
                        self.archive_store.delete_verified(locator)
                except Exception:
                    pass
                raise
            return reference
