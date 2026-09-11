"""Console publication boundary backed by the durable canonical authority.

The existing console filesystem remains work state. When a durable publication
store is configured, a publication only returns PASS after the exact released
knowledge-object versions are committed there. A failed durable write restores
all local publication artefacts to their pre-publish bytes.
"""
from __future__ import annotations

from contextlib import suppress
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.canonical_publication_postgres_v1 import (
    CanonicalPublicationStoreError,
    PostgresCanonicalPublicationStore,
)
from src.operations_console_v1 import ConsoleError
from src.review_closure_v1 import ReviewClosureConsole


class DurablePublicationConsole(ReviewClosureConsole):
    """Review console whose published knowledge is durably mirrored as authority."""

    def __init__(
        self,
        *args: Any,
        canonical_publication_store: PostgresCanonicalPublicationStore | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.canonical_publication_store = canonical_publication_store

    @staticmethod
    def _read_optional(path: Path) -> bytes | None:
        return path.read_bytes() if path.exists() else None

    @staticmethod
    def _restore_optional(path: Path, prior: bytes | None) -> None:
        if prior is None:
            with suppress(OSError):
                path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(prior)

    def _publish_locked(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        store = self.canonical_publication_store
        if store is None:
            return super()._publish_locked(actor_id=actor_id, snapshot_id=snapshot_id)

        considered = self.consider_publish(actor_id=actor_id, snapshot_id=snapshot_id)
        if not considered.get("publish_allowed"):
            return super()._publish_locked(actor_id=actor_id, snapshot_id=snapshot_id)

        publish_ids = set(considered["publishable_object_ids"])
        objects = [
            deepcopy(obj)
            for obj in self.snapshot_objects(snapshot_id)
            if obj.get("object_id") in publish_ids
        ]
        source_envelope = deepcopy(self._envelope(snapshot_id))

        projection_path = self._published_projection_path()
        envelopes_path = self._envelopes_path
        ledger_path = self._ledger_path
        prior_projection = self._read_optional(projection_path)
        prior_envelopes = self._read_optional(envelopes_path)
        prior_ledger = self._read_optional(ledger_path)
        prior_manifest_names = {
            path.name for path in (self.runtime / "release_manifests").glob("*.json")
        }
        prior_envelope_map = deepcopy(self._envelopes)

        result = super()._publish_locked(actor_id=actor_id, snapshot_id=snapshot_id)
        if result.get("status") != "PASS":
            return result

        published = self._envelope(snapshot_id)
        try:
            store.persist_published_release(
                snapshot_id=snapshot_id,
                source_sha256=str(source_envelope.get("sha256") or ""),
                source_locator=str(source_envelope.get("immutable_storage_locator") or ""),
                release_id=str(result.get("release_id") or ""),
                release_version=str(result.get("release_version") or ""),
                release_owner=str(published.get("published_by") or ""),
                published_at=str(published.get("published_at") or ""),
                objects=objects,
            )
        except CanonicalPublicationStoreError as exc:
            self._restore_optional(projection_path, prior_projection)
            self._restore_optional(envelopes_path, prior_envelopes)
            self._restore_optional(ledger_path, prior_ledger)
            manifests = self.runtime / "release_manifests"
            for path in manifests.glob("*.json"):
                if path.name not in prior_manifest_names:
                    with suppress(OSError):
                        path.unlink()
            self._envelopes = prior_envelope_map
            raise ConsoleError("durable_publication_store_failed", str(exc)) from exc
        return {**result, "canonical_authority": "postgres"}

    def reconcile_durable_publications(self) -> dict[str, int]:
        """Idempotently close the process-crash window for already-published local state.

        The durable store remains decisive for external serving. If local state
        says published after a process interruption, startup reconstructs the
        exact release from its immutable local manifest and persists it before
        the console becomes available.
        """
        store = self.canonical_publication_store
        if store is None:
            return {"checked": 0, "reconciled": 0}

        checked = 0
        reconciled = 0
        for envelope in self.list_envelopes():
            if envelope.get("state") != "published":
                continue
            checked += 1
            release_id = str(envelope.get("release_id") or "")
            if not release_id:
                raise ConsoleError("published_release_manifest_missing")
            manifest_path = self.runtime / "release_manifests" / f"{release_id}.json"
            if not manifest_path.is_file():
                raise ConsoleError("published_release_manifest_missing")
            import json

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            object_ids = {str(row.get("object_id") or "") for row in manifest.get("objects") or []}
            if not object_ids:
                raise ConsoleError("published_release_manifest_invalid")
            objects = [
                deepcopy(obj)
                for obj in self.snapshot_objects(str(envelope["snapshot_id"]))
                if obj.get("object_id") in object_ids
            ]
            if {str(obj.get("object_id") or "") for obj in objects} != object_ids:
                raise ConsoleError("published_release_manifest_object_missing")
            store.persist_published_release(
                snapshot_id=str(envelope["snapshot_id"]),
                source_sha256=str(envelope.get("sha256") or ""),
                source_locator=str(envelope.get("immutable_storage_locator") or ""),
                release_id=release_id,
                release_version=str(envelope.get("release_version") or ""),
                release_owner=str(envelope.get("published_by") or ""),
                published_at=str(envelope.get("published_at") or ""),
                objects=objects,
            )
            reconciled += 1
        return {"checked": checked, "reconciled": reconciled}
