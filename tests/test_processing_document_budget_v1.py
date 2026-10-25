"""#846: one authorization spans long forming; native state, virtual time.
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt recovery version-compat
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import time
from copy import deepcopy
from datetime import timedelta

import pytest

from src.operations_console_v1 import ConsoleError
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.source_bound_fields_v3 import MODE
from tests.production_support import restart_production
from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_recommendation_context_v3 import response_for


class ClockProxy:
    def __init__(self, original, elapsed):
        self.original, self.elapsed = original, elapsed
    def monotonic(self):
        return self.original.monotonic()+self.elapsed[0]
    def __getattr__(self, name):
        return getattr(self.original, name)


def document(tmp_path, production_console, monkeypatch, *, total=3, seconds=70, hook=None, feature="v1", reserve=True, worker_limit=None, mode=MODE):
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    actor = users['researcher']['account_id']
    html = '<html><body>'+''.join(f'<h1>Stap {i}</h1><p>Controleer dagelijks de huid bij patiënt {i}.</p>' for i in range(total))+'</body></html>'
    sid = console.receive_source(actor_id=actor, filename='budget.html', content_type='text/html', data=html.encode(),
        ingest_kind='new',title='Documentbudget',version='1',date='2026-10-25',live_url='',class_='richtlijn',family='budget',
        named_reviewers=[users['reviewer_a']['account_id']])['snapshot_id']
    elapsed, calls = [0], []
    from src import processing_retry_v1 as retry
    clock_start = retry.now()
    monkeypatch.setattr(retry, 'now', lambda: clock_start+timedelta(seconds=elapsed[0]))
    monkeypatch.setattr('src.source_processing_dispatch_v1.now', retry.now)
    monkeypatch.setattr('src.source_selection_v1.now', retry.now)
    proxy = ClockProxy(time, elapsed)
    for name in ('src.operations_console_v1.time','src.pre_review_semantic_v1.time','src.bounded_formation_v1.time'):
        monkeypatch.setattr(name, proxy)
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE','v1')
    monkeypatch.setenv('METIS_DOCUMENT_PROCESSING_BUDGET',feature)
    def provider(_url, _headers, payload, _timeout):
        assert payload['max_output_tokens'] == 16384
        text = json.loads(payload['input'][1]['content'])['source_blocks'][0]['text']
        calls.append(text)
        elapsed[0] += seconds
        if hook is not None:
            hook(text)
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text',
            'text':json.dumps(response_for(payload,text))}]}]}
    def bind(target):
        bind_pre_review_semantic_processing(target, environ={'METIS_PASSAGE_FORMATION_MODE':mode,
            'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'test'}, post_json=provider)
    bind(console)
    if worker_limit is not None:
        from dataclasses import replace
        original_limits = console._processing_limits()
        monkeypatch.setattr(console,'_model_call_limits_reader',lambda:replace(original_limits,attempt=worker_limit))
    attempt = None
    if reserve:
        attempt, fresh = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='one-document',
            expected_revision=console.objects_revision(sid))
        assert fresh
    return console, actor, sid, attempt, calls, bind, elapsed


def test_start_pins_four_hour_document_budget_and_preserves_call_worker_limits(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch)
    from datetime import datetime
    assert (datetime.fromisoformat(attempt['expires_at'])-datetime.fromisoformat(attempt['started_at'])).total_seconds() == 14400
    assert attempt['document_budget']['calls_reserved'] == 0
    assert attempt['dispatch']['version'] == 'source-dispatch-v3'
    assert attempt['limits']['attempt'] == 1800 and attempt['limits']['total'] == 900
    repeated, fresh = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='one-document',
        expected_revision=console.objects_revision(sid))
    assert not fresh and repeated['expires_at'] == attempt['expires_at'] and calls == []


def test_130_tasks_70_seconds_one_start_and_one_activation_across_workers(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch,total=130)
    first = None
    for worker in range(50):
        console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
        active = console._envelope(sid)['processing_attempts'][0]
        assert active['attempt_id'] == attempt['attempt_id'] and active['expires_at'] == attempt['expires_at']
        assert active['document_budget']['calls_reserved'] == len(calls)
        if active['state'] == 'succeeded':
            break
        assert active['dispatch']['state'] == 'pending' and console.snapshot_objects(sid) == []
        if first is None:
            with console.workflow_document_store._connect() as con:
                first = con.execute('SELECT ranges_hash,result_hash,payload FROM workflow.formation_task_results WHERE attempt_id=%s ORDER BY ranges_hash LIMIT 1',
                    (attempt['attempt_id'],)).fetchone()
            console = restart_production(console); bind(console)
            def forbidden(*args, **kwargs):
                raise AssertionError('Existing source preparation must survive the worker restart')
            monkeypatch.setattr(console, '_extract', forbidden)
            monkeypatch.setattr('src.source_reconstruction_v1._with_status', forbidden)
    else:
        pytest.fail('Document did not complete within its bounded number of workers')
    final = console._envelope(sid)
    assert len(final['processing_attempts']) == 1 and len(final['quality_processing_runs']) == 1
    assert len(calls) == len(set(calls)) == 130 and elapsed[0] == 9100
    assert final['processing_attempts'][0]['document_budget']['max_model_calls'] == 260
    assert final['processing_attempts'][0]['dispatch']['claim_number'] > 1
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT ranges_hash,result_hash,payload FROM workflow.formation_task_results WHERE ranges_hash=%s AND attempt_id=%s',
            (first['ranges_hash'],attempt['attempt_id'])).fetchone() == first


@pytest.mark.parametrize('progress', [False, True])
@pytest.mark.parametrize('path', ['discovery','execution'])
def test_four_hour_boundary_stops_with_consistent_progress_accounting(tmp_path, production_console, monkeypatch, progress, path):
    from src.source_processing_dispatch_v1 import pending, claim
    from src.processing_retry_v1 import _retry_budget_attempts
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch)
    if progress:
        monkeypatch.setattr('src.source_processing_dispatch_v1.WORKER_SECONDS',0)
        console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    claimed = claim(console,snapshot_id=sid,attempt_id=attempt['attempt_id']) if path == 'execution' else None
    elapsed[0] = 14401
    if path == 'discovery':
        assert pending(console) == []
    else:
        console._record_processing_failure(sid,attempt['attempt_id'],ConsoleError('processing_worker_deadline_reached'),
            claim_token=claimed['dispatch']['token'])
    final = console._envelope(sid)['processing_attempts'][0]
    assert final['state'] == 'incomplete_budget' and final['stop_reason'] == 'budget_exhausted'
    assert final['formation_progress_made'] is progress
    assert len(_retry_budget_attempts([final])) == (0 if progress else 1)
    assert final['dispatch']['state'] == 'blocked' and console.snapshot_objects(sid) == []
    assert len(calls) == (1 if progress else 0)
    assert final['expires_at'] == attempt['expires_at']


def test_worker_hard_limit_requeues_same_document_without_renewing_authorization(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch)
    original = console._fragments_and_spec
    def beyond_worker_deadline(*args, **kwargs):
        elapsed[0] += 1801
        return original(*args, **kwargs)
    monkeypatch.setattr(console,'_fragments_and_spec',beyond_worker_deadline)
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    pending = console._envelope(sid)['processing_attempts'][0]
    assert pending['state'] == 'running' and pending['dispatch']['state'] == 'pending'
    assert pending['expires_at'] == attempt['expires_at'] and calls == []
    monkeypatch.setattr(console,'_fragments_and_spec',original)
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    assert len(calls) == 3
    assert console._envelope(sid)['processing_attempts'][0]['state'] == 'succeeded'
    assert len(console._envelope(sid)['processing_attempts']) == 1


def test_call_reservations_survive_lost_worker_and_concurrent_last_slot(tmp_path, production_console, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from src.source_processing_dispatch_v1 import claim,pending
    from src.formation_checkpoint_v1 import TaskCheckpointWriter
    from src.processing_retry_v1 import now
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch)
    monkeypatch.setattr('src.source_processing_dispatch_v1.WORKER_SECONDS',0)
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    claimed = claim(console,snapshot_id=sid,attempt_id=attempt['attempt_id'])
    writer = TaskCheckpointWriter(console,sid,claimed)
    for _ in range(4):
        writer('model_request',{'current_task':{'status':'running'}})
    def reserve_one(_):
        try:
            TaskCheckpointWriter(console,sid,claimed)('model_request',{'current_task':{'status':'running'}})
            return 'reserved'
        except ConsoleError as error:
            return error.code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(reserve_one,range(2))) == ['processing_document_call_budget_exhausted','reserved']
    before = deepcopy(console._envelope(sid)['processing_attempts'][0])
    assert before['document_budget']['calls_reserved'] == before['document_budget']['max_model_calls'] == 6
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,lease_expires_at}',%s::jsonb) WHERE attempt_id=%s",
            (json.dumps((now()-timedelta(seconds=1)).isoformat()),attempt['attempt_id']))
    assert pending(console)
    next_claim = claim(console,snapshot_id=sid,attempt_id=attempt['attempt_id'])
    assert next_claim['document_budget'] == before['document_budget']
    with pytest.raises(ConsoleError,match='processing_command_conflict'):
        writer('model_request',{'current_task':{'status':'running'}})
    with pytest.raises(ConsoleError,match='processing_document_call_budget_exhausted'):
        TaskCheckpointWriter(console,sid,next_claim)('model_request',{'current_task':{'status':'running'}})
    from src import operations_console_v1 as operation
    with pytest.raises(ConsoleError,match='processing_document_call_budget_exhausted'):
        console._execute_source_attempt(actor_id=actor,snapshot_id=sid,attempt=next_claim,
            deadline=operation.time.monotonic()+1800)
    stopped = console._envelope(sid)['processing_attempts'][0]
    assert stopped['state'] == 'incomplete_budget'
    assert stopped['dispatch']['blocked_reason'] == 'processing_document_call_budget_exhausted'
    assert len(calls) == 1 and console.snapshot_objects(sid) == []


@pytest.mark.parametrize('damage',['missing','window','counter'])
def test_invalid_document_budget_rejected_before_model_work(tmp_path, production_console, monkeypatch, damage):
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch)
    bad = deepcopy(attempt)
    if damage == 'missing':
        bad.pop('document_budget')
    elif damage == 'window':
        bad['document_budget']['window_seconds'] = 999999
    else:
        bad['document_budget']['calls_reserved'] = -1
    with console.workflow_document_store._connect() as con:
        con.execute('UPDATE workflow.processing_attempts SET payload=%s::jsonb WHERE attempt_id=%s',(json.dumps(bad),attempt['attempt_id']))
    with pytest.raises(ConsoleError,match='processing_document_budget_invalid'):
        console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    assert calls == [] and console.snapshot_objects(sid) == []


def test_disabling_new_admission_does_not_change_an_accepted_budget(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch)
    monkeypatch.setattr('src.source_processing_dispatch_v1.WORKER_SECONDS',0)
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    monkeypatch.setenv('METIS_DOCUMENT_PROCESSING_BUDGET','off')
    monkeypatch.setattr('src.source_processing_dispatch_v1.WORKER_SECONDS',240)
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    assert len(calls) == 3 and console._envelope(sid)['processing_attempts'][0]['state'] == 'succeeded'
    assert console._envelope(sid)['processing_attempts'][0]['expires_at'] == attempt['expires_at']


def test_legacy_start_keeps_900_and_1800_seconds(tmp_path, production_console, monkeypatch):
    from datetime import datetime
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch,feature='off')
    assert 'document_budget' not in attempt and attempt['dispatch']['version'] == 'source-dispatch-v2'
    assert (datetime.fromisoformat(attempt['expires_at'])-datetime.fromisoformat(attempt['started_at'])).total_seconds() == 1800
    assert attempt['limits']['total'] == 900 and calls == []


def test_all_results_can_activate_without_new_call_when_call_quota_is_zero(tmp_path, production_console, monkeypatch):
    from src.formation_checkpoint_v1 import TaskCheckpointWriter
    from src.worker_handover_v1 import WorkerHandover
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch)
    original = TaskCheckpointWriter.final_validation
    transferred = []
    def hold_final(writer, proposal):
        if not transferred:
            for _ in range(3):
                writer('model_request',{'current_task':{'status':'running'}})
            with writer._locked() as (_, active):
                active['dispatch'].update(state='pending',token=None,release_reason='fixture_final_gate_transfer')
            transferred.append(True)
            raise WorkerHandover()
        return original(writer,proposal)
    monkeypatch.setattr(TaskCheckpointWriter,'final_validation',hold_final)
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    assert len(calls) == 3 and console.snapshot_objects(sid) == []
    before = deepcopy(console._envelope(sid)['processing_attempts'][0]['document_budget'])
    assert before['calls_reserved'] == before['max_model_calls'] == 6
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    final = console._envelope(sid)
    assert len(calls) == 3 and final['processing_attempts'][0]['state'] == 'succeeded'
    assert final['processing_attempts'][0]['document_budget'] == before
    assert len(final['quality_processing_runs']) == 1


@pytest.mark.parametrize('guard,code',[('authorization','researcher_role_required'),('configuration','processing_configuration_changed')])
def test_new_worker_rechecks_authority_and_configuration(tmp_path, production_console, monkeypatch, guard, code):
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch)
    monkeypatch.setattr('src.source_processing_dispatch_v1.WORKER_SECONDS',0)
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    with console.workflow_document_store._connect() as con:
        if guard == 'authorization':
            con.execute("UPDATE workflow.accounts SET roles=ARRAY['publisher']::text[] WHERE account_id=%s",(actor,))
        else:
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{processing_configuration,model}','\"other\"') WHERE attempt_id=%s",(attempt['attempt_id'],))
    with pytest.raises(ConsoleError,match=code):
        console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    stopped = console._envelope(sid)['processing_attempts'][0]
    assert stopped['dispatch']['state'] == 'blocked' and stopped['error_code'] == code
    assert stopped['document_budget']['calls_reserved'] == 1 and len(calls) == 1
    assert console.snapshot_objects(sid) == []


def test_http_one_start_displays_budget_and_reads_do_not_change_it(tmp_path, production_console, monkeypatch):
    from fastapi.testclient import TestClient
    from tests.production_support import application_for
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch,reserve=False)
    with TestClient(application_for(console),base_url='https://testserver') as client:
        assert client.post('/login',data={'username':'researcher.d54','password':'d54-secret'},follow_redirects=False).status_code == 303
        before = deepcopy(console._envelope(sid))
        page = client.get('/source-selection',params={'document':sid})
        assert page.status_code == 200 and 'binnen vier uur inclusief wachttijd' in page.text
        assert console._envelope(sid) == before
        started = client.post('/source-selection/start',data={'document':sid,'command_id':'one-http-start',
            'expected_revision':console.objects_revision(sid)},follow_redirects=False)
        assert started.status_code == 303
        until = time.monotonic()+10
        while console._envelope(sid)['processing_attempts'][0]['state'] == 'running' and time.monotonic() < until:
            time.sleep(.02)
        final = deepcopy(console._envelope(sid))
        assert final['processing_attempts'][0]['state'] == 'succeeded' and len(final['processing_attempts']) == 1
        for params in ({},{'document':sid}):
            page = client.get('/source-selection',params=params)
            assert page.status_code == 200 and 'Documentbudget: vier uur' in page.text
            assert '3 van 6' in page.text
        assert console._envelope(sid) == final and len(calls) == 3


def test_process_death_does_not_refund_an_uncertain_call_or_need_a_new_start(tmp_path, production_console, monkeypatch):
    import subprocess
    import sys
    from pathlib import Path
    from src.source_processing_dispatch_v1 import pending
    from src.processing_retry_v1 import now
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch)
    marker = tmp_path/'committed-document-task'
    command = [sys.executable,'-m','tests.formation_process_probe',str(console.root),console.workflow_document_store.config.dsn,
        sid,attempt['attempt_id'],actor,'crash',str(marker)]
    with (tmp_path/'document-worker.log').open('w') as log:
        child = subprocess.Popen(command,stdout=log,stderr=log)
        try:
            until = time.monotonic()+20
            while not marker.exists() and child.poll() is None and time.monotonic()<until:
                time.sleep(.02)
            assert marker.exists(), (tmp_path/'document-worker.log').read_text()
        finally:
            child.kill();child.wait(timeout=5)
    first_state = console._envelope(sid)['processing_attempts'][0]
    assert first_state['document_budget']['calls_reserved'] == 2
    with console.workflow_document_store._connect() as con:
        first = con.execute('SELECT ranges_hash,result_hash,payload FROM workflow.formation_task_results WHERE attempt_id=%s',
            (attempt['attempt_id'],)).fetchone()
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,lease_expires_at}',%s::jsonb) WHERE attempt_id=%s",
            (json.dumps((now()-timedelta(seconds=1)).isoformat()),attempt['attempt_id']))
    assert pending(console)[0][1]['attempt_id'] == attempt['attempt_id']
    command[8] = 'resume'
    resumed = subprocess.run(command,capture_output=True,text=True,timeout=25)
    assert resumed.returncode == 0, resumed.stderr
    final = console._envelope(sid)
    assert len(final['processing_attempts']) == 1 and final['processing_attempts'][0]['state'] == 'succeeded'
    assert final['processing_attempts'][0]['expires_at'] == attempt['expires_at']
    assert final['processing_attempts'][0]['document_budget']['calls_reserved'] == 4
    recorded_calls = [json.loads(line) for line in Path(str(marker)+'.calls').read_text().splitlines()]
    assert len(recorded_calls) == 4 and recorded_calls.count(recorded_calls[0]) == 1
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT ranges_hash,result_hash,payload FROM workflow.formation_task_results WHERE ranges_hash=%s AND attempt_id=%s',
            (first['ranges_hash'],attempt['attempt_id'])).fetchone() == first


def test_document_worker_never_gets_more_than_thirty_minutes(tmp_path, production_console, monkeypatch):
    from datetime import datetime
    from src.source_processing_dispatch_v1 import claim
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch,worker_limit=3600)
    claimed = claim(console,snapshot_id=sid,attempt_id=attempt['attempt_id'])
    dispatch = claimed['dispatch']
    assert (datetime.fromisoformat(dispatch['worker_expires_at'])-datetime.fromisoformat(dispatch['claimed_at'])).total_seconds() == 1800
    assert claimed['document_budget']['max_worker_seconds'] == 1800 and calls == []


def test_alternative_mode_keeps_original_contract_when_document_policy_is_enabled(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind, elapsed = document(tmp_path,production_console,monkeypatch,mode='semantic-source-bound-v1')
    assert attempt['dispatch']['version'] == 'source-dispatch-v1'
    assert 'document_budget' not in attempt and calls == []
