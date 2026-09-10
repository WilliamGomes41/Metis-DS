"""Closed-loop Review regressions.

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
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.passage_register_v1 import passage_register_of
from src.proportionate_review_v1 import normal_risk_batch_queue
from src.review_cockpit_v1 import broncontext_parts, confirmable_proposed_type
from src.serving_relations_v1 import binding_relations


def _system(tmp_path):
    console = ClosedLoopReviewConsole(
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
        filename="begrippen.html",
        content_type="text/html",
        data=(
            b"<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>"
            b"<p>De Dutch Job Group is een meetinstrument voor werkbelasting.</p>"
            b"<p>Een observatie is een systematische waarneming van gedrag.</p>"
            b"</body></html>"
        ),
        ingest_kind="new",
        title="Begrippen",
        version="1.0",
        date="2026-09-10",
        live_url="",
        class_="richtlijn",
        family="begrippen",
        named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    objects = console.snapshot_objects(sid)
    ids = [
        obj["object_id"]
        for obj in normal_risk_batch_queue(objects, review_path="richtlijn")
    ]
    assert len(ids) >= 2
    return console, researcher, reviewer, sid, ids


def _review(
    console,
    reviewer,
    sid,
    oid,
    *,
    decision,
    suitability,
    eindoordeel,
    comment="",
):
    obj = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    return console.review_object(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=oid,
        decision=decision,
        comment=comment,
        confirmed_object_type=(confirmable_proposed_type(obj) or None),
        suitability=suitability,
        eindoordeel=eindoordeel,
        type_action="dit_klopt",
    )


def test_impossible_review_combination_fails_closed(tmp_path):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
    with pytest.raises(ConsoleError, match="review_disposition_conflict"):
        _review(
            console,
            reviewer,
            sid,
            ids[0],
            decision="approve",
            suitability="geen_kenniseenheid",
            eindoordeel="goedkeuren",
        )


def test_reject_is_terminal_exclusion_and_becomes_audit_evidence(tmp_path):
    console, researcher, reviewer, sid, ids = _system(tmp_path)
    _review(
        console,
        reviewer,
        sid,
        ids[0],
        decision="reject",
        suitability="ja",
        eindoordeel="afwijzen",
        comment="Dit is geen zelfstandig kennisobject.",
    )
    obj = next(row for row in console.snapshot_objects(sid) if row["object_id"] == ids[0])
    assert obj["governance"]["validation_status"] == "rejected"
    assert passage_register_of(obj)["status"] == "excluded_with_reason"
    assert not any(row.get("valid") for row in console.object_review_bindings(sid) if row.get("object_id") == ids[0])
    assert console.waiting_task_counts(researcher["account_id"])["ingest"] == 0

    signal = console.audit_review_signals()[0]
    assert signal["object_id"] == ids[0]
    assert signal["details"]["snapshot_id"] == sid
    assert signal["details"]["decision"] == "reject"
    assert signal["details"]["suitability"] == "geen_kenniseenheid"
    assert signal["details"]["source_hash"] == console._envelope(sid)["sha256"]


def test_revise_is_real_repair_work_and_current_version_drives_badges(tmp_path):
    console, researcher, reviewer, sid, ids = _system(tmp_path)
    oid = ids[0]
    _review(
        console,
        reviewer,
        sid,
        oid,
        decision="revise",
        suitability="mist_context",
        eindoordeel="goedkeuren_na_correctie",
        comment="De passage moet opnieuw uit de bron worden samengesteld.",
    )
    revised = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    assert revised["governance"]["validation_status"] == "revise"
    assert console.waiting_task_counts(researcher["account_id"])["ingest"] == 1

    exact = broncontext_parts(revised)["source_text_exact"]
    console.correct_object(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=oid,
        patch={
            "reason": "Brongebonden herstel",
            "operations": [{"op": "set", "path": "content.clean_text", "value": exact}],
        },
    )
    repaired = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    assert repaired["governance"]["validation_status"] == "needs_review"
    assert repaired["object_version"] != revised["object_version"]
    # Historical revise rows no longer keep the uploader badge alive.
    assert console.waiting_task_counts(researcher["account_id"])["ingest"] == 0
    assert console.waiting_task_counts(reviewer["account_id"])["review"] == 1


def test_correction_cannot_invent_text_outside_source_context(tmp_path):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
    oid = ids[0]
    _review(
        console,
        reviewer,
        sid,
        oid,
        decision="revise",
        suitability="samenvoegen",
        eindoordeel="goedkeuren_na_correctie",
        comment="Samenvoegen met broncontext.",
    )
    with pytest.raises(ConsoleError, match="correction_not_source_bound"):
        console.correct_object(
            actor_id=reviewer["account_id"],
            snapshot_id=sid,
            object_id=oid,
            patch={
                "reason": "Geen bronbewijs",
                "operations": [
                    {
                        "op": "set",
                        "path": "content.clean_text",
                        "value": "Deze zin staat nergens in de bron.",
                    }
                ],
            },
        )


def test_later_is_not_a_hidden_state_transition(tmp_path):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
    oid = ids[0]
    before = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    before_register = dict(passage_register_of(before))
    before_version = before["object_version"]
    console.review_object(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=oid,
        decision="later",
        suitability="mist_context",
        eindoordeel="later_beoordelen",
        confirmed_object_type="recommendation",
        type_action="type_wijzigen",
    )
    after = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    assert after["governance"]["validation_status"] == "needs_review"
    assert after["object_version"] == before_version
    assert passage_register_of(after) == before_register
    assert after.get("confirmed_object_type") == before.get("confirmed_object_type")


def test_support_disposition_requires_real_relation_then_reopens_both_objects(tmp_path):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
    support_id, claim_id = ids[0], ids[1]
    _review(
        console,
        reviewer,
        sid,
        support_id,
        decision="revise",
        suitability="alleen_onderbouwing",
        eindoordeel="goedkeuren_na_correctie",
        comment="Deze passage is alleen onderbouwing.",
    )
    support = next(row for row in console.snapshot_objects(sid) if row["object_id"] == support_id)
    with pytest.raises(ConsoleError, match="support_relation_required"):
        console.review_object(
            actor_id=reviewer["account_id"],
            snapshot_id=sid,
            object_id=support_id,
            decision="approve",
            confirmed_object_type=confirmable_proposed_type(support),
            suitability="alleen_onderbouwing",
            eindoordeel="goedkeuren",
            type_action="dit_klopt",
        )

    console.resolve_support_relation(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        support_object_id=support_id,
        claim_object_id=claim_id,
    )
    current = {row["object_id"]: row for row in console.snapshot_objects(sid)}
    assert any(
        rel.get("relation_type") == "supported_by"
        and rel.get("target_object_id") == support_id
        for rel in binding_relations(current[claim_id])
    )
    assert current[support_id]["governance"]["validation_status"] == "needs_review"
    assert current[claim_id]["governance"]["validation_status"] == "needs_review"


def test_review_evidence_is_visible_in_audit_read_only_route(tmp_path):
    console, researcher, reviewer, sid, ids = _system(tmp_path)
    _review(
        console,
        reviewer,
        sid,
        ids[0],
        decision="revise",
        suitability="mist_context",
        eindoordeel="goedkeuren_na_correctie",
        comment="Context ontbreekt.",
    )
    app = create_console_app(console)
    install_closed_review_routes(app, console)
    client = TestClient(app)
    client.post("/login", data={"username": "anne", "password": "anne-secret"})
    response = client.get("/audit/review-signals")
    assert response.status_code == 200
    assert "Signalen uit Review" in response.text
    assert "Context ontbreekt." in response.text
    assert sid in response.text
    # Audit route is read-only: the Review state remains revise.
    obj = next(row for row in console.snapshot_objects(sid) if row["object_id"] == ids[0])
    assert obj["governance"]["validation_status"] == "revise"
