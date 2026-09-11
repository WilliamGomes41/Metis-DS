"""Final Review closure regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.closed_review_loop_v1 import ClosedLoopReviewConsole, install_closed_review_routes
from src.deterministic_review_repair_v1 import (
    REPAIR_SOURCE_UNITS,
    install_deterministic_review_repair_routes,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.review_closure_v1 import ReviewClosureConsole, harden_legacy_repair_routes
from src.review_ledger import read_events


def _system(tmp_path):
    console = ReviewClosureConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    researcher = console.create_account(
        username="anne", password="anne-secret", roles=("researcher",)
    )
    reviewer = console.create_account(
        username="bert", password="bert-secret", roles=("reviewer",)
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="bron.html",
        content_type="text/html",
        data=(
            b"<html><body><h1>Richtlijn</h1><h2>1 Zorg</h2>"
            b"<p>De verpleegkundige bespreekt passende ondersteuning met de client.</p>"
            b"<p>Daarna wordt de keuze samen met de client geevalueerd.</p>"
            b"</body></html>"
        ),
        ingest_kind="new",
        title="Bron",
        version="1.0",
        date="2026-09-11",
        live_url="",
        class_="richtlijn",
        family="zorg",
        named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    objects = [
        row
        for row in console.snapshot_objects(sid)
        if row.get("object_type") not in {"document", "heading"}
        and row.get("proposed_object_type") != "heading"
    ]
    assert objects
    app = create_console_app(console)
    install_deterministic_review_repair_routes(app, console)
    install_closed_review_routes(app, console)
    harden_legacy_repair_routes(app, console)
    client = TestClient(app)
    client.post("/login", data={"username": "bert", "password": "bert-secret"})
    return console, client, researcher, reviewer, sid, objects


def test_legacy_free_text_repair_is_not_writable(tmp_path):
    console, client, _researcher, _reviewer, sid, objects = _system(tmp_path)
    obj = objects[0]

    response = client.post(
        "/review/repair/source",
        data={
            "snapshot_id": sid,
            "object_id": obj["object_id"],
            "snapshot_revision": console.objects_revision(sid),
            "corrected_text": "vrije tekst",
            "reason": "mag niet",
        },
    )
    assert response.status_code == 404

    with pytest.raises(ConsoleError, match="legacy_free_text_repair_disabled"):
        console.repair_source(
            actor_id="irrelevant",
            snapshot_id=sid,
            object_id=obj["object_id"],
            corrected_text="vrije tekst",
            reason="mag niet",
            expected_revision=console.objects_revision(sid),
        )


def test_existing_recommendation_strength_does_not_force_classification_repair(tmp_path):
    console, _client, _researcher, _reviewer, sid, objects = _system(tmp_path)
    obj = objects[0]
    current = dict(obj)
    current["confirmed_recommendation_strength"] = "sterk"
    original = console._current_object
    console._current_object = lambda snapshot_id, object_id: current  # type: ignore[method-assign]
    try:
        kind = console.repair_kind_for_submission(
            {
                "snapshot_id": sid,
                "object_id": obj["object_id"],
                "suitability": "ja",
                "type_action": "dit_klopt",
                "documentpositie_action": "dit_klopt",
                "recommendation_strength": "sterk",
            }
        )
    finally:
        console._current_object = original  # type: ignore[method-assign]
    assert kind == REPAIR_SOURCE_UNITS


def test_source_repair_keeps_revision_patch_hash_and_records_exact_selection(tmp_path):
    console, _client, _researcher, reviewer, sid, objects = _system(tmp_path)
    obj = objects[0]
    units = console.source_units(snapshot_id=sid, object_id=obj["object_id"])
    own_fragment_ids = {
        str(ref.get("raw_object_id") or "")
        for ref in (obj.get("provenance") or {}).get("source_fragments") or []
    }
    selected = [row for row in units if row["fragment_id"] in own_fragment_ids]
    assert selected
    chosen = [selected[0]["unit_id"]]

    repaired = console.submit_review_resolution(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=obj["object_id"],
        expected_revision=console.objects_revision(sid),
        suitability="mist_context",
        comment="Gebruik deze exacte bronzin.",
        repair_kind=REPAIR_SOURCE_UNITS,
        source_unit_ids=chosen,
    )

    events = read_events(console._ledger_path)
    revision = next(
        event
        for event in reversed(events)
        if event.get("event_type") == "revision_created"
        and event.get("object_id") == obj["object_id"]
    )
    assert repaired["provenance"]["revision_patch_hash"] == revision["details"]["revision_patch_hash"]

    evidence = next(
        event
        for event in reversed(events)
        if event.get("event_type") == "review_audit_evidence"
        and (event.get("details") or {}).get("decision") == "repair_source_units"
    )
    spec = evidence["details"]["repair_spec"]
    assert spec["repair_kind"] == REPAIR_SOURCE_UNITS
    assert spec["source_units"] == [
        {
            "unit_id": selected[0]["unit_id"],
            "fragment_id": selected[0]["fragment_id"],
            "fragment_hash": selected[0]["fragment_hash"],
        }
    ]


def test_startup_migration_reopens_legacy_revise_without_editing_content(tmp_path):
    console, _client, _researcher, reviewer, sid, objects = _system(tmp_path)
    obj = objects[0]
    before_text = str((obj.get("content") or {}).get("clean_text") or "")

    # Simulate a persisted pre-closure revise row through the previous policy.
    ClosedLoopReviewConsole.review_object(
        console,
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=obj["object_id"],
        decision="revise",
        suitability="mist_context",
        eindoordeel="goedkeuren_na_correctie",
        comment="legacy revise",
        expected_revision=console.objects_revision(sid),
    )
    assert console._current_object(sid, obj["object_id"])["governance"]["validation_status"] == "revise"

    migrated = console.migrate_legacy_revise_to_review()
    current = console._current_object(sid, obj["object_id"])
    assert migrated == 1
    assert current["governance"]["validation_status"] == "needs_review"
    assert str((current.get("content") or {}).get("clean_text") or "") == before_text
    assert console.migrate_legacy_revise_to_review() == 0
