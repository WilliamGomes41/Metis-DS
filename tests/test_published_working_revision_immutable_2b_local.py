"""Repair #220 local authority and curation-boundary regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.durable_publication_console_v1 import DurablePublicationConsole
from src.operations_console_v1 import ConsoleError, _atomic_write
from src.review.review_closure_v1 import PUBLISHED_WORKING_REVISION_IMMUTABLE


pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


class _ReleaseAuthority:
    def __init__(self) -> None:
        self.releases: dict[str, dict[str, Any]] = {}

    def release_for_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        release = self.releases.get(snapshot_id)
        return deepcopy(release) if release is not None else None

    def active_publication_rows(self) -> list[dict[str, Any]]:
        return []


def _system(tmp_path: Path):
    authority = _ReleaseAuthority()
    console = DurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
        canonical_publication_store=authority,  # type: ignore[arg-type]
    )
    researcher = console.create_account(
        username="repair2b-researcher", password="repair2b-secret", roles=("researcher",)
    )
    reviewer = console.create_account(
        username="repair2b-reviewer", password="repair2b-secret", roles=("reviewer",)
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="repair2b.html",
        content_type="text/html",
        data=(
            b"<html><body><h1>Richtlijn</h1><h2>1 Zorg</h2>"
            b"<p>Bespreek passende ondersteuning met de client.</p>"
            b"<p>Evalueer daarna de gemaakte keuze met de client.</p>"
            b"</body></html>"
        ),
        ingest_kind="new",
        title="Repair 2b fixture",
        version="1.0",
        date="2026-09-16",
        live_url="",
        class_="richtlijn",
        family="repair2b",
        named_reviewers=[reviewer["account_id"]],
    )
    return console, authority, reviewer, str(receipt["snapshot_id"])


def _release(console: DurablePublicationConsole, snapshot_id: str) -> dict[str, Any]:
    envelope = console._envelope(snapshot_id)
    return {
        "release_id": "release-repair2b",
        "release_version": "1.0-repair2b",
        "release_owner": "publisher",
        "published_at": "2026-09-16T11:30:00+00:00",
        "snapshot_id": snapshot_id,
        "source_sha256": str(envelope.get("sha256") or ""),
        "source_locator": str(envelope.get("immutable_storage_locator") or ""),
        "objects": [
            {"object_id": str(row["object_id"]), "object_version": str(row["object_version"])}
            for row in console.snapshot_objects(snapshot_id)
        ],
    }


def test_canonical_authority_does_not_fall_back_to_stale_local_publication(tmp_path: Path) -> None:
    console, authority, _reviewer, snapshot_id = _system(tmp_path)
    stale = deepcopy(console._envelope(snapshot_id))
    stale.update({"state": "published", "published": True, "release_id": "stale-local-release"})
    console._envelopes[snapshot_id] = stale
    _atomic_write(console._envelopes_path, console._envelopes)

    assert authority.release_for_snapshot(snapshot_id) is None
    assert console.snapshot_is_published(snapshot_id) is False

    restarted = DurablePublicationConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
        canonical_publication_store=authority,  # type: ignore[arg-type]
    )
    assert restarted._envelope(snapshot_id)["state"] == "published"
    assert restarted.snapshot_is_published(snapshot_id) is False


def test_central_guard_blocks_type_and_relation_helpers_after_release(tmp_path: Path) -> None:
    console, authority, reviewer, snapshot_id = _system(tmp_path)
    targets = [
        row for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") not in {"document", "heading"}
        and row.get("proposed_object_type") != "heading"
    ]
    assert targets
    target = targets[0]
    before = console.snapshot_objects(snapshot_id)
    revision = console.objects_revision(snapshot_id)
    authority.releases[snapshot_id] = _release(console, snapshot_id)

    with pytest.raises(ConsoleError) as caught_type:
        console.confirm_object_type(
            actor_id=reviewer["account_id"], snapshot_id=snapshot_id,
            object_id=str(target["object_id"]), confirmed_object_type="explanation",
            expected_revision=revision,
        )
    assert caught_type.value.code == PUBLISHED_WORKING_REVISION_IMMUTABLE

    with pytest.raises(ConsoleError) as caught_relation:
        console.confirm_relations(
            actor_id=reviewer["account_id"], snapshot_id=snapshot_id,
            object_id=str(target["object_id"]), relations=[], expected_revision=revision,
        )
    assert caught_relation.value.code == PUBLISHED_WORKING_REVISION_IMMUTABLE
    assert console.snapshot_objects(snapshot_id) == before
    assert console.objects_revision(snapshot_id) == revision


def test_release_copy_preserves_existing_historical_state(tmp_path: Path) -> None:
    console, authority, _reviewer, snapshot_id = _system(tmp_path)
    release = _release(console, snapshot_id)
    authority.releases[snapshot_id] = release
    historical = deepcopy(console._envelope(snapshot_id))
    historical.update({"state": "withdrawn", "published": False})
    console._envelopes[snapshot_id] = historical
    _atomic_write(console._envelopes_path, console._envelopes)

    console._apply_local_release_copy(release, [])
    current = console._envelope(snapshot_id)
    assert current["state"] == "withdrawn"
    assert current["release_id"] == release["release_id"]
    assert console.snapshot_is_published(snapshot_id) is True
