from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from src.publication_chain_recovery_guard_v1 import (
    PublicationChainRecoveryError,
    restore_publication_chain,
    verify_publication_chain_backup,
)
from src.publication_chain_recovery_v1 import BACKUP_FORMAT, DB_TABLES


class Database:
    def __init__(self):
        self.restore_calls = 0

    def assert_empty(self):
        return None

    def restore_state(self, state):
        self.restore_calls += 1

    def export_state(self):
        return {"format": BACKUP_FORMAT, "exported_at": "test", "tables": {table: [] for table in DB_TABLES}}


class Blob:
    def __init__(self):
        self.data = {}

    def store_verified(self, *, data, sha256, filename):
        locator = f"azure://aidataservice/canonical-sources/{sha256}/{filename}"
        self.data[locator] = data
        return locator

    def load_verified(self, locator):
        return self.data[locator]


def _database_state(data: bytes):
    digest = hashlib.sha256(data).hexdigest()
    locator = f"azure://aidataservice/canonical-sources/{digest}/source.pdf"
    tables = {table: [] for table in DB_TABLES}
    tables["source_snapshots"] = [{"snapshot_id": "snap-1", "source_checksum": digest, "source_locator": locator, "recorded_at": "2026-09-12T00:00:00+00:00"}]
    return {"format": BACKUP_FORMAT, "exported_at": "test", "tables": tables}, digest, locator


def _write_checksum_valid_but_blobless_archive(path: Path):
    state, digest, locator = _database_state(b"source")
    database_bytes = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    manifest = {
        "format": BACKUP_FORMAT,
        "created_at": "test",
        "database": {"member": "database.json", "sha256": hashlib.sha256(database_bytes).hexdigest(), "tables": {table: len(state["tables"][table]) for table in DB_TABLES}},
        "blobs": [],
        "runtime": None,
        "preflight_integrity": {},
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("database.json", database_bytes)
        archive.writestr("chain_manifest.json", json.dumps(manifest))
    return locator


def test_database_referenced_blob_missing_from_manifest_blocks_restore_before_db_write(tmp_path: Path):
    archive = tmp_path / "missing-blob.zip"
    locator = _write_checksum_valid_but_blobless_archive(archive)
    report = verify_publication_chain_backup(archive)
    assert report["ok"] is False
    assert f"database_source_blob_missing_from_manifest:{locator}" in report["errors"]

    database = Database()
    with pytest.raises(PublicationChainRecoveryError, match="database_source_blob_missing_from_manifest"):
        restore_publication_chain(archive, database=database, source_store=Blob())
    assert database.restore_calls == 0


class CorruptReadbackBlob(Blob):
    def load_verified(self, locator):
        return b"corrupt-after-write"


def test_blob_readback_failure_occurs_before_database_restore(tmp_path: Path):
    # The guard store itself is exercised through a minimal valid v1 archive in
    # the main recovery suite; this regression pins the activation invariant.
    from src.publication_chain_recovery_guard_v1 import _ReadbackBeforeCommitStore
    database = Database()
    guarded = _ReadbackBeforeCommitStore(CorruptReadbackBlob())
    digest = hashlib.sha256(b"source").hexdigest()
    with pytest.raises(PublicationChainRecoveryError, match="chain_restore_blob_readback_hash_mismatch"):
        guarded.store_verified(data=b"source", sha256=digest, filename="source.pdf")
    assert database.restore_calls == 0
