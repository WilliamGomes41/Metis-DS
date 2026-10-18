"""#741/#742: one native participation owner; preserve the domain transition.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import psycopg
import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.operations_console_v1 import ConsoleError
from src.review_policy_v1 import participants
from src.workflows.workflow_badge_counts_postgres_v1 import (
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
)
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores, workflow_transaction
from tests.complete_workflow_support import complete_postgres
from tests.test_678_store_command_postgres import (
    _assert_document_mirrors_equal_pg, _count_reloads,
    _spy_mirror_writes_inside_transaction,
)
from tests.test_decision_graph_chain import _accounts, ingest
from tests.test_durable_publication_console_v1 import MemorySourceStore
from tests.test_r2_rollback_remirror_postgres import _assert_disk_mirrors_equal_pg
from tests.test_review_participation_management import change


@pytest.fixture(params=[
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
], ids=["local-r-plus", "azure-r-plus"])
def prepared(request, tmp_path, complete_postgres):
    stores = (CutoverPostgresWorkflowIdentityStore(complete_postgres),
              PostgresConcurrentWorkflowDocumentStore(complete_postgres),
              PostgresWorkflowReviewStore(complete_postgres),
              PostgresWorkflowRemainingStore(complete_postgres))
    bind_workflow_stores(*stores)
    console = request.param(
        root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime",
        workflow_identity_store=stores[0], workflow_document_store=stores[1],
        workflow_review_store=stores[2], workflow_remaining_store=stores[3],
        canonical_publication_store=PostgresCanonicalPublicationStore(complete_postgres),
        immutable_source_store=MemorySourceStore(),
    )
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    return console, accounts, sid


def _state(console, sid):
    return deepcopy((console.workflow_document_store.get_envelope(sid),
        console.workflow_document_store.list_document_objects(sid),
        console.workflow_review_store.read_bindings(),
        console.workflow_review_store.read_events()))


def _mirrors(console, sid):
    _assert_disk_mirrors_equal_pg(console)
    _assert_document_mirrors_equal_pg(console, sid)


def test_participation_has_one_reload_and_no_mirrors_before_commit(prepared, monkeypatch):
    console, accounts, sid = prepared
    revision = console.objects_revision(sid)
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    reloads = _count_reloads(monkeypatch, console)
    statements = []
    execute = psycopg.Connection.execute

    def counted(self, query, *args, **kwargs):
        statements.append(str(query))
        return execute(self, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.Connection, "execute", counted)
    change(console, accounts, sid, "add_optional", accounts["reviewer"]["account_id"],
           expected_revision=revision)
    list_reads = [query for query in statements if "FROM workflow.documents d " in query
                  and "ORDER BY d.acquired_at,d.snapshot_id" in query]
    print("PARTICIPATION_SQL", len(statements), "RELOADS", len(reloads), "LIST_READS", len(list_reads))
    assert inside == [], f"mirror writes inside participation transaction: {inside}"
    assert len(reloads) == len(list_reads) == 1
    _mirrors(console, sid)


@pytest.mark.parametrize("fault", ["body", "commit", "recovery"])
def test_fault_keeps_original_error_and_rolled_back_state(prepared, monkeypatch, fault):
    console, accounts, sid = prepared
    before = _state(console, sid)
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    original = console._commit_prepared_store
    if fault == "commit":
        with psycopg.connect(console.workflow_document_store.config.dsn) as con:
            con.execute("CREATE TABLE participation_parent (id integer PRIMARY KEY)")
            con.execute("CREATE TABLE participation_commit_fault (id integer REFERENCES participation_parent(id) DEFERRABLE INITIALLY DEFERRED)")

    def fail(**kwargs):
        original(**kwargs)
        assert _state(console, sid) != before
        if fault == "commit":
            with console.workflow_document_store._connect() as con:
                con.execute("INSERT INTO participation_commit_fault VALUES (1)")
        else:
            raise ConsoleError("participation_fault")

    monkeypatch.setattr(console, "_commit_prepared_store", fail)
    if fault == "recovery":
        def broken_recovery():
            raise OSError("participation_recovery_fault")
        monkeypatch.setattr(console, "_remirror_review_runtime", broken_recovery)
    error = psycopg.errors.ForeignKeyViolation if fault == "commit" else ConsoleError
    with pytest.raises(error, match=None if fault == "commit" else "^participation_fault$"):
        change(console, accounts, sid, "add_optional", accounts["reviewer"]["account_id"])
    assert inside == []
    assert _state(console, sid) == before
    _mirrors(console, sid)


@pytest.mark.parametrize("boundary", ["raw", "owned"])
def test_participation_remains_an_independent_command(prepared, boundary):
    console, accounts, sid = prepared
    before = _state(console, sid)
    context = (workflow_transaction(console.workflow_review_store) if boundary == "raw"
               else console._store_command(sid))
    with context:
        with pytest.raises(ConsoleError, match="^participation_independent_transaction_required$"):
            change(console, accounts, sid, "add_optional", accounts["reviewer"]["account_id"])
    assert _state(console, sid) == before
    _mirrors(console, sid)


def test_committed_participation_survives_failed_mirror_rebuild(prepared, monkeypatch, caplog):
    console, accounts, sid = prepared
    from src.workflows import workflow_review_cutover_v1 as review
    original = review._atomic_write

    def broken(path, *args, **kwargs):
        if path == console._bindings_path:
            raise RuntimeError("participation_mirror_fault")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(review, "_atomic_write", broken)
        result = change(console, accounts, sid, "add_optional", accounts["reviewer"]["account_id"])
    assert result["idempotent"] is False
    envelope = console.workflow_document_store.get_envelope(sid)
    assert accounts["reviewer"]["account_id"] in participants(envelope["review_policy"])
    assert any(record.message.startswith("store_command_remirror_failed") for record in caplog.records)
    # A later independent command keeps working after mirror failure.
    replay = change(console, accounts, sid, "add_optional", accounts["reviewer"]["account_id"],
                    command_id=result["command_id"])
    assert replay["idempotent"]
