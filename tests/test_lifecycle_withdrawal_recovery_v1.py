"""Native PostgreSQL proof of withdrawal and the complete recoverable lifecycle.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from copy import deepcopy
from threading import Event
from html.parser import HTMLParser
import shutil

import pytest
from fastapi.testclient import TestClient

from src.api_access_v1 import PostgresApiAccessStore
from src.audit_retention_v1 import AuditRetentionService
from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError, PostgresCanonicalPublicationStore
from src.operations_console_app import create_console_app
from src.operations_console_v1 import PRE_REVIEW_BLOCKED
from src.product_api_v1 import create_product_app
from src.product_security_v1 import TenantRegistry
from src.publish_readiness_ui_v1 import install_publish_readiness_ui
from src.usage_ledger_v1 import UsageLedger
from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole
from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter, backup_workflow_chain, restore_workflow_chain
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
from src.workflows.workflow_remaining_cutover_v1 import PostgresAuditRegistry
from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores
from tests.test_api_access_lifecycle_v1 import _provision
from tests.test_api_access_product_v1 import _paths
from tests.test_logical_document_withdrawal_v1 import _publish, _active_object_ids
from tests.test_publication_chain_recovery_v1 import FakeBlobStore
from tests.test_vsa_publish_readiness_ui_v1 import HTML_FIXTURE, TEST_PASSWORD, _complete_review
from tests.test_workflow_audit_retention_v1 import Archive
from tests.test_workflow_chain_recovery_v1 import _install_schema, recovery_postgres  # noqa: F401


def _console(root, config, source):
    identity = CutoverPostgresWorkflowIdentityStore(config)
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    remaining = PostgresWorkflowRemainingStore(config)
    bind_workflow_stores(identity, documents, reviews, remaining)
    return FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole(
        root=root, source_store=root / "sources", runtime=root / "runtime",
        immutable_source_store=source, canonical_publication_store=PostgresCanonicalPublicationStore(config),
        workflow_identity_store=identity, workflow_document_store=documents,
        workflow_review_store=reviews, workflow_remaining_store=remaining,
    )


def _client(console, username="publisher.carla"):
    app = create_console_app(console, trusted_origin="https://testserver")
    install_publish_readiness_ui(app, console)
    client = TestClient(app, base_url="https://testserver", headers={"Origin": "https://testserver"})
    assert client.post("/login", data={"username": username, "password": TEST_PASSWORD}, follow_redirects=False).status_code == 303
    return client


def _ingest(console, accounts, title, version, prior=None):
    receipt = console.ingest(
        actor_id=accounts["researcher"]["account_id"], title=title, version=version,
        ingest_kind="new_version" if prior else "new", replaces_snapshot_id=prior,
        filename=f"source-{title}-{version}.html", content_type="text/html",
        data=HTML_FIXTURE.read_bytes() + f"<!-- {title} {version} -->".encode(),
        date="2026-09-01", live_url=f"https://example.test/{title}",
        class_="richtlijn", family="continentie",
        named_reviewers=[accounts["researcher"]["account_id"], accounts["reviewer"]["account_id"]],
    )
    return console._envelope(receipt["snapshot_id"])


def _publish_http(console, client, accounts, receipt):
    _complete_review(console, accounts, receipt)
    response = client.post("/publish", data={"snapshot_id": receipt["snapshot_id"], "publish_confirmed": "yes"}, follow_redirects=False)
    assert response.status_code == 303, response.text
    return console.canonical_publication_store.release_for_snapshot(receipt["snapshot_id"])


def _api(root, config, source):
    root.mkdir(parents=True, exist_ok=True)
    paths = _paths(root)
    return TestClient(create_product_app(
        "real", paths=paths, tenant_registry=TenantRegistry([]),
        api_access_store=PostgresApiAccessStore(config), api_access_mode="postgres",
        canonical_publication_store=PostgresCanonicalPublicationStore(config),
        immutable_source_store=source, usage_ledger=UsageLedger(paths.usage_db),
    ))


def _documents(api, consumer):
    response = api.get("/v1/documents", headers={"Authorization": f"Bearer {consumer.credential}"})
    return response.status_code, sorted(row["document_id"] for row in response.json().get("documents", []))


class _PassageInventory(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.rows = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li" and "data-passage-id" in attrs:
            self.rows.append((attrs["data-passage-id"], attrs["data-passage-category"]))


def _assert_review_projection(console, client, snapshot_id):
    before = deepcopy(console.snapshot_objects(snapshot_id))
    bindings = deepcopy(console.object_review_bindings(snapshot_id))
    dashboard = client.get("/review", params={"document": snapshot_id})
    assert dashboard.status_code == 200
    assert "Jouw open werk" in dashboard.text
    assert 'class="review-workspace-layout"' in dashboard.text
    assert dashboard.text.count("Bekijk technische controle") == 1
    inventory = client.get("/review", params={"document": snapshot_id, "task": "inventory"})
    assert inventory.status_code == 200
    rows = _PassageInventory(inventory.text).rows
    expected = {obj["object_id"] for obj in before if obj.get("object_type") != "document"}
    assert len(rows) == len(expected)
    assert {oid for oid, _ in rows} == expected
    assert all(category in {"structure", "contextual", "batch", "second_review", "waiting", "repair", "disposition", "history"} for _, category in rows)
    assert console.snapshot_objects(snapshot_id) == before
    assert console.object_review_bindings(snapshot_id) == bindings
    return sorted(rows)


def test_http_withdrawal_complete_recovery_and_open_work_resume(recovery_postgres, tmp_path, monkeypatch):
    config = recovery_postgres
    source = FakeBlobStore()
    root = tmp_path / "original"
    console = _console(root, config, source)
    accounts = {
        name: console.create_account(username=username, password=TEST_PASSWORD, roles=roles)
        for name, username, roles in [
            ("researcher", "researcher.anne", ("researcher", "reviewer")),
            ("reviewer", "reviewer.bert", ("reviewer",)),
            ("publisher", "publisher.carla", ("publisher",)),
        ]
    }
    client = _client(console)
    v1 = _ingest(console, accounts, "document-a", "1.0")
    review_client = _client(console, "reviewer.bert")
    _assert_review_projection(console, review_client, v1["snapshot_id"])
    r1 = _publish_http(console, client, accounts, v1)
    published_v1 = deepcopy(console.snapshot_objects(v1["snapshot_id"]))
    console.migrate_legacy_revise_to_review()
    assert console.snapshot_objects(v1["snapshot_id"]) == published_v1
    v2 = _ingest(console, accounts, "document-a", "2.0", v1["snapshot_id"])
    _assert_review_projection(console, review_client, v2["snapshot_id"])
    assert console.snapshot_objects(v1["snapshot_id"]) == published_v1
    assert console.document_release_serving_status(v1["snapshot_id"])["serving_status"] == "active"
    r2 = _publish_http(console, client, accounts, v2)
    v3 = _ingest(console, accounts, "document-a", "3.0", v2["snapshot_id"])
    other = _ingest(console, accounts, "document-b", "1.0")
    other_release = _publish_http(console, client, accounts, other)
    assert r1["logical_document_id"] == r2["logical_document_id"] == v3["logical_document_id"]
    pending = deepcopy(console._envelope(v3["snapshot_id"]))
    pending["publication_eligibility"] = PRE_REVIEW_BLOCKED
    pending["processing_blocker"] = {"code": "empty_test_extract"}
    console.workflow_document_store.write_bundle(envelope=pending, objects=[])
    console.refresh_workflow_documents()
    stale = dict(snapshot_id=v1["snapshot_id"], expected_release_id=r1["release_id"], reason="Source withdrawn", withdraw_confirmed="yes")
    assert client.post("/publish/withdraw", data=stale).status_code == 409
    assert console.document_release_serving_status(v2["snapshot_id"])["serving_status"] == "active"

    access = PostgresApiAccessStore(config)
    document_ids = tuple({v1["document_id"], v2["document_id"], other["document_id"]})
    active = _provision(access, name="Active", tenant_docs=document_ids, app_docs=document_ids)
    revoked = _provision(access, name="Revoked", tenant_docs=document_ids, app_docs=document_ids)
    access.revoke_credential(actor_id=accounts["publisher"]["account_id"], tenant_id=revoked.tenant_id,
                             application_id=revoked.application_id, credential_id=revoked.credential_id)
    api = _api(tmp_path / "api-before", config, source)
    assert _documents(api, active) == (200, sorted({v2["document_id"], other["document_id"]}))
    assert _documents(api, revoked) == (401, [])

    payload = {**stale, "snapshot_id": v2["snapshot_id"], "expected_release_id": r2["release_id"]}
    with monkeypatch.context() as patch:
        patch.setattr(console, "_apply_local_release_copy", lambda *a: (_ for _ in ()).throw(OSError("projection unavailable")))
        response = client.post("/publish/withdraw", data=payload)
    assert response.status_code == 200
    assert 'data-withdrawal-result="pending"' in response.text
    assert _documents(api, active) == (200, [other["document_id"]])
    assert client.post("/publish/withdraw", data=payload).status_code == 200
    with console.canonical_publication_store._connect() as con:
        events = con.execute("SELECT actor,details FROM audit_events WHERE entity_id=%s AND event_type='release_withdrawn'", (r2["release_id"],)).fetchall()
    assert len(events) == 1
    assert events[0]["actor"] == "publisher.carla"
    assert events[0]["details"]["reason"] == payload["reason"]
    page = client.get("/publish")
    assert page.status_code == 200
    assert 'data-publication-state="withdrawn"' in page.text
    assert 'data-publication-state="superseded"' in page.text
    assert page.text.count("data-withdraw-form") == 1  # Only the other active document.
    assert console._envelope(v3["snapshot_id"]) == pending

    registry = PostgresAuditRegistry(console.workflow_remaining_store)
    archived = registry.create(audit_type="experiment", title="Archived evidence", actor_id=accounts["publisher"]["account_id"], payload={"evidence": "exact"})
    live = registry.create(audit_type="experiment", title="Live evidence", actor_id=accounts["publisher"]["account_id"], payload={"evidence": "live"})
    archive = Archive()
    retention = AuditRetentionService(live_store=registry, archive_store=archive, runtime=console.runtime)
    retention.archive(archived["audit_id"], actor_id=accounts["publisher"]["account_id"])
    inventories_before = {
        receipt["snapshot_id"]: _assert_review_projection(console, review_client, receipt["snapshot_id"])
        for receipt in (v1, v2, other)
    }
    review_client.close()
    adapter = PostgresWorkflowRecoveryAdapter(console.canonical_publication_store)
    before = adapter.export_state()
    path = tmp_path / "complete-lifecycle.zip"
    manifest = backup_workflow_chain(path, database=adapter, source_store=source, audit_archive_store=archive)
    assert len(manifest["blobs"]) == 4
    api.close()
    client.close()
    shutil.rmtree(root)  # No original Console files or cached source bytes survive.
    _install_schema(config.dsn)
    target_sources, target_audits = FakeBlobStore(), Archive()
    result = restore_workflow_chain(path, database=adapter, source_store=target_sources, audit_archive_store=target_audits)
    assert result["ok"]
    after = adapter.export_state()
    for group in ("tables", "workflow_tables", "api_access_tables"):
        assert after[group] == before[group]
    assert target_sources.blobs == source.blobs

    fresh = _console(tmp_path / "restored", config, target_sources)
    fresh.reconcile_durable_publications()
    restarted_client = _client(fresh)
    restored_review_client = _client(fresh, "reviewer.bert")
    for sid, inventory in inventories_before.items():
        assert _assert_review_projection(fresh, restored_review_client, sid) == inventory
    restored_review_client.close()
    restarted_api = _api(tmp_path / "api-restored", config, target_sources)
    assert _documents(restarted_api, active) == (200, [other["document_id"]])
    assert _documents(restarted_api, revoked) == (401, [])
    assert fresh.document_release_serving_status(v2["snapshot_id"]) == {"release_status": "withdrawn", "serving_status": "inactive"}
    for receipt in (v1, v2):
        assert fresh.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"])["status"] == "BLOCKED"
    assert restarted_client.post("/publish/withdraw", data=payload).status_code == 200
    assert _documents(restarted_api, active) == (200, [other["document_id"]])
    fresh_registry = PostgresAuditRegistry(fresh.workflow_remaining_store)
    restored_retention = AuditRetentionService(live_store=fresh_registry, archive_store=target_audits, runtime=fresh.runtime)
    assert fresh_registry.get_audit(live["audit_id"]) == live
    assert restored_retention.load_archived(archived["audit_id"]) == archived
    assert restored_retention.restore(archived["audit_id"], actor_id=accounts["publisher"]["account_id"]) == archived
    researcher_client = _client(fresh, "researcher.anne")
    resumed = researcher_client.post("/tree/reprocess", data={"snapshot_id": v3["snapshot_id"]}, follow_redirects=False)
    assert resumed.status_code == 303, resumed.text
    assert fresh.snapshot_objects(v3["snapshot_id"])
    _assert_review_projection(fresh, researcher_client, v3["snapshot_id"])
    resumed_envelope = fresh._envelope(v3["snapshot_id"])
    for key in ("snapshot_id", "logical_document_id", "working_revision_id", "working_revision_number", "sha256"):
        assert resumed_envelope[key] == pending[key]
    assert _documents(restarted_api, active) == (200, [other["document_id"]])


def _kernel_publish(store, number):
    return _publish(store, logical_document_id="logical", working_revision_id=f"w{number}",
                    snapshot_id=f"s{number}", release_id=f"r{number}", release_version=str(number),
                    document_id="document", checksum=str(number) * 64,
                    published_at=f"2026-09-01T00:00:0{number * 2}+00:00", object_ids=[f"o{number}"])


def _kernel_withdraw(store):
    return store.withdraw_logical_document(logical_document_id="logical", expected_release_id="r1",
                                           actor="publisher", reason="reason", withdrawn_at="2026-09-01T00:00:03+00:00")


@pytest.mark.parametrize("first", ["publish", "withdraw", "first_publish"])
def test_publish_and_withdraw_serialize_across_connections(recovery_postgres, monkeypatch, first):
    winner, loser = (PostgresCanonicalPublicationStore(recovery_postgres) for _ in range(2))
    if first != "first_publish":
        _kernel_publish(winner, 1)
    reached, release, attempted = Event(), Event(), Event()
    original_audit = winner._audit
    def hold_before_commit(con, **kwargs):
        original_audit(con, **kwargs)
        if kwargs["event_type"] in {"release_published", "release_withdrawn"}:
            reached.set()
            assert release.wait(10)
    monkeypatch.setattr(winner, "_audit", hold_before_commit)
    original_connect = loser._connect
    @contextmanager
    def observed_connect():
        with original_connect() as con:
            class Connection:
                def transaction(self):
                    return con.transaction()
                def execute(self, query, params=None):
                    if "pg_advisory_xact_lock" in query:
                        attempted.set()
                    return con.execute(query, params)
            yield Connection()
    monkeypatch.setattr(loser, "_connect", observed_connect)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(_kernel_withdraw, winner) if first == "withdraw" else pool.submit(_kernel_publish, winner, 1 if first == "first_publish" else 2)
        try:
            assert reached.wait(10)
            b = pool.submit(_kernel_withdraw, loser) if first == "publish" else pool.submit(_kernel_publish, loser, 2)
            assert attempted.wait(10)
            with pytest.raises(TimeoutError):
                b.result(timeout=0.1)
        finally:
            release.set()
        a.result(timeout=10)
        if first == "publish":
            with pytest.raises(CanonicalPublicationStoreError, match="canonical_expected_release_changed"):
                b.result(timeout=10)
        else:
            b.result(timeout=10)
    assert _active_object_ids(PostgresCanonicalPublicationStore(recovery_postgres)) == {"o2"}


def test_withdrawal_audit_failure_rolls_back_release_registry_and_evidence(recovery_postgres, monkeypatch):
    store = PostgresCanonicalPublicationStore(recovery_postgres)
    _kernel_publish(store, 1)
    adapter = PostgresWorkflowRecoveryAdapter(store)
    before = adapter.export_state()
    original = store._audit
    def fail_last_audit(con, **kwargs):
        original(con, **kwargs)
        if kwargs["event_type"] == "release_withdrawn":
            raise RuntimeError("audit interruption")
    monkeypatch.setattr(store, "_audit", fail_last_audit)
    with pytest.raises(CanonicalPublicationStoreError, match="canonical_postgres_write_failed"):
        _kernel_withdraw(store)
    assert adapter.export_state()["tables"] == before["tables"]
    assert _active_object_ids(store) == {"o1"}

