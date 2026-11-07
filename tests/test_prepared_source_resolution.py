"""W1: complete HTTP repair is prepared without a write lock or SQL transaction.
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale restart rollback
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from src.review.review_command_state_v1 import active_review_command
from src.workflows.workflow_transaction_v1 import workflow_transaction_active
from tests.test_a09_source_repair import setup_repair, assert_complete, PASSWORD
from fastapi.testclient import TestClient
from contextlib import contextmanager
import json
import pytest
from src.operations_console_v1 import ConsoleError
from src.review.review_ledger import read_events
from tests.test_prepared_review_batches import durable


def command_for(console, sid, obj, reviewer, units):
    return dict(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=obj['object_id'],
                expected_revision=console.objects_revision(sid), suitability='mist_context',
                comment='Exacte bronselectie.', repair_kind='source_units',
                source_unit_ids=[unit['unit_id'] for unit in units],
                source_discrepancy=['afbakening_onjuist'])


def intervene(console, monkeypatch, mutation):
    original = console._store_write_lock
    fired = []

    @contextmanager
    def lock():
        if active_review_command(console) is None and not fired:
            fired.append(True)
            mutation()
        with original():
            yield

    monkeypatch.setattr(console, '_store_write_lock', lock)
    return fired


@pytest.mark.parametrize('azure', [False, True])
def test_complete_http_repair_prepares_before_transaction(tmp_path, monkeypatch, production_console, production_app, azure):
    console, sid, obj, reviewer, fresh = setup_repair(tmp_path,
        production_console=lambda **options: production_console(azure=azure,
            environment={'CONSOLE_PUBLIC_ORIGIN': 'https://testserver'}, **options))
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    observed = []
    original = console._source_repair

    def probe(**kwargs):
        state = active_review_command(console)
        observed.append((state is not None and state.preparing,
                         console._store_lock_depth, workflow_transaction_active()))
        return original(**kwargs)

    monkeypatch.setattr(console, '_source_repair', probe)
    with TestClient(production_app(console), base_url='https://testserver',
                    headers={'Origin': 'https://testserver'}) as client:
        assert client.post('/login', data={'username':'reviewer', 'password':PASSWORD},
                           follow_redirects=False).status_code == 303
        response = client.post('/review/resolve', data={'snapshot_id':sid, 'object_id':obj['object_id'],
            'snapshot_revision':console.objects_revision(sid), 'suitability':'mist_context',
            'comment':'Exacte bronselectie.', 'repair_kind':'source_units',
            'source_unit_ids':[units[0]['unit_id']]}, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert observed == [(True, 0, False)]
    live = assert_complete(fresh(), sid, obj['object_id'])
    assert live['governance']['validation_status'] == 'needs_review'
    assert live['object_version'] != obj['object_version']


@pytest.mark.parametrize('change', ['role', 'identity', 'roster', 'policy', 'source',
                                   'unrelated_object', 'unrelated_without_epochs', 'retained_version'])
def test_current_dependency_change_preserves_concurrent_winner(tmp_path, monkeypatch, production_console, change):
    console, sid, obj, reviewer, fresh = setup_repair(tmp_path, production_console=production_console)
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    if change == 'retained_version':
        console.submit_review_resolution(**command_for(console, sid, obj, reviewer, units[:1]))
    command = command_for(console, sid, obj, reviewer, units[:1])
    if change == 'unrelated_without_epochs':
        monkeypatch.setattr(console.workflow_document_store, 'review_command_object_epochs', lambda sid: None)
    winner = []

    def mutation():
        with console.workflow_document_store._connect() as con:
            if change == 'role':
                con.execute("UPDATE workflow.accounts SET roles=ARRAY['researcher']::text[] WHERE account_id=%s", (reviewer['account_id'],))
            elif change == 'identity':
                con.execute("UPDATE workflow.accounts SET display_name='Changed' WHERE account_id=%s", (reviewer['account_id'],))
            elif change == 'roster':
                con.execute('DELETE FROM workflow.document_reviewers WHERE snapshot_id=%s', (sid,))
                con.execute("UPDATE workflow.documents SET envelope_payload=jsonb_set(envelope_payload,'{named_reviewers}', '[]'::jsonb,true),review_read_envelope=NULL WHERE snapshot_id=%s", (sid,))
            elif change == 'policy':
                con.execute("UPDATE workflow.documents SET envelope_payload=jsonb_set(envelope_payload,'{review_policy}',%s::jsonb,true),review_read_envelope=NULL WHERE snapshot_id=%s", (json.dumps({'contract':'changed'}), sid))
            elif change == 'source':
                con.execute("UPDATE workflow.documents SET source_sha256=%s,envelope_payload=jsonb_set(envelope_payload,'{sha256}',%s::jsonb,true),review_read_envelope=NULL WHERE snapshot_id=%s", ('0' * 64, json.dumps('0' * 64), sid))
            elif change == 'retained_version':
                con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{metadata,w1_concurrent}', 'true'::jsonb,true) WHERE snapshot_id=%s AND object_id=%s AND object_version=%s", (sid, obj['object_id'], obj['object_version']))
            else:
                con.execute("UPDATE workflow.document_objects SET payload=jsonb_set(payload,'{metadata,w1_concurrent}', 'true'::jsonb,true) WHERE snapshot_id=%s AND payload->>'object_type'='document'", (sid,))
        winner.append(durable(console, sid))

    fired = intervene(console, monkeypatch, mutation)
    with pytest.raises(ConsoleError):
        console.submit_review_resolution(**command)
    assert fired and winner
    # Deliberately corrupted retained history must not become readable at
    # restart; compare the raw authoritative records through the existing store.
    assert durable(console if change == 'retained_version' else fresh(), sid) == winner[0]
    assert console.workflow_review_store._buffer.get() is None


@pytest.mark.parametrize('failure', ['repair_evidence', 'late_commit'])
def test_complete_evidence_is_atomic_and_version_bound(tmp_path, production_console, failure):
    console, sid, obj, reviewer, fresh = setup_repair(tmp_path, production_console=production_console)
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    command = command_for(console, sid, obj, reviewer, units[:1])
    before = durable(console, sid)
    with console.workflow_review_store._connect() as con:
        con.execute("""CREATE FUNCTION workflow.w1_failure() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN IF NEW.event_payload->'details'->>'decision' = 'repair_source_units' THEN
            RAISE EXCEPTION 'w1_final_evidence_failure'; END IF; RETURN NEW; END $$""")
        timing = ('CREATE CONSTRAINT TRIGGER w1_failure AFTER INSERT ON workflow.review_events '
                  'DEFERRABLE INITIALLY DEFERRED' if failure == 'late_commit' else
                  'CREATE TRIGGER w1_failure BEFORE INSERT ON workflow.review_events')
        con.execute(timing + ' FOR EACH ROW EXECUTE FUNCTION workflow.w1_failure()')
    with pytest.raises(Exception) as refused:
        console.submit_review_resolution(**command)
    cause = refused.value
    while cause.__cause__ is not None:
        cause = cause.__cause__
    assert 'w1_final_evidence_failure' in str(cause)
    assert durable(fresh(), sid) == before
    with console.workflow_review_store._connect() as con:
        con.execute('DROP TRIGGER w1_failure ON workflow.review_events')
    revised = console.submit_review_resolution(**command)
    events = read_events(fresh()._ledger_path)
    discrepancy = [event for event in events if event['details'].get('source_discrepancy')]
    repair_events = [event for event in events if event['details'].get('decision') == 'repair_source_units']
    assert len(discrepancy) == len(repair_events) == 1
    assert discrepancy[0]['object_version'] == obj['object_version']
    assert repair_events[0]['object_version'] == revised['object_version']
    with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
        console.submit_review_resolution(**command)


@pytest.mark.parametrize('selection', ['same', 'other_block', 'multiple_blocks'])
def test_prepared_selection_equals_original_serial_kernel(tmp_path, production_console, selection):
    console, sid, obj, reviewer, fresh = setup_repair(tmp_path, production_console=production_console,
        text='Gebruik geen zalf.</p><p>Bespreek de opties.</p><p>Volg de instructies.',
        secondary='Volg de instructies.', heading='Bij een natte plek:')
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    chosen = {'same': units[:1], 'other_block': units[-1:], 'multiple_blocks': units[:2]}[selection]
    command = command_for(console, sid, obj, reviewer, chosen)
    before = durable(console, sid)

    class RollbackReference(Exception):
        pass

    with pytest.raises(RollbackReference):
        with console._store_command(sid, lock_row=True, buffered=False):
            expected = console.submit_review_resolution(**command)
            expected_bindings = console.object_review_bindings(sid)
            expected_details = [event['details'] for event in read_events(console._ledger_path)]
            raise RollbackReference()
    restarted = fresh()
    assert durable(restarted, sid) == before
    actual = restarted.submit_review_resolution(**command)
    assert actual == expected
    assert restarted.object_review_bindings(sid) == expected_bindings
    assert [event['details'] for event in read_events(restarted._ledger_path)] == expected_details


def test_unprepared_history_uses_existing_serial_contract(tmp_path, monkeypatch, production_console):
    console, sid, obj, reviewer, fresh = setup_repair(tmp_path, production_console=production_console)
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    command = command_for(console, sid, obj, reviewer, units[:1])
    with console.workflow_document_store._connect() as con:
        con.execute('UPDATE workflow.object_revision_frontiers SET certificate=NULL,certificate_hash=NULL WHERE snapshot_id=%s', (sid,))
    original = console._source_repair
    calls = []

    def serial(**kwargs):
        calls.append(active_review_command(console))
        return original(**kwargs)

    monkeypatch.setattr(console, '_source_repair', serial)
    result = console.submit_review_resolution(**command)
    assert calls == [None]
    assert assert_complete(fresh(), sid, obj['object_id']) == result


def test_source_selection_is_detached_before_dependency_capture(tmp_path, monkeypatch, production_console):
    from src.review import review_command_v1 as executor
    console, sid, obj, reviewer, fresh = setup_repair(tmp_path, production_console=production_console)
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    command = command_for(console, sid, obj, reviewer, units[:1])
    prepare = executor._prepare_review_source_inputs

    def mutate_caller(*args, **kwargs):
        command['source_unit_ids'][:] = [units[-1]['unit_id']]
        return prepare(*args, **kwargs)

    monkeypatch.setattr(executor, '_prepare_review_source_inputs', mutate_caller)
    result = console.submit_review_resolution(**command)
    assert command['source_unit_ids'] == [units[-1]['unit_id']]
    assert result['content']['clean_text'] == units[0]['text']
    assert assert_complete(fresh(), sid, obj['object_id']) == result
