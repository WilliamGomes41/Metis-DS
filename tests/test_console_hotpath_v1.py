"""Regression proof for the Documenten/Review interactive hot path.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import time
from typing import Any

import psycopg
import pytest

from src.azure_postgres_credential_v1 import CachedAzurePostgresCredential
from src.canonical_publication_postgres_v1 import (
    PostgresCanonicalConfig,
    PostgresCanonicalPublicationStore,
)
from src.workflow_badge_counts_postgres_v1 import _PostgresBadgeCountsMixin
from src.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore


pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.rows)


class _CanonicalConnection:
    def __init__(self, owner: "_CanonicalStore") -> None:
        self.owner = owner

    def __enter__(self) -> "_CanonicalConnection":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> _Result:
        self.owner.execute_calls += 1
        if self.owner.fail:
            raise RuntimeError("canonical unavailable")
        assert "release_published" in sql
        candidates = set(str(value) for value in params[0])
        return _Result(
            [{"snapshot_id": value} for value in sorted(candidates & self.owner.published)]
        )


class _CanonicalStore:
    def __init__(self, published: set[str], *, fail: bool = False) -> None:
        self.published = set(published)
        self.fail = fail
        self.execute_calls = 0

    def _connect(self) -> _CanonicalConnection:
        return _CanonicalConnection(self)


class _TreeBase:
    def __init__(self, canonical: _CanonicalStore) -> None:
        self.canonical_publication_store = canonical
        self.fallback_publication_calls = 0

    def family_tree(self) -> dict[str, Any]:
        return {
            "families": {
                "hotpath": {
                    "children": [
                        {"snapshot_id": "snap-published"},
                        {"snapshot_id": "snap-unpublished"},
                    ]
                }
            }
        }

    def snapshot_is_published(self, _snapshot_id: str) -> bool:
        self.fallback_publication_calls += 1
        return False


class _TreeSubject(_PostgresBadgeCountsMixin, _TreeBase):
    pass


def test_tree_batches_publication_history_once_then_uses_prefetched_truth() -> None:
    canonical = _CanonicalStore({"snap-published"})
    subject = _TreeSubject(canonical)

    tree = subject.family_tree()
    assert len(tree["families"]["hotpath"]["children"]) == 2
    assert canonical.execute_calls == 1

    assert subject.snapshot_is_published("snap-published") is True
    assert subject.snapshot_is_published("snap-unpublished") is False
    assert subject.fallback_publication_calls == 0

    # The request-local batch is exhausted after all tree cards consume it.
    assert subject.snapshot_is_published("snap-published") is False
    assert subject.fallback_publication_calls == 1


def test_tree_publication_prefetch_fails_closed_for_delete_affordance() -> None:
    canonical = _CanonicalStore(set(), fail=True)
    subject = _TreeSubject(canonical)

    subject.family_tree()
    assert canonical.execute_calls == 1
    assert subject.snapshot_is_published("snap-published") is True
    assert subject.snapshot_is_published("snap-unpublished") is True
    assert subject.fallback_publication_calls == 0


class _Token:
    def __init__(self, value: str, expires_on: int) -> None:
        self.token = value
        self.expires_on = expires_on


class _RawCredential:
    def __init__(self) -> None:
        self.calls = 0

    def get_token(self, *_scopes: str, **_kwargs: Any) -> _Token:
        self.calls += 1
        return _Token(f"token-{self.calls}", int(time.time()) + 3600)


def test_shared_cached_credential_avoids_token_request_per_connect(monkeypatch: Any) -> None:
    raw = _RawCredential()
    cached = CachedAzurePostgresCredential(raw)
    config = PostgresCanonicalConfig(host="postgres.test", database="metis", user="metis")
    connect_calls: list[dict[str, Any]] = []

    def fake_connect(*_args: Any, **kwargs: Any) -> object:
        connect_calls.append(dict(kwargs))
        return object()

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    canonical = PostgresCanonicalPublicationStore(config, credential=cached)
    workflow = PostgresWorkflowDocumentStore(config, credential=cached)

    canonical._connect()
    workflow._connect()
    canonical._connect()

    assert len(connect_calls) == 3
    assert raw.calls == 1
    assert {call["password"] for call in connect_calls} == {"token-1"}
