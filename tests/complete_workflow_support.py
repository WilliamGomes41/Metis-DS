"""Native R+ test constructor; all workflow stores share one transaction binding."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowDurablePublicationConsole
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores


def complete_console(root, config, **overrides):
    identity = CutoverPostgresWorkflowIdentityStore(config)
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    remaining = PostgresWorkflowRemainingStore(config)
    bind_workflow_stores(identity, documents, reviews, remaining)
    options = dict(
        root=root, source_store=root / "sources", runtime=root / "runtime",
        workflow_identity_store=identity, workflow_document_store=documents,
        workflow_review_store=reviews, workflow_remaining_store=remaining,
        canonical_publication_store=PostgresCanonicalPublicationStore(config),
    )
    options.update(overrides)
    return FastBadgePostgresCompleteWorkflowDurablePublicationConsole(**options)


@pytest.fixture
def complete_postgres(monkeypatch):
    """Full schema in an owned disposable database; never reset the supplied DB.

    METIS_TEST_POSTGRES_DSN must identify a test server with CREATEDB rights.
    Failure to create the isolated database is a test failure, not a skip.
    """
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for complete PostgreSQL evidence")
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    database = "metis_718_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database)))
    isolated_dsn = make_conninfo(dsn, dbname=database)
    try:
        root = Path(__file__).resolve().parents[1]
        with psycopg.connect(isolated_dsn, autocommit=True) as con:
            for path in [root / "db/schema_v2.sql", *sorted((root / "db/migrations").glob("*.sql"))]:
                con.execute(path.read_text(encoding="utf-8"))
        # Child-process proofs must connect to this same isolated authority.
        monkeypatch.setenv("METIS_TEST_POSTGRES_DSN", isolated_dsn)
        yield PostgresCanonicalConfig(dsn=isolated_dsn)
    finally:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
