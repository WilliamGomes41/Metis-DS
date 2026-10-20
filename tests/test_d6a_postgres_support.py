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
        assert admin.execute("SELECT count(*) FROM pg_database WHERE datname IN (%s,%s)",
                             (psycopg.conninfo.conninfo_to_dict(first.dsn)["dbname"],
                              psycopg.conninfo.conninfo_to_dict(second.dsn)["dbname"])).fetchone()[0] == 0


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
