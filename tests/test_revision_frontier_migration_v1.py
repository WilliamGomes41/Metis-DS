"""Native expand/rollback contract; derived inputs never own retained objects.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from tests.postgres_support import database
from tests.test_review_command_storage_v1 import seed, object_storage
from src.workflows.workflow_postgres_migration_v1 import migration_paths

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / 'db/migrations/032_object_revision_frontiers.sql'


@pytest.mark.parametrize('damage', ['missing_epoch', 'json_null_epoch', 'missing_position', 'null_identity', 'changed_order'])
def test_malformed_or_changed_execution_metadata_cannot_distort_admission_context(complete_postgres, damage):
    store, _, sid, _ = seed(complete_postgres)
    before = store.review_command_window(sid, ['delta-a'])
    cert = deepcopy(dict(before.frontiers['delta-a']))
    if damage == 'missing_epoch':
        del cert['epoch']
    elif damage == 'json_null_epoch':
        cert['epoch'] = None
    elif damage == 'missing_position':
        del cert['first_position']
    elif damage == 'null_identity':
        cert['snapshot_id'] = None
    else:
        cert['source_sequence'] = 999999
    with pytest.raises(psycopg.errors.CheckViolation):
        with store._connect() as con:
            if damage == 'changed_order':
                con.execute('UPDATE workflow.object_revision_frontiers SET certificate=%s '
                            'WHERE snapshot_id=%s AND object_id=%s', (Jsonb(cert), sid, 'delta-a'))
            else:
                con.execute("UPDATE workflow.object_revision_frontiers SET certificate=%s,"
                    "certificate_hash=encode(sha256(convert_to((%s::jsonb)::text,'UTF8')),'hex') "
                    'WHERE snapshot_id=%s AND object_id=%s', (Jsonb(cert), Jsonb(cert), sid, 'delta-a'))
    assert store.review_command_window(sid, ['delta-a']).frontiers == before.frontiers


def test_derived_entry_deletion_cannot_delete_or_hide_authoritative_history(complete_postgres):
    store, _, sid, _ = seed(complete_postgres)
    before = object_storage(store, sid)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with store._connect() as con:
            con.execute('DELETE FROM workflow.object_revision_frontiers WHERE snapshot_id=%s', (sid,))
    assert object_storage(store, sid) == before
    assert store.review_command_window(sid, ['delta-a']) is not None


def test_expand_is_idempotent_and_old_object_writer_receives_only_trigger_privileges(complete_postgres):
    role = 'met36_writer_' + uuid4().hex
    with psycopg.connect(complete_postgres.dsn, row_factory=dict_row, autocommit=True) as con:
        con.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
        try:
            con.execute(sql.SQL('GRANT USAGE ON SCHEMA workflow TO {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('GRANT SELECT,UPDATE ON workflow.documents TO {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE ON workflow.document_objects TO {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE ON workflow.review_fact_state,workflow.review_object_facts TO {}').format(sql.Identifier(role)))
            for _ in range(2):
                con.execute(MIGRATION.read_text())
            privileges = con.execute("SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE grantee=%s AND table_schema='workflow' AND table_name='object_revision_frontiers'", (role,)).fetchall()
            assert {row['privilege_type'] for row in privileges} == {'SELECT', 'INSERT', 'UPDATE'}
            store, _, sid, _ = seed(complete_postgres)
            con.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
            assert con.execute("UPDATE workflow.document_objects SET payload=payload "
                "WHERE snapshot_id=%s AND object_id='delta-a' AND object_version='1.0'", (sid,)).rowcount == 1
            con.execute('RESET ROLE')
            assert store.review_command_window(sid, ['delta-a']) is None
        finally:
            con.execute('RESET ROLE')
            con.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


def test_bounded_review_does_not_require_optional_review_card_schema(complete_postgres):
    # The controlled production migration list intentionally excludes optional027.
    with database(complete_postgres.dsn) as config:
        with psycopg.connect(config.dsn, autocommit=True) as con:
            con.execute((ROOT / 'db/schema_v2.sql').read_text())
            for path in migration_paths(ROOT):
                con.execute(path.read_text())
            assert con.execute("SELECT to_regclass('workflow.review_object_facts')").fetchone()[0] is None
        store, _, sid, _ = seed(config)
        before = store.review_command_window(sid, ['delta-a'])
        assert before is not None
        after = deepcopy(before)
        after[0]['text'] = 'Current review with production schema'
        env = store.get_envelope(sid)
        store.apply_review_changes(sid, before, after, env, env)
        assert store.review_command_window(sid, ['delta-a'])[0]['text'] == after[0]['text']
