"""VSA Slice 6: durable Publish Document transition.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable canonical authority concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, review_lane
from src.passage_register_v1 import passage_register_of
from src.publish_readiness_ui_v1 import install_publish_readiness_ui
from src.review_disposition_v1 import definitive_review_disposition
from src.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflow_documents_cutover_v1 import PostgresWorkflowDurablePublicationConsole
from src.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from src.workflow_remaining_cutover_v1 import (
    PostgresCompleteWorkflowDurablePublicationConsole,
    _PostgresRemainingWorkflowMixin,
)
from src.workflow_review_cutover_v1 import PostgresReviewWorkflowDurablePublicationConsole

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

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _migration_statements(text: str) -> list[str]:
    sql = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


@pytest.fixture()
def workflow_postgres() -> PostgresCanonicalConfig:
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for Slice 6 PostgreSQL evidence")

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


class MemoryCanonicalStore:
    """Small canonical authority fake; workflow persistence is real PostgreSQL."""

    def __init__(self) -> None:
        self.releases: dict[str, dict[str, Any]] = {}
        self.persist_calls = 0

    def persist_published_release(self, **payload: Any) -> None:
        self.persist_calls += 1
        release_id = str(payload["release_id"])
        self.releases[release_id] = json.loads(
            json.dumps(payload, default=str, sort_keys=True)
        )

    def release_for_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        matches = [row for row in self.releases.values() if row["snapshot_id"] == snapshot_id]
        if not matches:
            return None
        payload = sorted(matches, key=lambda row: row["published_at"])[-1]
        return {
            "release_id": payload["release_id"],
            "release_version": payload["release_version"],
            "release_owner": payload["release_owner"],
            "published_at": payload["published_at"],
            "snapshot_id": payload["snapshot_id"],
            "source_sha256": payload["source_sha256"],
            "source_locator": payload["source_locator"],
            "objects": [
                {
                    "object_id": obj["object_id"],
                    "object_version": obj["object_version"],
                    "canonical_object_hash": (obj.get("provenance") or {}).get(
                        "canonical_object_hash"
                    ),
                    "content_hash": (obj.get("provenance") or {}).get("content_hash"),
                    "confirmed_object_type": obj.get("confirmed_object_type"),
                }
                for obj in payload["objects"]
            ],
        }

    def active_publication_rows(self) -> list[dict[str, Any]]:
        latest_by_object: dict[str, tuple[str, dict[str, Any], dict[str, Any]]] = {}
        for payload in self.releases.values():
            for obj in payload["objects"]:
                object_id = str(obj["object_id"])
                prior = latest_by_object.get(object_id)
                if prior is None or prior[0] < payload["published_at"]:
                    latest_by_object[object_id] = (payload["published_at"], payload, obj)
        return [
            {
                "knowledge_object": deepcopy(obj),
                "publication": {
                    "release_id": payload["release_id"],
                    "release_version": payload["release_version"],
                    "published_at": payload["published_at"],
                },
                "snapshot_id": payload["snapshot_id"],
                "release_owner": payload["release_owner"],
            }
            for _stamp, payload, obj in sorted(
                latest_by_object.values(), key=lambda item: item[2]["object_id"]
            )
        ]


def _stores(
    config: PostgresCanonicalConfig,
) -> tuple[PostgresWorkflowIdentityStore, PostgresConcurrentWorkflowDocumentStore]:
    return (
        PostgresWorkflowIdentityStore(config),
        PostgresConcurrentWorkflowDocumentStore(config),
    )


def _console(
    tmp_path: Path,
    config: PostgresCanonicalConfig,
    durable: MemoryCanonicalStore,
    source: MemorySourceStore,
    *,
    runtime_name: str,
) -> PostgresWorkflowDurablePublicationConsole:
    identity, documents = _stores(config)
    return PostgresWorkflowDurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / runtime_name,
        immutable_source_store=source,
        canonical_publication_store=durable,  # type: ignore[arg-type]
        workflow_identity_store=identity,
        workflow_document_store=documents,
    )


def _ready_console(
    tmp_path: Path,
    config: PostgresCanonicalConfig,
    durable: MemoryCanonicalStore,
    source: MemorySourceStore,
) -> tuple[PostgresWorkflowDurablePublicationConsole, dict[str, dict], dict]:
    console = _console(
        tmp_path,
        config,
        durable,
        source,
        runtime_name="runtime-a",
    )
    accounts = {
        "researcher": console.create_account(
            username="researcher.anne",
            password=TEST_PASSWORD,
            roles=("researcher", "reviewer"),
        ),
        "reviewer": console.create_account(
            username="reviewer.bert",
            password=TEST_PASSWORD,
            roles=("reviewer",),
        ),
        "publisher": console.create_account(
            username="publisher.carla",
            password=TEST_PASSWORD,
            roles=("publisher",),
        ),
    }
    receipt = console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Continentie fixture",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/continentie",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )
    snapshot_id = receipt["snapshot_id"]
    target = next(
        obj
        for obj in console.snapshot_objects(snapshot_id)
        if obj.get("object_type") == "unclassified"
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
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
        }:
            continue
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=snapshot_id,
            object_id=obj["object_id"],
            decision="reject",
            comment="Testfixture: kandidaat definitief afgehandeld.",
        )
    for obj in console.snapshot_objects(snapshot_id):
        if obj.get("object_type") == "document" or review_lane(obj) == "fast":
            continue
        if definitive_review_disposition(obj)["final"]:
            continue
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=snapshot_id,
            object_id=obj["object_id"],
            decision="reject",
            suitability="ja",
            eindoordeel="afwijzen",
            comment="Testfixture: bronpassage definitief afgehandeld.",
        )
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=snapshot_id,
    )
    assert considered["publication_ready"] is True
    return console, accounts, receipt


def test_publish_persists_published_envelope_in_postgres_document_authority_and_ui(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    durable = MemoryCanonicalStore()
    source = MemorySourceStore()
    console, accounts, receipt = _ready_console(tmp_path, workflow_postgres, durable, source)
    snapshot_id = receipt["snapshot_id"]

    result = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
    )

    assert result["status"] == "PASS"
    assert durable.persist_calls == 1
    stored = console.workflow_document_store.get_envelope(snapshot_id)
    assert stored is not None
    assert stored["state"] == "published"
    assert stored["release_id"] == result["release_id"]

    app = create_console_app(console)
    install_publish_readiness_ui(app, console)
    client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    login = client.post(
        "/login",
        data={"username": "publisher.carla", "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert login.status_code == 303
    page = client.get("/publish")
    assert page.status_code == 200
    assert 'data-publication-state="published"' in page.text
    assert "data-publish-form" not in page.text


def test_restart_reads_published_state_from_postgres_document_authority(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    durable = MemoryCanonicalStore()
    source = MemorySourceStore()
    console, accounts, receipt = _ready_console(tmp_path, workflow_postgres, durable, source)
    snapshot_id = receipt["snapshot_id"]
    result = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
    )
    assert result["status"] == "PASS"

    restarted = _console(
        tmp_path,
        workflow_postgres,
        durable,
        source,
        runtime_name="runtime-b",
    )

    envelope = restarted._envelope(snapshot_id)
    assert envelope["state"] == "published"
    assert envelope["release_id"] == result["release_id"]
    assert restarted.snapshot_is_published(snapshot_id) is True


def test_postcanonical_workflow_failure_retries_same_release_and_converges(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    durable = MemoryCanonicalStore()
    source = MemorySourceStore()
    console, accounts, receipt = _ready_console(tmp_path, workflow_postgres, durable, source)
    snapshot_id = receipt["snapshot_id"]
    documents = console.workflow_document_store
    real_write = documents.write_bundle
    failed = {"value": False}

    def fail_first_published_write(**kwargs: Any) -> str:
        envelope = kwargs["envelope"]
        if envelope.get("state") == "published" and not failed["value"]:
            failed["value"] = True
            raise RuntimeError("simulated workflow envelope outage")
        return real_write(**kwargs)

    monkeypatch.setattr(documents, "write_bundle", fail_first_published_write)

    with pytest.raises(ConsoleError) as caught:
        console.publish(
            actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
        )
    assert caught.value.code == "durable_publication_local_copy_failed"
    assert durable.persist_calls == 1
    assert len(durable.releases) == 1
    persisted_after_failure = real_write.__self__.get_envelope(snapshot_id)
    assert persisted_after_failure is not None
    assert persisted_after_failure["state"] == "captured_not_published"

    retry = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
    )

    assert retry["status"] == "PASS"
    assert retry["local_projection"] == "reconciled"
    assert durable.persist_calls == 1
    assert len(durable.releases) == 1
    assert retry["release_id"] == next(iter(durable.releases))
    persisted = documents.get_envelope(snapshot_id)
    assert persisted is not None
    assert persisted["state"] == "published"
    assert persisted["release_id"] == retry["release_id"]


def test_all_postgres_document_workflow_modes_share_one_publication_followup() -> None:
    document_impl = PostgresWorkflowDurablePublicationConsole._apply_local_release_copy
    assert PostgresReviewWorkflowDurablePublicationConsole._apply_local_release_copy is document_impl
    assert PostgresCompleteWorkflowDurablePublicationConsole._apply_local_release_copy is document_impl
    assert "_apply_local_release_copy" not in _PostgresRemainingWorkflowMixin.__dict__


def test_reviewer_cannot_reconcile_existing_release_via_publish_route(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    durable = MemoryCanonicalStore()
    source = MemorySourceStore()
    console, accounts, receipt = _ready_console(tmp_path, workflow_postgres, durable, source)
    snapshot_id = str(receipt["snapshot_id"])

    published = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
    )
    assert published["status"] == "PASS"

    projection_path = console.runtime / "published_projection.jsonl"
    manifest_path = (
        console.runtime / "release_manifests" / f'{published["release_id"]}.json'
    )
    ledger_path = console.runtime / "review_ledger.jsonl"
    before = {
        "envelope": deepcopy(console.workflow_document_store.get_envelope(snapshot_id)),
        "projection": projection_path.read_bytes(),
        "manifest": manifest_path.read_bytes(),
        "ledger": ledger_path.read_bytes(),
        "persist_calls": durable.persist_calls,
        "release_count": len(durable.releases),
    }

    calls = {"sync": 0, "apply": 0}
    real_sync = console._sync_snapshot_from_authority
    real_apply = console._apply_local_release_copy

    def count_sync(target_snapshot_id: str) -> dict[str, Any] | None:
        calls["sync"] += 1
        return real_sync(target_snapshot_id)

    def count_apply(release: dict[str, Any], projection: list[dict[str, Any]]) -> None:
        calls["apply"] += 1
        real_apply(release, projection)

    monkeypatch.setattr(console, "_sync_snapshot_from_authority", count_sync)
    monkeypatch.setattr(console, "_apply_local_release_copy", count_apply)

    app = create_console_app(console)
    client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    login = client.post(
        "/login",
        data={"username": "reviewer.bert", "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert login.status_code == 303

    denied = client.post(
        "/publish",
        data={"snapshot_id": snapshot_id, "publish_confirmed": "yes"},
        follow_redirects=False,
    )

    assert denied.status_code == 403
    assert "publisher_role_required" in denied.text
    assert calls == {"sync": 0, "apply": 0}
    assert durable.persist_calls == before["persist_calls"]
    assert len(durable.releases) == before["release_count"]
    assert console.workflow_document_store.get_envelope(snapshot_id) == before["envelope"]
    assert projection_path.read_bytes() == before["projection"]
    assert manifest_path.read_bytes() == before["manifest"]
    assert ledger_path.read_bytes() == before["ledger"]
