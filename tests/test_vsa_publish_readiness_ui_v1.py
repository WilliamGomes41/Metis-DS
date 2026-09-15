"""VSA Slice 5: actionable Publish room over the existing readiness contract.

# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
# release-control-evidence: concurrent stale
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.durable_publication_console_v1 import DurablePublicationConsole
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_app import create_console_app
from src.operations_console_v1 import review_lane
from src.passage_register_v1 import passage_register_of
from src.publication_readiness_v1 import source_passage_closure
from src.publish_readiness_ui_v1 import (
    install_publish_readiness_ui,
    publish_readiness_view,
)
from src.review_disposition_v1 import definitive_review_disposition

ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
TEST_PASSWORD = __name__

pytestmark = [
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
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


def _console_with_document(
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
    return TestClient(
        app,
        base_url="https://testserver",
        raise_server_exceptions=False,
    )


def _login(client: TestClient, username: str) -> None:
    response = client.post(
        "/login",
        data={"username": username, "password": TEST_PASSWORD},
    )
    assert response.status_code in {200, 302, 303}


def test_view_model_preserves_codes_order_categories_and_recovery() -> None:
    considered = {
        "state": "captured_not_published",
        "publication_ready": False,
        "publish_allowed": False,
        "publishable_object_count": 1,
        "curation_ready": False,
        "curation_blockers": [
            "review_work_incomplete",
            "source_passage_review_incomplete",
        ],
        "unresolved_review_object_count": 2,
        "unresolved_source_passage_count": 3,
        "technical_ready": False,
        "technical_blockers": [
            "four_eyes_required",
            "g2_source_store_unavailable",
        ],
        "blockers": [
            "four_eyes_required",
            "review_work_incomplete",
            "source_passage_review_incomplete",
            "g2_source_store_unavailable",
        ],
    }

    view = publish_readiness_view(
        snapshot_id="snap-test",
        envelope_state="captured_not_published",
        considered=considered,
    )

    assert view["overall_state"] == "blocked"
    assert view["blocker_codes"] == considered["blockers"]
    assert view["curation_blocker_codes"] == considered["curation_blockers"]
    assert view["technical_blocker_codes"] == considered["technical_blockers"]
    assert view["unresolved_review_object_count"] == 2
    assert view["unresolved_source_passage_count"] == 3
    assert view["curation_blockers"][0]["recovery_href"] == "/review?document=snap-test"
    assert view["technical_blockers"][0]["recovery_href"] == "/review?document=snap-test"
    assert view["technical_blockers"][1]["recovery_href"] is None


def test_publish_page_separates_curation_and_technical_blockers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console, _accounts, receipt, _source = _console_with_document(tmp_path)
    considered = {
        "state": "captured_not_published",
        "publication_ready": False,
        "publish_allowed": False,
        "publishable_object_count": 1,
        "curation_ready": False,
        "curation_blockers": ["source_passage_review_incomplete"],
        "unresolved_review_object_count": 0,
        "unresolved_source_passage_count": 4,
        "technical_ready": False,
        "technical_blockers": ["four_eyes_required"],
        "blockers": ["four_eyes_required", "source_passage_review_incomplete"],
    }
    monkeypatch.setattr(
        console,
        "consider_publish",
        lambda *, actor_id, snapshot_id: dict(considered),
    )
    client = _client(console)
    _login(client, "publisher.carla")

    page = client.get("/publish")

    assert page.status_code == 200
    assert 'data-publication-state="blocked"' in page.text
    assert 'data-readiness-category="curation"' in page.text
    assert 'data-readiness-category="technical"' in page.text
    assert 'data-blocker-code="source_passage_review_incomplete"' in page.text
    assert 'data-blocker-code="four_eyes_required"' in page.text
    assert "Nog 4 inhoudelijke bronpassage(s)" in page.text
    assert "Open Review" in page.text
    assert 'data-publish-form' not in page.text
    assert str(receipt["snapshot_id"]) in page.text


def test_publish_form_is_only_rendered_for_publication_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console, _accounts, _receipt, _source = _console_with_document(tmp_path)
    monkeypatch.setattr(
        console,
        "consider_publish",
        lambda *, actor_id, snapshot_id: {
            "state": "captured_not_published",
            "publication_ready": True,
            "publish_allowed": True,
            "publishable_object_count": 2,
            "curation_ready": True,
            "curation_blockers": [],
            "technical_ready": True,
            "technical_blockers": [],
            "blockers": [],
        },
    )
    client = _client(console)
    _login(client, "publisher.carla")

    page = client.get("/publish")

    assert page.status_code == 200
    assert 'data-publication-state="ready"' in page.text
    assert "Klaar voor publicatie: 2 gereviewde kennisobjecten" in page.text
    assert 'data-publish-form' in page.text
    assert 'name="publish_confirmed"' in page.text


def test_published_document_has_no_publish_form(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console, _accounts, _receipt, _source = _console_with_document(tmp_path)
    monkeypatch.setattr(
        console,
        "consider_publish",
        lambda *, actor_id, snapshot_id: {
            "state": "published",
            "publication_ready": False,
            "publish_allowed": False,
            "publishable_object_count": 0,
            "curation_ready": True,
            "curation_blockers": [],
            "technical_ready": False,
            "technical_blockers": ["already_published"],
            "blockers": ["already_published"],
        },
    )
    client = _client(console)
    _login(client, "publisher.carla")

    page = client.get("/publish")

    assert page.status_code == 200
    assert 'data-publication-state="published"' in page.text
    assert "Gepubliceerd" in page.text
    assert 'data-publish-form' not in page.text


def test_publish_room_requires_publisher_role(tmp_path: Path) -> None:
    console, _accounts, _receipt, _source = _console_with_document(tmp_path)
    client = _client(console)
    _login(client, "researcher.anne")

    page = client.get("/publish")

    assert page.status_code == 403
    assert "publisher_role_required" in page.text


def test_direct_post_cannot_bypass_backend_readiness(tmp_path: Path) -> None:
    console, _accounts, receipt, _source = _console_with_document(tmp_path)
    client = _client(console)
    _login(client, "publisher.carla")

    blocked = client.post(
        "/publish",
        data={"snapshot_id": receipt["snapshot_id"], "publish_confirmed": "yes"},
    )

    assert blocked.status_code == 400
    assert console.snapshot_is_published(receipt["snapshot_id"]) is False


def test_stale_ready_page_is_rechecked_on_publish_post(tmp_path: Path) -> None:
    console, accounts, receipt, source = _console_with_document(tmp_path)
    _complete_review(console, accounts, receipt)
    client = _client(console)
    _login(client, "publisher.carla")

    ready = client.get("/publish")
    assert ready.status_code == 200
    assert 'data-publication-state="ready"' in ready.text
    assert 'data-publish-form' in ready.text

    locator = str(receipt["immutable_storage_locator"])
    source.blobs[locator] = b"changed after readiness screen"

    blocked = client.post(
        "/publish",
        data={"snapshot_id": receipt["snapshot_id"], "publish_confirmed": "yes"},
    )

    assert blocked.status_code == 400
    assert "g2_source_checksum_mismatch" in blocked.text
    assert console.snapshot_is_published(receipt["snapshot_id"]) is False


def test_superseded_review_passage_is_terminal_for_source_closure() -> None:
    retired = {
        "object_id": "retired-context",
        "object_type": "explanation",
        "proposed_object_type": "explanation",
        "metadata": {
            "passage_register": {
                "status": "used_as_context",
                "source": "review",
            }
        },
        "governance": {
            "validation_status": "superseded",
            "publication_status": "unpublished",
            "superseded_by": "merged-object",
        },
    }

    disposition = definitive_review_disposition(retired)
    closure = source_passage_closure([retired])

    assert disposition["state"] == "final"
    assert disposition["final"] is True
    assert disposition["outcome"] == "superseded"
    assert closure["source_passage_review_complete"] is True
    assert closure["unresolved_source_passage_ids"] == []
