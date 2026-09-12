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
from datetime import date, datetime, timezone
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
    if isinstance(value, (datetime, date)):
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
                                row["notes"], row["created_at"], row["published_at"], row["withdrawn_at"],
                            ),
                        )
                    for row in rows["publication_release_items"]:
                        con.execute(
                            """INSERT INTO publication_release_items(
                               release_id,object_id,object_version,action,replaces_object_version,content_hash
                               ) VALUES(%s,%s,%s,%s,%s,%s)""",
                            (
                                row["release_id"], row["object_id"], row["object_version"], row["action"],
                                row["replaces_object_version"], row["content_hash"],
                            ),
                        )
                    for row in rows["publication_registry"]:
                        con.execute(
                            """INSERT INTO publication_registry(
                               object_id,object_version,release_id,state,published_at,unpublished_at,unpublish_reason
                               ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                            (
                                row["object_id"], row["object_version"], row["release_id"], row["state"],
                                row["published_at"], row["unpublished_at"], row["unpublish_reason"],
                            ),
                        )
                    for row in rows["audit_events"]:
                        con.execute(
                            """INSERT INTO audit_events(
                               event_id,entity_type,entity_id,entity_version,event_type,actor,event_at,details
                               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                            (
                                row["event_id"], row["entity_type"], row["entity_id"], row["entity_version"],
                                row["event_type"], row["actor"], row["event_at"],
                                json.dumps(row["details"], ensure_ascii=False, sort_keys=True),
                            ),
                        )
                    row = con.execute("SELECT MAX(event_id) AS n FROM audit_events").fetchone()
                    if row and row["n"] is not None:
                        con.execute(
                            "SELECT setval(pg_get_serial_sequence('audit_events','event_id'), %s, true)",
                            (int(row["n"]),),
                        )
        except PublicationChainRecoveryError:
            raise
        except Exception as exc:
            raise PublicationChainRecoveryError("database_restore_failed") from exc


def _validate_database_backup_shape(state: Mapping[str, Any]) -> None:
    if state.get("format") != BACKUP_FORMAT:
        raise PublicationChainRecoveryError("database_backup_format_invalid")
    for table in DB_TABLES:
        _table_rows(state, table)


def check_chain_integrity(
    state: Mapping[str, Any],
    *,
    source_store: ImmutableBackupSourceStore,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        _validate_database_backup_shape(state)
    except PublicationChainRecoveryError as exc:
        return {"ok": False, "errors": [str(exc)]}

    object_rows = _table_rows(state, "canonical_object_versions")
    source_rows = _table_rows(state, "source_snapshots")
    link_rows = _table_rows(state, "canonical_object_sources")
    release_rows = _table_rows(state, "publication_releases")
    item_rows = _table_rows(state, "publication_release_items")
    registry_rows = _table_rows(state, "publication_registry")

    objects, object_errors = _index_unique(object_rows, ("object_id", "object_version"), "object")
    sources, source_errors = _index_unique(source_rows, ("snapshot_id",), "source")
    releases, release_errors = _index_unique(release_rows, ("release_id",), "release")
    errors.extend(object_errors + source_errors + release_errors)

    source_by_object: dict[tuple[str, str], str] = {}
    for link in link_rows:
        key = (str(link.get("object_id") or ""), str(link.get("object_version") or ""))
        snapshot_id = str(link.get("snapshot_id") or "")
        if key not in objects:
            errors.append(f"source_link_object_missing:{'|'.join(key)}")
            continue
        if snapshot_id not in sources:
            errors.append(f"source_link_snapshot_missing:{snapshot_id}")
            continue
        if key in source_by_object:
            errors.append(f"source_link_duplicate:{'|'.join(key)}")
            continue
        source_by_object[key] = snapshot_id

    for key, obj in objects.items():
        if obj.get("validation_status") != "approved":
            errors.append(f"object_not_approved:{'|'.join(key)}")
        canonical = obj.get("canonical_json")
        if not isinstance(canonical, Mapping):
            errors.append(f"canonical_json_invalid:{'|'.join(key)}")
            continue
        try:
            if compute_canonical_object_hash(dict(canonical)) != obj.get("content_hash"):
                errors.append(f"content_hash_mismatch:{'|'.join(key)}")
        except Exception:
            errors.append(f"content_hash_invalid:{'|'.join(key)}")
        if key not in source_by_object:
            errors.append(f"object_source_missing:{'|'.join(key)}")
            continue
        source = sources.get((source_by_object[key],))
        if source is None:
            continue
        if source.get("source_checksum") != obj.get("source_checksum"):
            errors.append(f"source_checksum_lineage_mismatch:{'|'.join(key)}")

    for snapshot_key, source in sources.items():
        checksum = str(source.get("source_checksum") or "")
        locator = str(source.get("source_locator") or "")
        if not SHA256_RE.fullmatch(checksum):
            errors.append(f"source_checksum_invalid:{snapshot_key[0]}")
            continue
        try:
            parsed = parse_g2_locator(locator)
            if parsed.sha256 != checksum:
                errors.append(f"source_locator_checksum_mismatch:{snapshot_key[0]}")
            data = source_store.load_verified(locator)
            if sha256_bytes(data) != checksum:
                errors.append(f"source_blob_checksum_mismatch:{snapshot_key[0]}")
        except (G2SourceStoreError, ValueError, KeyError):
            errors.append(f"source_blob_unavailable:{snapshot_key[0]}")

    items_by_release: dict[str, list[dict[str, Any]]] = {}
    for item in item_rows:
        release_id = str(item.get("release_id") or "")
        items_by_release.setdefault(release_id, []).append(item)
        key = (str(item.get("object_id") or ""), str(item.get("object_version") or ""))
        obj = objects.get(key)
        if obj is None:
            errors.append(f"release_item_object_missing:{release_id}:{'|'.join(key)}")
        elif item.get("content_hash") != obj.get("content_hash"):
            errors.append(f"release_item_hash_mismatch:{release_id}:{'|'.join(key)}")
        if release_id not in releases:
            errors.append(f"release_item_release_missing:{release_id}")

    for row in registry_rows:
        object_id = str(row.get("object_id") or "")
        object_version = str(row.get("object_version") or "")
        release_id = str(row.get("release_id") or "")
        key = (object_id, object_version)
        if row.get("state") not in {"active", "emergency_unpublished"}:
            errors.append(f"registry_state_invalid:{object_id}")
        if key not in objects:
            errors.append(f"registry_object_missing:{object_id}")
        release = releases.get((release_id,))
        if release is None:
            errors.append(f"registry_release_missing:{object_id}:{release_id}")
        elif release.get("status") != "published":
            errors.append(f"registry_release_not_published:{object_id}:{release_id}")
        release_items = items_by_release.get(release_id, [])
        if not any(
            str(item.get("object_id")) == object_id
            and str(item.get("object_version")) == object_version
            for item in release_items
        ):
            errors.append(f"registry_release_item_missing:{object_id}:{release_id}")

    if runtime_root is not None:
        try:
            _check_runtime_consistency(state, runtime_root, errors)
        except Exception:
            errors.append("runtime_consistency_check_failed")

    return {
        "ok": not errors,
        "errors": errors,
        "objects": len(objects),
        "sources": len(sources),
        "releases": len(releases),
        "registry": len(registry_rows),
    }


def _check_runtime_consistency(
    state: Mapping[str, Any],
    runtime_root: Path,
    errors: list[str],
) -> None:
    runtime = Path(runtime_root) / "output" / "runtime" / "operations-console"
    release_dir = runtime / "release_manifests"
    projection_path = runtime / "published_projection.jsonl"
    releases = {str(row["release_id"]): row for row in _table_rows(state, "publication_releases")}
    items = _table_rows(state, "publication_release_items")
    registry = _table_rows(state, "publication_registry")

    for release_id, release in releases.items():
        if release.get("status") != "published":
            continue
        path = release_dir / f"{release_id}.json"
        if not path.exists():
            errors.append(f"runtime_release_manifest_missing:{release_id}")
            continue
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append(f"runtime_release_manifest_invalid:{release_id}")
            continue
        if str(manifest.get("release_id") or "") != release_id:
            errors.append(f"runtime_release_manifest_id_mismatch:{release_id}")
        expected = sorted(
            (str(row["object_id"]), str(row["object_version"]), str(row["content_hash"]))
            for row in items if str(row["release_id"]) == release_id
        )
        actual = sorted(
            (
                str(row.get("object_id") or ""),
                str(row.get("object_version") or ""),
                str(row.get("canonical_object_hash") or row.get("content_hash") or ""),
            )
            for row in (manifest.get("objects") or []) if isinstance(row, Mapping)
        )
        if expected != actual:
            errors.append(f"runtime_release_manifest_items_mismatch:{release_id}")

    if projection_path.exists():
        try:
            rows = [
                json.loads(line) for line in projection_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError):
            errors.append("runtime_projection_invalid")
            return
        active = {
            (str(row["object_id"]), str(row["object_version"]))
            for row in registry if row.get("state") == "active"
        }
        projected = {
            (
                str((row.get("metadata") or {}).get("object_id") or ""),
                str((row.get("metadata") or {}).get("object_version") or ""),
            )
            for row in rows
        }
        if active != projected:
            errors.append("runtime_projection_registry_mismatch")


def _read_archive_json(zipf: zipfile.ZipFile, member: str) -> Any:
    try:
        return json.loads(zipf.read(member).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicationChainRecoveryError(f"chain_backup_member_invalid:{member}") from exc


def _archive_member_bytes(zipf: zipfile.ZipFile, member: str) -> bytes:
    try:
        return zipf.read(member)
    except KeyError as exc:
        raise PublicationChainRecoveryError(f"chain_backup_member_missing:{member}") from exc


def verify_publication_chain_backup(archive: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(archive) as zipf:
            manifest = _read_archive_json(zipf, "chain_manifest.json")
            if manifest.get("format") != BACKUP_FORMAT:
                errors.append("chain_backup_format_invalid")
            database = manifest.get("database") or {}
            db_member = _backup_member(str(database.get("member") or ""))
            db_bytes = _archive_member_bytes(zipf, db_member)
            if _sha256(db_bytes) != database.get("sha256"):
                errors.append("chain_backup_database_hash_mismatch")
            database_state = json.loads(db_bytes.decode("utf-8"))
            try:
                _validate_database_backup_shape(database_state)
            except PublicationChainRecoveryError as exc:
                errors.append(str(exc))

            runtime = manifest.get("runtime") or {}
            runtime_member = runtime.get("member")
            if runtime_member:
                member = _backup_member(str(runtime_member))
                runtime_bytes = _archive_member_bytes(zipf, member)
                if _sha256(runtime_bytes) != runtime.get("sha256"):
                    errors.append("chain_backup_runtime_hash_mismatch")

            blob_members: set[str] = set()
            for blob in manifest.get("blobs") or []:
                member = _backup_member(str(blob.get("member") or ""))
                if member in blob_members:
                    errors.append(f"chain_backup_duplicate_blob_member:{member}")
                    continue
                blob_members.add(member)
                data = _archive_member_bytes(zipf, member)
                checksum = str(blob.get("sha256") or "")
                if not SHA256_RE.fullmatch(checksum) or _sha256(data) != checksum:
                    errors.append(f"chain_backup_blob_hash_mismatch:{checksum}")
    except (OSError, zipfile.BadZipFile, PublicationChainRecoveryError, json.JSONDecodeError) as exc:
        errors.append(f"chain_backup_unreadable:{type(exc).__name__}")
    return {"ok": not errors, "errors": errors}


def backup_publication_chain(
    archive: Path,
    *,
    database: DatabaseBackupAdapter,
    source_store: ImmutableBackupSourceStore,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    database_state = database.export_state()
    db_bytes = _canonical_json_bytes(database_state)
    runtime_bytes: bytes | None = None
    if runtime_root is not None:
        with tempfile.TemporaryDirectory(prefix="metis-runtime-backup-") as tmpdir:
            runtime_path = Path(tmpdir) / "runtime.zip"
            export_runtime_data(runtime_path, root=runtime_root)
            runtime_bytes = runtime_path.read_bytes()

    source_rows = _table_rows(database_state, "source_snapshots")
    blobs: list[tuple[dict[str, Any], bytes]] = []
    for row in source_rows:
        locator = str(row.get("source_locator") or "")
        checksum = str(row.get("source_checksum") or "")
        if not SHA256_RE.fullmatch(checksum):
            raise PublicationChainRecoveryError("source_checksum_invalid_for_backup")
        try:
            data = source_store.load_verified(locator)
        except Exception as exc:
            raise PublicationChainRecoveryError("source_blob_unavailable_for_backup") from exc
        if _sha256(data) != checksum:
            raise PublicationChainRecoveryError("source_blob_checksum_mismatch_for_backup")
        filename = "source.bin"
        try:
            filename = parse_g2_locator(locator).filename
        except (G2SourceStoreError, ValueError):
            pass
        member = _backup_member(f"blobs/{checksum}/{filename}")
        blobs.append(({"sha256": checksum, "locator": locator, "member": member}, data))

    manifest: dict[str, Any] = {
        "format": BACKUP_FORMAT,
        "created_at": _utc_now(),
        "database": {"member": "database.json", "sha256": _sha256(db_bytes)},
        "runtime": None,
        "blobs": [entry for entry, _data in blobs],
    }
    if runtime_bytes is not None:
        manifest["runtime"] = {
            "member": "runtime/runtime.zip",
            "sha256": _sha256(runtime_bytes),
        }

    archive = Path(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("database.json", db_bytes)
        if runtime_bytes is not None:
            zipf.writestr("runtime/runtime.zip", runtime_bytes)
        for entry, data in blobs:
            zipf.writestr(entry["member"], data)
        zipf.writestr(
            "chain_manifest.json",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )

    verification = verify_publication_chain_backup(archive)
    if not verification["ok"]:
        raise PublicationChainRecoveryError("chain_backup_verification_failed:" + ";".join(verification["errors"]))
    return manifest


def restore_publication_chain(
    archive: Path,
    *,
    database: DatabaseBackupAdapter,
    source_store: ImmutableBackupSourceStore,
    runtime_dest: Path | None = None,
) -> dict[str, Any]:
    verification = verify_publication_chain_backup(archive)
    if not verification["ok"]:
        raise PublicationChainRecoveryError("chain_restore_backup_invalid:" + ";".join(verification["errors"]))

    with zipfile.ZipFile(archive) as zipf:
        manifest = _read_archive_json(zipf, "chain_manifest.json")
        database_state = _read_archive_json(zipf, _backup_member(manifest["database"]["member"]))

        # Fail closed before changing any external authority.
        database.assert_empty()
        blob_plan: list[tuple[dict[str, Any], bytes]] = []
        for row in manifest.get("blobs") or []:
            blob_plan.append((dict(row), _archive_member_bytes(zipf, _backup_member(row["member"]))))

        # Restore immutable source bytes first and require a read-back proof.
        for row, data in blob_plan:
            parsed = parse_g2_locator(str(row["locator"]))
            restored = source_store.store_verified(
                data=data,
                sha256=str(row["sha256"]),
                filename=parsed.filename,
            )
            if restored != row["locator"]:
                raise PublicationChainRecoveryError("restored_blob_locator_mismatch")
            if source_store.load_verified(restored) != data:
                raise PublicationChainRecoveryError("restored_blob_readback_mismatch")

        runtime = manifest.get("runtime") or {}
        if runtime.get("member"):
            if runtime_dest is None:
                raise PublicationChainRecoveryError("runtime_restore_destination_required")
            runtime_zip = _archive_member_bytes(zipf, _backup_member(runtime["member"]))
            with tempfile.TemporaryDirectory(prefix="metis-runtime-restore-") as tmpdir:
                path = Path(tmpdir) / "runtime.zip"
                path.write_bytes(runtime_zip)
                restore_runtime_data(path, destination=runtime_dest)

        # Authority is restored last.
        database.restore_state(database_state)

    restored_state = database.export_state()
    if _sha256(_canonical_json_bytes(restored_state.get("tables"))) != _sha256(
        _canonical_json_bytes(database_state.get("tables"))
    ):
        raise PublicationChainRecoveryError("database_restore_roundtrip_mismatch")
    integrity = check_chain_integrity(
        restored_state,
        source_store=source_store,
        runtime_root=runtime_dest,
    )
    if not integrity["ok"]:
        raise PublicationChainRecoveryError("restored_chain_integrity_failed:" + ";".join(integrity["errors"]))
    return {"ok": True, "integrity": integrity}


def live_chain_integrity(
    *,
    database: DatabaseBackupAdapter,
    source_store: ImmutableBackupSourceStore,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    state = database.export_state()
    return check_chain_integrity(state, source_store=source_store, runtime_root=runtime_root)
