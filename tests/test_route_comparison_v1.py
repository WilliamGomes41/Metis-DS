"""Full isolated comparison lifecycle with retry and stale-write boundaries."""
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.route_comparison_v1 import (
    ComparisonError, ComparisonStore, analyze, assess, blind_view, cancel,
    claim_arm, close, fail_arm, finish_arm, digest,
)


FRAGMENTS = [{"fragment_id": "f1", "clean_text": "Voorwaarde A. Advies B.",
              "section_path": ["Aanbevelingen"]}]
OUTPUT = [{"text": "Voorwaarde A. Advies B.", "type": "recommendation",
           "source_fragment_ids": ["f1"]}]


def recorded_frozen(*, deterministic=None):
    """A comparison frozen before Protocol 4.3.0; none can be created any more."""
    deterministic = deterministic or {"status": "pending", "attempts": []}
    return {"schema_version": "route-comparison-v1", "comparison_id": "rc_" + "1" * 32,
            "owner_account_id": "owner", "snapshot_id": "snapshot", "source_hash": "a" * 64,
            "title": "Bron", "state": "frozen", "version": 2, "created_at": "2026-10-01T00:00:00+00:00",
            "events": [{"actor": "owner", "action": "created", "at": "2026-10-01T00:00:00+00:00", "version": 1},
                       {"actor": "owner", "action": "frozen", "at": "2026-10-01T00:00:00+00:00", "version": 2}],
            "arms": {"deterministic": deterministic, "semantic": {"status": "pending", "attempts": []}},
            "assessments": {}, "analyses": [], "fragments": FRAGMENTS, "input_hash": digest(FRAGMENTS),
            "code_version": "commit-1", "semantic_model": "model-1",
            "blind_order": ["semantic", "deterministic"]}


def prepared(tmp_path, **recorded):
    store = ComparisonStore(tmp_path)
    return store, store.create(recorded_frozen(**recorded))


def change(store, row, operation):
    return store.change(row["comparison_id"], owner="owner", allowed_scope={"snapshot"},
                        expected_version=row["version"], operation=operation)


def test_deterministic_arm_is_retired_and_never_claimed(tmp_path):
    store, row = prepared(tmp_path)
    with pytest.raises(ComparisonError, match="comparison_route_retired"):
        change(store, row, lambda r: claim_arm(r, actor="owner", route="deterministic"))
    assert store.get(row["comparison_id"], allowed_scope={"snapshot"}) == row


def test_recorded_lifecycle_blindness_and_no_normal_quality_events(tmp_path):
    recorded = {"status": "succeeded", "output": OUTPUT, "output_hash": digest(OUTPUT),
                "execution": {"strategy": "deterministic"},
                "attempts": [{"attempt_id": "a" * 32, "status": "succeeded",
                              "started_at": "2026-10-01T00:00:00+00:00",
                              "finished_at": "2026-10-01T00:00:01+00:00"}]}
    store, row = prepared(tmp_path, deterministic=recorded)
    assert row["state"] == "frozen"
    assert store.get(row["comparison_id"], allowed_scope=set()) is None
    assert change(store, row, lambda r: claim_arm(r, actor="owner", route="deterministic"))[1] == ""
    row, attempt = change(store, row, lambda r: claim_arm(r, actor="owner", route="semantic"))
    row, _ = change(store, row, lambda r: finish_arm(
        r, actor="owner", route="semantic", attempt_id=attempt, output=OUTPUT,
        execution={"strategy": "semantic"}))
    assert row["state"] == "output_ready"
    view = blind_view(row)
    assert set(view["arms"]) == {"A", "B"}
    assert all("strategy" not in str(value) for value in view["arms"].values())
    for label in ("A", "B"):
        row, _ = change(store, row, lambda r: assess(
            r, actor="reviewer", label=label, choices=["direct"],
            coverage="complete", problems=[], actions=1))
    assert row["state"] == "assessed"
    row, report = change(store, row, lambda r: analyze(r, actor="owner"))
    assert {v["direct"] for v in report["results"].values()} == {1}
    row, _ = change(store, row, lambda r: close(r, actor="owner", decision="more_cases"))
    assert row["state"] == "closed"
    assert store.get(row["comparison_id"], allowed_scope={"snapshot"}) == row
    assert set(tmp_path.glob("*.json")) == {tmp_path / (row["comparison_id"] + ".json")}
    with pytest.raises(ComparisonError):
        change(store, row, lambda r: cancel(r, actor="owner", reason="late"))


def test_failed_arm_retry_and_stale_attempt_never_rewrites_result(tmp_path):
    store, row = prepared(tmp_path)
    row, first = change(store, row, lambda r: claim_arm(r, actor="owner", route="semantic"))
    row, _ = change(store, row, lambda r: fail_arm(
        r, actor="owner", route="semantic", attempt_id=first, error_code="provider_timeout"))
    assert row["state"] == "blocked"
    row, second = change(store, row, lambda r: claim_arm(r, actor="owner", route="semantic"))
    with pytest.raises(ComparisonError, match="stale_attempt"):
        change(store, row, lambda r: finish_arm(
            r, actor="owner", route="semantic", attempt_id=first, output=OUTPUT, execution={}))
    row, _ = change(store, row, lambda r: finish_arm(
        r, actor="owner", route="semantic", attempt_id=second, output=OUTPUT, execution={}))
    assert [a["status"] for a in row["arms"]["semantic"]["attempts"]] == ["failed", "succeeded"]


def test_concurrency_and_invalid_source_binding_do_not_commit(tmp_path):
    store, row = prepared(tmp_path)
    stale = row["version"]
    def claim(_):
        return store.change(row["comparison_id"], owner="owner", allowed_scope={"snapshot"},
                            expected_version=stale, operation=lambda r:
                            claim_arm(r, actor="owner", route="semantic"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _outcome(claim, _), range(2)))
    assert sorted(results) == ["comparison_stale_version", "ok"]
    current = store.get(row["comparison_id"], allowed_scope={"snapshot"})
    with pytest.raises(ComparisonError, match="source_unbound"):
        change(store, current, lambda r: finish_arm(
            r, actor="owner", route="semantic",
            attempt_id=r["arms"]["semantic"]["attempts"][-1]["attempt_id"],
            output=[dict(OUTPUT[0], source_fragment_ids=["elsewhere"])], execution={}))
    assert store.get(row["comparison_id"], allowed_scope={"snapshot"}) == current


def _outcome(fn, arg):
    try:
        fn(arg)
        return "ok"
    except ComparisonError as exc:
        return str(exc)
