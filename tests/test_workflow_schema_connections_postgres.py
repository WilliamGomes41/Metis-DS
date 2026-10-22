"""Native startup checks retain fail-closed schema validation with bounded I/O.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest
from psycopg import sql

from src.workflows.workflow_documents_postgres_v1 import (
    PostgresWorkflowDocumentStore,
    WorkflowDocumentStoreError,
)
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore, WorkflowReviewStoreError
from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore, WorkflowRemainingStoreError


@pytest.mark.parametrize("store_class,verify_name", [
    (PostgresWorkflowDocumentStore, "verify_schema"),
    (PostgresWorkflowDocumentRuntimeStore, "verify_cutover_schema"),
    (PostgresWorkflowReviewStore, "verify_review_schema"),
    (PostgresWorkflowRemainingStore, "verify_remaining_schema"),
])
def test_schema_check_uses_one_connection_and_rechecks_after_schema_damage(complete_postgres, monkeypatch, store_class, verify_name):
    store = store_class(complete_postgres)
    verify = getattr(store, verify_name)
    connect = store._connect
    connections = []

    def observed():
        connection = connect()
        connections.append(connection)
        return connection

    monkeypatch.setattr(store, "_connect", observed)
    verify()
    assert len(connections) == 1
    assert all(connection.closed for connection in connections)
    with connect() as connection:
        connection.execute("ALTER TABLE workflow.topics DROP COLUMN display_name CASCADE")
    with pytest.raises(WorkflowDocumentStoreError, match="workflow_document_schema_missing:topics.display_name"):
        verify()
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)


@pytest.mark.parametrize("table,column", [
    ("documents", None), ("topics", None),
    ("documents", "topic_id"), ("topics", "topic_id"),
    ("topics", "identity_key"), ("topics", "display_name"),
])
def test_incomplete_schema_is_refused(complete_postgres, table, column):
    store = PostgresWorkflowDocumentStore(complete_postgres)
    with store._connect() as connection:
        if column:
            connection.execute(sql.SQL("ALTER TABLE workflow.{} DROP COLUMN {} CASCADE").format(
                sql.Identifier(table), sql.Identifier(column)))
        else:
            connection.execute(sql.SQL("DROP TABLE workflow.{} CASCADE").format(sql.Identifier(table)))
    expected = table + ("." + column if column else "")
    with pytest.raises(WorkflowDocumentStoreError, match="workflow_document_schema_missing:.*" + expected):
        store.verify_schema()


@pytest.mark.parametrize("store_class,verify_name,table,column,error,code", [
    (PostgresWorkflowDocumentRuntimeStore, "verify_cutover_schema", "documents", "envelope_payload", WorkflowDocumentStoreError, "workflow_document_cutover_schema_missing"),
    (PostgresWorkflowDocumentRuntimeStore, "verify_cutover_schema", "document_objects", "position", WorkflowDocumentStoreError, "workflow_document_cutover_schema_missing"),
    (PostgresWorkflowReviewStore, "verify_review_schema", "review_events", "actor_text", WorkflowReviewStoreError, "workflow_review_schema_missing"),
    (PostgresWorkflowReviewStore, "verify_review_schema", "review_events", "event_payload", WorkflowReviewStoreError, "workflow_review_schema_missing"),
    (PostgresWorkflowReviewStore, "verify_review_schema", "publish_authorizations", "position", WorkflowReviewStoreError, "workflow_review_schema_missing"),
    (PostgresWorkflowReviewStore, "verify_review_schema", "publish_authorizations", "authorization_payload", WorkflowReviewStoreError, "workflow_review_schema_missing"),
    (PostgresWorkflowRemainingStore, "verify_remaining_schema", "audit_records", "retention_state", WorkflowRemainingStoreError, "workflow_remaining_schema_missing"),
])
def test_specialized_schema_guards_remain_enforced(complete_postgres, store_class, verify_name, table, column, error, code):
    store = store_class(complete_postgres)
    with store._connect() as connection:
        connection.execute(sql.SQL("ALTER TABLE workflow.{} DROP COLUMN {} CASCADE").format(
            sql.Identifier(table), sql.Identifier(column)))
    with pytest.raises(error, match=code):
        getattr(store, verify_name)()


@pytest.mark.parametrize("azure", [False, True])
@pytest.mark.parametrize("table,column", [("topics", "display_name"), ("review_events", "event_payload")])
def test_real_asgi_startup_refuses_schema_damage(complete_postgres, production_console, azure, table, column):
    from tests.test_durable_publication_console_v1 import MemorySourceStore

    store = PostgresWorkflowDocumentStore(complete_postgres)
    with store._connect() as connection:
        connection.execute(sql.SQL("ALTER TABLE workflow.{} DROP COLUMN {} CASCADE").format(
            sql.Identifier(table), sql.Identifier(column)))
    expected = WorkflowDocumentStoreError if table == "topics" else WorkflowReviewStoreError
    with pytest.raises(expected, match="schema_missing"):
        production_console(azure=azure, immutable_source_store=MemorySourceStore() if azure else None)


@pytest.mark.parametrize("store_class,verify_name,query_part,error,code", [
    (PostgresWorkflowDocumentStore, "verify_schema", "information_schema.columns", WorkflowDocumentStoreError, "workflow_document_schema_check_failed"),
    (PostgresWorkflowDocumentRuntimeStore, "verify_cutover_schema", "envelope_payload", WorkflowDocumentStoreError, "workflow_document_cutover_schema_check_failed"),
    (PostgresWorkflowDocumentRuntimeStore, "verify_cutover_schema", "COUNT(*)", WorkflowDocumentStoreError, "workflow_topic_identity_check_failed"),
    (PostgresWorkflowReviewStore, "verify_review_schema", "review_events", WorkflowReviewStoreError, "workflow_review_schema_check_failed"),
    (PostgresWorkflowRemainingStore, "verify_remaining_schema", "information_schema.tables", WorkflowRemainingStoreError, "workflow_remaining_schema_check_failed"),
])
def test_native_query_failure_retains_error_and_closes_connection(complete_postgres, monkeypatch, store_class, verify_name, query_part, error, code):
    from contextlib import contextmanager
    import psycopg

    store = store_class(complete_postgres)
    connect = store._connect
    opened = []

    @contextmanager
    def failing_connection():
        with connect() as connection:
            opened.append(connection)

            class QueryFailure:
                def execute(self, query, *args, **kwargs):
                    # Real PostgreSQL aborts this read transaction. Other schema
                    # queries still use the real adapter and database.
                    return connection.execute("SELECT 1/0" if query_part in query else query, *args, **kwargs)

            yield QueryFailure()

    with monkeypatch.context() as patch:
        patch.setattr(store, "_connect", failing_connection)
        with pytest.raises(error, match=code) as failure:
            getattr(store, verify_name)()
    assert isinstance(failure.value.__cause__, psycopg.errors.DivisionByZero)
    assert opened and all(connection.closed for connection in opened)
    getattr(store, verify_name)()  # No poisoned connection or durable mutation.
