"""Opt-in PostgreSQL authority with rebuildable review-state disk mirrors."""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from contextlib import contextmanager, suppress
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from src.operations_console_v1 import ConsoleError, _atomic_replace_bytes, _atomic_write
from src.review_ledger import buffer_events, register_backend
from src.workflows.workflow_documents_cutover_v1 import (
    PostgresWorkflowAzureAuthoritativePublicationConsole,
    PostgresWorkflowDurablePublicationConsole,
)
from src.workflows.workflow_review_postgres_v1 import (
    PostgresWorkflowReviewStore,
    WorkflowReviewStoreError,
)
from src.workflows.workflow_transaction_v1 import workflow_transaction


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
        super()._reload_store_locked()
        try:
            self._bindings = self.workflow_review_store.read_bindings()
        except WorkflowReviewStoreError as exc:
            raise ConsoleError("workflow_review_unavailable", str(exc)) from exc
        self._bindings_baseline = deepcopy(self._bindings)
        self._mirror_bindings()

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
