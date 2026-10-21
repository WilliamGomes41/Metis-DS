"""Controlled schema application and verification for workflow migrations 002-006 + 008-010."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from azure.identity import DefaultAzureCredential

from src.canonical_publication_postgres_v1 import AZURE_POSTGRES_SCOPE


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
