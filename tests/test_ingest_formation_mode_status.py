"""Read-only Inleveren projection of the active passage-formation runtime mode.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.operations_console_v1 import OperationsConsole
from src.passage_formation_policy_v1 import SEMANTIC_MODE
from src.pre_review_semantic_v1 import (
    PASSAGE_FORMATION_MODE_ENV,
    bind_pre_review_semantic_processing,
)


def _console(tmp_path: Path, *, production_console) -> OperationsConsole:
    console = production_console(processing_binder=lambda console: None,
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


def _management_page(console: OperationsConsole, *, production_app) -> str:
    client = TestClient(production_app(console))
    login = client.post(
        "/login",
        data={"username": "researcher.mode", "password": "mode-secret"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert "Actieve verwerkingsmodus" not in client.get("/ingest").text
    page = client.get("/settings/technical")
    assert page.status_code == 200
    return page.text


def test_management_shows_default_source_bound_v2_runtime_mode_read_only(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    bind_pre_review_semantic_processing(console, environ={})

    html = _management_page(console, production_app=production_app)

    assert "Actieve verwerkingsmodus: Semantisch met bronbewijs" in html
    assert (
        "Nieuwe en opnieuw verwerkte passages worden momenteel brongebonden "
        "semantisch gevormd. Review blijft verplicht."
    ) in html
    from src.source_bound_fields_v2 import MODE
    assert console._passage_formation_mode_reader() == MODE
    assert 'name="passage_formation_mode"' not in html
    assert "Wijzig modus" not in html


def test_management_shows_same_injected_semantic_mode_used_by_processing_router(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    env = {PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE}
    bind_pre_review_semantic_processing(console, environ=env)

    html = _management_page(console, production_app=production_app)

    assert "Actieve verwerkingsmodus: Semantisch" in html
    assert (
        "Nieuwe en opnieuw verwerkte passages worden momenteel brongebonden "
        "semantisch gevormd. Review blijft verplicht."
    ) in html
    assert console._passage_formation_mode_reader() == SEMANTIC_MODE
    assert 'name="passage_formation_mode"' not in html


def test_management_runtime_status_tracks_same_bound_configuration_mapping(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    env = {PASSAGE_FORMATION_MODE_ENV: SEMANTIC_MODE}
    bind_pre_review_semantic_processing(console, environ=env)

    assert "Actieve verwerkingsmodus: Semantisch" in _management_page(console, production_app=production_app)

    # The retired rollback mode is shown as the configuration error it is.
    env[PASSAGE_FORMATION_MODE_ENV] = "deterministic-v1"

    assert console._passage_formation_mode_reader() == "deterministic-v1"
    html = _management_page(console, production_app=production_app)
    assert "Actieve verwerkingsmodus: Configuratiefout" in html
    assert "Deterministisch" not in html
