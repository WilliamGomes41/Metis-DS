"""Backup, restore and integrity proof for the published Metis chain.

The recoverable product state spans three authorities/surfaces:
- Azure Blob: immutable canonical source bytes;
- PostgreSQL: canonical object versions, source lineage, releases, registry and audit;
- console runtime: rebuildable/local workflow state, including release manifests.

A restore is deliberately ordered Blob -> runtime -> PostgreSQL. PostgreSQL is
committed last so no restored publication can become authoritative while its
source bytes or local recovery payload are still missing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from src.g2_source_store import G2SourceStoreError, parse_g2_locator
from src.integrity_kernel import compute_canonical_object_hash, sha256_bytes
from src.runtime_data_inventory_v1 import export_runtime_data, restore_runtime_data

BACKUP_FORMAT = "metis-publication-chain-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

DB_TABLES = (
    "canonical_object_versions",
    "source_snapshots",
    "canonical_object_sources",
    "publication_releases",
    "publication_release_items",
    "publication_registry",
    "audit_events",
)

_DB_COLUMNS: dict[str, tuple[str, ...]] = {
    "canonical_object_versions": (
        "object_id", "object_version", "document_id", "object_type",
        "validation_status", "source_checksum", "content_hash",
        "canonical_json", "imported_at",
    ),
    "source_snapshots": (
        "snapshot_id", "source_checksum", "source_locator", "recorded_at",
    ),
    "canonical_object_sources": ("object_id", "object_version", "snapshot_id"),
    "publication_releases": (
        "release_id", "release_version", "release_owner", "status", "notes",
        "created_at", "published_at", "withdrawn_at",
    ),
    "publication_release_items": (
        "release_id", "object_id", "object_version", "action",
        "replaces_object_version", "content_hash",
    ),
    "publication_registry": (
        "object_id", "object_version", "release_id", "state", "published_at",
        "unpublished_at", "unpublish_reason",
    ),
    "audit_events": (
        "event_id", "entity_type", "entity_id", "entity_version", "event_type",
        "actor", "event_at", "details",
    ),
}

_DB_ORDER_BY: dict[str, str] = {
    "canonical_object_versions": "object_id, object_version",
    "source_snapshots": "snapshot_id",
    "canonical_object_sources": "object_id, object_version",
    "publication_releases": "release_id",
    "publication_release_items": "release_id, object_id, object_version",
    "publication_registry": "object_id",
    "audit_events": "event_id",
}


class PublicationChainRecoveryError(RuntimeError):
    """Fail-closed chain backup/restore/integrity error."""


class DatabaseBackupAdapter(Protocol):
    def export_state(self) -> dict[str, Any]: ...
    def assert_empty(self) -> None: ...
    def restore_state(self, state: Mapping[str, Any]) -> None: ...


class ImmutableBackupSourceStore(Protocol):
    def load_verified(self, locator: str) -> bytes: ...
    def store_verified(self, *, data: bytes, sha256: str, filename: str) -> str: ...


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _backup_member(name: str) -> str:
    raw = str(name or "").replace("\\", "/")
    if not raw or raw.startswith("/") or raw.endswith("/"):
        raise PublicationChainRecoveryError("unsafe_chain_backup_member")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} or ".." in part for part in parts):
        raise PublicationChainRecoveryError("unsafe_chain_backup_member")
    return "/".join(parts)


def _table_rows(state: Mapping[str, Any], table: str) -> list[dict[str, Any]]:
    tables = state.get("tables")
    if not isinstance(tables, Mapping):
        raise PublicationChainRecoveryError("database_backup_tables_missing")
    rows = tables.get(table)
    if not isinstance(rows, list):
        raise PublicationChainRecoveryError(f"database_backup_table_missing:{table}")
    if any(not isinstance(row, dict) for row in rows):
        raise PublicationChainRecoveryError(f"database_backup_table_invalid:{table}")
    return [dict(row) for row in rows]


def _index_unique(rows: list[dict[str, Any]], key_fields: tuple[str, ...], label: str) -> tuple[dict[tuple[str, ...], dict[str, Any]], list[str]]:
    out: dict[tuple[str, ...], dict[str, Any]] = {}
    errors: list[str] = []
    for row in rows:
        key = tuple(str(row.get(field) or "") for field in key_fields)
        if not all(key):
            errors.append(f"{label}_key_missing:{'|'.join(key)}")
            continue
        if key in out:
            errors.append(f"{label}_duplicate:{'|'.join(key)}")
            continue
        out[key] = row
    return out, errors


class PostgresPublicationBackupAdapter:
    """Logical, transactionally consistent backup adapter for canonical PostgreSQL."""

    def __init__(self, canonical_store: Any) -> None:
        self.store = canonical_store

    def export_state(self) -> dict[str, Any]:
        try:
            self.store.verify_schema()
            with self.store._connect() as con:
                with con.transaction():
                    con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                    tables: dict[str, list[dict[str, Any]]] = {}
                    for table in DB_TABLES:
                        columns = ",".join(_DB_COLUMNS[table])
                        order_by = _DB_ORDER_BY[table]
                        rows = con.execute(
                            f"SELECT {columns} FROM {table} ORDER BY {order_by}"
                        ).fetchall()
                        tables[table] = [_json_safe(dict(row)) for row in rows]
        except PublicationChainRecoveryError:
            raise
        except Exception as exc:
            raise PublicationChainRecoveryError("database_backup_export_failed") from exc
        return {
            "format": BACKUP_FORMAT,
            "exported_at": _utc_now(),
            "tables": tables,
        }

    def assert_empty(self) -> None:
        try:
            self.store.verify_schema()
            with self.store._connect() as con:
                nonempty = []
                for table in DB_TABLES:
                    count = int(con.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
                    if count:
                        nonempty.append(f"{table}:{count}")
        except Exception as exc:
            if isinstance(exc, PublicationChainRecoveryError):
                raise
            raise PublicationChainRecoveryError("database_restore_preflight_failed") from exc
        if nonempty:
            raise PublicationChainRecoveryError("database_restore_target_not_empty:" + ",".join(nonempty))

    def restore_state(self, state: Mapping[str, Any]) -> None:
        _validate_database_backup_shape(state)
        self.assert_empty()
        rows = {table: _table_rows(state, table) for table in DB_TABLES}
        try:
            with self.store._connect() as con:
                with con.transaction():
                    for row in rows["canonical_object_versions"]:
                        con.execute(
                            """INSERT INTO canonical_object_versions(
                               object_id,object_version,document_id,object_type,validation_status,
                               source_checksum,content_hash,canonical_json,imported_at
                               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                            (
                                row["object_id"], row["object_version"], row["document_id"],
                                row["object_type"], row["validation_status"], row["source_checksum"],
                                row["content_hash"], json.dumps(row["canonical_json"], ensure_ascii=False, sort_keys=True),
                                row["imported_at"],
                            ),
                        )
                    for row in rows["source_snapshots"]:
                        con.execute(
                            "INSERT INTO source_snapshots(snapshot_id,source_checksum,source_locator,recorded_at) VALUES(%s,%s,%s,%s)",
                            (row["snapshot_id"], row["source_checksum"], row["source_locator"], row["recorded_at"]),
                        )
                    for row in rows["canonical_object_sources"]:
                        con.execute(
                            "INSERT INTO canonical_object_sources(object_id,object_version,snapshot_id) VALUES(%s,%s,%s)",
                            (row["object_id"], row["object_version"], row["snapshot_id"]),
                        )
                    for row in rows["publication_releases"]:
                        con.execute(
                            """INSERT INTO publication_releases(
                               release_id,release_version,release_owner,status,notes,created_at,published_at,withdrawn_at
                               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (
                                row["release_id"], row["release_version"], row["release_owner"], row["status"],
                                row.get("notes"), row["created_at"], row.get("published_at"), row.get("withdrawn_at"),
                            ),
                        )
                    for row in rows["publication_release_items"]:
                        con.execute(
                            """INSERT INTO publication_release_items(
                               release_id,object_id,object_version,action,replaces_object_version,content_hash
                               ) VALUES(%s,%s,%s,%s,%s,%s)""",
                            (
                                row["release_id"], row["object_id"], row["object_version"], row["action"],
                                row.get("replaces_object_version"), row["content_hash"],
                            ),
                        )
                    for row in rows["publication_registry"]:
                        con.execute(
                            """INSERT INTO publication_registry(
                               object_id,object_version,release_id,state,published_at,unpublished_at,unpublish_reason
                               ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                            (
                                row["object_id"], row["object_version"], row["release_id"], row["state"],
                                row["published_at"], row.get("unpublished_at"), row.get("unpublish_reason"),
                            ),
                        )
                    for row in rows["audit_events"]:
                        con.execute(
                            """INSERT INTO audit_events(
                               event_id,entity_type,entity_id,entity_version,event_type,actor,event_at,details
                               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                            (
                                row["event_id"], row["entity_type"], row["entity_id"], row.get("entity_version"),
                                row["event_type"], row["actor"], row["event_at"],
                                json.dumps(row.get("details") or {}, ensure_ascii=False, sort_keys=True),
                            ),
                        )
                    audit_rows = rows["audit_events"]
                    if audit_rows:
                        max_id = max(int(row["event_id"]) for row in audit_rows)
                        con.execute(
                            "SELECT setval(pg_get_serial_sequence('audit_events','event_id'), %s, true)",
                            (max_id,),
                        )
        except Exception as exc:
            raise PublicationChainRecoveryError("database_restore_failed") from exc


def _validate_database_backup_shape(state: Mapping[str, Any]) -> None:
    if str(state.get("format") or "") != BACKUP_FORMAT:
        raise PublicationChainRecoveryError("database_backup_format_invalid")
    tables = state.get("tables")
    if not isinstance(tables, Mapping):
        raise PublicationChainRecoveryError("database_backup_tables_missing")
    missing = [table for table in DB_TABLES if table not in tables]
    if missing:
        raise PublicationChainRecoveryError("database_backup_tables_missing:" + ",".join(missing))
    for table in DB_TABLES:
        _table_rows(state, table)


def check_chain_integrity(
    database_state: Mapping[str, Any],
    *,
    source_store: ImmutableBackupSourceStore | None = None,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    """Validate relational identity plus Blob read-back and release manifests."""
    errors: list[str] = []
    try:
        _validate_database_backup_shape(database_state)
    except PublicationChainRecoveryError as exc:
        return {"ok": False, "errors": [str(exc)], "verified_blobs": 0, "verified_release_manifests": 0}

    objects, err = _index_unique(_table_rows(database_state, "canonical_object_versions"), ("object_id", "object_version"), "canonical_object")
    errors.extend(err)
    snapshots, err = _index_unique(_table_rows(database_state, "source_snapshots"), ("snapshot_id",), "source_snapshot")
    errors.extend(err)
    links, err = _index_unique(_table_rows(database_state, "canonical_object_sources"), ("object_id", "object_version"), "source_link")
    errors.extend(err)
    releases, err = _index_unique(_table_rows(database_state, "publication_releases"), ("release_id",), "release")
    errors.extend(err)
    release_items, err = _index_unique(
        _table_rows(database_state, "publication_release_items"),
        ("release_id", "object_id", "object_version"),
        "release_item",
    )
    errors.extend(err)
    registry, err = _index_unique(_table_rows(database_state, "publication_registry"), ("object_id",), "registry")
    errors.extend(err)
    audits = _table_rows(database_state, "audit_events")

    for key, row in objects.items():
        content_hash = str(row.get("content_hash") or "").lower()
        canonical = row.get("canonical_json")
        if not isinstance(canonical, dict):
            errors.append(f"canonical_json_invalid:{key[0]}@{key[1]}")
            continue
        actual = compute_canonical_object_hash(canonical)
        if actual != content_hash:
            errors.append(f"canonical_content_hash_mismatch:{key[0]}@{key[1]}")
        source_checksum = str(row.get("source_checksum") or "").lower()
        if SHA256_RE.fullmatch(source_checksum) is None:
            errors.append(f"canonical_source_checksum_invalid:{key[0]}@{key[1]}")
        link = links.get(key)
        if link is None:
            errors.append(f"canonical_source_link_missing:{key[0]}@{key[1]}")
            continue
        snapshot = snapshots.get((str(link.get("snapshot_id") or ""),))
        if snapshot is None:
            errors.append(f"source_snapshot_missing:{key[0]}@{key[1]}")
            continue
        if str(snapshot.get("source_checksum") or "").lower() != source_checksum:
            errors.append(f"canonical_source_checksum_conflict:{key[0]}@{key[1]}")

    for key, row in release_items.items():
        release_id, object_id, object_version = key
        if (release_id,) not in releases:
            errors.append(f"release_item_release_missing:{release_id}")
        obj = objects.get((object_id, object_version))
        if obj is None:
            errors.append(f"release_item_object_missing:{object_id}@{object_version}")
        elif str(row.get("content_hash") or "") != str(obj.get("content_hash") or ""):
            errors.append(f"release_item_hash_mismatch:{release_id}:{object_id}@{object_version}")

    for (object_id,), row in registry.items():
        object_version = str(row.get("object_version") or "")
        release_id = str(row.get("release_id") or "")
        obj = objects.get((object_id, object_version))
        release = releases.get((release_id,))
        if obj is None:
            errors.append(f"registry_object_missing:{object_id}@{object_version}")
        if release is None:
            errors.append(f"registry_release_missing:{object_id}:{release_id}")
        elif row.get("state") == "active" and release.get("status") != "published":
            errors.append(f"registry_active_release_not_published:{object_id}:{release_id}")
        if (release_id, object_id, object_version) not in release_items:
            errors.append(f"registry_release_item_missing:{object_id}@{object_version}:{release_id}")

    release_audits: dict[str, dict[str, Any]] = {}
    for event in audits:
        if event.get("entity_type") != "release" or event.get("event_type") != "release_published":
            continue
        release_id = str(event.get("entity_id") or "")
        if release_id in release_audits:
            errors.append(f"release_published_audit_duplicate:{release_id}")
            continue
        release_audits[release_id] = event

    for (release_id,), release in releases.items():
        if release.get("status") != "published":
            continue
        event = release_audits.get(release_id)
        if event is None:
            errors.append(f"release_published_audit_missing:{release_id}")
            continue
        details = event.get("details") or {}
        snapshot_id = str(details.get("snapshot_id") or "")
        snapshot = snapshots.get((snapshot_id,))
        if snapshot is None:
            errors.append(f"release_source_snapshot_missing:{release_id}:{snapshot_id}")
            continue
        if str(details.get("source_sha256") or "").lower() != str(snapshot.get("source_checksum") or "").lower():
            errors.append(f"release_source_sha256_mismatch:{release_id}")
        if str(details.get("source_locator") or "") != str(snapshot.get("source_locator") or ""):
            errors.append(f"release_source_locator_mismatch:{release_id}")
        for (rid, object_id, object_version), _item in release_items.items():
            if rid != release_id:
                continue
            link = links.get((object_id, object_version))
            if link is None or str(link.get("snapshot_id") or "") != snapshot_id:
                errors.append(f"release_item_source_snapshot_mismatch:{release_id}:{object_id}@{object_version}")

    verified_blobs = 0
    if source_store is not None:
        for (snapshot_id,), snapshot in snapshots.items():
            checksum = str(snapshot.get("source_checksum") or "").lower()
            locator = str(snapshot.get("source_locator") or "")
            parsed = parse_g2_locator(locator)
            if parsed is None:
                errors.append(f"blob_locator_invalid:{snapshot_id}")
                continue
            if parsed["sha256"] != checksum:
                errors.append(f"blob_locator_hash_mismatch:{snapshot_id}")
                continue
            try:
                data = source_store.load_verified(locator)
            except (G2SourceStoreError, ValueError, KeyError) as exc:
                errors.append(f"blob_readback_failed:{snapshot_id}:{type(exc).__name__}")
                continue
            if sha256_bytes(data) != checksum:
                errors.append(f"blob_sha256_mismatch:{snapshot_id}")
                continue
            verified_blobs += 1

    verified_release_manifests = 0
    if runtime_root is not None:
        manifest_dir = Path(runtime_root) / "output" / "runtime" / "operations-console" / "release_manifests"
        if manifest_dir.is_dir():
            for path in sorted(manifest_dir.glob("*.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    errors.append(f"release_manifest_invalid_json:{path.name}")
                    continue
                release_id = str(payload.get("release_id") or "")
                release = releases.get((release_id,))
                event = release_audits.get(release_id)
                if release is None or event is None:
                    errors.append(f"release_manifest_orphan:{path.name}")
                    continue
                details = event.get("details") or {}
                expected = {
                    "release_version": str(release.get("release_version") or ""),
                    "snapshot_id": str(details.get("snapshot_id") or ""),
                    "source_sha256": str(details.get("source_sha256") or "").lower(),
                    "immutable_storage_locator": str(details.get("source_locator") or ""),
                }
                actual = {
                    "release_version": str(payload.get("release_version") or ""),
                    "snapshot_id": str(payload.get("snapshot_id") or ""),
                    "source_sha256": str(payload.get("source_sha256") or "").lower(),
                    "immutable_storage_locator": str(payload.get("immutable_storage_locator") or ""),
                }
                if actual != expected:
                    errors.append(f"release_manifest_mismatch:{release_id}")
                    continue
                verified_release_manifests += 1

    return {
        "ok": not errors,
        "errors": errors,
        "canonical_objects": len(objects),
        "source_snapshots": len(snapshots),
        "releases": len(releases),
        "registry_entries": len(registry),
        "verified_blobs": verified_blobs,
        "verified_release_manifests": verified_release_manifests,
    }


def _blob_entries_from_state(database_state: Mapping[str, Any]) -> list[dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for snapshot in _table_rows(database_state, "source_snapshots"):
        snapshot_id = str(snapshot.get("snapshot_id") or "")
        checksum = str(snapshot.get("source_checksum") or "").lower()
        locator = str(snapshot.get("source_locator") or "")
        parsed = parse_g2_locator(locator)
        if parsed is None or parsed["sha256"] != checksum:
            raise PublicationChainRecoveryError(f"source_snapshot_locator_invalid:{snapshot_id}")
        member = _backup_member(f"blobs/{checksum}/{parsed['filename']}")
        previous = entries.get(locator)
        current = {
            "locator": locator,
            "sha256": checksum,
            "filename": parsed["filename"],
            "member": member,
        }
        if previous is not None and previous != current:
            raise PublicationChainRecoveryError(f"source_snapshot_locator_conflict:{snapshot_id}")
        entries[locator] = current
    return sorted(entries.values(), key=lambda item: item["locator"])


def backup_publication_chain(
    archive: Path,
    *,
    database: DatabaseBackupAdapter,
    source_store: ImmutableBackupSourceStore,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    """Create one verifiable archive covering DB, Blob bytes and runtime releases."""
    database_state = database.export_state()
    preflight = check_chain_integrity(database_state, source_store=source_store, runtime_root=runtime_root)
    if not preflight["ok"]:
        raise PublicationChainRecoveryError("chain_backup_preflight_failed:" + ";".join(preflight["errors"]))

    db_bytes = _canonical_json_bytes(database_state)
    blob_entries = _blob_entries_from_state(database_state)
    blobs: dict[str, bytes] = {}
    for entry in blob_entries:
        try:
            data = source_store.load_verified(entry["locator"])
        except Exception as exc:
            raise PublicationChainRecoveryError("chain_backup_blob_read_failed") from exc
        if sha256_bytes(data) != entry["sha256"]:
            raise PublicationChainRecoveryError("chain_backup_blob_hash_mismatch")
        blobs[entry["member"]] = data
        entry["size"] = str(len(data))

    runtime_bytes: bytes | None = None
    runtime_manifest: dict[str, Any] | None = None
    if runtime_root is not None:
        with tempfile.TemporaryDirectory(prefix="metis-chain-backup-") as temp_dir:
            runtime_archive = Path(temp_dir) / "runtime.zip"
            runtime_manifest = export_runtime_data(Path(runtime_root), runtime_archive)
            runtime_bytes = runtime_archive.read_bytes()

    manifest: dict[str, Any] = {
        "format": BACKUP_FORMAT,
        "created_at": _utc_now(),
        "database": {
            "member": "database.json",
            "sha256": _sha256(db_bytes),
            "tables": {table: len(_table_rows(database_state, table)) for table in DB_TABLES},
        },
        "blobs": blob_entries,
        "runtime": None,
        "preflight_integrity": preflight,
    }
    if runtime_bytes is not None:
        manifest["runtime"] = {
            "member": "runtime/runtime_backup.zip",
            "sha256": _sha256(runtime_bytes),
            "manifest": runtime_manifest,
        }

    archive = Path(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    temp_archive = archive.with_name(f".{archive.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(temp_archive, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("database.json", db_bytes)
            for member, data in blobs.items():
                zipf.writestr(member, data)
            if runtime_bytes is not None:
                zipf.writestr("runtime/runtime_backup.zip", runtime_bytes)
            zipf.writestr("chain_manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        os.replace(temp_archive, archive)
    finally:
        if temp_archive.exists():
            temp_archive.unlink()

    verification = verify_publication_chain_backup(archive)
    if not verification["ok"]:
        raise PublicationChainRecoveryError("chain_backup_verification_failed:" + ";".join(verification["errors"]))
    return manifest


def verify_publication_chain_backup(archive: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(archive) as zipf:
            names = zipf.namelist()
            if len(names) != len(set(names)):
                errors.append("duplicate_archive_member")
            if "chain_manifest.json" not in names:
                return {"ok": False, "errors": ["chain_manifest_missing"]}
            if "database.json" not in names:
                return {"ok": False, "errors": ["database_backup_missing"]}
            for name in names:
                _backup_member(name)
            manifest = json.loads(zipf.read("chain_manifest.json").decode("utf-8"))
            if manifest.get("format") != BACKUP_FORMAT:
                errors.append("chain_manifest_format_invalid")
            db_bytes = zipf.read("database.json")
            if _sha256(db_bytes) != str((manifest.get("database") or {}).get("sha256") or ""):
                errors.append("database_backup_hash_mismatch")
            try:
                database_state = json.loads(db_bytes.decode("utf-8"))
                logical = check_chain_integrity(database_state)
                errors.extend(f"database:{item}" for item in logical["errors"])
            except Exception as exc:
                errors.append(f"database_backup_invalid:{type(exc).__name__}")

            expected_members = {"chain_manifest.json", "database.json"}
            for entry in manifest.get("blobs") or []:
                member = _backup_member(str(entry.get("member") or ""))
                expected_members.add(member)
                if member not in names:
                    errors.append(f"blob_backup_missing:{member}")
                    continue
                data = zipf.read(member)
                expected = str(entry.get("sha256") or "").lower()
                if _sha256(data) != expected:
                    errors.append(f"blob_backup_hash_mismatch:{member}")
                if str(len(data)) != str(entry.get("size") or ""):
                    errors.append(f"blob_backup_size_mismatch:{member}")

            runtime = manifest.get("runtime")
            if runtime:
                member = _backup_member(str(runtime.get("member") or ""))
                expected_members.add(member)
                if member not in names:
                    errors.append("runtime_backup_missing")
                elif _sha256(zipf.read(member)) != str(runtime.get("sha256") or ""):
                    errors.append("runtime_backup_hash_mismatch")

            unexpected = sorted(set(names) - expected_members)
            if unexpected:
                errors.append("unexpected_archive_members:" + ",".join(unexpected))
    except PublicationChainRecoveryError as exc:
        errors.append(str(exc))
    except Exception as exc:
        errors.append(f"chain_backup_unreadable:{type(exc).__name__}")
    return {"ok": not errors, "errors": errors}


def restore_publication_chain(
    archive: Path,
    *,
    database: DatabaseBackupAdapter,
    source_store: ImmutableBackupSourceStore,
    runtime_dest: Path | None = None,
) -> dict[str, Any]:
    """Restore a clean target and prove the recovered chain before success."""
    verification = verify_publication_chain_backup(archive)
    if not verification["ok"]:
        raise PublicationChainRecoveryError("chain_restore_backup_invalid:" + ";".join(verification["errors"]))

    database.assert_empty()
    if runtime_dest is not None:
        runtime_dest = Path(runtime_dest)
        if runtime_dest.exists() and any(runtime_dest.iterdir()):
            raise PublicationChainRecoveryError("runtime_restore_target_not_clean")

    with zipfile.ZipFile(archive) as zipf:
        manifest = json.loads(zipf.read("chain_manifest.json").decode("utf-8"))
        database_state = json.loads(zipf.read("database.json").decode("utf-8"))

        restored_blobs = 0
        for entry in manifest.get("blobs") or []:
            locator = str(entry["locator"])
            checksum = str(entry["sha256"]).lower()
            filename = str(entry["filename"])
            data = zipf.read(str(entry["member"]))
            if sha256_bytes(data) != checksum:
                raise PublicationChainRecoveryError("chain_restore_blob_hash_mismatch")
            try:
                restored_locator = source_store.store_verified(data=data, sha256=checksum, filename=filename)
            except Exception as exc:
                raise PublicationChainRecoveryError("chain_restore_blob_write_failed") from exc
            if restored_locator != locator:
                raise PublicationChainRecoveryError("chain_restore_blob_locator_changed")
            restored_blobs += 1

        restored_runtime_files = 0
        runtime = manifest.get("runtime")
        if runtime_dest is not None and runtime:
            runtime_bytes = zipf.read(str(runtime["member"]))
            with tempfile.TemporaryDirectory(prefix="metis-chain-restore-") as temp_dir:
                runtime_archive = Path(temp_dir) / "runtime.zip"
                runtime_archive.write_bytes(runtime_bytes)
                result = restore_runtime_data(runtime_archive, runtime_dest)
                restored_runtime_files = len(result["restored"])

    # Publication authority is committed only after source bytes and runtime
    # recovery data are in place.
    database.restore_state(database_state)
    restored_state = database.export_state()
    if _sha256(_canonical_json_bytes(restored_state.get("tables") or {})) != _sha256(
        _canonical_json_bytes(database_state.get("tables") or {})
    ):
        raise PublicationChainRecoveryError("database_restore_roundtrip_mismatch")

    integrity = check_chain_integrity(
        restored_state,
        source_store=source_store,
        runtime_root=runtime_dest,
    )
    if not integrity["ok"]:
        raise PublicationChainRecoveryError("chain_restore_integrity_failed:" + ";".join(integrity["errors"]))
    return {
        "ok": True,
        "restored_blobs": restored_blobs,
        "restored_runtime_files": restored_runtime_files,
        "integrity": integrity,
    }


def live_publication_chain_integrity(
    *,
    database: DatabaseBackupAdapter,
    source_store: ImmutableBackupSourceStore,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    """Read all current authorities and produce a release-control integrity report."""
    return check_chain_integrity(
        database.export_state(),
        source_store=source_store,
        runtime_root=runtime_root,
    )
