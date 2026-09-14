"""Controlled schema application and verification for workflow migrations 002-005."""
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
)
REQUIRED_TABLES = frozenset(
    {
        "accounts",
        "sessions",
        "documents",
        "document_reviewers",
        "document_objects",
        "review_events",
        "publish_authorizations",
        "audit_records",
        "audit_secrets",
    }
)
REQUIRED_COLUMNS = frozenset(
    {
        ("documents", "envelope_payload"),
        ("document_objects", "position"),
        ("review_events", "actor_text"),
        ("review_events", "event_payload"),
        ("publish_authorizations", "position"),
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
    return {
        "status": "PASS" if not missing_tables and not missing_columns else "BLOCKED",
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
