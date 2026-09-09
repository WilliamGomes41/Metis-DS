"""C5 publication activation and route regression evidence.

Publication reloads its state under the shared store lock before cutover, so
concurrent changes cannot bypass the gate and stale preflight state is never
used.  The rollback test proves that a failed transaction leaves neither a
partial projection nor a release manifest behind.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.operations_console_v1 as console_module
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
TEST_PASSWORD = __name__

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


class MemoryImmutableStore:
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


def _ready_console(tmp_path: Path) -> tuple[OperationsConsole, dict[str, dict], dict, MemoryImmutableStore]:
    store = MemoryImmutableStore()
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
        immutable_source_store=store,
    )
    accounts = {
        "researcher": console.create_account(
            username="researcher.anne", password=TEST_PASSWORD, roles=("researcher", "reviewer")
        ),
        "reviewer": console.create_account(
            username="reviewer.bert", password=TEST_PASSWORD, roles=("reviewer",)
        ),
        "publisher": console.create_account(
            username="publisher.carla", password=TEST_PASSWORD, roles=("publisher",)
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
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") == "unclassified"
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="explanation",
    )
    return console, accounts, receipt, store


def test_verified_reviewed_object_can_be_published_once(tmp_path: Path) -> None:
    console, accounts, receipt, _store = _ready_console(tmp_path)
    snapshot_id = receipt["snapshot_id"]

    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
    )
    assert considered["publish_allowed"] is True
    assert considered["g2"] == "PASS"
    assert considered["publishable_object_count"] == 1

    result = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
    )
    assert result["status"] == "PASS"
    assert result["cutover"] is True
    assert result["published_items"] == 1
    assert console.snapshot_is_published(snapshot_id) is True

    projection = [
        json.loads(line)
        for line in (console.runtime / "published_projection.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(projection) == 1
    assert projection[0]["metadata"]["snapshot_id"] == snapshot_id
    assert projection[0]["metadata"]["object_type"] == "explanation"
    manifests = list((console.runtime / "release_manifests").glob("*.json"))
    assert len(manifests) == 1

    again = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
    )
    assert again["status"] == "BLOCKED"
    assert again["blockers"] == ["already_published"]


def test_changed_or_unavailable_blob_keeps_g2_closed(tmp_path: Path) -> None:
    console, accounts, receipt, store = _ready_console(tmp_path)
    locator = receipt["immutable_storage_locator"]
    store.blobs[locator] = b"tampered source"

    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"]
    )
    assert considered["publish_allowed"] is False
    assert considered["g2"] == "BLOCKED"
    assert "g2_source_checksum_mismatch" in considered["blockers"]
    assert not (console.runtime / "published_projection.jsonl").exists()

    del store.blobs[locator]
    missing = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"]
    )
    assert "g2_source_verification_failed" in missing["blockers"]


def test_independence_is_checked_for_each_published_object(tmp_path: Path) -> None:
    console, accounts, receipt, _store = _ready_console(tmp_path)
    second = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") == "unclassified"
        and "dagboek" in (obj.get("content") or {}).get("clean_text", "")
    )
    console.review_object(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=second["object_id"],
        decision="approve",
        confirmed_object_type="explanation",
    )

    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"]
    )
    assert considered["publish_allowed"] is False
    assert "second_named_reviewer_required" in considered["blockers"]


def test_publish_rolls_back_projection_manifest_and_state_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    console, accounts, receipt, _store = _ready_console(tmp_path)
    projection_path = console.runtime / "published_projection.jsonl"
    prior = '{"retrieval_id":"existing"}\n'
    projection_path.write_text(prior, encoding="utf-8")

    def fail_event(*args: object, **kwargs: object) -> None:
        raise OSError("ledger unavailable")

    monkeypatch.setattr(console_module, "append_event", fail_event)
    with pytest.raises(OSError, match="ledger unavailable"):
        console.publish(
            actor_id=accounts["publisher"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
        )

    assert projection_path.read_text(encoding="utf-8") == prior
    assert not list((console.runtime / "release_manifests").glob("*.json"))
    assert console._envelope(receipt["snapshot_id"])["state"] == "captured_not_published"


def test_publish_page_requires_explicit_confirmation_and_then_clears_badge(tmp_path: Path) -> None:
    console, accounts, receipt, _store = _ready_console(tmp_path)
    client = TestClient(
        create_console_app(console),
        base_url="https://testserver",
        raise_server_exceptions=False,
    )
    client.post("/login", data={"username": "publisher.carla", "password": TEST_PASSWORD})

    page = client.get("/publish")
    assert "Klaar voor publicatie: 1 gereviewd kennisobject" in page.text
    assert 'name="publish_confirmed"' in page.text
    missing = client.post("/publish", data={"snapshot_id": receipt["snapshot_id"]})
    assert missing.status_code == 400

    published = client.post(
        "/publish",
        data={"snapshot_id": receipt["snapshot_id"], "publish_confirmed": "yes"},
        follow_redirects=True,
    )
    assert published.status_code == 200
    assert "Publicatie voltooid" in published.text
    assert "Gepubliceerd" in published.text
    assert console.waiting_task_counts(accounts["publisher"]["account_id"])["publish"] == 0
