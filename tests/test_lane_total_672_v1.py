"""#672: lane totals count only real review decisions as afgerond.

# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.knowledge_path_v1 import content_reviewable
from src.operations_console_app import _lane_total
from src.review_workboard_v1 import review_work_item
from src.source_accountability_v1 import is_source_record
from src.source_context_review_v1 import confirm_source_exclusions
from tests.characterization.overview_support import LEGACY_TEXT, guideline_document
from tests.characterization.support import REVIEWER


def _legacy_source_id(rows):
    return next(row["object_id"] for row in rows
                if is_source_record(row) and LEGACY_TEXT in str(row.get("literal_text") or row.get("text") or row))


def _exclude_legacy(console, sid):
    rows = console.snapshot_objects(sid)
    confirm_source_exclusions(console, actor_id=REVIEWER, snapshot_id=sid,
                              source_object_ids=[_legacy_source_id(rows)], reason="Documentversie, geen kennis.",
                              command_id="lane-total-672", expected_revision=console.objects_revision(sid))
    return console.snapshot_objects(sid)


def _with_status(row, status):
    row = deepcopy(row)
    row.setdefault("governance", {})["validation_status"] = status
    return row


def test_excluded_v1_source_record_is_not_a_finished_knowledge_review(tmp_path):
    console, sid, _ = guideline_document(tmp_path)
    rows = _exclude_legacy(console, sid)
    excluded = next(row for row in rows if is_source_record(row) and row["governance"]["validation_status"] == "rejected")
    assert excluded  # the real V1 command rejected the record
    assert _lane_total(rows, review_path="richtlijn", lane="contextual", open_rows=[]) == 0


def test_workboard_object_path_individual_total_ignores_excluded_source_record(tmp_path):
    console, sid, account = guideline_document(tmp_path)
    _exclude_legacy(console, sid)
    item = review_work_item(console, account=account, envelope=console._envelope(sid))
    assert item is not None and item["individual_total"] == 0


def test_superseded_candidate_is_not_finished_but_approved_and_rejected_still_count(tmp_path):
    console, sid, _ = guideline_document(tmp_path)
    rows = console.snapshot_objects(sid)
    candidate = next(row for row in rows if content_reviewable(row))
    lane_rows = [row for row in rows if row is not candidate]
    base = _lane_total(rows, review_path="richtlijn", lane="batch", open_rows=[])
    for status, delta in (("superseded", 0), ("approved", 1), ("rejected", 1)):
        variant = lane_rows + [_with_status(candidate, status)]
        assert _lane_total(variant, review_path="richtlijn", lane="batch", open_rows=[]) == base + delta, status


def test_finished_heading_still_counts_in_structure_lane(tmp_path):
    console, sid, _ = guideline_document(tmp_path)
    rows = console.snapshot_objects(sid)
    heading = next(row for row in rows if row.get("object_type") == "heading")
    variant = [row for row in rows if row is not heading] + [_with_status(heading, "approved")]
    assert _lane_total(variant, review_path="richtlijn", lane="structure", open_rows=[]) == 1


LANES = ("structure", "contextual", "batch")


@pytest.mark.parametrize("role", ["excluded", "label", "context"])
def test_candidate_reclassified_as_source_role_is_not_finished(tmp_path, role):
    """#700: confirm_source_context stamps rejected, but it is source handling, not a review decision."""
    console, sid, _ = guideline_document(tmp_path)
    rows = console.snapshot_objects(sid)
    before = {lane: _lane_total(rows, review_path="richtlijn", lane=lane, open_rows=[]) for lane in LANES}
    candidate = next(row for row in rows if content_reviewable(row))
    targets = [] if role == "excluded" else [next(row["object_id"] for row in rows if is_source_record(row))]
    console.confirm_source_context(actor_id=REVIEWER, snapshot_id=sid, source_object_id=candidate["object_id"],
                                   role=role, target_object_ids=targets, reason="Bronafhandeling, geen kennis.",
                                   command_id=f"lane-total-700-{role}", expected_revision=console.objects_revision(sid))
    rows = console.snapshot_objects(sid)
    stamped = next(row for row in rows if row["object_id"] == candidate["object_id"])
    assert stamped["governance"]["validation_status"] == "rejected"
    assert stamped["metadata"]["source_role_review"]["role"] == role
    after = {lane: _lane_total(rows, review_path="richtlijn", lane=lane, open_rows=[]) for lane in LANES}
    assert after == before
