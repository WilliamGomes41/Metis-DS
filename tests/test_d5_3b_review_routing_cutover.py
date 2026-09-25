"""D5.3B Review routing cutover and second-review interaction regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.integrity_kernel import compute_canonical_object_hash, stamp_canonical_hashes
from src.operations_console_app import create_console_app, normalize_review_task
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.publish_authorization_v1 import tuple_record
from src.review_duty_v1 import exact_current_approver_ids
from src.review_ledger import read_events
from src.review_workboard_v1 import _work_item_from_counts, install_review_workboard


PASSWORD = "d53b-secret"
HTML = b"""<!doctype html><html><body><h1>Advies</h1><p>Gebruik interventie A bij verhoogd risico.</p></body></html>"""


def _console(tmp_path: Path) -> tuple[OperationsConsole, dict[str, dict], str, str]:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime" / "console",
    )
    researcher = console.create_account(
        username="researcher.d53b",
        password=PASSWORD,
        roles=("researcher", "reviewer"),
    )
    reviewer_a = console.create_account(
        username="reviewer.a.d53b",
        password=PASSWORD,
        roles=("reviewer",),
    )
    reviewer_b = console.create_account(
        username="reviewer.b.d53b",
        password=PASSWORD,
        roles=("reviewer",),
    )
    result = console.ingest(
        actor_id=researcher["account_id"],
        filename="d53b.html",
        data=HTML,
        content_type="text/html",
        ingest_kind="new",
        title="D5.3B fixture",
        version="1.0",
        date="2026-09-25",
        live_url="https://example.test/d53b",
        class_="richtlijn",
        family="test",
        named_reviewers=[
            reviewer_a["account_id"],
            reviewer_b["account_id"],
        ],
    )
    snapshot_id = result["snapshot_id"]

    rows = console._load_objects(snapshot_id)
    target = next(
        row
        for row in rows
        if row.get("object_type") != "document"
        and str((row.get("content") or {}).get("clean_text") or "").strip()
    )
    target["object_type"] = "recommendation"
    target["confirmed_object_type"] = "recommendation"
    target.setdefault("governance", {})["validation_status"] = "approved"
    target["governance"]["second_review"] = {
        "required": True,
        "status": "pending",
        "reviewer": None,
        "review_date": None,
        "snapshot_hash": None,
    }
    target["risk"] = {
        "level": "high",
        "risk_level": "high",
        "requires_second_review": True,
        "risk_fields": ["contraindication"],
    }
    stamp_canonical_hashes(target)
    console._save_objects(snapshot_id, rows)

    first_binding = tuple_record(
        object_id=target["object_id"],
        object_version=target["object_version"],
        canonical_object_hash=compute_canonical_object_hash(target),
        confirmed_object_type=target["confirmed_object_type"],
        reviewer=reviewer_a["username"],
        reviewer_id=reviewer_a["account_id"],
        decision="approve",
    )
    console._bindings[snapshot_id] = [first_binding]
    console._save_bindings()

    return (
        console,
        {
            "researcher": researcher,
            "reviewer_a": reviewer_a,
            "reviewer_b": reviewer_b,
        },
        snapshot_id,
        str(target["object_id"]),
    )


def test_legacy_task_names_only_normalize_to_canonical_tasks() -> None:
    assert normalize_review_task("headings") == "structure"
    assert normalize_review_task("individual") == "contextual"
    assert normalize_review_task("together") == "batch"
    assert normalize_review_task("control") == "repair"
    assert normalize_review_task("decisions") == "history"
    assert normalize_review_task("closure") == "disposition"
    assert normalize_review_task("second_review") == "second_review"
    for canonical in (
        "structure",
        "contextual",
        "batch",
        "second_review",
        "repair",
        "history",
        "disposition",
    ):
        assert normalize_review_task(canonical) == canonical
    assert normalize_review_task("unknown") == ""


def test_workboard_uses_actionable_duties_and_waiting_state() -> None:
    common = dict(
        envelope={"snapshot_id": "snap-1"},
        snapshot_id="snap-1",
        lifecycle_status={
            "workflow_status": "in_review",
            "release_status": "none",
            "serving_status": "inactive",
            "presentation_status": "in_review",
        },
        heading_pending=9,
        individual_pending=9,
        normal_passages=9,
        normal_batches=3,
        blocked_count=0,
        closure_gap_ids=[],
        closure_gap_count=0,
        source_passage_review_complete=True,
        review_duties=1,
        first_review_duties=0,
        second_review_duties=1,
        structure_review_duties=0,
        contextual_review_duties=1,
        batch_review_duties=0,
    )
    waiting = _work_item_from_counts(
        **common,
        actionable_review_duties=0,
        waiting_for_reviewer_duties=1,
        actionable_structure_duties=0,
        actionable_contextual_duties=0,
        actionable_batch_duties=0,
        actionable_second_review_duties=0,
    )
    assert waiting["remaining_review_items"] == 1
    assert waiting["work_state"] == "waiting_for_reviewer"
    assert waiting["next_task"] == ""

    actionable = _work_item_from_counts(
        **common,
        actionable_review_duties=1,
        waiting_for_reviewer_duties=0,
        actionable_structure_duties=0,
        actionable_contextual_duties=0,
        actionable_batch_duties=0,
        actionable_second_review_duties=1,
    )
    assert actionable["work_state"] == "review"
    assert actionable["next_task"] == "second_review"
    assert actionable["next_href"].endswith("task=second_review")


def test_second_review_approval_preserves_canonical_tuple_and_is_idempotent(tmp_path: Path) -> None:
    console, accounts, snapshot_id, object_id = _console(tmp_path)
    before = next(row for row in console.snapshot_objects(snapshot_id) if row["object_id"] == object_id)
    before_version = before["object_version"]
    before_hash = compute_canonical_object_hash(before)

    console.approve_second_review(
        actor_id=accounts["reviewer_b"]["account_id"],
        snapshot_id=snapshot_id,
        object_id=object_id,
        expected_revision=console.objects_revision(snapshot_id),
    )

    after = next(row for row in console.snapshot_objects(snapshot_id) if row["object_id"] == object_id)
    assert after["object_version"] == before_version
    assert compute_canonical_object_hash(after) == before_hash
    assert after["governance"]["second_review"]["status"] == "approved"
    assert after["governance"]["second_review"]["reviewer"] == accounts["reviewer_b"]["username"]

    bindings = console.object_review_bindings(snapshot_id)
    assert set(exact_current_approver_ids(after, bindings)) == {
        accounts["reviewer_a"]["account_id"],
        accounts["reviewer_b"]["account_id"],
    }
    events = [row for row in read_events(console._ledger_path) if row["event_type"] == "second_review_approve"]
    assert len(events) == 1

    console.approve_second_review(
        actor_id=accounts["reviewer_b"]["account_id"],
        snapshot_id=snapshot_id,
        object_id=object_id,
    )
    assert len([
        row for row in read_events(console._ledger_path)
        if row["event_type"] == "second_review_approve"
    ]) == 1


def test_first_reviewer_cannot_self_approve_second_review(tmp_path: Path) -> None:
    console, accounts, snapshot_id, object_id = _console(tmp_path)

    with pytest.raises(ConsoleError, match="independent_second_reviewer_required"):
        console.approve_second_review(
            actor_id=accounts["reviewer_a"]["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            expected_revision=console.objects_revision(snapshot_id),
        )


def test_stale_second_review_write_does_not_add_binding(tmp_path: Path) -> None:
    console, accounts, snapshot_id, object_id = _console(tmp_path)
    stale = console.objects_revision(snapshot_id)

    rows = console._load_objects(snapshot_id)
    document = next(row for row in rows if row.get("object_type") == "document")
    document.setdefault("metadata", {})["concurrent_touch"] = True
    stamp_canonical_hashes(document)
    console._save_objects(snapshot_id, rows)

    before = list(console.object_review_bindings(snapshot_id))
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        console.approve_second_review(
            actor_id=accounts["reviewer_b"]["account_id"],
            snapshot_id=snapshot_id,
            object_id=object_id,
            expected_revision=stale,
        )
    after = console.object_review_bindings(snapshot_id)
    assert after == before


def test_second_review_http_surface_is_read_only_for_canonical_semantics(tmp_path: Path) -> None:
    console, accounts, snapshot_id, object_id = _console(tmp_path)
    app = create_console_app(console)
    install_review_workboard(app, console)
    client = TestClient(app)

    login = client.post(
        "/login",
        data={"username": accounts["reviewer_b"]["username"], "password": PASSWORD},
    )
    assert login.status_code == 200

    lane = client.get(f"/review?document={snapshot_id}&task=second_review")
    assert lane.status_code == 200
    assert "Tweede beoordelingen" in lane.text
    assert f"object={object_id}" in lane.text
    assert "task=second_review" in lane.text

    card = client.get(
        f"/review?document={snapshot_id}&object={object_id}&task=second_review"
    )
    assert card.status_code == 200
    assert "Onafhankelijke tweede beoordeling" in card.text
    assert "Tweede beoordeling goedkeuren" in card.text
    assert 'action="/review/second-review"' in card.text
    assert '<input type="radio" name="type_action"' not in card.text
    assert '<input type="checkbox" name="relation_choice"' not in card.text
    assert "Wat voor informatie is dit?" not in card.text


def test_legacy_individual_url_redirects_into_contextual_surface(tmp_path: Path) -> None:
    console, accounts, snapshot_id, _object_id = _console(tmp_path)
    app = create_console_app(console)
    install_review_workboard(app, console)
    client = TestClient(app)
    client.post(
        "/login",
        data={"username": accounts["reviewer_b"]["username"], "password": PASSWORD},
    )

    response = client.get(f"/review?document={snapshot_id}&task=individual")
    assert response.status_code == 200
    assert "In samenhang" in response.text or "Belangrijke passages beoordelen" in response.text
    assert "task=individual" not in response.text
