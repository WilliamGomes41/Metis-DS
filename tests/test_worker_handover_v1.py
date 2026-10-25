"""#840: one durable command, replaceable workers on native PostgreSQL.
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import asyncio
import json
from copy import deepcopy
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.operations_console_v1 import ConsoleError
from src.processing_retry_v1 import now
from src.source_processing_dispatch_v1 import SourceProcessingDispatcher, claim, pending
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.source_bound_fields_v3 import MODE
from tests.production_support import restart_production
from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_recommendation_context_v3 import response_for


def setup_command(tmp_path, production_console, monkeypatch):
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    actor = users['researcher']['account_id']
    sid = console.receive_source(actor_id=actor, filename='handover.html', content_type='text/html',
        data=b'<html><body><h1>Een</h1><p>Gebruik geen zalf.</p><h1>Twee</h1><p>Controleer dagelijks de huid.</p><h1>Drie</h1><p>Was dagelijks de handen.</p></body></html>',
        ingest_kind='new', title='Overdracht', version='1', date='2026-10-25', live_url='', class_='richtlijn', family='test',
        named_reviewers=[users['reviewer_a']['account_id']])['snapshot_id']
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    calls = []
    def provider(_url, _headers, payload, _timeout):
        request = json.loads(payload['input'][1]['content'])
        text = request['source_blocks'][0]['text']
        calls.append(text)
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text',
            'text':json.dumps(response_for(payload,text))}]}]}
    def bind(target):
        bind_pre_review_semantic_processing(target, environ={'METIS_PASSAGE_FORMATION_MODE':MODE,
            'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'test'}, post_json=provider)
    bind(console)
    attempt, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid, command_id='one-start',
        expected_revision=console.objects_revision(sid))
    return console, actor, sid, attempt, calls, bind


def test_dispatcher_finishes_same_command_after_handover_and_kernel_restart(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    monkeypatch.setattr('src.source_processing_dispatch_v1.WORKER_SECONDS', 0, raising=False)
    console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    handed = console._envelope(sid)['processing_attempts'][-1]
    assert handed['state'] == 'running' and handed['dispatch']['state'] == 'pending'
    assert len(calls) == 1
    with console.workflow_document_store._connect() as con:
        first = con.execute('SELECT result_hash,payload FROM workflow.formation_task_results').fetchone()
    restarted = restart_production(console); bind(restarted)
    monkeypatch.setattr('src.source_processing_dispatch_v1.WORKER_SECONDS', 240)
    def forbidden(*args, **kwargs):
        raise AssertionError('Worker transfer must reuse source preparation')
    monkeypatch.setattr(restarted, '_extract', forbidden)
    monkeypatch.setattr('src.source_reconstruction_v1._with_status', forbidden)
    async def deliver():
        dispatcher = SourceProcessingDispatcher(restarted)
        await dispatcher.scan()
        await asyncio.gather(*tuple(dispatcher.workers))
        await dispatcher.stop()
    asyncio.run(deliver())
    final = restarted._envelope(sid)
    assert len(final['processing_attempts']) == 1
    done = final['processing_attempts'][0]
    assert done['state'] == 'succeeded'
    for key in ('attempt_id','command_id','expected_revision','expires_at','started_at'):
        assert done[key] == attempt[key]
    assert done['dispatch']['budget_expires_at'] == handed['dispatch']['budget_expires_at']
    assert done['dispatch']['claim_number'] == 2
    assert calls == ['Gebruik geen zalf.', 'Controleer dagelijks de huid.', 'Was dagelijks de handen.']
    with restarted.workflow_document_store._connect() as con:
        assert con.execute('SELECT result_hash,payload FROM workflow.formation_task_results WHERE result_hash=%s',
            (first['result_hash'],)).fetchone() == first
    assert len(final['quality_processing_runs']) == 1


def test_lease_reclaim_fences_previous_checkpoint_failure_and_execution(tmp_path, production_console, monkeypatch):
    from src.formation_checkpoint_v1 import TaskCheckpointWriter
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    first = claim(console, snapshot_id=sid, attempt_id=attempt['attempt_id'])
    stale = TaskCheckpointWriter(console, sid, first)
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,lease_expires_at}',%s::jsonb) WHERE attempt_id=%s",
            (json.dumps((now()-timedelta(seconds=1)).isoformat()), attempt['attempt_id']))
    assert pending(console)[0][0] == sid
    second = claim(console, snapshot_id=sid, attempt_id=attempt['attempt_id'])
    assert second['dispatch']['token'] != first['dispatch']['token']
    with pytest.raises(ConsoleError, match='processing_command_conflict'):
        stale('stale-write', {})
    console._record_processing_failure(sid, attempt['attempt_id'], ConsoleError('processing_old_worker'), claim_token=stale.claim_token)
    assert console._envelope(sid)['processing_attempts'][-1]['state'] == 'running'
    with pytest.raises(ConsoleError, match='processing_command_conflict'):
        console._execute_source_attempt(actor_id=actor, snapshot_id=sid, attempt=first, deadline=10**12)
    assert calls == []


def test_two_claimers_have_one_owner(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    other = restart_production(console); bind(other)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda c: claim(c, snapshot_id=sid, attempt_id=attempt['attempt_id']), (console, other)))
    assert sum(r is not None for r in results) == 1
    assert calls == []


@pytest.mark.parametrize('boundary,code', [
    ('deadline','processing_attempt_expired'), ('budget','source_task_budget_exhausted'),
    ('authorization','researcher_role_required'), ('configuration','processing_configuration_changed')])
def test_discovery_blocks_real_limits_without_new_start_or_provider(tmp_path, production_console, monkeypatch, boundary, code):
    from src.source_selection_v1 import summary_projection
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    past = (now()-timedelta(seconds=1)).isoformat()
    with console.workflow_document_store._connect() as con:
        if boundary == 'authorization':
            con.execute('UPDATE workflow.accounts SET roles=ARRAY[\'publisher\']::text[] WHERE account_id=%s', (actor,))
        else:
            record = deepcopy(attempt)
            if boundary == 'deadline':
                record['expires_at'] = past
            elif boundary == 'budget':
                record['dispatch']['budget_expires_at'] = past
            else:
                record['processing_configuration']['model'] = 'other-model'
            con.execute('UPDATE workflow.processing_attempts SET payload=%s::jsonb WHERE attempt_id=%s',
                (json.dumps(record), attempt['attempt_id']))
    assert pending(console) == []
    stored = console._envelope(sid)
    final = stored['processing_attempts'][-1]
    assert len(stored['processing_attempts']) == 1
    assert final['state'] == 'failed'
    assert final['dispatch']['state'] == 'blocked'
    assert final['dispatch']['blocked_reason'] == code
    assert final['dispatch']['required_action']
    assert calls == [] and console.snapshot_objects(sid) == []
    projected = summary_projection(console, envelope=stored, observations={})
    assert projected['state'] == 'geblokkeerd'
    assert projected['blocked_reason'] == code and projected['required_action']


def test_actual_claim_rechecks_authorization_and_persists_stop(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    assert pending(console)
    with console.workflow_document_store._connect() as con:
        con.execute('UPDATE workflow.accounts SET roles=ARRAY[\'publisher\']::text[] WHERE account_id=%s', (actor,))
    with pytest.raises(ConsoleError, match='researcher_role_required'):
        claim(console, snapshot_id=sid, attempt_id=attempt['attempt_id'])
    final = console._envelope(sid)['processing_attempts'][-1]
    assert final['dispatch']['state'] == 'blocked' and calls == []


def test_budget_not_reset_by_claim_and_next_call_stops_on_real_boundary(tmp_path, production_console, monkeypatch):
    from src.formation_checkpoint_v1 import TaskCheckpointWriter
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    claimed = claim(console, snapshot_id=sid, attempt_id=attempt['attempt_id'])
    writer = TaskCheckpointWriter(console, sid, claimed)
    assert writer.before_task() > 0
    budget = console._envelope(sid)['processing_attempts'][-1]['dispatch']['budget_expires_at']
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,worker_until}',%s::jsonb) WHERE attempt_id=%s",
            (json.dumps((now()-timedelta(seconds=1)).isoformat()), attempt['attempt_id']))
    writer.committed_this_worker = True
    from src.worker_handover_v1 import WorkerHandover
    with pytest.raises(WorkerHandover):
        writer.before_task()
    second = claim(console, snapshot_id=sid, attempt_id=attempt['attempt_id'])
    assert second['dispatch']['budget_expires_at'] == budget
    current = TaskCheckpointWriter(console, sid, second)
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,budget_expires_at}',%s::jsonb) WHERE attempt_id=%s",
            (json.dumps((now()-timedelta(seconds=1)).isoformat()), attempt['attempt_id']))
    with pytest.raises(ConsoleError, match='source_task_budget_exhausted'):
        current.before_task()
    assert calls == []


def test_rollback_does_not_publish_partial_claim(tmp_path, production_console, monkeypatch):
    from src.worker_handover_v1 import locked
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    before = deepcopy(console._envelope(sid)['processing_attempts'][-1])
    with pytest.raises(RuntimeError, match='rollback'):
        with locked(console, sid, attempt['attempt_id']) as (_, _, _, active):
            active['dispatch'].update(state='claimed', token='uncommitted')
            raise RuntimeError('rollback')
    assert console._envelope(sid)['processing_attempts'][-1] == before


def test_sigkill_then_new_worker_reclaims_same_command_without_human_start(tmp_path, production_console, monkeypatch):
    import subprocess
    import sys
    import time
    from pathlib import Path
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    marker = tmp_path/'first-committed'
    command = [sys.executable, '-m', 'tests.formation_process_probe', str(console.root),
        console.workflow_document_store.config.dsn, sid, attempt['attempt_id'], actor, 'crash', str(marker)]
    with (tmp_path/'worker.log').open('w') as log:
        child = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            until = time.monotonic()+20
            while not marker.exists() and child.poll() is None and time.monotonic() < until:
                time.sleep(.02)
            assert marker.exists(), (tmp_path/'worker.log').read_text()
        finally:
            child.kill(); child.wait(timeout=5)
    with console.workflow_document_store._connect() as con:
        first = con.execute('SELECT result_hash,payload FROM workflow.formation_task_results').fetchone()
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,lease_expires_at}',%s::jsonb) WHERE attempt_id=%s",
            (json.dumps((now()-timedelta(seconds=1)).isoformat()), attempt['attempt_id']))
    discovered = pending(console)
    assert len(discovered) == 1 and discovered[0][1]['attempt_id'] == attempt['attempt_id']
    command[8] = 'resume'
    done = subprocess.run(command, capture_output=True, text=True, timeout=25)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.splitlines()[-1])['state'] == 'succeeded'
    all_calls = [json.loads(line) for line in Path(str(marker)+'.calls').read_text().splitlines()]
    assert all_calls.count('Gebruik geen zalf.') == 1 and len(all_calls) == 4
    final = console._envelope(sid)
    assert len(final['processing_attempts']) == 1
    assert final['processing_attempts'][0]['expires_at'] == attempt['expires_at']
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT result_hash,payload FROM workflow.formation_task_results WHERE result_hash=%s',
            (first['result_hash'],)).fetchone() == first


def test_old_worker_cannot_activate_after_claim_changes_after_final_validation(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    original = console._fragments_and_spec
    stolen = []
    def prepared(*args, **kwargs):
        result = original(*args, **kwargs)
        with console.workflow_document_store._connect() as con:
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,token}','\"new-owner\"'::jsonb) WHERE attempt_id=%s",
                (attempt['attempt_id'],))
        stolen.append(True)
        return result
    monkeypatch.setattr(console, '_fragments_and_spec', prepared)
    with pytest.raises(ConsoleError, match='processing_command_conflict'):
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    assert stolen == [True] and len(calls) == 3
    assert console.snapshot_objects(sid) == []
    assert console._envelope(sid)['processing_attempts'][0]['state'] == 'running'
    assert console._envelope(sid)['processing_attempts'][0]['dispatch']['token'] == 'new-owner'


def test_late_expired_worker_failure_requeues_instead_of_ending_command(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    first = claim(console, snapshot_id=sid, attempt_id=attempt['attempt_id'])
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,lease_expires_at}',%s::jsonb) WHERE attempt_id=%s",
            (json.dumps((now()-timedelta(seconds=1)).isoformat()), attempt['attempt_id']))
    console._record_processing_failure(sid, attempt['attempt_id'], ConsoleError('processing_worker_lease_expired'),
        claim_token=first['dispatch']['token'])
    final = console._envelope(sid)['processing_attempts'][0]
    assert final['state'] == 'running' and final['dispatch']['state'] == 'pending'
    assert claim(console, snapshot_id=sid, attempt_id=attempt['attempt_id']) is not None


def test_source_selection_reads_show_waiting_and_blocked_without_mutation(tmp_path, production_console, monkeypatch):
    from fastapi.testclient import TestClient
    from tests.production_support import application_for
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    # No lifespan startup: this specifically exercises readonly HTTP routes.
    client = TestClient(application_for(console), base_url='https://testserver')
    assert client.post('/login', data={'username':'researcher.d54','password':'d54-secret'}, follow_redirects=False).status_code == 303
    before = deepcopy(console._envelope(sid))
    response = client.get('/source-selection', params={'document':sid})
    assert response.status_code == 200
    assert 'wacht op uitvoering' in response.text
    assert '<button class="btn-primary">Hervatten</button>' not in response.text
    assert console._envelope(sid) == before and calls == []
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{expires_at}',%s::jsonb) WHERE attempt_id=%s",
            (json.dumps((now()-timedelta(seconds=1)).isoformat()), attempt['attempt_id']))
    assert pending(console) == []
    before = deepcopy(console._envelope(sid))
    for params in ({}, {'document':sid}):
        response = client.get('/source-selection', params=params)
        assert response.status_code == 200
        assert 'geblokkeerd' in response.text and 'totale tijdslimiet' in response.text
    assert console._envelope(sid) == before and calls == []


def test_shutdown_signal_hands_over_after_commit_without_failing_command(tmp_path, production_console, monkeypatch):
    from threading import Event
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    stop = Event()
    original = __import__('src.formation_checkpoint_v1', fromlist=['TaskCheckpointWriter']).TaskCheckpointWriter.commit_task
    def committed(writer, **kwargs):
        original(writer, **kwargs)
        stop.set()
    monkeypatch.setattr('src.formation_checkpoint_v1.TaskCheckpointWriter.commit_task', committed)
    receipt = console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt, _dispatch_stop=stop)
    assert receipt['snapshot_id'] == sid
    assert len(calls) == 1
    stored = console._envelope(sid)['processing_attempts'][0]
    assert stored['state'] == 'running' and stored['dispatch']['state'] == 'pending'
    assert len(pending(console)) == 1


def test_revocation_during_running_worker_prevents_next_call_and_activation(tmp_path, production_console, monkeypatch):
    from src.formation_checkpoint_v1 import TaskCheckpointWriter
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    original = TaskCheckpointWriter.commit_task
    def committed(writer, **kwargs):
        original(writer, **kwargs)
        with console.workflow_document_store._connect() as con:
            con.execute('UPDATE workflow.accounts SET roles=ARRAY[\'publisher\']::text[] WHERE account_id=%s', (actor,))
    monkeypatch.setattr(TaskCheckpointWriter, 'commit_task', committed)
    with pytest.raises(ConsoleError, match='researcher_role_required'):
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    assert len(calls) == 1 and console.snapshot_objects(sid) == []
    stored = console._envelope(sid)['processing_attempts'][0]
    assert stored['dispatch']['state'] == 'blocked' and stored['error_code'] == 'researcher_role_required'
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.formation_task_results').fetchone()['n'] == 1


def test_worker_task_allowance_cannot_outlive_lease(tmp_path, production_console, monkeypatch):
    import time
    from datetime import datetime
    from src.formation_checkpoint_v1 import TaskCheckpointWriter
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    seen = []
    def inspect_deadline(**kwargs):
        active = kwargs['attempt']
        lease_left = (datetime.fromisoformat(active['dispatch']['lease_expires_at'])-now()).total_seconds()
        hard_left = (datetime.fromisoformat(active['expires_at'])-now()).total_seconds()
        assert 0 < kwargs['deadline']-time.monotonic() <= hard_left+.1
        allowed = TaskCheckpointWriter(console, sid, active).before_task()
        assert 0 < allowed <= lease_left-4
        seen.append(True)
    monkeypatch.setattr(console, '_execute_source_attempt', inspect_deadline)
    console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    assert seen == [True] and calls == []


def test_live_worker_renews_lease_during_long_preparation_without_extending_deadline(tmp_path, production_console, monkeypatch):
    import time
    from datetime import datetime
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    monkeypatch.setattr('src.worker_handover_v1.HEARTBEAT_SECONDS', .05)
    original = console._fragments_and_spec
    def long_preparation(*args, **kwargs):
        with console.workflow_document_store._connect() as con:
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,lease_expires_at}',%s::jsonb) WHERE attempt_id=%s",
                (json.dumps((now()+timedelta(seconds=.5)).isoformat()), attempt['attempt_id']))
        time.sleep(.8)
        stored = console._envelope(sid)['processing_attempts'][0]
        assert datetime.fromisoformat(stored['dispatch']['lease_expires_at']) > now()
        assert stored['dispatch']['heartbeat_at']
        assert stored['expires_at'] == attempt['expires_at']
        return original(*args, **kwargs)
    monkeypatch.setattr(console, '_fragments_and_spec', long_preparation)
    console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    assert len(calls) == 3
    final = console._envelope(sid)['processing_attempts'][0]
    assert final['state'] == 'succeeded' and final['expires_at'] == attempt['expires_at']
    assert not any(t.name == 'source-worker-lease' and t.is_alive() for t in __import__('threading').enumerate())


def test_heartbeat_cannot_revive_expired_or_replaced_claim(tmp_path, production_console, monkeypatch):
    from src.worker_handover_v1 import renew
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    first = claim(console, snapshot_id=sid, attempt_id=attempt['attempt_id'])
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,lease_expires_at}',%s::jsonb) WHERE attempt_id=%s",
            (json.dumps((now()-timedelta(seconds=1)).isoformat()), attempt['attempt_id']))
    assert not renew(console, sid, first)
    assert pending(console)
    second = claim(console, snapshot_id=sid, attempt_id=attempt['attempt_id'])
    before = deepcopy(console._envelope(sid)['processing_attempts'][0])
    assert not renew(console, sid, first)
    after = console._envelope(sid)['processing_attempts'][0]
    assert after == before  # Even record_version must remain unchanged for the stale heartbeat.
    assert second['dispatch']['token'] == after['dispatch']['token']
