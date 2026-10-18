"""Opt-in PostgreSQL authority with rebuildable review-state disk mirrors."""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from contextlib import contextmanager, nullcontext, suppress
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from src.operations_console_v1 import ConsoleError, _atomic_replace_bytes, _atomic_write
from src.request_diagnostics_v1 import diagnostic_phase
from src.review_ledger import buffer_events, register_backend
from src.workflows.workflow_documents_cutover_v1 import (
    PostgresWorkflowAzureAuthoritativePublicationConsole,
    PostgresWorkflowDurablePublicationConsole,
)
from src.workflows.workflow_review_postgres_v1 import (
    PostgresWorkflowReviewStore,
    WorkflowReviewStoreError,
)
from src.workflows.store_command_v1 import (
    StoreCommand,
    active_store_command,
    close_store_command,
    open_store_command,
    owned_store_command,
)
from src.workflows.workflow_transaction_v1 import workflow_transaction, workflow_transaction_active


_REMIRROR_WARNED_ATTR = "_metis_review_remirror_warned"
# Fallback for exceptions that reject attributes: identity match against the
# most recent ones; holding the objects keeps their id() from being reused.
_remirror_warned_fallback: deque[BaseException] = deque(maxlen=32)
_remirror_warned_fallback_lock = threading.Lock()


def _remirror_warning_already_logged(original: BaseException) -> bool:
    """Return True when a remirror warning was already logged for this fault.

    Follows explicit wrapping (``raise ... from``) so a wrapped original counts
    as the same fault. Marks ``original`` otherwise; NOOIT raises.
    """
    seen: set[int] = set()
    current: BaseException | None = original
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if getattr(current, _REMIRROR_WARNED_ATTR, False):
            return True
        with _remirror_warned_fallback_lock:
            if any(item is current for item in _remirror_warned_fallback):
                return True
        current = current.__cause__
    try:
        setattr(original, _REMIRROR_WARNED_ATTR, True)
    except Exception:
        with _remirror_warned_fallback_lock:
            _remirror_warned_fallback.append(original)
    return False


_UNREADABLE_TAIL = object()


def _ledger_mirror_tail_hash(path: Path) -> Any:
    """``event_hash`` of the mirror's last line, read backwards from the end.

    None for an empty or missing mirror; ``_UNREADABLE_TAIL`` when the last
    line cannot be read or parsed, which never matches an anchor.
    """
    try:
        with path.open("rb") as handle:
            position = handle.seek(0, 2)
            data = b""
            while position > 0:
                step = min(65536, position)
                position -= step
                handle.seek(position)
                data = handle.read(step) + data
                if b"\n" in data.rstrip(b"\n"):
                    break
    except FileNotFoundError:
        return None
    except OSError:
        return _UNREADABLE_TAIL
    line = data.rstrip(b"\n").rsplit(b"\n", 1)[-1]
    if not line:
        return None
    try:
        return json.loads(line)["event_hash"]
    except (ValueError, KeyError, TypeError):
        return _UNREADABLE_TAIL


class _PostgresWorkflowReviewMixin:
    workflow_review_store: PostgresWorkflowReviewStore
    # #665 naad B: the documents mixin only constructs under review authority.
    _metis_workflow_review_authority = True

    def __init__(
        self,
        *args: Any,
        workflow_review_store: PostgresWorkflowReviewStore,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.workflow_review_store = workflow_review_store
        self.workflow_review_store.verify_review_schema()
        self.workflow_review_store.bind_ledger_mirror(self._ledger_path)
        self._bindings = self._remirror_review_runtime()
        self._bindings_baseline = deepcopy(self._bindings)
        register_backend(self._ledger_path, self.workflow_review_store)

    def _startup_local_mirror_is_authority(self, path: Path) -> bool:
        if path.name == "publish_authorizations.json":
            return False
        return super()._startup_local_mirror_is_authority(path)

    def _remirror_review_runtime(self) -> dict[str, list[dict[str, Any]]]:
        """Rebuild disk mirrors from the authoritative PostgreSQL review state."""
        events = self.workflow_review_store.read_events()
        bindings = self.workflow_review_store.read_bindings()
        ledger_text = "".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events
        )
        with suppress(OSError):
            _atomic_replace_bytes(self._ledger_path, ledger_text.encode("utf-8"))
        self._bindings = bindings
        self._mirror_bindings()
        return bindings

    def _mirror_bindings(self) -> None:
        command = owned_store_command(self)
        if command is not None:
            # #678 U3: rebuilt from PostgreSQL after the commit.
            command.bindings = True
            return
        with suppress(OSError):
            _atomic_write(self._bindings_path, self._bindings)

    @staticmethod
    def _changed_binding_snapshots(
        before: dict[str, list[dict[str, Any]]],
        after: dict[str, list[dict[str, Any]]],
    ) -> set[str]:
        keys = set(before) | set(after)
        return {snapshot_id for snapshot_id in keys if before.get(snapshot_id, []) != after.get(snapshot_id, [])}

    def _persist_binding_changes(
        self,
        before: dict[str, list[dict[str, Any]]],
        after: dict[str, list[dict[str, Any]]],
    ) -> None:
        for snapshot_id in sorted(self._changed_binding_snapshots(before, after)):
            self.workflow_review_store.replace_snapshot_bindings(snapshot_id, list(after.get(snapshot_id, [])))

    def _save_bindings(self) -> None:
        payload = getattr(self, "_prepared_bindings", None)
        source = self._bindings if payload is None else payload
        baseline = deepcopy(self._bindings_baseline)
        try:
            self._persist_binding_changes(baseline, source)
            current = self.workflow_review_store.read_bindings()
        except WorkflowReviewStoreError as exc:
            raise ConsoleError("workflow_review_write_failed") from exc
        self._bindings = current
        self._bindings_baseline = deepcopy(current)
        self._mirror_bindings()

    def _reload_store_locked(self) -> None:
        command = owned_store_command(self)
        if command is not None and command.fresh:
            # #678 U1: the owner reloaded under the store lock; the command keeps
            # the in-process maps current, participants MAG NIET reload.
            return
        super()._reload_store_locked()
        try:
            self._bindings = self.workflow_review_store.read_bindings()
        except WorkflowReviewStoreError as exc:
            raise ConsoleError("workflow_review_unavailable", str(exc)) from exc
        self._bindings_baseline = deepcopy(self._bindings)
        self._mirror_bindings()
        if command is not None:
            command.fresh = True

    def object_review_bindings(self, snapshot_id: str, *, objects=None) -> list[dict[str, Any]]:
        """Refresh PostgreSQL authorizations before deriving the public view."""
        try:
            current = self.workflow_review_store.read_bindings()
        except WorkflowReviewStoreError as exc:
            raise ConsoleError("workflow_review_unavailable", str(exc)) from exc
        self._bindings = current
        self._bindings_baseline = deepcopy(current)
        return super().object_review_bindings(snapshot_id, objects=objects)

    def _remirror_after_rollback(self, snapshot_id: str | None, original: BaseException) -> None:
        """Rebuild disposable mirrors from PostgreSQL after a native rollback.

        Reads only PostgreSQL, writes only disk mirrors and process state, and
        runs under the re-entrant store lock so a stale read never replaces a
        concurrent writer's mirror. NOOIT write workflow.* here.
        """
        try:
            with self._store_write_lock():
                self._remirror_review_runtime()
                self._bindings_baseline = deepcopy(self._bindings)
                if snapshot_id:
                    self.refresh_workflow_documents()
                    self.refresh_objects_expected_revision(snapshot_id)
        except Exception as remirror_exc:
            # Option C: every nesting level remirrors, but the warning MOET
            # appear exactly once per original exception.
            if _remirror_warning_already_logged(original):
                return
            # Codes, ids and error types only: no text, corrections or actors.
            logging.getLogger(__name__).warning(
                "review_rollback_remirror_failed snapshot_id=%s error_code=%s remirror_error_type=%s",
                snapshot_id or "",
                getattr(original, "code", None) or type(original).__name__,
                type(remirror_exc).__name__,
            )

    def _store_command_applies(self) -> bool:
        """Whether this boundary owns or joins a Storeopdracht (#678).

        False only on the compatibility path: a raw ``workflow_transaction``
        that no command owns (publish, heading batch, ...) keeps the pre-#678
        nested behavior until that owner is migrated; reprocessing refuses it
        (#708). A command of another console is refused before any lock or write.
        """
        command = active_store_command()
        if command is not None:
            if command.owner is not self:
                raise ConsoleError("store_command_foreign_owner")
            return True
        return not workflow_transaction_active()

    def _lock_document_row(self, connection: Any, snapshot_id: str) -> None:
        row = connection.execute(
            "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise ConsoleError("unknown_snapshot")

    @contextmanager
    def _store_command(
        self, snapshot_id: str | None, *, lock_row: bool = False, buffered: bool = True,
    ) -> Iterator[StoreCommand]:
        """Own or join the Storeopdracht for one durable command.

        Owner: store lock, one transaction, one reload, then after the commit
        one mirror rebuild from PostgreSQL; after a rollback the existing full
        remirror. Participant: a savepoint and an event-buffer level only.
        """
        command = owned_store_command(self)
        if command is not None:
            with self._join_store_command(command, snapshot_id, lock_row=lock_row, buffered=buffered):
                yield command
            return
        with self._store_write_lock():
            command, token = open_store_command(self)
            if snapshot_id:
                command.snapshot_ids.add(snapshot_id)
            try:
                with diagnostic_phase("store_transaction"), \
                        workflow_transaction(self.workflow_review_store) as connection:
                    if lock_row and snapshot_id:
                        self._lock_document_row(connection, snapshot_id)
                    self._reload_store_locked()
                    with buffer_events(self._ledger_path) if buffered else nullcontext():
                        yield command
                    if command.poisoned:
                        # A caught participant fault left unverified process state.
                        raise ConsoleError("store_command_participant_refresh_failed")
            except BaseException as exc:
                close_store_command(token)
                with diagnostic_phase("store_remirror"):
                    self._remirror_after_rollback(snapshot_id, exc)
                raise
            close_store_command(token)
            with diagnostic_phase("store_remirror"):
                self._remirror_from_pg(command)

    @contextmanager
    def _join_store_command(
        self, command: StoreCommand, snapshot_id: str | None, *, lock_row: bool, buffered: bool,
    ) -> Iterator[None]:
        if snapshot_id:
            command.snapshot_ids.add(snapshot_id)
        mark = len(command.events)
        try:
            with workflow_transaction(self.workflow_review_store) as connection:
                if lock_row and snapshot_id:
                    self._lock_document_row(connection, snapshot_id)
                with buffer_events(self._ledger_path) if buffered else nullcontext():
                    yield
        except BaseException:
            # The savepoint rolled this level back: drop its ledger lines and
            # refresh process state from the transaction's own view (reads only).
            del command.events[mark:]
            if not self._refresh_runtime_in_command(snapshot_id):
                command.poisoned = True
            raise

    def _refresh_runtime_in_command(self, snapshot_id: str | None) -> bool:
        """Re-read in-process maps inside the open command. NOOIT a disk write; U4.

        Returns False when the refresh failed; the owner then rolls back.
        """
        try:
            self._bindings = self.workflow_review_store.read_bindings()
            self._bindings_baseline = deepcopy(self._bindings)
            self.refresh_workflow_documents()
            if snapshot_id:
                self.refresh_objects_expected_revision(snapshot_id)
        except Exception as refresh_exc:
            logging.getLogger(__name__).warning(
                "store_command_participant_refresh_failed snapshot_id=%s error_type=%s",
                snapshot_id or "", type(refresh_exc).__name__,
            )
            return False
        return True

    def _remirror_from_pg(self, command: StoreCommand) -> None:
        """B1: the single mirror writer, after a successful commit, under the store lock.

        Writes only what the command deferred, read back from PostgreSQL. A
        failure here MAG NIET fail the committed command; startup and the next
        command rebuild the disposable mirrors.
        """
        try:
            if command.events:
                self._project_committed_events(command.events)
            if command.bindings:
                self._bindings = self.workflow_review_store.read_bindings()
                self._bindings_baseline = deepcopy(self._bindings)
                self._mirror_bindings()
            for snapshot_id in sorted(command.objects):
                self._mirror_objects(snapshot_id, self.workflow_document_store.list_document_objects(snapshot_id))
            if command.envelopes:
                for snapshot_id in sorted(command.snapshot_ids):
                    envelope = self.workflow_document_store.get_envelope(snapshot_id)
                    if envelope is None:
                        self._envelopes.pop(snapshot_id, None)
                    else:
                        self._envelopes[snapshot_id] = envelope
                self._mirror_envelopes()
        except Exception as remirror_exc:
            logging.getLogger(__name__).warning(
                "store_command_remirror_failed snapshot_ids=%s error_type=%s",
                ",".join(sorted(command.snapshot_ids)), type(remirror_exc).__name__,
            )

    def _project_committed_events(self, deferred: list[dict[str, Any]]) -> None:
        """B1 (#708): append the command's committed events as read from PostgreSQL.

        One bounded read anchored on the hash the command chained onto. The
        deferred copies only name which rows to read. A mirror tail or rows that
        do not match that chain mean the mirror is stale: rebuild it in full.
        """
        anchor = deferred[0].get("previous_event_hash")
        try:
            committed = self.workflow_review_store.read_events_after(anchor, len(deferred))
        except WorkflowReviewStoreError as exc:
            if exc.args != ("workflow_review_chain_conflict",):
                raise
            committed = []
        if (_ledger_mirror_tail_hash(self._ledger_path) == anchor
                and [event["event_hash"] for event in committed] == [event["event_hash"] for event in deferred]):
            self.workflow_review_store._mirror_events(committed)
            return
        logging.getLogger(__name__).warning("store_command_ledger_divergence events=%d", len(deferred))
        self._remirror_review_runtime()

    @contextmanager
    def _reprocessing_transaction(self, snapshot_id: str) -> Iterator[None]:
        """Own or join the command with the document row lock, without an event buffer."""
        self._require_review_store_configured()
        if not self._store_command_applies():
            # A raw owner cannot defer mirrors or recover reprocessing safely.
            raise ConsoleError("reprocessing_store_command_required")
        with self._store_command(snapshot_id, lock_row=True, buffered=False):
            yield

    def _recover_after_failed_correction(self) -> None:
        # The Storeopdracht owner already rolled back and remirrored (#678 U4).
        # NOOIT raise here: this runs while the original error propagates.
        if active_store_command() is not None or not workflow_transaction_active():
            return
        super()._recover_after_failed_correction()

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
        sid = snapshot_id or (objects[0] if objects is not None else None)
        if sid is not None and getattr(self._objects_tls, "heading_batch_snapshot", None) == sid:
            # The batch owns native rollback, including the final commit. Avoid
            # the legacy compensating writes from captured per-member state.
            return super()._commit_prepared_store(
                envelopes=envelopes, bindings=bindings, objects=objects,
                expected_revision=expected_revision, ledger_fn=ledger_fn,
                snapshot_id=snapshot_id,
            )
        if self._store_command_applies():
            try:
                with self._store_command(sid):
                    super()._commit_prepared_store(
                        envelopes=envelopes, bindings=bindings, objects=objects,
                        expected_revision=expected_revision, ledger_fn=ledger_fn,
                        snapshot_id=snapshot_id,
                    )
                    if bindings is not None:
                        current = self.workflow_review_store.read_bindings()
                        self._bindings = current
                        self._bindings_baseline = deepcopy(current)
                        self._mirror_bindings()
            except WorkflowReviewStoreError as exc:
                # #665 V-b: codes only, NOOIT store text.
                raise ConsoleError("workflow_review_write_failed") from exc
            return
        with self._store_write_lock():
            self._reload_store_locked()
            try:
                with workflow_transaction(self.workflow_review_store):
                    with buffer_events(self._ledger_path):
                        super()._commit_prepared_store(
                            envelopes=envelopes,
                            bindings=bindings,
                            objects=objects,
                            expected_revision=expected_revision,
                            ledger_fn=ledger_fn,
                            snapshot_id=snapshot_id,
                        )
                        if bindings is not None:
                            current = self.workflow_review_store.read_bindings()
                            self._bindings = current
                            self._bindings_baseline = deepcopy(current)
                            self._mirror_bindings()
            except WorkflowReviewStoreError as exc:
                self._remirror_after_rollback(sid, exc)
                raise ConsoleError("workflow_review_write_failed") from exc
            except Exception as exc:
                if isinstance(exc, ConsoleError) and exc.code == "snapshot_object_write_conflict":
                    self._remirror_review_runtime()
                    self._bindings_baseline = deepcopy(self._bindings)
                    raise
                self._remirror_after_rollback(sid, exc)
                raise

    @contextmanager
    def _heading_batch_mutation(self, snapshot_id: str) -> Iterator[None]:
        with self._store_write_lock():
            try:
                with super()._heading_batch_mutation(snapshot_id):
                    with buffer_events(self._ledger_path):
                        yield
            finally:
                try:
                    self._remirror_review_runtime()
                    self._bindings_baseline = deepcopy(self._bindings)
                except Exception:
                    logging.getLogger(__name__).warning("heading_batch_review_mirror_refresh_failed")

    @contextmanager
    def _atomic_snapshot_mutation(self, snapshot_id: str) -> Iterator[None]:
        if getattr(self._objects_tls, "heading_batch_snapshot", None) == snapshot_id:
            yield
            return
        if self._store_command_applies():
            # #678: own or join the Storeopdracht. Route 1 holds: native rollback
            # only, never the inherited documents compensation.
            with self._store_command(snapshot_id):
                yield
            return
        try:
            # Route 1: take the process-shared store lock and reload directly,
            # NOOIT via the inherited documents context, whose except branch
            # compensates with a blind write_bundle and a ledger truncation
            # (#665 keeps that for non-review paths). The native transaction
            # is the only rollback; afterwards only PostgreSQL-backed remirror.
            with self._store_write_lock():
                self._reload_store_locked()
                with workflow_transaction(self.workflow_review_store):
                    with buffer_events(self._ledger_path):
                        yield
        except Exception as exc:
            if isinstance(exc, ConsoleError) and exc.code == "snapshot_object_write_conflict":
                with self._store_write_lock():
                    self.refresh_workflow_documents()
                    self.refresh_objects_expected_revision(snapshot_id)
                    self._remirror_review_runtime()
                    self._bindings_baseline = deepcopy(self._bindings)
                raise
            self._remirror_after_rollback(snapshot_id, exc)
            raise


class PostgresReviewWorkflowDurablePublicationConsole(
    _PostgresWorkflowReviewMixin,
    PostgresWorkflowDurablePublicationConsole,
):
    pass


class PostgresReviewWorkflowAzureAuthoritativePublicationConsole(
    _PostgresWorkflowReviewMixin,
    PostgresWorkflowAzureAuthoritativePublicationConsole,
):
    pass
