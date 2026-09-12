"""Shared PostgreSQL document/object store for the Metis operations console.

This module is deliberately not wired into console callers yet. It provides the
transactional store and explicit legacy-runtime migration used by the next
cut-over step. Publication authority remains separate.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from azure.identity import DefaultAzureCredential

from src.canonical_publication_postgres_v1 import AZURE_POSTGRES_SCOPE, PostgresCanonicalConfig

REQUIRED_WORKFLOW_DOCUMENT_TABLES = frozenset(
    {"accounts", "documents", "document_reviewers", "document_objects"}
)


class WorkflowDocumentStoreError(RuntimeError):
    """Fail-closed workflow document persistence error."""


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_legacy_runtime(runtime: Path) -> list[dict[str, Any]]:
    """Read and validate the complete file-backed document snapshot before writing."""
    envelopes_path = runtime / "envelopes.json"
    objects_dir = runtime / "objects"
    if not envelopes_path.exists():
        return []
    try:
        raw = json.loads(envelopes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowDocumentStoreError("workflow_legacy_envelopes_invalid") from exc
    if not isinstance(raw, dict):
        raise WorkflowDocumentStoreError("workflow_legacy_envelopes_invalid")

    bundles: list[dict[str, Any]] = []
    for key in sorted(raw):
        envelope = raw[key]
        if not isinstance(envelope, dict):
            raise WorkflowDocumentStoreError("workflow_legacy_envelope_invalid")
        snapshot_id = str(envelope.get("snapshot_id") or "")
        if not snapshot_id or snapshot_id != str(key):
            raise WorkflowDocumentStoreError("workflow_legacy_snapshot_identity_mismatch")
        path = objects_dir / f"{snapshot_id}.jsonl"
        try:
            rows = [] if not path.exists() else [
                json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowDocumentStoreError("workflow_legacy_objects_invalid") from exc
        seen: set[tuple[str, str]] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise WorkflowDocumentStoreError("workflow_legacy_object_invalid")
            identity = (str(row.get("object_id") or ""), str(row.get("object_version") or ""))
            if not all(identity) or identity in seen:
                raise WorkflowDocumentStoreError("workflow_legacy_object_identity_invalid")
            seen.add(identity)
        bundles.append({"envelope": envelope, "objects": rows})
    return bundles


class PostgresWorkflowDocumentStore:
    """Transactional authority for mutable document envelopes and work objects."""

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
        except ImportError as exc:  # pragma: no cover
            raise WorkflowDocumentStoreError("psycopg_unavailable") from exc
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
            raise WorkflowDocumentStoreError("workflow_postgres_unavailable") from exc

    def verify_schema(self) -> None:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='workflow'"
                ).fetchall()
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_schema_check_failed") from exc
        present = {str(row["tablename"]) for row in rows}
        missing = sorted(REQUIRED_WORKFLOW_DOCUMENT_TABLES - present)
        if missing:
            raise WorkflowDocumentStoreError("workflow_document_schema_missing:" + ",".join(missing))

    @staticmethod
    def _document_values(envelope: Mapping[str, Any]) -> tuple[Any, ...]:
        required = (
            "snapshot_id", "source_id", "document_id", "title", "family", "class", "state",
            "publication_eligibility", "content_kind", "ingest_kind", "version", "date", "sha256",
            "locator", "uploader_account_id", "acquired_at", "console_version",
        )
        if any(not str(envelope.get(key) or "").strip() for key in required):
            raise WorkflowDocumentStoreError("workflow_document_metadata_incomplete")
        return (
            envelope["snapshot_id"], envelope["source_id"], envelope["document_id"], envelope["title"],
            envelope["family"], envelope["class"], envelope["state"], envelope["publication_eligibility"],
            envelope["content_kind"], envelope["ingest_kind"], envelope["version"], envelope["date"],
            envelope["sha256"], envelope["locator"], envelope.get("immutable_storage_locator"),
            envelope.get("live_url") or "", envelope["uploader_account_id"], envelope.get("replaces_snapshot_id"),
            json.dumps(envelope.get("object_diff"), ensure_ascii=False, sort_keys=True) if envelope.get("object_diff") is not None else None,
            bool(envelope.get("clinical_rereview_required", False)), envelope["acquired_at"], envelope["console_version"],
        )

    @staticmethod
    def _document_projection(envelope: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "snapshot_id": str(envelope.get("snapshot_id") or ""),
            "source_id": str(envelope.get("source_id") or ""),
            "document_id": str(envelope.get("document_id") or ""),
            "title": str(envelope.get("title") or ""),
            "family": str(envelope.get("family") or ""),
            "class": str(envelope.get("class") or ""),
            "state": str(envelope.get("state") or ""),
            "publication_eligibility": str(envelope.get("publication_eligibility") or ""),
            "content_kind": str(envelope.get("content_kind") or ""),
            "ingest_kind": str(envelope.get("ingest_kind") or ""),
            "source_version": str(envelope.get("version") or ""),
            "source_date": str(envelope.get("date") or ""),
            "source_sha256": str(envelope.get("sha256") or ""),
            "source_locator": str(envelope.get("locator") or ""),
            "immutable_storage_locator": envelope.get("immutable_storage_locator"),
            "live_url": str(envelope.get("live_url") or ""),
            "uploader_account_id": str(envelope.get("uploader_account_id") or ""),
            "replaces_snapshot_id": envelope.get("replaces_snapshot_id"),
            "object_diff": envelope.get("object_diff"),
            "clinical_rereview_required": bool(envelope.get("clinical_rereview_required", False)),
            "acquired_at": str(envelope.get("acquired_at") or ""),
            "console_version": str(envelope.get("console_version") or ""),
        }

    @staticmethod
    def _normalized_database_document(row: Mapping[str, Any]) -> dict[str, Any]:
        def text(value: Any) -> str:
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return str(value or "")
        diff = row.get("object_diff")
        if isinstance(diff, str):
            diff = json.loads(diff)
        return {
            "snapshot_id": str(row["snapshot_id"]), "source_id": str(row["source_id"]),
            "document_id": str(row["document_id"]), "title": str(row["title"]), "family": str(row["family"]),
            "class": str(row["class"]), "state": str(row["state"]),
            "publication_eligibility": str(row["publication_eligibility"]), "content_kind": str(row["content_kind"]),
            "ingest_kind": str(row["ingest_kind"]), "source_version": str(row["source_version"]),
            "source_date": text(row["source_date"]), "source_sha256": str(row["source_sha256"]),
            "source_locator": str(row["source_locator"]), "immutable_storage_locator": row["immutable_storage_locator"],
            "live_url": str(row["live_url"] or ""), "uploader_account_id": str(row["uploader_account_id"]),
            "replaces_snapshot_id": row["replaces_snapshot_id"], "object_diff": diff,
            "clinical_rereview_required": bool(row["clinical_rereview_required"]),
            "acquired_at": text(row["acquired_at"]), "console_version": str(row["console_version"]),
        }

    def _assert_existing_matches(
        self,
        con: Any,
        envelope: Mapping[str, Any],
        objects: list[dict[str, Any]],
    ) -> None:
        snapshot_id = str(envelope["snapshot_id"])
        row = con.execute("SELECT * FROM workflow.documents WHERE snapshot_id=%s", (snapshot_id,)).fetchone()
        if row is None:
            raise WorkflowDocumentStoreError("workflow_document_missing_after_conflict")
        if self._normalized_database_document(row) != self._document_projection(envelope):
            raise WorkflowDocumentStoreError("workflow_document_migration_conflict")
        reviewers = {
            str(item["account_id"])
            for item in con.execute(
                "SELECT account_id FROM workflow.document_reviewers WHERE snapshot_id=%s", (snapshot_id,)
            ).fetchall()
        }
        if reviewers != set(str(x) for x in envelope.get("named_reviewers") or []):
            raise WorkflowDocumentStoreError("workflow_document_reviewers_migration_conflict")
        db_objects = con.execute(
            "SELECT object_id,object_version,payload FROM workflow.document_objects WHERE snapshot_id=%s",
            (snapshot_id,),
        ).fetchall()
        expected = {(str(o["object_id"]), str(o["object_version"])): _json_text(o) for o in objects}
        actual = {
            (str(o["object_id"]), str(o["object_version"])): _json_text(o["payload"] if isinstance(o["payload"], dict) else json.loads(o["payload"]))
            for o in db_objects
        }
        if actual != expected:
            raise WorkflowDocumentStoreError("workflow_document_objects_migration_conflict")

    def create_document_bundle(
        self,
        *,
        envelope: Mapping[str, Any],
        objects: list[dict[str, Any]],
        allow_exact_existing: bool = False,
    ) -> bool:
        """Persist document + reviewer assignments + all work objects atomically."""
        values = self._document_values(envelope)
        snapshot_id = str(envelope["snapshot_id"])
        reviewers = [str(x) for x in envelope.get("named_reviewers") or []]
        identities = [(str(o.get("object_id") or ""), str(o.get("object_version") or "")) for o in objects]
        if any(not a or not b for a, b in identities) or len(set(identities)) != len(identities):
            raise WorkflowDocumentStoreError("workflow_object_identity_invalid")
        try:
            with self._connect() as con:
                with con.transaction():
                    existing = con.execute(
                        "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE", (snapshot_id,)
                    ).fetchone()
                    if existing:
                        if not allow_exact_existing:
                            raise WorkflowDocumentStoreError("workflow_document_already_exists")
                        self._assert_existing_matches(con, envelope, objects)
                        return False
                    con.execute(
                        "INSERT INTO workflow.documents("
                        "snapshot_id,source_id,document_id,title,family,class,state,publication_eligibility,content_kind,"
                        "ingest_kind,source_version,source_date,source_sha256,source_locator,immutable_storage_locator,"
                        "live_url,uploader_account_id,replaces_snapshot_id,object_diff,clinical_rereview_required,"
                        "acquired_at,console_version) VALUES("
                        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)",
                        values,
                    )
                    for reviewer in reviewers:
                        con.execute(
                            "INSERT INTO workflow.document_reviewers(snapshot_id,account_id) VALUES(%s,%s)",
                            (snapshot_id, reviewer),
                        )
                    for obj in objects:
                        con.execute(
                            "INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload) "
                            "VALUES(%s,%s,%s,%s::jsonb)",
                            (snapshot_id, obj["object_id"], obj["object_version"], _json_text(obj)),
                        )
            return True
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_bundle_write_failed") from exc

    def get_document(self, snapshot_id: str) -> dict[str, Any] | None:
        try:
            with self._connect() as con:
                row = con.execute("SELECT * FROM workflow.documents WHERE snapshot_id=%s", (snapshot_id,)).fetchone()
            return dict(row) if row else None
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_read_failed") from exc

    def list_document_objects(self, snapshot_id: str) -> list[dict[str, Any]]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT payload FROM workflow.document_objects WHERE snapshot_id=%s "
                    "ORDER BY object_id,object_version",
                    (snapshot_id,),
                ).fetchall()
            return [dict(row["payload"]) if isinstance(row["payload"], dict) else json.loads(row["payload"]) for row in rows]
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_objects_read_failed") from exc

    def migrate_legacy_runtime(self, runtime: Path) -> dict[str, int]:
        """Idempotently copy file-backed document work state into PostgreSQL.

        Exact replays are accepted. Any mismatch fails closed and existing database
        state is left authoritative; local files are never used as fallback here.
        """
        bundles = _read_legacy_runtime(Path(runtime))
        inserted = 0
        exact_existing = 0
        for bundle in bundles:
            created = self.create_document_bundle(
                envelope=bundle["envelope"],
                objects=bundle["objects"],
                allow_exact_existing=True,
            )
            if created:
                inserted += 1
            else:
                exact_existing += 1
        return {"documents": len(bundles), "inserted": inserted, "exact_existing": exact_existing}
