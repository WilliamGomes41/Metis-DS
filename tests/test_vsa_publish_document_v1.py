"""VSA Slice 6: durable Publish Document transition.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable canonical authority concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig, PostgresCanonicalPublicationStore
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_v1 import ConsoleError, review_lane
from src.vorming.passage_register_v1 import passage_register_of
from src.review.review_disposition_v1 import definitive_review_disposition
from src.workflows.workflow_documents_cutover_v1 import _PostgresWorkflowDocumentsMixin
from src.workflows.workflow_remaining_cutover_v1 import (
    PostgresCompleteWorkflowDurablePublicationConsole,
    _PostgresRemainingWorkflowMixin,
)
from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowDurablePublicationConsole
from tests.complete_workflow_support import complete_console
from tests.production_support import application_for

ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
TEST_PASSWORD = __name__
MIGRATIONS = (
    "002_workflow_schema.sql",
    "003_workflow_document_envelope_payload.sql",
    "004_workflow_review_authority.sql",
    "005_workflow_remaining_authority.sql",
    "006_workflow_authorization_payload.sql",
    "011_workflow_audit_retention.sql",
    "016_workflow_topic_identity.sql",
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
def workflow_postgres(complete_postgres) -> PostgresCanonicalConfig:
    """Use the session schema template and an owned database per test."""
    return complete_postgres


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


def canonical_store(config):
    """Observe persist calls on the actual PostgreSQL canonical adapter."""
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    store = PostgresCanonicalPublicationStore(config)
    store.persist_calls = 0
    persist = store.persist_published_release
    def counted(**payload):
        store.persist_calls += 1
        return persist(**payload)
    store.persist_published_release = counted
    return store


def release_ids(store):
    with store._connect() as connection:
        return [row['release_id'] for row in connection.execute('SELECT release_id FROM publication_releases ORDER BY release_id')]


def _console(
    tmp_path: Path,
    config: PostgresCanonicalConfig,
    durable: PostgresCanonicalPublicationStore,
    source: MemorySourceStore,
    *,
    runtime_name: str,
) -> FastBadgePostgresCompleteWorkflowDurablePublicationConsole:
    return complete_console(
        tmp_path, config, source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / runtime_name, immutable_source_store=source,
        canonical_publication_store=durable,
    )


def _ready_console(
    tmp_path: Path,
    config: PostgresCanonicalConfig,
    durable: PostgresCanonicalPublicationStore,
    source: MemorySourceStore,
) -> tuple[FastBadgePostgresCompleteWorkflowDurablePublicationConsole, dict[str, dict], dict]:
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
    from tests.semantic_fixture_support import bind_fixture_selections
    bind_fixture_selections(console)
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


class _CountingConnection:
    def __init__(self, connection: Any, counter: dict[str, int]) -> None:
        self.connection = connection
        self.counter = counter
        self.entered: Any = connection

    def __enter__(self) -> "_CountingConnection":
        self.entered = self.connection.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        return self.connection.__exit__(*args)

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        self.counter["queries"] += 1
        return self.entered.execute(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.entered, name)


def test_publication_readiness_has_bounded_postgres_query_count(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    durable = canonical_store(workflow_postgres)
    source = MemorySourceStore()
    console, _accounts, receipt = _ready_console(
        tmp_path, workflow_postgres, durable, source
    )
    store = console.workflow_document_store
    original_connect = store._connect
    counter = {"queries": 0}

    def counted_connect() -> _CountingConnection:
        return _CountingConnection(original_connect(), counter)

    store._connect = counted_connect  # type: ignore[method-assign]
    try:
        readiness = console.publication_readiness(receipt["snapshot_id"])
    finally:
        store._connect = original_connect  # type: ignore[method-assign]

    assert readiness["publication_ready"] is True
    assert 0 < counter["queries"] <= 5


def test_publish_persists_published_envelope_in_postgres_document_authority_and_ui(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    durable = canonical_store(workflow_postgres)
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

    app = application_for(console)
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



def test_published_overview_never_loads_canonical_object_payloads(tmp_path, workflow_postgres, monkeypatch):
    durable = canonical_store(workflow_postgres)
    console, accounts, receipt = _ready_console(tmp_path, workflow_postgres, durable, MemorySourceStore())
    assert console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"])["status"] == "PASS"
    def full_payload_forbidden(*args, **kwargs):
        raise AssertionError("Overview loaded canonical object payloads")
    monkeypatch.setattr(durable, "release_for_snapshot", full_payload_forbidden)
    client = TestClient(application_for(console), base_url="https://testserver")
    assert client.post('/login', data={'username': 'publisher.carla', 'password': TEST_PASSWORD}, follow_redirects=False).status_code == 303
    page = client.get('/publish')
    assert page.status_code == 200 and 'data-publication-state="published"' in page.text
    assert 'data-publish-form' not in page.text


def test_restart_reads_published_state_from_postgres_document_authority(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
) -> None:
    durable = canonical_store(workflow_postgres)
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
    durable = canonical_store(workflow_postgres)
    source = MemorySourceStore()
    console, accounts, receipt = _ready_console(tmp_path, workflow_postgres, durable, source)
    snapshot_id = receipt["snapshot_id"]
    # Compose B before publication: startup after the crash is itself allowed
    # to reconcile, which would skip the still-unreconciled ingress window.
    restarted = _console(tmp_path, workflow_postgres, durable, source, runtime_name="runtime-b")
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
    assert len(release_ids(durable)) == 1
    persisted_after_failure = real_write.__self__.get_envelope(snapshot_id)
    assert persisted_after_failure is not None
    assert persisted_after_failure["state"] == "captured_not_published"

    # MET-43: an independent ordinary Review ingress must see canonical sealing
    # during this crash window, even though workflow publication is still old.
    before_objects = restarted.snapshot_objects(snapshot_id)
    before_bindings = restarted.object_review_bindings(snapshot_id)
    before_events = restarted.workflow_review_store.read_events()
    before_revision = restarted.objects_revision(snapshot_id)
    target = next(obj for obj in before_objects if obj.get("object_type") != "document")
    with pytest.raises(ConsoleError, match="published_working_revision_immutable"):
        restarted.review_object(actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=snapshot_id, object_id=target["object_id"], decision="later")
    assert restarted.snapshot_objects(snapshot_id) == before_objects
    assert restarted.object_review_bindings(snapshot_id) == before_bindings
    assert restarted.workflow_review_store.read_events() == before_events
    assert restarted.objects_revision(snapshot_id) == before_revision
    assert documents.get_envelope(snapshot_id) == persisted_after_failure

    retry = restarted.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
    )

    assert retry["status"] == "PASS"
    assert retry["local_projection"] == "reconciled"
    assert durable.persist_calls == 1
    assert len(release_ids(durable)) == 1
    assert retry["release_id"] == release_ids(durable)[0]
    persisted = documents.get_envelope(snapshot_id)
    assert persisted is not None
    assert persisted["state"] == "published"
    assert persisted["release_id"] == retry["release_id"]


def test_all_postgres_document_workflow_modes_share_one_publication_followup() -> None:
    # #665 (besluit 10b): the tier D console is refused at construction and
    # is no longer a workflow mode; the shared implementation is the mixin's.
    document_impl = _PostgresWorkflowDocumentsMixin._apply_release_state
    assert FastBadgePostgresCompleteWorkflowDurablePublicationConsole._apply_release_state is document_impl
    assert PostgresCompleteWorkflowDurablePublicationConsole._apply_release_state is document_impl
    assert "_apply_release_state" not in _PostgresRemainingWorkflowMixin.__dict__


def test_reviewer_cannot_reconcile_existing_release_via_publish_route(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    durable = canonical_store(workflow_postgres)
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
        "events": deepcopy(console.workflow_review_store.read_events()),
        "persist_calls": durable.persist_calls,
        "release_count": len(release_ids(durable)),
    }

    calls = {"sync": 0, "apply": 0}
    real_sync = console._sync_snapshot_from_authority
    real_apply = console._apply_release_state

    def count_sync(target_snapshot_id: str) -> dict[str, Any] | None:
        calls["sync"] += 1
        return real_sync(target_snapshot_id)

    def count_apply(release: dict[str, Any], projection: list[dict[str, Any]]) -> None:
        calls["apply"] += 1
        real_apply(release, projection)

    monkeypatch.setattr(console, "_sync_snapshot_from_authority", count_sync)
    monkeypatch.setattr(console, "_apply_release_state", count_apply)

    app = application_for(console)
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
    assert len(release_ids(durable)) == before["release_count"]
    assert console.workflow_document_store.get_envelope(snapshot_id) == before["envelope"]
    assert not projection_path.exists() and not manifest_path.exists() and not ledger_path.exists()
    assert console.workflow_review_store.read_events() == before["events"]
