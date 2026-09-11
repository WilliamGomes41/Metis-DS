"""ASGI entry for hosting the internal operations console.

Internal researcher surface only. Not a public website. G2 remains BLOCKED.
Bootstrap passwords come from environment, never from Git.

Supported topology (Post-#120 remediation 5): one Gunicorn worker /
one instance / sequential writes. ``build_app()`` fail-closes if a
multi-writer assumption is declared. EXTEND for multiple writers is later.
"""
from __future__ import annotations

import os
from pathlib import Path

from src.audit_llm_settings_v1 import install_audit_llm_settings_routes
from src.audit_room_v1 import install_audit_routes
from src.closed_review_loop_v1 import install_closed_review_routes
from src.console_navigation_simplify_v1 import install_navigation_simplification
from src.deterministic_review_repair_v1 import install_deterministic_review_repair_routes
from src.g2_source_store import AzureBlobSourceStore
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.proportionate_review_v1 import install_proportionate_review_routes
from src.review_closure_v1 import ReviewClosureConsole, harden_legacy_repair_routes
from src.topology_bound_v1 import assert_supported_topology

ROOT = Path(__file__).resolve().parents[1]
AZURE_DATA_ROOT = Path("/home/data/metis-console")


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


def _default_data_root() -> Path:
    """Keep Azure runtime data outside the deployment-managed wwwroot."""
    if os.environ.get("WEBSITE_SITE_NAME", "").strip():
        return AZURE_DATA_ROOT
    return ROOT


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
    assert_supported_topology()
    data_root = _env_path("CONSOLE_DATA_ROOT", _default_data_root())
    immutable_store = None
    source_store_kind = os.environ.get("CONSOLE_IMMUTABLE_SOURCE_STORE", "").strip().lower()
    if source_store_kind:
        if source_store_kind != "azure":
            raise RuntimeError("unsupported_immutable_source_store")
        immutable_store = AzureBlobSourceStore()
    console = ReviewClosureConsole(
        root=ROOT,
        source_store=_env_path("CONSOLE_SOURCE_STORE", data_root / "sources" / "private"),
        runtime=_env_path("CONSOLE_RUNTIME", data_root / "output" / "runtime" / "operations-console"),
        immutable_source_store=immutable_store,
    )
    bootstrap_accounts(console)
    # One-time/idempotent compatibility step for revise rows persisted before
    # structured repair existed. They must re-enter Review, not a legacy editor.
    console.migrate_legacy_revise_to_review()
    app = create_console_app(console)
    install_proportionate_review_routes(app, console)
    install_audit_llm_settings_routes(app, console)
    install_deterministic_review_repair_routes(app, console)
    # Register exact closed-loop routes before the generic /audit/{audit_id} route.
    install_closed_review_routes(app, console)
    # Delete the old writable repair endpoints after route installation. Only the
    # structured /review/resolve path may write a repair in the live runtime.
    harden_legacy_repair_routes(app, console)
    install_audit_routes(app, console)
    # Presentation-only: remove duplicate non-Audit doors after all routes exist.
    install_navigation_simplification(app)
    return app


def __getattr__(name: str) -> object:
    if name == "app":
        return build_app()
    raise AttributeError(name)
