"""VSA Slice 9: the Review Workboard and publication closure form one loop.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from src.operations_console_v1 import CAPTURED
from src.passage_register_v1 import passage_register_of
from src.proportionate_review_v1 import ProportionateReviewConsole, normal_risk_batch_queue
from src.publication_readiness_v1 import SOURCE_PASSAGE_REVIEW_INCOMPLETE, source_passage_closure
from src.review_closure_v1 import ReviewClosureConsole
from src.review_cockpit_v1 import confirmable_proposed_type
from src.review_workboard_v1 import review_work_item


class _QueueConsole(ProportionateReviewConsole):
    def __init__(self, objects: list[dict[str, Any]], status: str = "in_review") -> None:
        self._test_objects = objects
        self._test_status = status

    def snapshot_objects(self, _snapshot_id: str) -> list[dict[str, Any]]:
        return deepcopy(self._test_objects)

    def document_status(self, _snapshot_id: str) -> str:
        return self._test_status


def _object(
    object_id: str,
    *,
    object_type: str = "explanation",
    register_status: str = "not_yet_assessed",
    review_status: str = "needs_review",
    gate_result: str | None = None,
    passage_source: str = "extract",
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "passage_register": {
            "status": register_status,
            "source": passage_source,
        }
    }
    if gate_result is not None:
        metadata["admission"] = {
            "gate_result": gate_result,
            "section_path": ["Hoofdstuk"],
        }
    return {
        "object_id": object_id,
        "object_type": object_type,
        "proposed_object_type": object_type,
        "metadata": metadata,
        "governance": {"validation_status": review_status},
        "content": {"clean_text": object_id},
    }


def _envelope() -> dict[str, Any]:
    return {
        "snapshot_id": "snap-test",
        "title": "Testdocument",
        "version": "1.0",
        "family": "zorg",
        "class": "richtlijn",
        "state": CAPTURED,
        "named_reviewers": ["reviewer-1"],
    }


def _account() -> dict[str, Any]:
    return {
        "account_id": "reviewer-1",
        "roles": ["reviewer"],
        "username": "reviewer-1",
    }


def test_unresolved_closure_gap_is_reachable_instead_of_looking_complete() -> None:
    legacy_open = _object("legacy-open", gate_result=None)
    console = _QueueConsole([legacy_open])
    before = deepcopy(console._test_objects)

    item = review_work_item(console, account=_account(), envelope=_envelope())

    assert item is not None
    assert item["source_passage_review_complete"] is False
    assert item["closure_gap_ids"] == ["legacy-open"]
    assert item["closure_gap_count"] == 1
    assert item["remaining_review_items"] == 1
    assert item["work_state"] == "review"
    assert item["next_task"] == "closure"
    assert item["next_href"] == "/review?document=snap-test&object=legacy-open"
    assert console._test_objects == before


def test_terminal_exclusion_removes_blocked_passage_from_workboard() -> None:
    excluded = _object(
        "blocked-but-final",
        register_status="excluded_with_reason",
        review_status="rejected",
        gate_result="blocked",
        passage_source="review",
    )
    console = _QueueConsole([excluded], status="ready_for_publication")

    closure = source_passage_closure([excluded])
    item = review_work_item(console, account=_account(), envelope=_envelope())

    assert closure["source_passage_review_complete"] is True
    assert item is not None
    assert item["blocked_count"] == 0
    assert item["closure_gap_count"] == 0
    assert item["remaining_review_items"] == 0
    assert item["work_state"] == "complete"
    assert item["next_task"] == ""


def _review(
    console: ReviewClosureConsole,
    reviewer: dict[str, Any],
    snapshot_id: str,
    object_id: str,
    *,
    decision: str,
    eindoordeel: str,
    comment: str = "",
) -> None:
    obj = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row["object_id"] == object_id
    )
    console.review_object(
        actor_id=reviewer["account_id"],
        snapshot_id=snapshot_id,
        object_id=object_id,
        decision=decision,
        comment=comment,
        confirmed_object_type=confirmable_proposed_type(obj) or None,
        suitability="ja",
        eindoordeel=eindoordeel,
        type_action="dit_klopt",
    )


def test_exact_object_decisions_close_document_review_only_after_last_passage(
    tmp_path: Path,
) -> None:
    console = ReviewClosureConsole(
        root=tmp_path,
        source_store=tmp_path / "sources",
        runtime=tmp_path / "runtime",
    )
    researcher = console.create_account(
        username="researcher",
        password="researcher-secret",
        roles=("researcher",),
    )
    reviewer = console.create_account(
        username="reviewer",
        password="reviewer-secret",
        roles=("reviewer",),
    )
    publisher = console.create_account(
        username="publisher",
        password="publisher-secret",
        roles=("publisher",),
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
        date="2026-09-15",
        live_url="",
        class_="richtlijn",
        family="begrippen",
        named_reviewers=[reviewer["account_id"]],
    )
    snapshot_id = str(receipt["snapshot_id"])
    ids = [
        str(obj["object_id"])
        for obj in normal_risk_batch_queue(
            console.snapshot_objects(snapshot_id),
            review_path="richtlijn",
        )
    ]
    closure_before = source_passage_closure(console.snapshot_objects(snapshot_id))
    assert len(ids) == 2
    assert set(closure_before["unresolved_source_passage_ids"]) == set(ids)

    _review(
        console,
        reviewer,
        snapshot_id,
        ids[0],
        decision="approve",
        eindoordeel="goedkeuren",
    )

    after_one = console.consider_publish(
        actor_id=publisher["account_id"],
        snapshot_id=snapshot_id,
    )
    assert after_one["source_passage_review_complete"] is False
    assert after_one["unresolved_source_passage_ids"] == [ids[1]]
    assert SOURCE_PASSAGE_REVIEW_INCOMPLETE in after_one["curation_blockers"]
    assert console._envelope(snapshot_id)["state"] == CAPTURED
    first = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row["object_id"] == ids[0]
    )
    assert first["governance"]["validation_status"] == "approved"
    assert passage_register_of(first)["status"] == "selected_as_candidate"

    _review(
        console,
        reviewer,
        snapshot_id,
        ids[1],
        decision="reject",
        eindoordeel="afwijzen",
        comment="Geen zelfstandig kennisobject.",
    )

    after_last = console.consider_publish(
        actor_id=publisher["account_id"],
        snapshot_id=snapshot_id,
    )
    assert after_last["source_passage_review_complete"] is True
    assert after_last["unresolved_source_passage_ids"] == []
    assert SOURCE_PASSAGE_REVIEW_INCOMPLETE not in after_last["curation_blockers"]
    assert console._envelope(snapshot_id)["state"] == CAPTURED
    second = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row["object_id"] == ids[1]
    )
    assert second["governance"]["validation_status"] == "rejected"
    assert passage_register_of(second)["status"] == "excluded_with_reason"
