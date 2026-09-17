"""PostgreSQL nav-badge performance regressions for #238.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import os
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflow_badge_counts_postgres_v1 import _PostgresBadgeCountsMixin
from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflow_postgres_migration_v1 import apply_migrations, migration_digest, migration_paths


ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _dsn() -> str:
    value = os.getenv("METIS_TEST_POSTGRES_DSN", "").strip()
    if not value:
        pytest.skip("METIS_TEST_POSTGRES_DSN not configured")
    return value


def _envelope(
    *,
    snapshot_id: str,
    token: str,
    account_id: str,
    reviewer: bool,
    clinical_rereview_required: bool = False,
) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "source_id": f"src-{snapshot_id}",
        "document_id": f"document-{snapshot_id}",
        "title": f"Badge fixture {snapshot_id}",
        "family": "badge-performance",
        "class": "richtlijn",
        "state": "captured_not_published",
        "publication_eligibility": "blocked_pending_review",
        "content_kind": "html",
        "ingest_kind": "new",
        "version": "1.0",
        "date": "2026-09-16",
        "sha256": (token * 2)[:64],
        "locator": f"g0-local:sources/private/{snapshot_id}.html",
        "immutable_storage_locator": None,
        "live_url": "",
        "uploader_account_id": account_id,
        "named_reviewers": [account_id] if reviewer else [],
        "replaces_snapshot_id": None,
        "object_diff": None,
        "clinical_rereview_required": clinical_rereview_required,
        "acquired_at": "2026-09-16T20:00:00Z",
        "console_version": "badge-count-test",
    }


def _objects(snapshot_id: str, count: int, status: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append(
            {
                "object_id": f"{snapshot_id}-object-{index:03d}",
                "object_version": "1.0",
                "object_type": "document" if index == 0 else "recommendation",
                "governance": {
                    "validation_status": status if index == 0 else "approved"
                },
            }
        )
    return rows


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return deepcopy(self.rows)


class _CanonicalConnection:
    def __init__(self, owner: "_CanonicalStore") -> None:
        self.owner = owner

    def __enter__(self) -> "_CanonicalConnection":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> _Result:
        self.owner.execute_calls += 1
        assert "release_published" in sql
        candidates = set(str(value) for value in params[0])
        return _Result(
            [{"snapshot_id": snapshot_id} for snapshot_id in sorted(candidates & self.owner.published)]
        )


class _CanonicalStore:
    def __init__(self, published: set[str]) -> None:
        self.published = set(published)
        self.execute_calls = 0

    def _connect(self) -> _CanonicalConnection:
        return _CanonicalConnection(self)


class _BadgeSubject(_PostgresBadgeCountsMixin):
    def __init__(
        self,
        store: PostgresWorkflowDocumentRuntimeStore,
        canonical: _CanonicalStore,
        account_id: str,
    ) -> None:
        self.workflow_document_store = store
        self.canonical_publication_store = canonical
        self.account_id = account_id

    def _account(self, account_id: str) -> dict[str, Any]:
        assert account_id == self.account_id
        return {
            "account_id": account_id,
            "roles": ["researcher", "reviewer", "publisher"],
        }


def test_badges_use_constant_round_trips_and_reflect_next_read() -> None:
    config = PostgresCanonicalConfig(dsn=_dsn())
    store = PostgresWorkflowDocumentRuntimeStore(config)
    with store._connect() as con:
        paths = migration_paths(ROOT)
        apply_migrations(con, paths=paths, expected_digest=migration_digest(paths))
        workflow_indexes = {
            str(row["indexname"])
            for row in con.execute(
                "SELECT indexname FROM pg_indexes WHERE indexname="
                "'workflow_document_objects_snapshot_validation_status_idx'"
            ).fetchall()
        }
        assert workflow_indexes == {
            "workflow_document_objects_snapshot_validation_status_idx"
        }

        # The same migration must also install the canonical read index when the
        # canonical authority is present, while remaining safe in workflow-only
        # environments. A temporary table proves that branch without polluting
        # the shared PostgreSQL test database.
        con.execute(
            "CREATE TEMP TABLE audit_events ("
            "entity_type TEXT NOT NULL, event_type TEXT NOT NULL, details JSONB NOT NULL)"
        )
        con.execute((ROOT / "db" / "migrations" / "009_console_hotpath_indexes.sql").read_text(encoding="utf-8"))
        indexes = {
            str(row["indexname"])
            for row in con.execute(
                "SELECT indexname FROM pg_indexes WHERE indexname IN ("
                "'workflow_document_objects_snapshot_validation_status_idx',"
                "'audit_events_release_snapshot_idx')"
            ).fetchall()
        }
        assert indexes == {
            "workflow_document_objects_snapshot_validation_status_idx",
            "audit_events_release_snapshot_idx",
        }

    token = uuid.uuid4().hex
    account_id = f"acc-badges-{token[:16]}"
    snapshots = [f"snap-badges-{token[:12]}-{index}" for index in range(3)]
    envelopes = [
        _envelope(
            snapshot_id=snapshots[0],
            token=token,
            account_id=account_id,
            reviewer=True,
        ),
        _envelope(
            snapshot_id=snapshots[1],
            token=token,
            account_id=account_id,
            reviewer=True,
        ),
        _envelope(
            snapshot_id=snapshots[2],
            token=token,
            account_id=account_id,
            reviewer=False,
            clinical_rereview_required=True,
        ),
    ]
    object_sets = [
        _objects(snapshots[0], 200, "revise"),
        _objects(snapshots[1], 200, "needs_review"),
        _objects(snapshots[2], 10, "approved"),
    ]
    assert sum(len(rows) for rows in object_sets) >= 400

    with store._connect() as con:
        con.execute(
            "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
            (
                account_id,
                f"badges-{token}",
                "Badge Test",
                ["researcher", "reviewer", "publisher"],
                "salt",
                "hash",
            ),
        )

    original_connect = store._connect
    try:
        for envelope, objects in zip(envelopes, object_sets, strict=True):
            store.write_bundle(envelope=envelope, objects=objects)

        workflow_connects = 0

        def counted_connect() -> Any:
            nonlocal workflow_connects
            workflow_connects += 1
            return original_connect()

        store._connect = counted_connect  # type: ignore[method-assign]
        store.list_document_objects = lambda _snapshot_id: (_ for _ in ()).throw(  # type: ignore[method-assign]
            AssertionError("badge path must not materialize document objects")
        )
        canonical = _CanonicalStore({snapshots[0]})
        subject = _BadgeSubject(store, canonical, account_id)

        first = subject.waiting_task_counts(account_id)
        assert first == {
            "ingest": 1,
            "tree": 1,
            "review": 2,
            "publish": 2,
            "accounts": 0,
        }
        assert workflow_connects == 1
        assert canonical.execute_calls == 1

        store._connect = original_connect  # type: ignore[method-assign]
        changed = deepcopy(object_sets[0])
        changed[0]["governance"]["validation_status"] = "approved"
        store.write_bundle(envelope=envelopes[0], objects=changed)

        workflow_connects = 0
        canonical.execute_calls = 0
        store._connect = counted_connect  # type: ignore[method-assign]
        second = subject.waiting_task_counts(account_id)
        assert second["ingest"] == 0
        assert second["review"] == 1
        assert second["publish"] == 2
        assert workflow_connects == 1
        assert canonical.execute_calls == 1
    finally:
        store._connect = original_connect  # type: ignore[method-assign]
        with store._connect() as con:
            for snapshot_id in reversed(snapshots):
                con.execute("DELETE FROM workflow.documents WHERE snapshot_id=%s", (snapshot_id,))
            con.execute("DELETE FROM workflow.accounts WHERE account_id=%s", (account_id,))
