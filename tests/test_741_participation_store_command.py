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

from src.operations_console_v1 import ConsoleError
from src.review.review_policy_v1 import participants
from src.workflows.workflow_badge_counts_postgres_v1 import (
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
)
from src.workflows.workflow_transaction_v1 import workflow_transaction
from tests.complete_workflow_support import complete_console, complete_postgres  # noqa: F401
from tests.test_678_store_command_postgres import (
    _assert_document_authority_without_mirrors, _count_reloads,
    _spy_mirror_writes_inside_transaction,
)
from tests.test_decision_graph_chain import _accounts, ingest
from tests.test_durable_publication_console_v1 import MemorySourceStore
from tests.test_r2_rollback_remirror_postgres import _assert_review_authority_without_mirrors
from tests.test_review_participation_management import change


@pytest.fixture(params=[
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
], ids=["local-r-plus", "azure-r-plus"])
def prepared(request, tmp_path, complete_postgres):
    console = complete_console(tmp_path, complete_postgres, request.param,
                               immutable_source_store=MemorySourceStore())
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    return console, accounts, sid


def _state(console, sid):
    return deepcopy((console.workflow_document_store.get_envelope(sid),
        console.workflow_document_store.list_document_objects(sid),
        console.workflow_review_store.read_bindings(),
        console.workflow_review_store.read_events()))


def _mirrors(console, sid):
    _assert_review_authority_without_mirrors(console)
    _assert_document_authority_without_mirrors(console, sid)


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
        monkeypatch.setattr(console, "_refresh_review_runtime", broken_recovery)
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


def test_participation_ignores_inaccessible_mirrors(prepared, monkeypatch, caplog):
    console, accounts, sid = prepared
    from src import operations_console_v1 as operations
    original = operations._atomic_write

    def broken(path, *args, **kwargs):
        if path == (console.runtime / "publish_authorizations.json"):
            raise RuntimeError("participation_mirror_fault")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(operations, "_atomic_write", broken)
        result = change(console, accounts, sid, "add_optional", accounts["reviewer"]["account_id"])
    assert result["idempotent"] is False
    envelope = console.workflow_document_store.get_envelope(sid)
    assert accounts["reviewer"]["account_id"] in participants(envelope["review_policy"])
    assert not any("remirror" in record.message for record in caplog.records)
    # A later independent command keeps working without a mirror.
    replay = change(console, accounts, sid, "add_optional", accounts["reviewer"]["account_id"],
                    command_id=result["command_id"])
    assert replay["idempotent"]
