"""PostgreSQL authority for review events and publish authorizations.

The existing review functions keep their public API. Review events preserve the
exact hash-chained payload; relational columns are indexes only. Publish
authorizations preserve the existing per-snapshot tuple records.
"""
from __future__ import annotations

import json
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from src.integrity_kernel import stable_hash
from src.review_ledger import verify_ledger
from src.workflow_documents_postgres_v1 import (
    PostgresWorkflowDocumentStore,
    WorkflowDocumentStoreError,
    _json_text,
)


class WorkflowReviewStoreError(RuntimeError):
    """Fail-closed shared review-state error."""


class PostgresWorkflowReviewStore(PostgresWorkflowDocumentStore):
    """Shared authority for hash-chained review evidence and authorizations."""

    REVIEW_LEDGER_LOCK_KEY = 714812479584013
    AUTHORIZATION_LOCK_KEY = 714812479584014

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._buffer: ContextVar[list[dict[str, Any]] | None] = ContextVar(
            "workflow_review_event_buffer", default=None
        )
        self._mirror_path: Path | None = None

    def bind_ledger_mirror(self, path: Path) -> None:
        self._mirror_path = Path(path)

    def verify_review_schema(self) -> None:
        self.verify_schema()
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema='workflow' AND ("
                    "(table_name='review_events' AND column_name IN ('actor_text','event_payload')) OR "
                    "(table_name='publish_authorizations' AND column_name='position'))"
                ).fetchall()
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_review_schema_check_failed") from exc
        present = {(str(row["table_name"]), str(row["column_name"])) for row in rows}
        required = {
            ("review_events", "actor_text"),
            ("review_events", "event_payload"),
            ("publish_authorizations", "position"),
        }
        if present != required:
            raise WorkflowReviewStoreError("workflow_review_schema_missing")

    @staticmethod
    def _event_payload(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return deepcopy(value)
        if isinstance(value, str):
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        raise WorkflowReviewStoreError("workflow_review_event_payload_invalid")

    def read_events(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT event_payload FROM workflow.review_events ORDER BY event_id"
                ).fetchall()
            if any(row["event_payload"] is None for row in rows):
                raise WorkflowReviewStoreError("workflow_review_cutover_not_prepared")
            return [self._event_payload(row["event_payload"]) for row in rows]
        except WorkflowReviewStoreError:
            raise
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_review_events_read_failed") from exc

    @staticmethod
    def _new_event(
        *,
        event_type: str,
        object_id: str,
        object_version: str,
        actor: str,
        details: dict[str, Any],
        previous_event_hash: str | None,
    ) -> dict[str, Any]:
        body = {
            "event_type": event_type,
            "object_id": object_id,
            "object_version": object_version,
            "actor": actor,
            "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "details": deepcopy(details),
            "previous_event_hash": previous_event_hash,
        }
        body["event_hash"] = stable_hash(body)
        return body

    @classmethod
    def _lock_review_ledger(cls, con: Any) -> None:
        con.execute("SELECT pg_advisory_xact_lock(%s)", (cls.REVIEW_LEDGER_LOCK_KEY,))

    @classmethod
    def _lock_authorizations(cls, con: Any) -> None:
        con.execute("SELECT pg_advisory_xact_lock(%s)", (cls.AUTHORIZATION_LOCK_KEY,))

    def _last_hash(self) -> str | None:
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT event_hash FROM workflow.review_events ORDER BY event_id DESC LIMIT 1"
                ).fetchone()
            return str(row["event_hash"]) if row else None
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_review_events_read_failed") from exc

    def append_event(
        self,
        *,
        event_type: str,
        object_id: str,
        object_version: str,
        actor: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        buffered = self._buffer.get()
        if buffered is not None:
            previous = buffered[-1]["event_hash"] if buffered else self._last_hash()
            event = self._new_event(
                event_type=event_type,
                object_id=object_id,
                object_version=object_version,
                actor=actor,
                details=details,
                previous_event_hash=previous,
            )
            buffered.append(event)
            return deepcopy(event)
        try:
            with self._connect() as con:
                with con.transaction():
                    self._lock_review_ledger(con)
                    row = con.execute(
                        "SELECT event_hash FROM workflow.review_events "
                        "ORDER BY event_id DESC LIMIT 1 FOR UPDATE"
                    ).fetchone()
                    previous = str(row["event_hash"]) if row else None
                    event = self._new_event(
                        event_type=event_type,
                        object_id=object_id,
                        object_version=object_version,
                        actor=actor,
                        details=details,
                        previous_event_hash=previous,
                    )
                    self._insert_event(con, event)
            self._mirror_events([event])
            return deepcopy(event)
        except WorkflowReviewStoreError:
            raise
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_review_event_write_failed") from exc

    def _resolved_snapshot_id(self, con: Any, event: Mapping[str, Any]) -> str | None:
        candidate = str((event.get("details") or {}).get("snapshot_id") or "")
        if not candidate:
            return None
        row = con.execute(
            "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s", (candidate,)
        ).fetchone()
        return candidate if row else None

    @staticmethod
    def _resolved_actor_id(con: Any, actor: str) -> str | None:
        row = con.execute(
            "SELECT account_id FROM workflow.accounts "
            "WHERE username=%s OR display_name=%s ORDER BY account_id LIMIT 1",
            (actor, actor),
        ).fetchone()
        return str(row["account_id"]) if row else None

    def _insert_event(self, con: Any, event: Mapping[str, Any]) -> None:
        con.execute(
            "INSERT INTO workflow.review_events("
            "snapshot_id,object_id,object_version,event_type,actor_account_id,actor_text,"
            "occurred_at,details,previous_event_hash,event_hash,event_payload) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb)",
            (
                self._resolved_snapshot_id(con, event),
                str(event.get("object_id") or ""),
                str(event.get("object_version") or ""),
                str(event.get("event_type") or ""),
                self._resolved_actor_id(con, str(event.get("actor") or "")),
                str(event.get("actor") or ""),
                str(event.get("occurred_at") or ""),
                _json_text(event.get("details") or {}),
                event.get("previous_event_hash"),
                str(event.get("event_hash") or ""),
                _json_text(dict(event)),
            ),
        )

    @contextmanager
    def buffered(self) -> Iterator[None]:
        existing = self._buffer.get()
        if existing is not None:
            yield
            return
        token = self._buffer.set([])
        try:
            yield
            events = list(self._buffer.get() or [])
            if events:
                self._flush_buffer(events)
        finally:
            self._buffer.reset(token)

    def _flush_buffer(self, events: list[dict[str, Any]]) -> None:
        try:
            with self._connect() as con:
                with con.transaction():
                    self._lock_review_ledger(con)
                    row = con.execute(
                        "SELECT event_hash FROM workflow.review_events "
                        "ORDER BY event_id DESC LIMIT 1 FOR UPDATE"
                    ).fetchone()
                    current = str(row["event_hash"]) if row else None
                    if events[0].get("previous_event_hash") != current:
                        raise WorkflowReviewStoreError("workflow_review_chain_conflict")
                    previous = current
                    for event in events:
                        if event.get("previous_event_hash") != previous:
                            raise WorkflowReviewStoreError("workflow_review_buffer_chain_invalid")
                        body = dict(event)
                        got = body.pop("event_hash", None)
                        if stable_hash(body) != got:
                            raise WorkflowReviewStoreError("workflow_review_event_hash_invalid")
                        self._insert_event(con, event)
                        previous = str(got)
            self._mirror_events(events)
        except WorkflowReviewStoreError:
            raise
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_review_event_write_failed") from exc

    def _mirror_events(self, events: list[dict[str, Any]]) -> None:
        if self._mirror_path is None or not events:
            return
        with suppress(OSError):
            self._mirror_path.parent.mkdir(parents=True, exist_ok=True)
            with self._mirror_path.open("a", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def read_bindings(self) -> dict[str, list[dict[str, Any]]]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT snapshot_id,object_id,object_version,canonical_object_hash,"
                    "confirmed_object_type,reviewer_account_id,reviewer_display_name,decision,valid "
                    "FROM workflow.publish_authorizations "
                    "ORDER BY snapshot_id,position NULLS LAST,authorization_id"
                ).fetchall()
            out: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                out.setdefault(str(row["snapshot_id"]), []).append(
                    {
                        "object_id": str(row["object_id"]),
                        "object_version": str(row["object_version"]),
                        "canonical_object_hash": str(row["canonical_object_hash"]),
                        "confirmed_object_type": str(row["confirmed_object_type"]),
                        "reviewer": str(row["reviewer_display_name"]),
                        "reviewer_id": str(row["reviewer_account_id"]),
                        "decision": str(row["decision"]),
                        "valid": bool(row["valid"]),
                    }
                )
            return out
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_publish_authorizations_read_failed") from exc

    @staticmethod
    def _insert_binding_rows(con: Any, snapshot_id: str, rows: list[dict[str, Any]]) -> None:
        for position, row in enumerate(rows):
            con.execute(
                "INSERT INTO workflow.publish_authorizations("
                "snapshot_id,object_id,object_version,canonical_object_hash,"
                "confirmed_object_type,reviewer_account_id,reviewer_display_name,"
                "decision,valid,position) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    snapshot_id,
                    row["object_id"],
                    row["object_version"],
                    row["canonical_object_hash"],
                    row["confirmed_object_type"],
                    row["reviewer_id"],
                    row["reviewer"],
                    row["decision"],
                    bool(row.get("valid")),
                    position,
                ),
            )

    def replace_snapshot_bindings(self, snapshot_id: str, rows: list[dict[str, Any]]) -> None:
        """Replace one snapshot without rewriting unrelated authorization state."""
        try:
            with self._connect() as con:
                with con.transaction():
                    self._lock_authorizations(con)
                    con.execute(
                        "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                        (snapshot_id,),
                    ).fetchone()
                    con.execute(
                        "DELETE FROM workflow.publish_authorizations WHERE snapshot_id=%s",
                        (snapshot_id,),
                    )
                    self._insert_binding_rows(con, snapshot_id, rows)
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_publish_authorizations_write_failed") from exc

    def replace_bindings(self, bindings: Mapping[str, list[dict[str, Any]]]) -> None:
        """Replace all authorization state for migration or explicit whole-store restore."""
        try:
            with self._connect() as con:
                with con.transaction():
                    self._lock_authorizations(con)
                    con.execute("DELETE FROM workflow.publish_authorizations")
                    for snapshot_id in sorted(bindings):
                        self._insert_binding_rows(con, snapshot_id, bindings[snapshot_id])
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_publish_authorizations_write_failed") from exc

    @staticmethod
    def _read_legacy_events(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            events = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowReviewStoreError("workflow_legacy_review_ledger_invalid") from exc
        previous = None
        for index, event in enumerate(events):
            body = dict(event)
            got = body.pop("event_hash", None)
            if body.get("previous_event_hash") != previous or stable_hash(body) != got:
                raise WorkflowReviewStoreError(f"workflow_legacy_review_chain_invalid:{index}")
            previous = got
        return events

    @staticmethod
    def _read_legacy_bindings(path: Path) -> dict[str, list[dict[str, Any]]]:
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowReviewStoreError("workflow_legacy_publish_authorizations_invalid") from exc
        if not isinstance(raw, dict) or any(not isinstance(value, list) for value in raw.values()):
            raise WorkflowReviewStoreError("workflow_legacy_publish_authorizations_invalid")
        return {str(key): [dict(row) for row in value] for key, value in raw.items()}

    def migrate_legacy_runtime(self, runtime: Path) -> dict[str, int]:
        """Copy exact local review state once; mismatches fail closed."""
        runtime = Path(runtime)
        events = self._read_legacy_events(runtime / "review_ledger.jsonl")
        bindings = self._read_legacy_bindings(runtime / "publish_authorizations.json")
        current_events = self.read_events()
        current_bindings = self.read_bindings()
        if current_events and current_events != events:
            raise WorkflowReviewStoreError("workflow_review_ledger_migration_conflict")
        if current_bindings and current_bindings != bindings:
            raise WorkflowReviewStoreError("workflow_publish_authorizations_migration_conflict")
        if not current_events and events:
            try:
                with self._connect() as con:
                    with con.transaction():
                        self._lock_review_ledger(con)
                        previous = None
                        for event in events:
                            if event.get("previous_event_hash") != previous:
                                raise WorkflowReviewStoreError("workflow_review_ledger_migration_conflict")
                            self._insert_event(con, event)
                            previous = str(event["event_hash"])
            except WorkflowReviewStoreError:
                raise
            except Exception as exc:
                raise WorkflowReviewStoreError("workflow_review_ledger_migration_failed") from exc
        if not current_bindings and bindings:
            self.replace_bindings(bindings)
        return {
            "review_events": len(events),
            "authorization_snapshots": len(bindings),
            "authorizations": sum(len(rows) for rows in bindings.values()),
        }
