"""ASGI entry for hosting the internal operations console.

Internal researcher surface only. Not a public website. Bootstrap passwords and
database credentials come from the deployment environment, never from Git.

Supported console topology remains one Gunicorn worker / one instance with
serialized writes until explicit multi-instance proof lands. Azure runtime
requires both the durable PostgreSQL canonical publication store and Azure Blob
as the authoritative immutable source store; local development may continue
without either. Shared PostgreSQL workflow layers are opt-in until Azure cut-over.
"""
from __future__ import annotations

import os
from pathlib import Path

from src.audit_llm_settings_v1 import install_audit_llm_settings_routes
from src.audit_room_v1 import install_audit_routes
from src.azure_authoritative_publication_console_v1 import AzureAuthoritativePublicationConsole
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.closed_review_loop_v1 import install_closed_review_routes
from src.console_navigation_simplify_v1 import install_navigation_simplification
from src.deterministic_review_repair_v1 import install_deterministic_review_repair_routes
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.g2_source_store import AzureBlobSourceStore
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.proportionate_review_v1 import install_proportionate_review_routes
from src.review_closure_v1 import harden_legacy_repair_routes
from src.topology_bound_v1 import assert_supported_topology
from src.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflow_documents_cutover_v1 import (
    PostgresWorkflowAzureAuthoritativePublicationConsole,
    PostgresWorkflowDocumentRuntimeStore,
    PostgresWorkflowDurablePublicationConsole,
)
from src.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
from src.workflow_identity_postgres_v1 import (
    PostgresIdentityAzureAuthoritativePublicationConsole,
    PostgresIdentityDurablePublicationConsole,
    PostgresWorkflowIdentityStore,
)
from src.workflow_remaining_cutover_v1 import (
    PostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
    PostgresCompleteWorkflowDurablePublicationConsole,
    bind_remaining_route_backends,
)
from src.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflow_review_cutover_v1 import (
    PostgresReviewWorkflowAzureAuthoritativePublicationConsole,
    PostgresReviewWorkflowDurablePublicationConsole,
)
from src.workflow_review_postgres_v1 import PostgresWorkflowReviewStore

ROOT = Path(__file__).resolve().parents[1]
AZURE_DATA_ROOT = Path("/home/data/metis-console")


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


def _running_in_azure() -> bool:
    return bool(os.environ.get("WEBSITE_SITE_NAME", "").strip())


def _default_data_root() -> Path:
    """Keep rebuildable runtime copies outside deployment-managed wwwroot."""
    if _running_in_azure():
        return AZURE_DATA_ROOT
    return ROOT


def _canonical_store() -> PostgresCanonicalPublicationStore | None:
    kind = os.environ.get("METIS_CANONICAL_STORE", "").strip().lower()
    running_in_azure = _running_in_azure()
    if not kind:
        if running_in_azure:
            raise RuntimeError("canonical_store_required_in_azure")
        return None
    if kind != "postgres":
        raise RuntimeError("unsupported_canonical_store")
    store = PostgresCanonicalPublicationStore()
    store.verify_schema()
    return store


def _workflow_identity_store() -> PostgresWorkflowIdentityStore | None:
    kind = os.environ.get("METIS_WORKFLOW_STORE", "").strip().lower()
    if not kind:
        return None
    if kind != "postgres":
        raise RuntimeError("unsupported_workflow_store")
    store = CutoverPostgresWorkflowIdentityStore()
    store.verify_schema()
    return store


def _workflow_document_store() -> PostgresWorkflowDocumentRuntimeStore | None:
    kind = os.environ.get("METIS_WORKFLOW_DOCUMENT_STORE", "").strip().lower()
    if not kind:
        return None
    if kind != "postgres":
        raise RuntimeError("unsupported_workflow_document_store")
    if os.environ.get("METIS_WORKFLOW_STORE", "").strip().lower() != "postgres":
        raise RuntimeError("workflow_identity_store_required_for_document_store")
    store = PostgresConcurrentWorkflowDocumentStore()
    store.verify_cutover_schema()
    return store


def _workflow_review_store() -> PostgresWorkflowReviewStore | None:
    kind = os.environ.get("METIS_WORKFLOW_REVIEW_STORE", "").strip().lower()
    if not kind:
        return None
    if kind != "postgres":
        raise RuntimeError("unsupported_workflow_review_store")
    if os.environ.get("METIS_WORKFLOW_STORE", "").strip().lower() != "postgres":
        raise RuntimeError("workflow_identity_store_required_for_review_store")
    if os.environ.get("METIS_WORKFLOW_DOCUMENT_STORE", "").strip().lower() != "postgres":
        raise RuntimeError("workflow_document_store_required_for_review_store")
    store = PostgresWorkflowReviewStore()
    store.verify_review_schema()
    return store


def _workflow_remaining_store() -> PostgresWorkflowRemainingStore | None:
    kind = os.environ.get("METIS_WORKFLOW_REMAINING_STORE", "").strip().lower()
    if not kind:
        return None
    if kind != "postgres":
        raise RuntimeError("unsupported_workflow_remaining_store")
    required = {
        "METIS_WORKFLOW_STORE": "workflow_identity_store_required_for_remaining_store",
        "METIS_WORKFLOW_DOCUMENT_STORE": "workflow_document_store_required_for_remaining_store",
        "METIS_WORKFLOW_REVIEW_STORE": "workflow_review_store_required_for_remaining_store",
    }
    for name, error in required.items():
        if os.environ.get(name, "").strip().lower() != "postgres":
            raise RuntimeError(error)
    store = PostgresWorkflowRemainingStore()
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
    immutable_store = _immutable_source_store()
    canonical_store = _canonical_store()
    workflow_identity_store = _workflow_identity_store()
    workflow_document_store = _workflow_document_store()
    workflow_review_store = _workflow_review_store()
    workflow_remaining_store = _workflow_remaining_store()
    running_in_azure = _running_in_azure()

    common = dict(
        root=ROOT,
        source_store=_env_path("CONSOLE_SOURCE_STORE", data_root / "sources" / "private"),
        runtime=_env_path("CONSOLE_RUNTIME", data_root / "output" / "runtime" / "operations-console"),
        immutable_source_store=immutable_store,
        canonical_publication_store=canonical_store,
    )
    if workflow_remaining_store is not None:
        if workflow_identity_store is None or workflow_document_store is None or workflow_review_store is None:
            raise RuntimeError("workflow_prerequisites_required_for_remaining_store")
        console_cls = (
            PostgresCompleteWorkflowAzureAuthoritativePublicationConsole
            if running_in_azure
            else PostgresCompleteWorkflowDurablePublicationConsole
        )
        console = console_cls(
            **common,
            workflow_identity_store=workflow_identity_store,
            workflow_document_store=workflow_document_store,
            workflow_review_store=workflow_review_store,
            workflow_remaining_store=workflow_remaining_store,
        )
        bind_remaining_route_backends(workflow_remaining_store)
    elif workflow_review_store is not None:
        if workflow_identity_store is None or workflow_document_store is None:
            raise RuntimeError("workflow_prerequisites_required_for_review_store")
        console_cls = (
            PostgresReviewWorkflowAzureAuthoritativePublicationConsole
            if running_in_azure
            else PostgresReviewWorkflowDurablePublicationConsole
        )
        console = console_cls(
            **common,
            workflow_identity_store=workflow_identity_store,
            workflow_document_store=workflow_document_store,
            workflow_review_store=workflow_review_store,
        )
    elif workflow_document_store is not None:
        if workflow_identity_store is None:
            raise RuntimeError("workflow_identity_store_required_for_document_store")
        console_cls = (
            PostgresWorkflowAzureAuthoritativePublicationConsole
            if running_in_azure
            else PostgresWorkflowDurablePublicationConsole
        )
        console = console_cls(
            **common,
            workflow_identity_store=workflow_identity_store,
            workflow_document_store=workflow_document_store,
        )
    elif workflow_identity_store is not None:
        console_cls = (
            PostgresIdentityAzureAuthoritativePublicationConsole
            if running_in_azure
            else PostgresIdentityDurablePublicationConsole
        )
        console = console_cls(**common, workflow_identity_store=workflow_identity_store)
    else:
        console_cls = AzureAuthoritativePublicationConsole if running_in_azure else DurablePublicationConsole
        console = console_cls(**common)

    bootstrap_accounts(console)
    console.migrate_legacy_revise_to_review()
    console.reconcile_durable_publications()

    app = create_console_app(console)
    install_proportionate_review_routes(app, console)
    install_audit_llm_settings_routes(app, console)
    install_deterministic_review_repair_routes(app, console)
    install_closed_review_routes(app, console)
    harden_legacy_repair_routes(app, console)
    install_audit_routes(app, console)
    install_navigation_simplification(app)
    return app


def __getattr__(name: str) -> object:
    if name == "app":
        return build_app()
    raise AttributeError(name)
