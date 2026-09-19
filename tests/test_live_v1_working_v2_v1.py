"""Repair #227: a live immutable v1 may coexist with a mutable successor v2.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.canonical_publication_postgres_v1 import (
    PostgresCanonicalConfig,
    PostgresCanonicalPublicationStore,
)
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_v1 import ConsoleError, review_lane
from src.passage_register_v1 import passage_register_of
from src.review_disposition_v1 import definitive_review_disposition
from src.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflow_documents_cutover_v1 import PostgresWorkflowDurablePublicationConsole
from src.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from src.workflow_postgres_migration_v1 import apply_migrations, migration_digest, migration_paths

ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
TEST_PASSWORD = __name__

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


class MemorySourceStore:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def store_verified(self, *, data: bytes, sha256: str, filename: str) -> str:
        locator = build_g2_locator(sha256=sha256, filename=filename)
        self.blobs[locator] = bytes(data)
        return locator

    def load_verified(self, locator: str) -> bytes:
        try:
            return self.blobs[locator]
        except KeyError as exc:
            raise G2SourceStoreError("canonical_source_missing") from exc


def _config() -> PostgresCanonicalConfig:
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for Repair 5 PostgreSQL evidence")
    config = PostgresCanonicalConfig(dsn=dsn)
    with PostgresConcurrentWorkflowDocumentStore(config)._connect() as con:
        paths = migration_paths(ROOT)
        apply_migrations(con, paths=paths, expected_digest=migration_digest(paths))
        con.execute((ROOT / "db" / "schema_v2.sql").read_text(encoding="utf-8"))
        con.execute(
            (ROOT / "db" / "migrations" / "001_canonical_source_lineage.sql").read_text(
                encoding="utf-8"
            )
        )
    return config


def _console(
    tmp_path: Path,
    config: PostgresCanonicalConfig,
    source: MemorySourceStore,
    *,
    runtime_name: str,
) -> PostgresWorkflowDurablePublicationConsole:
    return PostgresWorkflowDurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / runtime_name,
        immutable_source_store=source,
        canonical_publication_store=PostgresCanonicalPublicationStore(config),
        workflow_identity_store=PostgresWorkflowIdentityStore(config),
        workflow_document_store=PostgresConcurrentWorkflowDocumentStore(config),
    )


def _complete_review(
    console: PostgresWorkflowDurablePublicationConsole,
    *,
    reviewer_id: str,
    snapshot_id: str,
) -> None:
    target = next(
        obj
        for obj in console.snapshot_objects(snapshot_id)
        if obj.get("object_type") == "unclassified"
    )
    console.review_object(
        actor_id=reviewer_id,
        snapshot_id=snapshot_id,
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="explanation",
    )
    for obj in console.snapshot_objects(snapshot_id):
        if obj.get("object_id") == target["object_id"]:
            continue
        if passage_register_of(obj).get("status") != "selected_as_candidate":
            continue
        if (obj.get("governance") or {}).get("validation_status") in {
            "approved",
            "rejected",
            "superseded",
        }:
            continue
        console.review_object(
            actor_id=reviewer_id,
            snapshot_id=snapshot_id,
            object_id=obj["object_id"],
            decision="reject",
            comment="Repair 5 fixture: kandidaat definitief afgehandeld.",
        )
    for obj in console.snapshot_objects(snapshot_id):
        if obj.get("object_type") == "document" or review_lane(obj) == "fast":
            continue
        if definitive_review_disposition(obj)["final"]:
            continue
        console.review_object(
            actor_id=reviewer_id,
            snapshot_id=snapshot_id,
            object_id=obj["object_id"],
            decision="reject",
            suitability="ja",
            eindoordeel="afwijzen",
            comment="Repair 5 fixture: bronpassage definitief afgehandeld.",
        )


def _cleanup(
    config: PostgresCanonicalConfig,
    *,
    snapshot_ids: list[str],
    account_ids: list[str],
    release_ids: list[str],
) -> None:
    store = PostgresConcurrentWorkflowDocumentStore(config)
    with store._connect() as con:
        canonical_rows = []
        if snapshot_ids:
            canonical_rows = con.execute(
                "SELECT object_id,object_version FROM canonical_object_sources "
                "WHERE snapshot_id = ANY(%s)",
                (snapshot_ids,),
            ).fetchall()
        canonical_object_ids = sorted({str(row["object_id"]) for row in canonical_rows})

        if release_ids:
            con.execute("DELETE FROM publication_registry WHERE release_id = ANY(%s)", (release_ids,))
            con.execute("DELETE FROM publication_release_items WHERE release_id = ANY(%s)", (release_ids,))
            con.execute(
                "DELETE FROM audit_events WHERE entity_id = ANY(%s) OR details->>'release_id' = ANY(%s)",
                (release_ids, release_ids),
            )
            con.execute("DELETE FROM publication_releases WHERE release_id = ANY(%s)", (release_ids,))
        if snapshot_ids:
            con.execute(
                "DELETE FROM audit_events WHERE details->>'snapshot_id' = ANY(%s)",
                (snapshot_ids,),
            )
            con.execute(
                "DELETE FROM canonical_object_sources WHERE snapshot_id = ANY(%s)",
                (snapshot_ids,),
            )
        if canonical_object_ids:
            con.execute(
                "DELETE FROM canonical_object_versions AS cov "
                "WHERE cov.object_id = ANY(%s) "
                "AND NOT EXISTS ("
                "SELECT 1 FROM canonical_object_sources AS cos "
                "WHERE cos.object_id=cov.object_id AND cos.object_version=cov.object_version"
                ") "
                "AND NOT EXISTS ("
                "SELECT 1 FROM publication_release_items AS pri "
                "WHERE pri.object_id=cov.object_id AND pri.object_version=cov.object_version"
                ")",
                (canonical_object_ids,),
            )
        for snapshot_id in reversed(snapshot_ids):
            con.execute("DELETE FROM workflow.documents WHERE snapshot_id=%s", (snapshot_id,))
            con.execute("DELETE FROM source_snapshots WHERE snapshot_id=%s", (snapshot_id,))
        for account_id in account_ids:
            con.execute("DELETE FROM workflow.accounts WHERE account_id=%s", (account_id,))


def test_published_v1_stays_live_while_successor_v2_is_mutable_and_unreleased(
    tmp_path: Path,
) -> None:
    config = _config()
    source = MemorySourceStore()
    console = _console(tmp_path, config, source, runtime_name="repair5-a")
    snapshots: list[str] = []
    releases: list[str] = []
    accounts: list[str] = []
    try:
        researcher = console.create_account(
            username=f"repair5.researcher.{tmp_path.name}",
            password=TEST_PASSWORD,
            roles=("researcher", "reviewer"),
        )
        reviewer = console.create_account(
            username=f"repair5.reviewer.{tmp_path.name}",
            password=TEST_PASSWORD,
            roles=("reviewer",),
        )
        publisher = console.create_account(
            username=f"repair5.publisher.{tmp_path.name}",
            password=TEST_PASSWORD,
            roles=("publisher",),
        )
        accounts.extend(
            [researcher["account_id"], reviewer["account_id"], publisher["account_id"]]
        )

        v1 = console.ingest(
            actor_id=researcher["account_id"],
            filename="repair5-v1.html",
            data=HTML_FIXTURE.read_bytes(),
            content_type="text/html",
            ingest_kind="new",
            title="Repair 5 lifecycle fixture",
            version="1.0",
            date="2026-09-16",
            live_url="https://example.test/repair5",
            class_="richtlijn",
            family="repair5",
            named_reviewers=[researcher["account_id"], reviewer["account_id"]],
        )
        snap1 = str(v1["snapshot_id"])
        snapshots.append(snap1)
        _complete_review(console, reviewer_id=reviewer["account_id"], snapshot_id=snap1)
        published = console.publish(actor_id=publisher["account_id"], snapshot_id=snap1)
        assert published["status"] == "PASS"
        releases.append(str(published["release_id"]))

        v1_before = console._envelope(snap1)
        v1_objects_before = console.snapshot_objects(snap1)
        assert console.document_lifecycle_status(snap1) == {
            "workflow_status": "closed",
            "release_status": "published",
            "serving_status": "active",
            "presentation_status": "published",
        }

        v2_bytes = HTML_FIXTURE.read_bytes() + b"\n<!-- repair-5-source-v2 -->\n"
        v2 = console.ingest(
            actor_id=researcher["account_id"],
            filename="repair5-v2.html",
            data=v2_bytes,
            content_type="text/html",
            ingest_kind="new_version",
            replaces_snapshot_id=snap1,
            title="Repair 5 lifecycle fixture",
            version="2.0",
            date="2026-09-16",
            live_url="https://example.test/repair5",
            class_="richtlijn",
            family="repair5",
            named_reviewers=[researcher["account_id"], reviewer["account_id"]],
        )
        snap2 = str(v2["snapshot_id"])
        snapshots.append(snap2)

        one = console._envelope(snap1)
        two = console._envelope(snap2)
        assert one["logical_document_id"] == two["logical_document_id"]
        assert one["source_snapshot_id"] == snap1
        assert two["source_snapshot_id"] == snap2
        assert one["working_revision_id"] != two["working_revision_id"]
        assert one["working_revision_number"] == 1
        assert two["working_revision_number"] == 2
        assert two["replaces_snapshot_id"] == snap1

        assert console.document_lifecycle_status(snap1) == {
            "workflow_status": "closed",
            "release_status": "published",
            "serving_status": "active",
            "presentation_status": "published",
        }
        v2_status = console.document_lifecycle_status(snap2)
        assert v2_status["workflow_status"] in {"processing", "in_review", "blocked"}
        assert v2_status["release_status"] == "none"
        assert v2_status["serving_status"] == "inactive"

        target_v2 = next(
            obj for obj in console.snapshot_objects(snap2) if obj.get("object_type") == "unclassified"
        )
        console.review_object(
            actor_id=reviewer["account_id"],
            snapshot_id=snap2,
            object_id=target_v2["object_id"],
            decision="approve",
            confirmed_object_type="explanation",
        )
        with pytest.raises(ConsoleError, match="published_working_revision_immutable"):
            target_v1 = next(
                obj
                for obj in console.snapshot_objects(snap1)
                if obj.get("object_type") != "document"
            )
            console.review_object(
                actor_id=reviewer["account_id"],
                snapshot_id=snap1,
                object_id=target_v1["object_id"],
                decision="reject",
                comment="must stay blocked",
            )

        assert console._envelope(snap1) == v1_before
        assert console.snapshot_objects(snap1) == v1_objects_before
        active = PostgresCanonicalPublicationStore(config).active_publication_rows()
        assert active
        assert {str(row["snapshot_id"]) for row in active} == {snap1}

        restarted = _console(tmp_path, config, source, runtime_name="repair5-b")
        restarted_one = restarted._envelope(snap1)
        restarted_two = restarted._envelope(snap2)
        assert restarted_one["logical_document_id"] == restarted_two["logical_document_id"]
        assert restarted_one["working_revision_number"] == 1
        assert restarted_two["working_revision_number"] == 2
        assert restarted.document_lifecycle_status(snap1)["serving_status"] == "active"
        restarted_v2 = restarted.document_lifecycle_status(snap2)
        assert restarted_v2["release_status"] == "none"
        assert restarted_v2["serving_status"] == "inactive"
        assert {
            str(row["snapshot_id"])
            for row in PostgresCanonicalPublicationStore(config).active_publication_rows()
        } == {snap1}
    finally:
        _cleanup(
            config,
            snapshot_ids=snapshots,
            account_ids=accounts,
            release_ids=releases,
        )



def test_unpublished_delete_removes_postgres_authority_and_stays_deleted_after_restart(
    tmp_path: Path,
) -> None:
    config = _config()
    source = MemorySourceStore()
    console = _console(tmp_path, config, source, runtime_name="delete-pg-a")
    snapshots: list[str] = []
    accounts: list[str] = []
    try:
        researcher = console.create_account(
            username=f"delete.pg.researcher.{tmp_path.name}",
            password=TEST_PASSWORD,
            roles=("researcher", "reviewer"),
        )
        reviewer = console.create_account(
            username=f"delete.pg.reviewer.{tmp_path.name}",
            password=TEST_PASSWORD,
            roles=("reviewer",),
        )
        accounts.extend([researcher["account_id"], reviewer["account_id"]])

        receipt = console.ingest(
            actor_id=researcher["account_id"],
            filename="delete-pg.html",
            data=HTML_FIXTURE.read_bytes(),
            content_type="text/html",
            ingest_kind="new",
            title="Postgres delete fixture",
            version="1.0",
            date="2026-09-19",
            live_url="https://example.test/delete-pg",
            class_="richtlijn",
            family="delete-pg",
            named_reviewers=[researcher["account_id"], reviewer["account_id"]],
        )
        snapshot_id = str(receipt["snapshot_id"])
        snapshots.append(snapshot_id)
        assert console.workflow_document_store.get_envelope(snapshot_id) is not None

        deleted = console.delete_unpublished_snapshot(
            actor_id=researcher["account_id"],
            snapshot_id=snapshot_id,
            confirmed=True,
            confirm_title="Postgres delete fixture",
        )

        assert deleted["deleted"] is True
        assert console.workflow_document_store.get_envelope(snapshot_id) is None
        assert snapshot_id not in {row["snapshot_id"] for row in console.list_envelopes()}

        restarted = _console(tmp_path, config, source, runtime_name="delete-pg-b")
        assert restarted.workflow_document_store.get_envelope(snapshot_id) is None
        assert snapshot_id not in {row["snapshot_id"] for row in restarted.list_envelopes()}
    finally:
        _cleanup(
            config,
            snapshot_ids=snapshots,
            account_ids=accounts,
            release_ids=[],
        )
