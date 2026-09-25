"""D5.4 review-interaction evidence and burden regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.integrity_kernel import stamp_canonical_hashes
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.publish_authorization_v1 import tuple_record
from src.review_interaction_v1 import (
    build_review_interaction_evidence,
    review_burden_projection,
    validate_review_interaction_identity,
)
from src.review_ledger import read_events


PASSWORD = "d54-secret"
HTML = b"""<!doctype html><html><body><h1>Advies</h1><p>Gebruik interventie A.</p></body></html>"""


def _system(tmp_path: Path) -> tuple[OperationsConsole, dict[str, dict], str, str]:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime" / "console",
    )
    researcher = console.create_account(
        username="researcher.d54",
        password=PASSWORD,
        roles=("researcher", "reviewer"),
    )
    reviewer_a = console.create_account(
        username="reviewer.a.d54",
        password=PASSWORD,
        roles=("reviewer",),
    )
    reviewer_b = console.create_account(
        username="reviewer.b.d54",
        password=PASSWORD,
        roles=("reviewer",),
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="d54.html",
        data=HTML,
        content_type="text/html",
        ingest_kind="new",
        title="D5.4 fixture",
        version="1.0",
        date="2026-09-25",
        live_url="https://example.test/d54",
        class_="richtlijn",
        family="test",
        named_reviewers=[
            reviewer_a["account_id"],
            reviewer_b["account_id"],
        ],
    )
    snapshot_id = receipt["snapshot_id"]
    rows = console._load_objects(snapshot_id)
    target = next(
        row
        for row in rows
        if row.get("object_type") != "document"
        and str((row.get("content") or {}).get("clean_text") or "").strip()
    )
    target["object_type"] = "definition"
    target["confirmed_object_type"] = "definition"
    target.setdefault("metadata", {}).setdefault("admission", {}).update(
        {
            "gate_result": "allowed",
            "section_path": ["Advies"],
        }
    )
    target["structure"] = {"section_path": ["Advies"]}
    target["risk"] = {
        "level": "standard",
        "risk_level": "standard",
        "requires_second_review": False,
        "risk_fields": [],
    }
    target["uncertainty"] = {"has_uncertainty": False, "items": []}
    target.setdefault("governance", {})["validation_status"] = "needs_review"
    target["governance"]["second_review"] = {
        "required": False,
        "status": "not_required",
        "reviewer": None,
        "review_date": None,
        "snapshot_hash": None,
    }
    stamp_canonical_hashes(target)
    console._save_objects(snapshot_id, rows)
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


def test_burden_groups_batch_members_into_one_human_interaction() -> None:
    evidence = {
        "version": "review-interaction-v1",
        "interaction_id": "ri_batch1",
        "interaction_kind": "batch",
        "canonical_task": "batch",
        "snapshot_id": "snap-1",
        "reviewer_account_id": "reviewer-a",
        "review_stage": "first_review",
        "requested_count": 3,
        "context_manifest": {"members": []},
        "context_manifest_hash": "hash",
    }
    events = [
        {
            "event_type": "clinical_review_approve",
            "object_id": "d1",
            "object_version": "1.0",
            "details": {"snapshot_id": "snap-1", "review_interaction": evidence},
        },
        {
            "event_type": "clinical_review_approve",
            "object_id": "d2",
            "object_version": "1.0",
            "details": {"snapshot_id": "snap-1", "review_interaction": evidence},
        },
    ]

    result = review_burden_projection(events, snapshot_id="snap-1")

    assert result["review_interactions"] == 1
    assert result["object_decisions"] == 2
    assert result["partial_batch_interactions"] == 1
    assert result["interactions"][0]["requested_count"] == 3
    assert result["interactions"][0]["committed_decisions"] == 2


def test_legacy_decision_is_unmeasured_not_invented_as_interaction() -> None:
    result = review_burden_projection(
        [
            {
                "event_type": "clinical_review_approve",
                "object_id": "old",
                "object_version": "1.0",
                "details": {"review_snapshot_hash": "abc"},
            }
        ]
    )
    assert result["review_interactions"] == 0
    assert result["object_decisions"] == 0
    assert result["legacy_unmeasured_decisions"] == 1


def test_document_projection_does_not_claim_unscoped_legacy_decision() -> None:
    result = review_burden_projection(
        [
            {
                "event_type": "clinical_review_approve",
                "object_id": "old",
                "object_version": "1.0",
                "details": {"review_snapshot_hash": "abc"},
            }
        ],
        snapshot_id="snap-1",
    )
    assert result["legacy_unmeasured_decisions"] == 0


def test_interaction_id_cannot_move_between_reviewer_snapshot_or_task() -> None:
    prior = {
        "event_type": "clinical_review_approve",
        "object_id": "o1",
        "object_version": "1.0",
        "details": {
            "review_interaction": {
                "interaction_id": "ri_same",
                "reviewer_account_id": "a",
                "snapshot_id": "s1",
                "canonical_task": "contextual",
            }
        },
    }
    validate_review_interaction_identity(
        {
            "interaction_id": "ri_same",
            "reviewer_account_id": "a",
            "snapshot_id": "s1",
            "canonical_task": "contextual",
        },
        [prior],
    )
    with pytest.raises(ValueError, match="review_interaction_identity_conflict"):
        validate_review_interaction_identity(
            {
                "interaction_id": "ri_same",
                "reviewer_account_id": "b",
                "snapshot_id": "s1",
                "canonical_task": "contextual",
            },
            [prior],
        )


def test_contextual_review_commits_interaction_evidence_with_existing_decision_event(
    tmp_path: Path,
) -> None:
    console, accounts, snapshot_id, object_id = _system(tmp_path)
    objects = console.snapshot_objects(snapshot_id)
    focal = next(row for row in objects if row["object_id"] == object_id)
    evidence = build_review_interaction_evidence(
        interaction_id="ri_contextual1",
        interaction_kind="contextual",
        reviewer_account_id=accounts["reviewer_a"]["account_id"],
        snapshot_id=snapshot_id,
        review_stage="first_review",
        focal=focal,
        objects=objects,
        review_path="richtlijn",
    )

    console.review_object(
        actor_id=accounts["reviewer_a"]["account_id"],
        snapshot_id=snapshot_id,
        object_id=object_id,
        decision="approve",
        confirmed_object_type="definition",
        expected_revision=console.objects_revision(snapshot_id),
        interaction_evidence=evidence,
    )

    events = read_events(console._ledger_path)
    decision = next(
        row
        for row in reversed(events)
        if row.get("event_type") == "clinical_review_approve"
        and row.get("object_id") == object_id
    )
    stored = decision["details"]["review_interaction"]
    assert stored["interaction_id"] == "ri_contextual1"
    assert stored["context_manifest"]["focal"]["object_id"] == object_id
    assert "text" not in str(stored["context_manifest"].keys()).lower()

    burden = review_burden_projection(events, snapshot_id=snapshot_id)
    assert burden["review_interactions"] == 1
    assert burden["object_decisions"] == 1


def test_second_review_uses_same_evidence_store_without_changing_object_tuple(
    tmp_path: Path,
) -> None:
    console, accounts, snapshot_id, object_id = _system(tmp_path)
    rows = console._load_objects(snapshot_id)
    target = next(row for row in rows if row["object_id"] == object_id)
    target["object_type"] = "recommendation"
    target["confirmed_object_type"] = "recommendation"
    target["risk"] = {
        "level": "high",
        "risk_level": "high",
        "requires_second_review": True,
        "risk_fields": ["contraindication"],
    }
    target["governance"]["validation_status"] = "approved"
    target["governance"]["second_review"] = {
        "required": True,
        "status": "pending",
        "reviewer": None,
        "review_date": None,
        "snapshot_hash": None,
    }
    stamp_canonical_hashes(target)
    console._save_objects(snapshot_id, rows)
    live = next(row for row in console.snapshot_objects(snapshot_id) if row["object_id"] == object_id)
    first = tuple_record(
        object_id=object_id,
        object_version=live["object_version"],
        canonical_object_hash=live["provenance"]["canonical_object_hash"],
        confirmed_object_type="recommendation",
        reviewer=accounts["reviewer_a"]["username"],
        reviewer_id=accounts["reviewer_a"]["account_id"],
        decision="approve",
    )
    console._bindings[snapshot_id] = [first]
    console._save_bindings()

    before_version = live["object_version"]
    before_hash = live["provenance"]["canonical_object_hash"]
    evidence = build_review_interaction_evidence(
        interaction_id="ri_second1",
        interaction_kind="second_review",
        reviewer_account_id=accounts["reviewer_b"]["account_id"],
        snapshot_id=snapshot_id,
        review_stage="second_review",
        focal=live,
        objects=console.snapshot_objects(snapshot_id),
        review_path="richtlijn",
    )
    console.approve_second_review(
        actor_id=accounts["reviewer_b"]["account_id"],
        snapshot_id=snapshot_id,
        object_id=object_id,
        expected_revision=console.objects_revision(snapshot_id),
        interaction_evidence=evidence,
    )

    after = next(row for row in console.snapshot_objects(snapshot_id) if row["object_id"] == object_id)
    assert after["object_version"] == before_version
    assert after["provenance"]["canonical_object_hash"] == before_hash

    event = next(
        row
        for row in reversed(read_events(console._ledger_path))
        if row.get("event_type") == "second_review_approve"
    )
    assert event["details"]["review_interaction"]["interaction_id"] == "ri_second1"
