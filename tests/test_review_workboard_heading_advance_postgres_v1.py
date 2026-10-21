"""Regression proof for confirmed headings leaving the Review workboard queue.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.operations_console_v1 import review_lane
from src.review_workboard_v1 import review_workboard_items


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
TEST_PASSWORD = __name__

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


@pytest.fixture
def workflow_postgres(complete_postgres):
    return complete_postgres


def _fresh_current_validation_statuses(
    config: PostgresCanonicalConfig,
    *,
    snapshot_id: str,
    object_ids: set[str],
) -> dict[str, str]:
    import psycopg
    from psycopg.rows import dict_row

    assert config.dsn
    with psycopg.connect(config.dsn, row_factory=dict_row) as con:
        rows = con.execute(
            "SELECT DISTINCT ON (object_id) object_id, "
            "payload->'governance'->>'validation_status' AS validation_status "
            "FROM workflow.document_objects "
            "WHERE snapshot_id=%s AND object_id=ANY(%s) "
            "ORDER BY object_id, position DESC NULLS LAST",
            (snapshot_id, sorted(object_ids)),
        ).fetchall()
    return {
        str(row["object_id"]): str(row["validation_status"] or "")
        for row in rows
    }


def test_batch_confirmed_headings_disappear_from_fast_workboard_summary(
    tmp_path: Path,
    workflow_postgres: PostgresCanonicalConfig,
    production_console,
) -> None:
    from tests.semantic_fixture_support import bind_fixture_selections
    console = production_console(processing_binder=bind_fixture_selections)

    researcher = console.create_account(
        username="researcher.heading-regression",
        password=TEST_PASSWORD,
        roles=("researcher",),
    )
    reviewer = console.create_account(
        username="reviewer.heading-regression",
        password=TEST_PASSWORD,
        roles=("reviewer",),
    )
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="heading-regression.html",
        data=HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Heading workboard regression",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/heading-regression",
        class_="richtlijn",
        family="review-regression",
        named_reviewers=[reviewer["account_id"]],
    )
    snapshot_id = str(receipt["snapshot_id"])

    headings = [
        row
        for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") != "document"
        and review_lane(row, review_path="richtlijn") == "fast"
        and (row.get("governance") or {}).get("validation_status")
        not in {"approved", "rejected", "superseded"}
    ]
    assert headings

    before = console.review_workboard_summaries(str(reviewer["account_id"]))[snapshot_id]
    assert before["heading_pending"] == len(headings)

    console.batch_confirm_headings(
        actor_id=reviewer["account_id"],
        snapshot_id=snapshot_id,
        object_ids=[str(row["object_id"]) for row in headings],
        expected_revision=console.objects_revision(snapshot_id),
    )

    heading_ids = {str(item["object_id"]) for item in headings}
    confirmed = {
        str(row["object_id"]): (row.get("governance") or {}).get("validation_status")
        for row in console.snapshot_objects(snapshot_id)
        if str(row.get("object_id") or "") in heading_ids
    }
    assert confirmed
    assert set(confirmed.values()) == {"approved"}

    committed = _fresh_current_validation_statuses(
        workflow_postgres,
        snapshot_id=snapshot_id,
        object_ids=heading_ids,
    )
    assert committed == confirmed

    after = console.review_workboard_summaries(str(reviewer["account_id"]))[snapshot_id]
    assert after["heading_pending"] == 0

    items = review_workboard_items(console, account=reviewer)
    work_item = next(row for row in items if row["snapshot_id"] == snapshot_id)
    assert work_item["heading_pending"] == 0
    assert work_item["next_task"] != "headings"
    assert work_item["next_href"] != f"/review?document={snapshot_id}&task=headings"
