"""Audit retention lifecycle for LIVE -> ARCHIVED.

This module separates audit meaning from retention location. It moves complete
audit records to a verified archive store and keeps only compact local index
metadata. Restore and user-facing purge are intentionally out of scope for VSA
A1.
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
from src.operations_console_v1 import ConsoleError, _atomic_write


AUDIT_ID_RE = re.compile(r"^audit-[0-9a-f]{16}$")
AUDIT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ARCHIVE_INDEX_SCHEMA_VERSION = 1


class LiveAuditStore(Protocol):
    def get_audit(self, audit_id: str) -> dict[str, Any] | None: ...

    def remove_audit(self, audit_id: str) -> bool: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_audit_bytes(record: dict[str, Any]) -> bytes:
    return json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _valid_audit_record(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and AUDIT_ID_RE.fullmatch(str(record.get("audit_id") or "")) is not None
        and AUDIT_TYPE_RE.fullmatch(str(record.get("audit_type") or "")) is not None
        and bool(str(record.get("title") or "").strip())
        and bool(str(record.get("created_by") or "").strip())
        and bool(str(record.get("created_at") or "").strip())
        and isinstance(record.get("payload"), dict)
    )


class AuditArchiveIndex:
    """Small local projection for locating archived audits."""

    def __init__(self, runtime: Path) -> None:
        self.root = Path(runtime) / "audits" / "archive-index"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _valid(row: Any) -> bool:
        return (
            isinstance(row, dict)
            and row.get("schema_version") == ARCHIVE_INDEX_SCHEMA_VERSION
            and AUDIT_ID_RE.fullmatch(str(row.get("audit_id") or "")) is not None
            and AUDIT_TYPE_RE.fullmatch(str(row.get("audit_type") or "")) is not None
            and bool(str(row.get("title") or "").strip())
            and bool(str(row.get("created_at") or "").strip())
            and bool(str(row.get("archived_at") or "").strip())
            and bool(str(row.get("archived_by") or "").strip())
            and bool(str(row.get("archive_locator") or "").strip())
            and SHA256_RE.fullmatch(str(row.get("checksum_sha256") or "")) is not None
            and "payload" not in row
        )

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
            raise ConsoleError("audit_archive_index_corrupt") from exc
        if not self._valid(row):
            raise ConsoleError("audit_archive_index_corrupt")
        return row

    def list(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.root.glob("audit-*.json"):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ConsoleError("audit_archive_index_corrupt") from exc
            if not self._valid(row):
                raise ConsoleError("audit_archive_index_corrupt")
            rows.append(row)
        return sorted(
            rows,
            key=lambda row: str(row.get("archived_at") or ""),
            reverse=True,
        )

    def put(self, row: dict[str, Any]) -> None:
        if not self._valid(row):
            raise ConsoleError("audit_archive_index_invalid")
        _atomic_write(self._path(str(row["audit_id"])), row)


class AuditRetentionService:
    """Own the fail-closed LIVE -> ARCHIVED transition."""

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
        self.index = AuditArchiveIndex(runtime)
        self._write_lock = write_lock or nullcontext

    def list_archived(self) -> list[dict[str, Any]]:
        return self.index.list()

    def get_archived_index(self, audit_id: str) -> dict[str, Any] | None:
        return self.index.get(audit_id)

    def load_archived(self, audit_id: str) -> dict[str, Any] | None:
        row = self.index.get(audit_id)
        if row is None:
            return None
        try:
            data = self.archive_store.load_verified(
                str(row["archive_locator"]),
                expected_sha256=str(row["checksum_sha256"]),
            )
        except AuditArchiveStoreError as exc:
            raise ConsoleError("audit_archive_unavailable", str(exc)) from exc
        try:
            record = json.loads(data.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ConsoleError("audit_archive_record_invalid") from exc
        if not _valid_audit_record(record):
            raise ConsoleError("audit_archive_record_invalid")
        if str(record["audit_id"]) != str(row["audit_id"]):
            raise ConsoleError("audit_archive_record_mismatch")
        return record

    def archive(self, audit_id: str, *, actor_id: str) -> dict[str, Any]:
        safe_id = str(audit_id or "").strip()
        safe_actor = str(actor_id or "").strip()
        if AUDIT_ID_RE.fullmatch(safe_id) is None:
            raise ConsoleError("audit_archive_id_invalid")
        if not safe_actor:
            raise ConsoleError("audit_actor_required")

        with self._write_lock():
            active = self.live_store.get_audit(safe_id)
            existing = self.index.get(safe_id)

            if active is None:
                if existing is not None:
                    return existing
                raise ConsoleError("unknown_audit")

            if not _valid_audit_record(active):
                raise ConsoleError("audit_record_corrupt")

            # Recovery path for a previously completed Azure+index write where
            # local LIVE cleanup did not finish.
            if existing is not None:
                archived = self.load_archived(safe_id)
                if archived != active:
                    raise ConsoleError("audit_archive_conflict")
                if not self.live_store.remove_audit(safe_id):
                    raise ConsoleError("audit_archive_live_delete_failed")
                return existing

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
                raise ConsoleError("audit_archive_store_failed", str(exc)) from exc
            if readback != data:
                raise ConsoleError("audit_archive_readback_mismatch")

            row = {
                "schema_version": ARCHIVE_INDEX_SCHEMA_VERSION,
                "audit_id": safe_id,
                "title": str(active["title"]),
                "audit_type": str(active["audit_type"]),
                "created_at": str(active["created_at"]),
                "archived_at": _now(),
                "archived_by": safe_actor,
                "archive_locator": locator,
                "checksum_sha256": checksum,
            }

            try:
                self.index.put(row)
            except Exception:
                try:
                    self.archive_store.delete_verified(locator)
                except AuditArchiveStoreError:
                    pass
                raise

            if not self.live_store.remove_audit(safe_id):
                # Keep Azure + index durable. A retry takes the recovery path
                # above and completes the local cleanup without data loss.
                raise ConsoleError("audit_archive_live_delete_failed")
            return row
