"""HTTP selection failure/success/restart proof against native PostgreSQL.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.proportionate_review_v1 import install_proportionate_review_routes, normal_risk_batch_queue
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from src.workflows.workflow_review_cutover_v1 import PostgresReviewWorkflowDurablePublicationConsole
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


def _console(root, config):
    identity = PostgresWorkflowIdentityStore(config)
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    bind_workflow_stores(identity, documents, reviews)
    console = PostgresReviewWorkflowDurablePublicationConsole(
        root=root, source_store=root / "sources", runtime=root / "runtime",
        workflow_identity_store=identity, workflow_document_store=documents,
        workflow_review_store=reviews,
    )
    return console


def _client(console):
    app = create_console_app(console)
    install_proportionate_review_routes(app, console)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/login", data={"username": "bert", "password": "bert-secret"}, follow_redirects=False).status_code == 303
    return client


def test_http_batch_failure_retry_stale_and_restart(workflow_postgres, tmp_path, monkeypatch):
    console = _console(tmp_path, workflow_postgres)
    from tests.semantic_fixture_support import bind_fixture_selections
    bind_fixture_selections(console)
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    receipt = console.ingest(
        actor_id=researcher["account_id"], filename="begrippen.html", content_type="text/html",
        data=b'<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>'
             b'<p>De Dutch Job Group is een meetinstrument voor werkbelasting.</p>'
             b'<p>Een observatie is een systematische waarneming van gedrag.</p></body></html>',
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-09-20", live_url="",
        class_="richtlijn", family="begrippen", named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    ids = [obj["object_id"] for obj in normal_risk_batch_queue(console.snapshot_objects(sid), review_path="richtlijn")]
    assert len(ids) == 2
    client = _client(console)
    before = deepcopy(console.snapshot_objects(sid))
    reviews = console.workflow_review_store
    before_bindings, before_events = reviews.read_bindings(), reviews.read_events()
    data = {"snapshot_id": sid, "snapshot_revision": console.objects_revision(sid), "object_ids": ids}
    original = console.review_object

    def fail_second(**kwargs):
        if kwargs["object_id"] == ids[1]:
            raise RuntimeError("second_member_failure")
        return original(**kwargs)

    monkeypatch.setattr(console, "review_object", fail_second)
    assert client.post("/review/normal-risk/batch-confirm", data=data).status_code == 500
    assert console.workflow_document_store.list_document_objects(sid) == before
    assert reviews.read_bindings() == before_bindings
    assert reviews.read_events() == before_events

    restarted = _console(tmp_path, workflow_postgres)
    assert restarted.snapshot_objects(sid) == before
    client = _client(restarted)
    assert client.post("/review/normal-risk/batch-confirm", data=data, follow_redirects=False).status_code == 303
    committed = _console(tmp_path, workflow_postgres)
    selected = [obj for obj in committed.snapshot_objects(sid) if obj["object_id"] in ids]
    assert all(obj["governance"]["validation_status"] == "approved" for obj in selected)
    bindings = committed.object_review_bindings(sid)
    assert {b["object_id"] for b in bindings if b["decision"] == "approve" and b["valid"]} == set(ids)
    events = committed.workflow_review_store.read_events()
    assert len(events) > len(before_events)
    assert client.post("/review/normal-risk/batch-confirm", data=data, follow_redirects=False).status_code == 409
    assert committed.workflow_review_store.read_events() == events
    assert committed.object_review_bindings(sid) == bindings
