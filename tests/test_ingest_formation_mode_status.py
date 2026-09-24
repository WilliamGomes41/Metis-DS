"""Read-only Inleveren projection of the active passage-formation runtime mode.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole
from src.passage_formation_policy_v1 import DETERMINISTIC_MODE, SEMANTIC_MODE
from src.pre_review_semantic_v1 import (
    PASSAGE_FORMATION_MODE_ENV,
    bind_pre_review_semantic_processing,
)


def _console(tmp_path: Path) -> OperationsConsole:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    console.create_account(
        username="researcher.mode",
        password="mode-secret",
        roles=("researcher",),
        display_name="Mode Researcher",
    )
    return console


def _ingest_page(console: OperationsConsole) -> str:
    client = TestClient(create_console_app(console))
    login = client.post(
        "/login",
        data={"username": "researcher.mode", "password": "mode-secret"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    page = client.get("/ingest")
    assert page.status_code == 200
    return page.text


def test_ingest_shows_default_deterministic_runtime_mode_read_only(tmp_path: Path) -> None:
    console = _console(tmp_path)
    bind_pre_review_semantic_processing(console, environ={})

    html = _ingest_page(console)

    assert "Actieve verwerkingsmodus: Deterministisch" in html
    assert (
        "Nieuwe en opnieuw verwerkte passages worden momenteel zonder taalmodel "
        "gevormd. Review blijft verplicht."
    ) in html
    assert console._passage_formation_mode_reader() == DETERMINISTIC_MODE
    assert 'name="passage_formation_mode"' not in html
    assert "Wijzig modus" not in html


def test_ingest_shows_same_injected_semantic_mode_used_by_processing_router(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    env = {PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE}
    bind_pre_review_semantic_processing(console, environ=env)

    html = _ingest_page(console)

    assert "Actieve verwerkingsmodus: Semantisch" in html
    assert (
        "Nieuwe en opnieuw verwerkte passages worden momenteel brongebonden "
        "semantisch gevormd. Review blijft verplicht."
    ) in html
    assert console._passage_formation_mode_reader() == SEMANTIC_MODE
    assert 'name="passage_formation_mode"' not in html


def test_ingest_runtime_status_tracks_same_bound_configuration_mapping(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    env = {PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE}
    bind_pre_review_semantic_processing(console, environ=env)

    assert "Actieve verwerkingsmodus: Semantisch" in _ingest_page(console)

    env[PASSAGE_FORMATION_MODE_ENV] = DETERMINISTIC_MODE

    assert console._passage_formation_mode_reader() == DETERMINISTIC_MODE
    assert "Actieve verwerkingsmodus: Deterministisch" in _ingest_page(console)
