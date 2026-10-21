"""Shared pytest configuration.

Historical Protocol-v2 contract tests remain executable audit evidence after the
Protocol-v3 cutover. Those tests were written when ``PROTOCOL.md``,
``ROADMAP.md`` and ``docs/GOVERNANCE.md`` also acted as an accumulating history
log. During historical tests only, reads of those three paths are therefore
resolved to the frozen pre-v3 snapshots. Current/V3 tests always read the live
root documents.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""

from __future__ import annotations

from pathlib import Path
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest
from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]

from tests.complete_workflow_support import complete_postgres, _isolated_console_postgres  # noqa: F401, E402


def _start_test_postgres(config):
    if getattr(config, "_metis_postgres_dsn", None):
        return config._metis_postgres_dsn
    state_dir = Path(tempfile.mkdtemp(prefix="metis-pytest-postgres-"))
    config._metis_postgres_state_dir = state_dir
    config._metis_previous_dsn = os.environ.get("METIS_TEST_POSTGRES_DSN")
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/test_postgres.sh")],
        env={**os.environ, "PYTHON": sys.executable,
             "METIS_TEST_POSTGRES_STATE_FILE": str(state_dir / "state.json")},
        capture_output=True, text=True,
    )
    if result.returncode:
        raise pytest.UsageError(
            "Console/PostgreSQL tests require a database. " + result.stderr.strip())
    config._metis_postgres_dsn = result.stdout.strip()
    import psycopg
    with psycopg.connect(config._metis_postgres_dsn, connect_timeout=3) as connection:
        can_create = connection.execute(
            "SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname=current_user"
        ).fetchone()[0]
    if not can_create:
        raise pytest.UsageError("Console/PostgreSQL tests require CREATEDB rights for isolated databases")
    os.environ["METIS_TEST_POSTGRES_DSN"] = config._metis_postgres_dsn
    return config._metis_postgres_dsn


def pytest_collection_modifyitems(config, items):
    """Bootstrap before fixtures can skip missing PG evidence; pure suites stay offline.

    During D6a the file scan also covers legacy helper imports and inline DSN
    fixtures. Pure cases in mixed modules can declare ``pure_function``.
    ``file_topology`` identifies behavior scheduled for removal in D6b.
    """
    console = re.compile(
        r"OperationsConsole\(|DurablePublicationConsole\(|AzureAuthoritativePublicationConsole\("
        r"|complete_console|create_console_app|build_app\(|METIS_TEST_POSTGRES_DSN"
    )
    files = {}
    def uses_console(path):
        if path in files:
            return files[path]
        source = path.read_text(encoding="utf-8")
        files[path] = bool(console.search(source))
        if not files[path]:
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tests."):
                    helper = ROOT.joinpath(*node.module.split(".")).with_suffix(".py")
                    if helper.is_file() and uses_console(helper):
                        files[path] = True
                        break
        return files[path]

    for item in items:
        if {"complete_postgres", "production_console", "production_app", "postgres_template"}.intersection(item.fixturenames):
            _start_test_postgres(config)
            return
        if item.get_closest_marker("pure_function") or item.get_closest_marker("file_topology"):
            continue
        path = Path(item.path)
        if uses_console(path):
            _start_test_postgres(config)
            return


def pytest_unconfigure(config):
    directory = getattr(config, "_metis_postgres_state_dir", None)
    if directory is None:
        return
    state = directory / "state.json"
    try:
        if state.exists():
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/test_postgres.sh"), "--stop", str(state)],
                env={**os.environ, "PYTHON": sys.executable}, capture_output=True, text=True,
            )
            if result.returncode:
                raise RuntimeError(result.stderr.strip())
    finally:
        shutil.rmtree(directory)
        previous = config._metis_previous_dsn
        if previous is None:
            os.environ.pop("METIS_TEST_POSTGRES_DSN", None)
        else:
            os.environ["METIS_TEST_POSTGRES_DSN"] = previous


@pytest.fixture(scope="session")
def postgres_template(pytestconfig):
    from psycopg.conninfo import conninfo_to_dict
    from tests.postgres_support import database, install_schema, prefetched_databases

    dsn = _start_test_postgres(pytestconfig)
    with database(dsn) as template:
        install_schema(template.dsn)
        name = conninfo_to_dict(template.dsn)["dbname"]
        with prefetched_databases(dsn, name):
            yield dsn, name


@pytest.fixture
def production_console(tmp_path, complete_postgres):
    """The same composition root as production, backed by this test's database."""
    from tests.production_support import production_application
    apps = {}

    def factory(root=None, **options):
        app = production_application(root or tmp_path, complete_postgres, **options)
        console = app.state.operations_kernel
        apps[console] = app
        return console
    factory.apps = apps
    return factory


@pytest.fixture
def production_app(production_console):
    def factory(console=None, **options):
        console = console if console is not None else production_console(**options)
        return production_console.apps[console]
    return factory


@pytest.fixture
def production_environment(tmp_path, complete_postgres, monkeypatch):
    """Configure explicit ASGI startup tests without replacing the composition root."""
    from tests.production_support import configure_production
    configure_production(monkeypatch, tmp_path, complete_postgres)


_V2_PROTOCOL = ROOT / "docs" / "history" / "protocol-v2" / "PROTOCOL_ROOT_FINAL_2026-09-10.md"
_V2_ROADMAP = ROOT / "docs" / "history" / "protocol-v2" / "ROADMAP_PRE_V3_2026-09-10.md"
_V2_GOVERNANCE = ROOT / "docs" / "history" / "protocol-v2" / "GOVERNANCE_PRE_V3_2026-09-10.md"

_LIVE_TO_HISTORY = {
    (ROOT / "PROTOCOL.md").resolve(): _V2_PROTOCOL,
    (ROOT / "ROADMAP.md").resolve(): _V2_ROADMAP,
    (ROOT / "docs" / "GOVERNANCE.md").resolve(): _V2_GOVERNANCE,
}

_HISTORICAL_FILE_PREFIXES = (
    "tests/test_protocol_v2_",
    "tests/test_roadmap_",
)

_HISTORICAL_EXACT_NODES = {
    "tests/test_g2_azure_preflight.py::test_roadmap_and_changelog_record_readiness_not_pass",
    "tests/test_gd_03_assurance.py::test_gd03_assurance_matches_governance_bytes_and_is_established",
    "tests/test_gd_03_assurance.py::test_gd03_human_record_and_governance_keep_other_decisions_open",
    "tests/test_topology_bound.py::test_roadmap_records_remediation_5_landing_note",
    "tests/test_topology_bound.py::test_remediation_5_does_not_open_multi_writer_extend_or_protocol",
    "tests/test_wave5_gericht_vereenvoudigen.py::test_roadmap_live_norm_is_readable_and_historical_stacks_are_demoted",
}

_orig_read_text = Path.read_text
_orig_read_bytes = Path.read_bytes


def _is_historical_governance_test(nodeid: str) -> bool:
    test_file = nodeid.split("::", 1)[0]
    return test_file.startswith(_HISTORICAL_FILE_PREFIXES) or nodeid in _HISTORICAL_EXACT_NODES


@pytest.fixture(autouse=True)
def _freeze_v2_root_documents_for_historical_contracts(request, monkeypatch):  # type: ignore[no-untyped-def]
    """Make legacy document assertions read the immutable pre-v3 snapshots."""
    if not _is_historical_governance_test(request.node.nodeid):
        return

    def historical_read_text(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        archived = _LIVE_TO_HISTORY.get(self.resolve())
        if archived is not None:
            return _orig_read_text(archived, *args, **kwargs)
        return _orig_read_text(self, *args, **kwargs)

    def historical_read_bytes(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        archived = _LIVE_TO_HISTORY.get(self.resolve())
        if archived is not None:
            return _orig_read_bytes(archived, *args, **kwargs)
        return _orig_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", historical_read_text)
    monkeypatch.setattr(Path, "read_bytes", historical_read_bytes)


class _EmptyCanonicalPublicationAuthority:
    """Canonical test authority with no active publication rows."""

    def active_publication_rows(self) -> list[dict]:
        return []


@pytest.fixture(autouse=True)
def _migrate_legacy_product_api_regression_to_canonical_authority(request, monkeypatch):  # type: ignore[no-untyped-def]
    """Keep the legacy REAL-mode abstention regression valid after PostgreSQL cutover.

    The regression predates the canonical-store requirement and used absence of
    local published JSONL data to represent an empty REAL corpus. REAL mode is
    now PostgreSQL-authoritative, so this single historical caller receives an
    explicit empty canonical authority instead of relying on missing database
    configuration or a local-file fallback.
    """
    if request.node.nodeid != "tests/test_operations_console_mvp.py::test_product_api_still_object_level_retrieve_and_unpublished_abstain":
        return

    from src import product_api_v1

    monkeypatch.setattr(
        product_api_v1,
        "_default_real_store",
        lambda: _EmptyCanonicalPublicationAuthority(),
    )


_orig_init = TestClient.__init__


def _https_init(self, app, base_url: str = "https://testserver", **kwargs):  # type: ignore[no-untyped-def]
    _orig_init(self, app, base_url=base_url, **kwargs)


TestClient.__init__ = _https_init  # type: ignore[method-assign]
