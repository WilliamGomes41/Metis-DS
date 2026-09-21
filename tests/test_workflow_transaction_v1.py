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
from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.workflow_review_cutover_v1 import PostgresReviewWorkflowDurablePublicationConsole
from src.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflow_transaction_v1 import bind_workflow_stores, workflow_transaction

ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
TEST_PASSWORD = __name__
MIGRATIONS = (
    "002_workflow_schema.sql",
    "003_workflow_document_envelope_payload.sql",
    "004_workflow_review_authority.sql",
    "005_workflow_remaining_authority.sql",
    "006_workflow_authorization_payload.sql",
    "010_workflow_topic_identity.sql",
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


def test_delete_transaction_rolls_back_document_binding_and_audit_together(
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    documents, reviews, _uploader, reviewer = _stores(workflow_postgres)
    reviews.replace_snapshot_bindings(
        "snap-atomic", [_authorization("snap-atomic", reviewer)]
    )

    with pytest.raises(RuntimeError, match="simulated_delete_failure"):
        with workflow_transaction(reviews):
            documents.delete_document("snap-atomic")
            reviews.replace_snapshot_bindings("snap-atomic", [])
            reviews.append_event(
                event_type="unpublished_snapshot_deleted",
                object_id="snap-atomic",
                object_version="1.0",
                actor="uploader",
                details={"snapshot_id": "snap-atomic"},
            )
            raise RuntimeError("simulated_delete_failure")

    assert documents.get_envelope("snap-atomic") is not None
    assert documents.list_document_objects("snap-atomic") == _objects()
    assert list(reviews.read_bindings()) == ["snap-atomic"]
    assert reviews.read_bindings()["snap-atomic"] == [
        _authorization("snap-atomic", reviewer)
    ]
    assert reviews.read_events() == []

def test_reject_stale_conflict_leaves_no_durable_event_or_authorization(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    identity = PostgresWorkflowIdentityStore(workflow_postgres)
    documents = PostgresConcurrentWorkflowDocumentStore(workflow_postgres)
    reviews = PostgresWorkflowReviewStore(workflow_postgres)
    bind_workflow_stores(identity, documents, reviews)
    console = PostgresReviewWorkflowDurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime-review-atomicity",
        workflow_identity_store=identity,
        workflow_document_store=documents,
        workflow_review_store=reviews,
    )
    researcher = console.create_account(
        username="researcher.atomic",
        password=TEST_PASSWORD,
        roles=("researcher", "reviewer"),
    )
    reviewer = console.create_account(
        username="reviewer.atomic",
        password=TEST_PASSWORD,
        roles=("reviewer",),
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="atomicity.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Review atomicity fixture",
        version="1.0",
        date="2026-09-20",
        live_url="https://example.test/review-atomicity",
        class_="richtlijn",
        family="test",
        named_reviewers=[researcher["account_id"], reviewer["account_id"]],
    )
    snapshot_id = receipt["snapshot_id"]
    current = console.snapshot_objects(snapshot_id)
    target = next(row for row in current if row.get("object_type") == "unclassified")
    stale_revision = console.objects_revision(snapshot_id)

    concurrent = documents.list_document_objects(snapshot_id)
    concurrent_target = next(
        row for row in concurrent if row["object_id"] == target["object_id"]
    )
    concurrent_target.setdefault("metadata", {})["concurrent_marker"] = "winner"
    envelope = documents.get_envelope(snapshot_id)
    assert envelope is not None
    documents.write_bundle(
        envelope=envelope,
        objects=concurrent,
        expected_revision=stale_revision,
    )

    before_objects = documents.list_document_objects(snapshot_id)
    before_events = reviews.read_events()
    before_bindings = reviews.read_bindings()

    with pytest.raises(ConsoleError) as caught:
        console.review_object(
            actor_id=reviewer["account_id"],
            snapshot_id=snapshot_id,
            object_id=target["object_id"],
            decision="reject",
            comment="Reject from a stale form submission.",
            expected_revision=stale_revision,
        )

    assert caught.value.code == SNAPSHOT_OBJECT_WRITE_CONFLICT
    assert documents.list_document_objects(snapshot_id) == before_objects
    assert reviews.read_bindings() == before_bindings
    assert reviews.read_events() == before_events

def test_successful_approve_persists_authorization_and_survives_restart(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    identity = PostgresWorkflowIdentityStore(workflow_postgres)
    documents = PostgresConcurrentWorkflowDocumentStore(workflow_postgres)
    reviews = PostgresWorkflowReviewStore(workflow_postgres)
    bind_workflow_stores(identity, documents, reviews)
    console = PostgresReviewWorkflowDurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime-approve-authority-a",
        workflow_identity_store=identity,
        workflow_document_store=documents,
        workflow_review_store=reviews,
    )
    researcher = console.create_account(
        username="researcher.approve",
        password=TEST_PASSWORD,
        roles=("researcher", "reviewer"),
    )
    reviewer = console.create_account(
        username="reviewer.approve",
        password=TEST_PASSWORD,
        roles=("reviewer",),
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="approve-authority.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Approve authority fixture",
        version="1.0",
        date="2026-09-20",
        live_url="https://example.test/approve-authority",
        class_="richtlijn",
        family="test",
        named_reviewers=[researcher["account_id"], reviewer["account_id"]],
    )
    snapshot_id = receipt["snapshot_id"]
    target = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") == "unclassified"
    )
    before_events = reviews.read_events()

    console.review_object(
        actor_id=reviewer["account_id"],
        snapshot_id=snapshot_id,
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="explanation",
        suitability="ja",
        eindoordeel="goedkeuren",
        type_action="dit_klopt",
        expected_revision=console.objects_revision(snapshot_id),
    )

    approved = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row["object_id"] == target["object_id"]
    )
    assert approved["governance"]["validation_status"] == "approved"
    events = reviews.read_events()
    assert len(events) == len(before_events) + 1
    bindings = reviews.read_bindings()
    assert snapshot_id in bindings
    assert len(bindings[snapshot_id]) == 1
    binding = bindings[snapshot_id][0]
    assert binding["object_id"] == approved["object_id"]
    assert binding["object_version"] == approved["object_version"]
    assert binding["reviewer_id"] == reviewer["account_id"]
    assert binding["decision"] == "approve"
    assert binding["valid"] is True

    import psycopg

    with psycopg.connect(workflow_postgres.dsn) as con:
        row = con.execute(
            "SELECT snapshot_id,object_id,object_version,reviewer_account_id,decision,valid "
            "FROM workflow.publish_authorizations WHERE snapshot_id=%s",
            (snapshot_id,),
        ).fetchone()
    assert row == (
        snapshot_id,
        approved["object_id"],
        approved["object_version"],
        reviewer["account_id"],
        "approve",
        True,
    )

    restarted_identity = PostgresWorkflowIdentityStore(workflow_postgres)
    restarted_documents = PostgresConcurrentWorkflowDocumentStore(workflow_postgres)
    restarted_reviews = PostgresWorkflowReviewStore(workflow_postgres)
    bind_workflow_stores(restarted_identity, restarted_documents, restarted_reviews)
    restarted = PostgresReviewWorkflowDurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime-approve-authority-b",
        workflow_identity_store=restarted_identity,
        workflow_document_store=restarted_documents,
        workflow_review_store=restarted_reviews,
    )
    assert restarted.object_review_bindings(snapshot_id) == bindings[snapshot_id]


def test_approve_stale_conflict_leaves_no_durable_event_or_authorization(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    identity = PostgresWorkflowIdentityStore(workflow_postgres)
    documents = PostgresConcurrentWorkflowDocumentStore(workflow_postgres)
    reviews = PostgresWorkflowReviewStore(workflow_postgres)
    bind_workflow_stores(identity, documents, reviews)
    console = PostgresReviewWorkflowDurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime-stale-approve",
        workflow_identity_store=identity,
        workflow_document_store=documents,
        workflow_review_store=reviews,
    )
    researcher = console.create_account(
        username="researcher.stale-approve",
        password=TEST_PASSWORD,
        roles=("researcher", "reviewer"),
    )
    reviewer = console.create_account(
        username="reviewer.stale-approve",
        password=TEST_PASSWORD,
        roles=("reviewer",),
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="stale-approve.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Stale approve fixture",
        version="1.0",
        date="2026-09-20",
        live_url="https://example.test/stale-approve",
        class_="richtlijn",
        family="test",
        named_reviewers=[researcher["account_id"], reviewer["account_id"]],
    )
    snapshot_id = receipt["snapshot_id"]
    target = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") == "unclassified"
    )
    console.review_object(
        actor_id=reviewer["account_id"],
        snapshot_id=snapshot_id,
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="explanation",
        suitability="ja",
        eindoordeel="goedkeuren",
        type_action="dit_klopt",
        expected_revision=console.objects_revision(snapshot_id),
    )
    current_target = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row["object_id"] == target["object_id"]
    )
    confirmed_type = current_target["confirmed_object_type"]
    stale_revision = console.objects_revision(snapshot_id)

    concurrent = documents.list_document_objects(snapshot_id)
    concurrent_target = next(
        row
        for row in reversed(concurrent)
        if row["object_id"] == target["object_id"]
        and row["object_version"] == current_target["object_version"]
    )
    concurrent_target.setdefault("metadata", {})["concurrent_marker"] = "winner"
    envelope = documents.get_envelope(snapshot_id)
    assert envelope is not None
    documents.write_bundle(
        envelope=envelope,
        objects=concurrent,
        expected_revision=stale_revision,
    )

    before_objects = documents.list_document_objects(snapshot_id)
    before_events = reviews.read_events()
    before_bindings = reviews.read_bindings()

    with pytest.raises(ConsoleError) as caught:
        console.review_object(
            actor_id=reviewer["account_id"],
            snapshot_id=snapshot_id,
            object_id=target["object_id"],
            decision="approve",
            confirmed_object_type=confirmed_type,
            suitability="ja",
            eindoordeel="goedkeuren",
            type_action="dit_klopt",
            expected_revision=stale_revision,
        )

    assert caught.value.code == SNAPSHOT_OBJECT_WRITE_CONFLICT
    assert documents.list_document_objects(snapshot_id) == before_objects
    assert reviews.read_bindings() == before_bindings
    assert reviews.read_events() == before_events

