"""Regression evidence for the durable published-knowledge authority.

# release-control-evidence: opslag durable canonical authority concurrent stale rollback
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.canonical_publication_postgres_v1 import (
    CanonicalPublicationStoreError,
    expected_release_item_set,
    registry_update_required,
)
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.g2_source_store import G2SourceStoreError, build_g2_locator

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
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.releases: dict[str, dict[str, Any]] = {}

    def persist_published_release(self, **payload: Any) -> None:
        if self.fail:
            raise CanonicalPublicationStoreError("simulated_durable_failure")
        release_id = str(payload["release_id"])
        prior = self.releases.get(release_id)
        normalized = json.loads(json.dumps(payload, default=str, sort_keys=True))
        if prior is not None and prior != normalized:
            raise CanonicalPublicationStoreError("simulated_release_conflict")
        self.releases[release_id] = normalized


def _ready_console(tmp_path: Path, durable: MemoryCanonicalStore) -> tuple[DurablePublicationConsole, dict[str, dict], dict]:
    source = MemorySourceStore()
    console = DurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
        immutable_source_store=source,
        canonical_publication_store=durable,  # type: ignore[arg-type]
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
        named_reviewers=[accounts["researcher"]["account_id"], accounts["reviewer"]["account_id"]],
    )
    target = next(obj for obj in console.snapshot_objects(receipt["snapshot_id"]) if obj.get("object_type") == "unclassified")
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="explanation",
    )
    return console, accounts, receipt


def test_successful_publication_is_persisted_in_durable_authority(tmp_path: Path) -> None:
    durable = MemoryCanonicalStore()
    console, accounts, receipt = _ready_console(tmp_path, durable)

    result = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"]
    )

    assert result["status"] == "PASS"
    assert result["canonical_authority"] == "postgres"
    stored = durable.releases[result["release_id"]]
    assert stored["snapshot_id"] == receipt["snapshot_id"]
    assert stored["source_sha256"] == receipt["sha256"]
    assert stored["source_locator"] == receipt["immutable_storage_locator"]
    assert len(stored["objects"]) == 1


def test_durable_failure_rolls_back_local_publication(tmp_path: Path) -> None:
    durable = MemoryCanonicalStore(fail=True)
    console, accounts, receipt = _ready_console(tmp_path, durable)
    snapshot_id = receipt["snapshot_id"]

    with pytest.raises(Exception, match="simulated_durable_failure"):
        console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id)

    assert console._envelope(snapshot_id)["state"] == "captured_not_published"
    assert not (console.runtime / "published_projection.jsonl").exists()
    assert not list((console.runtime / "release_manifests").glob("*.json"))
    ledger = (console.runtime / "review_ledger.jsonl").read_text(encoding="utf-8")
    assert "release_published" not in ledger


def test_startup_reconciliation_is_idempotent(tmp_path: Path) -> None:
    first_store = MemoryCanonicalStore()
    console, accounts, receipt = _ready_console(tmp_path, first_store)
    result = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"]
    )
    assert result["status"] == "PASS"

    replacement = MemoryCanonicalStore()
    restarted = DurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
        immutable_source_store=console.immutable_source_store,
        canonical_publication_store=replacement,  # type: ignore[arg-type]
    )
    report = restarted.reconcile_durable_publications()
    assert report == {"checked": 1, "reconciled": 1}
    assert result["release_id"] in replacement.releases

    again = restarted.reconcile_durable_publications()
    assert again == {"checked": 1, "reconciled": 1}
    assert len(replacement.releases) == 1


def test_reconciliation_refuses_tampered_manifest(tmp_path: Path) -> None:
    durable = MemoryCanonicalStore()
    console, accounts, receipt = _ready_console(tmp_path, durable)
    result = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"]
    )
    manifest_path = console.runtime / "release_manifests" / f'{result["release_id"]}.json'
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    restarted = DurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
        immutable_source_store=console.immutable_source_store,
        canonical_publication_store=MemoryCanonicalStore(),  # type: ignore[arg-type]
    )
    with pytest.raises(Exception, match="published_release_manifest_invalid"):
        restarted.reconcile_durable_publications()


def test_registry_replay_never_moves_newer_pointer_backwards() -> None:
    current = {
        "release_id": "release-new",
        "published_at": "2026-09-11T12:00:00+00:00",
    }
    assert registry_update_required(
        current,
        release_id="release-old",
        published_at="2026-09-10T12:00:00+00:00",
    ) is False
    assert registry_update_required(
        current,
        release_id="release-newer",
        published_at="2026-09-12T12:00:00+00:00",
    ) is True
    assert registry_update_required(
        current,
        release_id="release-new",
        published_at="2026-09-11T12:00:00+00:00",
    ) is False


def test_release_item_identity_includes_exact_version_and_hash() -> None:
    rows = [
        {
            "object_id": "ko-1",
            "object_version": "1.2",
            "provenance": {"content_hash": "a" * 64},
        },
        {
            "object_id": "ko-2",
            "object_version": "3.0",
            "provenance": {"content_hash": "b" * 64},
        },
    ]
    assert expected_release_item_set(rows) == {
        ("ko-1", "1.2", "a" * 64),
        ("ko-2", "3.0", "b" * 64),
    }
