"""Behavioral T10 regressions using pre-existing public entrypoints.
# release-control-evidence: scope/belofte kwaliteit slop releasebewijs
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: toegang beschikbaarheid metrics
"""
from copy import deepcopy
import pytest

from src.source_containers_v1 import partition, source_usage
from src.publication_readiness_v1 import source_passage_closure, review_followup_queues
from src.source_accountability_v1 import KEY, record
from src.review_duty_v1 import review_duty_for
from tests.test_source_containers_v1 import context_story


def _linked(rows):
    return next(item["record"] for item in partition(rows)["source"]
                if item["record"]["content"]["clean_text"] == "Bij volwassenen.")


@pytest.mark.parametrize("damage", ["binding", "spans", "text"])
def test_corrupt_source_is_repair_not_disposition(damage):
    rows = context_story()
    source = _linked(rows)
    if damage == "binding":
        source["metadata"][KEY]["binding_hash"] = "corrupt"
    elif damage == "spans":
        source["metadata"][KEY]["spans"][0]["end"] += 1
    else:
        source["content"]["clean_text"] += " corrupt"
    queues = review_followup_queues(rows, review_path="richtlijn")
    assert source["object_id"] in {o["object_id"] for o in queues["repair"]}
    assert source["object_id"] not in {o["object_id"] for o in queues["disposition"]}


def test_governance_approved_alone_cannot_close_target_context():
    rows = context_story()
    source = _linked(rows)
    target = partition(rows)["knowledge"][0]
    target["governance"]["validation_status"] = "approved"
    assert not source_usage(rows)[source["object_id"]]["accounted"]
    assert source["object_id"] in source_passage_closure(rows)["unresolved_source_passage_ids"]


def test_invalid_human_role_cannot_hide_behind_context_waiting():
    rows = context_story()
    source = _linked(rows)
    source["metadata"]["source_role_review"] = {"role": "context", "literal_hash": "bad"}
    queues = review_followup_queues(rows, review_path="richtlijn")
    assert source["object_id"] in {o["object_id"] for o in queues["repair"]}


def test_valid_pending_context_has_no_duplicate_source_task():
    rows = context_story()
    source = _linked(rows)
    before = deepcopy(rows)
    queues = review_followup_queues(rows, review_path="richtlijn")
    assert source["object_id"] not in {o["object_id"] for q in queues.values() for o in q}
    assert source["object_id"] in source_passage_closure(rows)["unresolved_source_passage_ids"]
    assert rows == before


def test_source_records_never_open_content_review():
    rows = context_story()
    for item in partition(rows)["source"]:
        assert review_duty_for(item["record"], review_path="richtlijn", bindings=[]) is None
