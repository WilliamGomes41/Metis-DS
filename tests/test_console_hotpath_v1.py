"""Regression proof for the Documenten/Review interactive hot path.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from src.azure_postgres_credential_v1 import CachedAzurePostgresCredential
from src.canonical_publication_postgres_v1 import (
    PostgresCanonicalConfig,
    PostgresCanonicalPublicationStore,
)
from src.document_status_ui_v1 import install_document_status_ui
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole
from src.review_workboard_v1 import install_review_workboard
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
        self.owner.connect_calls += 1
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
        self.connect_calls = 0
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
    assert canonical.connect_calls == 1
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
    assert canonical.connect_calls == 1
    assert canonical.execute_calls == 1
    assert subject.snapshot_is_published("snap-published") is True
    assert subject.snapshot_is_published("snap-unpublished") is True
    assert subject.fallback_publication_calls == 0


class _WorkflowResult:
    def fetchone(self) -> dict[str, Any]:
        return {
            "ingest": 0,
            "review": 2,
            "tree": 0,
            "publish_snapshot_ids": [],
        }


class _WorkflowConnection:
    def __init__(self, owner: "_WorkflowStore") -> None:
        self.owner = owner

    def __enter__(self) -> "_WorkflowConnection":
        self.owner.connect_calls += 1
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, sql: str, _params: tuple[Any, ...]) -> _WorkflowResult:
        self.owner.execute_calls += 1
        assert "document_status" in sql
        return _WorkflowResult()


class _WorkflowStore:
    def __init__(self) -> None:
        self.connect_calls = 0
        self.execute_calls = 0
        self.objects = {
            "snap-published": [object() for _ in range(205)],
            "snap-unpublished": [object() for _ in range(205)],
        }

    def _connect(self) -> _WorkflowConnection:
        return _WorkflowConnection(self)

    def list_document_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        raise AssertionError("hot GET must not materialize object payloads")


_ROUTE_ENVELOPES = [
    {
        "snapshot_id": "snap-published",
        "title": "Published fixture",
        "version": "1.0",
        "family": "hotpath",
        "class": "richtlijn",
        "state": "captured_not_published",
        "named_reviewers": ["acc-hotpath"],
    },
    {
        "snapshot_id": "snap-unpublished",
        "title": "Unpublished fixture",
        "version": "1.0",
        "family": "hotpath",
        "class": "richtlijn",
        "state": "captured_not_published",
        "named_reviewers": ["acc-hotpath"],
    },
]


class _RouteFixtureConsole(OperationsConsole):
    def _route_account(self) -> dict[str, Any]:
        return {
            "account_id": "acc-hotpath",
            "username": "hotpath.researcher",
            "display_name": "Hotpath Researcher",
            "roles": ["researcher", "reviewer"],
        }

    def session_account(self, token: str | None) -> dict[str, Any]:
        assert token == "hotpath-session"
        return self._route_account()

    def _account(self, account_id: str) -> dict[str, Any]:
        assert account_id == "acc-hotpath"
        return self._route_account()

    def family_tree(self) -> dict[str, Any]:
        return {
            "families": {
                "hotpath": {
                    "children": [dict(row) for row in _ROUTE_ENVELOPES]
                }
            }
        }

    def list_envelopes(self) -> list[dict[str, Any]]:
        return [dict(row) for row in _ROUTE_ENVELOPES]

    def snapshot_is_published(self, _snapshot_id: str) -> bool:
        raise AssertionError("tree card must use the prefetched publication set")


class _HotPathRouteConsole(_PostgresBadgeCountsMixin, _RouteFixtureConsole):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.list_status_calls = 0
        self.workboard_summary_calls = 0
        self.snapshot_object_reads = 0

    def list_document_lifecycle_statuses(
        self,
        snapshot_ids: list[str] | None = None,
    ) -> dict[str, dict[str, str]]:
        self.list_status_calls += 1
        assert snapshot_ids is None
        return {
            "snap-published": {
                "workflow_status": "closed",
                "release_status": "published",
                "serving_status": "active",
                "presentation_status": "published",
            },
            "snap-unpublished": {
                "workflow_status": "in_review",
                "release_status": "none",
                "serving_status": "inactive",
                "presentation_status": "in_review",
            },
        }

    def review_workboard_summaries(
        self,
        account_id: str,
        snapshot_id: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        self.workboard_summary_calls += 1
        assert account_id == "acc-hotpath"
        summaries = {
            "snap-published": {
                "envelope": dict(_ROUTE_ENVELOPES[0]),
                "heading_pending": 0,
                "individual_pending": 0,
                "normal_passages": 0,
                "normal_batches": 0,
                "blocked_count": 0,
                "closure_gap_count": 0,
                "closure_gap_first": "",
                "source_passage_review_complete": True,
                "heading_total": 0,
                "individual_total": 0,
                "progress_total": 204,
                "progress_done": 204,
                "progress_approved": 204,
                "progress_rejected": 0,
                "progress_not_included": 0,
                "progress_context": 0,
                "progress_support": 0,
                "progress_superseded": 0,
                "progress_revised": 0,
            },
            "snap-unpublished": {
                "envelope": dict(_ROUTE_ENVELOPES[1]),
                "heading_pending": 1,
                "individual_pending": 2,
                "normal_passages": 20,
                "normal_batches": 1,
                "blocked_count": 0,
                "closure_gap_count": 0,
                "closure_gap_first": "",
                "source_passage_review_complete": False,
                "heading_total": 4,
                "individual_total": 5,
                "progress_total": 204,
                "progress_done": 181,
                "progress_approved": 170,
                "progress_rejected": 2,
                "progress_not_included": 3,
                "progress_context": 2,
                "progress_support": 3,
                "progress_superseded": 1,
                "progress_revised": 4,
            },
        }
        if snapshot_id is not None:
            return {snapshot_id: summaries[snapshot_id]} if snapshot_id in summaries else {}
        return summaries

    def document_readiness(self, _snapshot_id: str) -> dict[str, Any]:
        raise AssertionError("presentation GET must not invoke document_readiness")

    def publication_readiness(self, _snapshot_id: str) -> dict[str, Any]:
        raise AssertionError("presentation GET must not invoke publication_readiness")

    def consider_publish(self, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("presentation GET must not invoke consider_publish")

    def snapshot_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        raise AssertionError("Review index must not load full snapshot objects")

    def snapshot_objects_and_revision(
        self,
        snapshot_id: str,
    ) -> tuple[list[dict[str, Any]], str]:
        assert snapshot_id == "snap-unpublished"
        self.snapshot_object_reads += 1
        return [], "revision-hotpath"


def _installed_client(console: OperationsConsole) -> TestClient:
    app = create_console_app(console)
    install_document_status_ui(app, console)
    install_review_workboard(app, console)
    client = TestClient(app)
    client.cookies.set("console_session", "hotpath-session")
    return client


def test_authenticated_tree_and_review_gets_use_production_list_installers(
    tmp_path: Path,
) -> None:
    canonical = _CanonicalStore({"snap-published"})
    workflow = _WorkflowStore()
    assert sum(len(rows) for rows in workflow.objects.values()) == 410

    console = _HotPathRouteConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    console.canonical_publication_store = canonical
    console.workflow_document_store = workflow
    client = _installed_client(console)

    tree = client.get("/tree")
    assert tree.status_code == 200
    assert "Published fixture" in tree.text
    assert "Unpublished fixture" in tree.text
    assert console.list_status_calls == 1
    assert workflow.connect_calls == 1
    assert workflow.execute_calls == 1
    assert canonical.connect_calls == 1
    assert canonical.execute_calls == 1

    workflow.connect_calls = 0
    workflow.execute_calls = 0
    canonical.connect_calls = 0
    canonical.execute_calls = 0
    review = client.get("/review")
    assert review.status_code == 200
    assert "Published fixture" in review.text
    assert "Unpublished fixture" in review.text
    assert "data-review-workboard" in review.text
    assert console.list_status_calls == 2
    assert console.workboard_summary_calls == 1
    assert console.snapshot_object_reads == 0
    assert workflow.connect_calls == 1
    assert workflow.execute_calls == 1
    assert canonical.connect_calls == 0
    assert canonical.execute_calls == 0


def test_review_default_document_dashboard_uses_projection_without_snapshot_read(
    tmp_path: Path,
) -> None:
    canonical = _CanonicalStore(set())
    workflow = _WorkflowStore()
    console = _HotPathRouteConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    console.canonical_publication_store = canonical
    console.workflow_document_store = workflow
    client = _installed_client(console)

    review = client.get("/review?document=snap-unpublished")
    assert review.status_code == 200
    assert "Unpublished fixture" in review.text
    assert "Reviewvoortgang" in review.text
    assert "181 van 204 bronpassages afgehandeld" in review.text
    assert "1 te controleren · 3 afgerond" in review.text
    assert "2 te beoordelen · 3 afgerond" in review.text
    assert console.snapshot_object_reads == 0


def test_review_task_detail_keeps_one_bounded_selected_snapshot_read(
    tmp_path: Path,
) -> None:
    canonical = _CanonicalStore(set())
    workflow = _WorkflowStore()
    console = _HotPathRouteConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    console.canonical_publication_store = canonical
    console.workflow_document_store = workflow
    client = _installed_client(console)

    review = client.get("/review?document=snap-unpublished&task=headings")
    assert review.status_code == 200
    assert "Unpublished fixture" in review.text
    assert console.list_status_calls == 1
    assert console.snapshot_object_reads == 1


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
