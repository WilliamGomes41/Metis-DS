"""Real PostgreSQL concurrency evidence for the shared workflow stores.

The tests use independent store instances and independent database connections.
Known blockers are strict xfails: they are reproduced evidence, not safety proof.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.operations_console_v1 import SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflow_identity_postgres_v1 import (
    PostgresWorkflowIdentityStore,
    WorkflowIdentityStoreError,
)
from src.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflow_review_postgres_v1 import PostgresWorkflowReviewStore

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    "002_workflow_schema.sql",
    "003_workflow_document_envelope_payload.sql",
    "004_workflow_review_authority.sql",
    "005_workflow_remaining_authority.sql",
)


@pytest.fixture(autouse=True)
def workflow_postgres() -> PostgresCanonicalConfig:
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for PostgreSQL concurrency evidence")

    import psycopg

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute("DROP SCHEMA IF EXISTS workflow CASCADE")
        for migration in MIGRATIONS:
            text = (ROOT / "db" / "migrations" / migration).read_text(encoding="utf-8")
            for statement in text.split(";"):
                statement = statement.strip()
                if statement:
                    con.execute(statement)

    config = PostgresCanonicalConfig(dsn=dsn)
    yield config

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute("DROP SCHEMA IF EXISTS workflow CASCADE")


def _account_record(account_id: str, username: str, *, roles: list[str] | None = None) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "username": username,
        "display_name": username,
        "roles": roles or ["reviewer"],
        "password_salt": "salt",
        "password_hash": "hash",
        "created_at": "2026-09-12T10:00:00Z",
    }


def _seed_accounts(config: PostgresCanonicalConfig) -> tuple[str, str]:
    store = PostgresWorkflowIdentityStore(config)
    uploader = "acc-uploader"
    reviewer = "acc-reviewer"
    store.create_account(_account_record(uploader, "uploader", roles=["researcher", "publisher"]))
    store.create_account(_account_record(reviewer, "reviewer", roles=["reviewer"]))
    return uploader, reviewer


def _envelope(snapshot_id: str, uploader: str, reviewer: str) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "source_id": f"source-{snapshot_id}",
        "document_id": f"doc-{snapshot_id}",
        "title": f"Document {snapshot_id}",
        "family": "test",
        "class": "richtlijn",
        "state": "review",
        "publication_eligibility": "eligible",
        "content_kind": "pdf",
        "ingest_kind": "upload",
        "version": "1.0",
        "date": "2026-09-12",
        "sha256": "a" * 64,
        "locator": f"source://{snapshot_id}",
        "immutable_storage_locator": f"azure://{snapshot_id}",
        "live_url": "",
        "uploader_account_id": uploader,
        "named_reviewers": [reviewer],
        "replaces_snapshot_id": None,
        "object_diff": None,
        "clinical_rereview_required": False,
        "acquired_at": "2026-09-12T10:00:00Z",
        "console_version": "concurrency-test",
    }


def _objects(prefix: str) -> list[dict[str, Any]]:
    return [
        {"object_id": f"{prefix}-a", "object_version": "1.0", "text": "A"},
        {"object_id": f"{prefix}-b", "object_version": "1.0", "text": "B"},
    ]


def _authorization(snapshot_id: str, object_id: str, reviewer: str) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_version": "1.0",
        "canonical_object_hash": (object_id[-1:] or "a") * 64,
        "confirmed_object_type": "claim",
        "reviewer": "reviewer",
        "reviewer_id": reviewer,
        "decision": "approve",
        "valid": True,
    }


def test_concurrent_duplicate_username_has_one_winner(workflow_postgres: PostgresCanonicalConfig) -> None:
    first = PostgresWorkflowIdentityStore(workflow_postgres)
    second = PostgresWorkflowIdentityStore(workflow_postgres)
    barrier = threading.Barrier(2)

    def create(store: PostgresWorkflowIdentityStore, account_id: str) -> str:
        barrier.wait(timeout=5)
        try:
            store.create_account(_account_record(account_id, "same-user"))
            return "ok"
        except WorkflowIdentityStoreError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: create(*args), ((first, "acc-a"), (second, "acc-b"))))

    assert sorted(results) == ["ok", "username_already_exists"]
    assert len(first.list_accounts()) == 1


def test_session_revoke_is_immediately_visible_to_other_instance(
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    first = PostgresWorkflowIdentityStore(workflow_postgres)
    second = PostgresWorkflowIdentityStore(workflow_postgres)
    first.create_account(_account_record("acc-session", "session-user"))
    session = {
        "token": "shared-session-token",
        "account_id": "acc-session",
        "created_at": "2026-09-12T10:00:00Z",
        "expires_at": "2027-09-12T10:00:00Z",
    }
    first.create_session(session)
    assert second.session_account(session["token"])["account_id"] == "acc-session"
    first.revoke_session(session["token"])
    assert second.session_account(session["token"]) is None


def test_same_object_concurrent_write_rejects_one_stale_writer(
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    uploader, reviewer = _seed_accounts(workflow_postgres)
    first = PostgresWorkflowDocumentRuntimeStore(workflow_postgres)
    second = PostgresWorkflowDocumentRuntimeStore(workflow_postgres)
    envelope = _envelope("snap-same", uploader, reviewer)
    first.write_bundle(envelope=envelope, objects=_objects("same"))

    revision = first.objects_revision("snap-same")
    rows_a = first.list_document_objects("snap-same")
    rows_b = second.list_document_objects("snap-same")
    rows_a[0]["text"] = "A from instance A"
    rows_b[0]["text"] = "A from instance B"
    barrier = threading.Barrier(2)

    def write(store: PostgresWorkflowDocumentRuntimeStore, rows: list[dict[str, Any]]) -> str:
        barrier.wait(timeout=5)
        try:
            store.write_bundle(envelope=envelope, objects=rows, expected_revision=revision)
            return "ok"
        except WorkflowDocumentStoreError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: write(*args), ((first, rows_a), (second, rows_b))))

    assert results.count("ok") == 1
    assert results.count(SNAPSHOT_OBJECT_WRITE_CONFLICT) == 1
    final = first.list_document_objects("snap-same")
    assert final[0]["text"] in {"A from instance A", "A from instance B"}


@pytest.mark.xfail(
    strict=True,
    reason="known blocker: snapshot-wide revision rejects independent edits to different objects",
)
def test_different_object_concurrent_edits_both_survive(
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    uploader, reviewer = _seed_accounts(workflow_postgres)
    first = PostgresWorkflowDocumentRuntimeStore(workflow_postgres)
    second = PostgresWorkflowDocumentRuntimeStore(workflow_postgres)
    envelope = _envelope("snap-independent", uploader, reviewer)
    first.write_bundle(envelope=envelope, objects=_objects("independent"))

    revision = first.objects_revision("snap-independent")
    rows_a = first.list_document_objects("snap-independent")
    rows_b = second.list_document_objects("snap-independent")
    rows_a[0]["text"] = "A changed"
    rows_b[1]["text"] = "B changed"
    barrier = threading.Barrier(2)

    def write(store: PostgresWorkflowDocumentRuntimeStore, rows: list[dict[str, Any]]) -> str:
        barrier.wait(timeout=5)
        try:
            store.write_bundle(envelope=envelope, objects=rows, expected_revision=revision)
            return "ok"
        except WorkflowDocumentStoreError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: write(*args), ((first, rows_a), (second, rows_b))))

    final = first.list_document_objects("snap-independent")
    assert results == ["ok", "ok"]
    assert [row["text"] for row in final] == ["A changed", "B changed"]


def test_concurrent_audit_creates_from_two_instances_both_survive(
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    identity = PostgresWorkflowIdentityStore(workflow_postgres)
    identity.create_account(_account_record("acc-auditor", "auditor", roles=["researcher"]))
    first = PostgresWorkflowRemainingStore(workflow_postgres)
    second = PostgresWorkflowRemainingStore(workflow_postgres)
    barrier = threading.Barrier(2)

    def create(store: PostgresWorkflowRemainingStore, audit_id: str) -> str:
        barrier.wait(timeout=5)
        store.create_audit(
            {
                "audit_id": audit_id,
                "audit_type": "experiment",
                "title": audit_id,
                "created_by": "acc-auditor",
                "created_at": "2026-09-12T10:00:00Z",
                "updated_at": "2026-09-12T10:00:00Z",
                "payload": {"audit_id": audit_id},
            }
        )
        return "ok"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: create(*args), ((first, "audit-a"), (second, "audit-b"))))

    assert results == ["ok", "ok"]
    assert {row["audit_id"] for row in first.list_audits()} == {"audit-a", "audit-b"}


class _BarrierReviewStore(PostgresWorkflowReviewStore):
    def __init__(self, *args: Any, barrier: threading.Barrier, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._test_barrier = barrier

    def _new_event(self, **kwargs: Any) -> dict[str, Any]:
        self._test_barrier.wait(timeout=5)
        return super()._new_event(**kwargs)


@pytest.mark.xfail(
    strict=True,
    reason="known blocker: locking the current tail cannot serialize two writers when the ledger is empty",
)
def test_concurrent_review_events_keep_one_linear_hash_chain(
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    barrier = threading.Barrier(2)
    first = _BarrierReviewStore(workflow_postgres, barrier=barrier)
    second = _BarrierReviewStore(workflow_postgres, barrier=barrier)

    def append(store: PostgresWorkflowReviewStore, actor: str) -> str:
        store.append_event(
            event_type="review_decision",
            object_id=f"object-{actor}",
            object_version="1.0",
            actor=actor,
            details={},
        )
        return "ok"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: append(*args), ((first, "reviewer-a"), (second, "reviewer-b"))))

    events = first.read_events()
    assert results == ["ok", "ok"]
    assert len(events) == 2
    assert events[0]["previous_event_hash"] is None
    assert events[1]["previous_event_hash"] == events[0]["event_hash"]


@pytest.mark.xfail(
    strict=True,
    reason="known blocker: whole-table authorization replacement loses another instance's stale-snapshot update",
)
def test_independent_instances_do_not_lose_authorization_updates_from_stale_snapshots(
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    uploader, reviewer = _seed_accounts(workflow_postgres)
    documents = PostgresWorkflowDocumentRuntimeStore(workflow_postgres)
    for snapshot_id in ("snap-base", "snap-a", "snap-b"):
        documents.write_bundle(
            envelope=_envelope(snapshot_id, uploader, reviewer),
            objects=_objects(snapshot_id),
        )

    first = PostgresWorkflowReviewStore(workflow_postgres)
    second = PostgresWorkflowReviewStore(workflow_postgres)
    first.replace_bindings(
        {"snap-base": [_authorization("snap-base", "snap-base-a", reviewer)]}
    )

    stale_a = deepcopy(first.read_bindings())
    stale_b = deepcopy(second.read_bindings())
    stale_a["snap-a"] = [_authorization("snap-a", "snap-a-a", reviewer)]
    stale_b["snap-b"] = [_authorization("snap-b", "snap-b-a", reviewer)]

    first.replace_bindings(stale_a)
    second.replace_bindings(stale_b)

    final = first.read_bindings()
    assert set(final) == {"snap-base", "snap-a", "snap-b"}
