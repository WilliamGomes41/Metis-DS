"""R2 guards: after a native rollback the review mixin only remirrors.

T3: without a concurrent writer a failed review mutation leaves PostgreSQL unchanged.
T4: after the rollback no write reaches workflow.* from the review mixin's error
    path (including remirror/refresh_*), and disk mirrors are written under the lock.
T5: two threads on one console object (sync route + threadpool): B's concurrent
    approve survives A's failed review.
T7: the review path NOOIT enters the inherited documents_cutover compensating
    context (blind write_bundle + ledger truncation, documents_cutover:774-790).
T6: a remirror failure logs codes, ids and error types only.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import threading
from contextlib import contextmanager

import pytest

from src.review.proportionate_review_v1 import _batch_type, normal_risk_batch_queue
from src.workflows import workflow_documents_cutover_v1 as documents_cutover
from src.workflows import workflow_review_cutover_v1 as rc
from tests.complete_workflow_support import complete_postgres as workflow_postgres  # noqa: F401

REVIEW_WRITES = ("append_event", "replace_snapshot_bindings", "replace_bindings")
DOCUMENT_WRITES = ("write_bundle", "create_document_bundle")
# No exemption: on the review path neither the inherited compensating block in
# documents_cutover (blind write_bundle, ledger truncation) nor anything else
# MAG write workflow.* after the native rollback (Route 1).


from tests.complete_workflow_support import complete_console as _console


def _setup(tmp_path, config):
    console = _console(tmp_path, config)
    from tests.semantic_fixture_support import bind_fixture_selections
    bind_fixture_selections(console)
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    receipt = console.ingest(
        actor_id=researcher["account_id"], filename="begrippen.html", content_type="text/html",
        data=b'<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>'
             b'<p>De Dutch Job Group is een meetinstrument voor werkbelasting.</p>'
             b'<p>Een observatie is een systematische waarneming van gedrag.</p></body></html>',
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-09-20", live_url="",
        class_="richtlijn", family="begrippen", named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    queue = normal_risk_batch_queue(console.snapshot_objects(sid), review_path="richtlijn",
                                    fragments=console.review_source_fragments(sid),
                                    bindings=console.object_review_bindings(sid))
    assert len(queue) == 2
    return console, reviewer["account_id"], sid, queue


def _approve(console, actor, sid, obj):
    return console.review_object(
        actor_id=actor, snapshot_id=sid, object_id=obj["object_id"], decision="approve",
        confirmed_object_type=_batch_type(obj), suitability="ja", eindoordeel="goedkeuren",
        type_action="dit_klopt",
    )


def _state(console, sid):
    return (
        console.workflow_review_store.read_bindings(),
        console.workflow_review_store.read_events(),
        console.workflow_document_store.list_document_objects(sid),
    )


def _ledger_state_bytes(console):
    from src.review.review_ledger import read_events
    return _serialise(read_events(console._ledger_path))


def _serialise(events):
    return "".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n" for e in events).encode("utf-8")


def _assert_review_authority_without_mirrors(console):
    """The ledger API and process view agree with PG without creating copies."""
    assert _ledger_state_bytes(console) == _serialise(console.workflow_review_store.read_events())
    assert console._bindings == console.workflow_review_store.read_bindings()
    assert not console._ledger_path.exists()
    assert not (console.runtime / "publish_authorizations.json").exists()


def _inject_fault(monkeypatch, flag):
    """Fail after the real commit in the documents layer (below the review mixin)."""
    original = documents_cutover._PostgresWorkflowDocumentsMixin._commit_prepared_store

    def faulty(self, **kwargs):
        original(self, **kwargs)
        if flag.is_set():  # fault fires exactly once (first mutation after arming)
            return
        flag.set()
        raise RuntimeError("r2_injected_fault")

    monkeypatch.setattr(documents_cutover._PostgresWorkflowDocumentsMixin, "_commit_prepared_store", faulty)


def _spy_writes(monkeypatch, console, flag, writes):
    for store, names in ((console.workflow_review_store, REVIEW_WRITES),
                         (console.workflow_document_store, DOCUMENT_WRITES)):
        for name in names:
            original = getattr(store, name)

            def spy(*args, __name=name, __original=original, **kwargs):
                if flag.is_set():
                    writes.append(__name)
                return __original(*args, **kwargs)

            monkeypatch.setattr(store, name, spy)


def _spy_mirror_depth(monkeypatch, console, flag, depths):
    original = console._refresh_review_runtime

    def spy():
        if flag.is_set():
            depths.append(console._store_lock_depth)
        return original()

    monkeypatch.setattr(console, "_refresh_review_runtime", spy)


def test_t3_failed_review_without_concurrency_leaves_state_unchanged(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    before = _state(console, sid)
    before_ledger = _ledger_state_bytes(console)
    assert before_ledger == _serialise(console.workflow_review_store.read_events())
    flag = threading.Event()
    _inject_fault(monkeypatch, flag)
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        _approve(console, rid, sid, obj_a)
    assert flag.is_set()
    assert _state(console, sid) == before
    # R1: ledger size and bytes unchanged; R3: bindings file equals PostgreSQL.
    assert len(_ledger_state_bytes(console)) == len(before_ledger)
    assert _ledger_state_bytes(console) == before_ledger
    _assert_review_authority_without_mirrors(console)
    assert _state(_console(tmp_path, workflow_postgres), sid) == before


def test_t4_review_path_no_workflow_write_after_rollback(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    flag, writes, depths = threading.Event(), [], []
    _inject_fault(monkeypatch, flag)
    _spy_writes(monkeypatch, console, flag, writes)
    _spy_mirror_depth(monkeypatch, console, flag, depths)
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        _approve(console, rid, sid, obj_a)
    print("R2_T4_REVIEW", {"writes_after_rollback": writes, "mirror_depths": depths})
    assert writes == [], f"workflow.* writes after rollback: {writes}"
    assert depths and all(d > 0 for d in depths), f"mirror written outside lock: {depths}"


def test_t4_commit_prepared_store_path_no_workflow_write_after_rollback(workflow_postgres, tmp_path, monkeypatch):
    """Seam: an envelope commit via _commit_prepared_store (as source_selection_v1:94)."""
    from copy import deepcopy
    console, _rid, sid, _queue = _setup(tmp_path, workflow_postgres)
    before = _state(console, sid)
    before_envelope = deepcopy(console._envelope(sid))
    changed = deepcopy(before_envelope)
    changed["title"] = "Begrippen (r2)"
    flag, writes, depths = threading.Event(), [], []
    _inject_fault(monkeypatch, flag)
    _spy_writes(monkeypatch, console, flag, writes)
    _spy_mirror_depth(monkeypatch, console, flag, depths)
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        console._commit_prepared_store(envelopes={sid: changed}, snapshot_id=sid)
    print("R2_T4_COMMIT", {"writes_after_rollback": writes, "mirror_depths": depths})
    assert writes == [], f"workflow.* writes after rollback: {writes}"
    assert depths and all(d > 0 for d in depths), f"mirror written outside lock: {depths}"
    fresh = _console(tmp_path, workflow_postgres)
    assert _state(fresh, sid) == before
    assert fresh._envelope(sid)["title"] == before_envelope["title"]


def _inject_forbidden_remirror_write(monkeypatch, console):
    """Negative control: a workflow.* write from the remirror MOET trip the spy."""
    original = console._refresh_review_runtime

    def remirror_with_forbidden_write():
        result = original()
        try:
            # Called without arguments: the spy records the attempt, the real
            # store then raises TypeError, so no row is written.
            console.workflow_review_store.append_event()
        except TypeError:
            pass
        return result

    monkeypatch.setattr(console, "_refresh_review_runtime", remirror_with_forbidden_write)


def test_t4_negative_review_path_spy_catches_forbidden_remirror_write(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    flag, writes = threading.Event(), []
    _inject_fault(monkeypatch, flag)
    _spy_writes(monkeypatch, console, flag, writes)
    _inject_forbidden_remirror_write(monkeypatch, console)
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        _approve(console, rid, sid, obj_a)
    assert "append_event" in writes, f"spy MOET catch a remirror write: {writes}"


def test_t4_negative_commit_path_spy_catches_forbidden_remirror_write(workflow_postgres, tmp_path, monkeypatch):
    from copy import deepcopy
    console, _rid, sid, _queue = _setup(tmp_path, workflow_postgres)
    changed = deepcopy(console._envelope(sid))
    changed["title"] = "Begrippen (r2)"
    flag, writes = threading.Event(), []
    _inject_fault(monkeypatch, flag)
    _spy_writes(monkeypatch, console, flag, writes)
    _inject_forbidden_remirror_write(monkeypatch, console)
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        console._commit_prepared_store(envelopes={sid: changed}, snapshot_id=sid)
    assert "append_event" in writes, f"spy MOET catch a remirror write: {writes}"


def test_t5_two_threads_same_console_concurrent_approve_survives(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, obj_b) = _setup(tmp_path, workflow_postgres)
    flag, b_done, errors = threading.Event(), threading.Event(), []
    _inject_fault(monkeypatch, flag)
    a_thread, order = {}, []
    before_events = console.workflow_review_store.read_events()
    before_ledger = _ledger_state_bytes(console)
    assert before_ledger == _serialise(before_events)

    def hook(name):
        original = getattr(console, name, None)
        if original is None:
            return

        def wrapped(*args, **kwargs):
            # Thread A's post-rollback step (restore on main, remirror after
            # the fix) when A no longer owns the store lock. _store_lock_depth
            # and the flock are shared by both threads, so ownership MOET be
            # checked per thread on the re-entrant thread lock.
            if threading.get_ident() == a_thread.get("id"):
                if console._store_thread_lock._is_owned():
                    order.append(f"a_post_rollback_locked:{name}")
                else:
                    order.append(f"a_released:{name}")
                    b_done.wait(timeout=10)
                    order.append(f"a_post_rollback:{name}")
            return original(*args, **kwargs)

        monkeypatch.setattr(console, name, wrapped)

    for name in ("_restore_review_state", "_refresh_after_rollback"):
        hook(name)

    def run_a():
        a_thread["id"] = threading.get_ident()
        try:
            _approve(console, rid, sid, obj_a)
        except RuntimeError as exc:
            errors.append(str(exc))
        finally:
            order.append("a_done")

    def run_b():
        flag.wait(timeout=10)
        order.append("a_fault")
        try:
            _approve(console, rid, sid, obj_b)
            order.append("b_committed")
        except Exception as exc:  # surfaced via the assertion below
            errors.append(f"B:{type(exc).__name__}:{exc}")
        finally:
            b_done.set()

    ta, tb = threading.Thread(target=run_a), threading.Thread(target=run_b)
    tb.start(); ta.start()
    ta.join(timeout=30); tb.join(timeout=30)
    assert not ta.is_alive() and not tb.is_alive()
    assert errors == ["r2_injected_fault"]
    print("R2_T5_ORDER", order)
    # #678 (B1): the Storeopdracht owner remirrors after its rollback while it
    # still holds the store lock, so the pre-#678 window (A releases, B commits,
    # A remirrors stale) MAG NIET exist. B commits only after A's remirror.
    released = [i for i, m in enumerate(order) if m.startswith("a_released:")]
    locked = [i for i, m in enumerate(order) if m.startswith("a_post_rollback_locked:")]
    assert released == [], f"A MAG NIET remirror after releasing the store lock: {order}"
    assert locked, f"A's post-rollback remirror MOET run: {order}"
    assert order.index("a_fault") < locked[0] < order.index("b_committed"), order
    fresh = _console(tmp_path, workflow_postgres)
    b_bindings = [x for x in fresh.workflow_review_store.read_bindings().get(sid, [])
                  if x["object_id"] == obj_b["object_id"] and x["decision"] == "approve"]
    a_bindings = [x for x in fresh.workflow_review_store.read_bindings().get(sid, [])
                  if x["object_id"] == obj_a["object_id"]]
    events = fresh.workflow_review_store.read_events()
    print("R2_T5", {"b_bindings": len(b_bindings), "a_bindings": len(a_bindings), "events": len(events)})
    assert len(b_bindings) == 1, "B's concurrent approve binding lost"
    assert a_bindings == [], "A's failed review left a binding"
    assert any(e.get("object_id") == obj_b["object_id"] for e in events), "B's audit event lost"
    # R1: ledger = bytes before A + exactly B's events; R3: bindings file = PostgreSQL.
    assert events[: len(before_events)] == before_events
    assert _ledger_state_bytes(console) == before_ledger + _serialise(events[len(before_events):])
    _assert_review_authority_without_mirrors(console)


def test_t6_remirror_failure_warning_carries_only_allowed_fields(workflow_postgres, tmp_path, monkeypatch, caplog):
    import logging
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    flag = threading.Event()
    _inject_fault(monkeypatch, flag)
    secret_text = obj_a["content"]["clean_text"]
    username = console._account(rid)["username"]

    def failing_remirror():
        raise RuntimeError(f"{secret_text} {username} {rid}")

    monkeypatch.setattr(console, "_refresh_review_runtime", failing_remirror)
    caplog.set_level(logging.WARNING, logger="src.workflows.workflow_review_cutover_v1")
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        _approve(console, rid, sid, obj_a)
    records = [r for r in caplog.records if r.name == "src.workflows.workflow_review_cutover_v1"]
    assert records, "a remirror failure MOET log a structured warning"
    for record in records:
        message = record.getMessage()
        assert message == (
            f"review_rollback_refresh_failed snapshot_id={sid} "
            "error_code=RuntimeError refresh_error_type=RuntimeError"
        )
        for forbidden in (secret_text, username, rid, "r2_injected_fault"):
            assert forbidden not in message
        assert record.exc_info is None


def test_t7_review_path_bypasses_inherited_documents_compensation(workflow_postgres, tmp_path, monkeypatch):
    """Route 1: the review path MOET NOOIT run documents_cutover's compensating context."""
    from contextlib import contextmanager
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    before = _state(console, sid)
    entered = []
    inherited = documents_cutover._PostgresWorkflowDocumentsMixin._atomic_snapshot_mutation

    @contextmanager
    def recording(self, snapshot_id):
        entered.append(snapshot_id)
        with inherited(self, snapshot_id):
            yield

    monkeypatch.setattr(documents_cutover._PostgresWorkflowDocumentsMixin, "_atomic_snapshot_mutation", recording)
    flag = threading.Event()
    _inject_fault(monkeypatch, flag)
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        _approve(console, rid, sid, obj_a)
    print("R2_T7", {"inherited_compensating_context_entered": entered})
    assert entered == [], f"review path entered inherited compensation: {entered}"
    assert _state(_console(tmp_path, workflow_postgres), sid) == before


# R2: pin every class in the production MRO that defines one of the boundary methods.
EXPECTED_BOUNDARY_MRO = [
    ("src.workflows.workflow_review_cutover_v1", "_PostgresWorkflowReviewMixin",
     ("_atomic_snapshot_mutation", "_reload_store_locked")),
    ("src.workflows.workflow_documents_cutover_v1", "_PostgresWorkflowDocumentsMixin",
     ("_atomic_snapshot_mutation", "_reload_store_locked")),
    # D6b: the file-only base/ReviewClosure mutation contexts and base reload are gone;
    # Route 1 in the review mixin is the only mutation boundary.
    ("src.operations_console_v1", "OperationsConsole", ("_store_write_lock",)),
]


def test_r2_mro_boundary_methods_are_pinned():
    from src.workflows.workflow_badge_counts_postgres_v1 import (
        FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole as Production,
    )
    names = ("_atomic_snapshot_mutation", "_store_write_lock", "_reload_store_locked")
    found = [
        (cls.__module__, cls.__qualname__, tuple(n for n in names if n in cls.__dict__))
        for cls in Production.__mro__
        if any(n in cls.__dict__ for n in names)
    ]
    print("R2_MRO", found)
    assert found == EXPECTED_BOUNDARY_MRO, "MRO of the boundary methods changed; Route 1 MOET be re-reviewed"


def _arm_inner_fault(monkeypatch):
    """R4: raise inside the INNER nested review mutation (closed_review_loop:252 approve)."""
    original = rc._PostgresWorkflowReviewMixin._atomic_snapshot_mutation
    depth, fired = threading.local(), []

    @contextmanager
    def wrapped(self, snapshot_id):
        level = getattr(depth, "n", 0) + 1
        depth.n = level
        try:
            with original(self, snapshot_id):
                yield
                if level == 2 and not fired:
                    fired.append(level)
                    raise RuntimeError("r2_inner_fault")
        finally:
            depth.n = level - 1

    monkeypatch.setattr(rc._PostgresWorkflowReviewMixin, "_atomic_snapshot_mutation", wrapped)
    return fired


def test_r4_inner_nested_fault_restores_state_and_original_error(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    before, before_ledger = _state(console, sid), _ledger_state_bytes(console)
    fired = _arm_inner_fault(monkeypatch)
    with pytest.raises(RuntimeError, match="^r2_inner_fault$"):
        _approve(console, rid, sid, obj_a)
    assert fired == [2], "fault MOET fire in the inner nested mutation"
    assert _state(console, sid) == before
    assert _state(_console(tmp_path, workflow_postgres), sid) == before
    assert _ledger_state_bytes(console) == before_ledger
    _assert_review_authority_without_mirrors(console)


def test_r4_inner_nested_fault_with_remirror_failure_logs_one_warning(workflow_postgres, tmp_path, monkeypatch, caplog):
    import logging
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    before = _state(console, sid)
    _arm_inner_fault(monkeypatch)

    def failing_remirror():
        raise RuntimeError("remirror_down")

    monkeypatch.setattr(console, "_refresh_review_runtime", failing_remirror)
    caplog.set_level(logging.WARNING, logger="src.workflows.workflow_review_cutover_v1")
    with pytest.raises(RuntimeError, match="^r2_inner_fault$"):
        _approve(console, rid, sid, obj_a)
    records = [r.getMessage() for r in caplog.records if r.name == "src.workflows.workflow_review_cutover_v1"]
    print("R4_WARNINGS", records)
    assert _state(_console(tmp_path, workflow_postgres), sid) == before
    assert len(records) == 1, f"exactly one remirror warning MOET be logged: {records}"


def test_r6_heading_batch_route_does_not_enter_inherited_compensation(workflow_postgres, tmp_path, monkeypatch):
    """R6: observe the heading_batch route under a fault; behaviour unchanged."""
    from src.operations_console_v1 import review_lane
    console, rid, sid, _queue = _setup(tmp_path, workflow_postgres)
    headings = [r for r in console.snapshot_objects(sid)
                if r.get("object_type") != "document" and review_lane(r, review_path="richtlijn") == "fast"
                and (r.get("governance") or {}).get("validation_status") not in {"approved", "rejected", "superseded"}]
    assert headings
    before, before_ledger = _state(console, sid), _ledger_state_bytes(console)
    entered = []
    inherited = documents_cutover._PostgresWorkflowDocumentsMixin._atomic_snapshot_mutation

    @contextmanager
    def recording(self, snapshot_id):
        entered.append(snapshot_id)
        with inherited(self, snapshot_id):
            yield

    monkeypatch.setattr(documents_cutover._PostgresWorkflowDocumentsMixin, "_atomic_snapshot_mutation", recording)
    flag, writes = threading.Event(), []
    _inject_fault(monkeypatch, flag)
    _spy_writes(monkeypatch, console, flag, writes)
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        console.batch_confirm_headings(actor_id=rid, snapshot_id=sid,
                                       object_ids=[r["object_id"] for r in headings],
                                       expected_revision=console.objects_revision(sid))
    print("R6", {"entered": entered, "writes_after_fault": writes})
    assert flag.is_set()
    assert entered == []
    assert writes == []
    assert _state(_console(tmp_path, workflow_postgres), sid) == before
    assert _ledger_state_bytes(console) == before_ledger


def _failing_remirror_warnings(monkeypatch, console, caplog):
    import logging

    def failing_remirror():
        raise RuntimeError("remirror_down")

    monkeypatch.setattr(console, "_refresh_review_runtime", failing_remirror)
    caplog.set_level(logging.WARNING, logger="src.workflows.workflow_review_cutover_v1")

    def collected():
        return [r.getMessage() for r in caplog.records
                if r.name == "src.workflows.workflow_review_cutover_v1"
                and r.getMessage().startswith("review_rollback_refresh_failed")]

    return collected


def test_optc_ordinary_fault_through_commit_prepared_store_logs_one_warning(workflow_postgres, tmp_path, monkeypatch, caplog):
    """B1 (#678): the fault fires in _commit_prepared_store below two nested review
    mutations; only the Storeopdracht owner remirrors, the warning MOET appear exactly once."""
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    before = _state(console, sid)
    flag = threading.Event()
    _inject_fault(monkeypatch, flag)
    remirror_calls = []
    collected = _failing_remirror_warnings(monkeypatch, console, caplog)
    original = rc._PostgresWorkflowReviewMixin._refresh_after_rollback

    def counting(self, snapshot_id, exc):
        remirror_calls.append(type(exc).__name__)
        return original(self, snapshot_id, exc)

    monkeypatch.setattr(rc._PostgresWorkflowReviewMixin, "_refresh_after_rollback", counting)
    with pytest.raises(RuntimeError, match="^r2_injected_fault$"):
        _approve(console, rid, sid, obj_a)
    records = collected()
    print("OPTC_COMMIT_WARNINGS", records, "REMIRROR_CALLS", remirror_calls)
    assert len(remirror_calls) == 1, f"only the command owner MAG remirror: {remirror_calls}"
    assert _state(_console(tmp_path, workflow_postgres), sid) == before
    assert len(records) == 1, f"exactly one remirror warning MOET be logged: {records}"


def test_optc_direct_commit_prepared_store_fault_logs_one_warning(workflow_postgres, tmp_path, monkeypatch, caplog):
    from copy import deepcopy
    console, _rid, sid, _queue = _setup(tmp_path, workflow_postgres)
    changed = deepcopy(console._envelope(sid))
    changed["title"] = "Begrippen (optc)"
    flag = threading.Event()
    _inject_fault(monkeypatch, flag)
    collected = _failing_remirror_warnings(monkeypatch, console, caplog)
    with pytest.raises(RuntimeError, match="^r2_injected_fault$"):
        console._commit_prepared_store(envelopes={sid: changed}, snapshot_id=sid)
    records = collected()
    print("OPTC_DIRECT_COMMIT_WARNINGS", records)
    assert len(records) == 1, f"exactly one remirror warning MOET be logged: {records}"


def _caught_nested(console, rid, sid, obj):
    with console._atomic_snapshot_mutation(sid):
        try:
            with console._atomic_snapshot_mutation(sid):
                _approve(console, rid, sid, obj)
                raise RuntimeError("optc_caught_inner")
        except RuntimeError as exc:
            assert str(exc) == "optc_caught_inner"


def test_optc_caught_nested_fault_mirrors_equal_pg(workflow_postgres, tmp_path, monkeypatch):
    """A caller catches the inner fault and continues: mirrors MOET equal PG after.
    B1 (#678): the participant MAG NIET remirror; the owner commits and rebuilds."""
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    calls = []
    original = rc._PostgresWorkflowReviewMixin._refresh_after_rollback

    def counting(self, snapshot_id, exc):
        calls.append(str(exc))
        return original(self, snapshot_id, exc)

    monkeypatch.setattr(rc._PostgresWorkflowReviewMixin, "_refresh_after_rollback", counting)
    events_before = console.workflow_review_store.read_events()
    bindings_before = console.workflow_review_store.read_bindings()
    _caught_nested(console, rid, sid, obj_a)
    print("OPTC_CAUGHT_REMIRRORS", calls)
    _assert_i2_events_match_bindings(console, events_before, bindings_before)
    assert calls == [], f"a participant MAG NIET remirror inside the open command: {calls}"
    _assert_review_authority_without_mirrors(console)
    fresh = _console(tmp_path, workflow_postgres)
    assert _state(fresh, sid) == _state(console, sid)


def test_optc_caught_nested_fault_does_not_run_rollback_remirror(workflow_postgres, tmp_path, monkeypatch, caplog):
    """B1 (#678): a caught participant fault is no command rollback, so the
    rollback remirror MAG NIET run and no rollback warning is logged."""
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    collected = _failing_remirror_warnings(monkeypatch, console, caplog)
    _caught_nested(console, rid, sid, obj_a)
    records = collected()
    print("OPTC_CAUGHT_WARNINGS", records)
    assert records == [], f"no rollback remirror MAG run for a caught participant fault: {records}"


def test_optc_dedupe_survives_exception_rejecting_attributes(workflow_postgres, tmp_path, monkeypatch, caplog):
    """An exception type without __dict__ (slots) MOET still log exactly once
    per original exception and MAG NIET raise from the dedupe itself."""
    console, _rid, sid, _queue = _setup(tmp_path, workflow_postgres)
    collected = _failing_remirror_warnings(monkeypatch, console, caplog)

    class Slotted(Exception):
        __slots__ = ()

        def __setattr__(self, name, value):
            raise AttributeError(name)

    exc = Slotted("x")
    console._refresh_after_rollback(sid, exc)
    console._refresh_after_rollback(sid, exc)
    records = collected()
    print("OPTC_SLOTTED_WARNINGS", records)
    assert len(records) == 1, f"exactly one remirror warning MOET be logged: {records}"


def _binding_rows(bindings):
    return sum(len(rows) for rows in bindings.values())


def _assert_i2_events_match_bindings(console, events_before, bindings_before):
    """I2: new approve events count MOET equal new binding rows count."""
    events = console.workflow_review_store.read_events()[len(events_before):]
    approves = [e for e in events if e.get("event_type") == "clinical_review_approve"]
    new_rows = _binding_rows(console.workflow_review_store.read_bindings()) - _binding_rows(bindings_before)
    assert len(approves) == new_rows, {"approve_events": len(approves), "new_binding_rows": new_rows}


def test_i2_successful_nested_approve_merges_event_into_parent_buffer(workflow_postgres, tmp_path):
    """Per-level buffers: a nested level that succeeds MOET merge its events
    into the parent, so the outer commit flushes exactly the approve event."""
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    events_before = console.workflow_review_store.read_events()
    bindings_before = console.workflow_review_store.read_bindings()
    with console._atomic_snapshot_mutation(sid):
        with console._atomic_snapshot_mutation(sid):
            _approve(console, rid, sid, obj_a)
    events = console.workflow_review_store.read_events()[len(events_before):]
    print("I2_NESTED_OK", [e.get("event_type") for e in events])
    assert [e.get("event_type") for e in events].count("clinical_review_approve") == 1
    _assert_i2_events_match_bindings(console, events_before, bindings_before)
    _assert_review_authority_without_mirrors(console)
