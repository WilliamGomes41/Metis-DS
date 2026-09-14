"""Migration runner tests without a live Azure or PostgreSQL dependency.

# release-control-evidence: opslag
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from src.workflow_postgres_migration_v1 import (
    MIGRATION_NAMES,
    REQUIRED_COLUMNS,
    REQUIRED_TABLES,
    WorkflowMigrationError,
    apply_migrations,
    migration_digest,
    migration_paths,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeConnection:
    def __init__(self) -> None:
        self.applied: list[str] = []

    def transaction(self):
        return nullcontext()

    def execute(self, query: str):
        if query.startswith("SELECT current_database"):
            return Rows([{"database": "metis", "user": "admin"}])
        if "information_schema.tables" in query:
            return Rows([{"table_name": name} for name in REQUIRED_TABLES])
        if "information_schema.columns" in query:
            return Rows([{"table_name": table, "column_name": column} for table, column in REQUIRED_COLUMNS])
        if query.startswith("SELECT count"):
            return Rows([{"count": 0}])
        self.applied.append(query)
        return Rows([])


class Rows:
    def __init__(self, values: list[dict]) -> None:
        self.values = values

    def fetchone(self):
        return self.values[0]

    def fetchall(self):
        return self.values


def test_plan_digest_binds_exact_ordered_migration_bytes() -> None:
    paths = migration_paths(ROOT)
    assert tuple(path.name for path in paths) == MIGRATION_NAMES
    digest = migration_digest(paths)
    assert len(digest) == 64
    assert digest == migration_digest(paths)


def test_apply_requires_exact_digest_and_verifies_all_required_shape() -> None:
    paths = migration_paths(ROOT)
    connection = FakeConnection()
    result = apply_migrations(
        connection,
        paths=paths,
        expected_digest=migration_digest(paths),
    )
    assert result["status"] == "PASS"
    assert result["applied"] == list(MIGRATION_NAMES)
    assert len(connection.applied) == 4
    assert result["verification"]["row_counts"] == {name: 0 for name in sorted(REQUIRED_TABLES)}


def test_apply_refuses_unconfirmed_or_changed_migration_bytes() -> None:
    paths = migration_paths(ROOT)
    with pytest.raises(WorkflowMigrationError, match="workflow_migration_digest_mismatch"):
        apply_migrations(FakeConnection(), paths=paths, expected_digest="0" * 64)
