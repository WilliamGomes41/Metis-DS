from __future__ import annotations

from pathlib import Path

import src.console_asgi as console_asgi
from src.console_asgi import build_app


def test_azure_build_defaults_to_persistent_data_outside_wwwroot(
    tmp_path: Path, monkeypatch
) -> None:
    azure_data = tmp_path / "home" / "data" / "metis-console"
    monkeypatch.setattr(console_asgi, "AZURE_DATA_ROOT", azure_data)
    monkeypatch.setenv("WEBSITE_SITE_NAME", "vvn-metis-console")
    monkeypatch.delenv("CONSOLE_DATA_ROOT", raising=False)
    monkeypatch.delenv("CONSOLE_SOURCE_STORE", raising=False)
    monkeypatch.delenv("CONSOLE_RUNTIME", raising=False)
    monkeypatch.delenv("CONSOLE_BOOTSTRAP_USERNAME", raising=False)
    monkeypatch.delenv("CONSOLE_BOOTSTRAP_PASSWORD", raising=False)

    build_app()

    assert (azure_data / "sources" / "private").is_dir()
    assert (azure_data / "output" / "runtime" / "operations-console" / "objects").is_dir()
    assert not (tmp_path / "site" / "wwwroot" / "output" / "runtime").exists()


def test_azure_startup_script_sets_persistent_default() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "azure_console_startup.sh").read_text(
        encoding="utf-8"
    )
    assert 'CONSOLE_DATA_ROOT="${CONSOLE_DATA_ROOT:-/home/data/metis-console}"' in script
