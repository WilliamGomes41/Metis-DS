"""PostgreSQL proof for the cross-store workflow transaction boundary.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from src.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflow_transaction_v1 import bind_workflow_stores, workflow_transaction

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    "002_workflow_schema.sql",
    "003_workflow_document_envelope_payload.sql",
    "004_workflow_review_authority.sql",
    "005_workflow_remaining_authority.sql",
)


def _migration_statements(text: str) -> list[str]:
    sql = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


@pytest.fixture
def workflow_postgres() -> PostgresCanonicalConfig:
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for PostgreSQL transaction evidence")

    import psycopg

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute("DROP SCHEMA IF EXISTS workflow CASCADE")
        for migration in MIGRATIONS:
            text = (ROOT / "db" / "migrations" / migration).read_text(encoding="utf-8")
            for statement in _migration_statements(text):
                con.execute(statement)

    config = PostgresCanonicalConfig(dsn=dsn)
    yield config

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute("DROP SCHEMA IF EXISTS workflow CASCADE")


def _account(account_id: str, username: str, roles: list[str]) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "username": username,
        "display_name": username,
        "roles": roles,
        "password_salt": "salt",
        "password_hash": "hash",
        "created_at": "2026-09-12T10:00:00Z",
    }


def _envelope(snapshot_id: str, uploader: str, reviewer: str) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "source_id": f"source-{snapshot_id}",
        "document_id": f"doc-{snapshot_id}",
        "title": "Original title",
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
        "console_version": "transaction-test",
    }


def _objects() -> list[dict[str, Any]]:
    return [
        {"object_id": "atomic-a", "object_version": "1.0", "text": "A"},
        {"object_id": "atomic-b", "object_version": "1.0", "text": "B"},
    ]


def _authorization(snapshot_id: str, reviewer: str) -> dict[str, Any]:
    return {
        "object_id": "atomic-a",
        "object_version": "1.0",
        "canonical_object_hash": "b" * 64,
        "confirmed_object_type": "claim",
        "reviewer": "reviewer",
        "reviewer_id": reviewer,
        "decision": "approve",
        "valid": True,
    }


def _stores(config: PostgresCanonicalConfig) -> tuple[PostgresConcurrentWorkflowDocumentStore, PostgresWorkflowReviewStore, str, str]:
    identity = PostgresWorkflowIdentityStore(config)
    uploader = "acc-uploader"
    reviewer = "acc-reviewer"
    identity.create_account(_account(uploader, "uploader", ["researcher", "publisher"]))
    identity.create_account(_account(reviewer, "reviewer", ["reviewer"]))
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    documents.write_bundle(envelope=_envelope("snap-atomic", uploader, reviewer), objects=_objects())
    bind_workflow_stores(documents, reviews)
    return documents, reviews, uploader, reviewer


def test_cross_store_failure_rolls_back_document_authorization_and_review_event(
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    documents, reviews, uploader, reviewer = _stores(workflow_postgres)
    changed_envelope = _envelope("snap-atomic", uploader, reviewer)
    changed_envelope["title"] = "Changed title"
    changed_objects = documents.list_document_objects("snap-atomic")
    changed_objects[0]["text"] = "Changed A"
    revision = documents.objects_revision("snap-atomic")

    with pytest.raises(RuntimeError, match="simulated_process_loss"):
        with workflow_transaction(reviews):
            documents.write_bundle(
                envelope=changed_envelope,
                objects=changed_objects,
                expected_revision=revision,
            )
            reviews.replace_snapshot_bindings(
                "snap-atomic", [_authorization("snap-atomic", reviewer)]
            )
            reviews.append_event(
                event_type="review_decision",
                object_id="atomic-a",
                object_version="1.0",
                actor="reviewer",
                details={"snapshot_id": "snap-atomic"},
            )
            raise RuntimeError("simulated_process_loss")

    assert documents.get_envelope("snap-atomic")["title"] == "Original title"
    assert documents.list_document_objects("snap-atomic")[0]["text"] == "A"
    assert reviews.read_bindings() == {}
    assert reviews.read_events() == []


def test_cross_store_success_commits_all_workflow_state_together(
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    documents, reviews, uploader, reviewer = _stores(workflow_postgres)
    changed_envelope = _envelope("snap-atomic", uploader, reviewer)
    changed_envelope["title"] = "Committed title"
    changed_objects = documents.list_document_objects("snap-atomic")
    changed_objects[0]["text"] = "Committed A"
    revision = documents.objects_revision("snap-atomic")

    with workflow_transaction(reviews):
        documents.write_bundle(
            envelope=changed_envelope,
            objects=changed_objects,
            expected_revision=revision,
        )
        reviews.replace_snapshot_bindings(
            "snap-atomic", [_authorization("snap-atomic", reviewer)]
        )
        reviews.append_event(
            event_type="review_decision",
            object_id="atomic-a",
            object_version="1.0",
            actor="reviewer",
            details={"snapshot_id": "snap-atomic"},
        )

    assert documents.get_envelope("snap-atomic")["title"] == "Committed title"
    assert documents.list_document_objects("snap-atomic")[0]["text"] == "Committed A"
    assert list(reviews.read_bindings()) == ["snap-atomic"]
    events = reviews.read_events()
    assert len(events) == 1
    assert events[0]["details"]["snapshot_id"] == "snap-atomic"


def test_runtime_review_cutover_uses_shared_workflow_transaction() -> None:
    review_source = (ROOT / "src" / "workflow_review_cutover_v1.py").read_text(encoding="utf-8")
    asgi_source = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert review_source.count("with workflow_transaction(self.workflow_review_store):") >= 2
    assert "bind_workflow_stores(" in asgi_source
