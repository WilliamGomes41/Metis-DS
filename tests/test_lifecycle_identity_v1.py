"""Lifecycle identity closure for Repair #215.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflow_postgres_migration_v1 import apply_migrations, migration_digest, migration_paths


ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _dsn() -> str:
    value = os.getenv("METIS_TEST_POSTGRES_DSN", "").strip()
    if not value:
        pytest.skip("METIS_TEST_POSTGRES_DSN not configured")
    return value


def _ids() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"snap-{token[:16]}-{token[16:24]}", token


def _envelope(*, snapshot_id: str, token: str, account_id: str, version: str, ingest_kind: str, replaces: str | None = None) -> dict:
    return {
        "snapshot_id": snapshot_id,
        "source_id": f"src-{token[:16]}",
        "document_id": f"console-richtlijn-identiteit-{version.replace('.', '-')}-{token[:8]}",
        "title": "Lifecycle identity fixture",
        "family": "identiteit",
        "class": "richtlijn",
        "state": "captured_not_published",
        "publication_eligibility": "blocked_pending_review",
        "content_kind": "html",
        "ingest_kind": ingest_kind,
        "version": version,
        "date": "2026-09-16",
        "sha256": token * 2,
        "locator": f"g0-local:sources/private/{token * 2}/fixture.html",
        "immutable_storage_locator": None,
        "live_url": "",
        "uploader_account_id": account_id,
        "named_reviewers": [],
        "replaces_snapshot_id": replaces,
        "object_diff": None,
        "clinical_rereview_required": False,
        "acquired_at": "2026-09-16T08:00:00Z",
        "console_version": "identity-test",
    }


def _object(document_id: str, suffix: str) -> dict:
    return {
        "object_id": f"{document_id}-{suffix}",
        "object_version": "1.0",
        "object_type": "document",
        "content": {"clean_text": suffix},
    }


def _prepare_store() -> tuple[PostgresWorkflowDocumentRuntimeStore, str]:
    dsn = _dsn()
    config = PostgresCanonicalConfig(dsn=dsn)
    store = PostgresWorkflowDocumentRuntimeStore(config)
    with store._connect() as con:
        paths = migration_paths(ROOT)
        apply_migrations(con, paths=paths, expected_digest=migration_digest(paths))
    return store, dsn


def _create_account(store: PostgresWorkflowDocumentRuntimeStore, token: str) -> str:
    account_id = f"acc-{token[:20]}"
    with store._connect() as con:
        con.execute(
            "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
            (account_id, f"identity-{token}", "Identity Test", ["researcher"], "salt", "hash"),
        )
    return account_id


def _delete_fixture(store: PostgresWorkflowDocumentRuntimeStore, snapshot_ids: list[str], account_id: str) -> None:
    with store._connect() as con:
        for snapshot_id in reversed(snapshot_ids):
            con.execute("DELETE FROM workflow.documents WHERE snapshot_id=%s", (snapshot_id,))
        con.execute("DELETE FROM workflow.accounts WHERE account_id=%s", (account_id,))


def test_v1_v2_restart_preserves_explicit_lifecycle_identity() -> None:
    store, dsn = _prepare_store()
    snap1, token1 = _ids()
    snap2, token2 = _ids()
    account_id = _create_account(store, token1)
    created: list[str] = []
    try:
        v1 = _envelope(snapshot_id=snap1, token=token1, account_id=account_id, version="1.0", ingest_kind="new")
        store.write_bundle(envelope=v1, objects=[_object(v1["document_id"], "v1")])
        created.append(snap1)

        v2 = _envelope(
            snapshot_id=snap2,
            token=token2,
            account_id=account_id,
            version="2.0",
            ingest_kind="new_version",
            replaces=snap1,
        )
        store.write_bundle(envelope=v2, objects=[_object(v2["document_id"], "v2")])
        created.append(snap2)

        # Restart/read: a fresh store must project the same durable identities.
        restarted = PostgresWorkflowDocumentRuntimeStore(PostgresCanonicalConfig(dsn=dsn))
        one = restarted.get_envelope(snap1)
        two = restarted.get_envelope(snap2)
        assert one is not None and two is not None

        assert one["document_id"] != two["document_id"]
        assert one["logical_document_id"] == two["logical_document_id"] == f"ldoc-{snap1}"
        assert one["source_snapshot_id"] == snap1
        assert two["source_snapshot_id"] == snap2
        assert one["source_version"] == "1.0"
        assert two["source_version"] == "2.0"
        assert one["working_revision_id"] == f"work-{snap1}"
        assert two["working_revision_id"] == f"work-{snap2}"
        assert one["working_revision_number"] == 1
        assert two["working_revision_number"] == 2

        with restarted._connect() as con:
            rows = con.execute(
                "SELECT snapshot_id,logical_document_id,working_revision_id,working_revision_number "
                "FROM workflow.documents WHERE snapshot_id IN (%s,%s) ORDER BY working_revision_number",
                (snap1, snap2),
            ).fetchall()
        assert [str(row["snapshot_id"]) for row in rows] == [snap1, snap2]
        assert {str(row["logical_document_id"]) for row in rows} == {f"ldoc-{snap1}"}
    finally:
        _delete_fixture(store, created, account_id)


def test_lifecycle_identity_is_immutable_after_capture() -> None:
    store, _ = _prepare_store()
    snap1, token1 = _ids()
    account_id = _create_account(store, token1)
    created: list[str] = []
    try:
        envelope = _envelope(snapshot_id=snap1, token=token1, account_id=account_id, version="1.0", ingest_kind="new")
        store.write_bundle(envelope=envelope, objects=[_object(envelope["document_id"], "v1")])
        created.append(snap1)

        with pytest.raises(Exception, match="lifecycle_identity_immutable"):
            with store._connect() as con:
                con.execute(
                    "UPDATE workflow.documents SET logical_document_id=%s WHERE snapshot_id=%s",
                    ("ldoc-tampered", snap1),
                )
    finally:
        _delete_fixture(store, created, account_id)


def test_concurrent_successors_receive_distinct_working_revision_numbers() -> None:
    store, _ = _prepare_store()
    snap1, token1 = _ids()
    account_id = _create_account(store, token1)
    created: list[str] = []
    try:
        root = _envelope(snapshot_id=snap1, token=token1, account_id=account_id, version="1.0", ingest_kind="new")
        store.write_bundle(envelope=root, objects=[_object(root["document_id"], "root")])
        created.append(snap1)

        successors: list[dict] = []
        for version in ("2.0", "2.1"):
            snapshot_id, token = _ids()
            successors.append(
                _envelope(
                    snapshot_id=snapshot_id,
                    token=token,
                    account_id=account_id,
                    version=version,
                    ingest_kind="new_version",
                    replaces=snap1,
                )
            )
            created.append(snapshot_id)

        barrier = threading.Barrier(2)
        errors: list[BaseException] = []

        def write(envelope: dict) -> None:
            try:
                barrier.wait(timeout=5)
                store.write_bundle(envelope=envelope, objects=[_object(envelope["document_id"], envelope["version"])])
            except BaseException as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        threads = [threading.Thread(target=write, args=(envelope,)) for envelope in successors]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            assert not thread.is_alive()

        assert errors == []
        with store._connect() as con:
            rows = con.execute(
                "SELECT logical_document_id,working_revision_number FROM workflow.documents "
                "WHERE snapshot_id IN (%s,%s,%s) ORDER BY working_revision_number",
                (snap1, successors[0]["snapshot_id"], successors[1]["snapshot_id"]),
            ).fetchall()
        assert [int(row["working_revision_number"]) for row in rows] == [1, 2, 3]
        assert {str(row["logical_document_id"]) for row in rows} == {f"ldoc-{snap1}"}
    finally:
        _delete_fixture(store, created, account_id)


def test_identity_migration_names_source_work_and_release_dimensions_separately() -> None:
    sql = (ROOT / "db" / "migrations" / "008_workflow_lifecycle_identity.sql").read_text(encoding="utf-8")
    assert "logical_document_id" in sql
    assert "snapshot_id` remains the SourceSnapshot identity" in sql
    assert "working_revision_id" in sql
    assert "working_revision_number" in sql
    assert "source_version" in sql
    assert "document_id` remains a source-derived technical identifier" in sql
    assert "publication_releases" not in sql
    assert "publication_registry" not in sql
