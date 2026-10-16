"""R2 guards: after a native rollback the review mixin only remirrors.

T3: without a concurrent writer a failed review mutation leaves PostgreSQL unchanged.
T4: after the rollback no write reaches workflow.* from the review mixin's error
    path (including remirror/refresh_*), and disk mirrors are written under the lock.
T5: two threads on one console object (sync route + threadpool): B's concurrent
    approve survives A's failed review.
T6: a remirror failure logs codes, ids and error types only.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import inspect
import threading
import traceback

import pytest

from src.proportionate_review_v1 import _batch_type, normal_risk_batch_queue
from src.workflows import workflow_documents_cutover_v1 as documents_cutover
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from src.workflows.workflow_review_cutover_v1 import PostgresReviewWorkflowDurablePublicationConsole
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401

REVIEW_WRITES = ("append_event", "replace_snapshot_bindings", "replace_bindings")
DOCUMENT_WRITES = ("write_bundle", "create_document_bundle")
# documents_cutover:778-783 compensates under the lock; out of scope (#665).
# Only frames inside that compensating block are exempt, never the whole function.
OUT_OF_SCOPE_FILE = "workflow_documents_cutover_v1.py"
OUT_OF_SCOPE_FUNC = "_atomic_snapshot_mutation"


def _compensation_line_range():
    """Line range of the blind write_bundle compensation in documents_cutover (#665).

    Located from the source via markers, not hardcoded: from the
    `with suppress(Exception):` line up to (not including) the
    `self._bindings = before_bindings` line in the non-conflict except branch.
    """
    func = documents_cutover._PostgresWorkflowDocumentsMixin._atomic_snapshot_mutation
    func = getattr(func, "__wrapped__", func)
    lines, first = inspect.getsourcelines(func)
    start = end = None
    for offset, line in enumerate(lines):
        text = line.strip()
        if start is None and text == "with suppress(Exception):":
            start = first + offset
        elif start is not None and text == "self._bindings = before_bindings":
            end = first + offset
            break
    assert start is not None and end is not None, "compensation markers MOET exist in documents_cutover"
    body = "".join(lines[start - first:end - first])
    assert "workflow_document_store.write_bundle(" in body, "compensation block MOET be the write_bundle call"
    return range(start, end)


COMPENSATION_LINES = _compensation_line_range()


def _is_out_of_scope(frames):
    return any(
        f.filename.rsplit("/", 1)[-1] == OUT_OF_SCOPE_FILE
        and f.name == OUT_OF_SCOPE_FUNC
        and f.lineno in COMPENSATION_LINES
        for f in frames
    )


def _console(root, config):
    identity = PostgresWorkflowIdentityStore(config)
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    bind_workflow_stores(identity, documents, reviews)
    return PostgresReviewWorkflowDurablePublicationConsole(
        root=root, source_store=root / "sources", runtime=root / "runtime",
        workflow_identity_store=identity, workflow_document_store=documents,
        workflow_review_store=reviews,
    )


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
                    if not _is_out_of_scope(traceback.extract_stack()):
                        writes.append(__name)
                return __original(*args, **kwargs)

            monkeypatch.setattr(store, name, spy)


def _spy_mirror_depth(monkeypatch, console, flag, depths):
    original = console._mirror_bindings

    def spy():
        if flag.is_set():
            depths.append(console._store_lock_depth)
        return original()

    monkeypatch.setattr(console, "_mirror_bindings", spy)


def test_t3_failed_review_without_concurrency_leaves_state_unchanged(workflow_postgres, tmp_path, monkeypatch):
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    before = _state(console, sid)
    flag = threading.Event()
    _inject_fault(monkeypatch, flag)
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        _approve(console, rid, sid, obj_a)
    assert flag.is_set()
    assert _state(console, sid) == before
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
    original = console._remirror_review_runtime

    def remirror_with_forbidden_write():
        result = original()
        try:
            # Called without arguments: the spy records the attempt, the real
            # store then raises TypeError, so no row is written.
            console.workflow_review_store.append_event()
        except TypeError:
            pass
        return result

    monkeypatch.setattr(console, "_remirror_review_runtime", remirror_with_forbidden_write)


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

    def hook(name):
        original = getattr(console, name, None)
        if original is None:
            return

        def wrapped(*args, **kwargs):
            # Thread A's post-rollback step (restore on main, remirror after
            # the fix) when A no longer owns the store lock. _store_lock_depth
            # and the flock are shared by both threads, so ownership MOET be
            # checked per thread on the re-entrant thread lock.
            if threading.get_ident() == a_thread.get("id") and not console._store_thread_lock._is_owned():
                order.append(f"a_released:{name}")
                b_done.wait(timeout=10)
                order.append(f"a_post_rollback:{name}")
            return original(*args, **kwargs)

        monkeypatch.setattr(console, name, wrapped)

    for name in ("_restore_review_state", "_remirror_after_rollback"):
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
    # Intended interleaving (MOET): A faults under the lock, releases it, then
    # B commits, and only then A's post-rollback step (restore pre-fix,
    # remirror post-fix) runs.
    released = [i for i, m in enumerate(order) if m.startswith("a_released:")]
    resumed = [i for i, m in enumerate(order) if m.startswith("a_post_rollback:")]
    assert released and resumed, f"window MOET be exercised: {order}"
    assert order.index("a_fault") < released[0] < order.index("b_committed") < resumed[0], order
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


def test_t6_remirror_failure_warning_carries_only_allowed_fields(workflow_postgres, tmp_path, monkeypatch, caplog):
    import logging
    console, rid, sid, (obj_a, _obj_b) = _setup(tmp_path, workflow_postgres)
    flag = threading.Event()
    _inject_fault(monkeypatch, flag)
    secret_text = obj_a["content"]["clean_text"]
    username = console._account(rid)["username"]

    def failing_remirror():
        raise RuntimeError(f"{secret_text} {username} {rid}")

    monkeypatch.setattr(console, "_remirror_review_runtime", failing_remirror)
    caplog.set_level(logging.WARNING, logger="src.workflows.workflow_review_cutover_v1")
    with pytest.raises(RuntimeError, match="r2_injected_fault"):
        _approve(console, rid, sid, obj_a)
    records = [r for r in caplog.records if r.name == "src.workflows.workflow_review_cutover_v1"]
    assert records, "a remirror failure MOET log a structured warning"
    for record in records:
        message = record.getMessage()
        assert message == (
            f"review_rollback_remirror_failed snapshot_id={sid} "
            "error_code=RuntimeError remirror_error_type=RuntimeError"
        )
        for forbidden in (secret_text, username, rid, "r2_injected_fault"):
            assert forbidden not in message
        assert record.exc_info is None
