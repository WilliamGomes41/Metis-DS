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
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


def _system(tmp_path, console=None):
    console = console or ReviewClosureConsole(
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


@pytest.mark.parametrize("backend", ["local", "postgres"])
def test_blocked_passage_ui_leads_to_source_repair_and_new_pending_version(tmp_path, backend, request):
    from html.parser import HTMLParser
    from tests.test_deterministic_review_repair_v1 import _review_payload

    class Inputs(HTMLParser):
        def __init__(self, text):
            super().__init__()
            self.inputs = []
            self.feed(text)

        def handle_starttag(self, tag, attrs):
            if tag == "input":
                self.inputs.append(dict(attrs))

    from tests.test_review_batch_atomic_postgres import _console
    config = request.getfixturevalue("workflow_postgres") if backend == "postgres" else None
    runtime = _console(tmp_path, config) if config else None
    console, client, _researcher, _reviewer, sid, objects = _system(tmp_path, runtime)
    obj = objects[0]
    rows = console._load_objects(sid)
    target = next(row for row in rows if row["object_id"] == obj["object_id"])
    target.setdefault("metadata", {}).setdefault("admission", {}).update(
        gate_result="blocked", reason_codes=["source_context_incomplete"]
    )
    console._save_objects(sid, rows)
    before = console.snapshot_objects(sid)
    card = client.get(f'/review?document={sid}&object={obj["object_id"]}&task=repair')
    assert card.status_code == 200
    assert "Eerst de passage herstellen" in card.text
    inputs = Inputs(card.text).inputs
    approval = next(row for row in inputs if row.get("name") == "eindoordeel" and row.get("value") == "goedkeuren")
    correction = next(row for row in inputs if row.get("name") == "eindoordeel" and row.get("value") == "goedkeuren_na_correctie")
    assert "disabled" in approval
    assert "disabled" not in correction
    assert console.snapshot_objects(sid) == before
    inventory = client.get(f'/review?document={sid}&task=repair')
    assert "Bekijk bronpassage" in inventory.text

    approval_payload = _review_payload(console, sid, target)
    approval_payload.update(suitability="ja", eindoordeel="goedkeuren")
    rejected = client.post("/review", data=approval_payload)
    assert rejected.status_code == 400
    assert "blocked_candidate_not_reviewable" in rejected.text
    assert console.snapshot_objects(sid) == before
    specification = client.post("/review", data=_review_payload(console, sid, target))
    assert specification.status_code == 200
    assert "Er is nog niets gewijzigd" in specification.text
    assert console.snapshot_objects(sid) == before
    payload = {row["name"]: row.get("value", "") for row in Inputs(specification.text).inputs if row.get("type") == "hidden"}
    fragments = {str(ref.get("raw_object_id") or "") for ref in obj["provenance"]["source_fragments"]}
    payload["source_unit_ids"] = [unit["unit_id"] for unit in console.source_units(snapshot_id=sid, object_id=obj["object_id"]) if unit["fragment_id"] in fragments]
    assert payload["source_unit_ids"]
    response = client.post("/review/resolve", data=payload, follow_redirects=False)
    assert response.status_code == 303, response.text
    repaired = console._current_object(sid, obj["object_id"])
    assert repaired["object_version"] != obj["object_version"]
    assert repaired["governance"]["validation_status"] == "needs_review"
    restarted = _console(tmp_path, config) if config else ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert restarted._current_object(sid, obj["object_id"]) == repaired
