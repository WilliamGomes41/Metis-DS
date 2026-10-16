"""#636 F1 (Sherlock 02:10): migration 018 MOET be safe twice and on top of the pre-UNIQUE 018.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable authority concurrent
# release-control-evidence: releasebewijs

The named UNIQUE constraint is added in a DO block guarded by pg_constraint (conname +
conrelid). The repository MAG NIET rely on 018 never having reached a persistent database.
Runs only with METIS_TEST_POSTGRES_DSN (CI postgres:16 service).
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


def test_018_applies_on_top_of_the_pre_unique_018_with_duplicate_rows(pg):
    pg.execute(OLD.read_text())
    _insert(pg, 'k1', 3)  # the pre-UNIQUE 018 allowed repeated dedup keys across windows
    _insert(pg, 'k2', 1)
    pg.execute(NEW.read_text())
    pg.execute(NEW.read_text())
    assert _constraints(pg) == 1
    assert pg.execute('SELECT count(*) FROM workflow.publication_refusals').fetchone()[0] == 4  # NOOIT deleted
    import psycopg
    with pytest.raises(psycopg.errors.UniqueViolation):
        _insert(pg, 'k2', 1)
