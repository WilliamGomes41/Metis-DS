"""Full isolated comparison lifecycle with retry and stale-write boundaries."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.route_comparison_v1 import (
    ComparisonError, ComparisonStore, analyze, assess, blind_view, cancel,
    claim_arm, close, fail_arm, finish_arm, freeze, new_comparison,
)


FRAGMENTS = [{"fragment_id": "f1", "clean_text": "Voorwaarde A. Advies B.",
              "section_path": ["Aanbevelingen"]}]
OUTPUT = [{"text": "Voorwaarde A. Advies B.", "type": "recommendation",
           "source_fragment_ids": ["f1"]}]


def prepared(tmp_path):
    store = ComparisonStore(tmp_path)
    row = store.create(new_comparison(owner="owner", snapshot_id="snapshot",
                                      source_hash="a" * 64, title="Bron"))
    row, _ = store.change(row["comparison_id"], owner="owner", allowed_scope={"snapshot"},
                          expected_version=row["version"], operation=lambda r:
                          freeze(r, actor="owner", source_hash="a" * 64,
                                 fragments=FRAGMENTS, code_version="commit-1", semantic_model="model-1"))
    return store, row


def change(store, row, operation):
    return store.change(row["comparison_id"], owner="owner", allowed_scope={"snapshot"},
                        expected_version=row["version"], operation=operation)


def test_paired_lifecycle_blindness_and_no_normal_quality_events(tmp_path):
    store, row = prepared(tmp_path)
    assert row["state"] == "frozen"
    assert store.get(row["comparison_id"], allowed_scope=set()) is None
    for route in ("deterministic", "semantic"):
        row, attempt = change(store, row, lambda r: claim_arm(r, actor="owner", route=route))
        row, _ = change(store, row, lambda r: finish_arm(
            r, actor="owner", route=route, attempt_id=attempt, output=OUTPUT,
            execution={"strategy": route}))
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
