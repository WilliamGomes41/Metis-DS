"""#741: one native decision-review command owner; preserve the domain transition.

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
from src.workflows.workflow_badge_counts_postgres_v1 import (
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
)
from src.workflows.workflow_transaction_v1 import workflow_transaction
from tests.complete_workflow_support import complete_console, complete_postgres  # noqa: F401
from tests.test_678_store_command_postgres import (
    _assert_document_mirrors_equal_pg, _count_reloads,
    _spy_mirror_writes_inside_transaction,
)
from tests.test_decision_graph_chain import _accounts, command, complete_graph, ingest
from tests.test_durable_publication_console_v1 import MemorySourceStore
from tests.test_r2_rollback_remirror_postgres import _assert_disk_mirrors_equal_pg


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
    _assert_disk_mirrors_equal_pg(console)
    _assert_document_mirrors_equal_pg(console, sid)


def _update(console, accounts, sid, command_id="graph-1"):
    return console.update_decision_graph(
        **command(console, accounts, sid, command_id, graph=complete_graph(console, sid)))


def _ready_to_confirm(console, accounts, sid):
    _update(console, accounts, sid, "initial-graph")
    for obj in console.snapshot_objects(sid):
        if obj["object_type"] != "document":
            console.review_object(actor_id=accounts["researcher"]["account_id"], snapshot_id=sid,
                                  object_id=obj["object_id"], decision="approve", confirmed_object_type="node")
    _update(console, accounts, sid, "graph-1")


@pytest.mark.parametrize("action", ["graph", "confirm"])
def test_decision_command_has_one_reload_and_no_mirrors_before_commit(prepared, monkeypatch, action):
    console, accounts, sid = prepared
    if action == "confirm":
        _ready_to_confirm(console, accounts, sid)
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    reloads = _count_reloads(monkeypatch, console)
    if action == "graph":
        result = _update(console, accounts, sid)
    else:
        result = console.confirm_decision_graph(**command(console, accounts, sid, "confirm-1"))
    assert result.get("idempotent") is not True
    assert inside == [], f"mirror writes inside decision command transaction: {inside}"
    assert len(reloads) == 1
    _mirrors(console, sid)


@pytest.mark.parametrize("fault", ["body", "commit", "recovery"])
def test_fault_keeps_original_error_and_rolled_back_state(prepared, monkeypatch, fault):
    console, accounts, sid = prepared
    before = _state(console, sid)
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    original = console._commit_prepared_store
    if fault == "commit":
        with psycopg.connect(console.workflow_document_store.config.dsn) as con:
            con.execute("CREATE TABLE decision_parent (id integer PRIMARY KEY)")
            con.execute("CREATE TABLE decision_commit_fault (id integer REFERENCES decision_parent(id) DEFERRABLE INITIALLY DEFERRED)")

    def fail(**kwargs):
        original(**kwargs)
        assert _state(console, sid) != before
        if fault == "commit":
            with console.workflow_document_store._connect() as con:
                con.execute("INSERT INTO decision_commit_fault VALUES (1)")
        else:
            raise ConsoleError("decision_command_fault")

    monkeypatch.setattr(console, "_commit_prepared_store", fail)
    if fault == "recovery":
        def broken_recovery():
            raise OSError("decision_recovery_fault")
        monkeypatch.setattr(console, "_remirror_review_runtime", broken_recovery)
    error = psycopg.errors.ForeignKeyViolation if fault == "commit" else ConsoleError
    with pytest.raises(error, match=None if fault == "commit" else "^decision_command_fault$"):
        _update(console, accounts, sid)
    assert inside == []
    assert _state(console, sid) == before
    _mirrors(console, sid)


@pytest.mark.parametrize("boundary", ["raw", "owned"])
def test_decision_command_remains_an_independent_command(prepared, boundary):
    console, accounts, sid = prepared
    before = _state(console, sid)
    context = (workflow_transaction(console.workflow_review_store) if boundary == "raw"
               else console._store_command(sid))
    with context:
        with pytest.raises(ConsoleError, match="^decision_review_independent_transaction_required$"):
            _update(console, accounts, sid)
    assert _state(console, sid) == before
    _mirrors(console, sid)


def test_committed_decision_command_survives_failed_mirror_rebuild(prepared, monkeypatch, caplog):
    console, accounts, sid = prepared
    from src.workflows import workflow_review_cutover_v1 as review
    original = review._atomic_write

    def broken(path, *args, **kwargs):
        if path == console._envelopes_path:
            raise RuntimeError("decision_mirror_fault")
        return original(path, *args, **kwargs)

    graph_command = command(console, accounts, sid, "graph-1", graph=complete_graph(console, sid))
    with monkeypatch.context() as patch:
        patch.setattr(review, "_atomic_write", broken)
        from src.workflows import workflow_documents_cutover_v1 as documents
        patch.setattr(documents, "_atomic_write", broken)
        result = console.update_decision_graph(**graph_command)
    assert result.get("idempotent") is not True
    events = console.workflow_review_store.read_events()
    assert any(event["event_type"] == "decision_review_command"
               and event["details"].get("command_id") == "graph-1" for event in events)
    assert any(record.message.startswith("store_command_remirror_failed") for record in caplog.records)
    assert console.update_decision_graph(**graph_command)["idempotent"]
