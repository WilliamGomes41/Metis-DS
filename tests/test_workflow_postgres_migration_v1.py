"""Migration runner tests without a live Azure or PostgreSQL dependency.

# release-control-evidence: opslag
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from src.workflows.workflow_postgres_migration_v1 import (
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
        if query.startswith("SELECT c.conname"):  # #636: named constraints are part of verification
            return Rows([{"conname": "publication_refusals_dedup_key_uniq", "table_name": "publication_refusals",
                         "contype": "u", "columns": ["dedup_key"]}])
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
    assert MIGRATION_NAMES[-19:] == (
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
        "028_processing_archives.sql",
        "029_formation_evidence.sql",
    )
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
    assert len(connection.applied) == len(MIGRATION_NAMES)
    assert ("documents", "logical_document_id") in REQUIRED_COLUMNS
    assert ("documents", "working_revision_id") in REQUIRED_COLUMNS
    assert ("documents", "working_revision_number") in REQUIRED_COLUMNS
    assert ("documents", "topic_id") in REQUIRED_COLUMNS
    assert ("topics", "identity_key") in REQUIRED_COLUMNS
    assert "topics" in REQUIRED_TABLES
    assert result["verification"]["row_counts"] == {name: 0 for name in sorted(REQUIRED_TABLES)}


def test_controlled_plan_installs_review_indexes_and_can_be_reapplied(complete_postgres):
    import psycopg
    from psycopg.rows import dict_row

    paths = migration_paths(ROOT)
    with psycopg.connect(complete_postgres.dsn, row_factory=dict_row) as connection:
        connection.execute('DROP INDEX workflow.workflow_document_objects_dependencies')
        connection.execute('DROP INDEX workflow.workflow_review_events_document_history')
        connection.execute('DROP INDEX workflow.workflow_review_events_interaction_identity')
        connection.commit()
        for _ in range(2):
            assert apply_migrations(connection, paths=paths,
                expected_digest=migration_digest(paths))['status'] == 'PASS'
        indexes = {row['indexname']: row['indexdef'] for row in connection.execute(
            "SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='workflow'")}
        assert 'USING gin (payload jsonb_path_ops)' in indexes['workflow_document_objects_dependencies']
        assert "snapshot_id" in indexes['workflow_review_events_document_history']
        assert "interaction_id" in indexes['workflow_review_events_interaction_identity']


def test_apply_refuses_unconfirmed_or_changed_migration_bytes() -> None:
    paths = migration_paths(ROOT)
    with pytest.raises(WorkflowMigrationError, match="workflow_migration_digest_mismatch"):
        apply_migrations(FakeConnection(), paths=paths, expected_digest="0" * 64)
