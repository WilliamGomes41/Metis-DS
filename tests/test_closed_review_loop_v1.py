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

from src.closed_review_loop_v1 import (
    ClosedLoopReviewConsole,
    REVIEW_DISPOSITION_INCONSISTENT,
    install_closed_review_routes,
)
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.passage_register_v1 import passage_register_of
from src.proportionate_review_v1 import normal_risk_batch_queue
from src.review_cockpit_v1 import broncontext_parts, confirmable_proposed_type
from src.review_ledger import read_events
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
    proposed_correction="",
):
    obj = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    return console.review_object(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=oid,
        decision=decision,
        comment=comment,
        proposed_correction=proposed_correction,
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


def test_reject_is_terminal_exclusion_and_preserves_original_suitability(tmp_path):
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
    assert not any(
        row.get("valid")
        for row in console.object_review_bindings(sid)
        if row.get("object_id") == ids[0]
    )
    assert console.waiting_task_counts(researcher["account_id"])["ingest"] == 0

    signal = console.audit_review_signals()[0]
    assert signal["object_id"] == ids[0]
    assert signal["details"]["snapshot_id"] == sid
    assert signal["details"]["decision"] == "reject"
    assert signal["details"]["original_suitability"] == "ja"
    assert signal["details"]["final_disposition"] == "excluded_with_reason"
    assert signal["details"]["source_hash"] == console._envelope(sid)["sha256"]


def test_revise_is_non_terminal_until_repair_executes(tmp_path):
    console, researcher, reviewer, sid, ids = _system(tmp_path)
    oid = ids[0]
    before = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    before_status = passage_register_of(before)["status"]
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
    assert passage_register_of(revised)["status"] == before_status
    assert passage_register_of(revised)["status"] != "used_as_context"
    assert console.waiting_task_counts(researcher["account_id"])["ingest"] == 1
    assert console.waiting_task_counts(reviewer["account_id"])["review"] == 1
    signal = console.audit_review_signals()[0]
    assert signal["details"]["original_suitability"] == "mist_context"
    assert signal["details"]["final_disposition"] == "repair_required"


def test_repair_is_revision_pinned_and_returns_to_review(tmp_path):
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
        comment="Brongebonden herstel.",
    )
    revised = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    exact = broncontext_parts(revised)["source_text_exact"]
    stale = "0" * 64
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        console.repair_source(
            actor_id=reviewer["account_id"],
            snapshot_id=sid,
            object_id=oid,
            corrected_text=exact,
            reason="Brongebonden herstel",
            expected_revision=stale,
        )
    pin = console.objects_revision(sid)
    repaired = console.repair_source(
        actor_id=reviewer["account_id"],
        snapshot_id=sid,
        object_id=oid,
        corrected_text=exact,
        reason="Brongebonden herstel",
        expected_revision=pin,
    )
    assert repaired["governance"]["validation_status"] == "needs_review"
    assert repaired["object_version"] != revised["object_version"]
    assert console.waiting_task_counts(researcher["account_id"])["ingest"] == 0
    assert console.waiting_task_counts(reviewer["account_id"])["review"] == 1
    assert console.audit_review_signals()[0]["details"]["decision"] == "repair"


def test_proposed_correction_is_not_automatically_applied(tmp_path):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
    oid = ids[0]
    before = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    exact = broncontext_parts(before)["source_text_exact"]
    _review(
        console,
        reviewer,
        sid,
        oid,
        decision="revise",
        suitability="mist_context",
        eindoordeel="goedkeuren_na_correctie",
        comment="Voorstel, nog niet uitvoeren.",
        proposed_correction=exact,
    )
    current = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    assert current["object_version"] == before["object_version"]
    assert current["content"]["clean_text"] == before["content"]["clean_text"]


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
        expected_revision=console.objects_revision(sid),
    )
    current = {row["object_id"]: row for row in console.snapshot_objects(sid)}
    assert any(
        rel.get("relation_type") == "supported_by"
        and rel.get("target_object_id") == support_id
        for rel in binding_relations(current[claim_id])
    )
    assert passage_register_of(current[support_id])["status"] == "linked_as_support"
    assert current[support_id]["governance"]["validation_status"] == "needs_review"
    assert current[claim_id]["governance"]["validation_status"] == "needs_review"


def test_review_write_and_audit_evidence_roll_back_together(tmp_path, monkeypatch):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
    oid = ids[0]
    before = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    ledger_before = list(read_events(console._ledger_path))

    def fail_audit(**_kwargs):
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(console, "_append_audit_evidence", fail_audit)
    with pytest.raises(RuntimeError, match="audit write failed"):
        _review(
            console,
            reviewer,
            sid,
            oid,
            decision="revise",
            suitability="mist_context",
            eindoordeel="goedkeuren_na_correctie",
            comment="Moet atomair zijn.",
        )
    after = next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)
    assert after == before
    assert read_events(console._ledger_path) == ledger_before


def test_publication_fails_closed_on_disposition_mismatch(tmp_path):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
    publisher = console.create_account(
        username="piet", password="piet-secret", roles=("publisher",)
    )
    oid = ids[0]
    _review(
        console,
        reviewer,
        sid,
        oid,
        decision="approve",
        suitability="ja",
        eindoordeel="goedkeuren",
    )
    rows, revision = console.snapshot_objects_and_revision(sid, include_blocked=True)
    live = next(row for row in rows if row.get("object_id") == oid)
    metadata = dict(live.get("metadata") or {})
    register = dict(metadata.get("passage_register") or {})
    register["status"] = "excluded_with_reason"
    metadata["passage_register"] = register
    live["metadata"] = metadata
    console._commit_prepared_store(objects=(sid, rows), expected_revision=revision)

    considered = console.consider_publish(
        actor_id=publisher["account_id"], snapshot_id=sid
    )
    assert considered["publish_allowed"] is False
    assert REVIEW_DISPOSITION_INCONSISTENT in considered["blockers"]
    assert oid in considered["disposition_conflict_object_ids"]


def test_revise_and_rejected_objects_do_not_leak_from_question_selector(tmp_path):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
    revise_id, reject_id = ids[0], ids[1]
    _review(
        console,
        reviewer,
        sid,
        revise_id,
        decision="revise",
        suitability="mist_context",
        eindoordeel="goedkeuren_na_correctie",
        comment="Herstel nodig.",
    )
    _review(
        console,
        reviewer,
        sid,
        reject_id,
        decision="reject",
        suitability="ja",
        eindoordeel="afwijzen",
        comment="Niet gebruiken.",
    )
    selected = console.select_for_question(family="begrippen", asked_class="richtlijn")
    selected_ids = {row["object_id"] for row in selected}
    assert revise_id not in selected_ids
    assert reject_id not in selected_ids


def test_repair_ui_escapes_review_evidence_and_uses_internal_redirects(tmp_path):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
    oid = ids[0]
    _review(
        console,
        reviewer,
        sid,
        oid,
        decision="revise",
        suitability="mist_context",
        eindoordeel="goedkeuren_na_correctie",
        comment='<script>alert("x")</script>',
        proposed_correction='<img src=x onerror=alert("x")>',
    )
    app = create_console_app(console)
    install_closed_review_routes(app, console)
    client = TestClient(app, base_url="https://testserver")
    client.post("/login", data={"username": "bert", "password": "bert-secret"})
    response = client.get(f"/review/repair?document={sid}&object={oid}")
    assert response.status_code == 200
    assert "<script>alert" not in response.text
    assert "<img src=x" not in response.text
    assert "&lt;script&gt;" in response.text
    assert "&lt;img src=x" in response.text
    assert 'action="/review/repair/source"' in response.text
    assert 'name="snapshot_revision"' in response.text


def test_review_evidence_is_visible_in_audit_read_only_route(tmp_path):
    console, _researcher, reviewer, sid, ids = _system(tmp_path)
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
    client = TestClient(app, base_url="https://testserver")
    client.post("/login", data={"username": "anne", "password": "anne-secret"})
    response = client.get("/audit/review-signals")
    assert response.status_code == 200
    assert "Signalen uit Review" in response.text
    assert "Context ontbreekt." in response.text
    assert sid in response.text
    obj = next(row for row in console.snapshot_objects(sid) if row["object_id"] == ids[0])
    assert obj["governance"]["validation_status"] == "revise"
