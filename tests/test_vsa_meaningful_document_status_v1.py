"""VSA Slice 7: one meaningful derived document status across workflow rooms.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.document_status_ui_v1 import install_document_status_ui
from src.document_status_v1 import (
    DocumentStatusReadinessMixin,
    derive_document_status,
)
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, review_lane
from src.passage_register_v1 import passage_register_of
from src.publish_readiness_ui_v1 import install_publish_readiness_ui
from src.review_disposition_v1 import definitive_review_disposition
from src.workflow_documents_cutover_v1 import PostgresWorkflowDurablePublicationConsole

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
) -> tuple[DurablePublicationConsole, dict[str, dict[str, Any]], dict[str, Any], MemorySourceStore]:
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
    return console, accounts, receipt, source


def _complete_review(
    console: DurablePublicationConsole,
    accounts: dict[str, dict[str, Any]],
    receipt: dict[str, Any],
) -> None:
    snapshot_id = str(receipt["snapshot_id"])
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
            "superseded",
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


def _client(console: DurablePublicationConsole) -> TestClient:
    app = create_console_app(console)
    install_publish_readiness_ui(app, console)
    install_document_status_ui(app)
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


def _login(client: TestClient, username: str) -> None:
    response = client.post(
        "/login",
        data={"username": username, "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _assert_room_statuses(
    client: TestClient,
    *,
    researcher_username: str,
    publisher_username: str,
    expected_label: str,
) -> None:
    _login(client, researcher_username)
    tree = client.get("/tree")
    review = client.get("/review")
    assert tree.status_code == 200
    assert review.status_code == 200
    assert f"status <b>{expected_label}</b>" in tree.text
    assert f"status <b>{expected_label}</b>" in review.text

    _login(client, publisher_username)
    publish = client.get("/publish")
    assert publish.status_code == 200
    assert f"status <b>{expected_label}</b>" in publish.text


def test_status_precedence_is_deterministic_and_fail_closed() -> None:
    assert derive_document_status(
        envelope_state="published",
        readiness={"publication_ready": False},
    ) == "published"
    assert derive_document_status(
        envelope_state="captured_not_published",
        readiness={"publication_ready": True},
    ) == "ready_for_publication"
    assert derive_document_status(
        envelope_state="captured_not_published",
        readiness={"curation_ready": True, "technical_ready": False},
    ) == "blocked"
    assert derive_document_status(
        envelope_state="captured_not_published",
        readiness={"curation_ready": False, "technical_ready": True},
    ) == "in_review"
    assert derive_document_status(
        envelope_state="captured_not_published",
        readiness={},
    ) == "processing"


def test_read_only_status_does_not_widen_publisher_authority(tmp_path: Path) -> None:
    console, accounts, receipt, _source = _system(tmp_path)
    snapshot_id = str(receipt["snapshot_id"])

    assert console.document_status(snapshot_id) == "in_review"
    with pytest.raises(ConsoleError, match="publisher_role_required"):
        console.consider_publish(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=snapshot_id,
        )


def test_open_review_has_same_meaningful_status_in_all_three_rooms(tmp_path: Path) -> None:
    console, _accounts, _receipt, _source = _system(tmp_path)
    client = _client(console)

    _assert_room_statuses(
        client,
        researcher_username="researcher.anne",
        publisher_username="publisher.carla",
        expected_label="in review",
    )
    assert "captured not published" not in client.get("/publish").text.lower()


def test_complete_review_moves_from_blocked_to_ready_without_persisting_status(
    tmp_path: Path,
) -> None:
    console, accounts, receipt, source = _system(tmp_path)
    snapshot_id = str(receipt["snapshot_id"])
    _complete_review(console, accounts, receipt)

    assert console.document_status(snapshot_id) == "ready_for_publication"
    stored = console._envelope(snapshot_id)
    assert stored["state"] == "captured_not_published"
    assert "meaningful_status" not in stored

    source.blobs.pop(str(receipt["immutable_storage_locator"]))
    assert console.document_status(snapshot_id) == "blocked"
    assert console._envelope(snapshot_id)["state"] == "captured_not_published"


def test_ready_blocked_and_published_labels_are_shared_across_rooms(tmp_path: Path) -> None:
    console, accounts, receipt, source = _system(tmp_path)
    snapshot_id = str(receipt["snapshot_id"])
    _complete_review(console, accounts, receipt)
    client = _client(console)

    _assert_room_statuses(
        client,
        researcher_username="researcher.anne",
        publisher_username="publisher.carla",
        expected_label="klaar voor publicatie",
    )

    locator = str(receipt["immutable_storage_locator"])
    source.blobs.pop(locator)
    _assert_room_statuses(
        client,
        researcher_username="researcher.anne",
        publisher_username="publisher.carla",
        expected_label="geblokkeerd",
    )

    source.blobs[locator] = HTML_FIXTURE.read_bytes()
    result = console.publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=snapshot_id,
    )
    assert result["status"] == "PASS"
    assert console.document_status(snapshot_id) == "published"
    _assert_room_statuses(
        client,
        researcher_username="researcher.anne",
        publisher_username="publisher.carla",
        expected_label="gepubliceerd",
    )


def test_postgres_workflow_console_inherits_same_derived_status_policy() -> None:
    assert issubclass(PostgresWorkflowDurablePublicationConsole, DocumentStatusReadinessMixin)
