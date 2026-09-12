"""Full PostgreSQL workflow recovery layered onto the publication-chain backup.

This module deliberately reuses the existing publication-chain archive and Blob
restore guard. It adds the workflow schema to the same database snapshot and
restores workflow + canonical/publication state in one PostgreSQL transaction.
"""
from __future__ import annotations

import json
import zipfile
from typing import Any, Mapping

from src.integrity_kernel import stable_hash
from src.publication_chain_recovery_guard_v1 import (
    restore_publication_chain as _guarded_restore,
    verify_publication_chain_backup as _guarded_verify,
)
from src.publication_chain_recovery_v1 import (
    BACKUP_FORMAT,
    DB_TABLES,
    PublicationChainRecoveryError,
    PostgresPublicationBackupAdapter,
    _DB_COLUMNS,
    _DB_ORDER_BY,
    _json_safe,
    _utc_now,
    backup_publication_chain as _backup_chain,
    check_chain_integrity,
)

WORKFLOW_RECOVERY_VERSION = 1
WORKFLOW_TABLES = (
    "accounts",
    "sessions",
    "documents",
    "document_reviewers",
    "document_objects",
    "review_events",
    "publish_authorizations",
    "audit_records",
    "audit_secrets",
)

_WORKFLOW_COLUMNS: dict[str, tuple[str, ...]] = {
    "accounts": (
        "account_id", "username", "display_name", "roles", "password_salt",
        "password_hash", "created_at",
    ),
    "sessions": (
        "token_hash", "account_id", "created_at", "expires_at", "revoked_at",
    ),
    "documents": (
        "snapshot_id", "source_id", "document_id", "title", "family", "class",
        "state", "publication_eligibility", "content_kind", "ingest_kind",
        "source_version", "source_date", "source_sha256", "source_locator",
        "immutable_storage_locator", "live_url", "uploader_account_id",
        "replaces_snapshot_id", "object_diff", "clinical_rereview_required",
        "acquired_at", "console_version", "revision", "updated_at",
        "envelope_payload",
    ),
    "document_reviewers": ("snapshot_id", "account_id", "assigned_at"),
    "document_objects": (
        "snapshot_id", "object_id", "object_version", "payload", "revision",
        "updated_at", "position",
    ),
    "review_events": (
        "event_id", "snapshot_id", "object_id", "object_version", "event_type",
        "actor_account_id", "occurred_at", "details", "previous_event_hash",
        "event_hash", "actor_text", "event_payload",
    ),
    "publish_authorizations": (
        "authorization_id", "snapshot_id", "object_id", "object_version",
        "canonical_object_hash", "confirmed_object_type", "reviewer_account_id",
        "reviewer_display_name", "decision", "valid", "created_at", "position",
    ),
    "audit_records": (
        "audit_id", "audit_type", "title", "created_by", "created_at", "updated_at",
        "payload",
    ),
    "audit_secrets": ("secret_name", "secret_payload", "updated_at"),
}

_WORKFLOW_ORDER_BY: dict[str, str] = {
    "accounts": "account_id",
    "sessions": "token_hash",
    "documents": "snapshot_id",
    "document_reviewers": "snapshot_id,account_id",
    "document_objects": "snapshot_id,position NULLS LAST,object_id,object_version",
    "review_events": "event_id",
    "publish_authorizations": "snapshot_id,position NULLS LAST,authorization_id",
    "audit_records": "audit_id",
    "audit_secrets": "secret_name",
}

_WORKFLOW_JSON_COLUMNS = {
    "documents": {"object_diff", "envelope_payload"},
    "document_objects": {"payload"},
    "review_events": {"details", "event_payload"},
    "audit_records": {"payload"},
    "audit_secrets": {"secret_payload"},
}

_CANONICAL_JSON_COLUMNS = {
    "canonical_object_versions": {"canonical_json"},
    "audit_events": {"details"},
}


def _rows(state: Mapping[str, Any], table: str) -> list[dict[str, Any]]:
    tables = state.get("workflow_tables")
    if not isinstance(tables, Mapping):
        raise PublicationChainRecoveryError("workflow_backup_tables_missing")
    rows = tables.get(table)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise PublicationChainRecoveryError(f"workflow_backup_table_invalid:{table}")
    return [dict(row) for row in rows]


def _validate_workflow_shape(state: Mapping[str, Any]) -> None:
    if int(state.get("workflow_recovery_version") or 0) != WORKFLOW_RECOVERY_VERSION:
        raise PublicationChainRecoveryError("workflow_backup_version_invalid")
    tables = state.get("workflow_tables")
    if not isinstance(tables, Mapping):
        raise PublicationChainRecoveryError("workflow_backup_tables_missing")
    missing = [table for table in WORKFLOW_TABLES if table not in tables]
    if missing:
        raise PublicationChainRecoveryError("workflow_backup_tables_missing:" + ",".join(missing))
    for table in WORKFLOW_TABLES:
        _rows(state, table)


def check_workflow_integrity(state: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        _validate_workflow_shape(state)
    except PublicationChainRecoveryError as exc:
        return {"ok": False, "errors": [str(exc)]}

    accounts = {str(row.get("account_id") or "") for row in _rows(state, "accounts")}
    if "" in accounts:
        errors.append("workflow_account_id_missing")
    snapshots = {str(row.get("snapshot_id") or "") for row in _rows(state, "documents")}
    if "" in snapshots:
        errors.append("workflow_snapshot_id_missing")

    for row in _rows(state, "sessions"):
        if str(row.get("account_id") or "") not in accounts:
            errors.append(f"workflow_session_account_missing:{row.get('token_hash')}")

    for row in _rows(state, "documents"):
        sid = str(row.get("snapshot_id") or "")
        if str(row.get("uploader_account_id") or "") not in accounts:
            errors.append(f"workflow_document_uploader_missing:{sid}")
        replaces = str(row.get("replaces_snapshot_id") or "")
        if replaces and replaces not in snapshots:
            errors.append(f"workflow_document_replaces_missing:{sid}:{replaces}")
        if not isinstance(row.get("envelope_payload"), dict):
            errors.append(f"workflow_document_envelope_missing:{sid}")

    for row in _rows(state, "document_reviewers"):
        sid = str(row.get("snapshot_id") or "")
        if sid not in snapshots:
            errors.append(f"workflow_reviewer_snapshot_missing:{sid}")
        if str(row.get("account_id") or "") not in accounts:
            errors.append(f"workflow_reviewer_account_missing:{sid}")

    object_positions: set[tuple[str, int]] = set()
    for row in _rows(state, "document_objects"):
        sid = str(row.get("snapshot_id") or "")
        if sid not in snapshots:
            errors.append(f"workflow_object_snapshot_missing:{sid}")
        if not isinstance(row.get("payload"), dict):
            errors.append(f"workflow_object_payload_invalid:{sid}:{row.get('object_id')}")
        position = row.get("position")
        if position is None:
            errors.append(f"workflow_object_position_missing:{sid}:{row.get('object_id')}")
        else:
            key = (sid, int(position))
            if key in object_positions:
                errors.append(f"workflow_object_position_duplicate:{sid}:{position}")
            object_positions.add(key)

    previous: str | None = None
    for row in _rows(state, "review_events"):
        payload = row.get("event_payload")
        event_hash = str(row.get("event_hash") or "")
        if not isinstance(payload, dict):
            errors.append(f"workflow_review_payload_invalid:{row.get('event_id')}")
            continue
        body = dict(payload)
        payload_hash = str(body.pop("event_hash", ""))
        if payload_hash != event_hash or stable_hash(body) != event_hash:
            errors.append(f"workflow_review_hash_invalid:{row.get('event_id')}")
        if payload.get("previous_event_hash") != previous or row.get("previous_event_hash") != previous:
            errors.append(f"workflow_review_chain_invalid:{row.get('event_id')}")
        previous = event_hash
        actor_id = str(row.get("actor_account_id") or "")
        if actor_id and actor_id not in accounts:
            errors.append(f"workflow_review_actor_missing:{row.get('event_id')}")
        sid = str(row.get("snapshot_id") or "")
        if sid and sid not in snapshots:
            errors.append(f"workflow_review_snapshot_missing:{row.get('event_id')}")

    authorization_positions: set[tuple[str, int]] = set()
    for row in _rows(state, "publish_authorizations"):
        sid = str(row.get("snapshot_id") or "")
        if sid not in snapshots:
            errors.append(f"workflow_authorization_snapshot_missing:{sid}")
        if str(row.get("reviewer_account_id") or "") not in accounts:
            errors.append(f"workflow_authorization_reviewer_missing:{sid}")
        position = row.get("position")
        if position is None:
            errors.append(f"workflow_authorization_position_missing:{sid}")
        else:
            key = (sid, int(position))
            if key in authorization_positions:
                errors.append(f"workflow_authorization_position_duplicate:{sid}:{position}")
            authorization_positions.add(key)

    for row in _rows(state, "audit_records"):
        if str(row.get("created_by") or "") not in accounts:
            errors.append(f"workflow_audit_creator_missing:{row.get('audit_id')}")
        if not isinstance(row.get("payload"), dict):
            errors.append(f"workflow_audit_payload_invalid:{row.get('audit_id')}")
    for row in _rows(state, "audit_secrets"):
        if not isinstance(row.get("secret_payload"), dict):
            errors.append(f"workflow_audit_secret_payload_invalid:{row.get('secret_name')}")

    return {
        "ok": not errors,
        "errors": errors,
        "accounts": len(accounts),
        "documents": len(snapshots),
        "review_events": len(_rows(state, "review_events")),
        "authorizations": len(_rows(state, "publish_authorizations")),
        "audits": len(_rows(state, "audit_records")),
    }


def _insert_rows(con: Any, *, schema: str | None, table: str, rows: list[dict[str, Any]], columns: tuple[str, ...], json_columns: set[str]) -> None:
    if not rows:
        return
    target = f"{schema}.{table}" if schema else table
    placeholders = ["%s::jsonb" if column in json_columns else "%s" for column in columns]
    sql = f"INSERT INTO {target}({','.join(columns)}) VALUES({','.join(placeholders)})"
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column)
            if column in json_columns and value is not None:
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            values.append(value)
        con.execute(sql, tuple(values))


class PostgresWorkflowRecoveryAdapter(PostgresPublicationBackupAdapter):
    """One logical backup/restore boundary for canonical + workflow PostgreSQL."""

    def _verify_workflow_schema(self, con: Any) -> None:
        rows = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='workflow'"
        ).fetchall()
        present = {str(row["table_name"]) for row in rows}
        missing = sorted(set(WORKFLOW_TABLES) - present)
        if missing:
            raise PublicationChainRecoveryError("workflow_recovery_schema_missing:" + ",".join(missing))
        for table, columns in _WORKFLOW_COLUMNS.items():
            rows = con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='workflow' AND table_name=%s",
                (table,),
            ).fetchall()
            present_columns = {str(row["column_name"]) for row in rows}
            missing_columns = sorted(set(columns) - present_columns)
            if missing_columns:
                raise PublicationChainRecoveryError(
                    f"workflow_recovery_columns_missing:{table}:" + ",".join(missing_columns)
                )

    def export_state(self) -> dict[str, Any]:
        try:
            self.store.verify_schema()
            with self.store._connect() as con:
                with con.transaction():
                    con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                    self._verify_workflow_schema(con)
                    tables: dict[str, list[dict[str, Any]]] = {}
                    for table in DB_TABLES:
                        rows = con.execute(
                            f"SELECT {','.join(_DB_COLUMNS[table])} FROM {table} ORDER BY {_DB_ORDER_BY[table]}"
                        ).fetchall()
                        tables[table] = [_json_safe(dict(row)) for row in rows]
                    workflow_tables: dict[str, list[dict[str, Any]]] = {}
                    for table in WORKFLOW_TABLES:
                        rows = con.execute(
                            f"SELECT {','.join(_WORKFLOW_COLUMNS[table])} FROM workflow.{table} ORDER BY {_WORKFLOW_ORDER_BY[table]}"
                        ).fetchall()
                        workflow_tables[table] = [_json_safe(dict(row)) for row in rows]
        except PublicationChainRecoveryError:
            raise
        except Exception as exc:
            raise PublicationChainRecoveryError("workflow_database_backup_export_failed") from exc
        state = {
            "format": BACKUP_FORMAT,
            "exported_at": _utc_now(),
            "tables": tables,
            "workflow_recovery_version": WORKFLOW_RECOVERY_VERSION,
            "workflow_tables": workflow_tables,
        }
        report = check_workflow_integrity(state)
        if not report["ok"]:
            raise PublicationChainRecoveryError("workflow_backup_integrity_failed:" + ";".join(report["errors"]))
        return state

    def assert_empty(self) -> None:
        try:
            self.store.verify_schema()
            with self.store._connect() as con:
                self._verify_workflow_schema(con)
                nonempty: list[str] = []
                for table in DB_TABLES:
                    count = int(con.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
                    if count:
                        nonempty.append(f"{table}:{count}")
                for table in WORKFLOW_TABLES:
                    count = int(con.execute(f"SELECT COUNT(*) AS n FROM workflow.{table}").fetchone()["n"])
                    if count:
                        nonempty.append(f"workflow.{table}:{count}")
        except PublicationChainRecoveryError:
            raise
        except Exception as exc:
            raise PublicationChainRecoveryError("workflow_database_restore_preflight_failed") from exc
        if nonempty:
            raise PublicationChainRecoveryError("database_restore_target_not_empty:" + ",".join(nonempty))

    def restore_state(self, state: Mapping[str, Any]) -> None:
        from src.publication_chain_recovery_v1 import _validate_database_backup_shape, _table_rows

        _validate_database_backup_shape(state)
        _validate_workflow_shape(state)
        workflow_report = check_workflow_integrity(state)
        if not workflow_report["ok"]:
            raise PublicationChainRecoveryError("workflow_restore_integrity_failed:" + ";".join(workflow_report["errors"]))
        self.assert_empty()

        canonical_rows = {table: _table_rows(state, table) for table in DB_TABLES}
        workflow_rows = {table: _rows(state, table) for table in WORKFLOW_TABLES}
        try:
            with self.store._connect() as con:
                with con.transaction():
                    self._verify_workflow_schema(con)
                    _insert_rows(
                        con, schema="workflow", table="accounts", rows=workflow_rows["accounts"],
                        columns=_WORKFLOW_COLUMNS["accounts"], json_columns=set(),
                    )
                    _insert_rows(
                        con, schema="workflow", table="sessions", rows=workflow_rows["sessions"],
                        columns=_WORKFLOW_COLUMNS["sessions"], json_columns=set(),
                    )

                    document_rows = workflow_rows["documents"]
                    document_columns = _WORKFLOW_COLUMNS["documents"]
                    for row in document_rows:
                        first = dict(row)
                        first["replaces_snapshot_id"] = None
                        _insert_rows(
                            con, schema="workflow", table="documents", rows=[first],
                            columns=document_columns, json_columns=_WORKFLOW_JSON_COLUMNS["documents"],
                        )
                    for row in document_rows:
                        if row.get("replaces_snapshot_id"):
                            con.execute(
                                "UPDATE workflow.documents SET replaces_snapshot_id=%s WHERE snapshot_id=%s",
                                (row["replaces_snapshot_id"], row["snapshot_id"]),
                            )

                    for table in (
                        "document_reviewers", "document_objects", "review_events",
                        "publish_authorizations", "audit_records", "audit_secrets",
                    ):
                        _insert_rows(
                            con, schema="workflow", table=table, rows=workflow_rows[table],
                            columns=_WORKFLOW_COLUMNS[table], json_columns=_WORKFLOW_JSON_COLUMNS.get(table, set()),
                        )

                    for table in DB_TABLES:
                        _insert_rows(
                            con, schema=None, table=table, rows=canonical_rows[table],
                            columns=_DB_COLUMNS[table], json_columns=_CANONICAL_JSON_COLUMNS.get(table, set()),
                        )

                    for table, column in (
                        ("workflow.review_events", "event_id"),
                        ("workflow.publish_authorizations", "authorization_id"),
                        ("audit_events", "event_id"),
                    ):
                        row = con.execute(f"SELECT MAX({column}) AS n FROM {table}").fetchone()
                        if row and row["n"] is not None:
                            con.execute(
                                "SELECT setval(pg_get_serial_sequence(%s,%s), %s, true)",
                                (table, column, int(row["n"])),
                            )
        except PublicationChainRecoveryError:
            raise
        except Exception as exc:
            raise PublicationChainRecoveryError("workflow_database_restore_failed") from exc


def verify_workflow_chain_backup(archive: Any) -> dict[str, Any]:
    base = _guarded_verify(archive)
    errors = list(base.get("errors") or [])
    if errors:
        return {"ok": False, "errors": errors}
    try:
        with zipfile.ZipFile(archive) as zipf:
            state = json.loads(zipf.read("database.json").decode("utf-8"))
        report = check_workflow_integrity(state)
        errors.extend(report["errors"])
    except Exception as exc:
        errors.append(f"workflow_backup_verification_failed:{type(exc).__name__}")
    return {"ok": not errors, "errors": errors}


def backup_workflow_chain(archive: Any, *, database: PostgresWorkflowRecoveryAdapter, source_store: Any, runtime_root: Any = None) -> dict[str, Any]:
    manifest = _backup_chain(
        archive,
        database=database,
        source_store=source_store,
        runtime_root=runtime_root,
    )
    verification = verify_workflow_chain_backup(archive)
    if not verification["ok"]:
        raise PublicationChainRecoveryError("workflow_chain_backup_verification_failed:" + ";".join(verification["errors"]))
    return manifest


def restore_workflow_chain(archive: Any, *, database: PostgresWorkflowRecoveryAdapter, source_store: Any, runtime_dest: Any = None) -> dict[str, Any]:
    verification = verify_workflow_chain_backup(archive)
    if not verification["ok"]:
        raise PublicationChainRecoveryError("workflow_chain_restore_backup_invalid:" + ";".join(verification["errors"]))
    result = _guarded_restore(
        archive,
        database=database,
        source_store=source_store,
        runtime_dest=runtime_dest,
    )
    restored = database.export_state()
    workflow = check_workflow_integrity(restored)
    canonical = check_chain_integrity(restored, source_store=source_store, runtime_root=runtime_dest)
    if not workflow["ok"] or not canonical["ok"]:
        raise PublicationChainRecoveryError(
            "workflow_chain_restore_integrity_failed:" + ";".join(workflow["errors"] + canonical["errors"])
        )
    result["workflow_integrity"] = workflow
    return result


def live_workflow_chain_integrity(*, database: PostgresWorkflowRecoveryAdapter, source_store: Any, runtime_root: Any = None) -> dict[str, Any]:
    state = database.export_state()
    canonical = check_chain_integrity(state, source_store=source_store, runtime_root=runtime_root)
    workflow = check_workflow_integrity(state)
    return {
        "ok": bool(canonical["ok"] and workflow["ok"]),
        "errors": list(canonical["errors"]) + list(workflow["errors"]),
        "publication": canonical,
        "workflow": workflow,
    }
