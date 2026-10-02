"""Native reserved-call failure, restart, activation and shared-client proofs.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from argparse import Namespace
from copy import deepcopy
from datetime import timedelta
import json
import hashlib
import sys
import time
from threading import Thread, Barrier
from types import SimpleNamespace

import pytest

from src.operations_console_v1 import ConsoleError, PRE_REVIEW_BLOCKED
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.processing_retry_v1 import now, reserve, finish, assert_active, status
from src.bounded_model_call_v1 import ModelCallLimits
from tests.model_transport_support import peer
from tests.test_source_bound_fields_v2 import fragment, proposal, TEXT
from tests.test_review_batch_atomic_postgres import _console, _client
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


def response(payload):
    return json.dumps({'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal(payload))}]}]}).encode()


def bind(console, monkeypatch, url, *, model='test-model', slow=False):
    import src.pre_review_semantic_v1 as semantic
    monkeypatch.setattr(semantic, 'OPENAI_RESPONSES_URL', url)
    source_fragment=fragment()
    source_fragment['fragment_hash']=hashlib.sha256(TEXT.encode()).hexdigest()
    console._extract=lambda *args, **kwargs: [deepcopy(source_fragment)]
    env={
        'METIS_LLM_API_KEY':'synthetic-key', 'METIS_LLM_MODEL':model,
        'METIS_LLM_CONNECT_TIMEOUT_SECONDS':'.3', 'METIS_LLM_IDLE_TIMEOUT_SECONDS':'.4',
        'METIS_LLM_TOTAL_TIMEOUT_SECONDS':'.8', 'METIS_PROCESSING_ATTEMPT_TIMEOUT_SECONDS':'61'}
    if slow:
        env.update(METIS_LLM_CONNECT_TIMEOUT_SECONDS="2",METIS_LLM_IDLE_TIMEOUT_SECONDS="5",
                   METIS_LLM_TOTAL_TIMEOUT_SECONDS="10",METIS_PROCESSING_ATTEMPT_TIMEOUT_SECONDS="75")
    bind_pre_review_semantic_processing(console, environ=env)
    return env


def command(actor, reviewer):
    return dict(actor_id=actor, filename='screening.html', data=f'<html><body><p>{TEXT}</p></body></html>'.encode(),
        content_type='text/html', ingest_kind='new', title='Screening', version='1.0', date='2026-10-02',
        live_url='', class_='richtlijn', family='test', named_reviewers=[reviewer], command_id='source-command')


def setup(root, config):
    console=_console(root, config)
    actor=console.create_account(username='anne',password='anne-secret',roles=('researcher',))['account_id']
    reviewer=console.create_account(username='bert',password='bert-secret',roles=('reviewer',))['account_id']
    return console,actor,reviewer


def test_native_stall_reserves_before_call_and_recovers_same_source(workflow_postgres,tmp_path,monkeypatch):
    console,actor,reviewer=setup(tmp_path,workflow_postgres)
    outcomes=[]
    with peer(delay=3) as (url,received):
        bind(console,monkeypatch,url)
        worker=Thread(target=lambda:outcomes.append(console.ingest(**command(actor,reviewer))))
        worker.start()
        try:
            assert received.wait(5)
            restarted=_console(tmp_path/'reader',workflow_postgres)
            envelope=restarted.list_envelopes()[0]
            sid=envelope['snapshot_id']
            assert envelope['processing_attempts'][-1]['state']=='running'
            assert restarted.snapshot_objects(sid)==[]
            assert restarted.processing_status(sid)['retry_allowed'] is False
        finally:worker.join(5)
        assert not worker.is_alive()
    envelope=_console(tmp_path,workflow_postgres)._envelope(sid)
    attempt=envelope['processing_attempts'][-1]
    assert attempt['state']=='failed'
    assert attempt['error_code']=='pre_review_llm_inactivity_timeout'
    assert attempt['transport']['local_worker_reaped']
    assert attempt['transport']['external_cancellation']=='unknown'
    assert attempt['limits']['automatic_retries']==0
    assert console.ingest(**command(actor,reviewer))['snapshot_id']==sid
    assert len(console._envelope(sid)['processing_attempts'])==1
    with pytest.raises(ConsoleError,match='processing_retry_cooldown'):
        console.retry_pre_review(actor_id=actor,snapshot_id=sid,command_id='too-soon')
    from src.cli import cmd_processing_status
    monkeypatch.setitem(sys.modules,'src.console_asgi',SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(operations_kernel=console))))
    from src.cli import main
    monkeypatch.setattr(sys,"argv",["metis","processing-status","--snapshot-id",sid,"--actor-id",actor])
    assert main()==0
    assert cmd_processing_status(Namespace(snapshot_id=sid,actor_id=reviewer))==_client(console).get(
        '/review/processing-diagnostics',params={'document':sid}).json()['processing']
    original_hash=envelope['sha256']
    future=now()+timedelta(minutes=1)
    monkeypatch.setattr('src.processing_retry_v1.now',lambda:future)
    with peer(body=response) as (url,_):
        bind(console,monkeypatch,url)
        from src.cli import cmd_processing_retry
        assert cmd_processing_retry(Namespace(actor_id=actor,snapshot_id=sid,command_id="recovery"))["state"]=="succeeded"
        assert console.retry_pre_review(actor_id=actor,snapshot_id=sid,command_id='recovery')['snapshot_id']==sid
    final=_console(tmp_path,workflow_postgres)
    envelope=final._envelope(sid)
    assert [a['state'] for a in envelope['processing_attempts']]==['failed','succeeded']
    assert envelope['sha256']==original_hash
    assert final.snapshot_objects(sid)
    assert envelope['quality_processing_runs'][-1]['attempt_id']==envelope['processing_attempts'][-1]['attempt_id']


@pytest.mark.parametrize('change',['expired','monotonic','source','review'])
def test_response_cannot_activate_after_concurrent_change(workflow_postgres,tmp_path,monkeypatch,change):
    console,actor,reviewer=setup(tmp_path,workflow_postgres)
    def changed(payload):
        second=_console(tmp_path/'writer',workflow_postgres)
        envelope=deepcopy(second.list_envelopes()[0])
        if change=='expired':
            future=now()+timedelta(hours=1)
            monkeypatch.setattr('src.processing_retry_v1.now',lambda:future)
        elif change=='monotonic':
            future=time.monotonic()+120
            monkeypatch.setattr('src.operations_console_v1.time',SimpleNamespace(monotonic=lambda:future))
        elif change=='source':
            console._source_cache_path(envelope).write_bytes(b'changed-source')
        else:
            envelope['review_passes']={'retained-review':{'decision':'approve','object_revision':'prior'}}
            second.workflow_document_store.write_bundle(envelope=envelope)
        return response(payload)
    with peer(body=changed) as (url,_):
        bind(console,monkeypatch,url,slow=True)
        with pytest.raises(ConsoleError):console.ingest(**command(actor,reviewer))
    final=_console(tmp_path,workflow_postgres)
    envelope=final.list_envelopes()[0]
    assert final.snapshot_objects(envelope['snapshot_id'])==[]
    assert envelope['processing_attempts'][-1]['state']=='failed'
    assert envelope['publication_eligibility']==PRE_REVIEW_BLOCKED
    if change=='review':assert envelope['review_passes']['retained-review']['decision']=='approve'


def test_reviewer_decision_during_native_reextract_survives_stale_activation(workflow_postgres,tmp_path,monkeypatch):
    console,actor,reviewer=setup(tmp_path,workflow_postgres)
    with peer(body=response) as (url,_):
        env=bind(console,monkeypatch,url,slow=True)
        sid=console.ingest(**command(actor,reviewer))['snapshot_id']
    before=deepcopy(console.snapshot_objects(sid))
    target=next(obj for obj in before if obj.get('proposed_object_type')=='recommendation')
    retained=[]
    review_events=[]
    def reviewed(payload):
        second=_console(tmp_path,workflow_postgres)
        second.review_object(actor_id=reviewer,snapshot_id=sid,object_id=target['object_id'],
                             decision='reject',comment='Behoud deze beoordeling')
        retained.extend(deepcopy(second.snapshot_objects(sid)))
        review_events.extend(deepcopy(second.workflow_review_store.read_events()))
        return response(payload)
    with peer(body=reviewed) as (url,_):
        monkeypatch.setattr('src.pre_review_semantic_v1.OPENAI_RESPONSES_URL',url)
        env['METIS_LLM_MODEL']='test-model-new'  # a distinct proposal; historical evidence remains
        with pytest.raises(ConsoleError):console.reextract_unpublished(actor_id=actor,snapshot_id=sid)
    final=_console(tmp_path,workflow_postgres)
    assert retained and final.snapshot_objects(sid)==retained
    assert retained != before
    assert review_events and final.workflow_review_store.read_events()==review_events
    assert final._envelope(sid)['processing_attempts'][-1]['state']=='failed'
    assert len(final._envelope(sid)['quality_processing_runs'])==1


def test_model_budget_uses_remaining_attempt_time_and_never_calls_after_expiry(tmp_path,monkeypatch):
    from src.operations_console_v1 import OperationsConsole
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    console=OperationsConsole(root=tmp_path,source_store=tmp_path/'sources',runtime=tmp_path/'runtime')
    console._extract=lambda *args,**kwargs:[fragment()]
    calls=[]
    def post(url,headers,payload,timeout):
        calls.append(timeout)
        return json.loads(response(payload))
    bind_pre_review_semantic_processing(console,environ={'METIS_LLM_API_KEY':'test','METIS_LLM_MODEL':'test'},post_json=post)
    args=dict(data=b'',document_id='doc',source_id='source',title='Test',family='test',class_='richtlijn')
    console._fragments_and_spec('html',tmp_path/'source',**args,
        formation_context={'attempt_deadline':time.monotonic()+2.5})
    assert 0 < calls[0] <= .5
    with pytest.raises(ConsoleError,match='processing_attempt_expired'):
        console._fragments_and_spec('html',tmp_path/'source',**args,
            formation_context={'attempt_deadline':time.monotonic()-1})
    assert len(calls)==1


def test_concurrent_initial_command_reserves_once_across_runtime_locks(workflow_postgres,tmp_path,monkeypatch):
    first,actor,reviewer=setup(tmp_path,workflow_postgres)
    second=_console(tmp_path/'second',workflow_postgres)
    barrier=Barrier(2)
    calls=[]
    results=[]
    def provider(payload):
        calls.append(1)
        return response(payload)
    with peer(body=provider) as (url,_):
        for console in [first,second]:
            bind(console,monkeypatch,url,slow=True)
            commit=console._commit_prepared_store
            def synchronize(*, _commit=commit, **kwargs):
                env=next(iter((kwargs.get('envelopes') or {}).values()),{})
                if env.get('processing_blocker')=='pre_review_llm_processing_in_progress':barrier.wait(5)
                return _commit(**kwargs)
            monkeypatch.setattr(console,'_commit_prepared_store',synchronize)
        def execute(console):
            try:results.append(console.ingest(**command(actor,reviewer)))
            except BaseException as exc:results.append(exc)
        threads=[Thread(target=execute,args=(console,)) for console in [first,second]]
        for thread in threads:thread.start()
        for thread in threads:thread.join(10)
        assert not any(thread.is_alive() for thread in threads)
    assert len(results)==2 and all(isinstance(result,dict) for result in results),results
    assert len(calls)==1
    final=_console(tmp_path,workflow_postgres)
    envelope=final.list_envelopes()[0]
    assert len(envelope['processing_attempts'])==1
    assert envelope['processing_attempts'][0]['state']=='succeeded'
    assert final.snapshot_objects(envelope['snapshot_id'])


def test_initial_process_interruption_leaves_durable_recoverable_reservation(workflow_postgres,tmp_path,monkeypatch):
    console,actor,reviewer=setup(tmp_path,workflow_postgres)
    bind(console,monkeypatch,'http://127.0.0.1:1')
    def crash(*args,**kwargs):raise KeyboardInterrupt()
    monkeypatch.setattr(console,'_fragments_and_spec',crash)
    with pytest.raises(KeyboardInterrupt):console.ingest(**command(actor,reviewer))
    final=_console(tmp_path,workflow_postgres)
    envelope=final.list_envelopes()[0]
    sid=envelope['snapshot_id']
    assert final.processing_status(sid)['state']=='running'
    future=now()+timedelta(hours=1)
    monkeypatch.setattr('src.processing_retry_v1.now',lambda:future)
    assert final.processing_status(sid)['state']=='expired'
    assert final.processing_status(sid)['retry_allowed']
    with peer(body=response) as (url,_):
        bind(final,monkeypatch,url)
        final.retry_pre_review(actor_id=actor,snapshot_id=sid,command_id='restart')
    assert [a['state'] for a in final._envelope(sid)['processing_attempts']]==['interrupted','succeeded']


def test_retry_caps_structural_errors_and_legacy_reader():
    envelope={'sha256':'a'*64,'version':'1.0','publication_eligibility':PRE_REVIEW_BLOCKED,
              'processing_blocker':'pre_review_llm_provider_unavailable'}
    assert status(envelope)['state']=='not_recorded'
    limits=ModelCallLimits(max_attempts=2)
    for command_id in ['one','two']:
        attempt,fresh=reserve(envelope,command_id=command_id,actor_id='actor',revision='r',clock=now(),limits=limits)
        assert fresh
        assert status(envelope,policy=limits)["reason_code"] == "processing_attempt_in_progress"
        finish(envelope,attempt['attempt_id'],state='failed',error=ConsoleError('pre_review_llm_connection_failed'))
    assert reserve(envelope,command_id='two',actor_id='actor',revision='r',clock=now(),limits=limits)[1] is False
    with pytest.raises(ConsoleError,match='processing_attempt_limit_reached'):
        reserve(envelope,command_id='three',actor_id='actor',revision='r',clock=now(),limits=limits)
    assert status(envelope,policy=limits)['retry_allowed'] is False
    envelope['processing_attempts']=envelope['processing_attempts'][:1]
    envelope['processing_attempts'][0]['error_code']='pre_review_llm_input_limit_exceeded'
    with pytest.raises(ConsoleError,match='processing_structural_limit'):
        reserve(envelope,command_id='new',actor_id='actor',revision='r',clock=now(),limits=limits)
    assert status(envelope)['retry_allowed'] is False
