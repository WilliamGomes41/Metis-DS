from __future__ import annotations

from pathlib import Path

import src.console_asgi as console_asgi
from src.console_asgi import build_app


def test_azure_build_defaults_to_persistent_data_outside_wwwroot(
    tmp_path: Path, monkeypatch
) -> None:
    azure_data = tmp_path / "home" / "data" / "metis-console"
    monkeypatch.setattr(console_asgi, "AZURE_DATA_ROOT", azure_data)
    # Path placement is independent of composition; actual Azure composition is
    # covered with a complete native PG configuration in the #718 tests.
    monkeypatch.setenv("WEBSITE_SITE_NAME", "vvn-metis-console")
    monkeypatch.delenv("CONSOLE_DATA_ROOT", raising=False)
    assert console_asgi._default_data_root() == azure_data
    assert console_asgi._env_path("CONSOLE_DATA_ROOT", console_asgi._default_data_root()) == azure_data
    assert azure_data != tmp_path / "site" / "wwwroot"



def test_azure_startup_script_requires_production_authorities() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "azure_console_startup.sh").read_text(
        encoding="utf-8"
    )
    assert 'CONSOLE_DATA_ROOT="${CONSOLE_DATA_ROOT:-/home/data/metis-console}"' in script
    assert '"${METIS_CANONICAL_STORE:-}" != "postgres"' in script
    assert '"${CONSOLE_IMMUTABLE_SOURCE_STORE:-}" != "azure"' in script
