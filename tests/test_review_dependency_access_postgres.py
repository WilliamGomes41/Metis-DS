"""Real dependency lookup budget and derived-access parity, not a closure oracle.

# release-control-evidence: scope/belofte opslag kwaliteit beschikbaarheid releasebewijs
"""
import json
import random
import time
from pathlib import Path

import pytest
from psycopg.types.json import Jsonb

from tests.postgres_support import database
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores, workflow_read_transaction


@pytest.fixture
def dependency_store(complete_postgres):
    # This is the actual SQL-store seam in a native disposable PG database.
    # It deliberately creates no KnowledgeCandidates or publication authority.
    with database(complete_postgres.dsn) as config:
        store = PostgresConcurrentWorkflowDocumentStore(config)
        bind_workflow_stores(store)
        with store._connect() as con:
            con.execute('CREATE SCHEMA workflow')
            con.execute('CREATE TABLE workflow.document_objects(snapshot_id text,object_id text,position bigint,payload jsonb,PRIMARY KEY(snapshot_id,position))')
            con.execute('CREATE INDEX idx_workflow_document_objects_current ON workflow.document_objects(snapshot_id,object_id,position)')
            con.execute('CREATE INDEX workflow_document_objects_dependencies ON workflow.document_objects USING gin(payload jsonb_path_ops)')
            migration = Path(__file__).resolve().parents[1] / 'db/migrations/031_review_dependency_keys.sql'
            if migration.exists():
                con.execute(migration.read_text())
        yield store


def test_real_lookup_stays_inside_original_read_transaction_with_large_unrelated_payload(dependency_store):
    store = dependency_store
    random_source = random.Random(951)
    rows = []
    for index in range(1100):
        payload = {'object_id': f'object-{index}', 'metadata': {
            'independent_retained_content': ''.join(random_source.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ', k=16000))}, 'relations': []}
        if index % 100 == 0:
            payload['relations'] = [{'target_object_id': 'object-0'}]
        rows.append(('snapshot', f'object-{index}', index, Jsonb(payload)))
    with store._connect() as con:
        with con.cursor() as cursor:
            cursor.executemany('INSERT INTO workflow.document_objects(snapshot_id,object_id,position,payload) VALUES(%s,%s,%s,%s)', rows)
        con.execute('ANALYZE workflow.document_objects')
    expected = {f'object-{i}' for i in range(0, 1100, 100)}
    started = time.monotonic()
    with workflow_read_transaction(store) as con:
        con.execute("SET LOCAL enable_indexscan=off")
        con.execute("SET LOCAL enable_bitmapscan=off")
        assert set(store.review_neighbor_ids('snapshot', [f'object-{i}' for i in range(150)], [f'block-{i}' for i in range(150)])) == expected
        assert set(store.review_command_neighbor_ids('snapshot', [f'object-{i}' for i in range(150)])) == expected
    print(json.dumps({'proof': 'current_dependency_capture', 'objects': 1100, 'payload_chars': 16000, 'targets': 150, 'seconds': round(time.monotonic()-started, 4)}))


def test_current_dependencies_ignore_superseded_edges_and_keep_all_required_current_edges(dependency_store):
    store = dependency_store
    rows = [
        ('snapshot', 'old-only', 1, Jsonb({'relations': [{'target_object_id': 'target'}]})),
        ('snapshot', 'old-only', 2, Jsonb({'relations': []})),
        ('snapshot', 'current-link', 3, Jsonb({'metadata': {'confirmed_source_context': [{'source_object_id': 'target'}]}})),
        ('snapshot', 'block-link', 4, Jsonb({'metadata': {'source_bound_context': {'entries': [{'span': {'block_id': 'block'}}]}}})),
        ('other-snapshot', 'cross-snapshot', 5, Jsonb({'relations': [{'target_object_id': 'target'}]})),
    ]
    with store._connect() as con:
        with con.cursor() as cursor:
            cursor.executemany('INSERT INTO workflow.document_objects(snapshot_id,object_id,position,payload) VALUES(%s,%s,%s,%s)', rows)
    with workflow_read_transaction(store):
        assert set(store.review_neighbor_ids('snapshot', ['target'], ['block'])) == {'current-link', 'block-link'}
        assert set(store.review_command_neighbor_ids('snapshot', ['target'])) == {'current-link'}


@pytest.mark.parametrize('payload', [
    {}, {'relations': None}, {'relations': {}}, {'relations': ['target', None, 1]},
    {'relations': [{'target_object_id': 'target'}, {'target_object_id': 'target'}]},
    {'confirmed_relations': [{'target_object_id': 'target'}]},
    {'proposed_knowledge_relations': [{'target_object_id': 'target'}]},
    {'confirmed_knowledge_relations': [{'target_object_id': 'target'}]},
    {'relations': [{'target_object_id': 1}, {'target_object_id': True}, {'target_object_id': None}]},
    {'metadata': None}, {'metadata': {'confirmed_source_context': None}},
    {'metadata': {'confirmed_source_context': [{'source_object_id': 'target'}]}},
    {'metadata': {'source_bound_context': {'entries': [{'span': {'block_id': 'block'}}]}}},
    {'metadata': {'source_bound_context': {'entries': [{'span': {'block_id': 1}}, {}, 'block']}}},
])
def test_generated_keys_match_original_json_containment_without_reinterpreting_payload(dependency_store, payload):
    store = dependency_store
    families = ('proposed_knowledge_relations', 'confirmed_knowledge_relations', 'relations', 'confirmed_relations')
    original_probes = [json.dumps({key: [{'target_object_id': 'target'}]}) for key in families]
    original_probes += [json.dumps({'metadata': {'confirmed_source_context': [{'source_object_id': 'target'}]}}),
                        json.dumps({'metadata': {'source_bound_context': {'entries': [{'span': {'block_id': 'block'}}]}}})]
    with store._connect() as con:
        con.execute('INSERT INTO workflow.document_objects(snapshot_id,object_id,position,payload) VALUES(%s,%s,%s,%s)', ('snapshot', 'candidate', 1, Jsonb(payload)))
        expected = con.execute('SELECT object_id FROM workflow.document_objects WHERE snapshot_id=%s AND payload @> ANY(%s::jsonb[])', ('snapshot', original_probes)).fetchall()
        original_text = con.execute('SELECT payload::text AS value FROM workflow.document_objects').fetchone()['value']
    with workflow_read_transaction(store):
        assert set(store.review_neighbor_ids('snapshot', ['target'], ['block'])) == {row['object_id'] for row in expected}
    with store._connect() as con:
        assert con.execute('SELECT payload::text AS value FROM workflow.document_objects').fetchone()['value'] == original_text


def test_legacy_writer_restore_and_failed_write_keep_one_derived_owner(dependency_store):
    import psycopg
    store = dependency_store
    with store._connect() as con:
        con.execute('INSERT INTO workflow.document_objects(snapshot_id,object_id,position,payload) VALUES(%s,%s,%s,%s)',
                    ('snapshot', 'candidate', 1, Jsonb({'relations': [{'target_object_id': 'before'}]})))
    assert store.review_command_neighbor_ids('snapshot', ['before']) == ['candidate']
    with pytest.raises(psycopg.Error):
        with store._connect() as con:
            con.execute('UPDATE workflow.document_objects SET review_dependency_keys=%s', (Jsonb({'objects': ['forged'], 'blocks': []}),))
    with pytest.raises(psycopg.Error):
        with store._connect() as con:
            con.execute('UPDATE workflow.document_objects SET payload=%s', (Jsonb({'relations': [{'target_object_id': 'uncommitted'}]}),))
            con.execute('SELECT 1/0')
    assert store.review_command_neighbor_ids('snapshot', ['before']) == ['candidate']
    assert store.review_command_neighbor_ids('snapshot', ['forged', 'uncommitted']) == []
    with store._connect() as con:
        con.execute('UPDATE workflow.document_objects SET payload=%s', (Jsonb({'relations': [{'target_object_id': 'after'}]}),))
        retained = con.execute('SELECT snapshot_id,object_id,position,payload FROM workflow.document_objects').fetchone()
        con.execute('DELETE FROM workflow.document_objects')
        con.execute('INSERT INTO workflow.document_objects(snapshot_id,object_id,position,payload) VALUES(%s,%s,%s,%s)',
                    (retained['snapshot_id'], retained['object_id'], retained['position'], Jsonb(retained['payload'])))
        migration = Path(__file__).resolve().parents[1] / 'db/migrations/031_review_dependency_keys.sql'
        con.execute(migration.read_text())
    assert store.review_command_neighbor_ids('snapshot', ['before']) == []
    assert store.review_command_neighbor_ids('snapshot', ['after']) == ['candidate']


def test_startup_rejects_missing_or_manually_forged_dependency_storage(complete_postgres):
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    store = PostgresConcurrentWorkflowDocumentStore(complete_postgres)
    store.verify_cutover_schema()
    with store._connect() as con:
        con.execute('ALTER TABLE workflow.document_objects DROP COLUMN review_dependency_keys')
    with pytest.raises(WorkflowDocumentStoreError, match='cutover_schema_missing'):
        store.verify_cutover_schema()
    with store._connect() as con:
        con.execute('ALTER TABLE workflow.document_objects ADD COLUMN review_dependency_keys JSONB')
    with pytest.raises(WorkflowDocumentStoreError, match='dependency_schema_invalid'):
        store.verify_cutover_schema()
    migration = Path(__file__).resolve().parents[1] / 'db/migrations/031_review_dependency_keys.sql'
    import psycopg
    with pytest.raises(psycopg.Error, match='dependency_schema_invalid'):
        with store._connect() as con:
            con.execute(migration.read_text())
