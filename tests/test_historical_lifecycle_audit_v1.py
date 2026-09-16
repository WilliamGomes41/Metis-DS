from __future__ import annotations

import re

from scripts.historical_lifecycle_audit import CHECKS, run_audit


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Connection:
    def __init__(self, result_sets):
        self.result_sets = list(result_sets)
        self.executed = []
        self.rolled_back = False

    def execute(self, sql):
        self.executed.append(sql)
        if sql == "BEGIN READ ONLY":
            return _Rows([])
        return _Rows(self.result_sets.pop(0))

    def rollback(self):
        self.rolled_back = True


def test_audit_queries_are_read_only() -> None:
    forbidden = re.compile(r"\b(insert|update|delete|alter|drop|create|truncate|grant|revoke)\b", re.IGNORECASE)
    assert CHECKS
    for check in CHECKS:
        assert forbidden.search(check.sql) is None, check.name


def test_run_audit_starts_read_only_transaction_and_rolls_back() -> None:
    result_sets = [[] for _ in CHECKS]
    result_sets[0] = [{"release_id": "release-legacy", "status": "published", "published_at": None}]
    connection = _Connection(result_sets)

    report = run_audit(connection)

    assert connection.executed[0] == "BEGIN READ ONLY"
    assert connection.rolled_back is True
    assert report["read_only"] is True
    assert report["status"] == "findings"
    assert report["counts"] == {"error": 1, "warning": 0}
    assert report["by_check"][CHECKS[0].name] == 1
    assert report["findings"][0]["evidence"]["release_id"] == "release-legacy"


def test_clean_audit_is_explicit() -> None:
    connection = _Connection([[] for _ in CHECKS])

    report = run_audit(connection)

    assert report["status"] == "clean"
    assert report["findings"] == []
    assert report["counts"] == {"error": 0, "warning": 0}
