"""Full PostgreSQL workflow recovery layered onto the publication-chain backup.

This module deliberately reuses the existing publication-chain archive and Blob
restore guard. It adds the workflow schema to the same database snapshot and
restores workflow + canonical/publication state in one PostgreSQL transaction.
"""
from __future__ import annotations

import json
import zipfile
from contextlib import nullcontext
from graphlib import CycleError, TopologicalSorter
from typing import Any, Mapping
from uuid import UUID

from src.api_access_v1 import (
    NULLABLE_COLUMNS as API_ACCESS_NULLABLE_COLUMNS,
    REQUIRED_COLUMNS as API_ACCESS_COLUMNS,
    REQUIRED_KEYS as API_ACCESS_KEYS,
    ApiAccessStoreError,
    PostgresApiAccessStore,
)
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
    _audit_entries_from_state,
    _audit_store,
    _verify_audit_data,
    _utc_now,
    backup_publication_chain as _backup_chain,
    check_chain_integrity,
)

WORKFLOW_RECOVERY_VERSION = 5
API_ACCESS_TABLES = tuple(API_ACCESS_COLUMNS)
_API_ACCESS_ORDER_BY = {
    table: ",".join(columns)
    for table, kind, columns, _parent, _parent_columns in API_ACCESS_KEYS
    if kind == "p"
}
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
        "password_hash", "created_at", "retirement",
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
        "logical_document_id", "working_revision_id", "working_revision_number",
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
        "payload", "retention_state",
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


def _rows(state: Mapping[str, Any], table: str, *, group: str = "workflow") -> list[dict[str, Any]]:
    tables = state.get(f"{group}_tables")
    if not isinstance(tables, Mapping):
        raise PublicationChainRecoveryError(f"{group}_backup_tables_missing")
    rows = tables.get(table)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise PublicationChainRecoveryError(f"{group}_backup_table_invalid:{table}")
    return [dict(row) for row in rows]


def _validate_workflow_shape(state: Mapping[str, Any]) -> None:
    if state.get("workflow_recovery_version") == 1:
        raise PublicationChainRecoveryError("workflow_backup_lifecycle_identity_missing:reexport_required")
    if state.get("workflow_recovery_version") == 2:
        raise PublicationChainRecoveryError("workflow_backup_api_access_missing:reexport_required")
    if state.get("workflow_recovery_version") == 3:
        raise PublicationChainRecoveryError("workflow_backup_audit_retention_missing:reexport_required")
    if state.get("workflow_recovery_version") == 4:
        raise PublicationChainRecoveryError("workflow_backup_account_retirement_missing:reexport_required")
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
    _audit_entries_from_state(state)


def _validate_api_access(state: Mapping[str, Any]) -> None:
    """Use the existing access schema contract, without creating new grants."""
    tables = {table: _rows(state, table, group="api_access") for table in API_ACCESS_TABLES}
    for table, rows in tables.items():
        for row in rows:
            if set(row) != set(API_ACCESS_COLUMNS[table]):
                raise PublicationChainRecoveryError(f"api_access_backup_columns_invalid:{table}")
            for column in API_ACCESS_COLUMNS[table]:
                if row[column] is None and (table, column) not in API_ACCESS_NULLABLE_COLUMNS:
                    raise PublicationChainRecoveryError(f"api_access_backup_value_missing:{table}:{column}")
    for table, kind, columns, parent, parent_columns in API_ACCESS_KEYS:
        values = [tuple(row[column] for column in columns) for row in tables[table]]
        if kind in {"p", "u"}:
            if any(any(not isinstance(value, str) or not value for value in key) for key in values):
                raise PublicationChainRecoveryError(f"api_access_backup_key_invalid:{table}")
            if len(set(values)) != len(values):
                raise PublicationChainRecoveryError(f"api_access_backup_key_duplicate:{table}")
        elif kind == "f":
            targets = {tuple(row[column] for column in parent_columns) for row in tables[parent]}
            if any(key not in targets for key in values):
                raise PublicationChainRecoveryError(f"api_access_backup_reference_missing:{table}:{parent}")
    for row in tables["credentials"]:
        digest = row["secret_sha256"]
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise PublicationChainRecoveryError("api_access_backup_credential_hash_invalid")
    if any(not isinstance(row["details"], dict) for row in tables["audit_events"]):
        raise PublicationChainRecoveryError("api_access_backup_audit_details_invalid")


def _ordered_documents(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Validate authoritative identities, then order the exact rows for import."""
    documents = _rows(state, "documents")
    by_id = {row.get("snapshot_id"): row for row in documents}
    if len(by_id) != len(documents):
        raise PublicationChainRecoveryError("workflow_snapshot_id_duplicate")
    work_ids: set[str] = set()
    revisions: set[tuple[str, int]] = set()
    graph: dict[str, set[str]] = {}
    for row in documents:
        sid = row.get("snapshot_id")
        logical = row.get("logical_document_id")
        work = row.get("working_revision_id")
        number = row.get("working_revision_number")
        if any(not isinstance(value, str) or not value.strip() for value in (sid, logical, work)):
            raise PublicationChainRecoveryError(f"workflow_lifecycle_identity_missing:{sid}")
        if type(number) is not int or number < 1:
            raise PublicationChainRecoveryError(f"workflow_revision_number_invalid:{sid}")
        if work in work_ids or (logical, number) in revisions:
            raise PublicationChainRecoveryError(f"workflow_lifecycle_identity_duplicate:{sid}")
        work_ids.add(work)
        revisions.add((logical, number))
        envelope = row.get("envelope_payload")
        projection = {
            "snapshot_id": sid, "source_snapshot_id": sid,
            "logical_document_id": logical, "working_revision_id": work,
            "working_revision_number": number, "source_version": row.get("source_version"),
            "replaces_snapshot_id": row.get("replaces_snapshot_id"),
        }
        if not isinstance(envelope, dict) or any(envelope.get(key) != value for key, value in projection.items()):
            raise PublicationChainRecoveryError(f"workflow_lifecycle_projection_mismatch:{sid}")
        predecessor = row.get("replaces_snapshot_id")
        if row.get("ingest_kind") == "new_version" and not predecessor:
            raise PublicationChainRecoveryError(f"workflow_document_predecessor_required:{sid}")
        if predecessor:
            parent = by_id.get(predecessor)
            if parent is None:
                raise PublicationChainRecoveryError(f"workflow_document_replaces_missing:{sid}:{predecessor}")
            if parent.get("logical_document_id") != logical:
                raise PublicationChainRecoveryError(f"workflow_document_lineage_mismatch:{sid}")
        graph[sid] = {predecessor} if predecessor else set()
    try:
        return [by_id[sid] for sid in TopologicalSorter(graph).static_order()]
    except CycleError as exc:
        raise PublicationChainRecoveryError("workflow_document_lineage_cycle") from exc


def check_workflow_integrity(state: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        _validate_workflow_shape(state)
        _ordered_documents(state)
        _validate_api_access(state)
    except PublicationChainRecoveryError as exc:
        return {"ok": False, "errors": [str(exc)]}

    accounts = {str(row.get("account_id") or "") for row in _rows(state, "accounts")}
    if "" in accounts:
        errors.append("workflow_account_id_missing")
    retired = set()
    for row in _rows(state, "accounts"):
        evidence = row.get("retirement")
        if "retirement" not in row:
            errors.append("workflow_account_retirement_missing")
        if evidence is not None:
            if (not isinstance(evidence, dict) or evidence.get("actor") not in accounts
                    or not evidence.get("reason") or not evidence.get("at")
                    or row.get("password_hash") or row.get("password_salt")):
                errors.append("workflow_account_retirement_invalid")
            retired.add(row.get("account_id"))
    for row in _rows(state, "sessions"):
        if row.get("account_id") in retired and row.get("revoked_at") is None:
            errors.append("workflow_retired_account_session_active")
    entra_rows = state.get("entra_identities", [])
    if not isinstance(entra_rows, list):
        errors.append("entra_identity_backup_invalid")
        entra_rows = []
    seen_accounts, seen_principals = set(), set()
    for row in entra_rows:
        if not isinstance(row, dict):
            errors.append("entra_identity_backup_invalid")
            continue
        aid = row.get("account_id")
        try:
            principal = (str(UUID(row["tenant_id"])), str(UUID(row["object_id"])))
            if (not isinstance(aid, str) or aid not in accounts or aid in seen_accounts or principal in seen_principals
                    or not isinstance(row.get("blocked"), bool) or not isinstance(row.get("evidence"), list)):
                raise ValueError()
            seen_accounts.add(aid)
            seen_principals.add(principal)
        except (KeyError, ValueError, TypeError, AttributeError):
            errors.append("entra_identity_backup_invalid")
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
        "api_access": {table: len(_rows(state, table, group="api_access")) for table in API_ACCESS_TABLES},
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
        # Borrow the same connection/snapshot; the access store's schema check
        # must not close or commit the surrounding recovery transaction.
        try:
            PostgresApiAccessStore(
                self.store.config, connection_factory=lambda: nullcontext(con)
            ).verify_schema()
        except ApiAccessStoreError as exc:
            raise PublicationChainRecoveryError(str(exc)) from exc
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
                    snapshot_at = _json_safe(con.execute("SELECT clock_timestamp() AS moment").fetchone()["moment"])
                    self._verify_workflow_schema(con)
                    tables: dict[str, list[dict[str, Any]]] = {}
                    for table in DB_TABLES:
                        rows = con.execute(
                            f"SELECT {','.join(_DB_COLUMNS[table])} FROM {table} ORDER BY {_DB_ORDER_BY[table]}"
                        ).fetchall()
                        tables[table] = [_json_safe(dict(row)) for row in rows]
                    workflow_tables: dict[str, list[dict[str, Any]]] = {}
                    for table in WORKFLOW_TABLES:
                        select_columns = [
                            "source_date::text AS source_date" if table == "documents" and column == "source_date" else column
                            for column in _WORKFLOW_COLUMNS[table]
                        ]
                        rows = con.execute(
                            f"SELECT {','.join(select_columns)} FROM workflow.{table} ORDER BY {_WORKFLOW_ORDER_BY[table]}"
                        ).fetchall()
                        workflow_tables[table] = [_json_safe(dict(row)) for row in rows]
                    entra_rows = []
                    if con.execute("SELECT to_regclass('workflow.entra_identities') AS name").fetchone()["name"]:
                        entra_rows = [_json_safe(dict(r)) for r in con.execute(
                            "SELECT tenant_id::text AS tenant_id,object_id::text AS object_id,account_id,blocked,evidence FROM workflow.entra_identities ORDER BY account_id"
                        ).fetchall()]
                    access_tables: dict[str, list[dict[str, Any]]] = {}
                    for table in API_ACCESS_TABLES:
                        rows = con.execute(
                            f"SELECT {','.join(API_ACCESS_COLUMNS[table])} FROM api_access.{table} "
                            f"ORDER BY {_API_ACCESS_ORDER_BY[table]}"
                        ).fetchall()
                        access_tables[table] = [_json_safe(dict(row)) for row in rows]
        except PublicationChainRecoveryError:
            raise
        except Exception as exc:
            raise PublicationChainRecoveryError("workflow_database_backup_export_failed") from exc
        state = {
            "format": BACKUP_FORMAT,
            "exported_at": _utc_now(),
            "snapshot_at": snapshot_at,
            "tables": tables,
            "workflow_recovery_version": WORKFLOW_RECOVERY_VERSION,
            "workflow_tables": workflow_tables,
            "api_access_tables": access_tables,
            "entra_identities": entra_rows,
        }
        report = check_workflow_integrity(state)
        if not report["ok"]:
            raise PublicationChainRecoveryError("workflow_backup_integrity_failed:" + ";".join(report["errors"]))
        return state

    def _assert_empty(self, con: Any) -> None:
        nonempty: list[str] = []
        for table in (
            *DB_TABLES, *(f"workflow.{table}" for table in WORKFLOW_TABLES),
            *(f"api_access.{table}" for table in API_ACCESS_TABLES),
        ):
            count = int(con.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            if count:
                nonempty.append(f"{table}:{count}")
        if nonempty:
            raise PublicationChainRecoveryError("database_restore_target_not_empty:" + ",".join(nonempty))

    def assert_empty(self) -> None:
        try:
            self.store.verify_schema()
            with self.store._connect() as con:
                self._verify_workflow_schema(con)
                self._assert_empty(con)
        except PublicationChainRecoveryError:
            raise
        except Exception as exc:
            raise PublicationChainRecoveryError("workflow_database_restore_preflight_failed") from exc

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
                    has_entra = bool(con.execute("SELECT to_regclass('workflow.entra_identities') AS name").fetchone()["name"])
                    if state.get("entra_identities") and not has_entra:
                        raise PublicationChainRecoveryError("entra_restore_schema_required")
                    if has_entra:
                        con.execute("LOCK TABLE workflow.entra_identities,workflow.entra_sessions,workflow.entra_flows IN ACCESS EXCLUSIVE MODE")
                        for table in ("entra_identities", "entra_sessions", "entra_flows"):
                            if con.execute(f"SELECT 1 FROM workflow.{table} LIMIT 1").fetchone():
                                raise PublicationChainRecoveryError("entra_restore_target_not_empty")
                    # Offline, empty-target import. Locks and trigger DDL share
                    # the data transaction: other writers cannot enter it, and
                    # a failed import restores the allocator automatically.
                    targets = (
                        *DB_TABLES, *(f"workflow.{table}" for table in WORKFLOW_TABLES),
                        *(f"api_access.{table}" for table in API_ACCESS_TABLES),
                    )
                    con.execute("LOCK TABLE " + ",".join(targets) + " IN ACCESS EXCLUSIVE MODE")
                    self._assert_empty(con)
                    trigger = con.execute(
                        "SELECT tgenabled FROM pg_trigger WHERE tgrelid='workflow.documents'::regclass "
                        "AND tgname='trg_workflow_documents_lifecycle_identity'"
                    ).fetchone()
                    if not trigger or trigger["tgenabled"] != "O":
                        raise PublicationChainRecoveryError("workflow_restore_identity_trigger_invalid")
                    con.execute(
                        "ALTER TABLE workflow.documents DISABLE TRIGGER trg_workflow_documents_lifecycle_identity"
                    )
                    _insert_rows(
                        con, schema="workflow", table="accounts", rows=workflow_rows["accounts"],
                        columns=_WORKFLOW_COLUMNS["accounts"], json_columns={"retirement"},
                    )
                    if state.get("entra_identities"):
                        _insert_rows(
                            con, schema="workflow", table="entra_identities", rows=state["entra_identities"],
                            columns=("tenant_id", "object_id", "account_id", "blocked", "evidence"), json_columns={"evidence"},
                        )
                    # No Entra handshake/session markers restored: fresh sign-in required.
                    _insert_rows(
                        con, schema="workflow", table="sessions", rows=workflow_rows["sessions"],
                        columns=_WORKFLOW_COLUMNS["sessions"], json_columns=set(),
                    )

                    _insert_rows(
                        con, schema="workflow", table="documents", rows=_ordered_documents(state),
                        columns=_WORKFLOW_COLUMNS["documents"], json_columns=_WORKFLOW_JSON_COLUMNS["documents"],
                    )
                    con.execute(
                        "ALTER TABLE workflow.documents ENABLE TRIGGER trg_workflow_documents_lifecycle_identity"
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

                    for table in API_ACCESS_TABLES:
                        _insert_rows(
                            con, schema="api_access", table=table,
                            rows=_rows(state, table, group="api_access"), columns=tuple(API_ACCESS_COLUMNS[table]),
                            json_columns={"details"} if table == "audit_events" else set(),
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


def backup_workflow_chain(archive: Any, *, database: PostgresWorkflowRecoveryAdapter, source_store: Any, runtime_root: Any = None, audit_archive_store: Any = None) -> dict[str, Any]:
    from src.workflows.workflow_remaining_postgres_v1 import audit_retention_lock

    # Keep archived bytes stable from the database snapshot through Blob read.
    with audit_retention_lock(database.store._connect):
        manifest = _backup_chain(
            archive, database=database, source_store=source_store,
            runtime_root=runtime_root, audit_archive_store=audit_archive_store,
        )
    verification = verify_workflow_chain_backup(archive)
    if not verification["ok"]:
        raise PublicationChainRecoveryError("workflow_chain_backup_verification_failed:" + ";".join(verification["errors"]))
    return manifest


def restore_workflow_chain(archive: Any, *, database: PostgresWorkflowRecoveryAdapter, source_store: Any, runtime_dest: Any = None, audit_archive_store: Any = None) -> dict[str, Any]:
    verification = verify_workflow_chain_backup(archive)
    if not verification["ok"]:
        raise PublicationChainRecoveryError("workflow_chain_restore_backup_invalid:" + ";".join(verification["errors"]))
    result = _guarded_restore(
        archive,
        database=database,
        source_store=source_store,
        runtime_dest=runtime_dest,
        audit_archive_store=audit_archive_store,
    )
    restored = database.export_state()
    with zipfile.ZipFile(archive) as zipf:
        expected = json.loads(zipf.read("database.json").decode("utf-8"))
    for group in ("workflow_tables", "api_access_tables"):
        if stable_hash(restored[group]) != stable_hash(expected[group]):
            raise PublicationChainRecoveryError(f"{group}_restore_roundtrip_mismatch")
    workflow = check_workflow_integrity(restored)
    canonical = check_chain_integrity(restored, source_store=source_store, runtime_root=runtime_dest)
    if not workflow["ok"] or not canonical["ok"]:
        raise PublicationChainRecoveryError(
            "workflow_chain_restore_integrity_failed:" + ";".join(workflow["errors"] + canonical["errors"])
        )
    result["workflow_integrity"] = workflow
    return result


def live_workflow_chain_integrity(*, database: PostgresWorkflowRecoveryAdapter, source_store: Any, runtime_root: Any = None, audit_archive_store: Any = None) -> dict[str, Any]:
    from src.workflows.workflow_remaining_postgres_v1 import audit_retention_lock

    with audit_retention_lock(database.store._connect):
        state = database.export_state()
        entries = _audit_entries_from_state(state)
        audit_archive_store = _audit_store(audit_archive_store, entries)
        for entry in entries:
            _verify_audit_data(state, entry, audit_archive_store.load_verified(
                entry["locator"], expected_sha256=entry["sha256"],
            ))
    canonical = check_chain_integrity(state, source_store=source_store, runtime_root=runtime_root)
    workflow = check_workflow_integrity(state)
    return {
        "ok": bool(canonical["ok"] and workflow["ok"]),
        "errors": list(canonical["errors"]) + list(workflow["errors"]),
        "publication": canonical,
        "workflow": workflow,
    }
