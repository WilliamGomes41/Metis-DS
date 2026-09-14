"""Fail-closed recovery of a pre-cutover canonical release manifest.

The release manifest is only recovery evidence.  The exact object payloads and
review authorizations are re-read from the PostgreSQL workflow authority, and
the immutable source is read back from Blob storage, before the existing
transactional canonical publication store is allowed to write anything.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Protocol

from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.g2_source_store import G2SourceStoreError, parse_g2_locator
from src.integrity_kernel import compute_canonical_object_hash, sha256_bytes
from src.publish_authorization_v1 import still_matches


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class LegacyCanonicalRecoveryError(RuntimeError):
    """A legacy release cannot be proven safe to recover."""


class WorkflowDocumentAuthority(Protocol):
    def get_envelope(self, snapshot_id: str) -> dict[str, Any] | None: ...
    def list_document_objects(self, snapshot_id: str) -> list[dict[str, Any]]: ...


class WorkflowReviewAuthority(Protocol):
    def read_bindings(self) -> dict[str, list[dict[str, Any]]]: ...


class ImmutableSourceAuthority(Protocol):
    def load_verified(self, locator: str) -> bytes: ...


@dataclass(frozen=True)
class LegacyCanonicalCandidate:
    release_id: str
    release_version: str
    release_owner: str
    published_at: str
    snapshot_id: str
    source_sha256: str
    source_locator: str
    objects: tuple[dict[str, Any], ...]

    def summary(self, *, status: str) -> dict[str, Any]:
        return {
            "ok": True,
            "status": status,
            "release_id": self.release_id,
            "release_version": self.release_version,
            "release_owner": self.release_owner,
            "published_at": self.published_at,
            "snapshot_id": self.snapshot_id,
            "source_sha256": self.source_sha256,
            "source_locator": self.source_locator,
            "objects": [
                {
                    "object_id": str(obj["object_id"]),
                    "object_version": str(obj["object_version"]),
                    "content_hash": str((obj.get("provenance") or {})["content_hash"]),
                }
                for obj in self.objects
            ],
            "mutation": "none" if status == "PLANNED" else "canonical_publication_transaction",
        }


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise LegacyCanonicalRecoveryError(f"legacy_release_manifest_field_missing:{field}")
    return value


def _load_manifest(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != ".json":
        raise LegacyCanonicalRecoveryError("legacy_release_manifest_missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyCanonicalRecoveryError("legacy_release_manifest_invalid_json") from exc
    if not isinstance(payload, dict):
        raise LegacyCanonicalRecoveryError("legacy_release_manifest_invalid")
    release_id = _required_text(payload, "release_id")
    if path.name != f"{release_id}.json":
        raise LegacyCanonicalRecoveryError("legacy_release_manifest_filename_mismatch")
    return payload


def prepare_legacy_canonical_candidate(
    manifest_path: Path,
    *,
    documents: WorkflowDocumentAuthority,
    reviews: WorkflowReviewAuthority,
    source_store: ImmutableSourceAuthority,
) -> LegacyCanonicalCandidate:
    """Prove the complete immutable release tuple without mutating authority."""
    manifest = _load_manifest(manifest_path)
    release_id = _required_text(manifest, "release_id")
    release_version = _required_text(manifest, "release_version")
    release_owner = _required_text(manifest, "release_owner")
    published_at = _required_text(manifest, "published_at")
    snapshot_id = _required_text(manifest, "snapshot_id")
    source_sha256 = _required_text(manifest, "source_sha256").lower()
    source_locator = _required_text(manifest, "immutable_storage_locator")
    try:
        datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LegacyCanonicalRecoveryError("legacy_release_published_at_invalid") from exc
    if SHA256_RE.fullmatch(source_sha256) is None:
        raise LegacyCanonicalRecoveryError("legacy_release_source_sha256_invalid")
    parsed_locator = parse_g2_locator(source_locator)
    if parsed_locator is None or parsed_locator["sha256"] != source_sha256:
        raise LegacyCanonicalRecoveryError("legacy_release_source_locator_invalid")

    envelope = documents.get_envelope(snapshot_id)
    if envelope is None:
        raise LegacyCanonicalRecoveryError("legacy_release_snapshot_missing")
    if str(envelope.get("snapshot_id") or "") != snapshot_id:
        raise LegacyCanonicalRecoveryError("legacy_release_snapshot_identity_mismatch")
    if str(envelope.get("sha256") or "").lower() != source_sha256:
        raise LegacyCanonicalRecoveryError("legacy_release_envelope_sha256_mismatch")
    if str(envelope.get("immutable_storage_locator") or "") != source_locator:
        raise LegacyCanonicalRecoveryError("legacy_release_envelope_locator_mismatch")

    try:
        source_bytes = source_store.load_verified(source_locator)
    except (G2SourceStoreError, OSError, ValueError, KeyError) as exc:
        raise LegacyCanonicalRecoveryError("legacy_release_source_readback_failed") from exc
    if sha256_bytes(source_bytes) != source_sha256:
        raise LegacyCanonicalRecoveryError("legacy_release_source_readback_mismatch")

    manifest_objects = manifest.get("objects")
    if not isinstance(manifest_objects, list) or not manifest_objects:
        raise LegacyCanonicalRecoveryError("legacy_release_objects_missing")
    workflow_objects = {
        (str(obj.get("object_id") or ""), str(obj.get("object_version") or "")): obj
        for obj in documents.list_document_objects(snapshot_id)
    }
    bindings = reviews.read_bindings().get(snapshot_id, [])
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in manifest_objects:
        if not isinstance(item, dict):
            raise LegacyCanonicalRecoveryError("legacy_release_object_invalid")
        object_id = _required_text(item, "object_id")
        object_version = _required_text(item, "object_version")
        key = (object_id, object_version)
        if key in seen:
            raise LegacyCanonicalRecoveryError("legacy_release_object_duplicate")
        seen.add(key)
        obj = workflow_objects.get(key)
        if obj is None:
            raise LegacyCanonicalRecoveryError(
                f"legacy_release_workflow_object_missing:{object_id}@{object_version}"
            )
        actual_hash = compute_canonical_object_hash(obj)
        manifest_canonical_hash = _required_text(item, "canonical_object_hash").lower()
        manifest_content_hash = _required_text(item, "content_hash").lower()
        provenance = obj.get("provenance") or {}
        if not (
            actual_hash == manifest_canonical_hash == manifest_content_hash
            and str(provenance.get("canonical_object_hash") or "").lower() == actual_hash
            and str(provenance.get("content_hash") or "").lower() == actual_hash
        ):
            raise LegacyCanonicalRecoveryError(
                f"legacy_release_object_hash_mismatch:{object_id}@{object_version}"
            )
        confirmed_type = _required_text(item, "confirmed_object_type")
        if str(obj.get("confirmed_object_type") or "") != confirmed_type:
            raise LegacyCanonicalRecoveryError(
                f"legacy_release_object_type_mismatch:{object_id}@{object_version}"
            )
        if str((obj.get("source") or {}).get("source_checksum") or "").lower() != source_sha256:
            raise LegacyCanonicalRecoveryError(
                f"legacy_release_object_source_mismatch:{object_id}@{object_version}"
            )
        authorized = any(
            binding.get("decision") == "approve" and still_matches(binding, obj)
            for binding in bindings
        )
        if not authorized:
            raise LegacyCanonicalRecoveryError(
                f"legacy_release_object_authorization_missing:{object_id}@{object_version}"
            )
        selected.append(obj)

    return LegacyCanonicalCandidate(
        release_id=release_id,
        release_version=release_version,
        release_owner=release_owner,
        published_at=published_at,
        snapshot_id=snapshot_id,
        source_sha256=source_sha256,
        source_locator=source_locator,
        objects=tuple(selected),
    )


def recover_legacy_canonical_release(
    candidate: LegacyCanonicalCandidate,
    *,
    canonical_store: PostgresCanonicalPublicationStore,
) -> dict[str, Any]:
    """Persist the proven release through the normal atomic publication path."""
    canonical_store.persist_published_release(
        snapshot_id=candidate.snapshot_id,
        source_sha256=candidate.source_sha256,
        source_locator=candidate.source_locator,
        release_id=candidate.release_id,
        release_version=candidate.release_version,
        release_owner=candidate.release_owner,
        published_at=candidate.published_at,
        objects=list(candidate.objects),
    )
    return candidate.summary(status="PASS")
