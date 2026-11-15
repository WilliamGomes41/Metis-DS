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
    REQUIRED_TRIGGERS,
    WorkflowMigrationError,
    apply_migrations,
    migration_digest,
    migration_paths,
)


ROOT = Path(__file__).resolve().parents[1]


def test_test_reset_migration_keeps_workflow_only_installation_usable_and_fences_later_lineage(complete_postgres):
    import psycopg
    from psycopg.rows import dict_row
    from tests.postgres_support import database
    from src.workflows.workflow_postgres_migration_v1 import observe_schema
    paths = migration_paths(ROOT)
    with database(complete_postgres.dsn) as config:
        with psycopg.connect(config.dsn, autocommit=True, row_factory=dict_row) as con:
            con.execute((ROOT / 'db/schema_v2.sql').read_text())
            assert apply_migrations(con, paths=paths, expected_digest=migration_digest(paths))['status'] == 'PASS'
            assert con.execute("SELECT to_regclass('public.source_snapshots') AS name").fetchone()['name'] is None
            from src.documents.test_document_deletion_v1 import _storage
            from src.operations_console_v1 import ConsoleError
            with pytest.raises(ConsoleError, match='storage_not_ready'):
                _storage(con)
            con.execute((ROOT / 'db/migrations/001_canonical_source_lineage.sql').read_text())
            assert 'public.source_snapshots.refuse_deleted_test_source' in observe_schema(con)['missing_triggers']
            assert apply_migrations(con, paths=paths, expected_digest=migration_digest(paths))['status'] == 'PASS'
            # With canonical lineage present the source fence is mandatory.
            con.execute('DROP TRIGGER refuse_deleted_test_source ON public.source_snapshots')
            assert 'public.source_snapshots.refuse_deleted_test_source' in observe_schema(con)['missing_triggers']


class FakeConnection:
    def __init__(self) -> None:
        self.applied: list[str] = []

    def transaction(self):
        return nullcontext()

    def execute(self, query: str, params=None):
        if query == 'SHOW lock_timeout':
            return Rows([{'lock_timeout': '0'}])
        if query.startswith("SELECT set_config"):
            return Rows([{"set_config": params[0]}])
        if query.startswith("SELECT current_database"):
            return Rows([{"database": "metis", "user": "admin"}])
        if "information_schema.tables" in query:
            return Rows([{"table_name": name} for name in REQUIRED_TABLES])
        if "information_schema.columns" in query:
            return Rows([{"table_name": table, "column_name": column} for table, column in REQUIRED_COLUMNS])
        if 'FROM pg_trigger t' in query:
            return Rows([{'table_name': table, 'trigger_name': trigger} for table, trigger in REQUIRED_TRIGGERS])
        if query.startswith("SELECT c.conname"):  # #636: named constraints are part of verification
            return Rows([{"conname": "require_human_annotation_binding", "table_name": "document_objects", "contype": "t", "columns": []},
                         {"conname": "guard_annotation_build_receipt", "table_name": "annotation_build_commands", "contype": "t", "columns": []},
                         {"conname": "require_annotation_build_receipt", "table_name": "processing_attempts", "contype": "t", "columns": []},
                         {"conname": "formation_evidence_producer", "table_name": "formation_evidence_roots",
                          "contype": "c", "columns": ["context_id", "header", "annotation_seal_id"]},
                         {"conname": "guard_annotation_input_transition", "table_name": "annotation_versions",
                          "contype": "t", "columns": []},
                         {"conname": "guard_annotation_head_transition", "table_name": "annotation_heads",
                          "contype": "t", "columns": []},
                         {"conname": "publication_refusals_dedup_key_uniq", "table_name": "publication_refusals",
                         "contype": "u", "columns": ["dedup_key"]},
                         {"conname": "object_revision_frontiers_pkey", "table_name": "object_revision_frontiers",
                          "contype": "p", "columns": ["snapshot_id", "object_id"]},
                         {"conname": "workflow_object_revision_frontier_fk", "table_name": "document_objects",
                          "contype": "f", "columns": ["snapshot_id", "object_id"]}])
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
    assert MIGRATION_NAMES[-32:] == (
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
        "030_operational_document_inputs.sql",
        "031_review_dependency_keys.sql",
        "032_object_revision_frontiers.sql",
        "033_statement_object_generation.sql",
        "034_human_annotations.sql",
        "035_annotation_meaning_input.sql",
        "036_human_annotation_build.sql",
        "037_human_annotation_revisions.sql",
        "038_prose_transitions.sql",
        "039_test_document_deletion.sql",
        "040_attempt_index_document_cascade.sql",
        "041_annotation_source_preparation.sql",
        "042_retire_essential_relationships.sql",
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


def test_registered_plan_installs_stop_guards_and_verifies_their_enabled_relations(complete_postgres):
    import psycopg
    from psycopg.rows import dict_row
    from src.workflows.workflow_postgres_migration_v1 import observe_schema
    paths = migration_paths(ROOT)
    with psycopg.connect(complete_postgres.dsn, row_factory=dict_row) as con:
        for table, trigger in REQUIRED_TRIGGERS:
            relation = table if '.' in table else 'workflow.'+table
            con.execute(f'DROP TRIGGER {trigger} ON {relation}')
        assert set(observe_schema(con)['missing_triggers']) == {
            f'{table}.{trigger}' for table, trigger in REQUIRED_TRIGGERS}
        con.commit()
        result = apply_migrations(con, paths=paths, expected_digest=migration_digest(paths))
        assert result['status'] == 'PASS'
        assert result['applied'][-3:] == ['040_attempt_index_document_cascade.sql', '041_annotation_source_preparation.sql', '042_retire_essential_relationships.sql']
        con.execute('ALTER TABLE workflow.processing_attempts DISABLE TRIGGER guard_prose_transition_attempt')
        observed = observe_schema(con)
        assert observed['status'] == 'BLOCKED'
        assert observed['missing_triggers'] == ['processing_attempts.guard_prose_transition_attempt']
        con.execute('ALTER TABLE workflow.processing_attempts ENABLE TRIGGER guard_prose_transition_attempt')
        assert observe_schema(con)['status'] == 'PASS'


@pytest.mark.parametrize('timeout', [0, -1, True, 1.5, '5000', 2147483648])
def test_invalid_lock_timeout_is_rejected_before_any_migration(timeout):
    con = FakeConnection()
    paths = migration_paths(ROOT)
    with pytest.raises(WorkflowMigrationError, match='workflow_migration_lock_timeout_invalid'):
        apply_migrations(con, paths=paths, expected_digest=migration_digest(paths), lock_timeout_ms=timeout)
    assert con.applied == []


def test_lock_timeout_rolls_back_only_the_failing_file_and_retry_succeeds(complete_postgres, tmp_path):
    import psycopg
    from psycopg.rows import dict_row

    first = tmp_path/'first.sql'
    second = tmp_path/'second.sql'
    first.write_text('CREATE TABLE IF NOT EXISTS workflow.design_first(setting TEXT); '
                     "INSERT INTO workflow.design_first SELECT current_setting('lock_timeout') "
                     'WHERE NOT EXISTS(SELECT 1 FROM workflow.design_first);')
    second.write_text('CREATE TABLE workflow.design_partial(value TEXT); '
                      'ALTER TABLE workflow.documents ADD COLUMN IF NOT EXISTS design_column TEXT;')
    paths = (first, second)
    with psycopg.connect(complete_postgres.dsn, autocommit=True, row_factory=dict_row) as con:
        con.execute("SET lock_timeout='2s'")
        with psycopg.connect(complete_postgres.dsn) as holder:
            holder.execute('SELECT * FROM workflow.documents LIMIT 0')
            with pytest.raises(WorkflowMigrationError, match='workflow_migration_failed:second.sql') as error:
                apply_migrations(con, paths=paths, expected_digest=migration_digest(paths), lock_timeout_ms=100)
            assert error.value.__cause__.sqlstate == '55P03'
            assert con.execute('SELECT setting FROM workflow.design_first').fetchone()['setting'] == '100ms'
            assert con.execute("SELECT to_regclass('workflow.design_partial') AS name").fetchone()['name'] is None
            assert not con.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='workflow' "
                                   "AND table_name='documents' AND column_name='design_column'").fetchone()
            assert con.execute('SHOW lock_timeout').fetchone()['lock_timeout'] == '2s'
            holder.rollback()
        result = apply_migrations(con, paths=paths, expected_digest=migration_digest(paths), lock_timeout_ms=100)
        assert result['status'] == 'PASS'
        assert con.execute('SELECT count(*) AS n FROM workflow.design_first').fetchone()['n'] == 1
        assert con.execute("SELECT to_regclass('workflow.design_partial') AS name").fetchone()['name']
        assert con.execute('SHOW lock_timeout').fetchone()['lock_timeout'] == '2s'


def test_default_lock_timeout_is_local_to_the_migration(complete_postgres, tmp_path):
    import psycopg
    from psycopg.rows import dict_row

    path = tmp_path/'capture.sql'
    path.write_text("CREATE TABLE workflow.design_timeout AS SELECT current_setting('lock_timeout') AS value;")
    with psycopg.connect(complete_postgres.dsn, autocommit=True, row_factory=dict_row) as con:
        before = con.execute('SHOW lock_timeout').fetchone()['lock_timeout']
        apply_migrations(con, paths=(path,), expected_digest=migration_digest((path,)))
        assert con.execute('SELECT value FROM workflow.design_timeout').fetchone()['value'] == '5s'
        assert con.execute('SHOW lock_timeout').fetchone()['lock_timeout'] == before


@pytest.mark.parametrize('arguments', [
    ['verify', '--strict-runtime-privileges'],
    ['apply', '--strict-runtime-privileges', '--runtime-role', 'runtime'],
    ['plan', '--lock-timeout-ms', '0'],
])
def test_cli_rejects_invalid_hardening_options_before_connect(monkeypatch, arguments):
    import sys
    from scripts import apply_workflow_postgres_migrations as cli

    attempted = []
    monkeypatch.setattr(cli, 'connect_entra', lambda **kwargs: attempted.append(kwargs))
    monkeypatch.setattr(sys, 'argv', ['apply_workflow_postgres_migrations.py', *arguments,
                                     '--host', 'example', '--database', 'metis', '--user', 'admin'])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert attempted == []


def test_cli_forwards_strict_policy_without_mutating_privileges(monkeypatch, capsys):
    import sys
    from scripts import apply_workflow_postgres_migrations as cli

    class Connection(FakeConnection):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    captured = {}
    def observe(con, role, **kwargs):
        captured.update(role=role, **kwargs)
        return {'status': 'BLOCKED', 'excess_privileges': ['forbidden-update']}
    monkeypatch.setattr(cli, 'connect_entra', lambda **kwargs: Connection())
    monkeypatch.setattr(cli, 'observe_runtime_privileges', observe)
    monkeypatch.setattr(sys, 'argv', ['apply_workflow_postgres_migrations.py', 'verify',
                                     '--host', 'example', '--database', 'metis', '--user', 'admin',
                                     '--runtime-role', 'runtime', '--strict-runtime-privileges'])
    assert cli.main() == 2
    assert captured['strict'] is True and captured['role'] == 'runtime'
    import json
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'BLOCKED' and report['mutation'] == 'none'


@pytest.mark.parametrize('fail', [False, True])
def test_timeout_is_restored_inside_a_caller_owned_transaction(complete_postgres, tmp_path, fail):
    import psycopg
    from psycopg.rows import dict_row

    path = tmp_path/'nested.sql'
    statement = "CREATE TABLE workflow.design_nested AS SELECT current_setting('lock_timeout') AS value;"
    if fail:
        statement += ' SELECT 1 / 0;'
    path.write_text(statement)
    with psycopg.connect(complete_postgres.dsn, row_factory=dict_row) as con:
        con.execute("SET LOCAL lock_timeout='2s'")
        if fail:
            with pytest.raises(WorkflowMigrationError, match='workflow_migration_failed:nested.sql'):
                apply_migrations(con, paths=(path,), expected_digest=migration_digest((path,)), lock_timeout_ms=100)
            assert con.execute("SELECT to_regclass('workflow.design_nested') AS name").fetchone()['name'] is None
        else:
            apply_migrations(con, paths=(path,), expected_digest=migration_digest((path,)), lock_timeout_ms=100)
            assert con.execute('SELECT value FROM workflow.design_nested').fetchone()['value'] == '100ms'
        assert con.execute('SHOW lock_timeout').fetchone()['lock_timeout'] == '2s'
        # The migration must not commit or discard the caller's transaction.
        con.rollback()
        assert con.execute("SELECT to_regclass('workflow.design_nested') AS name").fetchone()['name'] is None
