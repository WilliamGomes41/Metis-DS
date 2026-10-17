"""Native R+ test constructor; all workflow stores share one transaction binding."""
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowDurablePublicationConsole
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores


def complete_console(root, config):
    identity = CutoverPostgresWorkflowIdentityStore(config)
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    remaining = PostgresWorkflowRemainingStore(config)
    bind_workflow_stores(identity, documents, reviews, remaining)
    return FastBadgePostgresCompleteWorkflowDurablePublicationConsole(
        root=root, source_store=root / "sources", runtime=root / "runtime",
        workflow_identity_store=identity, workflow_document_store=documents,
        workflow_review_store=reviews, workflow_remaining_store=remaining,
        canonical_publication_store=PostgresCanonicalPublicationStore(config),
    )
