"""Strict recovery guard for publication-chain restore.

This module hardens the v1 archive implementation at the activation boundary:
- database source_snapshots and manifest Blob entries must be an exact set;
- each manifest entry must reproduce the locator/hash/filename derived from DB;
- restored Blob bytes are read back and SHA-256 verified before PostgreSQL is
  allowed to restore publication authority.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Mapping

from src.integrity_kernel import sha256_bytes
from src.publication_chain_recovery_v1 import (
    PublicationChainRecoveryError,
    _blob_entries_from_state,
    restore_publication_chain as _restore_v1,
    verify_publication_chain_backup as _verify_v1,
)


def _identity(entry: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(entry.get("locator") or ""),
        str(entry.get("sha256") or "").lower(),
        str(entry.get("filename") or ""),
        str(entry.get("member") or ""),
    )


def verify_publication_chain_backup(archive: Path) -> dict[str, Any]:
    base = _verify_v1(archive)
    errors = list(base.get("errors") or [])
    if errors:
        return {"ok": False, "errors": errors}
    try:
        with zipfile.ZipFile(archive) as zipf:
            manifest = json.loads(zipf.read("chain_manifest.json").decode("utf-8"))
            database_state = json.loads(zipf.read("database.json").decode("utf-8"))
        expected = {_identity(entry) for entry in _blob_entries_from_state(database_state)}
        actual_entries = manifest.get("blobs")
        if not isinstance(actual_entries, list):
            errors.append("chain_manifest_blobs_invalid")
        else:
            actual = {_identity(entry) for entry in actual_entries if isinstance(entry, Mapping)}
            if len(actual) != len(actual_entries):
                errors.append("chain_manifest_blob_duplicate_or_invalid")
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            for locator, _sha, _filename, _member in missing:
                errors.append(f"database_source_blob_missing_from_manifest:{locator}")
            for locator, _sha, _filename, _member in extra:
                errors.append(f"manifest_blob_not_referenced_by_database:{locator}")
    except PublicationChainRecoveryError as exc:
        errors.append(str(exc))
    except Exception as exc:
        errors.append(f"chain_blob_set_verification_failed:{type(exc).__name__}")
    return {"ok": not errors, "errors": errors}


class _ReadbackBeforeCommitStore:
    def __init__(self, source_store: Any) -> None:
        self.source_store = source_store

    def load_verified(self, locator: str) -> bytes:
        return self.source_store.load_verified(locator)

    def store_verified(self, *, data: bytes, sha256: str, filename: str) -> str:
        locator = self.source_store.store_verified(data=data, sha256=sha256, filename=filename)
        try:
            restored = self.source_store.load_verified(locator)
        except Exception as exc:
            raise PublicationChainRecoveryError("chain_restore_blob_readback_failed") from exc
        if sha256_bytes(restored) != sha256.lower():
            raise PublicationChainRecoveryError("chain_restore_blob_readback_hash_mismatch")
        return locator


def restore_publication_chain(
    archive: Path,
    *,
    database: Any,
    source_store: Any,
    runtime_dest: Path | None = None,
) -> dict[str, Any]:
    verification = verify_publication_chain_backup(archive)
    if not verification["ok"]:
        raise PublicationChainRecoveryError(
            "chain_restore_backup_invalid:" + ";".join(verification["errors"])
        )
    return _restore_v1(
        archive,
        database=database,
        source_store=_ReadbackBeforeCommitStore(source_store),
        runtime_dest=runtime_dest,
    )
