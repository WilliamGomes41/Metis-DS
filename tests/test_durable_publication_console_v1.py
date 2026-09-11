"""Regression evidence for the durable published-knowledge authority.

# release-control-evidence: opslag durable canonical authority concurrent stale rollback
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

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
    def __init__(
        self,
        *,
        fail: bool = False,
        before_commit: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.fail = fail
        self.before_commit = before_commit
        self.releases: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []

    def persist_published_release(self, **payload: Any) -> None:
        self.order.append("durable_commit")
        if self.before_commit is not None:
            self.before_commit(payload)
        if self.fail:
            raise CanonicalPublicationStoreError("simulated_durable_failure")
        release_id = str(payload["release_id"])
        prior = self.releases.get(release_id)
        normalized = json.loads(json.dumps(payload, default=str, sort_keys=True))
        if prior is not None and prior != normalized:
            raise CanonicalPublicationStoreError("simulated_release_conflict")
        self.releases[release_id] = normalized

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
                    "canonical_object_hash": (obj.get("provenance") or {}).get("canonical_object_hash"),
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
        rows: list[dict[str, Any]] = []
        for _stamp, payload, obj in sorted(latest_by_object.values(), key=lambda item: item[2]["object_id"]):
            rows.append(
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
            )
        return rows


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


def test_durable_commit_precedes_every_local_publication_artifact(tmp_path: Path) -> None:
    observed: dict[str, Any] = {}
    durable = MemoryCanonicalStore()
    console, accounts, receipt = _ready_console(tmp_path, durable)
    snapshot_id = receipt["snapshot_id"]

    def observe(_payload: dict[str, Any]) -> None:
        observed["envelope_state"] = console._envelope(snapshot_id)["state"]
        observed["projection_exists"] = (console.runtime / "published_projection.jsonl").exists()
        observed["manifest_exists"] = (console.runtime / "release_manifests").exists()
        observed["ledger_has_release"] = "release_published" in (
            console.runtime / "review_ledger.jsonl"
        ).read_text(encoding="utf-8")

    durable.before_commit = observe
    result = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id
    )

    assert result["status"] == "PASS"
    assert observed == {
        "envelope_state": "captured_not_published",
        "projection_exists": False,
        "manifest_exists": False,
        "ledger_has_release": False,
    }


def test_successful_publication_is_persisted_then_projected_from_authority(tmp_path: Path) -> None:
    durable = MemoryCanonicalStore()
    console, accounts, receipt = _ready_console(tmp_path, durable)

    result = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"]
    )

    assert result["status"] == "PASS"
    assert result["canonical_authority"] == "postgres"
    assert result["local_projection"] == "derived"
    stored = durable.releases[result["release_id"]]
    assert stored["snapshot_id"] == receipt["snapshot_id"]
    assert stored["source_sha256"] == receipt["sha256"]
    assert stored["source_locator"] == receipt["immutable_storage_locator"]
    assert len(stored["objects"]) == 1
    projection = [
        json.loads(line)
        for line in (console.runtime / "published_projection.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(projection) == 1
    assert projection[0]["metadata"]["snapshot_id"] == receipt["snapshot_id"]


def test_durable_failure_creates_no_local_publication_state(tmp_path: Path) -> None:
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
    assert durable.releases == {}


def test_local_copy_failure_does_not_undo_durable_release_and_retry_reconciles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    durable = MemoryCanonicalStore()
    console, accounts, receipt = _ready_console(tmp_path, durable)
    snapshot_id = receipt["snapshot_id"]

    import src.durable_publication_console_v1 as module

    real_replace = module.atomic_replace_projection
    calls = {"count": 0}

    def fail_once(path: Path, rows: Any) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("simulated local projection failure")
        real_replace(path, rows)

    monkeypatch.setattr(module, "atomic_replace_projection", fail_once)
    with pytest.raises(Exception, match="durable_publication_local_copy_failed"):
        console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id)

    assert len(durable.releases) == 1
    assert console._envelope(snapshot_id)["state"] == "captured_not_published"
    assert not (console.runtime / "published_projection.jsonl").exists()

    result = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=snapshot_id)
    assert result["status"] == "PASS"
    assert result["local_projection"] == "reconciled"
    assert len(durable.releases) == 1
    assert console._envelope(snapshot_id)["state"] == "published"
    assert (console.runtime / "published_projection.jsonl").is_file()


def test_startup_reconciliation_flows_from_authority_to_local_copy(tmp_path: Path) -> None:
    durable = MemoryCanonicalStore()
    console, accounts, receipt = _ready_console(tmp_path, durable)
    result = console.publish(
        actor_id=accounts["publisher"]["account_id"], snapshot_id=receipt["snapshot_id"]
    )
    assert result["status"] == "PASS"

    projection_path = console.runtime / "published_projection.jsonl"
    projection_path.unlink()
    envelope = console._envelope(receipt["snapshot_id"])
    envelope["state"] = "captured_not_published"
    envelope.pop("release_id", None)
    envelope.pop("release_version", None)
    envelope.pop("published_at", None)
    envelope.pop("published_by", None)
    console._save_envelopes()

    restarted = DurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime",
        immutable_source_store=console.immutable_source_store,
        canonical_publication_store=durable,  # type: ignore[arg-type]
    )
    report = restarted.reconcile_durable_publications()
    assert report == {"checked": 1, "reconciled": 1}
    assert projection_path.is_file()
    assert restarted._envelope(receipt["snapshot_id"])["release_id"] == result["release_id"]
    assert restarted._envelope(receipt["snapshot_id"])["state"] == "published"

    again = restarted.reconcile_durable_publications()
    assert again == {"checked": 1, "reconciled": 1}
    ledger = (restarted.runtime / "review_ledger.jsonl").read_text(encoding="utf-8")
    assert ledger.count(result["release_id"]) == 1


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
