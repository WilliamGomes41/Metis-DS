"""W4 native generation accounting and bounded activation work.

# release-control-evidence: scope/belofte same durable result with bounded activation writes
# release-control-evidence: opslag concurrent stale recovery exact row generations
# release-control-evidence: toegang existing restricted writer privileges
# release-control-evidence: beschikbaarheid interrupt resume without repeated provider calls
# release-control-evidence: kwaliteit exact ordered objects and retained task results
# release-control-evidence: slop existing document owner and task authority, no parallel store
# release-control-evidence: releasebewijs native database rollback and restart proofs
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from tests.test_prepared_review_batches import durable
from tests.test_review_command_storage_v1 import document_counters, object_storage
from tests.test_workflow_postgres_concurrency import _envelope, _seed_accounts
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError

MIGRATION = Path(__file__).resolve().parents[1] / 'db/migrations/033_statement_object_generation.sql'


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


@pytest.mark.parametrize('fault', ['suppress', 'rewrite', 'identity', 'position', 'hidden', 'commit'])
def test_fault_in_later_insert_group_rolls_back_every_participant(complete_postgres, fault):
    store, sid = task_document(complete_postgres)
    prior = [{'object_id': 'retained', 'object_version': '1.0', 'text': 'Existing work'}]
    store.write_bundle(envelope=store.get_envelope(sid), objects=prior)
    before = durable(SimpleNamespace(workflow_document_store=store), sid), object_storage(store, sid)
    actions = {
        'suppress': 'RETURN NULL;',
        'rewrite': "NEW.payload=jsonb_set(NEW.payload,'{text}','\"Wrong text\"'); RETURN NEW;",
        'identity': "NEW.object_id='wrong-identity'; RETURN NEW;",
        'position': 'NEW.position=NEW.position+1000; RETURN NEW;',
        'hidden': "UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{text}',"
                  "'\"Hidden edit\"') WHERE snapshot_id=NEW.snapshot_id AND object_id='retained'; RETURN NEW;",
        'commit': "RAISE EXCEPTION 'w4_late_commit_fault';",
    }
    with store._connect() as con:
        con.execute('CREATE FUNCTION workflow.w4_insert_fault() RETURNS trigger LANGUAGE plpgsql AS $$ '
            "BEGIN IF NEW.object_id='added-129' THEN " + actions[fault] + ' END IF; RETURN NEW; END $$')
        if fault == 'commit':
            con.execute('CREATE CONSTRAINT TRIGGER w4_insert_fault AFTER INSERT ON workflow.document_objects '
                'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.w4_insert_fault()')
        else:
            timing = 'AFTER' if fault == 'hidden' else 'BEFORE'
            con.execute(f'CREATE TRIGGER w4_insert_fault {timing} INSERT ON workflow.document_objects '
                'FOR EACH ROW EXECUTE FUNCTION workflow.w4_insert_fault()')
    additions = [{'object_id': f'added-{i}', 'object_version': '1.0', 'text': f'Added {i}'}
                 for i in range(261)]
    expected_error = 'workflow_document_bundle_write_failed' if fault == 'commit' else 'snapshot_object_write_conflict'
    with pytest.raises(WorkflowDocumentStoreError, match=expected_error):
        store.write_bundle(envelope=store.get_envelope(sid), objects=prior + additions)
    assert (durable(SimpleNamespace(workflow_document_store=store), sid), object_storage(store, sid)) == before


def test_generation_counts_actual_rows_across_documents_and_dml(complete_postgres):
    store, first = task_document(complete_postgres)
    second, legacy = 'snap-w4-second', 'snap-w4-native0'
    for sid in (second, legacy):
        envelope = _envelope(sid, 'acc-uploader', 'acc-reviewer')
        if sid == second:
            envelope.update(processing_storage='task-v1', processing_attempts=[])
        store.write_bundle(envelope=envelope, objects=[])
    def generations():
        return [document_counters(store, sid)['object_generation'] for sid in (first, second, legacy)]
    assert generations() == [0, 0, 0]
    with store._connect() as con:
        con.execute("INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,position,payload) "
            "SELECT sid,oid,'1.0',pos,jsonb_build_object('object_id',oid,'object_version','1.0','text','A') "
            "FROM unnest(%s::text[]) AS sid CROSS JOIN (VALUES('a',0),('b',1)) AS v(oid,pos)",
            ([first, second, legacy],))
    assert generations() == [2, 2, 0]
    with store._connect() as con:
        con.execute('UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id=ANY(%s)',
                    ([first, second, legacy],))
    assert generations() == [4, 4, 0]
    with store._connect() as con:
        con.execute("INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,position,payload) "
            "SELECT %s,oid,'1.0',pos,jsonb_build_object('object_id',oid,'object_version','1.0','text','A') "
            "FROM (VALUES('a',0),('c',2)) AS v(oid,pos) "
            "ON CONFLICT(snapshot_id,object_id,object_version) DO UPDATE SET payload=EXCLUDED.payload", (first,))
    assert generations() == [6, 4, 0]  # One real insert and one real update, no double count.
    with store._connect() as con:
        con.execute("DELETE FROM workflow.document_objects WHERE snapshot_id=ANY(%s) AND object_id='b'",
                    ([first, second, legacy],))
        con.execute("UPDATE workflow.document_objects SET payload=payload WHERE object_id='absent'")
        con.execute("DELETE FROM workflow.document_objects WHERE object_id='absent'")
        con.execute('INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,position,payload) '
            'SELECT snapshot_id,object_id,object_version,position,payload FROM workflow.document_objects WHERE false')
    assert generations() == [7, 5, 0]
    with pytest.raises(RuntimeError, match='rollback'):
        with store._connect() as con:
            con.execute('UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id=%s', (first,))
            raise RuntimeError('rollback')
    assert generations() == [7, 5, 0]


def test_migration_is_repeatable_and_old_trigger_and_writer_remain_compatible(complete_postgres):
    store, sid = task_document(complete_postgres)
    initial = [{'object_id': 'kept', 'object_version': '1.0', 'text': 'Kept'}]
    store.write_bundle(envelope=store.get_envelope(sid), objects=initial)
    before = durable(SimpleNamespace(workflow_document_store=store), sid)
    with store._connect() as con:
        for _ in range(2):
            con.execute(MIGRATION.read_text())
    assert durable(SimpleNamespace(workflow_document_store=store), sid) == before
    with store._connect() as con:
        # Exact previous generation trigger: rollback changes no stored data.
        for operation in ('insert', 'update', 'delete'):
            con.execute('DROP TRIGGER advance_object_generation_' + operation + ' ON workflow.document_objects')
        con.execute('CREATE TRIGGER advance_object_generation AFTER INSERT OR UPDATE OR DELETE '
            'ON workflow.document_objects FOR EACH ROW EXECUTE FUNCTION workflow.advance_object_generation()')
    rows = initial + [{'object_id': f'old-schema-{i}', 'object_version': '1.0', 'text': 'Old trigger'} for i in range(7)]
    store.write_bundle(envelope=store.get_envelope(sid), objects=rows)
    assert document_counters(store, sid)['object_generation'] == len(rows)
    before_upgrade = durable(SimpleNamespace(workflow_document_store=store), sid)
    with store._connect() as con:
        con.execute(MIGRATION.read_text())
    assert durable(SimpleNamespace(workflow_document_store=store), sid) == before_upgrade
    with store._connect() as con:
        # An old single-row SQL writer needs no new API or bypass setting.
        con.execute('UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id=%s AND object_id=%s',
                    (sid, 'kept'))
    assert document_counters(store, sid)['object_generation'] == len(rows) + 1
    assert store.list_document_objects(sid) == rows


def test_concurrent_disjoint_sql_statements_keep_exact_generation(complete_postgres):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    store, sid = task_document(complete_postgres)
    rows = [{'object_id': f'c-{i}', 'object_version': '1.0', 'text': 'Independent'} for i in range(4)]
    store.write_bundle(envelope=store.get_envelope(sid), objects=rows)
    barrier = Barrier(2)
    def change(ids):
        with psycopg.connect(complete_postgres.dsn) as con:
            barrier.wait(timeout=5)
            return con.execute('UPDATE workflow.document_objects SET payload=payload '
                'WHERE snapshot_id=%s AND object_id=ANY(%s)', (sid, ids)).rowcount
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(change, [['c-0', 'c-1'], ['c-2', 'c-3']])) == [2, 2]
    assert document_counters(store, sid)['object_generation'] == 8
    assert store.list_document_objects(sid) == rows


def test_restricted_old_writer_maintains_task_generation_without_new_grants(complete_postgres):
    from uuid import uuid4
    from psycopg import sql
    role = 'w4_writer_' + uuid4().hex
    store, sid = task_document(complete_postgres)
    rows = [{'object_id': f'old-{i}', 'object_version': '1.0', 'text': 'Existing'} for i in range(3)]
    store.write_bundle(envelope=store.get_envelope(sid), objects=rows)
    with psycopg.connect(complete_postgres.dsn, autocommit=True) as con:
        con.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
        try:
            con.execute(sql.SQL('GRANT USAGE ON SCHEMA workflow TO {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('GRANT SELECT,UPDATE ON workflow.documents TO {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('GRANT SELECT ON workflow.document_inputs TO {}').format(sql.Identifier(role)))
            # Same privileges required by the previous generation/frontier/fact triggers.
            con.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE ON workflow.document_objects, '
                'workflow.object_revision_frontiers,workflow.review_fact_state,workflow.review_object_facts '
                'TO {}').format(sql.Identifier(role)))
            for operation in ('insert', 'update', 'delete'):
                con.execute('DROP TRIGGER advance_object_generation_' + operation + ' ON workflow.document_objects')
            con.execute('CREATE TRIGGER advance_object_generation AFTER INSERT OR UPDATE OR DELETE '
                'ON workflow.document_objects FOR EACH ROW EXECUTE FUNCTION workflow.advance_object_generation()')
            con.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
            assert con.execute("UPDATE workflow.document_objects SET payload=payload "
                "WHERE snapshot_id=%s AND object_id='old-0'", (sid,)).rowcount == 1
            con.execute('RESET ROLE')
            assert document_counters(store, sid)['object_generation'] == 4
            con.execute(MIGRATION.read_text())
            con.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
            assert con.execute('UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id=%s',
                               (sid,)).rowcount == 3
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                con.execute('CREATE TABLE workflow.w4_forbidden (id integer)')
            con.execute('RESET ROLE')
            assert document_counters(store, sid)['object_generation'] == 7
            assert store.list_document_objects(sid) == rows
        finally:
            con.execute('RESET ROLE')
            con.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


def test_task_activation_works_with_controlled_schema_without_optional_cards(complete_postgres):
    from tests.postgres_support import database
    from src.workflows.workflow_postgres_migration_v1 import migration_paths
    root = MIGRATION.parents[2]
    with database(complete_postgres.dsn) as config:
        with psycopg.connect(config.dsn, autocommit=True) as con:
            con.execute((root / 'db/schema_v2.sql').read_text())
            for path in migration_paths(root):
                con.execute(path.read_text())
            assert con.execute("SELECT to_regclass('workflow.review_object_facts')").fetchone()[0] is None
        store, sid = task_document(config)
        objects = [{'object_id': f'no-card-{i}', 'object_version': '1.0', 'text': 'Candidate'} for i in range(129)]
        store.write_bundle(envelope=store.get_envelope(sid), objects=objects)
        assert store.list_document_objects(sid) == objects
        assert document_counters(store, sid)['object_generation'] == len(objects)
        assert store.review_command_window(sid, [o['object_id'] for o in objects]) is not None


def test_bulk_object_change_invalidates_existing_formation_checkpoint(tmp_path, production_console):
    from src.operations_console_v1 import ConsoleError
    from tests.test_formation_task_store_postgres import prepared, checkpoint_context
    console, envelope, data = prepared(tmp_path, production_console)
    writer = checkpoint_context(console, envelope, data)
    with console.workflow_document_store._connect() as con:
        before = con.execute('SELECT count(*) AS n FROM workflow.processing_checkpoints').fetchone()['n']
        changed = con.execute('UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id=%s',
                              (writer.snapshot_id,)).rowcount
    assert changed > 1
    with pytest.raises(ConsoleError, match='processing_command_conflict'):
        writer('model_request', {'current_task': {'task_id': 'stale-after-bulk-write'}})
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.processing_checkpoints').fetchone()['n'] == before


@pytest.mark.parametrize('azure', [False, True])
def test_resume_keeps_task_commits_through_late_activation_failure_and_restart(
        tmp_path, production_console, monkeypatch, azure):
    import json
    from src.operations_console_v1 import ConsoleError
    from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.vorming.source_bound_fields_v3 import MODE
    from tests.production_support import restart_production
    from tests.test_recommendation_context_v3 import response_for
    calls = []
    def provider(_url, _headers, payload, _timeout):
        text = json.loads(payload['input'][1]['content'])['source_blocks'][0]['text']
        calls.append(text)
        if len(calls) == 2:
            raise ConsoleError('processing_fixture_interrupted')
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(response_for(payload, text))}]}]}
    def bind(console):
        bind_pre_review_semantic_processing(console, environ={'METIS_PASSAGE_FORMATION_MODE': MODE,
            'METIS_LLM_API_KEY': 'fixture', 'METIS_LLM_MODEL': 'test'}, post_json=provider)
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console = production_console(root=tmp_path, azure=azure, processing_binder=bind)
    author = console.create_account(username='author', password='fixture-only', roles=('researcher',))['account_id']
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))['account_id']
    count = 6
    source = ('<html><body>' + ''.join(f'<h1>Stap {i}</h1><p>Controleer dagelijks de huid bij patiënt {i}.</p>'
        for i in range(count)) + '</body></html>').encode()
    sid = console.receive_source(actor_id=author, filename='resume.html', content_type='text/html', data=source,
        ingest_kind='new', title='Resume', version='1', date='2026-11-07', live_url='', class_='richtlijn',
        family='test', named_reviewers=[reviewer])['snapshot_id']
    def attempt(command):
        return console.reserve_source_selection(actor_id=author, snapshot_id=sid, command_id=command,
            expected_revision=console.objects_revision(sid))[0]
    with pytest.raises(ConsoleError, match='processing_fixture_interrupted'):
        console.execute_source_selection(actor_id=author, snapshot_id=sid, attempt=attempt('initial'))
    store = console.workflow_document_store
    with store._connect() as con:
        first = con.execute('SELECT context_id,ranges_hash,result_hash,payload FROM workflow.formation_task_results').fetchone()
    assert first is not None
    old_objects = object_storage(store, sid)
    old_generation = document_counters(store, sid)['object_generation']
    console = restart_production(console)
    with store._connect() as con:
        con.execute("CREATE FUNCTION workflow.w4_fail_activation() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'w4_activation_commit_fault'; END $$")
        con.execute('CREATE CONSTRAINT TRIGGER w4_fail_activation AFTER INSERT ON workflow.document_objects '
            'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.w4_fail_activation()')
    from psycopg.errors import RaiseException
    with pytest.raises(RaiseException, match='w4_activation_commit_fault'):
        console.execute_source_selection(actor_id=author, snapshot_id=sid, attempt=attempt('late-failure'))
    assert object_storage(store, sid) == old_objects
    assert document_counters(store, sid)['object_generation'] == old_generation
    with store._connect() as con:
        committed = con.execute('SELECT context_id,ranges_hash,result_hash,payload FROM workflow.formation_task_results '
            'ORDER BY ranges_hash').fetchall()
        assert len(committed) == count and first in committed
        con.execute('DROP TRIGGER w4_fail_activation ON workflow.document_objects')
    assert len(calls) == count + 1
    console = restart_production(console)
    console.execute_source_selection(actor_id=author, snapshot_id=sid, attempt=attempt('retry-activation'))
    assert len(calls) == count + 1, 'Committed task results were sent to the provider again'
    expected = deepcopy(console.snapshot_objects(sid))
    assert expected and console._envelope(sid)['processing_attempts'][-1]['state'] == 'succeeded'
    with store._connect() as con:
        assert con.execute('SELECT context_id,ranges_hash,result_hash,payload FROM workflow.formation_task_results '
            'ORDER BY ranges_hash').fetchall() == committed
    final = restart_production(console)
    assert final.snapshot_objects(sid) == expected
    assert final._verified_source_bytes(final._envelope(sid))[1] == source
    assert not final.publication_readiness(sid)['publish_allowed']
