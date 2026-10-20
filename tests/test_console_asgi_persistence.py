from __future__ import annotations

from pathlib import Path

import src.console_asgi as console_asgi
from src.console_asgi import build_app

from tests.complete_workflow_support import complete_postgres  # noqa: F401
from src.workflow_store_configuration import POSTGRES_STORE_SETTINGS


def test_azure_build_defaults_to_persistent_data_outside_wwwroot(
    tmp_path: Path, monkeypatch, complete_postgres
) -> None:
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore
    azure_data = tmp_path / "home" / "data" / "metis-console"
    wwwroot = tmp_path / "site" / "wwwroot"
    wwwroot.mkdir(parents=True)
    monkeypatch.setattr(console_asgi, "ROOT", wwwroot)
    monkeypatch.setattr(console_asgi, "AZURE_DATA_ROOT", azure_data)
    for key in POSTGRES_STORE_SETTINGS:
        monkeypatch.setenv(key, "postgres")
    monkeypatch.setenv("METIS_CANONICAL_DB_DSN", complete_postgres.dsn)
    monkeypatch.setattr(console_asgi, "_postgres_credential", lambda: None)
    monkeypatch.setattr(console_asgi, "_immutable_source_store", lambda: FakeBlobStore({}))
    monkeypatch.setenv("WEBSITE_SITE_NAME", "test-app")
    monkeypatch.setenv("CONSOLE_PUBLIC_ORIGIN", "https://console.example.test")
    for key in ("CONSOLE_DATA_ROOT", "CONSOLE_SOURCE_STORE", "CONSOLE_RUNTIME",
                "CONSOLE_BOOTSTRAP_USERNAME", "CONSOLE_BOOTSTRAP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)

    kernel = build_app().state.operations_kernel

    assert kernel.source_store == azure_data / "sources" / "private"
    assert kernel.runtime == azure_data / "output" / "runtime" / "operations-console"
    assert not (kernel.runtime / "objects").exists()
    assert not (wwwroot / "output" / "runtime").exists()
    assert not (wwwroot / "sources").exists()


def test_azure_startup_script_requires_production_authorities() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "azure_console_startup.sh").read_text(
        encoding="utf-8"
    )
    assert 'CONSOLE_DATA_ROOT="${CONSOLE_DATA_ROOT:-/home/data/metis-console}"' in script
    assert '"${METIS_CANONICAL_STORE:-}" != "postgres"' in script
    assert '"${CONSOLE_IMMUTABLE_SOURCE_STORE:-}" != "azure"' in script
