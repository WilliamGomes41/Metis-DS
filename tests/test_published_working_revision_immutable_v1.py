"""Repair #217: a durable publication seals the WorkingRevision.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.review.closed_review_loop_v1 import ClosedLoopReviewConsole
from src.operations_console_v1 import ConsoleError
from src.review.review_closure_v1 import PUBLISHED_WORKING_REVISION_IMMUTABLE
from src.workflows.workflow_document_concurrency_v1 import (
    PUBLISHED_WORKING_REVISION_IMMUTABLE as STORE_IMMUTABLE,
    PostgresConcurrentWorkflowDocumentStore,
)
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError


ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]






def test_canonical_release_seals_review_before_workflow_envelope_reconciliation(tmp_path: Path, production_console) -> None:
    console = production_console(processing_binder=bind_fixture_selections)
    researcher = console.create_account(
        username="immutable-researcher",
        password="immutable-secret",
        roles=("researcher",),
    )
    reviewer = console.create_account(
        username="immutable-reviewer",
        password="immutable-secret",
        roles=("reviewer",),
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="immutable.html",
        content_type="text/html",
        data=(
            b"<html><body><h1>Richtlijn</h1><h2>1 Zorg</h2>"
            b"<p>De verpleegkundige bespreekt passende ondersteuning met de client.</p>"
            b"</body></html>"
        ),
        ingest_kind="new",
        title="Immutable fixture",
        version="1.0",
        date="2026-09-16",
        live_url="",
        class_="richtlijn",
        family="immutable",
        named_reviewers=[reviewer["account_id"]],
    )
    snapshot_id = receipt["snapshot_id"]
    target = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") not in {"document", "heading"}
        and row.get("proposed_object_type") != "heading"
    )

    # Persist one pre-closure revise state before publication. This is exactly the
    # kind of legacy state the startup migration used to reopen.
    ClosedLoopReviewConsole.review_object(
        console,
        actor_id=reviewer["account_id"],
        snapshot_id=snapshot_id,
        object_id=target["object_id"],
        decision="revise",
        suitability="mist_context",
        eindoordeel="goedkeuren_na_correctie",
        comment="legacy revise before publication",
        expected_revision=console.objects_revision(snapshot_id),
    )
    assert console._current_object(snapshot_id, target["object_id"])["governance"]["validation_status"] == "revise"

    before_revision = console.objects_revision(snapshot_id)
    before_objects = console.snapshot_objects(snapshot_id)
    from tests.complete_workflow_support import seed_canonical_release
    seed_canonical_release(console.canonical_publication_store, snapshot_id=snapshot_id, token=snapshot_id)


    # Canonical authority has committed, but the workflow projection has not.
    assert console._envelope(snapshot_id)["state"] == "captured_not_published"
    assert console.snapshot_is_published(snapshot_id) is True

    assert console.migrate_legacy_revise_to_review() == 0
    with pytest.raises(ConsoleError) as caught:
        console.review_object(
            actor_id=reviewer["account_id"],
            snapshot_id=snapshot_id,
            object_id=target["object_id"],
            decision="reject",
            comment="must not mutate published history",
            expected_revision=before_revision,
        )
    assert caught.value.code == PUBLISHED_WORKING_REVISION_IMMUTABLE
    assert console.objects_revision(snapshot_id) == before_revision
    assert console.snapshot_objects(snapshot_id) == before_objects

    # Production startup reconciles metadata while retaining the canonical seal.
    restarted = production_console(processing_binder=bind_fixture_selections)
    assert restarted._envelope(snapshot_id)["state"] == "published"
    assert restarted.snapshot_is_published(snapshot_id) is True
    assert restarted.migrate_legacy_revise_to_review() == 0
    assert restarted.objects_revision(snapshot_id) == before_revision
    assert restarted._current_object(snapshot_id, target["object_id"])["governance"]["validation_status"] == "revise"




def _snapshot_token() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"snap-{token[:16]}-{token[16:24]}", token


def _workflow_envelope(*, snapshot_id: str, token: str, account_id: str) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "source_id": f"src-{token[:16]}",
        "document_id": f"console-richtlijn-immutable-{token[:8]}",
        "title": "Published immutability fixture",
        "family": "immutable",
        "class": "richtlijn",
        "state": "captured_not_published",
        "publication_eligibility": "eligible",
        "content_kind": "html",
        "ingest_kind": "new",
        "version": "1.0",
        "date": "2026-09-16",
        "sha256": token * 2,
        "locator": f"g0-local:sources/private/{token * 2}/fixture.html",
        "immutable_storage_locator": f"azure://aidataservice/canonical-sources/{token * 2}/fixture.html",
        "live_url": "",
        "uploader_account_id": account_id,
        "named_reviewers": [],
        "replaces_snapshot_id": None,
        "object_diff": None,
        "clinical_rereview_required": False,
        "acquired_at": "2026-09-16T09:00:00Z",
        "console_version": "immutable-test",
    }


def _workflow_object(document_id: str) -> dict[str, Any]:
    return {
        "object_id": f"{document_id}-object",
        "object_version": "1.0",
        "object_type": "explanation",
        "content": {"clean_text": "Published content must remain unchanged."},
    }


def _prepare_postgres(complete_postgres) -> tuple[PostgresConcurrentWorkflowDocumentStore, str]:
    return PostgresConcurrentWorkflowDocumentStore(complete_postgres), complete_postgres.dsn


def _create_workflow_account(store: PostgresConcurrentWorkflowDocumentStore, token: str) -> str:
    account_id = f"acc-{token[:20]}"
    with store._connect() as con:
        con.execute(
            "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
            (account_id, f"immutable-{token}", "Immutable Test", ["researcher"], "salt", "hash"),
        )
    return account_id


def _seed_durable_release(
    store: PostgresConcurrentWorkflowDocumentStore,
    *,
    snapshot_id: str,
    token: str,
) -> tuple[str, str, str]:
    release_id = f"release-{token}"
    release_version = f"1.0-{token[:8]}"
    published_at = "2026-09-16T09:30:00+00:00"
    with store._connect() as con:
        con.execute(
            "INSERT INTO publication_releases(release_id,release_version,release_owner,status,created_at,published_at) "
            "VALUES(%s,%s,'publisher','published',%s,%s)",
            (release_id, release_version, published_at, published_at),
        )
        con.execute(
            "INSERT INTO audit_events(entity_type,entity_id,entity_version,event_type,actor,event_at,details) "
            "VALUES('release',%s,%s,'release_published','publisher',%s,%s::jsonb)",
            (release_id, release_version, published_at, json.dumps({"snapshot_id": snapshot_id})),
        )
    return release_id, release_version, published_at


def test_postgres_authority_blocks_object_write_in_canonical_commit_crash_window(complete_postgres) -> None:
    store, _dsn_value = _prepare_postgres(complete_postgres)
    snapshot_id, token = _snapshot_token()
    account_id = _create_workflow_account(store, token)
    release_id = ""
    try:
        envelope = _workflow_envelope(snapshot_id=snapshot_id, token=token, account_id=account_id)
        objects = [_workflow_object(envelope["document_id"])]
        store.write_bundle(envelope=envelope, objects=objects)
        before_envelope = store.get_envelope(snapshot_id)
        assert before_envelope is not None
        before_objects = store.list_document_objects(snapshot_id)
        before_revision = store.objects_revision(snapshot_id)

        release_id, release_version, published_at = _seed_durable_release(
            store, snapshot_id=snapshot_id, token=token
        )

        mutated = deepcopy(before_objects)
        mutated[0]["content"]["clean_text"] = "This mutation must be rejected."
        with pytest.raises(WorkflowDocumentStoreError, match=STORE_IMMUTABLE):
            store.write_bundle(
                envelope=before_envelope,
                objects=mutated,
                expected_revision=before_revision,
            )
        assert store.list_document_objects(snapshot_id) == before_objects
        assert store.objects_revision(snapshot_id) == before_revision
        assert store.get_envelope(snapshot_id)["state"] == "captured_not_published"  # type: ignore[index]

        # Reconciliation is allowed to copy only exact publication metadata from
        # canonical authority; it cannot alter the WorkingRevision payload.
        published = deepcopy(before_envelope)
        published.update(
            {
                "state": "published",
                "published": True,
                "release_id": release_id,
                "release_version": release_version,
                "published_at": published_at,
                "published_by": "publisher",
            }
        )
        store.write_bundle(envelope=published)
        reconciled = store.get_envelope(snapshot_id)
        assert reconciled is not None
        assert reconciled["state"] == "published"
        assert reconciled["release_id"] == release_id
        assert store.list_document_objects(snapshot_id) == before_objects
        assert store.objects_revision(snapshot_id) == before_revision

        changed_metadata = deepcopy(reconciled)
        changed_metadata["title"] = "Attempted historical rewrite"
        with pytest.raises(WorkflowDocumentStoreError, match=STORE_IMMUTABLE):
            store.write_bundle(envelope=changed_metadata)
        assert store.get_envelope(snapshot_id)["title"] == "Published immutability fixture"  # type: ignore[index]
    finally:
        with store._connect() as con:
            con.execute("DELETE FROM workflow.documents WHERE snapshot_id=%s", (snapshot_id,))
            con.execute("DELETE FROM workflow.accounts WHERE account_id=%s", (account_id,))
            if release_id:
                con.execute("DELETE FROM audit_events WHERE entity_type='release' AND entity_id=%s", (release_id,))
                con.execute("DELETE FROM publication_releases WHERE release_id=%s", (release_id,))
