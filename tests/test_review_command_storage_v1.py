"""Native delta persistence preserves untouched history, ordering and rollback.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy

import pytest

from src.review.review_interaction_v1 import validate_review_interaction_identity
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore, WorkflowReviewStoreError
from src.workflows.workflow_transaction_v1 import bind_workflow_stores, workflow_transaction
from tests.test_workflow_postgres_concurrency import _authorization, _envelope, _objects, _seed_accounts


def seed(config):
    uploader, reviewer = _seed_accounts(config)
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    envelope = _envelope("snap-review-delta", uploader, reviewer)
    objects = _objects("delta")
    historical = {**objects[0], "object_version": "1.1", "text": "A current"}
    documents.write_bundle(envelope=envelope, objects=[*objects, historical])
    return documents, reviews, envelope["snapshot_id"], reviewer


def object_storage(documents, sid):
    with documents._connect() as con:
        return con.execute(
            "SELECT object_id,object_version,position,payload,ctid::text AS physical,xmin::text AS writer "
            "FROM workflow.document_objects WHERE snapshot_id=%s ORDER BY position", (sid,),
        ).fetchall()


def document_counters(documents, sid):
    with documents._connect() as con:
        return con.execute(
            "SELECT revision,object_generation FROM workflow.documents WHERE snapshot_id=%s", (sid,),
        ).fetchone()


def test_native_review_delta_retains_unrelated_physical_rows_and_appends(complete_postgres):
    documents, _reviews, sid, reviewer = seed(complete_postgres)
    before = documents.review_command_histories(sid, ["delta-a"])
    assert [obj["object_version"] for obj in before] == ["1.0", "1.1"]
    stored = object_storage(documents, sid)
    counters = document_counters(documents, sid)
    after = deepcopy(before)
    after[-1]["text"] = "A reviewed"
    after.append({**after[-1], "object_version": "1.2", "text": "A successor"})
    envelope = documents.get_envelope(sid)
    updated = {**envelope, "review_passes": {reviewer: {"passed": True, "object_id": "delta-a"}}}
    documents.apply_review_changes(sid, before, after, envelope, updated, commit_count=2)
    current = object_storage(documents, sid)
    assert current[0] == stored[0]  # Retained predecessor, not rewritten.
    assert current[1] == stored[1]  # Independent object, not rewritten.
    assert current[2]["position"] == stored[2]["position"]
    assert current[2]["payload"]["text"] == "A reviewed"
    assert current[3]["position"] == 3
    assert documents.review_command_histories(sid, ["delta-a"]) == after
    assert document_counters(documents, sid)["revision"] == counters["revision"] + 2
    assert documents.get_envelope(sid)["review_passes"] == updated["review_passes"]
    # A completed later command preserves its compact-form invalidation effect.
    stable = object_storage(documents, sid)
    current_envelope = documents.get_envelope(sid)
    documents.apply_review_changes(sid, after, after, current_envelope, current_envelope)
    assert object_storage(documents, sid) == stable
    assert document_counters(documents, sid)["revision"] == counters["revision"] + 3


def test_native_review_delta_refuses_stale_history_and_unsupported_envelope(complete_postgres):
    documents, _reviews, sid, _reviewer = seed(complete_postgres)
    before = documents.review_command_histories(sid, ["delta-a"])
    envelope = documents.get_envelope(sid)
    winner = deepcopy(before)
    winner[-1]["text"] = "A durable winner"
    documents.apply_review_changes(sid, before, winner, envelope, envelope)
    durable = object_storage(documents, sid), document_counters(documents, sid)
    with pytest.raises(WorkflowDocumentStoreError, match="snapshot_object_write_conflict"):
        documents.apply_review_changes(sid, before, before, envelope, envelope)
    with pytest.raises(WorkflowDocumentStoreError, match="envelope_delta_unsupported"):
        documents.apply_review_changes(sid, winner, winner, envelope, {**envelope, "title": "Unsupported"})
    assert (object_storage(documents, sid), document_counters(documents, sid)) == durable
    with documents._connect() as con:
        con.execute("UPDATE workflow.documents SET state='published' WHERE snapshot_id=%s", (sid,))
    with pytest.raises(WorkflowDocumentStoreError, match="published_working_revision_immutable"):
        documents.apply_review_changes(sid, winner, winner, envelope, envelope)
    assert object_storage(documents, sid) == durable[0]


def test_native_transition_chain_keeps_each_history_guard(tmp_path, production_console):
    from src.review.revision_workflow import revise_object
    from tests.test_t9_review_knowledge_authority import _console

    console, reviewer, sid, focal = _console(tmp_path, production_console=production_console)
    documents = console.workflow_document_store
    before = documents.review_command_histories(sid, [focal['object_id']])
    envelope = documents.get_envelope(sid)
    governed = deepcopy(before)
    governed[-1]['governance']['validation_status'] = 'revise'
    successor = revise_object(governed[-1], governed[-1], snapshot_id=sid,
        reason='Synthetic staged successor', actor=reviewer['account_id'], force=True)
    after = [*governed, successor]
    durable = object_storage(documents, sid), document_counters(documents, sid)
    # Flattening would illegally change a now-historical row; only the actual
    # separately validated current-governance -> successor chain is accepted.
    with pytest.raises(WorkflowDocumentStoreError):
        documents.apply_review_changes(sid, before, after, envelope, envelope, commit_count=2)
    invalid = deepcopy(after)
    invalid[0]['governance']['validation_status'] = 'approved'
    with pytest.raises(WorkflowDocumentStoreError):
        documents.apply_review_changes(sid, before, invalid, envelope, envelope,
            commit_count=3, transitions=[governed, after, invalid])
    assert (object_storage(documents, sid), document_counters(documents, sid)) == durable
    documents.apply_review_changes(sid, before, after, envelope, envelope,
        commit_count=2, transitions=[governed, after])
    assert documents.review_command_histories(sid, [focal['object_id']]) == after


@pytest.mark.parametrize("legacy_null", [False, True])
def test_native_binding_delta_preserves_retained_tuple_occurrences_and_order(complete_postgres, legacy_null):
    documents, reviews, sid, reviewer = seed(complete_postgres)
    first = _authorization(sid, "delta-a", reviewer)
    other = _authorization(sid, "delta-b", reviewer)
    history = {**first, "object_version": "1.1"}
    reviews.replace_snapshot_bindings(sid, [first, other, history])
    if legacy_null:
        with reviews._connect() as con:
            con.execute("UPDATE workflow.publish_authorizations SET position=NULL WHERE snapshot_id=%s", (sid,))
    before = reviews.read_bindings([sid], object_ids=["delta-a"])[sid]
    with reviews._connect() as con:
        physical = con.execute(
            "SELECT authorization_id,position,object_id,authorization_payload,ctid::text AS physical,xmin::text AS writer "
            "FROM workflow.publish_authorizations WHERE snapshot_id=%s ORDER BY position NULLS LAST,authorization_id", (sid,),
        ).fetchall()
    counters = document_counters(documents, sid)
    after = [{**row, "valid": False} for row in before]
    after.append({**first, "object_version": "1.2"})
    reviews.apply_review_binding_delta(sid, before, after)
    with reviews._connect() as con:
        current = con.execute(
            "SELECT authorization_id,position,object_id,authorization_payload,ctid::text AS physical,xmin::text AS writer "
            "FROM workflow.publish_authorizations WHERE snapshot_id=%s ORDER BY position NULLS LAST,authorization_id", (sid,),
        ).fetchall()
    assert current[1] == physical[1]
    assert [row["authorization_id"] for row in current[:3]] == [row["authorization_id"] for row in physical]
    assert [row["position"] for row in current] == ([None] * 4 if legacy_null else [0, 1, 2, 3])
    assert reviews.read_bindings([sid])[sid] == [after[0], other, after[1], after[2]]
    assert document_counters(documents, sid) == counters
    with pytest.raises(WorkflowReviewStoreError, match="snapshot_object_write_conflict"):
        reviews.apply_review_binding_delta(sid, before, after)
    with pytest.raises(WorkflowReviewStoreError, match="removal_or_reorder"):
        reviews.apply_review_binding_delta(sid, after, list(reversed(after)))


def test_native_binding_fault_rolls_back_preceding_object_delta(complete_postgres):
    documents, reviews, sid, reviewer = seed(complete_postgres)
    bind_workflow_stores(documents, reviews)
    before = documents.review_command_histories(sid, ["delta-a"])
    after = deepcopy(before)
    after[-1]["text"] = "Should roll back"
    envelope = documents.get_envelope(sid)
    durable = object_storage(documents, sid), document_counters(documents, sid)
    with reviews._connect() as con:
        con.execute("CREATE FUNCTION workflow.delta_fault() RETURNS trigger LANGUAGE plpgsql AS $$ "
                    "BEGIN RAISE EXCEPTION 'controlled delta fault' USING ERRCODE='P9031'; END $$")
        con.execute("CREATE TRIGGER delta_fault BEFORE INSERT ON workflow.publish_authorizations "
                    "FOR EACH ROW EXECUTE FUNCTION workflow.delta_fault()")
    with pytest.raises(WorkflowReviewStoreError) as failed:
        with workflow_transaction(reviews):
            documents.apply_review_changes(sid, before, after, envelope, envelope)
            reviews.apply_review_binding_delta(sid, [], [_authorization(sid, "delta-a", reviewer)])
    assert failed.value.__cause__.sqlstate == "P9031"
    assert (object_storage(documents, sid), document_counters(documents, sid)) == durable
    assert reviews.read_bindings([sid]) == {}


def test_native_command_events_keep_global_interaction_identity_and_pending_levels(complete_postgres):
    documents, reviews, sid, reviewer = seed(complete_postgres)
    other_sid = "snap-other-review"
    envelope = documents.get_envelope(sid)
    documents.write_bundle(envelope=_envelope(other_sid, envelope["uploader_account_id"], reviewer), objects=_objects("other"))
    identity = {"interaction_id": "shared-interaction", "reviewer_account_id": reviewer,
                "snapshot_id": sid, "canonical_task": "passage"}
    foreign = reviews.append_event(event_type="review", object_id="delta-a", object_version="1.0",
        actor="reviewer", details={"snapshot_id": sid, "review_interaction": identity})
    local = reviews.append_event(event_type="review", object_id="other-a", object_version="1.0",
        actor="reviewer", details={"snapshot_id": other_sid})
    reviews.append_event(event_type="review", object_id="delta-b", object_version="1.0",
        actor="reviewer", details={"snapshot_id": sid})
    expected = [foreign, local]
    assert reviews.read_review_command_events(other_sid, ["other-a"], interaction_id="shared-interaction") == expected
    with pytest.raises(ValueError, match="review_interaction_identity_conflict"):
        validate_review_interaction_identity({**identity, "snapshot_id": other_sid}, expected)
    with reviews.buffered():
        expected.append(reviews.append_event(event_type="pending-local", object_id="other-a", object_version="1.0",
            actor="reviewer", details={"snapshot_id": other_sid}))
        with reviews.buffered():
            expected.append(reviews.append_event(event_type="pending-foreign", object_id="delta-b", object_version="1.0",
                actor="reviewer", details={"snapshot_id": sid, "review_interaction": identity}))
            assert reviews.read_review_command_events(other_sid, ["other-a"], interaction_id="shared-interaction") == expected
    assert reviews.read_review_command_events(other_sid, ["other-a"], interaction_id="shared-interaction") == expected
