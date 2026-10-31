"""MET-36 slice 3a: object writes store only the difference, with the same result.

Before: every object write deleted all rows of the snapshot and inserted the full
list again, so one exclusion on Richtlijn Smetten held the transaction for minutes
(incident 2026-10-31). After: the stored rows equal the old full replacement
(identity, payload, position 0..n-1), but unchanged rows are not touched.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.vorming.source_accountability_v1 import evidence_of, is_source_record
from tests.test_b6_source_batch_scale import _large_pdf


def _rows(store, sid):
    with store._connect() as con:
        return con.execute(
            "SELECT object_id,object_version,position,payload,xmin::text AS xmin FROM workflow.document_objects "
            "WHERE snapshot_id=%s ORDER BY position", (sid,)).fetchall()


def _assert_full_replacement_result(store, sid, following):
    """The state the old DELETE + INSERT-all wrote: exactly `following`, at positions 0..n-1."""
    rows = _rows(store, sid)
    assert [(r["object_id"], r["object_version"], r["position"]) for r in rows] == [
        (o["object_id"], o["object_version"], i) for i, o in enumerate(following)]
    assert [r["payload"] for r in rows] == following
    assert store.objects_revision(sid) == store.revision_for_rows(following)


def _touched(before, after):
    old = {(r["object_id"], r["object_version"]): r["xmin"] for r in before}
    return sorted((r["object_id"], r["object_version"]) for r in after
                  if old.get((r["object_id"], r["object_version"])) != r["xmin"])


@pytest.fixture
def document(tmp_path, production_console):
    state, sid, reviewer = _large_pdf(tmp_path, production_console=production_console)
    return state, sid, reviewer


def test_append_update_and_remove_store_the_same_rows_and_touch_only_the_change(document):
    state, sid, _reviewer = document
    store = state.workflow_document_store
    envelope = state._envelope(sid)
    current = [deepcopy(r) for r in store.list_document_objects(sid)]
    sources = [r for r in current if is_source_record(r)]
    assert len(current) >= 200

    # 1. Append one successor version (the normal review/source write).
    successor = deepcopy(sources[0])
    successor["object_version"] = sources[0]["object_version"] + ".1"
    following = current + [successor]
    before = _rows(store, sid)
    store.write_bundle(envelope=envelope, objects=following)
    _assert_full_replacement_result(store, sid, following)
    assert _touched(before, _rows(store, sid)) == [(successor["object_id"], successor["object_version"])]

    # 2. Change the payload of one current row in place (governance update).
    changed = deepcopy(following)
    target = next(i for i, r in enumerate(changed) if r["object_id"] == sources[1]["object_id"])
    changed[target].setdefault("metadata", {})["met36_probe"] = "changed"
    before = _rows(store, sid)
    store.write_bundle(envelope=envelope, objects=changed)
    _assert_full_replacement_result(store, sid, changed)
    assert _touched(before, _rows(store, sid)) == [(changed[target]["object_id"], changed[target]["object_version"])]

    # 2b. An int that becomes an equal float is a change in stored JSON and revision (1 == 1.0 in Python).
    floated = deepcopy(changed)
    floated[target].setdefault("metadata", {})["met36_number"] = 1
    store.write_bundle(envelope=envelope, objects=floated)
    floated = deepcopy(floated)
    floated[target]["metadata"]["met36_number"] = 1.0
    store.write_bundle(envelope=envelope, objects=floated)
    _assert_full_replacement_result(store, sid, floated)
    assert isinstance(_rows(store, sid)[target]["payload"]["metadata"]["met36_number"], float)
    changed = floated

    # 3. Drop one working (source) record: replacement semantics are kept for now (V3 comes later).
    dropped = [r for r in changed if r["object_id"] != sources[2]["object_id"]]
    before = _rows(store, sid)
    store.write_bundle(envelope=envelope, objects=dropped)
    _assert_full_replacement_result(store, sid, dropped)
    # Rows after the removed one shift one position; nothing else is rewritten.
    assert len(_touched(before, _rows(store, sid))) <= len(dropped) - [r["object_id"] for r in changed].index(sources[2]["object_id"])


def test_source_batch_on_a_large_document_touches_only_the_new_versions(document):
    from src.review.source_context_review_v1 import confirm_source_exclusions
    state, sid, reviewer = document
    store = state.workflow_document_store
    ids = [r["object_id"] for r in state.snapshot_objects(sid)
           if is_source_record(r) and evidence_of(r).get("proposed_role") == "metadata"][:5]
    before = _rows(store, sid)
    result = confirm_source_exclusions(state, actor_id=reviewer, snapshot_id=sid, source_object_ids=ids,
        reason="Colofon, geen kennis.", command_id="met36-batch", expected_revision=state.objects_revision(sid))
    after = _rows(store, sid)
    new_versions = sorted((oid, version) for oid, version in result["source_versions"].items())
    assert len(after) == len(before) + len(ids)
    # Only the five successor rows are written; the 200+ existing rows keep their tuple.
    assert _touched(before, after) == new_versions
