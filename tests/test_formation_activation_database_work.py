"""W4 native generation accounting and bounded activation work.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from tests.test_review_command_storage_v1 import document_counters, object_storage
from tests.test_workflow_postgres_concurrency import _envelope, _seed_accounts
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore


def task_document(config, sid='snap-w4'):
    uploader, reviewer = _seed_accounts(config)
    store = PostgresConcurrentWorkflowDocumentStore(config)
    envelope = {**_envelope(sid, uploader, reviewer),
                'processing_storage': 'task-v1', 'processing_attempts': []}
    store.write_bundle(envelope=envelope, objects=[])
    return store, sid


def test_full_activation_bounds_document_rewrites_without_losing_rows(complete_postgres):
    store, sid = task_document(complete_postgres)
    before = document_counters(store, sid)
    with store._connect() as con:
        con.execute('CREATE TABLE workflow.w4_generation_observations (increment bigint NOT NULL)')
        con.execute('CREATE FUNCTION workflow.w4_observe_generation() RETURNS trigger LANGUAGE plpgsql AS $$ '
            'BEGIN INSERT INTO workflow.w4_generation_observations VALUES '
            '(NEW.object_generation-OLD.object_generation); RETURN NEW; END $$')
        con.execute('CREATE TRIGGER w4_observe_generation AFTER UPDATE OF object_generation ON workflow.documents '
            'FOR EACH ROW WHEN (NEW.object_generation IS DISTINCT FROM OLD.object_generation) '
            'EXECUTE FUNCTION workflow.w4_observe_generation()')
    objects = [{'object_id': f'w4-{i}', 'object_version': '1.0', 'text': f'Candidate {i}'}
               for i in range(261)]
    store.write_bundle(envelope=store.get_envelope(sid), objects=objects)
    rows = object_storage(store, sid)
    assert [(r['position'], r['payload']) for r in rows] == list(enumerate(objects))
    assert document_counters(store, sid)['object_generation'] == before['object_generation'] + len(objects)
    with store._connect() as con:
        observed = con.execute('SELECT count(*) AS updates,sum(increment) AS increment '
            'FROM workflow.w4_generation_observations').fetchone()
    assert observed['increment'] == len(objects)
    assert observed['updates'] <= 4, 'Activation repeats the full document update for individual object rows'
    # A new owner reads the same actual rows and usable lineage certificates.
    fresh = PostgresConcurrentWorkflowDocumentStore(complete_postgres)
    assert fresh.list_document_objects(sid) == objects
    assert fresh.review_command_window(sid, [o['object_id'] for o in objects]) is not None
