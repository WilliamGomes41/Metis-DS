"""PostgreSQL proof for list-safe Documenten/Review reads in #242.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflows.workflow_badge_counts_postgres_v1 import _PostgresBadgeCountsMixin
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflows.workflow_postgres_migration_v1 import apply_migrations, migration_digest, migration_paths


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


def _envelope(snapshot_id: str, token: str, account_id: str) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "source_id": f"src-{snapshot_id}",
        "document_id": f"document-{snapshot_id}",
        "title": f"List-read fixture {snapshot_id}",
        "family": "list-read-performance",
        "class": "richtlijn",
        "state": "captured_not_published",
        "publication_eligibility": "blocked_pending_review",
        "content_kind": "html",
        "ingest_kind": "new",
        "version": "1.0",
        "date": "2026-09-17",
        "sha256": (token * 2)[:64],
        "locator": f"g0-local:sources/private/{snapshot_id}.html",
        "immutable_storage_locator": None,
        "live_url": "",
        "uploader_account_id": account_id,
        "named_reviewers": [account_id],
        "replaces_snapshot_id": None,
        "object_diff": None,
        "clinical_rereview_required": False,
        "acquired_at": "2026-09-17T09:00:00Z",
        "console_version": "list-read-test",
    }


def _object(
    snapshot_id: str,
    index: int,
    *,
    object_type: str,
    validation_status: str,
    gate_result: str = "allowed",
    register_status: str = "selected_as_candidate",
    section: str = "Sectie A",
) -> dict[str, Any]:
    return {
        "object_id": f"{snapshot_id}-object-{index:03d}",
        "object_version": "1.0",
        "object_type": object_type,
        "proposed_object_type": object_type,
        "governance": {"validation_status": validation_status},
        "metadata": {
            "admission": {
                "gate_result": gate_result,
                "section_path": [section],
                "proposed_type": object_type,
            },
            "passage_register": {
                "status": register_status,
                "source": "extract",
            },
        },
        "risk": {
            "level": "standard",
            "risk_level": "standard",
            "requires_second_review": False,
            "risk_fields": [],
        },
        "uncertainty": {"has_uncertainty": False},
        "content": {"clean_text": f"Fixture {index}"},
    }


def _open_objects(snapshot_id: str) -> list[dict[str, Any]]:
    rows = [
        _object(
            snapshot_id,
            0,
            object_type="document",
            validation_status="approved",
        )
    ]
    rows.append(
        _object(
            snapshot_id,
            1,
            object_type="heading",
            validation_status="needs_review",
        )
    )
    for index in range(2, 102):
        rows.append(
            _object(
                snapshot_id,
                index,
                object_type="explanation",
                validation_status="needs_review",
                section="Batch sectie",
            )
        )
    for index in range(102, 152):
        rows.append(
            _object(
                snapshot_id,
                index,
                object_type="recommendation",
                validation_status="needs_review",
                section="Advies",
            )
        )
    for index in range(152, 172):
        rows.append(
            _object(
                snapshot_id,
                index,
                object_type="explanation",
                validation_status="needs_review",
                gate_result="blocked",
                register_status="not_yet_assessed",
                section="Geblokkeerd",
            )
        )
    for index in range(172, 205):
        rows.append(
            _object(
                snapshot_id,
                index,
                object_type="explanation",
                validation_status="approved",
                section="Afgerond",
            )
        )
    return rows


def _closed_objects(snapshot_id: str) -> list[dict[str, Any]]:
    rows = [
        _object(
            snapshot_id,
            0,
            object_type="document",
            validation_status="approved",
        )
    ]
    for index in range(1, 205):
        rows.append(
            _object(
                snapshot_id,
                index,
                object_type="explanation",
                validation_status="approved",
                section="Afgerond",
            )
        )
    return rows


class _ListReadSubject(_PostgresBadgeCountsMixin):
    def __init__(self, store: PostgresWorkflowDocumentRuntimeStore, account_id: str) -> None:
        self.workflow_document_store = store
        self.canonical_publication_store = None
        self.account_id = account_id

    def _account(self, account_id: str) -> dict[str, Any]:
        assert account_id == self.account_id
        return {
            "account_id": account_id,
            "roles": ["researcher", "reviewer", "publisher"],
        }


def test_list_status_and_workboard_are_set_based_at_pilot_scale() -> None:
    config = PostgresCanonicalConfig(dsn=_dsn())
    store = PostgresWorkflowDocumentRuntimeStore(config)
    with store._connect() as con:
        paths = migration_paths(ROOT)
        apply_migrations(con, paths=paths, expected_digest=migration_digest(paths))

    token = uuid.uuid4().hex
    account_id = f"acc-list-{token[:16]}"
    snapshots = [f"snap-list-{token[:12]}-{index}" for index in range(2)]
    envelopes = [_envelope(snapshot_id, token, account_id) for snapshot_id in snapshots]
    object_sets = [_open_objects(snapshots[0]), _closed_objects(snapshots[1])]
    assert sum(len(rows) for rows in object_sets) == 410

    with store._connect() as con:
        con.execute(
            "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
            (
                account_id,
                f"list-{token}",
                "List Read Test",
                ["researcher", "reviewer", "publisher"],
                "salt",
                "hash",
            ),
        )

    original_connect = store._connect
    original_list = store.list_document_objects
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
            AssertionError("list path must not materialize document objects")
        )
        subject = _ListReadSubject(store, account_id)

        lifecycle = subject.list_document_lifecycle_statuses(snapshots)
        assert workflow_connects == 1
        assert lifecycle[snapshots[0]]["presentation_status"] == "in_review"
        assert lifecycle[snapshots[1]]["presentation_status"] == "processing"
        assert all(
            row["presentation_status"] != "ready_for_publication"
            for row in lifecycle.values()
        )

        workflow_connects = 0
        summaries = subject.review_workboard_summaries(account_id)
        assert workflow_connects == 1
        assert set(summaries) == set(snapshots)

        opened = summaries[snapshots[0]]
        assert opened["heading_total"] == 1
        assert opened["heading_pending"] == 1
        assert opened["individual_total"] == 83
        assert opened["individual_pending"] == 50
        assert opened["normal_passages"] == 100
        assert opened["normal_batches"] == 5
        assert opened["blocked_count"] == 20
        assert opened["closure_gap_count"] == 0
        assert opened["source_passage_review_complete"] is False
        assert opened["progress_total"] == 204
        assert opened["progress_done"] == 33
        assert opened["progress_approved"] == 33
        assert opened["progress_rejected"] == 0

        closed = summaries[snapshots[1]]
        assert closed["heading_total"] == 0
        assert closed["heading_pending"] == 0
        assert closed["individual_total"] == 204
        assert closed["individual_pending"] == 0
        assert closed["normal_passages"] == 0
        assert closed["normal_batches"] == 0
        assert closed["blocked_count"] == 0
        assert closed["closure_gap_count"] == 0
        assert closed["source_passage_review_complete"] is True
        assert closed["progress_total"] == 204
        assert closed["progress_done"] == 204
        assert closed["progress_approved"] == 204
    finally:
        store._connect = original_connect  # type: ignore[method-assign]
        store.list_document_objects = original_list  # type: ignore[method-assign]
        with store._connect() as con:
            for snapshot_id in reversed(snapshots):
                con.execute("DELETE FROM workflow.documents WHERE snapshot_id=%s", (snapshot_id,))
            con.execute("DELETE FROM workflow.accounts WHERE account_id=%s", (account_id,))


def test_review_workboard_summary_uses_exact_authorizations_for_four_eyes() -> None:
    config = PostgresCanonicalConfig(dsn=_dsn())
    store = PostgresWorkflowDocumentRuntimeStore(config)
    with store._connect() as con:
        paths = migration_paths(ROOT)
        apply_migrations(con, paths=paths, expected_digest=migration_digest(paths))

    token = uuid.uuid4().hex
    reviewer_a = f"acc-d53a-a-{token[:12]}"
    reviewer_b = f"acc-d53a-b-{token[:12]}"
    snapshot_id = f"snap-d53a-{token[:12]}"
    envelope = _envelope(snapshot_id, token, reviewer_a)
    envelope["named_reviewers"] = [reviewer_a, reviewer_b]

    target = _object(
        snapshot_id,
        1,
        object_type="recommendation",
        validation_status="approved",
        section="Advies",
    )
    target["object_version"] = "2.0"
    target["confirmed_object_type"] = "recommendation"
    target["provenance"] = {"canonical_object_hash": "c" * 64}
    target["risk"] = {
        "level": "high",
        "risk_level": "high",
        "requires_second_review": True,
        "risk_fields": ["contraindication"],
    }
    target["governance"]["second_review"] = {
        "required": True,
        "status": "pending",
        "reviewer": None,
        "review_date": None,
        "snapshot_hash": None,
    }
    document = _object(
        snapshot_id,
        0,
        object_type="document",
        validation_status="approved",
    )

    with store._connect() as con:
        for account_id, username in (
            (reviewer_a, f"d53a-a-{token}"),
            (reviewer_b, f"d53a-b-{token}"),
        ):
            con.execute(
                "INSERT INTO workflow.accounts("
                "account_id,username,display_name,roles,password_salt,password_hash,created_at"
                ") VALUES(%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
                (
                    account_id,
                    username,
                    username,
                    ["reviewer"],
                    "salt",
                    "hash",
                ),
            )

    try:
        store.write_bundle(envelope=envelope, objects=[document, target])
        with store._connect() as con:
            con.execute(
                "INSERT INTO workflow.publish_authorizations("
                "snapshot_id,object_id,object_version,canonical_object_hash,"
                "confirmed_object_type,reviewer_account_id,reviewer_display_name,"
                "decision,valid"
                ") VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    snapshot_id,
                    target["object_id"],
                    target["object_version"],
                    target["provenance"]["canonical_object_hash"],
                    target["confirmed_object_type"],
                    reviewer_a,
                    "Reviewer A",
                    "approve",
                    True,
                ),
            )

        subject_a = _ListReadSubject(store, reviewer_a)
        first = subject_a.review_workboard_summaries(reviewer_a)[snapshot_id]
        assert first["review_duties"] == 1
        assert first["first_review_duties"] == 0
        assert first["second_review_duties"] == 1
        assert first["actionable_review_duties"] == 0
        assert first["waiting_for_reviewer_duties"] == 1
        assert first["actionable_second_review_duties"] == 0

        subject_b = _ListReadSubject(store, reviewer_b)
        other = subject_b.review_workboard_summaries(reviewer_b)[snapshot_id]
        assert other["review_duties"] == 1
        assert other["actionable_review_duties"] == 1
        assert other["waiting_for_reviewer_duties"] == 0
        assert other["actionable_second_review_duties"] == 1

        with store._connect() as con:
            con.execute(
                "INSERT INTO workflow.publish_authorizations("
                "snapshot_id,object_id,object_version,canonical_object_hash,"
                "confirmed_object_type,reviewer_account_id,reviewer_display_name,"
                "decision,valid"
                ") VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    snapshot_id,
                    target["object_id"],
                    target["object_version"],
                    target["provenance"]["canonical_object_hash"],
                    target["confirmed_object_type"],
                    reviewer_b,
                    "Reviewer B",
                    "approve",
                    True,
                ),
            )

        complete = subject_a.review_workboard_summaries(reviewer_a)[snapshot_id]
        assert complete["review_duties"] == 0
        assert complete["second_review_duties"] == 0
        assert complete["actionable_review_duties"] == 0
        # The compatibility mirror deliberately remains pending; bindings win.
        assert target["governance"]["second_review"]["status"] == "pending"
    finally:
        with store._connect() as con:
            con.execute("DELETE FROM workflow.documents WHERE snapshot_id=%s", (snapshot_id,))
            con.execute(
                "DELETE FROM workflow.accounts WHERE account_id=ANY(%s)",
                ([reviewer_a, reviewer_b],),
            )
