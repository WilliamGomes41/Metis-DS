"""Durable PostgreSQL authority for published Metis knowledge.

The operations console may keep rebuildable/local work state under ``/home/data``,
but a successful publication is not complete until the exact published object
versions, source binding, release and publication registry are committed here.

Production authentication defaults to Microsoft Entra workload identity for
Azure Database for PostgreSQL. A DSN may be supplied explicitly for controlled
development/migration use; credentials are never stored in the repository.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping

from azure.identity import DefaultAzureCredential

from src.integrity_kernel import compute_canonical_object_hash

AZURE_POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
REQUIRED_TABLES = frozenset(
    {
        "canonical_object_versions",
        "publication_releases",
        "publication_release_items",
        "publication_registry",
        "audit_events",
        "source_snapshots",
        "canonical_object_sources",
    }
)


class CanonicalPublicationStoreError(RuntimeError):
    """Fail-closed durable publication error."""


@dataclass(frozen=True)
class PostgresCanonicalConfig:
    host: str = ""
    database: str = ""
    user: str = ""
    dsn: str = ""

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> "PostgresCanonicalConfig":
        env = environ if environ is not None else os.environ
        return cls(
            host=str(env.get("METIS_CANONICAL_DB_HOST", "") or "").strip(),
            database=str(env.get("METIS_CANONICAL_DB_NAME", "") or "").strip(),
            user=str(env.get("METIS_CANONICAL_DB_USER", "") or "").strip(),
            dsn=str(env.get("METIS_CANONICAL_DB_DSN", "") or "").strip(),
        )

    def validate(self) -> None:
        if self.dsn:
            return
        if not self.host or not self.database or not self.user:
            raise CanonicalPublicationStoreError("canonical_postgres_configuration_incomplete")


class PostgresCanonicalPublicationStore:
    """One transactional authority for canonical versions and published releases."""

    def __init__(
        self,
        config: PostgresCanonicalConfig | None = None,
        *,
        credential: Any | None = None,
    ) -> None:
        self.config = config or PostgresCanonicalConfig.from_environ()
        self.config.validate()
        self._credential = credential

    def _connect(self) -> Any:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - deployment dependency guard
            raise CanonicalPublicationStoreError("psycopg_unavailable") from exc

        try:
            if self.config.dsn:
                return psycopg.connect(self.config.dsn, row_factory=dict_row, connect_timeout=10)
            credential = self._credential or DefaultAzureCredential()
            token = credential.get_token(AZURE_POSTGRES_SCOPE).token
            return psycopg.connect(
                host=self.config.host,
                dbname=self.config.database,
                user=self.config.user,
                password=token,
                sslmode="require",
                connect_timeout=10,
                row_factory=dict_row,
            )
        except Exception as exc:
            raise CanonicalPublicationStoreError("canonical_postgres_unavailable") from exc

    def verify_schema(self) -> None:
        """Require the provisioned schema; the application runtime does not perform DDL."""
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = current_schema()"
                ).fetchall()
        except CanonicalPublicationStoreError:
            raise
        except Exception as exc:
            raise CanonicalPublicationStoreError("canonical_postgres_schema_check_failed") from exc
        present = {str(row["tablename"]) for row in rows}
        missing = sorted(REQUIRED_TABLES - present)
        if missing:
            raise CanonicalPublicationStoreError(
                "canonical_postgres_schema_missing:" + ",".join(missing)
            )

    @staticmethod
    def _canonical_payload(obj: dict[str, Any]) -> tuple[str, str]:
        payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        expected = str((obj.get("provenance") or {}).get("content_hash") or "")
        actual = compute_canonical_object_hash(obj)
        if not expected or actual != expected:
            raise CanonicalPublicationStoreError("canonical_object_hash_mismatch")
        return payload, actual

    def persist_published_release(
        self,
        *,
        snapshot_id: str,
        source_sha256: str,
        source_locator: str,
        release_id: str,
        release_version: str,
        release_owner: str,
        published_at: str,
        objects: list[dict[str, Any]],
    ) -> None:
        """Atomically persist one already-authorized console publication.

        Exact object versions are immutable. Repeating the same release is
        idempotent; conflicting bytes, source bindings or release metadata fail
        closed. The publication registry points only at versions committed in the
        same transaction.
        """
        if not objects:
            raise CanonicalPublicationStoreError("canonical_release_empty")
        if len(source_sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in source_sha256):
            raise CanonicalPublicationStoreError("canonical_source_sha256_invalid")
        if not snapshot_id or not source_locator or not release_id or not release_version or not release_owner:
            raise CanonicalPublicationStoreError("canonical_release_metadata_incomplete")

        prepared = [(obj, *self._canonical_payload(obj)) for obj in objects]
        try:
            with self._connect() as con:
                with con.transaction():
                    existing_source = con.execute(
                        "SELECT source_checksum, source_locator FROM source_snapshots WHERE snapshot_id=%s",
                        (snapshot_id,),
                    ).fetchone()
                    if existing_source:
                        if (
                            str(existing_source["source_checksum"]).lower() != source_sha256.lower()
                            or str(existing_source["source_locator"]) != source_locator
                        ):
                            raise CanonicalPublicationStoreError("canonical_source_snapshot_conflict")
                    else:
                        con.execute(
                            "INSERT INTO source_snapshots(snapshot_id,source_checksum,source_locator,created_at) VALUES(%s,%s,%s,%s)",
                            (snapshot_id, source_sha256.lower(), source_locator, published_at),
                        )

                    for obj, payload, content_hash in prepared:
                        object_id = str(obj["object_id"])
                        object_version = str(obj["object_version"])
                        document_id = str(obj["document_id"])
                        object_type = str(obj.get("confirmed_object_type") or obj["object_type"])
                        source_checksum = str((obj.get("source") or {}).get("source_checksum") or "")
                        if source_checksum.lower() != source_sha256.lower():
                            raise CanonicalPublicationStoreError("canonical_object_source_mismatch")
                        existing = con.execute(
                            "SELECT content_hash FROM canonical_object_versions WHERE object_id=%s AND object_version=%s",
                            (object_id, object_version),
                        ).fetchone()
                        if existing and str(existing["content_hash"]) != content_hash:
                            raise CanonicalPublicationStoreError("immutable_version_content_conflict")
                        if not existing:
                            con.execute(
                                "INSERT INTO canonical_object_versions(object_id,object_version,document_id,object_type,validation_status,source_checksum,content_hash,canonical_json,imported_at) VALUES(%s,%s,%s,%s,'approved',%s,%s,%s::jsonb,%s)",
                                (
                                    object_id,
                                    object_version,
                                    document_id,
                                    object_type,
                                    source_sha256.lower(),
                                    content_hash,
                                    payload,
                                    published_at,
                                ),
                            )
                            con.execute(
                                "INSERT INTO audit_events(entity_type,entity_id,entity_version,event_type,actor,event_at,details) VALUES('object',%s,%s,'canonical_imported',%s,%s,%s::jsonb)",
                                (
                                    object_id,
                                    object_version,
                                    release_owner,
                                    published_at,
                                    json.dumps({"content_hash": content_hash, "snapshot_id": snapshot_id}, sort_keys=True),
                                ),
                            )
                        con.execute(
                            "INSERT INTO canonical_object_sources(object_id,object_version,snapshot_id) VALUES(%s,%s,%s) ON CONFLICT(object_id,object_version) DO NOTHING",
                            (object_id, object_version, snapshot_id),
                        )
                        link = con.execute(
                            "SELECT snapshot_id FROM canonical_object_sources WHERE object_id=%s AND object_version=%s",
                            (object_id, object_version),
                        ).fetchone()
                        if not link or str(link["snapshot_id"]) != snapshot_id:
                            raise CanonicalPublicationStoreError("canonical_object_source_link_conflict")

                    existing_release = con.execute(
                        "SELECT release_version, release_owner, status, published_at FROM publication_releases WHERE release_id=%s",
                        (release_id,),
                    ).fetchone()
                    if existing_release:
                        if (
                            str(existing_release["release_version"]) != release_version
                            or str(existing_release["release_owner"]) != release_owner
                            or str(existing_release["status"]) != "published"
                        ):
                            raise CanonicalPublicationStoreError("canonical_release_conflict")
                    else:
                        con.execute(
                            "INSERT INTO publication_releases(release_id,release_version,release_owner,status,created_at,published_at) VALUES(%s,%s,%s,'published',%s,%s)",
                            (release_id, release_version, release_owner, published_at, published_at),
                        )

                    for obj, _payload, content_hash in prepared:
                        object_id = str(obj["object_id"])
                        object_version = str(obj["object_version"])
                        item = con.execute(
                            "SELECT content_hash FROM publication_release_items WHERE release_id=%s AND object_id=%s AND object_version=%s",
                            (release_id, object_id, object_version),
                        ).fetchone()
                        if item and str(item["content_hash"]) != content_hash:
                            raise CanonicalPublicationStoreError("canonical_release_item_conflict")
                        if not item:
                            con.execute(
                                "INSERT INTO publication_release_items(release_id,object_id,object_version,action,replaces_object_version,content_hash) VALUES(%s,%s,%s,'publish',NULL,%s)",
                                (release_id, object_id, object_version, content_hash),
                            )

                        current = con.execute(
                            "SELECT object_version, release_id, state FROM publication_registry WHERE object_id=%s",
                            (object_id,),
                        ).fetchone()
                        if current and (
                            str(current["object_version"]) != object_version
                            or str(current["release_id"]) != release_id
                        ):
                            con.execute(
                                "INSERT INTO audit_events(entity_type,entity_id,entity_version,event_type,actor,event_at,details) VALUES('object',%s,%s,'superseded',%s,%s,%s::jsonb)",
                                (
                                    object_id,
                                    str(current["object_version"]),
                                    release_owner,
                                    published_at,
                                    json.dumps({"superseded_by_version": object_version, "release_id": release_id}, sort_keys=True),
                                ),
                            )
                        con.execute(
                            "INSERT INTO publication_registry(object_id,object_version,release_id,state,published_at,unpublished_at,unpublish_reason) VALUES(%s,%s,%s,'active',%s,NULL,NULL) ON CONFLICT(object_id) DO UPDATE SET object_version=EXCLUDED.object_version,release_id=EXCLUDED.release_id,state='active',published_at=EXCLUDED.published_at,unpublished_at=NULL,unpublish_reason=NULL",
                            (object_id, object_version, release_id, published_at),
                        )

                    event = con.execute(
                        "SELECT 1 FROM audit_events WHERE entity_type='release' AND entity_id=%s AND event_type='release_published' LIMIT 1",
                        (release_id,),
                    ).fetchone()
                    if not event:
                        con.execute(
                            "INSERT INTO audit_events(entity_type,entity_id,entity_version,event_type,actor,event_at,details) VALUES('release',%s,%s,'release_published',%s,%s,%s::jsonb)",
                            (
                                release_id,
                                release_version,
                                release_owner,
                                published_at,
                                json.dumps(
                                    {
                                        "item_count": len(prepared),
                                        "snapshot_id": snapshot_id,
                                        "source_sha256": source_sha256.lower(),
                                        "source_locator": source_locator,
                                    },
                                    sort_keys=True,
                                ),
                            ),
                        )
        except CanonicalPublicationStoreError:
            raise
        except Exception as exc:
            raise CanonicalPublicationStoreError("canonical_postgres_write_failed") from exc
