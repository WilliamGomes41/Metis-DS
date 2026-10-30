"""#930: migration verify checks the runtime identity's grants, never grants them.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from src.workflows.workflow_postgres_migration_v1 import (
    MIGRATION_NAMES,
    OPTIONAL_MIGRATION_TABLES,
    OPTIONAL_TABLE_PRIVILEGES,
    RUNTIME_SEQUENCE_PRIVILEGES,
    RUNTIME_TABLE_PRIVILEGES,
    observe_runtime_privileges,
)

ROOT = Path(__file__).resolve().parents[1]


def _registered_tables():
    sql = "\n".join((ROOT / "db" / "migrations" / name).read_text() for name in MIGRATION_NAMES)
    return set(re.findall(r"CREATE TABLE IF NOT EXISTS workflow\.([a-z_]+)", sql))


def test_every_registered_table_has_a_runtime_privilege_expectation():
    assert set(RUNTIME_TABLE_PRIVILEGES) == _registered_tables()


def test_every_workflow_migration_outside_the_registry_is_inventoried():
    """A migration file not in MIGRATION_NAMES (027) still declares its runtime grants."""
    files = {p.name for p in (ROOT / "db" / "migrations").glob("0*.sql")}
    for name in sorted(files - set(MIGRATION_NAMES)):
        created = set(re.findall(r"CREATE TABLE IF NOT EXISTS workflow\.([a-z_]+)",
                                 (ROOT / "db" / "migrations" / name).read_text()))
        if created:
            assert set(OPTIONAL_MIGRATION_TABLES.get(name, ())) == created, name
    assert {t for ts in OPTIONAL_MIGRATION_TABLES.values() for t in ts} == set(OPTIONAL_TABLE_PRIVILEGES)


def test_every_serial_sequence_of_a_registered_table_is_expected():
    sql = "\n".join((ROOT / "db" / "migrations" / name).read_text() for name in MIGRATION_NAMES)
    serials = set()
    for table, body in re.findall(r"CREATE TABLE IF NOT EXISTS workflow\.([a-z_]+)\s*\((.*?)\n\);", sql, re.DOTALL):
        serials |= {f"{table}_{column}_seq" for column in re.findall(r"^\s*([a-z_]+)\s+BIGSERIAL", body, re.MULTILINE)}
    assert set(RUNTIME_SEQUENCE_PRIVILEGES) == serials


def test_runtime_sql_writes_are_covered_by_the_expectation():
    """Every write the console code issues on a registered table is an expected privilege."""
    code = "\n".join(p.read_text() for p in (ROOT / "src").rglob("*.py"))
    for table, privileges in {**RUNTIME_TABLE_PRIVILEGES, **OPTIONAL_TABLE_PRIVILEGES}.items():
        name = rf"(?:workflow\.)?{table}\b"
        used = {"SELECT"}
        # _immutable() builds INSERT ... ON CONFLICT DO NOTHING from a module-owned table literal.
        if re.search(rf"INSERT INTO {name}", code) or re.search(rf"_immutable\(con, ['\"]{table}['\"]", code):
            used.add("INSERT")
        if re.search(rf"UPDATE {name}", code) or re.search(
                rf"INSERT INTO {name}[^;]{{0,800}}?DO UPDATE", code, re.DOTALL):
            used.add("UPDATE")
        if re.search(rf"DELETE FROM {name}", code):
            used.add("DELETE")
        assert used <= set(privileges), (table, used - set(privileges))


@pytest.fixture()
def runtime_role(complete_postgres):
    import psycopg
    role = f"metis_runtime_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(complete_postgres.dsn, autocommit=True) as con:
        con.execute(f'CREATE ROLE "{role}" LOGIN')
        con.execute(f'GRANT USAGE ON SCHEMA workflow TO "{role}"')  # Initial provisioning (cutover runbook).
        try:
            yield con, role
        finally:
            con.execute(f'DROP OWNED BY "{role}"')
            con.execute(f'DROP ROLE "{role}"')


def _observe(con, role, **kw):
    from psycopg.rows import dict_row
    with con.cursor(row_factory=dict_row) as cur:
        class C:
            def execute(self, *a):
                cur.execute(*a)
                return cur
        return observe_runtime_privileges(C(), role, **kw)


def test_missing_grant_fails_with_the_exact_targeted_grant_and_passes_after_it(runtime_role):
    con, role = runtime_role
    # The documented baseline grant, then a later migration's table without a grant (as 026 did).
    con.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA workflow TO "{role}"')
    con.execute(f'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA workflow TO "{role}"')
    con.execute(f'REVOKE ALL ON workflow.source_read_blocks FROM "{role}"')
    result = _observe(con, role)
    assert result["status"] == "BLOCKED"
    assert result["missing_privileges"] == ["source_read_blocks:SELECT", "source_read_blocks:INSERT"]
    assert result["grants"] == [f'GRANT SELECT, INSERT ON workflow.source_read_blocks TO "{role}";']
    con.execute(result["grants"][0])
    assert _observe(con, role) == {"status": "PASS", "runtime_role": role, "missing_relations": [],
                                  "missing_privileges": [], "grants": []}


def _grant_expected(con, role, *, skip=(), optional=True, sequences=True):
    expected = {**RUNTIME_TABLE_PRIVILEGES, **(OPTIONAL_TABLE_PRIVILEGES if optional else {})}
    for table, privileges in expected.items():
        if table not in skip:
            con.execute(f'GRANT {", ".join(privileges)} ON workflow.{table} TO "{role}"')
    for sequence in RUNTIME_SEQUENCE_PRIVILEGES if sequences else ():
        con.execute(f'GRANT USAGE ON SEQUENCE workflow.{sequence} TO "{role}"')


def test_deliberately_narrow_grants_do_not_fail(runtime_role):
    con, role = runtime_role
    _grant_expected(con, role)
    # publication_refusals has no UPDATE, and that is correct.
    assert _observe(con, role, view_check=True)["status"] == "PASS"


def test_view_check_table_is_only_required_when_enabled_and_sequences_are_checked(runtime_role):
    con, role = runtime_role
    _grant_expected(con, role, skip={"view_checks"}, sequences=False)
    assert _observe(con, role)["missing_privileges"] == [
        f"{sequence}:USAGE" for sequence in sorted(RUNTIME_SEQUENCE_PRIVILEGES)]
    assert f'GRANT USAGE ON SEQUENCE workflow.publication_refusals_refusal_id_seq TO "{role}";' in _observe(con, role)["grants"]
    assert "view_checks:SELECT" in _observe(con, role, view_check=True)["missing_privileges"]


def test_an_unapplied_registered_table_blocks_instead_of_passing(runtime_role):
    con, role = runtime_role
    _grant_expected(con, role)
    con.execute("DROP TABLE workflow.view_checks")  # Schema verify does not list 019 itself.
    assert _observe(con, role)["status"] == "PASS"
    result = _observe(con, role, view_check=True)
    assert result["status"] == "BLOCKED" and result["missing_relations"] == ["view_checks"]


def test_installed_review_card_tables_are_checked_and_absent_ones_are_not(runtime_role):
    con, role = runtime_role
    _grant_expected(con, role, optional=False)
    assert con.execute("SELECT to_regclass('workflow.review_fact_state') IS NOT NULL").fetchone()[0]
    result = _observe(con, role, view_check=True)
    assert {"review_fact_state:INSERT", "review_object_facts:UPDATE"} <= set(result["missing_privileges"])
    _grant_expected(con, role)
    assert _observe(con, role, view_check=True)["status"] == "PASS"
    # A partly installed 027 blocks on its missing peer.
    con.execute("DROP TABLE workflow.review_object_facts CASCADE")
    assert _observe(con, role, view_check=True)["missing_relations"] == ["review_object_facts"]
    # Where 027 was never applied (production today), its tables are not required,
    # unless compact cards are enabled.
    con.execute("DROP TABLE workflow.review_fact_state CASCADE")
    assert _observe(con, role, view_check=True)["status"] == "PASS"
    compact = _observe(con, role, view_check=True, compact_cards=True)
    assert compact["missing_relations"][:2] == ["review_fact_state", "review_object_facts"]


def test_missing_schema_usage_blocks_with_its_grant(runtime_role):
    con, role = runtime_role
    _grant_expected(con, role)
    assert _observe(con, role, view_check=True)["status"] == "PASS"
    con.execute(f'REVOKE USAGE ON SCHEMA workflow FROM "{role}"')
    con.execute('REVOKE USAGE ON SCHEMA workflow FROM PUBLIC')
    result = _observe(con, role, view_check=True)
    assert result["status"] == "BLOCKED" and result["missing_privileges"] == ["schema workflow:USAGE"]
    assert result["grants"] == [f'GRANT USAGE ON SCHEMA workflow TO "{role}";']
    con.execute(result["grants"][0])
    assert _observe(con, role, view_check=True)["status"] == "PASS"


def test_missing_connect_blocks_with_its_grant(runtime_role):
    con, role = runtime_role
    _grant_expected(con, role)
    database = con.execute("SELECT current_database()").fetchone()[0]
    con.execute(f'REVOKE CONNECT ON DATABASE "{database}" FROM PUBLIC')
    result = _observe(con, role, view_check=True)
    assert result["missing_privileges"] == [f"database {database}:CONNECT"]
    assert result["grants"] == [f'GRANT CONNECT ON DATABASE "{database}" TO "{role}";']
    con.execute(result["grants"][0])
    assert _observe(con, role, view_check=True)["status"] == "PASS"


def test_compact_card_functions_need_execute(runtime_role):
    con, role = runtime_role
    _grant_expected(con, role)
    con.execute("REVOKE EXECUTE ON FUNCTION workflow.review_card_envelope_for(jsonb) FROM PUBLIC")
    result = _observe(con, role, view_check=True)
    assert result["missing_privileges"] == ["review_card_envelope_for(jsonb):EXECUTE"]
    assert result["grants"] == [f'GRANT EXECUTE ON FUNCTION workflow.review_card_envelope_for(jsonb) TO "{role}";']
    con.execute(result["grants"][0])
    assert _observe(con, role, view_check=True)["status"] == "PASS"


def test_role_that_cannot_log_in_blocks(runtime_role):
    con, role = runtime_role
    _grant_expected(con, role)
    con.execute(f'ALTER ROLE "{role}" NOLOGIN')
    result = _observe(con, role, view_check=True)
    assert result["missing_privileges"] == ["role:LOGIN"] and result["grants"] == [f'ALTER ROLE "{role}" LOGIN;']


def test_nested_helper_functions_are_derived_not_listed(runtime_role):
    con, role = runtime_role
    _grant_expected(con, role)
    con.execute("REVOKE EXECUTE ON FUNCTION workflow.review_read_envelope_for(jsonb) FROM PUBLIC")
    assert _observe(con, role, view_check=True)["missing_privileges"] == ["review_read_envelope_for(jsonb):EXECUTE"]


def test_unknown_role_blocks_without_guessing(runtime_role):
    con, _ = runtime_role
    result = _observe(con, "no-such-runtime-role")
    assert result["status"] == "BLOCKED" and result["error"] == "workflow_runtime_role_missing"
