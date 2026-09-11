from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from src.integrity_kernel import compute_canonical_object_hash
from src.publication_chain_recovery_v1 import (
    BACKUP_FORMAT,
    DB_TABLES,
    PublicationChainRecoveryError,
    backup_publication_chain,
    check_chain_integrity,
    restore_publication_chain,
    verify_publication_chain_backup,
)
from src.runtime_data_inventory_v1 import INVENTORY_CATEGORIES, inventory_runtime_data


class FakeDatabase:
    def __init__(self, state=None):
        self.state = copy.deepcopy(state or {"format": BACKUP_FORMAT, "exported_at": "test", "tables": {table: [] for table in DB_TABLES}})
        self.restore_calls = 0

    def export_state(self):
        return copy.deepcopy(self.state)

    def assert_empty(self):
        if any(self.state["tables"][table] for table in DB_TABLES):
            raise PublicationChainRecoveryError("database_restore_target_not_empty")

    def restore_state(self, state):
        self.assert_empty()
        self.restore_calls += 1
        self.state = copy.deepcopy(dict(state))


class FakeBlobStore:
    def __init__(self, blobs=None, *, fail_writes=False):
        self.blobs = dict(blobs or {})
        self.fail_writes = fail_writes

    def load_verified(self, locator):
        data = self.blobs[locator]
        expected = locator.split("/")[-2]
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("hash mismatch")
        return data

    def store_verified(self, *, data, sha256, filename):
        if self.fail_writes:
            raise OSError("blob unavailable")
        locator = f"azure://aidataservice/canonical-sources/{sha256}/{filename}"
        if hashlib.sha256(data).hexdigest() != sha256:
            raise ValueError("hash mismatch")
        self.blobs[locator] = bytes(data)
        return locator


def _state(source_bytes=b"canonical source bytes"):
    checksum = hashlib.sha256(source_bytes).hexdigest()
    locator = f"azure://aidataservice/canonical-sources/{checksum}/guideline.pdf"
    obj = {
        "object_id": "obj-1",
        "document_id": "doc-1",
        "object_version": "1.0",
        "parent_object_id": None,
        "object_type": "recommendation",
        "source": {"title": "Guideline", "source_url": "https://example.test/guideline"},
        "structure": {"heading": "Advice", "section_path": ["Advice"]},
        "content": {"clean_text": "Do the reviewed action.", "topic": ["test"]},
        "logic": {},
        "relations": [],
        "decision_graph": {},
        "risk": {"risk_level": "low"},
        "uncertainty": {"has_uncertainty": False},
        "provenance": {"source_fragments": []},
        "governance": {"validation_status": "approved"},
        "confirmed_object_type": "recommendation",
    }
    content_hash = compute_canonical_object_hash(obj)
    state = {
        "format": BACKUP_FORMAT,
        "exported_at": "2026-09-11T20:00:00+00:00",
        "tables": {
            "canonical_object_versions": [{
                "object_id": "obj-1", "object_version": "1.0", "document_id": "doc-1",
                "object_type": "recommendation", "validation_status": "approved",
                "source_checksum": checksum, "content_hash": content_hash,
                "canonical_json": obj, "imported_at": "2026-09-11T20:00:00+00:00",
            }],
            "source_snapshots": [{
                "snapshot_id": "snap-1", "source_checksum": checksum,
                "source_locator": locator, "recorded_at": "2026-09-11T20:00:00+00:00",
            }],
            "canonical_object_sources": [{
                "object_id": "obj-1", "object_version": "1.0", "snapshot_id": "snap-1",
            }],
            "publication_releases": [{
                "release_id": "release-1", "release_version": "1.0", "release_owner": "publisher-1",
                "status": "published", "notes": None, "created_at": "2026-09-11T20:00:00+00:00",
                "published_at": "2026-09-11T20:01:00+00:00", "withdrawn_at": None,
            }],
            "publication_release_items": [{
                "release_id": "release-1", "object_id": "obj-1", "object_version": "1.0",
                "action": "publish", "replaces_object_version": None, "content_hash": content_hash,
            }],
            "publication_registry": [{
                "object_id": "obj-1", "object_version": "1.0", "release_id": "release-1",
                "state": "active", "published_at": "2026-09-11T20:01:00+00:00",
                "unpublished_at": None, "unpublish_reason": None,
            }],
            "audit_events": [{
                "event_id": 1, "entity_type": "release", "entity_id": "release-1",
                "entity_version": "1.0", "event_type": "release_published", "actor": "publisher-1",
                "event_at": "2026-09-11T20:01:00+00:00",
                "details": {"snapshot_id": "snap-1", "source_sha256": checksum, "source_locator": locator},
            }],
        },
    }
    return state, locator, source_bytes, checksum


def _runtime(root: Path, *, checksum: str, locator: str):
    runtime = root / "output/runtime/operations-console"
    (runtime / "release_manifests").mkdir(parents=True)
    (runtime / "release_manifests/release-1.json").write_text(json.dumps({
        "release_id": "release-1", "release_version": "1.0", "snapshot_id": "snap-1",
        "source_sha256": checksum, "immutable_storage_locator": locator,
    }), encoding="utf-8")
    (runtime / "publish_authorizations.json").write_text("{}\n", encoding="utf-8")
    (runtime / "accounts.json").write_text("{}\n", encoding="utf-8")
    (runtime / "envelopes.json").write_text("{}\n", encoding="utf-8")


def test_full_chain_backup_restore_roundtrip_proves_blob_database_release_identity(tmp_path: Path):
    state, locator, source_bytes, checksum = _state()
    runtime_root = tmp_path / "source-runtime"
    _runtime(runtime_root, checksum=checksum, locator=locator)
    source_db = FakeDatabase(state)
    source_blob = FakeBlobStore({locator: source_bytes})

    pre = check_chain_integrity(state, source_store=source_blob, runtime_root=runtime_root)
    assert pre["ok"] is True
    assert pre["verified_blobs"] == 1
    assert pre["verified_release_manifests"] == 1

    archive = tmp_path / "chain-backup.zip"
    manifest = backup_publication_chain(
        archive, database=source_db, source_store=source_blob, runtime_root=runtime_root
    )
    assert manifest["database"]["tables"]["publication_releases"] == 1
    assert manifest["database"]["tables"]["publication_registry"] == 1
    assert len(manifest["blobs"]) == 1
    assert verify_publication_chain_backup(archive)["ok"] is True

    target_db = FakeDatabase()
    target_blob = FakeBlobStore()
    target_runtime = tmp_path / "restored-runtime"
    restored = restore_publication_chain(
        archive, database=target_db, source_store=target_blob, runtime_dest=target_runtime
    )
    assert restored["ok"] is True
    assert target_db.restore_calls == 1
    assert target_blob.load_verified(locator) == source_bytes
    assert restored["integrity"]["verified_blobs"] == 1
    assert restored["integrity"]["verified_release_manifests"] == 1
    assert target_db.state["tables"]["publication_registry"] == state["tables"]["publication_registry"]
    assert target_db.state["tables"]["publication_release_items"] == state["tables"]["publication_release_items"]

    inventory = inventory_runtime_data(target_runtime)
    names = {item["category"] for item in inventory["categories"]}
    assert names == set(INVENTORY_CATEGORIES)
    assert {"publication_authorizations", "release_manifests"}.issubset(names)


def test_restore_does_not_commit_database_if_blob_restore_fails(tmp_path: Path):
    state, locator, source_bytes, checksum = _state()
    runtime_root = tmp_path / "source-runtime"
    _runtime(runtime_root, checksum=checksum, locator=locator)
    archive = tmp_path / "chain-backup.zip"
    backup_publication_chain(
        archive,
        database=FakeDatabase(state),
        source_store=FakeBlobStore({locator: source_bytes}),
        runtime_root=runtime_root,
    )

    target_db = FakeDatabase()
    with pytest.raises(PublicationChainRecoveryError, match="chain_restore_blob_write_failed"):
        restore_publication_chain(
            archive,
            database=target_db,
            source_store=FakeBlobStore(fail_writes=True),
            runtime_dest=tmp_path / "restore",
        )
    assert target_db.restore_calls == 0
    assert all(not target_db.state["tables"][table] for table in DB_TABLES)


def test_integrity_detects_release_hash_and_blob_tampering(tmp_path: Path):
    state, locator, source_bytes, checksum = _state()
    bad = copy.deepcopy(state)
    bad["tables"]["publication_release_items"][0]["content_hash"] = "0" * 64
    report = check_chain_integrity(bad, source_store=FakeBlobStore({locator: source_bytes}))
    assert report["ok"] is False
    assert any("release_item_hash_mismatch" in err for err in report["errors"])

    corrupted_blob = FakeBlobStore({locator: b"tampered"})
    report = check_chain_integrity(state, source_store=corrupted_blob)
    assert report["ok"] is False
    assert any("blob_readback_failed" in err for err in report["errors"])


def test_archive_tampering_is_rejected_before_restore(tmp_path: Path):
    state, locator, source_bytes, checksum = _state()
    runtime_root = tmp_path / "source-runtime"
    _runtime(runtime_root, checksum=checksum, locator=locator)
    archive = tmp_path / "chain-backup.zip"
    backup_publication_chain(
        archive,
        database=FakeDatabase(state),
        source_store=FakeBlobStore({locator: source_bytes}),
        runtime_root=runtime_root,
    )

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(tampered, "w") as dst:
        for name in src.namelist():
            data = src.read(name)
            if name.startswith("blobs/"):
                data = b"tampered"
            dst.writestr(name, data)
    verification = verify_publication_chain_backup(tampered)
    assert verification["ok"] is False
    assert any("blob_backup_hash_mismatch" in err for err in verification["errors"])
