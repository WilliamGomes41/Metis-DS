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
    DeterministicRepairReviewConsole,
    REPAIR_MERGE_OBJECTS,
    REPAIR_SOURCE_UNITS,
    install_deterministic_review_repair_routes,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.review_closure_v1 import ReviewClosureConsole, harden_legacy_repair_routes
from src.review_ledger import read_events
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


@pytest.mark.parametrize("console_type", [DeterministicRepairReviewConsole, ReviewClosureConsole])
@pytest.mark.parametrize("repair_kind", [REPAIR_SOURCE_UNITS, REPAIR_MERGE_OBJECTS])
def test_repair_finalization_preserves_hash_policy_restart_and_stale_replay(
    tmp_path, console_type, repair_kind,
):
    from src.integrity_kernel import stable_hash, schema_errors, compute_canonical_object_hash
    from tests.test_deterministic_review_repair_v1 import _system as repair_system

    console, _, _, reviewer, sid, objects = repair_system(tmp_path, console_type)
    obj = objects[0]
    command = dict(
        actor_id=reviewer["account_id"], snapshot_id=sid, object_id=obj["object_id"],
        expected_revision=console.objects_revision(sid), comment="Exacte bronselectie.",
        repair_kind=repair_kind,
    )
    if repair_kind == REPAIR_SOURCE_UNITS:
        fragment_ids = {ref["raw_object_id"] for ref in obj["provenance"]["source_fragments"]}
        units = [unit for unit in console.source_units(snapshot_id=sid, object_id=obj["object_id"])
                 if unit["fragment_id"] in fragment_ids]
        command.update(suitability="mist_context", source_unit_ids=[unit["unit_id"] for unit in units])
    else:
        command.update(suitability="samenvoegen", merge_object_ids=[objects[1]["object_id"]])

    repaired = console.submit_review_resolution(**command)
    events = read_events(console._ledger_path)
    revision_event = next(event for event in reversed(events)
                          if event.get("event_type") == "revision_created"
                          and event.get("object_id") == obj["object_id"])
    if console_type is ReviewClosureConsole:
        expected_hash = revision_event["details"]["revision_patch_hash"]
    elif repair_kind == REPAIR_SOURCE_UNITS:
        expected_hash = stable_hash({
            "repair_kind": REPAIR_SOURCE_UNITS,
            "source_unit_ids": command["source_unit_ids"],
            "source_fragment_ids": list(dict.fromkeys(unit["fragment_id"] for unit in units)),
            "text": repaired["content"]["clean_text"],
        })
    else:
        expected_hash = stable_hash({
            "repair_kind": REPAIR_MERGE_OBJECTS,
            "merge_object_ids": command["merge_object_ids"],
            "merged_text": repaired["content"]["clean_text"],
        })
    assert repaired["provenance"]["revision_patch_hash"] == expected_hash
    assert repaired["provenance"]["canonical_object_hash"] == compute_canonical_object_hash(repaired)
    assert schema_errors(repaired, console.schema_path) == []
    assert repaired["governance"]["validation_status"] == "needs_review"
    before = console.snapshot_objects(sid)
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        console.submit_review_resolution(**command)
    assert console.snapshot_objects(sid) == before
    assert read_events(console._ledger_path) == events
    restarted = console_type(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert restarted._current_object(sid, obj["object_id"]) == repaired


@pytest.mark.parametrize("console_type", [DeterministicRepairReviewConsole, ReviewClosureConsole])
def test_failure_after_prepared_correction_commit_rolls_back_whole_repair(tmp_path, monkeypatch, console_type):
    from tests.test_deterministic_review_repair_v1 import _system as repair_system

    console, _, _, reviewer, sid, objects = repair_system(tmp_path, console_type)
    obj = objects[0]
    units = console.source_units(snapshot_id=sid, object_id=obj["object_id"])
    fragment_ids = {ref["raw_object_id"] for ref in obj["provenance"]["source_fragments"]}
    selected = [unit["unit_id"] for unit in units if unit["fragment_id"] in fragment_ids]
    before = console.snapshot_objects(sid)
    events = read_events(console._ledger_path)
    revision = console.objects_revision(sid)
    commit = console._commit_prepared_store

    def fail_after_commit(**kwargs):
        commit(**kwargs)
        if kwargs.get("ledger_fn") is not None:
            raise RuntimeError("injected_after_finalization")

    monkeypatch.setattr(console, "_commit_prepared_store", fail_after_commit)
    with pytest.raises(RuntimeError, match="injected_after_finalization"):
        console.submit_review_resolution(
            actor_id=reviewer["account_id"], snapshot_id=sid, object_id=obj["object_id"],
            expected_revision=revision, suitability="mist_context", comment="Exacte bronselectie.",
            repair_kind=REPAIR_SOURCE_UNITS, source_unit_ids=selected,
        )
    assert console.snapshot_objects(sid) == before
    assert console.objects_revision(sid) == revision
    assert read_events(console._ledger_path) == events
    restarted = console_type(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert restarted.snapshot_objects(sid) == before


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


@pytest.mark.parametrize("gate", [None, "allowed", "blocked"])
def test_approval_ui_uses_existing_admission_policy(tmp_path, gate):
    import re

    from tests.semantic_fixture_support import bind_fixture_selections
    console = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    bind_fixture_selections(console, [("De verpleegkundige bespreekt passende ondersteuning met de client.", "definition")])
    console, client, _researcher, _reviewer, sid, objects = _system(tmp_path, console)
    obj = next(row for row in objects if row.get("proposed_object_type") == "definition")
    rows = console._load_objects(sid)
    target = next(row for row in rows if row["object_id"] == obj["object_id"])
    admission = target.setdefault("metadata", {}).setdefault("admission", {})
    if gate is None:
        admission.pop("gate_result", None)
    else:
        admission["gate_result"] = gate
    console._save_objects(sid, rows)
    page = client.get(f'/review?document={sid}&object={obj["object_id"]}')
    assert page.status_code == 200
    approval = re.search(r'<input[^>]*name="eindoordeel"[^>]*value="goedkeuren"[^>]*>', page.text)
    assert approval
    assert ("disabled" in approval.group()) == (gate != "allowed")
