"""ASGI entry for hosting the internal operations console.

Internal researcher surface only. Not a public website. Bootstrap passwords and
database credentials come from the deployment environment, never from Git.

Supported console topology is one worker by default or two workers on one
instance with serialized writes. Multi-instance remains fail-closed. Azure runtime
requires both the durable PostgreSQL canonical publication store and Azure Blob
as the authoritative immutable source store; local development may use the
local source directory. PostgreSQL is the only workflow and canonical authority
everywhere (D6b); there is no file topology and workflow disk mirrors are unused.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.azure_postgres_credential_v1 import CachedAzurePostgresCredential
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.closed_review_loop_v1 import install_closed_review_routes
from src.console_navigation_simplify_v1 import install_navigation_simplification
from src.deterministic_review_repair_v1 import install_deterministic_review_repair_routes
from src.document_status_ui_v1 import install_document_status_ui
from src.g2_source_store import AzureBlobSourceStore
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.proportionate_review_v1 import install_proportionate_review_routes
from src.publish_readiness_ui_v1 import install_publish_readiness_ui
from src.review_closure_v1 import install_review_recovery_page
from src.review_workboard_v1 import install_review_workboard
from src.semantic_safety_app_v1 import install_semantic_safety_routes
from src.structured_logging_v1 import install_startup_reinstall, install_structured_logging
from src.topology_bound_v1 import assert_supported_topology
from src.workflows.workflow_badge_counts_postgres_v1 import (
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
)
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
from src.workflows.workflow_identity_postgres_v1 import (
    PostgresWorkflowIdentityStore,
)
from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores

from src.workflow_store_configuration import (
    postgres_dsn_configured, running_in_azure as _running_in_azure,
    validate_workflow_store_configuration,
)

ROOT = Path(__file__).resolve().parents[1]
AZURE_DATA_ROOT = Path("/home/data/metis-console")


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


def _default_data_root() -> Path:
    """Keep rebuildable runtime copies outside deployment-managed wwwroot."""
    if _running_in_azure():
        return AZURE_DATA_ROOT
    return ROOT


def _console_public_origin(*, running_in_azure: bool) -> str | None:
    origin = os.environ.get("CONSOLE_PUBLIC_ORIGIN", "").strip() or None
    if running_in_azure:
        if origin is None:
            raise RuntimeError("console_public_origin_required_in_azure")
        if not origin.lower().startswith("https://"):
            raise RuntimeError("console_public_origin_must_be_https_in_azure")
    return origin


def _postgres_credential() -> CachedAzurePostgresCredential | None:
    """Create one process-local cached AAD credential for all PG stores without a DSN."""
    if postgres_dsn_configured():
        return None
    return CachedAzurePostgresCredential()


def _canonical_store(*, credential: Any | None = None) -> PostgresCanonicalPublicationStore:
    store = PostgresCanonicalPublicationStore(credential=credential)
    store.verify_schema()
    return store


def _workflow_identity_store(*, credential: Any | None = None) -> PostgresWorkflowIdentityStore:
    if credential is None:
        store = CutoverPostgresWorkflowIdentityStore()
    else:
        store = CutoverPostgresWorkflowIdentityStore(credential=credential)
    store.verify_schema()
    return store


def _workflow_document_store(*, credential: Any | None = None) -> PostgresWorkflowDocumentRuntimeStore:
    store = PostgresConcurrentWorkflowDocumentStore(credential=credential)
    store.verify_cutover_schema()
    return store


def _workflow_review_store(*, credential: Any | None = None) -> PostgresWorkflowReviewStore:
    store = PostgresWorkflowReviewStore(credential=credential)
    store.verify_review_schema()
    return store


def _workflow_remaining_store(*, credential: Any | None = None) -> PostgresWorkflowRemainingStore:
    store = PostgresWorkflowRemainingStore(credential=credential)
    store.verify_remaining_schema()
    return store


def _immutable_source_store() -> AzureBlobSourceStore | None:
    """Azure production may never run without Blob as source-byte authority."""
    kind = os.environ.get("CONSOLE_IMMUTABLE_SOURCE_STORE", "").strip().lower()
    running_in_azure = _running_in_azure()
    if not kind:
        if running_in_azure:
            raise RuntimeError("azure_blob_source_store_required_in_azure")
        return None
    if kind != "azure":
        raise RuntimeError("unsupported_immutable_source_store")
    return AzureBlobSourceStore()


def bootstrap_accounts(console: OperationsConsole) -> None:
    if os.getenv("METIS_CONSOLE_AUTH", "local").strip().lower() == "entra":
        return
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
    install_structured_logging()
    validate_workflow_store_configuration()
    topology = assert_supported_topology()
    data_root = _env_path("CONSOLE_DATA_ROOT", _default_data_root())
    immutable_store = _immutable_source_store()
    postgres_credential = _postgres_credential()
    canonical_store = _canonical_store(credential=postgres_credential)
    workflow_identity_store = _workflow_identity_store(credential=postgres_credential)
    workflow_document_store = _workflow_document_store(credential=postgres_credential)
    workflow_review_store = _workflow_review_store(credential=postgres_credential)
    workflow_remaining_store = _workflow_remaining_store(credential=postgres_credential)
    running_in_azure = _running_in_azure()

    bind_workflow_stores(
        workflow_identity_store,
        workflow_document_store,
        workflow_review_store,
        workflow_remaining_store,
    )
    console_cls = (
        FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole
        if running_in_azure
        else FastBadgePostgresCompleteWorkflowDurablePublicationConsole
    )
    console = console_cls(
        root=ROOT,
        source_store=_env_path("CONSOLE_SOURCE_STORE", data_root / "sources" / "private"),
        runtime=_env_path("CONSOLE_RUNTIME", data_root / "output" / "runtime" / "operations-console"),
        immutable_source_store=immutable_store,
        canonical_publication_store=canonical_store,
        workflow_identity_store=workflow_identity_store,
        workflow_document_store=workflow_document_store,
        workflow_review_store=workflow_review_store,
        workflow_remaining_store=workflow_remaining_store,
    )

    bind_pre_review_semantic_processing(console)

    # Gunicorn workers initialize independently. Keep migration and local-copy
    # reconciliation inside the same process-shared store lock used by runtime
    # commits, and refresh after acquiring it so worker two cannot replay a
    # stale startup snapshot over worker one's completed work.
    with console._store_write_lock():
        console._reload_store_locked()
        bootstrap_accounts(console)
        console.migrate_legacy_revise_to_review()
        console.reconcile_durable_publications()

    return build_console_app(
        console, trusted_origin=_console_public_origin(running_in_azure=running_in_azure),
        topology=topology,
    )


def build_console_app(console: OperationsConsole, *, trusted_origin=None, topology=None):
    """Install the production routes for both ASGI startup and console tests."""
    app = create_console_app(console, trusted_origin=trusted_origin)
    install_publish_readiness_ui(app, console)
    install_document_status_ui(app, console)
    install_review_workboard(app, console)
    install_proportionate_review_routes(app, console)
    install_deterministic_review_repair_routes(app, console)
    install_closed_review_routes(app, console)
    install_review_recovery_page(app, console)
    install_semantic_safety_routes(app, console)
    install_navigation_simplification(app)
    app.state.operations_kernel = console
    app.state.console_topology = topology
    # Register last so timings include status/auth middleware and all DB reads.
    from src.telemetry.install import install_console_observability
    install_console_observability(app, console.runtime)
    install_startup_reinstall(app)  # Metis 638-1: after the server's own log setup
    return app


def __getattr__(name: str) -> object:
    if name == "app":
        return build_app()
    raise AttributeError(name)
