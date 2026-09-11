"""End-to-end evidence for deterministic Review repair.

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

from src.closed_review_loop_v1 import install_closed_review_routes
from src.deterministic_review_repair_v1 import (
    DeterministicRepairReviewConsole,
    REPAIR_MERGE_OBJECTS,
    REPAIR_SOURCE_UNITS,
    REPAIR_SUPPORT_RELATION,
    StructuredRepairRequired,
    install_deterministic_review_repair_routes,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.review_ledger import read_events
from src.serving_relations_v1 import binding_relations


def _system(tmp_path):
    console = DeterministicRepairReviewConsole(
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
            b"<p>Wanneer de client ondersteuning wil, bespreekt de verpleegkundige passende ondersteuning.</p>"
            b"<p>De verpleegkundige verwijst de client zo nodig naar passende ondersteuning.</p>"
            b"<p>De keuze wordt samen met de client geevalueerd.</p>"
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
    assert len(objects) >= 3
    app = create_console_app(console)
    install_deterministic_review_repair_routes(app, console)
    install_closed_review_routes(app, console)
    client = TestClient(app)
    client.post("/login", data={"username": "bert", "password": "bert-secret"})
    return console, client, researcher, reviewer, sid, objects


def _review_payload(console, sid, obj, *, suitability="mist_context", comment="Context ontbreekt."):
    return {
        "snapshot_id": sid,
        "object_id": obj["object_id"],
        "snapshot_revision": console.objects_revision(sid),
        "suitability": suitability,
        "documentpositie_action": "dit_klopt",
        "type_action": "dit_klopt",
        "proposed_object_type": obj.get("proposed_object_type") or obj.get("object_type") or "explanation",
        "eindoordeel": "goedkeuren_na_correctie",
        "comment": comment,
        "proposed_correction": "vrije tekst mag nooit canonieke reparatie worden",
    }


def test_revise_first_post_is_prewrite_specification_step(tmp_path):
    console, client, _researcher, _reviewer, sid, objects = _system(tmp_path)
    obj = objects[0]
    before_rows = console._objects_path(sid).read_bytes()
    before_ledger = console._ledger_path.read_bytes() if console._ledger_path.exists() else b""

    response = client.post("/review", data=_review_payload(console, sid, obj))

    assert response.status_code == 200
    assert "Correctie specificeren" in response.text
    assert "Er is nog niets gewijzigd" in response.text
    assert 'action="/review/resolve"' in response.text
    assert console._objects_path(sid).read_bytes() == before_rows
    after_ledger = console._ledger_path.read_bytes() if console._ledger_path.exists() else b""
    assert after_ledger == before_ledger
    current = console._current_object(sid, obj["object_id"])
    assert current["governance"]["validation_status"] == "needs_review"


def test_source_unit_resolution_creates_new_proposal_and_no_revise_remains(tmp_path):
    console, _client, _researcher, reviewer, sid, objects = _system(tmp_path)
    obj = objects[0]
    before_version = obj["object_version"]
    units = console.source_units(snapshot_id=sid, object_id=obj["object_id"])
    own_fragment_ids = {
        str(ref.get("raw_object_id") or "")
        for ref in (obj.get("provenance") or {}).get("source_fragments") or []
    }
    own_units = [row["unit_id"] for row in units if row["fragment_id"] in own_fragment_ids]
    assert own_units

    repaired = console.submit_review_resolution(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=obj["object_id"],
        expected_revision=console.objects_revision(sid),
        suitability="mist_context",
        comment="Gebruik de volledige bronzin.",
        repair_kind=REPAIR_SOURCE_UNITS,
        source_unit_ids=own_units,
    )

    assert repaired["object_version"] != before_version
    assert repaired["governance"]["validation_status"] == "needs_review"
    assert not any(
        (row.get("governance") or {}).get("validation_status") == "revise"
        for row in console.snapshot_objects(sid)
    )
    assert "vrije tekst" not in str((repaired.get("content") or {}).get("clean_text") or "")
    events = read_events(console._ledger_path)
    assert any(
        event.get("event_type") == "revision_created"
        and event.get("object_id") == obj["object_id"]
        for event in events
    )
    assert any(
        event.get("event_type") == "review_audit_evidence"
        and (event.get("details") or {}).get("decision") == "repair_source_units"
        for event in events
    )


def test_unknown_source_unit_rolls_back_review_and_repair(tmp_path):
    console, _client, _researcher, reviewer, sid, objects = _system(tmp_path)
    obj = objects[0]
    before_rows = console._objects_path(sid).read_bytes()
    before_ledger = console._ledger_path.read_bytes() if console._ledger_path.exists() else b""

    with pytest.raises(ConsoleError, match="repair_source_unit_unknown"):
        console.submit_review_resolution(
            actor_id=reviewer["account_id"],
            snapshot_id=sid,
            object_id=obj["object_id"],
            expected_revision=console.objects_revision(sid),
            suitability="mist_context",
            comment="Onbekende bronselectie mag niet landen.",
            repair_kind=REPAIR_SOURCE_UNITS,
            source_unit_ids=["does-not-exist::s1"],
        )

    assert console._objects_path(sid).read_bytes() == before_rows
    after_ledger = console._ledger_path.read_bytes() if console._ledger_path.exists() else b""
    assert after_ledger == before_ledger


def test_merge_resolution_supersedes_absorbed_object_and_reopens_primary(tmp_path):
    console, _client, _researcher, reviewer, sid, objects = _system(tmp_path)
    primary, absorbed = objects[0], objects[1]

    repaired = console.submit_review_resolution(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=primary["object_id"],
        expected_revision=console.objects_revision(sid),
        suitability="samenvoegen",
        comment="Deze passages vormen samen een kennisobject.",
        repair_kind=REPAIR_MERGE_OBJECTS,
        merge_object_ids=[absorbed["object_id"]],
    )

    absorbed_now = console._current_object(sid, absorbed["object_id"])
    assert repaired["governance"]["validation_status"] == "needs_review"
    assert absorbed_now["governance"]["validation_status"] == "superseded"
    assert absorbed_now["governance"]["superseded_by"] == primary["object_id"]
    assert str((primary.get("content") or {}).get("clean_text") or "") in str(
        (repaired.get("content") or {}).get("clean_text") or ""
    )
    assert str((absorbed.get("content") or {}).get("clean_text") or "") in str(
        (repaired.get("content") or {}).get("clean_text") or ""
    )
    assert not any(
        (row.get("governance") or {}).get("validation_status") == "revise"
        for row in console.snapshot_objects(sid)
    )


def test_support_resolution_writes_real_relation_and_reopens_review(tmp_path):
    console, _client, _researcher, reviewer, sid, objects = _system(tmp_path)
    support, claim = objects[0], objects[1]

    repaired = console.submit_review_resolution(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=support["object_id"],
        expected_revision=console.objects_revision(sid),
        suitability="alleen_onderbouwing",
        comment="Deze passage onderbouwt de volgende claim.",
        repair_kind=REPAIR_SUPPORT_RELATION,
        claim_object_id=claim["object_id"],
    )

    claim_now = console._current_object(sid, claim["object_id"])
    assert repaired["governance"]["validation_status"] == "needs_review"
    assert any(
        relation.get("relation_type") == "supported_by"
        and relation.get("target_object_id") == support["object_id"]
        for relation in binding_relations(claim_now)
    )
    assert not any(
        (row.get("governance") or {}).get("validation_status") == "revise"
        for row in console.snapshot_objects(sid)
    )


def test_direct_revise_cannot_be_left_behind(tmp_path):
    console, _client, _researcher, reviewer, sid, objects = _system(tmp_path)
    obj = objects[0]
    before = console._objects_path(sid).read_bytes()

    with pytest.raises(StructuredRepairRequired):
        console.review_object(
            actor_id=reviewer["account_id"],
            snapshot_id=sid,
            object_id=obj["object_id"],
            decision="revise",
            suitability="mist_context",
            eindoordeel="goedkeuren_na_correctie",
            comment="Nog te repareren.",
            expected_revision=console.objects_revision(sid),
        )

    assert console._objects_path(sid).read_bytes() == before
    assert console._current_object(sid, obj["object_id"])["governance"]["validation_status"] == "needs_review"
