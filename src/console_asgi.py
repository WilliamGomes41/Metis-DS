"""ASGI entry for hosting the internal operations console.

Internal researcher surface only. Not a public website. G2 remains BLOCKED.
Bootstrap passwords come from environment, never from Git.
"""
from __future__ import annotations

import os
from pathlib import Path

from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole

ROOT = Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


def bootstrap_accounts(console: OperationsConsole) -> None:
    username = os.environ.get("CONSOLE_BOOTSTRAP_USERNAME", "").strip()
    password = os.environ.get("CONSOLE_BOOTSTRAP_PASSWORD", "")
    if username and password:
        try:
            console.create_account(
                username,
                password,
                roles=["researcher", "reviewer", "publisher"],
                display_name=os.environ.get("CONSOLE_BOOTSTRAP_DISPLAY_NAME") or username,
            )
        except ConsoleError as exc:
            if exc.code != "username_already_exists":
                raise
    reviewer_user = os.environ.get("CONSOLE_BOOTSTRAP_REVIEWER_USERNAME", "").strip()
    reviewer_password = os.environ.get("CONSOLE_BOOTSTRAP_REVIEWER_PASSWORD", "")
    if reviewer_user and reviewer_password:
        try:
            console.create_account(
                reviewer_user,
                reviewer_password,
                roles=["reviewer"],
                display_name=os.environ.get("CONSOLE_BOOTSTRAP_REVIEWER_DISPLAY_NAME") or reviewer_user,
            )
        except ConsoleError as exc:
            if exc.code != "username_already_exists":
                raise


def build_app() -> object:
    data_root = _env_path("CONSOLE_DATA_ROOT", ROOT)
    console = OperationsConsole(
        root=ROOT,
        source_store=_env_path("CONSOLE_SOURCE_STORE", data_root / "sources" / "private"),
        runtime=_env_path("CONSOLE_RUNTIME", data_root / "output" / "runtime" / "operations-console"),
    )
    bootstrap_accounts(console)
    return create_console_app(console)


def __getattr__(name: str) -> object:
    if name == "app":
        return build_app()
    raise AttributeError(name)
