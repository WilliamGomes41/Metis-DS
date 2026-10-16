"""#636 F1 (Sherlock 02:10): migration 018 MOET be safe twice and on top of the pre-UNIQUE 018.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable authority concurrent
# release-control-evidence: releasebewijs

The named UNIQUE constraint is added in a DO block guarded by pg_constraint (conname +
conrelid). The repository MAG NIET rely on 018 never having reached a persistent database.
Runs only with METIS_TEST_POSTGRES_DSN (CI postgres:16 service). The fixture runs DROP SCHEMA
workflow CASCADE: METIS_TEST_POSTGRES_DSN MOET only point at a disposable database.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / 'db' / 'migrations' / '018_publication_refusal_audit.sql'
OLD = ROOT / 'tests' / 'fixtures' / '018_publication_refusal_audit_pre_unique.sql'
CONSTRAINT = 'publication_refusals_dedup_key_uniq'

pytestmark = [pytest.mark.release_control_opslag, pytest.mark.release_control_releasebewijs]


def test_018_guards_a_named_unique_constraint_via_pg_constraint():
    sql = NEW.read_text()
    assert 'DO $$' in sql and 'pg_constraint' in sql and 'conname' in sql and 'conrelid' in sql
    assert f'CONSTRAINT {CONSTRAINT} UNIQUE (dedup_key)' in sql


@pytest.fixture()
def pg():
    dsn = os.environ.get('METIS_TEST_POSTGRES_DSN', '').strip()
    if not dsn:
        pytest.skip('METIS_TEST_POSTGRES_DSN is required for migration 018 evidence')
    import psycopg
    con = psycopg.connect(dsn, autocommit=True)
    con.execute('DROP SCHEMA IF EXISTS workflow CASCADE')
    con.execute('CREATE SCHEMA workflow')
    yield con
    con.execute('DROP SCHEMA IF EXISTS workflow CASCADE')
    con.close()


def _constraints(con):
    return con.execute("SELECT count(*) FROM pg_constraint WHERE conname=%s AND "
                       "conrelid='workflow.publication_refusals'::regclass", (CONSTRAINT,)).fetchone()[0]


def _insert(con, key, n=1):
    for _ in range(n):
        con.execute("INSERT INTO workflow.publication_refusals(recorded_at, snapshot_id, object_version, actor, verdict,"
                    " reason_codes, revision_sha256, dedup_key, schema_version) VALUES (now(),'s','1','a','refused',"
                    " '[]'::jsonb, NULL, %s, 'v1')", (key,))


def test_018_applies_twice(pg):
    pg.execute(NEW.read_text())
    pg.execute(NEW.read_text())
    assert _constraints(pg) == 1


def test_018_applies_on_top_of_the_pre_unique_018_without_duplicates(pg):
    pg.execute(OLD.read_text())
    _insert(pg, 'k1', 1)
    _insert(pg, 'k2', 1)
    pg.execute(NEW.read_text())
    pg.execute(NEW.read_text())
    assert _constraints(pg) == 1
    assert sorted(r[0] for r in pg.execute('SELECT dedup_key FROM workflow.publication_refusals')) == ['k1', 'k2']


def test_018_fails_on_duplicates_with_count_and_keys_and_updates_nothing(pg):
    # Metis F1-5: 018 does NO UPDATE on audit rows; duplicates MOETEN stop 018 for a human decision.
    import psycopg
    pg.execute(OLD.read_text())
    _insert(pg, 'k1', 3)
    _insert(pg, 'k2', 2)
    _insert(pg, 'k3', 1)
    before = pg.execute('SELECT refusal_id, dedup_key FROM workflow.publication_refusals ORDER BY 1').fetchall()
    with pytest.raises(psycopg.errors.RaiseException) as error:
        pg.execute(NEW.read_text())
    message = str(error.value)
    assert 'publication_refusals_duplicate_dedup_keys' in message and 'count=2' in message
    assert 'k1' in message and 'k2' in message and 'k3' not in message
    assert pg.execute('SELECT refusal_id, dedup_key FROM workflow.publication_refusals ORDER BY 1').fetchall() == before
    assert _constraints(pg) == 0


def test_018_contains_no_update():
    assert 'UPDATE' not in '\n'.join(l for l in NEW.read_text().splitlines() if not l.lstrip().startswith('--')).upper()


def test_runbook_orders_018_before_code_with_williams_go_and_lists_retention():
    text = (ROOT / 'docs' / 'TEST_AND_RELEASE_RUNBOOK.md').read_text()
    assert '018_publication_refusal_audit.sql' in text and 'vóór de code' in text and 'GO van William' in text
    assert 'scripts/publication_refusal_retention.py' in text and 'Deploy-checklist' in text
    assert 'publication_refusals_duplicate_dedup_keys' in text and 'Een mens beslist' in text


def test_018_duplicate_error_lists_a_capped_number_of_keys(pg):
    # Sherlock 02:55: the error message MOET stay bounded; count is exact, the key list is capped.
    import psycopg
    pg.execute(OLD.read_text())
    for n in range(25):
        _insert(pg, f'dup{n:02d}', 2)
    with pytest.raises(psycopg.errors.RaiseException) as error:
        pg.execute(NEW.read_text())
    message = str(error.value)
    assert 'count=25' in message and 'more=5' in message
    assert sum(1 for n in range(25) if f'dup{n:02d}' in message) == 20


def test_018_caps_the_key_list_in_sql():
    assert 'LIMIT 20' in NEW.read_text()


def test_disposable_database_rule_is_documented():
    # Sherlock 02:55: these tests DROP SCHEMA workflow; the DSN MOET only point at a disposable database.
    rule = 'METIS_TEST_POSTGRES_DSN MOET only point at a disposable database'
    assert rule in (__doc__ or '')
    assert rule in (ROOT / 'docs' / 'TEST_AND_RELEASE_RUNBOOK.md').read_text()


# --- Sherlock #636 P2: schema verify MOET check the refusal columns and the named constraint ---

class _Res:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _SchemaCon:
    def __init__(self, *, drop_column=None, constraint=True, constraint_row=None):
        from src.workflows.workflow_postgres_migration_v1 import REQUIRED_COLUMNS, REQUIRED_TABLES
        self.tables = [{'table_name': t} for t in REQUIRED_TABLES]
        self.columns = [{'table_name': t, 'column_name': c} for t, c in REQUIRED_COLUMNS
                        if (t, c) != drop_column]
        self.constraint = constraint
        self.constraint_row = constraint_row or {'conname': CONSTRAINT, 'table_name': 'publication_refusals',
                                                 'contype': 'u', 'columns': ['dedup_key']}

    def execute(self, sql, params=None):
        if 'current_database' in sql:
            return _Res([{'database': 'd', 'user': 'u'}])
        if 'information_schema.tables' in sql:
            return _Res(self.tables)
        if 'information_schema.columns' in sql:
            return _Res(self.columns)
        if 'pg_constraint' in sql:
            return _Res([self.constraint_row] if self.constraint else [])
        return _Res([{'count': 0}])


def test_schema_verify_requires_refusal_columns_and_named_constraint():
    from src.workflows.workflow_postgres_migration_v1 import REQUIRED_COLUMNS, observe_schema
    for column in ('refusal_id', 'recorded_at', 'snapshot_id', 'object_version', 'actor', 'verdict',
                   'reason_codes', 'revision_sha256', 'dedup_key', 'schema_version'):
        assert ('publication_refusals', column) in REQUIRED_COLUMNS
    assert observe_schema(_SchemaCon())['status'] == 'PASS'
    missing_constraint = observe_schema(_SchemaCon(constraint=False))
    assert missing_constraint['status'] == 'BLOCKED' and missing_constraint['missing_constraints'] == [CONSTRAINT]
    assert observe_schema(_SchemaCon(drop_column=('publication_refusals', 'dedup_key')))['status'] == 'BLOCKED'


def test_runbooks_grant_runtime_access_to_the_refusal_table_and_sequence():
    # Sherlock #636 P2: GRANT ... ON ALL TABLES does not cover tables created later (018).
    for name in ('AZURE_STEP9_CUTOVER_RUNBOOK.md', 'TEST_AND_RELEASE_RUNBOOK.md'):
        text = (ROOT / 'docs' / name).read_text()
        assert 'GRANT SELECT, INSERT, DELETE ON workflow.publication_refusals TO' in text, name
        assert 'GRANT USAGE, SELECT ON SEQUENCE workflow.publication_refusals_refusal_id_seq TO' in text, name


@pytest.mark.parametrize('row', [
    {'conname': CONSTRAINT, 'table_name': 'documents', 'contype': 'u', 'columns': ['dedup_key']},
    {'conname': CONSTRAINT, 'table_name': 'publication_refusals', 'contype': 'c', 'columns': ['dedup_key']},
    {'conname': CONSTRAINT, 'table_name': 'publication_refusals', 'contype': 'u', 'columns': ['snapshot_id']},
    {'conname': CONSTRAINT, 'table_name': 'publication_refusals', 'contype': 'u', 'columns': ['dedup_key', 'actor']},
])
def test_schema_verify_checks_constraint_table_type_and_column(row):
    # 4291505169: a same-named constraint on another table, a non-unique one, or one on other
    # columns MAG NIET pass: ON CONFLICT (dedup_key) needs UNIQUE(dedup_key) on publication_refusals.
    from src.workflows.workflow_postgres_migration_v1 import observe_schema
    result = observe_schema(_SchemaCon(constraint_row=row))
    assert result['status'] == 'BLOCKED' and result['missing_constraints'] == [CONSTRAINT]
