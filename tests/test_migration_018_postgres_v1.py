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
