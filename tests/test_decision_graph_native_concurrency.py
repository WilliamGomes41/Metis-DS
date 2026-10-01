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
            fn = workers[index].update_decision_graph if index == 0 else workers[index].change_review_policy
            return fn(**(graph_command if index == 0 else policy_command))
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
    original = console._commit_prepared_store
    def fail_after_writes(**kwargs):
        original(**kwargs)
        raise RuntimeError("simulated_failure_before_outer_commit")
    monkeypatch.setattr(console, "_commit_prepared_store", fail_after_writes)
    with pytest.raises(RuntimeError, match="simulated_failure"):
        console.change_review_policy(**command(console, accounts, sid, "rollback", policy=p))
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
