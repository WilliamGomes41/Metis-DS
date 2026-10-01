"""Isolated native PostgreSQL console used by decision lifecycle scenarios."""
import os
import pytest


def native_state(tmp_path):
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN required for native graph lifecycle proof")
    from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig, PostgresCanonicalPublicationStore
    from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
    from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
    from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
    from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
    from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowDurablePublicationConsole
    from tests.test_durable_publication_console_v1 import MemorySourceStore
    from tests.test_workflow_chain_recovery_v1 import _install_schema
    _install_schema(dsn)
    config = PostgresCanonicalConfig(dsn=dsn)
    store, source = PostgresCanonicalPublicationStore(config), MemorySourceStore()
    def state(node="default"):
        from src.workflows.workflow_transaction_v1 import bind_workflow_stores
        identity = CutoverPostgresWorkflowIdentityStore(config)
        documents = PostgresConcurrentWorkflowDocumentStore(config)
        reviews = PostgresWorkflowReviewStore(config)
        remaining = PostgresWorkflowRemainingStore(config)
        bind_workflow_stores(identity, documents, reviews, remaining)
        return FastBadgePostgresCompleteWorkflowDurablePublicationConsole(
            root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / f"runtime-{node}",
            immutable_source_store=source, canonical_publication_store=store,
            workflow_identity_store=identity, workflow_document_store=documents,
            workflow_review_store=reviews, workflow_remaining_store=remaining)
    return state, store, source
