"""Production composition shared by pytest fixtures and real subprocess proofs."""
from pathlib import Path
from threading import RLock

import pytest

from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing


# Configuration/composition touches process globals; console commands stay concurrent.
_configuration_lock = RLock()


def configure_production(patch, root, config):
    from src import console_asgi
    from src.workflow_store_configuration import POSTGRES_STORE_SETTINGS
    root = Path(root)
    for name in POSTGRES_STORE_SETTINGS:
        patch.setenv(name, "postgres")
    patch.setenv("METIS_CANONICAL_DB_DSN", config.dsn)
    patch.setenv("CONSOLE_DATA_ROOT", str(root))
    patch.setenv("CONSOLE_RUNTIME", str(root / "runtime"))
    patch.setenv("CONSOLE_SOURCE_STORE", str(root / "sources"))
    patch.setenv("WEB_CONCURRENCY", "1")
    for name in ("WEBSITE_SITE_NAME", "CONSOLE_BOOTSTRAP_USERNAME", "CONSOLE_BOOTSTRAP_PASSWORD",
                 "CONSOLE_BOOTSTRAP_REVIEWER_USERNAME", "CONSOLE_BOOTSTRAP_REVIEWER_PASSWORD",
                 "CONSOLE_IMMUTABLE_SOURCE_STORE", "METIS_CONSOLE_AUTH"):
        patch.delenv(name, raising=False)
    patch.setattr(console_asgi, "ROOT", root)
    patch.setattr(console_asgi, "_postgres_credential", lambda: None)


def production_application(root, config, *, azure=False,
                           processing_binder=bind_pre_review_semantic_processing,
                           immutable_source_store=None, source_store=None, runtime=None,
                           canonical_publication_store=None, environment=None):
    """Call build_app itself; replace only model/Blob transport and configuration."""
    from src import console_asgi
    root = Path(root)
    with _configuration_lock, pytest.MonkeyPatch.context() as patch:
        configure_production(patch, root, config)
        for name, value in (environment or {}).items():
            patch.setenv(name, str(value))
        if runtime is not None:
            patch.setenv("CONSOLE_RUNTIME", str(runtime))
        if source_store is not None:
            patch.setenv("CONSOLE_SOURCE_STORE", str(source_store))
        if canonical_publication_store is not None:
            from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
            if (type(canonical_publication_store) is not PostgresCanonicalPublicationStore
                    or canonical_publication_store.config != config):
                raise ValueError("Canonical store must be the production PostgreSQL store for this test database")
            patch.setattr(console_asgi, "_canonical_store", lambda **kwargs: canonical_publication_store)
        patch.setattr(console_asgi, "_immutable_source_store", lambda: immutable_source_store)
        patch.setattr(console_asgi, "bind_pre_review_semantic_processing", processing_binder)
        if azure:
            patch.setenv("WEBSITE_SITE_NAME", "d6a-test")
            patch.setenv("CONSOLE_PUBLIC_ORIGIN", (environment or {}).get("CONSOLE_PUBLIC_ORIGIN", "https://console.example.test"))
        app = console_asgi.build_app()
        app.state.operations_kernel._metis_test_application = app
        return app


def application_for(console):
    """Return the actual ASGI composition created by this shared factory."""
    return console._metis_test_application


def restart_production(console):
    """New production composition over the same committed test authorities."""
    from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole
    return production_application(
        console.root, console.workflow_document_store.config,
        azure=isinstance(console, FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole),
        processing_binder=lambda console: None, immutable_source_store=console.immutable_source_store,
        runtime=console.runtime, source_store=console.source_store,
    ).state.operations_kernel
