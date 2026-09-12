"""Durable-first console publication boundary.

For Azure publication the PostgreSQL canonical store is the authority. Publication
is committed there first in one transaction. Only after that succeeds are the
console envelope, release manifest, local ledger and Product API JSONL projection
updated as rebuildable local copies.
"""
from __future__ import annotations

import json
import uuid
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError, PostgresCanonicalPublicationStore
from src.operations_console_v1 import PUBLICATION_PROTOCOL_VERSION, RELEASE_MANIFEST_DIRNAME, ConsoleError, _atomic_replace_bytes, _atomic_write
from src.published_projection_v1 import atomic_replace_projection
from src.retrieval_projection_v2 import build_projection
from src.review_closure_v1 import ReviewClosureConsole
from src.review_ledger import append_event


class DurablePublicationConsole(ReviewClosureConsole):
    """Review console whose successful publication is PostgreSQL-first."""

    def __init__(self, *args: Any, canonical_publication_store: PostgresCanonicalPublicationStore | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.canonical_publication_store = canonical_publication_store

    @staticmethod
    def _read_optional(path: Path) -> bytes | None:
        return path.read_bytes() if path.exists() else None

    @staticmethod
    def _restore_optional(path: Path, prior: bytes | None) -> None:
        if prior is None:
            with suppress(OSError): path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_replace_bytes(path, prior)

    @staticmethod
    def _manifest_from_release(release: dict[str, Any]) -> dict[str, Any]:
        return {"release_id": str(release["release_id"]), "release_version": str(release["release_version"]), "release_owner": str(release["release_owner"]), "published_at": str(release["published_at"]), "protocol_version": PUBLICATION_PROTOCOL_VERSION, "snapshot_id": str(release["snapshot_id"]), "source_sha256": str(release["source_sha256"]), "immutable_storage_locator": str(release["source_locator"]), "objects": deepcopy(release["objects"])}

    def _projection_from_authority(self) -> list[dict[str, Any]]:
        store = self.canonical_publication_store
        if store is None: raise ConsoleError("durable_publication_store_required")
        try: authority_rows = store.active_publication_rows()
        except CanonicalPublicationStoreError as exc: raise ConsoleError("durable_publication_projection_read_failed", str(exc)) from exc
        projected, blocked = build_projection([{"knowledge_object": deepcopy(row["knowledge_object"]), "publication": deepcopy(row["publication"])} for row in authority_rows])
        if blocked: raise ConsoleError("durable_publication_projection_invalid", json.dumps(blocked, sort_keys=True))
        if len(projected) != len(authority_rows): raise ConsoleError("durable_publication_projection_incomplete")
        for projected_row, authority_row in zip(projected, authority_rows, strict=True): projected_row.setdefault("metadata", {})["snapshot_id"] = str(authority_row["snapshot_id"])
        return projected

    def _local_ledger_has_release(self, release_id: str) -> bool:
        if not self._ledger_path.is_file(): return False
        for line in self._ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            try: event = json.loads(line)
            except json.JSONDecodeError: continue
            if event.get("event_type") == "release_published" and str((event.get("details") or {}).get("release_id") or "") == release_id: return True
        return False

    def _apply_local_release_copy(self, release: dict[str, Any], projection: list[dict[str, Any]]) -> None:
        snapshot_id, release_id = str(release["snapshot_id"]), str(release["release_id"])
        projection_path = self._published_projection_path(); manifest_path = self.runtime / RELEASE_MANIFEST_DIRNAME / f"{release_id}.json"
        prior_projection = self._read_optional(projection_path); prior_manifest = self._read_optional(manifest_path); prior_envelopes = self._read_optional(self._envelopes_path); prior_ledger = self._read_optional(self._ledger_path); prior_envelope_map = deepcopy(self._envelopes)
        try:
            _atomic_write(manifest_path, self._manifest_from_release(release)); atomic_replace_projection(projection_path, projection)
            current = deepcopy(self._envelope(snapshot_id)); current.update({"state":"published","published":True,"release_id":release_id,"release_version":str(release["release_version"]),"published_at":str(release["published_at"]),"published_by":str(release["release_owner"])}); self._envelopes[snapshot_id] = current; _atomic_write(self._envelopes_path, self._envelopes)
            if not self._local_ledger_has_release(release_id): append_event(self._ledger_path,event_type="release_published",object_id=snapshot_id,object_version=str(current.get("version") or ""),actor=str(release["release_owner"]),details={"release_id":release_id,"release_version":str(release["release_version"]),"published_object_ids":sorted(str(row["object_id"]) for row in release["objects"]),"source_sha256":str(release["source_sha256"]),"authority":"postgres"})
        except Exception:
            self._restore_optional(projection_path, prior_projection); self._restore_optional(manifest_path, prior_manifest); self._restore_optional(self._envelopes_path, prior_envelopes); self._restore_optional(self._ledger_path, prior_ledger); self._envelopes = prior_envelope_map; raise

    def _durable_release_for_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        store = self.canonical_publication_store
        if store is None: return None
        try: return store.release_for_snapshot(snapshot_id)
        except CanonicalPublicationStoreError as exc: raise ConsoleError("durable_publication_lookup_failed", str(exc)) from exc

    def _sync_snapshot_from_authority(self, snapshot_id: str) -> dict[str, Any] | None:
        release = self._durable_release_for_snapshot(snapshot_id)
        if release is None: return None
        self._apply_local_release_copy(release, self._projection_from_authority()); return release

    def _publish_locked(self, *, actor_id: str, snapshot_id: str) -> dict[str, Any]:
        store = self.canonical_publication_store
        if store is None: return super()._publish_locked(actor_id=actor_id, snapshot_id=snapshot_id)
        existing = self._sync_snapshot_from_authority(snapshot_id)
        if existing is not None: return {"status":"PASS","state":"published","snapshot_id":snapshot_id,"release_id":str(existing["release_id"]),"release_version":str(existing["release_version"]),"published_items":len(existing["objects"]),"g2":"PASS","cutover":True,"canonical_authority":"postgres","local_projection":"reconciled"}
        considered = self.consider_publish(actor_id=actor_id, snapshot_id=snapshot_id); envelope = self._envelope(snapshot_id)
        if not considered.get("publish_allowed"): return {"status":"BLOCKED","state":envelope["state"],"snapshot_id":snapshot_id,"blockers":considered.get("blockers") or ["object_tuple_required"],"g2":considered.get("g2","BLOCKED"),"cutover":False}
        account = self._require_role(actor_id, "publisher"); publish_ids = set(considered["publishable_object_ids"]); objects = [deepcopy(obj) for obj in self.snapshot_objects(snapshot_id) if obj.get("object_id") in publish_ids]
        # Preserve enough precision that two valid releases in one wall-clock second remain ordered.
        published_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        release_id = f"release-{uuid.uuid4().hex}"; release_version = f"{envelope['version']}-{release_id[-8:]}"
        _candidate_projection, blocked = build_projection([{"knowledge_object":deepcopy(obj),"publication":{"release_id":release_id,"release_version":release_version,"published_at":published_at}} for obj in objects])
        if blocked: return {"status":"BLOCKED","state":envelope["state"],"snapshot_id":snapshot_id,"blockers":["prepublication_projection_failed"],"projection_errors":blocked,"g2":"PASS","cutover":False}
        try: store.persist_published_release(snapshot_id=snapshot_id,source_sha256=str(envelope.get("sha256") or ""),source_locator=str(envelope.get("immutable_storage_locator") or ""),release_id=release_id,release_version=release_version,release_owner=str(account["username"]),published_at=published_at,objects=objects)
        except CanonicalPublicationStoreError as exc: raise ConsoleError("durable_publication_store_failed", str(exc)) from exc
        release = self._durable_release_for_snapshot(snapshot_id)
        if release is None or str(release.get("release_id") or "") != release_id: raise ConsoleError("durable_publication_commit_not_readable")
        try: projection = self._projection_from_authority(); self._apply_local_release_copy(release, projection)
        except Exception as exc: raise ConsoleError("durable_publication_local_copy_failed", str(exc)) from exc
        return {"status":"PASS","state":"published","snapshot_id":snapshot_id,"release_id":release_id,"release_version":release_version,"published_items":len(objects),"g2":"PASS","cutover":True,"canonical_authority":"postgres","local_projection":"derived"}

    def reconcile_durable_publications(self) -> dict[str, int]:
        store = self.canonical_publication_store
        if store is None: return {"checked":0,"reconciled":0}
        checked = 0; releases: list[dict[str, Any]] = []
        for envelope in self.list_envelopes():
            checked += 1; release = self._durable_release_for_snapshot(str(envelope["snapshot_id"]));
            if release is not None: releases.append(release)
        if not releases:
            atomic_replace_projection(self._published_projection_path(), self._projection_from_authority()); return {"checked":checked,"reconciled":0}
        projection = self._projection_from_authority(); releases.sort(key=lambda row: str(row.get("published_at") or ""))
        for release in releases: self._apply_local_release_copy(release, projection)
        return {"checked":checked,"reconciled":len(releases)}
