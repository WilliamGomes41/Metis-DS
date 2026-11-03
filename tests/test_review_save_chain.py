"""Ordinary HTTP save and navigation use the existing prepared owners.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import re
import json

import pytest

from tests.test_v233_review_audit_regressions import review_system


def form(client, sid, oid):
    page = client.get('/review', params={'document': sid, 'object': oid})
    assert page.status_code == 200
    revision = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text).group(1)
    return {'snapshot_id': sid, 'object_id': oid, 'snapshot_revision': revision,
            'suitability': 'ja', 'documentpositie_action': 'dit_klopt',
            'type_action': 'dit_klopt', 'confirmed_object_type': 'definition',
            'eindoordeel': 'goedkeuren', 'decision': 'approve', 'relation_review_ack': '1'}


def test_ordinary_http_kernel_runs_without_write_lock_or_workflow_io(review_system, monkeypatch):
    from src.review.review_command_state_v1 import active_review_command
    from src.workflows.workflow_transaction_v1 import workflow_transaction_active, WorkflowTransactionError
    console, client, sid, actor, ids = review_system
    data = form(client, sid, ids[0])
    original = console.review_object
    observed = []

    def probe(*args, **kwargs):
        state = active_review_command(console)
        if state is not None:
            assert not console._store_lock_depth, 'ordinary kernel still holds the outer write lock'
            assert not workflow_transaction_active(), 'ordinary kernel still holds a SQL transaction'
            assert state.preparing
            with pytest.raises(WorkflowTransactionError, match='workflow_io_during_review_preparation'):
                console.workflow_document_store._connect()
            observed.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(console, 'review_object', probe)
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    assert observed == [True]
    assert next(o for o in console.snapshot_objects(sid) if o['object_id'] == ids[0])['governance']['validation_status'] == 'approved'
    assert any(b['object_id'] == ids[0] and b['reviewer_id'] == actor for b in console.object_review_bindings(sid))


@pytest.mark.parametrize('task', ['', 'contextual'])
def test_next_passage_uses_verified_cards_then_real_passage(tmp_path, production_console, monkeypatch, task):
    from fastapi.testclient import TestClient
    from tests.test_review_formation_problems import received, execute
    from tests.test_review_command_bounded_http_v1 import submission
    from tests.test_availability_repair import login
    from src.workflows.review_card_inputs_postgres_v1 import prepare_review_cards
    from tests.production_support import restart_production
    console, sid, author, _actor, _calls, mode, _provider = received(tmp_path, production_console, monkeypatch)
    mode['broken'] = False
    execute(console, sid, author, 'ordinary-next-proof')
    candidates = [o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == 'recommendation']
    assert len(candidates) == 2
    ids = [o['object_id'] for o in candidates]
    client = TestClient(console._metis_test_application, base_url='https://console.example.test',
                        headers={'Origin': 'https://console.example.test'})
    login(client, 'reviewer')
    prepare_review_cards(console.workflow_document_store, sid)
    opened = client.get('/review', params={'document': sid, 'object': ids[0]})
    assert opened.status_code == 200
    data = {**submission(opened, sid, candidates[0]), 'return_task': task}
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    store = console.workflow_document_store
    with monkeypatch.context() as patch:
        def forbidden(*args, **kwargs):
            raise AssertionError('next-passage navigation evaluated the complete document')
        patch.setattr(store, 'formation_input', forbidden)
        patch.setattr(store, 'review_document_window', forbidden)
        patch.setattr(store, 'list_document_objects', forbidden)
        page = client.get(saved.headers['location'])
    assert page.status_code == 200, page.text
    assert f'id="review-form-{ids[1]}"' in page.text
    assert f'id="review-form-{ids[0]}"' not in page.text
    reopened = client.get('/review', params={'document': sid, 'object': ids[0]})
    assert reopened.status_code == 200
    restarted = restart_production(console)
    assert next(o for o in restarted.snapshot_objects(sid) if o['object_id'] == ids[0])['governance']['validation_status'] == 'approved'


@pytest.mark.parametrize('change', ['role', 'identity', 'roster', 'policy', 'source', 'quality', 'native0', 'binding', 'new_inbound'])
def test_ordinary_prepared_save_rechecks_current_dependencies(review_system, monkeypatch, change):
    from src.integrity_kernel import compute_canonical_object_hash
    from src.operations_console_v1 import ConsoleError
    from src.review.review_passage_read_v1 import _revision
    from tests.test_prepared_review_batches import before_commit, durable
    from tests.production_support import restart_production
    console, _client, sid, actor, ids = review_system
    store = console.workflow_document_store
    _, generation = store.review_document_input(sid)
    focal = next(o for o in console.snapshot_objects(sid) if o['object_id'] == ids[0])
    winner = []

    def mutation():
        with store._connect() as con:
            if change == 'role':
                con.execute("UPDATE workflow.accounts SET roles=ARRAY['researcher']::text[] WHERE account_id=%s", (actor,))
            elif change == 'identity':
                con.execute("UPDATE workflow.accounts SET display_name='Changed reviewer' WHERE account_id=%s", (actor,))
            elif change == 'native0':
                con.execute('UPDATE workflow.documents SET processing_storage_version=0 WHERE snapshot_id=%s', (sid,))
                con.execute('UPDATE workflow.document_objects SET payload=payload WHERE snapshot_id=%s AND object_id=%s', (sid, ids[0]))
            elif change == 'binding':
                console.workflow_review_store.apply_review_binding_delta(sid, [], [{
                    'object_id': ids[0], 'object_version': focal['object_version'],
                    'canonical_object_hash': compute_canonical_object_hash(focal),
                    'confirmed_object_type': 'definition', 'reviewer_id': actor,
                    'reviewer': console._account(actor)['display_name'], 'decision': 'approve', 'valid': True}])
            elif change == 'new_inbound':
                con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{confirmed_relations}',%s::jsonb,true) "
                            'WHERE snapshot_id=%s AND object_id=%s',
                            (json.dumps([{'relation_type': 'supported_by', 'target_object_id': ids[0]}]), sid, ids[1]))
            else:
                key, value = {'roster': ('named_reviewers', []), 'policy': ('review_policy', {'contract': 'changed'}),
                              'source': ('sha256', '0' * 64),
                              'quality': ('quality_processing_runs', [{'run_id': 'changed', 'candidates': []}])}[change]
                con.execute('UPDATE workflow.documents SET envelope_payload=jsonb_set(envelope_payload,%s,%s::jsonb,true),'
                            'review_read_envelope=NULL WHERE snapshot_id=%s', ([key], json.dumps(value), sid))
                if change == 'source':
                    con.execute('UPDATE workflow.documents SET source_sha256=%s WHERE snapshot_id=%s', ('0' * 64, sid))
                elif change == 'roster':
                    con.execute('DELETE FROM workflow.document_reviewers WHERE snapshot_id=%s', (sid,))
        winner.append(durable(console, sid))

    before_commit(console, monkeypatch, mutation)
    with pytest.raises(ConsoleError):
        console.review_object(actor_id=actor, snapshot_id=sid, object_id=ids[0], decision='approve',
                              confirmed_object_type='definition', expected_revision=_revision(sid, generation),
                              _compact_result=True)
    assert winner and durable(console, sid) == winner[0]
    assert durable(restart_production(console), sid) == winner[0]
    assert console.workflow_review_store._buffer.get() is None


def test_ordinary_late_commit_failure_rolls_back_decision_bindings_facts_and_audit(review_system):
    from tests.test_prepared_review_batches import durable
    from tests.production_support import restart_production
    console, client, sid, _actor, ids = review_system
    data = form(client, sid, ids[0])
    with console.workflow_document_store._connect() as con:
        con.execute("CREATE FUNCTION workflow.ordinary_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                    "BEGIN RAISE EXCEPTION 'ordinary_deferred_commit_failure'; END $$")
        con.execute('CREATE CONSTRAINT TRIGGER ordinary_commit_failure AFTER UPDATE ON workflow.documents '
                    'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.ordinary_commit_failure()')
    before = durable(console, sid)
    with pytest.raises(Exception) as refused:
        client.post('/review', data=data, follow_redirects=False)
    def failures(error):
        yield str(error)
        if error.__cause__ is not None:
            yield from failures(error.__cause__)
        for child in getattr(error, 'exceptions', ()):
            yield from failures(child)
    assert any('ordinary_deferred_commit_failure' in value for value in failures(refused.value))
    assert durable(restart_production(console), sid) == before
    assert console.workflow_review_store._buffer.get() is None


def test_passage_read_keeps_lineage_without_downloading_retained_prefix(review_system):
    from copy import deepcopy
    from src.review.revision_workflow import revise_object
    from src.workflows.workflow_transaction_v1 import workflow_read_transaction
    from src.console_performance_v1 import performance_scope
    console, _client, sid, actor, ids = review_system
    rows = console._load_objects(sid)
    previous = next(o for o in rows if o['object_id'] == ids[0])
    for _ in range(512):
        previous = revise_object(previous, deepcopy(previous), snapshot_id=sid,
                                 reason='Retained synthetic review history', actor=actor, force=True)
        rows.append(previous)
    console._save_objects(sid, rows, expected_revision=console.objects_revision(sid))
    store = console.workflow_document_store
    with performance_scope() as metrics:
        with workflow_read_transaction(store):
            selected = store.review_object_histories(sid, [ids[0]])
    assert selected == [previous]
    assert metrics.json_bytes < 128_000, f'one passage downloaded {metrics.json_bytes} JSON bytes'
