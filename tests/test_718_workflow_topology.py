"""#718/D6b: PostgreSQL is the only console authority; no file topology can be chosen.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from itertools import product

import pytest

from src import console_asgi as asgi

from src.workflow_store_configuration import (
    POSTGRES_CONNECTION_SETTINGS, POSTGRES_DSN_SETTING, POSTGRES_STORE_SETTINGS as SETTINGS,
)

STORAGE = ("_postgres_credential", "_canonical_store", "_immutable_source_store",
           "_workflow_identity_store", "_workflow_document_store",
           "_workflow_review_store", "_workflow_remaining_store")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch, tmp_path):
    for key in (*SETTINGS, *POSTGRES_CONNECTION_SETTINGS, POSTGRES_DSN_SETTING,
                "WEBSITE_SITE_NAME", "CONSOLE_IMMUTABLE_SOURCE_STORE",
                "CONSOLE_BOOTSTRAP_USERNAME", "CONSOLE_BOOTSTRAP_PASSWORD",
                "CONSOLE_SOURCE_STORE", "CONSOLE_RUNTIME"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CONSOLE_DATA_ROOT", str(tmp_path / "untouched"))


def _forbid_storage(monkeypatch):
    touched = []

    def forbidden(*args, **kwargs):
        touched.append(True)
        raise AssertionError("storage_or_credentials_opened_before_refusal")

    for name in STORAGE:
        monkeypatch.setattr(asgi, name, forbidden)
    return touched


SELECTIONS = list(product((False, True), repeat=len(SETTINGS)))


@pytest.mark.parametrize("azure", [False, True])
@pytest.mark.parametrize("bits", SELECTIONS)
def test_no_selector_combination_starts_without_postgres(bits, azure, monkeypatch, tmp_path):
    """Retired selectors choose nothing: without PostgreSQL every start is refused."""
    for key, enabled in zip(SETTINGS, bits):
        if enabled:
            monkeypatch.setenv(key, "postgres")
    if azure:
        monkeypatch.setenv("WEBSITE_SITE_NAME", "test-app")
    touched = _forbid_storage(monkeypatch)
    with pytest.raises(RuntimeError, match="^postgres_authority_configuration_required$"):
        asgi.build_app()
    assert touched == []
    assert not (tmp_path / "untouched").exists()


@pytest.mark.parametrize("missing", POSTGRES_CONNECTION_SETTINGS)
def test_incomplete_managed_identity_configuration_refused(missing, monkeypatch):
    for key in POSTGRES_CONNECTION_SETTINGS:
        if key != missing:
            monkeypatch.setenv(key, "configured")
    touched = _forbid_storage(monkeypatch)
    with pytest.raises(RuntimeError, match="^postgres_authority_configuration_required$"):
        asgi.build_app()
    assert touched == []


@pytest.mark.parametrize("value", ["file", "local", "postgress", "json"])
@pytest.mark.parametrize("key", SETTINGS)
def test_retired_selector_with_another_value_is_refused(key, value, monkeypatch):
    monkeypatch.setenv(POSTGRES_DSN_SETTING, "postgresql://unused.invalid/metis")
    monkeypatch.setenv(key, value)
    touched = _forbid_storage(monkeypatch)
    with pytest.raises(RuntimeError, match="^unsupported_" + key.removeprefix("METIS_").lower() + "$"):
        asgi.build_app()
    assert touched == []


@pytest.mark.parametrize("azure", [False, True])
@pytest.mark.parametrize("kind", [None, "postgres", " POSTGRES "])
@pytest.mark.parametrize("connection", ["dsn", "managed_identity"])
def test_postgres_configuration_reaches_storage(monkeypatch, azure, kind, connection):
    if connection == "dsn":
        monkeypatch.setenv(POSTGRES_DSN_SETTING, "postgresql://unused.invalid/metis")
    else:
        for key in POSTGRES_CONNECTION_SETTINGS:
            monkeypatch.setenv(key, "configured")
    if kind is not None:
        for key in SETTINGS:
            monkeypatch.setenv(key, kind)
    if azure:
        monkeypatch.setenv("WEBSITE_SITE_NAME", "test-app")
    class ReachedStorage(Exception):
        pass
    def storage():
        raise ReachedStorage
    monkeypatch.setattr(asgi, "_immutable_source_store", storage)
    with pytest.raises(ReachedStorage):
        asgi.build_app()


@pytest.mark.parametrize("command", ["cmd_serve_console", "cmd_console_account"])
def test_local_cli_refuses_without_postgres(monkeypatch, command):
    from argparse import Namespace
    from src import cli
    touched = _forbid_storage(monkeypatch)
    import uvicorn
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: pytest.fail("served without PostgreSQL"))
    with pytest.raises(RuntimeError, match="^postgres_authority_configuration_required$"):
        getattr(cli, command)(Namespace(source_store=None, runtime=None, host="127.0.0.1", port=0,
                                        username="u", password="p", roles="reviewer", display_name=None))
    assert touched == []


@pytest.mark.parametrize("azure", [False, True])
def test_native_complete_build_login_and_restart(azure, tmp_path, monkeypatch, recovery_postgres):
    from fastapi.testclient import TestClient
    for key in SETTINGS:
        monkeypatch.setenv(key, "postgres")
    monkeypatch.setenv("METIS_CANONICAL_DB_DSN", recovery_postgres.dsn)
    monkeypatch.setattr(asgi, "_postgres_credential", lambda: None)
    if azure:
        monkeypatch.setenv("WEBSITE_SITE_NAME", "test-app")
        monkeypatch.setenv("CONSOLE_PUBLIC_ORIGIN", "https://console.example.test")
        # Immutable bytes are outside this configuration/PG proof. No paid calls.
        from tests.test_publication_chain_recovery_v1 import FakeBlobStore
        monkeypatch.setattr(asgi, "_immutable_source_store", lambda: FakeBlobStore({}))
    app = asgi.build_app()
    kernel = app.state.operations_kernel
    assert kernel.workflow_remaining_store is not None
    assert kernel.canonical_publication_store is not None
    created = kernel.create_account("topology.reviewer", "topology-test-secret", roles=["reviewer"])
    with TestClient(app) as client:
        assert client.get("/login").status_code == 200
    fresh_root = tmp_path / "fresh-worker"
    assert not fresh_root.exists()
    monkeypatch.setenv("CONSOLE_DATA_ROOT", str(fresh_root))
    restarted = asgi.build_app().state.operations_kernel
    authenticated = restarted.authenticate("topology.reviewer", "topology-test-secret")
    assert authenticated["account_id"] == created["account_id"]


from tests.complete_workflow_support import complete_postgres as recovery_postgres  # noqa: F401,E402


def test_local_cli_uses_the_production_composition(tmp_path, monkeypatch, recovery_postgres):
    """serve-console and console-account start the same PostgreSQL console as ASGI."""
    from argparse import Namespace
    import uvicorn
    from fastapi.testclient import TestClient
    from src import cli
    from src.workflows.workflow_badge_counts_postgres_v1 import (
        FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
    )
    monkeypatch.setenv(POSTGRES_DSN_SETTING, recovery_postgres.dsn)
    monkeypatch.setattr(asgi, "_postgres_credential", lambda: None)
    served = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: served.setdefault("app", app))
    runtime, sources = tmp_path / "runtime", tmp_path / "sources"
    arguments = dict(source_store=sources, runtime=runtime, host="127.0.0.1", port=0)
    created = cli.cmd_console_account(Namespace(**arguments, username="cli.reviewer", password="cli-test-secret",
                                                roles="reviewer", display_name=None))["account"]
    cli.cmd_serve_console(Namespace(**arguments))
    kernel = served["app"].state.operations_kernel
    assert type(kernel) is FastBadgePostgresCompleteWorkflowDurablePublicationConsole
    assert kernel.runtime == runtime and kernel.source_store == sources
    assert kernel.authenticate("cli.reviewer", "cli-test-secret")["account_id"] == created["account_id"]
    with TestClient(served["app"]) as client:
        assert client.get("/login").status_code == 200
    assert not any(runtime.glob("*.json")), "workflow state must not be written to files"


def test_no_console_class_without_complete_postgres_authority_constructs(tmp_path):
    """Production refuses every console class below the complete PostgreSQL composition."""
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-c", f"""
import json
from pathlib import Path
from src.operations_console_v1 import OperationsConsole
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.azure_authoritative_publication_console_v1 import AzureAuthoritativePublicationConsole
from src.review_closure_v1 import ReviewClosureConsole
from src.workflows.workflow_identity_postgres_v1 import PostgresIdentityDurablePublicationConsole
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDurablePublicationConsole
from src.workflows.workflow_review_cutover_v1 import PostgresReviewWorkflowDurablePublicationConsole
root = Path({str(tmp_path)!r})
canonical = dict(canonical_publication_store=object())
identity = dict(canonical, workflow_identity_store=object())
documents = dict(identity, workflow_document_store=object())
review = dict(documents, workflow_review_store=object())
outcomes = {{}}
for cls, stores in ((OperationsConsole, {{}}), (ReviewClosureConsole, {{}}),
                    (DurablePublicationConsole, canonical), (AzureAuthoritativePublicationConsole, canonical),
                    (PostgresIdentityDurablePublicationConsole, identity),
                    (PostgresWorkflowDurablePublicationConsole, documents),
                    (PostgresReviewWorkflowDurablePublicationConsole, review)):
    try:
        cls(root=root, **stores)
        outcomes[cls.__name__] = "constructed"
    except RuntimeError as exc:
        outcomes[cls.__name__] = str(exc)
print(json.dumps(outcomes))
"""], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    import json
    outcomes = json.loads(result.stdout)
    assert len(outcomes) == 7
    assert set(outcomes.values()) <= {"postgres_workflow_authority_required",
                                      "canonical_publication_store_required",
                                      "workflow_review_store_required_for_document_store"}, outcomes
    assert not list(tmp_path.iterdir()), "a refused console created runtime files"
