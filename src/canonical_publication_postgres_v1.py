"""Durable PostgreSQL authority for published Metis knowledge.

The operations console may keep local work state under ``/home/data``, but a
successful durable publication records the exact object versions, immutable
source binding, release, active publication pointer and audit evidence here.

Production authentication defaults to Microsoft Entra workload identity for
Azure Database for PostgreSQL. An environment-only DSN is supported for
controlled development or migration use; credentials are never stored in Git.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
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


def _timestamp(value: Any) -> datetime:
    raw = str(value or "").strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CanonicalPublicationStoreError("canonical_publication_timestamp_invalid") from exc


def _timestamp_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise CanonicalPublicationStoreError("canonical_postgres_json_invalid") from exc
        if isinstance(parsed, dict):
            return parsed
    raise CanonicalPublicationStoreError("canonical_postgres_json_invalid")


def registry_update_required(current: Mapping[str, Any] | None, *, release_id: str, published_at: str) -> bool:
    """Never move an active publication pointer backwards during replay."""
    if not current:
        return True
    if str(current.get("release_id") or "") == release_id:
        return False
    return _timestamp(current.get("published_at")) < _timestamp(published_at)


def expected_release_item_set(objects: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {
        (
            str(obj["object_id"]),
            str(obj["object_version"]),
            str((obj.get("provenance") or {}).get("content_hash") or ""),
        )
        for obj in objects
    }


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
        """Require provisioned tables; the application runtime never performs DDL."""
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
            raise CanonicalPublicationStoreError("canonical_postgres_schema_missing:" + ",".join(missing))

    @staticmethod
    def _canonical_payload(obj: dict[str, Any]) -> tuple[str, str]:
        payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        expected = str((obj.get("provenance") or {}).get("content_hash") or "")
        actual = compute_canonical_object_hash(obj)
        if not expected or actual != expected:
            raise CanonicalPublicationStoreError("canonical_object_hash_mismatch")
        return payload, actual

    @staticmethod
    def _audit(
        con: Any,
        *,
        entity_type: str,
        entity_id: str,
        entity_version: str,
        event_type: str,
        actor: str,
        event_at: str,
        details: dict[str, Any],
    ) -> None:
        con.execute(
            "INSERT INTO audit_events(entity_type,entity_id,entity_version,event_type,actor,event_at,details) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (
                entity_type,
                entity_id,
                entity_version,
                event_type,
                actor,
                event_at,
                json.dumps(details, sort_keys=True),
            ),
        )

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
        """Atomically persist one authorized publication and its Azure lineage."""
        if not objects:
            raise CanonicalPublicationStoreError("canonical_release_empty")
        if len(source_sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in source_sha256):
            raise CanonicalPublicationStoreError("canonical_source_sha256_invalid")
        if not snapshot_id or not source_locator or not release_id or not release_version or not release_owner:
            raise CanonicalPublicationStoreError("canonical_release_metadata_incomplete")
        _timestamp(published_at)

        prepared = [(obj, *self._canonical_payload(obj)) for obj in objects]
        incoming_items = expected_release_item_set(objects)
        if len(incoming_items) != len(objects):
            raise CanonicalPublicationStoreError("canonical_release_duplicate_object_version")

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
                            "INSERT INTO source_snapshots(snapshot_id,source_checksum,source_locator,recorded_at) VALUES(%s,%s,%s,%s)",
                            (snapshot_id, source_sha256.lower(), source_locator, published_at),
                        )

                    for obj, payload, content_hash in prepared:
                        object_id = str(obj["object_id"])
                        object_version = str(obj["object_version"])
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
                                    str(obj["document_id"]),
                                    str(obj.get("confirmed_object_type") or obj["object_type"]),
                                    source_sha256.lower(),
                                    content_hash,
                                    payload,
                                    published_at,
                                ),
                            )
                            self._audit(
                                con,
                                entity_type="object",
                                entity_id=object_id,
                                entity_version=object_version,
                                event_type="canonical_imported",
                                actor=release_owner,
                                event_at=published_at,
                                details={"content_hash": content_hash, "snapshot_id": snapshot_id},
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
                        "SELECT release_version,release_owner,status,published_at FROM publication_releases WHERE release_id=%s",
                        (release_id,),
                    ).fetchone()
                    if existing_release:
                        if (
                            str(existing_release["release_version"]) != release_version
                            or str(existing_release["release_owner"]) != release_owner
                            or str(existing_release["status"]) != "published"
                            or _timestamp(existing_release["published_at"]) != _timestamp(published_at)
                        ):
                            raise CanonicalPublicationStoreError("canonical_release_conflict")
                        rows = con.execute(
                            "SELECT object_id,object_version,content_hash FROM publication_release_items WHERE release_id=%s",
                            (release_id,),
                        ).fetchall()
                        stored_items = {
                            (str(row["object_id"]), str(row["object_version"]), str(row["content_hash"]))
                            for row in rows
                        }
                        if stored_items != incoming_items:
                            raise CanonicalPublicationStoreError("canonical_release_item_set_conflict")
                    else:
                        con.execute(
                            "INSERT INTO publication_releases(release_id,release_version,release_owner,status,created_at,published_at) VALUES(%s,%s,%s,'published',%s,%s)",
                            (release_id, release_version, release_owner, published_at, published_at),
                        )

                    for obj, _payload, content_hash in prepared:
                        object_id = str(obj["object_id"])
                        object_version = str(obj["object_version"])
                        current = con.execute(
                            "SELECT object_version,release_id,state,published_at FROM publication_registry WHERE object_id=%s",
                            (object_id,),
                        ).fetchone()
                        advance = registry_update_required(current, release_id=release_id, published_at=published_at)
                        if current and str(current["release_id"]) != release_id and not advance:
                            if not existing_release:
                                raise CanonicalPublicationStoreError("stale_release_replay")
                            continue

                        if not existing_release:
                            action = "supersede" if current and str(current["release_id"]) != release_id else "publish"
                            replaces = str(current["object_version"]) if action == "supersede" else None
                            con.execute(
                                "INSERT INTO publication_release_items(release_id,object_id,object_version,action,replaces_object_version,content_hash) VALUES(%s,%s,%s,%s,%s,%s)",
                                (release_id, object_id, object_version, action, replaces, content_hash),
                            )
                            if action == "supersede":
                                self._audit(
                                    con,
                                    entity_type="object",
                                    entity_id=object_id,
                                    entity_version=str(current["object_version"]),
                                    event_type="superseded",
                                    actor=release_owner,
                                    event_at=published_at,
                                    details={"superseded_by_version": object_version, "release_id": release_id},
                                )

                        if advance:
                            con.execute(
                                "INSERT INTO publication_registry(object_id,object_version,release_id,state,published_at,unpublished_at,unpublish_reason) VALUES(%s,%s,%s,'active',%s,NULL,NULL) ON CONFLICT(object_id) DO UPDATE SET object_version=EXCLUDED.object_version,release_id=EXCLUDED.release_id,state='active',published_at=EXCLUDED.published_at,unpublished_at=NULL,unpublish_reason=NULL",
                                (object_id, object_version, release_id, published_at),
                            )
                            self._audit(
                                con,
                                entity_type="object",
                                entity_id=object_id,
                                entity_version=object_version,
                                event_type="published",
                                actor=release_owner,
                                event_at=published_at,
                                details={"release_id": release_id, "snapshot_id": snapshot_id},
                            )

                    release_event = con.execute(
                        "SELECT 1 FROM audit_events WHERE entity_type='release' AND entity_id=%s AND event_type='release_published' LIMIT 1",
                        (release_id,),
                    ).fetchone()
                    if not release_event:
                        self._audit(
                            con,
                            entity_type="release",
                            entity_id=release_id,
                            entity_version=release_version,
                            event_type="release_published",
                            actor=release_owner,
                            event_at=published_at,
                            details={
                                "item_count": len(prepared),
                                "snapshot_id": snapshot_id,
                                "source_sha256": source_sha256.lower(),
                                "source_locator": source_locator,
                            },
                        )
        except CanonicalPublicationStoreError:
            raise
        except Exception as exc:
            raise CanonicalPublicationStoreError("canonical_postgres_write_failed") from exc

    def active_publication_rows(self) -> list[dict[str, Any]]:
        """Read the complete active publication set used to derive API projection."""
        try:
            with self._connect() as con:
                rows = con.execute(
                    """
                    SELECT c.canonical_json,
                           c.content_hash,
                           r.release_id,
                           rel.release_version,
                           rel.release_owner,
                           r.published_at,
                           s.snapshot_id
                    FROM publication_registry r
                    JOIN canonical_object_versions c
                      ON c.object_id=r.object_id AND c.object_version=r.object_version
                    JOIN publication_releases rel
                      ON rel.release_id=r.release_id
                    JOIN canonical_object_sources s
                      ON s.object_id=c.object_id AND s.object_version=c.object_version
                    WHERE r.state='active' AND rel.status='published'
                    ORDER BY c.object_id
                    """
                ).fetchall()
        except CanonicalPublicationStoreError:
            raise
        except Exception as exc:
            raise CanonicalPublicationStoreError("canonical_postgres_read_failed") from exc

        out: list[dict[str, Any]] = []
        for row in rows:
            obj = _json_mapping(row["canonical_json"])
            actual = compute_canonical_object_hash(obj)
            if actual != str(row["content_hash"]):
                raise CanonicalPublicationStoreError("canonical_authority_hash_mismatch")
            out.append(
                {
                    "knowledge_object": obj,
                    "publication": {
                        "release_id": str(row["release_id"]),
                        "release_version": str(row["release_version"]),
                        "published_at": _timestamp_text(row["published_at"]),
                    },
                    "snapshot_id": str(row["snapshot_id"]),
                    "release_owner": str(row["release_owner"]),
                }
            )
        return out

    def release_for_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        """Return the durable release record for one console source snapshot."""
        if not snapshot_id:
            raise CanonicalPublicationStoreError("canonical_snapshot_id_required")
        try:
            with self._connect() as con:
                release = con.execute(
                    """
                    SELECT rel.release_id,
                           rel.release_version,
                           rel.release_owner,
                           rel.published_at,
                           ev.details
                    FROM audit_events ev
                    JOIN publication_releases rel ON rel.release_id=ev.entity_id
                    WHERE ev.entity_type='release'
                      AND ev.event_type='release_published'
                      AND ev.details->>'snapshot_id'=%s
                      AND rel.status='published'
                    ORDER BY rel.published_at DESC
                    LIMIT 1
                    """,
                    (snapshot_id,),
                ).fetchone()
                if not release:
                    return None
                items = con.execute(
                    """
                    SELECT i.object_id,
                           i.object_version,
                           i.content_hash,
                           c.canonical_json
                    FROM publication_release_items i
                    JOIN canonical_object_versions c
                      ON c.object_id=i.object_id AND c.object_version=i.object_version
                    WHERE i.release_id=%s
                    ORDER BY i.object_id, i.object_version
                    """,
                    (release["release_id"],),
                ).fetchall()
        except CanonicalPublicationStoreError:
            raise
        except Exception as exc:
            raise CanonicalPublicationStoreError("canonical_postgres_read_failed") from exc

        details = _json_mapping(release["details"])
        objects: list[dict[str, Any]] = []
        for row in items:
            obj = _json_mapping(row["canonical_json"])
            actual = compute_canonical_object_hash(obj)
            if actual != str(row["content_hash"]):
                raise CanonicalPublicationStoreError("canonical_authority_hash_mismatch")
            provenance = obj.get("provenance") or {}
            objects.append(
                {
                    "object_id": str(row["object_id"]),
                    "object_version": str(row["object_version"]),
                    "canonical_object_hash": str(provenance.get("canonical_object_hash") or actual),
                    "content_hash": str(row["content_hash"]),
                    "confirmed_object_type": obj.get("confirmed_object_type"),
                }
            )
        if not objects:
            raise CanonicalPublicationStoreError("canonical_release_items_missing")
        return {
            "release_id": str(release["release_id"]),
            "release_version": str(release["release_version"]),
            "release_owner": str(release["release_owner"]),
            "published_at": _timestamp_text(release["published_at"]),
            "snapshot_id": str(details.get("snapshot_id") or ""),
            "source_sha256": str(details.get("source_sha256") or ""),
            "source_locator": str(details.get("source_locator") or ""),
            "objects": objects,
        }
