"""#678 Storeopdracht: one owner per durable command in the R+ review topology.

U1: only the owner reloads (one reload per approve, constant in a batch).
U2: a nested level joins with a savepoint; a caught nested fault leaves no
    phantom ledger line and no mirror written inside the open transaction.
U3 (B1): disk mirrors are written only after the commit or rollback.
U4: the original error survives a failing recovery; a failing mirror rebuild
    after a commit does not fail the committed command.
Foreign consoles MAG NIET join an open command.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import logging
import pathlib
import threading
from copy import deepcopy

import pytest

from src.operations_console_v1 import ConsoleError
from src.proportionate_review_v1 import _batch_type
from src.review_ledger import append_event
from src.workflows import workflow_documents_cutover_v1 as documents_cutover
from src.workflows import workflow_review_cutover_v1 as rc
from src.workflows.workflow_transaction_v1 import workflow_transaction_active
from tests.complete_workflow_support import complete_postgres as workflow_postgres  # noqa: F401
from tests.test_r2_rollback_remirror_postgres import (
    _approve, _assert_review_authority_without_mirrors, _console, _inject_fault, _setup, _state,
)


def _count_reloads(monkeypatch, console):
    calls = []
    original = console.workflow_document_store.list_envelopes

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(console.workflow_document_store, "list_envelopes", counting)
    return calls


def _spy_mirror_writes_inside_transaction(monkeypatch, console):
    """Record every disk-mirror write that happens while a transaction is open."""
    inside = []
    mirror_paths = {console._ledger_path.resolve(), console._bindings_path.resolve(),
                    console._envelopes_path.resolve()}

    def is_mirror(path):
        path = pathlib.Path(path).resolve()
        return path in mirror_paths or path.parent == console._objects_dir.resolve()

    import os
    original_os_open = os.open

    def os_open_spy(path, flags, *args, **kwargs):
        if not isinstance(path, int) and workflow_transaction_active() and is_mirror(path):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                inside.append(("os.open", pathlib.Path(path).name))
        return original_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", os_open_spy)
    original_open = pathlib.Path.open

    def open_spy(self, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "awx+") and workflow_transaction_active() and is_mirror(self):
            inside.append(("append", self.name))
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", open_spy)
    return inside


def _assert_document_authority_without_mirrors(console, sid):
    assert not console._objects_path(sid).exists()
    assert not console._envelopes_path.exists()
    assert console._load_objects(sid) == console.workflow_document_store.list_document_objects(sid)
    assert console._envelope(sid) == console.workflow_document_store.get_envelope(sid)


def test_u1_one_reload_per_approve(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    reloads = _count_reloads(monkeypatch, console)
    _approve(console, rid, sid, obj_a)
    print("U1_APPROVE_RELOADS", len(reloads))
    assert len(reloads) == 1, f"only the command owner MAG reload: {len(reloads)} reloads"


def test_u1_batch_reloads_constant_in_k(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, queue = _setup(tmp_path, workflow_postgres)
    reloads = _count_reloads(monkeypatch, console)
    console.batch_review_normal_risk(
        actor_id=rid, snapshot_id=sid, object_ids=[obj["object_id"] for obj in queue],
        expected_revision=console.objects_revision(sid),
    )
    print("U1_BATCH_RELOADS", len(reloads), "k", len(queue))
    assert len(reloads) == 1, f"a batch of {len(queue)} MOET reload once: {len(reloads)} reloads"
    _assert_review_authority_without_mirrors(console)
    _assert_document_authority_without_mirrors(console, sid)


def test_u3_no_mirror_write_inside_open_transaction_on_approve(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    _approve(console, rid, sid, obj_a)
    print("U3_APPROVE_INSIDE", inside)
    assert inside == [], f"mirror written inside the open transaction: {inside}"
    _assert_review_authority_without_mirrors(console)
    _assert_document_authority_without_mirrors(console, sid)


def test_u2_caught_nested_fault_writes_no_mirror_inside_transaction(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, obj_b) = _setup(tmp_path, workflow_postgres)
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    with console._atomic_snapshot_mutation(sid):
        try:
            with console._atomic_snapshot_mutation(sid):
                _approve(console, rid, sid, obj_a)
                raise RuntimeError("u2_caught_inner")
        except RuntimeError as exc:
            assert str(exc) == "u2_caught_inner"
        _approve(console, rid, sid, obj_b)
    print("U2_CAUGHT_INSIDE", inside)
    assert inside == [], f"mirror written inside the open transaction: {inside}"
    approved = {b["object_id"] for rows in console.workflow_review_store.read_bindings().values() for b in rows}
    assert obj_b["object_id"] in approved and obj_a["object_id"] not in approved
    _assert_review_authority_without_mirrors(console)
    _assert_document_authority_without_mirrors(console, sid)


def test_u2_unbuffered_event_in_failed_participant_leaves_no_phantom_ledger_line(workflow_postgres, tmp_path):
    console, rid, sid, _queue = _setup(tmp_path, workflow_postgres)
    with console._reprocessing_transaction(sid):
        try:
            with console._reprocessing_transaction(sid):
                append_event(console._ledger_path, event_type="u2_phantom_probe", object_id="probe",
                             object_version="1.0.0", actor="bert", details={"snapshot_id": sid})
                raise RuntimeError("u2_participant_fault")
        except RuntimeError:
            pass
    events = console.workflow_review_store.read_events()
    assert not [e for e in events if e.get("event_type") == "u2_phantom_probe"]
    _assert_review_authority_without_mirrors(console)


def test_u3_reprocessing_rollback_leaves_no_uncommitted_envelope_mirror(workflow_postgres, tmp_path):
    """S14 (#708): a commit inside a reprocessing command that later fails MAG NIET
    leave the uncommitted envelope in the disk mirror."""
    console, _rid, sid, _queue = _setup(tmp_path, workflow_postgres)
    before = deepcopy(console.workflow_document_store.get_envelope(sid))
    with pytest.raises(RuntimeError, match="^u3_outer_fault$"):
        with console._reprocessing_transaction(sid):
            changed = deepcopy(console._envelope(sid))
            changed["title"] = "Begrippen (uncommitted)"
            console._commit_prepared_store(envelopes={sid: changed}, snapshot_id=sid)
            raise RuntimeError("u3_outer_fault")
    assert console.workflow_document_store.get_envelope(sid) == before
    assert console._envelope(sid) == before
    assert not console._envelopes_path.exists()
    _assert_review_authority_without_mirrors(console)


def test_u4_correct_object_original_error_survives_failing_recovery(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (_obj_a, obj_b) = _setup(tmp_path, workflow_postgres)
    text = obj_b["content"]["clean_text"]
    # A proposal other than the patch value: the legacy auto-apply guard MAG NIET short-circuit.
    console.review_object(actor_id=rid, snapshot_id=sid, object_id=obj_b["object_id"], decision="revise",
                          comment="Corrigeer.", proposed_correction="Een andere formulering.")
    before = _state(console, sid)
    flag = threading.Event()
    _inject_fault(monkeypatch, flag)

    def failing_remirror():
        raise RuntimeError("remirror_down")

    monkeypatch.setattr(console, "_refresh_review_runtime", failing_remirror)
    with pytest.raises(RuntimeError, match="^r2_injected_fault$"):
        console.correct_object(actor_id=rid, snapshot_id=sid, object_id=obj_b["object_id"],
                               patch={"reason": "u4", "operations": [
                                   {"op": "set", "path": "content.clean_text", "value": text}]})
    assert flag.is_set()
    assert _state(_console(tmp_path, workflow_postgres), sid) == before


def test_u4_inaccessible_mirror_does_not_affect_committed_command(workflow_postgres, tmp_path, monkeypatch, caplog):
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    from src import operations_console_v1 as operations
    original = operations._atomic_write
    bindings_path = console._bindings_path.resolve()

    def failing_write(path, *args, **kwargs):
        if pathlib.Path(path).resolve() == bindings_path:
            raise RuntimeError("mirror_disk_down")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(operations, "_atomic_write", failing_write)
    caplog.set_level(logging.WARNING, logger="src.workflows.workflow_review_cutover_v1")
    rows = _approve(console, rid, sid, obj_a)
    assert any(row["object_id"] == obj_a["object_id"] for row in rows)
    approved = {b["object_id"] for b in console.workflow_review_store.read_bindings().get(sid, [])}
    assert obj_a["object_id"] in approved
    messages = [r.getMessage() for r in caplog.records]
    print("U4_AFTER_COMMIT", messages)
    assert not any("remirror" in m for m in messages)
    assert not any("mirror_disk_down" in m for m in messages), "warning MAG NIET carry exception text"


def _foreign_console(root, config, runtime):
    from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
    from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
    from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
    from src.workflows.workflow_transaction_v1 import bind_workflow_stores
    identity = PostgresWorkflowIdentityStore(config)
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    bind_workflow_stores(identity, documents, reviews)
    return rc.PostgresReviewWorkflowDurablePublicationConsole(
        root=root, source_store=root / "sources", runtime=runtime,
        workflow_identity_store=identity, workflow_document_store=documents,
        workflow_review_store=reviews,
    )


def test_foreign_console_cannot_join_open_command(workflow_postgres, tmp_path):
    """Another console MAG NIET borrow this command's connection. It gets its own
    runtime here: on a shared runtime the pre-#678 code self-deadlocks on store.lock."""
    console, _rid, sid, _queue = _setup(tmp_path, workflow_postgres)
    other = _foreign_console(tmp_path, workflow_postgres, tmp_path / "runtime-other")
    before = _state(console, sid)
    entered = []
    with pytest.raises(ConsoleError, match="store_command_foreign_owner"):
        with console._atomic_snapshot_mutation(sid):
            with other._atomic_snapshot_mutation(sid):
                entered.append(sid)
    assert entered == [], "the foreign console MAG NIET enter the open command"
    assert _state(console, sid) == before
    _assert_review_authority_without_mirrors(console)


def test_successful_nested_approve_commits_once_and_mirrors_after(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    events_before = console.workflow_review_store.read_events()
    with console._atomic_snapshot_mutation(sid):
        with console._atomic_snapshot_mutation(sid):
            _approve(console, rid, sid, obj_a)
    events = console.workflow_review_store.read_events()[len(events_before):]
    assert [e.get("event_type") for e in events].count("clinical_review_approve") == 1
    _assert_review_authority_without_mirrors(console)
    _assert_document_authority_without_mirrors(console, sid)
    assert _batch_type(obj_a)


def test_u2_failed_participant_refresh_poisons_the_command(workflow_postgres, tmp_path, monkeypatch):
    """Codex P1 on #739: when the refresh after a caught participant fault fails,
    the owner MAG NIET commit the stale in-process state; the command rolls back."""
    console, rid, sid, (obj_a, obj_b) = _setup(tmp_path, workflow_postgres)
    before = _state(console, sid)
    original = console.workflow_review_store.read_bindings
    armed = []

    def failing_after_fault(*args, **kwargs):
        if armed:
            raise RuntimeError("read_bindings_down")
        return original(*args, **kwargs)

    monkeypatch.setattr(console.workflow_review_store, "read_bindings", failing_after_fault)
    with pytest.raises(ConsoleError, match="store_command_participant_refresh_failed"):
        with console._atomic_snapshot_mutation(sid):
            try:
                with console._atomic_snapshot_mutation(sid):
                    _approve(console, rid, sid, obj_a)
                    armed.append(1)
                    raise RuntimeError("u2_caught_inner")
            except RuntimeError as exc:
                assert str(exc) == "u2_caught_inner"
            armed.clear()
    assert _state(_console(tmp_path, workflow_postgres), sid) == before
