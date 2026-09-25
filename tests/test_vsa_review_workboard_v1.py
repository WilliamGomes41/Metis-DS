"""VSA Slice 8: reviewer workboard over existing review queues.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.document_status_ui_v1 import install_document_status_ui
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_app import create_console_app
from src.operations_console_v1 import review_stacks
from src.proportionate_review_v1 import ProportionateReviewConsole
from src.publish_readiness_ui_v1 import install_publish_readiness_ui
from src.review_workboard_v1 import install_review_workboard, review_work_item

ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
TEST_PASSWORD = __name__

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


class _QueueConsole(ProportionateReviewConsole):
    def __init__(self, objects: list[dict[str, Any]], status: str = "in_review") -> None:
        self._test_objects = objects
        self._test_status = status

    def snapshot_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        return deepcopy(self._test_objects)

    def object_review_bindings(self, _snapshot_id: str) -> list[dict[str, Any]]:
        return []


    def document_status(self, _snapshot_id: str) -> str:
        return self._test_status


def _obj(
    object_id: str,
    object_type: str,
    *,
    validation_status: str = "needs_review",
    gate_result: str | None = "allowed",
    section_path: list[str] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "passage_register": {
            "status": "not_yet_assessed" if gate_result == "blocked" else "selected_as_candidate",
            "source": "extract",
        }
    }
    if gate_result is not None or section_path is not None:
        metadata["admission"] = {
            "gate_result": gate_result,
            "section_path": section_path or ["Hoofdstuk"],
        }
    return {
        "object_id": object_id,
        "object_type": object_type,
        "proposed_object_type": object_type,
        "metadata": metadata,
        "governance": {"validation_status": validation_status},
        "content": {"clean_text": object_id},
    }


def _envelope(*, reviewer: str = "reviewer-1") -> dict[str, Any]:
    return {
        "snapshot_id": "snap-test",
        "title": "Testdocument",
        "version": "1.0",
        "family": "zorg",
        "class": "richtlijn",
        "state": "captured_not_published",
        "named_reviewers": [reviewer],
    }


def _account(account_id: str = "reviewer-1") -> dict[str, Any]:
    return {"account_id": account_id, "roles": ["reviewer"], "username": account_id}


def test_work_item_reuses_existing_queue_order_and_deep_links() -> None:
    heading = _obj("heading", "heading")
    individual = _obj("individual", "recommendation")
    batch = _obj("batch", "explanation")
    blocked = _obj("blocked", "explanation", gate_result="blocked")
    console = _QueueConsole([heading, individual, batch, blocked])

    item = review_work_item(console, account=_account(), envelope=_envelope())
    assert item is not None
    assert item["next_task"] == "headings"
    assert item["next_href"].endswith("task=headings")

    heading["governance"]["validation_status"] = "approved"
    console._test_objects = [heading, individual, batch, blocked]
    item = review_work_item(console, account=_account(), envelope=_envelope())
    assert item is not None
    assert item["next_task"] == "individual"
    assert item["next_href"].endswith("task=individual")

    individual["governance"]["validation_status"] = "approved"
    console._test_objects = [heading, individual, batch, blocked]
    item = review_work_item(console, account=_account(), envelope=_envelope())
    assert item is not None
    assert item["next_task"] == "together"
    assert item["normal_passages"] == 1
    assert item["next_href"].endswith("task=together")

    batch["governance"]["validation_status"] = "approved"
    console._test_objects = [heading, individual, batch, blocked]
    item = review_work_item(console, account=_account(), envelope=_envelope())
    assert item is not None
    assert item["remaining_review_items"] == 0
    assert item["work_state"] == "technical_repair"
    assert item["next_task"] == "control"
    assert item["next_href"].endswith("task=control")


def test_unassigned_document_is_not_a_work_item() -> None:
    console = _QueueConsole([_obj("heading", "heading")])

    item = review_work_item(
        console,
        account=_account("reviewer-other"),
        envelope=_envelope(reviewer="reviewer-1"),
    )

    assert item is None


def test_review_complete_status_does_not_masquerade_as_open_work() -> None:
    objects = [
        _obj("heading", "heading", validation_status="approved"),
        _obj("content", "explanation", validation_status="approved"),
    ]
    console = _QueueConsole(objects, status="ready_for_publication")

    item = review_work_item(console, account=_account(), envelope=_envelope())

    assert item is not None
    assert item["remaining_review_items"] == 0
    assert item["blocked_count"] == 0
    assert item["work_state"] == "complete"
    assert item["next_task"] == ""


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


def _system(
    tmp_path: Path,
) -> tuple[DurablePublicationConsole, dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    source = MemorySourceStore()
    console = DurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
        immutable_source_store=source,
    )
    accounts = {
        "researcher": console.create_account(
            username="researcher.anne",
            password=TEST_PASSWORD,
            roles=("researcher", "reviewer"),
        ),
        "reviewer_a": console.create_account(
            username="reviewer.a",
            password=TEST_PASSWORD,
            roles=("reviewer",),
        ),
        "reviewer_b": console.create_account(
            username="reviewer.b",
            password=TEST_PASSWORD,
            roles=("reviewer",),
        ),
        "publisher": console.create_account(
            username="publisher.carla",
            password=TEST_PASSWORD,
            roles=("publisher",),
        ),
    }
    common = {
        "actor_id": accounts["researcher"]["account_id"],
        "data": HTML_FIXTURE.read_bytes(),
        "content_type": "text/html",
        "ingest_kind": "new",
        "version": "1.0",
        "date": "2025-04-01",
        "live_url": "https://example.test/continentie",
        "class_": "richtlijn",
        "family": "continentie",
    }
    first = console.ingest(
        **common,
        filename="document-a.html",
        title="Document A",
        named_reviewers=[accounts["reviewer_a"]["account_id"]],
    )
    second = console.ingest(
        **common,
        filename="document-b.html",
        title="Document B",
        named_reviewers=[accounts["reviewer_b"]["account_id"]],
    )
    return console, accounts, first, second


def _client(console: DurablePublicationConsole) -> TestClient:
    app = create_console_app(console)
    install_publish_readiness_ui(app, console)
    install_document_status_ui(app, console)
    install_review_workboard(app, console)
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


def _login(client: TestClient, username: str) -> None:
    response = client.post(
        "/login",
        data={"username": username, "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_review_landing_is_assignment_scoped_workboard(tmp_path: Path) -> None:
    console, _accounts, first, second = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.a")

    page = client.get("/review")

    assert page.status_code == 200
    assert "data-review-workboard" in page.text
    assert "Document A" in page.text
    assert str(first["snapshot_id"]) in page.text
    assert "Document B" not in page.text
    assert str(second["snapshot_id"]) not in page.text
    assert "status <b>in review</b>" in page.text
    assert "Volgende stap" in page.text


def test_selected_document_keeps_existing_review_dashboard(tmp_path: Path) -> None:
    console, _accounts, first, _second = _system(tmp_path)
    client = _client(console)
    _login(client, "reviewer.a")

    page = client.get(f"/review?document={first['snapshot_id']}")

    assert page.status_code == 200
    assert "data-review-workboard" not in page.text
    assert "Alle taken" in page.text
    assert "Document A" in page.text


def test_heading_batch_success_returns_to_live_document_dashboard(tmp_path: Path) -> None:
    console, _accounts, first, _second = _system(tmp_path)
    snapshot_id = str(first["snapshot_id"])
    objects = console.snapshot_objects(snapshot_id)
    headings, _ = review_stacks(objects, review_path="richtlijn")
    heading_ids = [
        str(row["object_id"])
        for row in headings
        if (row.get("governance") or {}).get("validation_status")
        not in {"approved", "rejected", "superseded"}
    ]
    assert heading_ids

    client = _client(console)
    _login(client, "reviewer.a")
    response = client.post(
        "/review/headings/batch-confirm",
        data={
            "snapshot_id": snapshot_id,
            "snapshot_revision": console.objects_revision(snapshot_id),
            "object_ids": heading_ids,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/review?document={snapshot_id}"
    assert "task=headings" not in response.headers["location"]

    page = client.get(response.headers["location"])
    assert page.status_code == 200
    assert "Alle taken" in page.text
    assert (
        f'href="/review?document={snapshot_id}&amp;task=headings">Ga verder</a>'
        not in page.text
    )


def test_workboard_read_does_not_persist_progress_or_change_objects(tmp_path: Path) -> None:
    console, _accounts, first, _second = _system(tmp_path)
    snapshot_id = str(first["snapshot_id"])
    before_envelopes = deepcopy(console.list_envelopes())
    before_revision = console.objects_revision(snapshot_id)
    client = _client(console)
    _login(client, "reviewer.a")

    page = client.get("/review")

    assert page.status_code == 200
    assert console.list_envelopes() == before_envelopes
    assert console.objects_revision(snapshot_id) == before_revision
    assert all("review_progress" not in row for row in console.list_envelopes())


def test_non_reviewer_cannot_open_reviewer_workboard(tmp_path: Path) -> None:
    console, _accounts, _first, _second = _system(tmp_path)
    client = _client(console)
    _login(client, "publisher.carla")

    page = client.get("/review")

    assert page.status_code == 403
    assert "reviewer_role_required" in page.text
