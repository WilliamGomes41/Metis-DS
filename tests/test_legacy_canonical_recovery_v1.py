"""Fail-closed proof for pre-cutover canonical release recovery.

# release-control-evidence: opslag
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.integrity_kernel import compute_canonical_object_hash
from src.canonical_publication_postgres_v1 import (
    PostgresCanonicalConfig,
    PostgresCanonicalPublicationStore,
)
from src.legacy_canonical_recovery_v1 import (
    LegacyCanonicalRecoveryError,
    prepare_legacy_canonical_candidate,
    recover_legacy_canonical_release,
)


def _object(checksum: str) -> dict:
    obj = {
        "object_id": "object-1",
        "document_id": "document-1",
        "object_version": "1.0.1",
        "parent_object_id": None,
        "object_type": "recommendation",
        "source": {
            "title": "Source",
            "source_url": "https://example.test/source",
            "source_checksum": checksum,
        },
        "structure": {"heading": "Advice", "section_path": ["Advice"]},
        "content": {"clean_text": "Use the reviewed intervention.", "topic": ["test"]},
        "logic": {},
        "relations": [],
        "decision_graph": {},
        "risk": {"risk_level": "low"},
        "uncertainty": {"has_uncertainty": False},
        "provenance": {"source_fragments": []},
        "governance": {"validation_status": "approved"},
        "confirmed_object_type": "recommendation",
    }
    digest = compute_canonical_object_hash(obj)
    obj["provenance"].update({"canonical_object_hash": digest, "content_hash": digest})
    return obj


class Documents:
    def __init__(self, envelope: dict, objects: list[dict]) -> None:
        self.envelope = envelope
        self.objects = objects

    def get_envelope(self, snapshot_id: str) -> dict | None:
        return dict(self.envelope) if snapshot_id == self.envelope["snapshot_id"] else None

    def list_document_objects(self, snapshot_id: str) -> list[dict]:
        assert snapshot_id == self.envelope["snapshot_id"]
        return self.objects


class Reviews:
    def __init__(self, snapshot_id: str, obj: dict) -> None:
        self.snapshot_id = snapshot_id
        self.obj = obj

    def read_bindings(self) -> dict[str, list[dict]]:
        return {
            self.snapshot_id: [
                {
                    "object_id": self.obj["object_id"],
                    "object_version": self.obj["object_version"],
                    "canonical_object_hash": self.obj["provenance"]["canonical_object_hash"],
                    "confirmed_object_type": self.obj["confirmed_object_type"],
                    "reviewer": "Reviewer",
                    "reviewer_id": "reviewer-1",
                    "decision": "approve",
                    "valid": True,
                }
            ]
        }


class Blobs:
    def __init__(self, locator: str, data: bytes) -> None:
        self.locator = locator
        self.data = data

    def load_verified(self, locator: str) -> bytes:
        assert locator == self.locator
        return self.data


class Canonical:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def persist_published_release(self, **kwargs) -> None:
        self.calls.append(kwargs)


class HistoricalConnection:
    def __init__(self, *, checksum: str, locator: str, content_hash: str) -> None:
        self.checksum = checksum
        self.locator = locator
        self.content_hash = content_hash
        self.queries: list[tuple[str, tuple | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def transaction(self):
        return self

    def execute(self, query: str, params: tuple | None = None):
        self.queries.append((query, params))
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT source_checksum, source_locator"):
            return Row({"source_checksum": self.checksum, "source_locator": self.locator})
        if normalized.startswith("SELECT content_hash FROM canonical_object_versions"):
            return Row({"content_hash": self.content_hash})
        if normalized.startswith("SELECT snapshot_id FROM canonical_object_sources"):
            return Row({"snapshot_id": "snapshot-1"})
        if normalized.startswith("SELECT release_version,release_owner,status,published_at"):
            return Row(None)
        if normalized.startswith("SELECT object_version,release_id,state,published_at"):
            return Row(
                {
                    "object_version": "2.0.0",
                    "release_id": "release-newer",
                    "state": "active",
                    "published_at": "2026-09-10T17:28:39+00:00",
                }
            )
        if normalized.startswith("SELECT 1 FROM audit_events"):
            return Row(None)
        return Row(None)


class Row:
    def __init__(self, row: dict | None) -> None:
        self.row = row

    def fetchone(self) -> dict | None:
        return self.row

    def fetchall(self) -> list[dict]:
        return [] if self.row is None else [self.row]


def _fixture(tmp_path: Path) -> tuple[Path, Documents, Reviews, Blobs, dict]:
    source = b"immutable source bytes"
    checksum = hashlib.sha256(source).hexdigest()
    locator = f"azure://aidataservice/canonical-sources/{checksum}/source.pdf"
    obj = _object(checksum)
    snapshot_id = "snapshot-1"
    manifest = {
        "release_id": "release-legacy-1",
        "release_version": "1.0.1-legacy",
        "release_owner": "publisher",
        "published_at": "2026-09-09T17:28:39+00:00",
        "snapshot_id": snapshot_id,
        "source_sha256": checksum,
        "immutable_storage_locator": locator,
        "objects": [
            {
                "object_id": obj["object_id"],
                "object_version": obj["object_version"],
                "canonical_object_hash": obj["provenance"]["canonical_object_hash"],
                "content_hash": obj["provenance"]["content_hash"],
                "confirmed_object_type": obj["confirmed_object_type"],
            }
        ],
    }
    path = tmp_path / "release-legacy-1.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    envelope = {
        "snapshot_id": snapshot_id,
        "sha256": checksum,
        "immutable_storage_locator": locator,
    }
    return path, Documents(envelope, [obj]), Reviews(snapshot_id, obj), Blobs(locator, source), manifest


def test_prepare_proves_manifest_workflow_authorization_and_blob_without_mutation(tmp_path: Path) -> None:
    path, documents, reviews, blobs, manifest = _fixture(tmp_path)
    candidate = prepare_legacy_canonical_candidate(
        path, documents=documents, reviews=reviews, source_store=blobs
    )
    summary = candidate.summary(status="PLANNED")
    assert summary["mutation"] == "none"
    assert summary["release_id"] == manifest["release_id"]
    assert summary["objects"] == [
        {
            "object_id": "object-1",
            "object_version": "1.0.1",
            "content_hash": manifest["objects"][0]["content_hash"],
        }
    ]


def test_prepare_fails_closed_when_manifest_hash_is_tampered(tmp_path: Path) -> None:
    path, documents, reviews, blobs, manifest = _fixture(tmp_path)
    manifest["objects"][0]["content_hash"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(LegacyCanonicalRecoveryError, match="legacy_release_object_hash_mismatch"):
        prepare_legacy_canonical_candidate(
            path, documents=documents, reviews=reviews, source_store=blobs
        )


def test_prepare_fails_closed_without_exact_publish_authorization(tmp_path: Path) -> None:
    path, documents, reviews, blobs, _manifest = _fixture(tmp_path)
    reviews.read_bindings = lambda: {}  # type: ignore[method-assign]
    with pytest.raises(LegacyCanonicalRecoveryError, match="legacy_release_object_authorization_missing"):
        prepare_legacy_canonical_candidate(
            path, documents=documents, reviews=reviews, source_store=blobs
        )


def test_execute_delegates_exact_release_to_transactional_canonical_store(tmp_path: Path) -> None:
    path, documents, reviews, blobs, manifest = _fixture(tmp_path)
    candidate = prepare_legacy_canonical_candidate(
        path, documents=documents, reviews=reviews, source_store=blobs
    )
    canonical = Canonical()
    result = recover_legacy_canonical_release(candidate, canonical_store=canonical)  # type: ignore[arg-type]
    assert result["status"] == "PASS"
    assert result["mutation"] == "canonical_publication_transaction"
    assert len(canonical.calls) == 1
    assert canonical.calls[0]["release_id"] == manifest["release_id"]
    assert canonical.calls[0]["objects"] == documents.objects
    assert canonical.calls[0]["preserve_newer_registry"] is True


def test_historical_recovery_persists_release_without_rewinding_newer_registry(tmp_path: Path) -> None:
    path, documents, reviews, blobs, manifest = _fixture(tmp_path)
    candidate = prepare_legacy_canonical_candidate(
        path, documents=documents, reviews=reviews, source_store=blobs
    )
    connection = HistoricalConnection(
        checksum=candidate.source_sha256,
        locator=candidate.source_locator,
        content_hash=manifest["objects"][0]["content_hash"],
    )
    store = PostgresCanonicalPublicationStore(PostgresCanonicalConfig(dsn="test"))
    store._connect = lambda: connection  # type: ignore[method-assign]

    result = recover_legacy_canonical_release(candidate, canonical_store=store)

    assert result["status"] == "PASS"
    statements = [" ".join(query.split()) for query, _params in connection.queries]
    assert any(statement.startswith("INSERT INTO publication_releases") for statement in statements)
    assert any(statement.startswith("INSERT INTO publication_release_items") for statement in statements)
    assert not any(statement.startswith("INSERT INTO publication_registry") for statement in statements)
    audit_params = [params for query, params in connection.queries if query.startswith("INSERT INTO audit_events")]
    assert any('"registry_preserved": true' in str(params[-1]) for params in audit_params if params)
