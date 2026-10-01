"""Native independent workers preserve graph/policy CAS and transaction atomicity.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
import pytest

from src.operations_console_v1 import ConsoleError
from tests.test_review_participation_management import change, person
from tests.decision_graph_native_support import native_state
from tests.test_decision_graph_chain import _accounts, ingest, command, complete_graph, policy, source_pdf, _ingest_boom


def test_native_graph_policy_race_and_failure_rollback(tmp_path, monkeypatch):
    state, _, _ = native_state(tmp_path)
    console = state("setup")
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    workers = [state(str(i)) for i in range(2)]
    graph_command = command(workers[0], accounts, sid, "graph-race", graph=complete_graph(console, sid))
    new_policy = policy(accounts, "required")
    new_policy["revision"] = 2
    policy_command = command(workers[1], accounts, sid, "policy-race", policy=new_policy)
    barrier = Barrier(2)
    def run(index):
        barrier.wait(timeout=5)
        try:
            if index == 0:
                return workers[index].update_decision_graph(**graph_command)
            return change(workers[index], accounts, sid, "add_required", accounts["reviewer"]["account_id"], expected_revision=policy_command["expected_revision"])
        except ConsoleError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sum(isinstance(r, dict) for r in results) == 1, results
    assert results.count("snapshot_object_write_conflict") == 1
    console = state("rollback")
    before = deepcopy(console._envelope(sid))
    objects = deepcopy(console.snapshot_objects(sid))
    events = console.workflow_review_store.read_events()
    p = deepcopy(before["review_policy"])
    p["revision"] += 1
    extra = person(console, "rollback-extra")
    original = console._commit_prepared_store
    def fail_after_writes(**kwargs):
        original(**kwargs)
        raise RuntimeError("simulated_failure_before_outer_commit")
    monkeypatch.setattr(console, "_commit_prepared_store", fail_after_writes)
    with pytest.raises(RuntimeError, match="simulated_failure"):
        change(console, accounts, sid, "add_optional", extra)
    restarted = state("verify")
    assert restarted._envelope(sid) == before
    assert restarted.snapshot_objects(sid) == objects
    assert restarted.workflow_review_store.read_events() == events


def test_native_identical_ingest_retry_has_one_snapshot(tmp_path):
    state, _, _ = native_state(tmp_path)
    console = state("setup")
    accounts = _accounts(console)
    workers = [state(str(i)) for i in range(2)]
    data = source_pdf()
    barrier = Barrier(2)
    def run(index):
        barrier.wait(timeout=5)
        return _ingest_boom(workers[index], accounts, data=data, filename="same.pdf", content_type="application/pdf",
            named_reviewers=[], review_policy=policy(accounts), command_id="identical-upload")["snapshot_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results[0] == results[1]
    assert len(state("restart").list_envelopes()) == 1


def test_native_policy_publication_race_never_publishes_stale_review(tmp_path):
    from tests.test_decision_graph_chain import finish
    state, store, _ = native_state(tmp_path)
    console = state("setup")
    accounts = _accounts(console)
    sid = ingest(console, accounts)["snapshot_id"]
    finish(console, accounts, sid)
    publisher, editor = state("publisher"), state("editor")
    p = policy(accounts, "required")
    p["revision"] = 2
    cmd = command(editor, accounts, sid, "policy-vs-publish", policy=p)
    barrier = Barrier(2)
    def run(index):
        barrier.wait(timeout=5)
        try:
            if index == 0:
                return publisher.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
            return change(editor, accounts, sid, "add_required", accounts["reviewer"]["account_id"], expected_revision=cmd["expected_revision"])
        except ConsoleError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        published, changed = list(pool.map(run, range(2)))
    release = store.release_for_snapshot(sid)
    if release:
        assert published["status"] == "PASS"
        assert changed == "published_working_revision_immutable"
        assert release["decision_graph_release"]["policy"]["revision"] == 1
    else:
        assert published["status"] == "BLOCKED"
        assert isinstance(changed, dict)
        assert state("verify")._envelope(sid)["review_policy"]["revision"] == 2


def test_native_late_extraction_cannot_replace_new_policy(tmp_path, monkeypatch):
    from threading import Event
    state, _, _ = native_state(tmp_path)
    setup = state("setup")
    accounts = _accounts(setup)
    sid = ingest(setup, accounts)["snapshot_id"]
    worker, editor = state("worker"), state("editor")
    started, proceed = Event(), Event()
    original = worker._fragments_and_spec
    def delayed(*args, **kwargs):
        started.set()
        assert proceed.wait(timeout=5)
        return original(*args, **kwargs)
    monkeypatch.setattr(worker, "_fragments_and_spec", delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker.reextract_unpublished,
            actor_id=accounts["researcher"]["account_id"], snapshot_id=sid)
        assert started.wait(timeout=5)
        p = policy(accounts, "required")
        p["revision"] = 2
        try:
            change(editor, accounts, sid, "add_required", accounts["reviewer"]["account_id"])
            p = deepcopy(editor._envelope(sid)["review_policy"])
            expected = deepcopy(editor.snapshot_objects(sid))
        finally:
            proceed.set()
        with pytest.raises(ConsoleError) as failure:
            future.result(timeout=10)
        assert failure.value.code == "snapshot_object_write_conflict"
    restarted = state("verify")
    assert restarted._envelope(sid)["review_policy"] == p
    assert restarted.snapshot_objects(sid) == expected
