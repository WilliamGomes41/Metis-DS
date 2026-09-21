"""Durable Topic identity regressions for workflow Onderwerp.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale durable recovery replay
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.topic_identity_v1 import topic_id_for_key, topic_identity_key
from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflow_documents_postgres_v1 import (
    PostgresWorkflowDocumentStore,
    WorkflowDocumentStoreError,
)
from src.workflow_postgres_migration_v1 import migration_paths


ROOT = Path(__file__).resolve().parents[1]


def _install_schema(dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute("DROP SCHEMA IF EXISTS workflow CASCADE")
        for path in migration_paths(ROOT):
            con.execute(path.read_text(encoding="utf-8"))


@pytest.fixture()
def topic_postgres() -> PostgresCanonicalConfig:
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for Topic identity evidence")
    _install_schema(dsn)
    config = PostgresCanonicalConfig(dsn=dsn)
    yield config
    _install_schema(dsn)


def _seed_accounts(config: PostgresCanonicalConfig) -> None:
    import psycopg

    with psycopg.connect(config.dsn, autocommit=True) as con:
        con.execute(
            "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            ("acc-uploader", "uploader", "Uploader", ["researcher"], "salt", "hash", "2026-09-21T09:00:00Z"),
        )
        con.execute(
            "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            ("acc-reviewer", "reviewer", "Reviewer", ["reviewer"], "salt", "hash", "2026-09-21T09:00:00Z"),
        )


def _envelope(snapshot_id: str, *, family: str, suffix: str) -> dict:
    return {
        "snapshot_id": snapshot_id,
        "source_id": f"source-{suffix}",
        "document_id": f"doc-{suffix}",
        "title": f"Document {suffix}",
        "family": family,
        "class": "richtlijn",
        "state": "captured_not_published",
        "publication_eligibility": "eligible_for_transform_and_review",
        "content_kind": "html",
        "ingest_kind": "new",
        "version": "1.0",
        "date": "2026-09-21",
        "sha256": suffix[0] * 64,
        "locator": f"source://{suffix}",
        "immutable_storage_locator": f"azure://{suffix}",
        "live_url": "",
        "uploader_account_id": "acc-uploader",
        "named_reviewers": ["acc-reviewer"],
        "replaces_snapshot_id": None,
        "object_diff": None,
        "clinical_rereview_required": False,
        "acquired_at": "2026-09-21T09:00:00Z",
        "console_version": "topic-test",
    }


def _objects(suffix: str) -> list[dict]:
    return [{"object_id": f"obj-{suffix}", "object_version": "1.0", "text": suffix}]


def test_topic_identity_is_deterministic_for_case_and_whitespace() -> None:
    key = topic_identity_key("Delier")
    assert key == topic_identity_key("  DELIER  ")
    assert topic_id_for_key(key) == topic_id_for_key(topic_identity_key("dElIeR"))


def test_concurrent_first_create_claims_one_durable_topic(topic_postgres: PostgresCanonicalConfig) -> None:
    import psycopg

    _seed_accounts(topic_postgres)
    first = PostgresWorkflowDocumentRuntimeStore(topic_postgres)
    second = PostgresWorkflowDocumentRuntimeStore(topic_postgres)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def write(store: PostgresWorkflowDocumentRuntimeStore, envelope: dict, objects: list[dict]) -> None:
        try:
            barrier.wait(timeout=5)
            store.write_bundle(envelope=envelope, objects=objects, expected_revision="")
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [
        threading.Thread(
            target=write,
            args=(first, _envelope("snap-a", family="Delier", suffix="a"), _objects("a")),
        ),
        threading.Thread(
            target=write,
            args=(second, _envelope("snap-b", family="  DELIER  ", suffix="b"), _objects("b")),
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive()

    assert errors == []
    expected_topic_id = topic_id_for_key(topic_identity_key("Delier"))
    with psycopg.connect(topic_postgres.dsn) as con:
        topics = con.execute(
            "SELECT topic_id,identity_key,display_name FROM workflow.topics ORDER BY identity_key"
        ).fetchall()
        documents = con.execute(
            "SELECT snapshot_id,topic_id,source_sha256 FROM workflow.documents ORDER BY snapshot_id"
        ).fetchall()

    assert len(topics) == 1
    assert str(topics[0][0]) == expected_topic_id
    assert {str(row[1]) for row in documents} == {expected_topic_id}
    assert {str(row[2]) for row in documents} == {"a" * 64, "b" * 64}

    restarted = PostgresWorkflowDocumentRuntimeStore(topic_postgres)
    restarted.verify_cutover_schema()
    envelopes = restarted.list_envelopes()
    assert {row["topic_id"] for row in envelopes} == {expected_topic_id}
    assert len({row["family"] for row in envelopes}) == 1


def test_failed_document_transaction_rolls_back_new_topic(topic_postgres: PostgresCanonicalConfig) -> None:
    import psycopg

    _seed_accounts(topic_postgres)
    store = PostgresWorkflowDocumentRuntimeStore(topic_postgres)
    envelope = _envelope("snap-fail", family="Delier", suffix="f")
    envelope["named_reviewers"] = ["missing-reviewer"]

    with pytest.raises(WorkflowDocumentStoreError, match="workflow_document_bundle_write_failed"):
        store.write_bundle(envelope=envelope, objects=_objects("f"), expected_revision="")

    with psycopg.connect(topic_postgres.dsn) as con:
        assert con.execute("SELECT COUNT(*) FROM workflow.topics").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM workflow.documents").fetchone()[0] == 0


def test_backfill_merges_legacy_variants_without_rewriting_family(
    topic_postgres: PostgresCanonicalConfig,
) -> None:
    import psycopg

    _seed_accounts(topic_postgres)
    rows = [
        ("snap-a", "Delier", "a"),
        ("snap-b", "  DELIER  ", "b"),
    ]
    with psycopg.connect(topic_postgres.dsn, autocommit=True) as con:
        for snapshot_id, family, suffix in rows:
            envelope = _envelope(snapshot_id, family=family, suffix=suffix)
            con.execute(
                """INSERT INTO workflow.documents(
                    snapshot_id,source_id,document_id,title,family,class,state,publication_eligibility,
                    content_kind,ingest_kind,source_version,source_date,source_sha256,source_locator,
                    immutable_storage_locator,live_url,uploader_account_id,replaces_snapshot_id,object_diff,
                    clinical_rereview_required,acquired_at,console_version,envelope_payload
                ) VALUES(
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,%s,%s,%s,%s::jsonb
                )""",
                (
                    snapshot_id,
                    envelope["source_id"],
                    envelope["document_id"],
                    envelope["title"],
                    family,
                    envelope["class"],
                    envelope["state"],
                    envelope["publication_eligibility"],
                    envelope["content_kind"],
                    envelope["ingest_kind"],
                    envelope["version"],
                    envelope["date"],
                    envelope["sha256"],
                    envelope["locator"],
                    envelope["immutable_storage_locator"],
                    envelope["live_url"],
                    envelope["uploader_account_id"],
                    envelope["clinical_rereview_required"],
                    envelope["acquired_at"],
                    envelope["console_version"],
                    json.dumps(envelope, sort_keys=True),
                ),
            )
            con.execute(
                "INSERT INTO workflow.document_reviewers(snapshot_id,account_id) VALUES(%s,%s)",
                (snapshot_id, "acc-reviewer"),
            )

    runtime = PostgresWorkflowDocumentRuntimeStore(topic_postgres)
    with pytest.raises(WorkflowDocumentStoreError, match="workflow_topic_identity_not_prepared"):
        runtime.verify_cutover_schema()

    store = PostgresWorkflowDocumentStore(topic_postgres)
    result = store.backfill_topic_identity()
    assert result["documents"] == 2
    assert result["linked"] == 2
    assert result["topics"] == 1

    with psycopg.connect(topic_postgres.dsn) as con:
        docs = con.execute(
            "SELECT snapshot_id,family,topic_id FROM workflow.documents ORDER BY snapshot_id"
        ).fetchall()
        topics = con.execute("SELECT topic_id FROM workflow.topics").fetchall()
    assert [str(row[1]) for row in docs] == ["Delier", "  DELIER  "]
    assert len(topics) == 1
    assert len({str(row[2]) for row in docs}) == 1

    runtime.verify_cutover_schema()
    canonical = runtime.list_envelopes()
    assert len({row["family"] for row in canonical}) == 1
    assert len({row["topic_id"] for row in canonical}) == 1

    second = store.backfill_topic_identity()
    assert second["linked"] == 0
    assert second["already_linked"] == 2
