"""Behavioral design probes, deliberately outside production code and test suite."""
import json
import os
from pathlib import Path
import time
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from tests.postgres_support import database, install_schema
from src.workflows.workflow_postgres_migration_v1 import (
    observe_runtime_privileges, RUNTIME_TABLE_PRIVILEGES,
    OPTIONAL_TABLE_PRIVILEGES, RUNTIME_SEQUENCE_PRIVILEGES,
)

OUT = Path(__file__).resolve().parent
results = []

def record(name, **details):
    results.append({'probe': name, **details})

with database(os.environ['METIS_TEST_POSTGRES_DSN']) as config:
    install_schema(config.dsn)
    role = 'design_runtime_' + uuid.uuid4().hex[:10]
    group = 'design_group_' + uuid.uuid4().hex[:10]
    with psycopg.connect(config.dsn, autocommit=True, row_factory=dict_row) as admin:
        admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(role)))
        try:
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA workflow TO {}').format(sql.Identifier(role)))
            for table, privileges in {**RUNTIME_TABLE_PRIVILEGES, **OPTIONAL_TABLE_PRIVILEGES}.items():
                admin.execute(sql.SQL('GRANT {} ON workflow.{} TO {}').format(
                    sql.SQL(', '.join(privileges)), sql.Identifier(table), sql.Identifier(role)))
            for sequence, privileges in RUNTIME_SEQUENCE_PRIVILEGES.items():
                admin.execute(sql.SQL('GRANT {} ON SEQUENCE workflow.{} TO {}').format(
                    sql.SQL(', '.join(privileges)), sql.Identifier(sequence), sql.Identifier(role)))
            assert observe_runtime_privileges(admin, role, view_check=True)['status'] == 'PASS'
            admin.execute(sql.SQL('GRANT UPDATE ON workflow.publication_refusals TO {}').format(sql.Identifier(role)))
            report = observe_runtime_privileges(admin, role, view_check=True)
            assert report['status'] == 'PASS'
            admin.execute("INSERT INTO workflow.publication_refusals(recorded_at,snapshot_id,object_version,actor,verdict,reason_codes,dedup_key,schema_version) VALUES(now(),'design-snapshot','1','original','refused','[]','design-dedup','1')")
            admin.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
            changed = admin.execute("UPDATE workflow.publication_refusals SET actor='changed' WHERE dedup_key='design-dedup'").rowcount
            admin.execute('RESET ROLE')
            assert changed == 1
            record('excess_privilege_not_detected', current_verifier=report['status'], unauthorized_by_design_update_succeeded=True)
            admin.execute(sql.SQL('REVOKE UPDATE ON workflow.publication_refusals FROM {}').format(sql.Identifier(role)))
            assert observe_runtime_privileges(admin, role, view_check=True)['status'] == 'PASS'
            admin.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
            try:
                admin.execute("UPDATE workflow.publication_refusals SET actor='forbidden' WHERE dedup_key='design-dedup'")
                raise AssertionError('UPDATE unexpectedly allowed')
            except psycopg.errors.InsufficientPrivilege:
                pass
            finally:
                admin.execute('RESET ROLE')
            assert admin.execute("SELECT actor FROM workflow.publication_refusals WHERE dedup_key='design-dedup'").fetchone()['actor'] == 'changed'
            record('targeted_revoke_preserves_minimum', current_verifier='PASS', update_denied=True, row_unchanged=True)
            admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(group)))
            admin.execute(sql.SQL('GRANT UPDATE ON workflow.publication_refusals TO {}').format(sql.Identifier(group)))
            admin.execute(sql.SQL('GRANT {} TO {}').format(sql.Identifier(group), sql.Identifier(role)))
            admin.execute(sql.SQL('REVOKE UPDATE ON workflow.publication_refusals FROM {}').format(sql.Identifier(role)))
            inherited = admin.execute("SELECT has_table_privilege(%s,'workflow.publication_refusals','UPDATE') AS ok", (role,)).fetchone()['ok']
            assert inherited
            record('direct_revoke_does_not_remove_inherited_grant', effective_update=inherited)
            admin.execute(sql.SQL('REVOKE {} FROM {}').format(sql.Identifier(group), sql.Identifier(role)))
            admin.execute('GRANT UPDATE ON workflow.publication_refusals TO PUBLIC')
            public = admin.execute("SELECT has_table_privilege(%s,'workflow.publication_refusals','UPDATE') AS ok", (role,)).fetchone()['ok']
            assert public
            admin.execute('REVOKE UPDATE ON workflow.publication_refusals FROM PUBLIC')
            record('public_grant_counts_as_effective_privilege', effective_update=public)

            with psycopg.connect(config.dsn) as holder:
                holder.execute('SELECT * FROM workflow.documents LIMIT 0')
                start = time.monotonic()
                try:
                    with admin.transaction():
                        admin.execute("SET LOCAL lock_timeout='300ms'")
                        admin.execute('ALTER TABLE workflow.documents ADD COLUMN design_lock_probe TEXT')
                    raise AssertionError('ALTER unexpectedly acquired lock')
                except psycopg.errors.LockNotAvailable as error:
                    assert error.sqlstate == '55P03'
                elapsed = time.monotonic()-start
                assert not admin.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='workflow' AND table_name='documents' AND column_name='design_lock_probe'").fetchone()
                holder.rollback()
            assert admin.execute('SHOW lock_timeout').fetchone()['lock_timeout'] == '0'
            with admin.transaction():
                admin.execute("SET LOCAL lock_timeout='300ms'")
                admin.execute('ALTER TABLE workflow.documents ADD COLUMN design_lock_probe TEXT')
            assert admin.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='workflow' AND table_name='documents' AND column_name='design_lock_probe'").fetchone()
            record('bounded_ddl_lock_and_retry', sqlstate='55P03', timeout_seconds=round(elapsed,3), failed_attempt_left_no_column=True, retry_succeeded=True, setting_did_not_leak=True)
            with admin.transaction():
                try:
                    with admin.transaction():
                        admin.execute('CREATE INDEX CONCURRENTLY design_probe_idx ON workflow.documents(title)')
                    raise AssertionError('Concurrent index allowed inside transaction')
                except psycopg.errors.ActiveSqlTransaction:
                    pass
            admin.execute('CREATE INDEX CONCURRENTLY design_probe_idx ON workflow.documents(title)')
            record('concurrent_index_requires_separate_execution', transaction_rejected=True, autocommit_succeeded=True)
        finally:
            admin.execute('RESET ROLE')
            admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
            if admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (group,)).fetchone():
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(group)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(group)))

port = int(os.environ['DESIGN_PROBE_PORT'])
tls = dict(hostaddr='127.0.0.1', port=port, dbname='postgres', user='postgres',
           sslrootcert=os.environ['DESIGN_PROBE_CERT'], connect_timeout=3)
with psycopg.connect(**tls, host='localhost', sslmode='verify-full') as con:
    assert con.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()[0]
record('tls_correct_hostname', verify_full_succeeded=True, ssl_active=True)
try:
    psycopg.connect(**tls, host='wrong-host.invalid', sslmode='verify-full')
    raise AssertionError('Wrong hostname unexpectedly accepted')
except psycopg.OperationalError as error:
    assert 'does not match host name' in str(error)
record('tls_wrong_hostname', verify_full_rejected=True)
with psycopg.connect(**tls, host='wrong-host.invalid', sslmode='require') as con:
    assert con.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()[0]
record('tls_require_wrong_hostname', connection_succeeded=True, ssl_active=True)
for result in results:
    print(json.dumps(result, sort_keys=True))
(OUT/'probes.json').write_text(json.dumps(results, indent=2)+'\n')
