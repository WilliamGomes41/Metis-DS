"""Opt-in PostgreSQL authority for review evidence and publish authorizations."""
from __future__ import annotations

from contextlib import contextmanager, suppress
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from src.operations_console_v1 import ConsoleError, _atomic_write
from src.review_ledger import buffer_events, register_backend
from src.workflow_documents_cutover_v1 import (
    PostgresWorkflowAzureAuthoritativePublicationConsole,
    PostgresWorkflowDurablePublicationConsole,
)
from src.workflow_review_postgres_v1 import (
    PostgresWorkflowReviewStore,
    WorkflowReviewStoreError,
)


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
        self._assert_review_cutover_prepared()
        self.workflow_review_store.bind_ledger_mirror(self._ledger_path)
        register_backend(self._ledger_path, self.workflow_review_store)
        self._bindings = self.workflow_review_store.read_bindings()
        self._bindings_baseline = deepcopy(self._bindings)
        self._mirror_bindings()

    def _assert_review_cutover_prepared(self) -> None:
        runtime = Path(self.runtime)
        legacy_events = self.workflow_review_store._read_legacy_events(runtime / "review_ledger.jsonl")
        legacy_bindings = self.workflow_review_store._read_legacy_bindings(
            runtime / "publish_authorizations.json"
        )
        db_events = self.workflow_review_store.read_events()
        db_bindings = self.workflow_review_store.read_bindings()
        if legacy_events and db_events != legacy_events:
            raise ConsoleError("workflow_review_cutover_not_prepared")
        if legacy_bindings and db_bindings != legacy_bindings:
            raise ConsoleError("workflow_review_cutover_not_prepared")

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
        prior_bindings = deepcopy(self.workflow_review_store.read_bindings())
        prior_envelope: dict[str, Any] | None = None
        prior_objects: list[dict[str, Any]] | None = None
        if sid:
            with suppress(ConsoleError):
                prior_envelope = deepcopy(self._envelope(sid))
                prior_objects = deepcopy(self._load_objects(sid, remember=False))
        try:
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
        prior_bindings = deepcopy(self.workflow_review_store.read_bindings())
        prior_envelope = deepcopy(self._envelope(snapshot_id))
        prior_objects = deepcopy(self._load_objects(snapshot_id, remember=False))
        try:
            with buffer_events(self._ledger_path):
                with super()._atomic_snapshot_mutation(snapshot_id):
                    yield
        except Exception:
            self._restore_review_state(
                bindings=prior_bindings,
                snapshot_id=snapshot_id,
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
