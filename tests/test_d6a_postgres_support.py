"""D6a: real composition, independent commits, collection failure and server cleanup.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import os
import subprocess
import sys

import psycopg
import pytest

from tests.postgres_support import ROOT, database


@pytest.mark.parametrize("azure", [False, True])
def test_factories_use_asgi_classes_and_all_routes(
    production_console, production_app, production_environment, monkeypatch, azure,
):
    from src import console_asgi
    from tests.test_durable_publication_console_v1 import MemorySourceStore

    source = MemorySourceStore()
    if azure:
        monkeypatch.setenv("WEBSITE_SITE_NAME", "d6a-test")
        monkeypatch.setenv("CONSOLE_PUBLIC_ORIGIN", "https://console.example.test")
    monkeypatch.setattr(console_asgi, "_immutable_source_store", lambda: source)
    direct = console_asgi.build_app()
    console = production_console(azure=azure, immutable_source_store=source)
    app = production_app(console)
    assert type(console) is type(direct.state.operations_kernel)
    def routes(app):
        return [(route.path, getattr(route, "methods", None), type(route)) for route in app.routes]
    assert routes(app) == routes(direct)
    assert [m.cls for m in app.user_middleware] == [m.cls for m in direct.user_middleware]


def test_template_copies_keep_commits_visible_and_databases_independent(postgres_template):
    dsn, template = postgres_template
    with database(dsn, template=template) as first, database(dsn, template=template) as second:
        with psycopg.connect(first.dsn) as con:
            con.execute("INSERT INTO workflow.topics(topic_id,identity_key,display_name) VALUES ('first','first','First')")
        with psycopg.connect(first.dsn) as fresh, psycopg.connect(second.dsn) as other:
            assert fresh.execute("SELECT count(*) FROM workflow.topics").fetchone()[0] == 1
            assert other.execute("SELECT count(*) FROM workflow.topics").fetchone()[0] == 0
    with psycopg.connect(dsn) as admin:
        from tests.postgres_support import _copies
        _copies[dsn, template].flush()
        assert admin.execute("SELECT count(*) FROM pg_database WHERE datname IN (%s,%s)",
                             (psycopg.conninfo.conninfo_to_dict(first.dsn)["dbname"],
                              psycopg.conninfo.conninfo_to_dict(second.dsn)["dbname"])).fetchone()[0] == 0


def test_prefetch_keeps_fresh_committed_copies_and_cleans_up_after_exception(postgres_template):
    from tests.postgres_support import prefetched_databases
    dsn, template = postgres_template
    connect = psycopg.connect
    with database(dsn, template=template) as nested_template:
        name = psycopg.conninfo.conninfo_to_dict(nested_template.dsn)["dbname"]
        with prefetched_databases(dsn, name) as copies:
            with pytest.MonkeyPatch.context() as patch:
                def forbidden(*args, **kwargs):
                    raise AssertionError("A test-local connection spy must not intercept administrative work")
                patch.setattr(psycopg, "connect", forbidden)
                owned = []
                for value in ("first", "second"):
                    with database(dsn, template=name) as config:
                        owned.append(psycopg.conninfo.conninfo_to_dict(config.dsn)["dbname"])
                        with connect(config.dsn) as connection:
                            assert connection.execute("SELECT count(*) FROM workflow.topics").fetchone()[0] == 0
                            connection.execute("INSERT INTO workflow.topics(topic_id,identity_key,display_name) VALUES (%s,%s,%s)",
                                               (value, value, value))
                        with connect(config.dsn) as fresh:
                            assert fresh.execute("SELECT topic_id FROM workflow.topics").fetchone()[0] == value
                with pytest.raises(RuntimeError, match="test body failed"):
                    with database(dsn, template=name):
                        raise RuntimeError("test body failed")
                owned.append(copies.ready.result())
        assert copies.owned == set()
        with connect(dsn) as admin:
            assert admin.execute("SELECT count(*) FROM pg_database WHERE datname = ANY(%s)", (owned,)).fetchone()[0] == 0


def test_prefetch_reports_background_creation_failure(postgres_template):
    from tests.postgres_support import prefetched_databases
    dsn, _ = postgres_template
    with pytest.raises(ExceptionGroup, match="Could not prepare or remove") as failure:
        with prefetched_databases(dsn, "metis_missing_template"):
            pass
    assert isinstance(failure.value.exceptions[0], psycopg.errors.InvalidCatalogName)


@pytest.mark.pure_function
def test_missing_postgres_fails_once_during_collection_but_pure_cases_can_run():
    env = {**os.environ, "PGBIN": "/missing/d6a/postgresql", "PYTHON": sys.executable}
    env.pop("METIS_TEST_POSTGRES_DSN", None)
    env.pop("PYTEST_ADDOPTS", None)
    failed = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                             "tests/test_console_asgi.py::test_bootstrap_creates_owner_once"],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert failed.returncode == 4
    assert failed.stderr.count("Console/PostgreSQL tests require a database") == 1
    assert "SKIPPED" not in failed.stdout
    indirect = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                                "tests/test_decision_graph_structure.py"],
                               cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert indirect.returncode == 4
    assert indirect.stderr.count("Console/PostgreSQL tests require a database") == 1
    pure = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_workflow_postgres_schema.py",
                           "tests/test_console_asgi.py::test_azure_console_requires_explicit_https_public_origin",
                           "tests/test_workflow_identity_postgres_v1.py::test_local_only_account_listing_uses_local_authority"],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert pure.returncode == 0, pure.stdout + pure.stderr


def test_start_script_reuses_configured_server_without_owning_it(complete_postgres, tmp_path):
    state = tmp_path / "state.json"
    result = subprocess.run(["bash", str(ROOT / "scripts/test_postgres.sh")],
                            env={**os.environ, "PYTHON": sys.executable,
                                 "METIS_TEST_POSTGRES_DSN": complete_postgres.dsn,
                                 "METIS_TEST_POSTGRES_STATE_FILE": str(state), "PGBIN": "/missing/unused"},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == complete_postgres.dsn
    assert not state.exists()


@pytest.mark.parametrize("kind", ["fake", "foreign-database"])
def test_factory_refuses_a_fake_or_different_canonical_authority(production_console, kind):
    from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig, PostgresCanonicalPublicationStore
    store = object() if kind == "fake" else PostgresCanonicalPublicationStore(
        PostgresCanonicalConfig(dsn="postgresql://postgres@127.0.0.1:1/foreign_database"))
    with pytest.raises(ValueError, match="Canonical store must be the production PostgreSQL store for this test database"):
        production_console(canonical_publication_store=store)


from tests.complete_workflow_support import complete_postgres as legacy_postgres  # noqa: E402,F401


def test_legacy_fixture_alias_observes_the_factorys_committed_accounts(legacy_postgres, production_console):
    from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
    console = production_console()
    account = console.create_account('shared-fixture', 'fixture-test-secret', roles=['reviewer'])
    assert PostgresWorkflowIdentityStore(legacy_postgres).account_by_id(account['account_id']) is not None


def test_independent_factory_copies_keep_identities_and_sessions_separate(production_console):
    from src.operations_console_v1 import ConsoleError
    from tests.production_support import restart_production
    first = production_console(processing_binder=lambda console: None)
    other = production_console(processing_binder=lambda console: None, isolated=True)
    assert first.workflow_document_store.config != other.workflow_document_store.config
    first.create_account(username='same-name', password='fixture-password', roles=['researcher'])
    assert other.list_accounts() == []
    other.create_account(username='same-name', password='fixture-password', roles=['reviewer'])
    token = first.authenticate('same-name', 'fixture-password')['token']
    with pytest.raises(ConsoleError, match='not_authenticated'):
        other.session_account(token)
    assert restart_production(first).session_account(token)['roles'] == ['researcher']
    assert restart_production(other).list_accounts()[0]['roles'] == ['reviewer']
