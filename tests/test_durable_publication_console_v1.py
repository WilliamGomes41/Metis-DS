"""Regression evidence for the durable published-knowledge authority.

# release-control-evidence: opslag durable canonical authority concurrent stale rollback
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest

from src.publication.canonical_publication_postgres_v1 import (
    CanonicalPublicationStoreError,
    expected_release_item_set,
    registry_update_required,
)
from src.publication.durable_publication_console_v1 import DurablePublicationConsole
from src.g2_source_store import G2SourceStoreError, build_g2_locator
from src.operations_console_v1 import review_lane
from src.vorming.passage_register_v1 import passage_register_of
from src.review.review_disposition_v1 import definitive_review_disposition

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


def _ready_console(tmp_path: Path, *, production_console, isolated=False):
    console = production_console(root=tmp_path, source_store=tmp_path / "sources" / "private",
                                 runtime=tmp_path / "runtime", immutable_source_store=MemorySourceStore(),
                                 processing_binder=bind_fixture_selections, isolated=isolated)
    return _prepare_console(console)


def _prepare_console(console):
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
        named_reviewers=[accounts["researcher"]["account_id"], accounts["reviewer"]["account_id"]],
    )
    snapshot_id = receipt["snapshot_id"]
    target = next(obj for obj in console.snapshot_objects(snapshot_id) if obj.get("object_type") == "unclassified")
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
        if (obj.get("governance") or {}).get("validation_status") in {"approved", "rejected"}:
            continue
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=snapshot_id,
            object_id=obj["object_id"],
            decision="reject",
            comment="Testfixture: candidate definitief afgehandeld en niet publiceren.",
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
            comment="Testfixture: inhoudelijke bronpassage definitief afgehandeld.",
        )
    return console, accounts, receipt


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
