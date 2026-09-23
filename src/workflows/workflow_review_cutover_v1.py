"""Opt-in PostgreSQL authority with rebuildable review-state disk mirrors."""
from __future__ import annotations

import json
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


class _PostgresWorkflowReviewMixin:
    workflow_review_store: PostgresWorkflowReviewStore

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
            raise ConsoleError("workflow_review_write_failed", str(exc)) from exc
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

    def object_review_bindings(self, snapshot_id: str) -> list[dict[str, Any]]:
        """Refresh PostgreSQL authorizations before deriving the public view."""
        try:
            current = self.workflow_review_store.read_bindings()
        except WorkflowReviewStoreError as exc:
            raise ConsoleError("workflow_review_unavailable", str(exc)) from exc
        self._bindings = current
        self._bindings_baseline = deepcopy(current)
        return super().object_review_bindings(snapshot_id)

    def _restore_review_state(
        self,
        *,
        bindings: dict[str, Any],
        snapshot_id: str | None,
        envelope: dict[str, Any] | None,
        objects: list[dict[str, Any]] | None,
    ) -> None:
        if snapshot_id is not None:
            with suppress(Exception):
                self.workflow_review_store.replace_snapshot_bindings(
                    snapshot_id,
                    list(bindings.get(snapshot_id, [])),
                )
        current = self.workflow_review_store.read_bindings()
        self._bindings = current
        self._bindings_baseline = deepcopy(current)
        self._mirror_bindings()
        if envelope is not None and objects is not None:
            with suppress(Exception):
                self.workflow_document_store.write_bundle(envelope=envelope, objects=objects)
            self.refresh_workflow_documents()
            self.refresh_objects_expected_revision(str(envelope["snapshot_id"]))

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
        with self._store_write_lock():
            self._reload_store_locked()
            prior_bindings = deepcopy(self._bindings)
            prior_envelope: dict[str, Any] | None = None
            prior_objects: list[dict[str, Any]] | None = None
            if sid:
                with suppress(ConsoleError):
                    prior_envelope = deepcopy(self._envelope(sid))
                    prior_objects = deepcopy(self._load_objects(sid, remember=False))
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
                self._restore_review_state(
                    bindings=prior_bindings,
                    snapshot_id=sid,
                    envelope=prior_envelope,
                    objects=prior_objects,
                )
                raise ConsoleError("workflow_review_write_failed", str(exc)) from exc
            except Exception:
                self._restore_review_state(
                    bindings=prior_bindings,
                    snapshot_id=sid,
                    envelope=prior_envelope,
                    objects=prior_objects,
                )
                raise

    @contextmanager
    def _atomic_snapshot_mutation(self, snapshot_id: str) -> Iterator[None]:
        prior_bindings: dict[str, Any] = {}
        prior_envelope: dict[str, Any] | None = None
        prior_objects: list[dict[str, Any]] | None = None
        restore_snapshot_id: str | None = None
        try:
            # The document context takes the process-shared store lock and
            # refreshes documents plus bindings before these rollback values
            # are captured. That ordering is required for a second worker.
            with super()._atomic_snapshot_mutation(snapshot_id):
                prior_bindings = deepcopy(self.workflow_review_store.read_bindings())
                prior_envelope = deepcopy(self._envelope(snapshot_id))
                prior_objects = deepcopy(self._load_objects(snapshot_id, remember=False))
                restore_snapshot_id = snapshot_id
                with workflow_transaction(self.workflow_review_store):
                    with buffer_events(self._ledger_path):
                        yield
        except Exception:
            self._restore_review_state(
                bindings=prior_bindings,
                snapshot_id=restore_snapshot_id,
                envelope=prior_envelope,
                objects=prior_objects,
            )
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
