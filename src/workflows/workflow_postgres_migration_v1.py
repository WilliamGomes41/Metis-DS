"""Controlled application and verification of the registered workflow migrations."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from azure.identity import DefaultAzureCredential

from src.publication.canonical_publication_postgres_v1 import AZURE_POSTGRES_SCOPE


MIGRATION_NAMES = (
    "002_workflow_schema.sql",
    "003_workflow_document_envelope_payload.sql",
    "004_workflow_review_authority.sql",
    "005_workflow_remaining_authority.sql",
    "006_workflow_authorization_payload.sql",
    "008_workflow_lifecycle_identity.sql",
    "009_console_hotpath_indexes.sql",
    "011_workflow_audit_retention.sql",
    "012_console_entra_identity.sql",
    "013_quality_measurements.sql",
    "014_route_comparisons.sql",
    "015_historical_accounts.sql",
    "016_workflow_topic_identity.sql",
    "018_publication_refusal_audit.sql",
    "019_view_checks.sql",
    "020_source_selection_summary.sql",
    "021_formation_task_records.sql",
    "022_formation_task_plans.sql",
    "023_formation_source_views.sql",
    "024_review_dependency_lookup.sql",
    "025_review_interaction_identity_lookup.sql",
    "026_review_source_records.sql",
)
REQUIRED_TABLES = frozenset(
    {
        "accounts",
        "sessions",
        "documents",
        "topics",
        "document_reviewers",
        "document_objects",
        "review_events",
        "publish_authorizations",
        "audit_records",
        "audit_secrets",
        "entra_identities",
        "entra_sessions",
        "entra_flows",
        "route_comparisons",
        "publication_refusals",
        "source_read_roots", "source_read_fragments", "source_read_blocks", "source_read_block_fragments",
    }
)
REFUSAL_COLUMNS = (
    "refusal_id", "recorded_at", "snapshot_id", "object_version", "actor", "verdict",
    "reason_codes", "revision_sha256", "dedup_key", "schema_version",
)
# Named constraints the runtime depends on (ON CONFLICT (dedup_key) needs the UNIQUE).
# (table, name, contype, columns): ON CONFLICT (dedup_key) needs UNIQUE(dedup_key) on exactly this
# table; a same-named constraint elsewhere, a non-unique one or other columns MAG NIET pass (4291505169).
REQUIRED_CONSTRAINTS = frozenset({("publication_refusals", "publication_refusals_dedup_key_uniq", "u", ("dedup_key",))})
REQUIRED_COLUMNS = frozenset(
    {
        ("documents", "review_source_ref"),
        ("documents", "review_read_envelope"),
        *(("publication_refusals", column) for column in REFUSAL_COLUMNS),
        ("accounts", "retirement"),
        ("documents", "envelope_payload"),
        ("documents", "logical_document_id"),
        ("documents", "working_revision_id"),
        ("documents", "working_revision_number"),
        ("documents", "topic_id"),
        ("topics", "identity_key"),
        ("topics", "display_name"),
        ("document_objects", "position"),
        ("review_events", "actor_text"),
        ("review_events", "event_payload"),
        ("publish_authorizations", "position"),
        ("publish_authorizations", "authorization_payload"),
        ("audit_records", "retention_state"),
    }
)

# Least privileges the console runtime uses per table created by a registered migration
# (#930). `GRANT ... ON ALL TABLES` misses later tables, so verify checks these explicitly.
_S, _I, _U, _D = "SELECT", "INSERT", "UPDATE", "DELETE"
RUNTIME_TABLE_PRIVILEGES = {
    "accounts": (_S, _I, _U),
    "sessions": (_S, _I, _U, _D),
    "documents": (_S, _I, _U, _D),
    "topics": (_S, _I),
    "document_reviewers": (_S, _I, _D),
    "document_objects": (_S, _I, _U, _D),
    "review_events": (_S, _I, _U),
    "publish_authorizations": (_S, _I, _U, _D),
    "audit_records": (_S, _I, _U, _D),
    "audit_secrets": (_S, _I, _U),
    "entra_identities": (_S, _I, _U),
    "entra_sessions": (_S, _I),
    "entra_flows": (_S, _I, _D),
    "quality_measurements": (_S, _I, _U),
    "route_comparisons": (_S, _I, _U),
    "publication_refusals": (_S, _I, _D),
    "view_checks": (_S, _I, _U),
    "processing_attempts": (_S, _I, _U),
    "processing_document_summaries": (_S, _I, _U),
    "processing_checkpoints": (_S, _I),
    "prepared_extraction_versions": (_S, _I),
    "formation_inputs": (_S, _I),
    "formation_contexts": (_S, _I, _U),
    "formation_task_results": (_S, _I, _U),
    "formation_task_findings": (_S, _I),
    "formation_task_result_history": (_S, _I),
    "formation_task_plans": (_S, _I),
    "formation_source_views": (_S, _I),
    "source_read_roots": (_S, _I, _U),
    "source_read_fragments": (_S, _I),
    "source_read_blocks": (_S, _I),
    "source_read_block_fragments": (_S, _I),
}
# Serial sequences the runtime advances on INSERT (identity columns need no grant).
RUNTIME_SEQUENCE_PRIVILEGES = {
    "review_events_event_id_seq": ("USAGE",),
    "publish_authorizations_authorization_id_seq": ("USAGE",),
    "publication_refusals_refusal_id_seq": ("USAGE",),
}
# Only required when the view check is enabled (METIS_VIEW_CHECK_ORIGIN).
VIEW_CHECK_TABLES = frozenset({"view_checks"})
# Tables from migrations applied outside MIGRATION_NAMES (027, compact review cards).
# Checked whenever present: their triggers write them on every document mutation.
OPTIONAL_MIGRATION_TABLES = {"027_review_card_facts.sql": ("review_fact_state", "review_object_facts")}
OPTIONAL_TABLE_PRIVILEGES = {
    "review_fact_state": (_S, _I, _U),
    "review_object_facts": (_S, _I, _U),
}


class WorkflowMigrationError(RuntimeError):
    """Migration target, digest, connectivity, or schema verification failure."""


def migration_paths(root: Path) -> tuple[Path, ...]:
    paths = tuple(root / "db" / "migrations" / name for name in MIGRATION_NAMES)
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise WorkflowMigrationError("workflow_migration_files_missing:" + ",".join(missing))
    return paths


def migration_digest(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        data = path.read_bytes()
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def connect_entra(*, host: str, database: str, user: str, credential: Any | None = None) -> Any:
    if not host.strip() or not database.strip() or not user.strip():
        raise WorkflowMigrationError("workflow_migration_target_incomplete")
    try:
        import psycopg
        from psycopg.rows import dict_row

        token = (credential or DefaultAzureCredential()).get_token(AZURE_POSTGRES_SCOPE).token
        return psycopg.connect(
            host=host,
            dbname=database,
            user=user,
            password=token,
            sslmode="require",
            connect_timeout=10,
            row_factory=dict_row,
        )
    except WorkflowMigrationError:
        raise
    except Exception as exc:
        raise WorkflowMigrationError("workflow_migration_postgres_unavailable") from exc


def observe_schema(connection: Any) -> dict[str, Any]:
    """Read schema shape and row counts; never expose row contents."""
    try:
        identity = connection.execute(
            "SELECT current_database() AS database, current_user AS user"
        ).fetchone()
        table_rows = connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='workflow' AND table_type='BASE TABLE'"
        ).fetchall()
        column_rows = connection.execute(
            "SELECT table_name,column_name FROM information_schema.columns "
            "WHERE table_schema='workflow'"
        ).fetchall()
        constraint_rows = connection.execute(
            "SELECT c.conname AS conname, t.relname AS table_name, c.contype::text AS contype, "
            "ARRAY(SELECT a.attname::text FROM unnest(c.conkey) AS k(attnum) JOIN pg_attribute a "
            "ON a.attrelid = c.conrelid AND a.attnum = k.attnum ORDER BY a.attnum) AS columns "
            "FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid JOIN pg_namespace n ON n.oid = t.relnamespace "
            "WHERE n.nspname='workflow'"
        ).fetchall()
        tables = {str(row["table_name"]) for row in table_rows}
        columns = {(str(row["table_name"]), str(row["column_name"])) for row in column_rows}
        counts: dict[str, int] = {}
        for table in sorted(REQUIRED_TABLES & tables):
            # Table names are constants from REQUIRED_TABLES, never user input.
            row = connection.execute(f'SELECT count(*) AS count FROM workflow."{table}"').fetchone()
            counts[table] = int(row["count"])
    except Exception as exc:
        raise WorkflowMigrationError("workflow_schema_observation_failed") from exc
    missing_tables = sorted(REQUIRED_TABLES - tables)
    missing_columns = sorted(f"{table}.{column}" for table, column in REQUIRED_COLUMNS - columns)
    present_constraints = {
        (str(row["table_name"]), str(row["conname"]), str(row.get("contype") or ""), tuple(row.get("columns") or ()))
        for row in constraint_rows
    }
    missing_constraints = sorted(spec[1] for spec in REQUIRED_CONSTRAINTS if spec not in present_constraints)
    return {
        "status": "PASS" if not missing_tables and not missing_columns and not missing_constraints else "BLOCKED",
        "missing_constraints": missing_constraints,
        "database": str(identity["database"]),
        "database_user": str(identity["user"]),
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "row_counts": counts,
    }


def observe_runtime_privileges(connection: Any, role: str, *, view_check: bool = False) -> dict[str, Any]:
    """Report missing runtime grants and the targeted GRANT lines; never grants anything."""
    if not role.strip():
        raise WorkflowMigrationError("workflow_runtime_role_required")
    try:
        if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
            return {"status": "BLOCKED", "runtime_role": role, "error": "workflow_runtime_role_missing",
                    "missing_relations": [], "missing_privileges": [], "grants": []}
        tables = {str(row["relname"]): str(row["relkind"]) for row in connection.execute(
            "SELECT c.relname, c.relkind::text AS relkind FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname='workflow' AND c.relkind IN ('r','S')"
        ).fetchall()}
        missing: list[str] = []
        grants: list[str] = []
        absent: list[str] = []
        checks = [(name, privs, "r") for name, privs in RUNTIME_TABLE_PRIVILEGES.items()
                  if view_check or name not in VIEW_CHECK_TABLES]
        checks += [(name, privs, "S") for name, privs in RUNTIME_SEQUENCE_PRIVILEGES.items()]
        for optional in OPTIONAL_MIGRATION_TABLES.values():
            if any(name in tables for name in optional):  # Partly installed counts as installed.
                checks += [(name, OPTIONAL_TABLE_PRIVILEGES[name], "r") for name in optional]
        if not connection.execute("SELECT has_schema_privilege(%s, 'workflow', 'USAGE') AS ok",
                                  (role,)).fetchone()["ok"]:
            missing.append("schema workflow:USAGE")
            grants.append(f'GRANT USAGE ON SCHEMA workflow TO "{role}";')
        for name, privileges, kind in sorted(checks):
            if tables.get(name) != kind:
                absent.append(name)  # Not every registered table is in REQUIRED_TABLES.
                continue
            function = "has_table_privilege" if kind == "r" else "has_sequence_privilege"
            lacking = [p for p in privileges if not connection.execute(
                f"SELECT {function}(%s, %s, %s) AS ok", (role, f"workflow.{name}", p)).fetchone()["ok"]]
            if lacking:
                missing += [f"{name}:{p}" for p in lacking]
                target = f"workflow.{name}" if kind == "r" else f"SEQUENCE workflow.{name}"
                grants.append(f'GRANT {", ".join(lacking)} ON {target} TO "{role}";')
    except Exception as exc:
        raise WorkflowMigrationError("workflow_runtime_privilege_observation_failed") from exc
    return {"status": "PASS" if not missing and not absent else "BLOCKED", "runtime_role": role,
            "missing_relations": absent, "missing_privileges": missing, "grants": grants}


def apply_migrations(
    connection: Any,
    *,
    paths: tuple[Path, ...],
    expected_digest: str,
) -> dict[str, Any]:
    actual_digest = migration_digest(paths)
    if expected_digest != actual_digest:
        raise WorkflowMigrationError("workflow_migration_digest_mismatch")
    applied: list[str] = []
    try:
        for path in paths:
            with connection.transaction():
                connection.execute(path.read_text(encoding="utf-8"))
            applied.append(path.name)
    except Exception as exc:
        raise WorkflowMigrationError(
            "workflow_migration_failed:" + (paths[len(applied)].name if len(applied) < len(paths) else "unknown")
        ) from exc
    verification = observe_schema(connection)
    if verification["status"] != "PASS":
        raise WorkflowMigrationError("workflow_schema_verification_failed")
    return {
        "status": "PASS",
        "digest": actual_digest,
        "applied": applied,
        "verification": verification,
    }
