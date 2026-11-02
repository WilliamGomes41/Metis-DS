"""PostgreSQL authority for review events and publish authorizations.

The existing review functions keep their public API. Review events preserve the
exact hash-chained payload; relational columns are indexes only. Publish
authorizations preserve the existing per-snapshot tuple records.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from src.integrity_kernel import stable_hash
from src.review.review_ledger import verify_ledger
from src.workflows.workflow_documents_postgres_v1 import (
    PostgresWorkflowDocumentStore,
    WorkflowDocumentStoreError,
    _json_text,
)


class WorkflowReviewStoreError(RuntimeError):
    """Fail-closed shared review-state error."""


class _EventBuffer(list):
    """Events buffered by one ``buffered()`` nesting level."""

    def __init__(self, parent: "_EventBuffer | None") -> None:
        super().__init__()
        self.parent = parent

    def last_hash(self) -> str | None:
        """Hash of the newest buffered event on this level or any parent."""
        level: _EventBuffer | None = self
        while level is not None:
            if level:
                return str(level[-1]["event_hash"])
            level = level.parent
        return None


class PostgresWorkflowReviewStore(PostgresWorkflowDocumentStore):
    """Shared authority for hash-chained review evidence and authorizations."""

    REVIEW_LEDGER_LOCK_KEY = 714812479584013
    AUTHORIZATION_LOCK_KEY = 714812479584014

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._buffer: ContextVar[_EventBuffer | None] = ContextVar(
            "workflow_review_event_buffer", default=None
        )


    def verify_review_schema(self) -> None:
        try:
            with self._connect() as con:
                self._verify_schema_connection(con)
                rows = con.execute(
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema='workflow' AND ("
                    "(table_name='review_events' AND column_name IN ('actor_text','event_payload')) OR "
                    "(table_name='publish_authorizations' AND column_name IN "
                    "('position','authorization_payload')))"
                ).fetchall()
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_review_schema_check_failed") from exc
        present = {(str(row["table_name"]), str(row["column_name"])) for row in rows}
        required = {
            ("review_events", "actor_text"),
            ("review_events", "event_payload"),
            ("publish_authorizations", "position"),
            ("publish_authorizations", "authorization_payload"),
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

    def read_events_for_snapshots(self, snapshot_ids: list[str]) -> list[dict[str, Any]]:
        """Read authorized document history without decoding the global ledger."""
        if not snapshot_ids:
            return []
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT event_payload FROM workflow.review_events "
                    "WHERE event_payload->'details'->>'snapshot_id'=ANY(%s) ORDER BY event_id",
                    (snapshot_ids,),
                ).fetchall()
            return [self._event_payload(row['event_payload']) for row in rows]
        except Exception as exc:
            raise WorkflowReviewStoreError('workflow_review_read_failed') from exc

    def read_review_participation_events(self, snapshot_ids: list[str]) -> list[dict[str, Any]]:
        """Distinct read-only event facts used by the personal start/continue link.

        This does not decide whether an event is a review or belongs to an actor;
        the existing presentation predicates still own those decisions. Audit
        details, chain hashes and prior object payloads are deliberately absent.
        """
        if not snapshot_ids:
            return []
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT DISTINCT jsonb_build_object("
                    "'event_type',event_payload->'event_type','actor',event_payload->'actor',"
                    "'details',jsonb_build_object('snapshot_id',event_payload#>'{details,snapshot_id}',"
                    "'reviewer_id',event_payload#>'{details,reviewer_id}',"
                    "'reviewer_account_id',event_payload#>'{details,reviewer_account_id}')) AS event "
                    "FROM workflow.review_events "
                    "WHERE event_payload->'details'->>'snapshot_id'=ANY(%s)",
                    (snapshot_ids,)).fetchall()
            return [self._event_payload(row['event']) for row in rows]
        except Exception as exc:
            raise WorkflowReviewStoreError('workflow_review_read_failed') from exc

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

    def read_command_events(self) -> list[dict[str, Any]]:
        """Persisted events plus this command context's pending audit evidence."""
        events = self.read_events()
        levels = []
        level = self._buffer.get()
        while level is not None:
            levels.append(level)
            level = level.parent
        for level in reversed(levels):
            events.extend(deepcopy(list(level)))
        return events

    def source_command_receipt(self, snapshot_id, event_type, command_id):
        """Existing receipt semantics, scoped before precondition validation."""
        try:
            with self._connect() as con:
                row = con.execute("SELECT event_payload FROM workflow.review_events WHERE "
                    "event_payload#>>'{details,snapshot_id}'=%s AND event_type=%s "
                    "AND event_payload#>>'{details,command_id}'=%s ORDER BY event_id LIMIT 1",
                    (snapshot_id, event_type, command_id)).fetchone()
            return self._event_payload(row['event_payload']) if row else None
        except Exception as exc:
            raise WorkflowReviewStoreError('workflow_review_events_read_failed') from exc

    def read_review_command_events(
        self, snapshot_id: str, object_ids: list[str], *, interaction_id: str = "",
    ) -> list[dict[str, Any]]:
        """Scoped evidence plus the global interaction-identity history.

        An interaction ID can conflict across snapshots, so that lookup must
        not be restricted to this command's document. Pending native buffer
        levels participate in the same identity and command checks.
        """
        try:
            conditions, params = [], []
            if object_ids:
                conditions.append(
                    "((snapshot_id=%s OR event_payload->'details'->>'snapshot_id'=%s) "
                    "AND object_id=ANY(%s))"
                )
                params.extend((snapshot_id, snapshot_id, sorted(set(object_ids))))
            if interaction_id:
                conditions.append("event_payload#>>'{details,review_interaction,interaction_id}'=%s")
                params.append(interaction_id)
            events = []
            if conditions:
                with self._connect() as con:
                    rows = con.execute(
                        "SELECT event_payload FROM workflow.review_events WHERE "
                        + " OR ".join(conditions) + " ORDER BY event_id", tuple(params),
                    ).fetchall()
                events = [self._event_payload(row["event_payload"]) for row in rows]
            levels = []
            level = self._buffer.get()
            while level is not None:
                levels.append(level)
                level = level.parent
            wanted = set(object_ids)
            for level in reversed(levels):
                for event in level:
                    details = event.get("details") or {}
                    interaction = details.get("review_interaction") or {}
                    if ((details.get("snapshot_id") == snapshot_id and event.get("object_id") in wanted)
                            or (interaction_id and interaction.get("interaction_id") == interaction_id)):
                        events.append(deepcopy(event))
            return events
        except WorkflowReviewStoreError:
            raise
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_review_events_read_failed") from exc

    def read_events_after(self, previous_event_hash: str | None, limit: int) -> list[dict[str, Any]]:
        """Up to ``limit`` committed events chained directly after ``previous_event_hash``.

        B1 (#708): the bounded read behind the post-commit ledger projection.
        Fewer rows than requested means the anchor is not in PostgreSQL.
        """
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT event_payload FROM workflow.review_events "
                    + ("" if previous_event_hash is None else
                       "WHERE event_id > (SELECT event_id FROM workflow.review_events WHERE event_hash=%s) ")
                    + "ORDER BY event_id LIMIT %s",
                    (limit,) if previous_event_hash is None else (previous_event_hash, limit),
                ).fetchall()
            if any(row["event_payload"] is None for row in rows):
                raise WorkflowReviewStoreError("workflow_review_cutover_not_prepared")
            events = [self._event_payload(row["event_payload"]) for row in rows]
        except WorkflowReviewStoreError:
            raise
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_review_events_read_failed") from exc
        previous = previous_event_hash
        for event in events:
            body = dict(event)
            got = body.pop("event_hash", None)
            if body.get("previous_event_hash") != previous or stable_hash(body) != got:
                raise WorkflowReviewStoreError("workflow_review_chain_conflict")
            previous = str(got)
        return events

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
            previous = buffered.last_hash()
            if previous is None:
                previous = self._last_hash()
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
        # I2: every nesting level owns its events. On an exception the level
        # discards them (its savepoint rolled the bindings back); on success
        # they merge into the parent level. Only the outermost level flushes.
        parent = self._buffer.get()
        level = _EventBuffer(parent)
        token = self._buffer.set(level)
        try:
            yield
            events = list(level)
            if parent is not None:
                parent.extend(events)
            elif events:
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
        except WorkflowReviewStoreError:
            raise
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_review_event_write_failed") from exc


    def read_bindings(self, snapshot_ids: list[str] | None = None, *,
                      object_ids: list[str] | None = None) -> dict[str, list[dict[str, Any]]]:
        if snapshot_ids == []:
            return {}
        if object_ids == []:
            return {}
        try:
            conditions, params = [], []
            if snapshot_ids is not None:
                conditions.append('snapshot_id=ANY(%s)')
                params.append(snapshot_ids)
            if object_ids is not None:
                conditions.append('object_id=ANY(%s)')
                params.append(object_ids)
            with self._connect() as con:
                rows = con.execute(
                    "SELECT snapshot_id,object_id,object_version,canonical_object_hash,"
                    "confirmed_object_type,reviewer_account_id,reviewer_display_name,decision,valid,"
                    "authorization_payload "
                    "FROM workflow.publish_authorizations "
                    + ('WHERE ' + ' AND '.join(conditions) + ' ' if conditions else '')
                    + "ORDER BY snapshot_id,position NULLS LAST,authorization_id",
                    *((tuple(params),) if params else ()),
                ).fetchall()
            out: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                relational = self._binding_projection(row)
                payload = row["authorization_payload"]
                if payload is None:
                    binding = relational
                else:
                    binding = self._authorization_payload(payload)
                    if self._binding_projection(binding) != relational:
                        raise WorkflowReviewStoreError("workflow_publish_authorization_payload_invalid")
                out.setdefault(str(row["snapshot_id"]), []).append(binding)
            return out
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_publish_authorizations_read_failed") from exc

    @staticmethod
    def _authorization_payload(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return deepcopy(value)
        if isinstance(value, str):
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        raise WorkflowReviewStoreError("workflow_publish_authorization_payload_invalid")

    @staticmethod
    def _binding_projection(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "object_id": str(row["object_id"]),
            "object_version": str(row["object_version"]),
            "canonical_object_hash": str(row["canonical_object_hash"]),
            "confirmed_object_type": str(row["confirmed_object_type"]),
            "reviewer": str(row.get("reviewer", row.get("reviewer_display_name", ""))),
            "reviewer_id": str(row.get("reviewer_id", row.get("reviewer_account_id", ""))),
            "decision": str(row["decision"]),
            "valid": bool(row["valid"]),
        }

    @staticmethod
    def _insert_binding_rows(con: Any, snapshot_id: str, rows: list[dict[str, Any]]) -> None:
        for position, row in enumerate(rows):
            con.execute(
                "INSERT INTO workflow.publish_authorizations("
                "snapshot_id,object_id,object_version,canonical_object_hash,"
                "confirmed_object_type,reviewer_account_id,reviewer_display_name,"
                "decision,valid,position,authorization_payload) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
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
                    _json_text(row),
                ),
            )

    def _backfill_exact_binding_payloads(
        self, bindings: Mapping[str, list[dict[str, Any]]]
    ) -> None:
        """Attach exact legacy payloads only after every relational field matches."""
        expected = [
            (snapshot_id, position, row)
            for snapshot_id in sorted(bindings)
            for position, row in enumerate(bindings[snapshot_id])
        ]
        try:
            with self._connect() as con:
                with con.transaction():
                    self._lock_authorizations(con)
                    rows = con.execute(
                        "SELECT authorization_id,snapshot_id,object_id,object_version,"
                        "canonical_object_hash,confirmed_object_type,reviewer_account_id,"
                        "reviewer_display_name,decision,valid,position,authorization_payload "
                        "FROM workflow.publish_authorizations "
                        "ORDER BY snapshot_id,position NULLS LAST,authorization_id FOR UPDATE"
                    ).fetchall()
                    if len(rows) != len(expected):
                        raise WorkflowReviewStoreError("workflow_publish_authorizations_migration_conflict")
                    for database_row, (snapshot_id, position, legacy_row) in zip(rows, expected):
                        if (
                            str(database_row["snapshot_id"]) != snapshot_id
                            or database_row["position"] != position
                            or self._binding_projection(database_row)
                            != self._binding_projection(legacy_row)
                        ):
                            raise WorkflowReviewStoreError("workflow_publish_authorizations_migration_conflict")
                        payload = database_row["authorization_payload"]
                        if payload is not None and self._authorization_payload(payload) != legacy_row:
                            raise WorkflowReviewStoreError("workflow_publish_authorizations_migration_conflict")
                    for database_row, (_, _, legacy_row) in zip(rows, expected):
                        if database_row["authorization_payload"] is None:
                            con.execute(
                                "UPDATE workflow.publish_authorizations "
                                "SET authorization_payload=%s::jsonb WHERE authorization_id=%s",
                                (_json_text(legacy_row), database_row["authorization_id"]),
                            )
        except WorkflowReviewStoreError:
            raise
        except Exception as exc:
            raise WorkflowReviewStoreError("workflow_publish_authorizations_migration_failed") from exc

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

    def apply_review_binding_delta(
        self, snapshot_id: str, before: list[dict[str, Any]], after: list[dict[str, Any]],
    ) -> None:
        """Renew/invalidate retained tuples and append new ones, preserving order.

        Physical authorization IDs and positions stay private to this adapter;
        canonical binding payloads retain their established exact representation.
        Repeated legacy tuples are matched by occurrence, never collapsed.
        """
        fields = ("object_id", "object_version", "canonical_object_hash", "confirmed_object_type",
                  "reviewer_id", "decision")
        def identity(row):
            return tuple(row.get(field) for field in fields)
        if len(after) < len(before) or [identity(row) for row in after[:len(before)]] != [identity(row) for row in before]:
            raise WorkflowReviewStoreError("workflow_review_binding_removal_or_reorder")
        object_ids = sorted({str(row.get("object_id") or "") for row in [*before, *after]})
        if "" in object_ids or not snapshot_id:
            raise WorkflowReviewStoreError("workflow_publish_authorizations_write_failed")
        if not object_ids:
            return
        try:
            with self._connect() as con:
                with con.transaction():
                    self._lock_authorizations(con)
                    document = con.execute(
                        "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE", (snapshot_id,),
                    ).fetchone()
                    if document is None:
                        raise WorkflowReviewStoreError("unknown_snapshot")
                    rows = con.execute(
                        "SELECT authorization_id,position,snapshot_id,object_id,object_version,canonical_object_hash,"
                        "confirmed_object_type,reviewer_account_id,reviewer_display_name,decision,valid,authorization_payload "
                        "FROM workflow.publish_authorizations WHERE snapshot_id=%s AND object_id=ANY(%s) "
                        "ORDER BY position NULLS LAST,authorization_id FOR UPDATE", (snapshot_id, object_ids),
                    ).fetchall()
                    current = []
                    for row in rows:
                        projection = self._binding_projection(row)
                        payload = row["authorization_payload"]
                        binding = projection if payload is None else self._authorization_payload(payload)
                        if self._binding_projection(binding) != projection:
                            raise WorkflowReviewStoreError("workflow_publish_authorization_payload_invalid")
                        current.append(binding)
                    if current != before:
                        raise WorkflowReviewStoreError("snapshot_object_write_conflict")
                    for row, previous, following in zip(rows, before, after):
                        if previous != following:
                            con.execute(
                                "UPDATE workflow.publish_authorizations SET reviewer_display_name=%s,valid=%s,"
                                "authorization_payload=%s::jsonb WHERE authorization_id=%s",
                                (following["reviewer"], bool(following.get("valid")), _json_text(following),
                                 row["authorization_id"]),
                            )
                    additions = after[len(before):]
                    if additions:
                        tail = con.execute(
                            "SELECT position FROM workflow.publish_authorizations WHERE snapshot_id=%s "
                            "ORDER BY position DESC LIMIT 1", (snapshot_id,),
                        ).fetchone()
                        for offset, row in enumerate(additions, 1):
                            # NULL-position legacy rows sort last by authorization_id.
                            # Appending another NULL retains that established order.
                            position = None if tail is not None and tail["position"] is None else (
                                tail["position"] if tail is not None else -1) + offset
                            con.execute(
                                "INSERT INTO workflow.publish_authorizations("
                                "snapshot_id,object_id,object_version,canonical_object_hash,confirmed_object_type,"
                                "reviewer_account_id,reviewer_display_name,decision,valid,position,authorization_payload) "
                                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                                (snapshot_id, row["object_id"], row["object_version"], row["canonical_object_hash"],
                                 row["confirmed_object_type"], row["reviewer_id"], row["reviewer"], row["decision"],
                                 bool(row.get("valid")), position, _json_text(row)),
                            )
        except WorkflowReviewStoreError:
            raise
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
            self._backfill_exact_binding_payloads(bindings)
            current_bindings = self.read_bindings()
            if current_bindings != bindings:
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
