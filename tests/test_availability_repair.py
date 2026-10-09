"""A26 A04/A05 A02: actual installed routes, durable commands, deterministic barriers.

# release-control-evidence: scope/belofte opslag durable concurrent stale interrupt retry version-compat
# release-control-evidence: toegang beschikbaarheid kwaliteit metrics slop releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import asyncio
import json
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.review_closure_v1 import ReviewClosureConsole
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.processing_retry_v1 import now
from tests.test_recommendation_context_v3 import response_for
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


@pytest.fixture(params=["local", "postgres"])
def backend_state(request, monkeypatch):
    if request.param == "postgres":
        import sys
        from tests.test_review_batch_atomic_postgres import _console
        config = request.getfixturevalue("workflow_postgres")
        monkeypatch.setattr(sys.modules[__name__], "state", lambda root: _console(root, config))


def state(root):
    return ReviewClosureConsole(root=root, source_store=root/'sources', runtime=root/'runtime')


def accounts(console):
    author = console.create_account(username='author', password='fixture-only', roles=('researcher','reviewer','publisher'))
    reviewer = console.create_account(username='reviewer', password='fixture-only', roles=('reviewer',))
    return author['account_id'], reviewer['account_id']


def bind(console, provider):
    bind_pre_review_semantic_processing(console, environ={'METIS_PASSAGE_FORMATION_MODE':'semantic-source-bound-v3',
        'METIS_LLM_API_KEY':'fixture', 'METIS_LLM_MODEL':'fixture'}, post_json=provider)


def provider(_url, _headers, payload, _timeout):
    data=json.loads(payload['input'][1]['content'])
    proposal = response_for(payload, 'Gebruik geen zalf.') if not data.get('selection_targets') else {'objects': [], 'relations': [], 'abstain_reason': 'uncertain'}
    return {'status':'completed', 'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal)}]}]}


def login(client, username='author'):
    assert client.post('/login', data={'username':username, 'password':'fixture-only'}, follow_redirects=False).status_code == 303


def upload(client, reviewer, *, command='receipt', title='Fixture'):
    return client.post('/ingest', data={'ingest_kind':'new','title':title,'version':'1','date':'2026-10-08',
        'class_':'richtlijn','family':'fixture','review_mode':'single','primary_reviewer':reviewer,'command_id':command},
        files={'file':('fixture.html',b'<html><body><p>Gebruik geen zalf.</p></body></html>','text/html')},follow_redirects=False)


def start(client, console, sid, command='start'):
    return client.post('/source-selection/start',data={'document':sid,'command_id':command,
        'expected_revision':console.objects_revision(sid)},follow_redirects=False)


def drain(client, app):
    async def wait():
        await asyncio.gather(*tuple(app.state.source_selection_workers))
    client.portal.call(wait)


def test_a26_receipt_without_provider_restart_duplicate_and_later_failure(backend_state,tmp_path):
    console=state(tmp_path); author, reviewer=accounts(console); calls=[]
    def failure(*args):
        calls.append(1)
        raise ConsoleError('processing_dependency_failed')
    bind(console,failure)
    app=create_console_app(console)
    with TestClient(app,base_url='https://testserver') as client:
        login(client)
        receipt=upload(client,reviewer)
        assert receipt.status_code==303,receipt.text
        sid=console.list_envelopes()[0]['snapshot_id']
        assert receipt.headers['location']==f'/source-selection?document={sid}&received=yes'
        assert calls==[]
        assert console._envelope(sid).get('processing_attempts',[])==[]
        assert console.snapshot_objects(sid)==[]
        assert upload(client,reviewer).headers['location']==receipt.headers['location']
        assert len(console.list_envelopes())==1
        selected=client.get(receipt.headers['location'])
        assert f'data-source-document="{sid}" data-selected="true"' in selected.text
        assert 'Status: nog niet gestart' in selected.text and '>Starten</button>' in selected.text
    restarted=state(tmp_path);bind(restarted,failure);app=create_console_app(restarted)
    before=deepcopy(restarted._envelope(sid))
    with TestClient(app,base_url='https://testserver') as client:
        login(client)
        assert start(client,restarted,sid).status_code==303
        drain(client,app)
        assert client.get('/source-selection',params={'document':sid}).status_code==200
    final=state(tmp_path)
    assert final._envelope(sid)['sha256']==before['sha256']
    assert final._verified_source_bytes(final._envelope(sid))[1].startswith(b'<html>')
    assert final._envelope(sid)['processing_attempts'][-1]['state']=='failed'
    assert calls==[1]


def test_a26_short_selection_request_health_reads_writer_refresh_duplicate(backend_state,tmp_path):
    console=state(tmp_path);author,reviewer=accounts(console)
    entered=Event();release=Event();calls=[];observations=[]
    def paused(*args):
        calls.append(1)
        try: asyncio.get_running_loop(); on_loop=True
        except RuntimeError: on_loop=False
        from src.workflows.workflow_transaction_v1 import workflow_transaction_active
        observations.append((on_loop, console._store_lock_depth, workflow_transaction_active()))
        entered.set(); assert release.wait(5)
        return provider(*args)
    bind(console,paused); app=create_console_app(console)
    with TestClient(app,base_url='https://testserver') as client,ThreadPoolExecutor(3) as pool:
        login(client);assert upload(client,reviewer).status_code==303
        sid=console.list_envelopes()[0]['snapshot_id'];rev=console.objects_revision(sid)
        try:
            assert start(client,console,sid).status_code==303
            assert entered.wait(3)
            for path in ('/health','/source-selection','/ingest','/'):
                assert pool.submit(client.get,path).result(timeout=1).status_code==200
            assert client.post('/source-selection/start',data={'document':sid,'command_id':'start','expected_revision':rev},follow_redirects=False).status_code==303
            assert len(calls)==1 and len(console._envelope(sid)['processing_attempts'])==1
            # Independent writer actually commits while provider is paused.
            assert pool.submit(console.create_account,username='independent',password='fixture-only',roles=('researcher',)).result(timeout=1)
            assert 'Status: bezig' in client.get('/source-selection',params={'document':sid}).text
        finally:release.set();drain(client,app)
        result=client.get('/source-selection',params={'document':sid})
        assert 'Status: voltooid' in result.text and 'Naar Review' in result.text
        assert console.processing_status(sid)['state']=='succeeded'
        assert observations==[(False,0,False)]
        assert len(calls)==1


def test_a04_a05_successor_register_then_prepare_without_lock_and_stale_parent(backend_state,tmp_path):
    console=state(tmp_path);author,_=accounts(console);bind_fixture_selections(console)
    policy={'contract':'explicit-review-v1','revision':1,'primary':author,'assignments':[]}
    receipt=console.ingest(actor_id=author,filename='fixture.html',data=b'<html><body><p>Een observatie is een systematische waarneming.</p></body></html>',
        content_type='text/html',ingest_kind='new',title='Fixture',version='1',date='2026-10-08',live_url='',
        class_='richtlijn',family='fixture',named_reviewers=[],review_policy=policy)
    sid=receipt['snapshot_id'];before=deepcopy(console.snapshot_objects(sid));original=console._fragments_and_spec
    entered=Event();release=Event();observations=[]
    def paused(*args,**kwargs):
        try: asyncio.get_running_loop();on_loop=True
        except RuntimeError:on_loop=False
        from src.workflows.workflow_transaction_v1 import workflow_transaction_active
        observations.append((on_loop,console._store_lock_depth,workflow_transaction_active()))
        entered.set();assert release.wait(5);return original(*args,**kwargs)
    console._fragments_and_spec=paused;app=create_console_app(console)
    with TestClient(app,base_url='https://testserver') as client,ThreadPoolExecutor(3) as pool:
        login(client)
        command={'document':sid,'expected_revision':console.objects_revision(sid),'command_id':'successor',
                 'reason':'Nieuwe controle','primary':author,'policy_revision':'2','new_class':'richtlijn'}
        received=client.post('/review/successor',data=command,follow_redirects=False)
        assert received.status_code==303 and received.headers['location'].startswith('/source-selection?document=')
        assert not entered.is_set()
        sid2=received.headers['location'].split('document=')[1]
        assert client.post('/review/successor',data=command,follow_redirects=False).headers['location']==received.headers['location']
        assert len(console.list_envelopes())==2
        other=client.post('/review/successor',data={**command,'command_id':'duplicate-context'},follow_redirects=False)
        assert other.status_code==400 and 'review_successor_already_exists' in other.text
        try:
            assert start(client,console,sid2).status_code==303
            assert entered.wait(3)
            assert pool.submit(client.get,'/health').result(timeout=1).status_code==200
            assert pool.submit(client.get,'/ingest').result(timeout=1).status_code==200
            # Durable concurrent parent policy mutation must fence activation.
            with console._reprocessing_transaction(sid):
                changed=deepcopy(console._envelope(sid));changed['review_policy']['revision']=3
                console._commit_prepared_store(envelopes={sid:changed},snapshot_id=sid)
        finally:release.set();drain(client,app)
    assert console.snapshot_objects(sid)==before
    assert console.snapshot_objects(sid2)==[]
    attempt=console._envelope(sid2)['processing_attempts'][-1]
    assert attempt['state']=='failed' and attempt['error_code']=='snapshot_object_write_conflict'
    assert observations==[(False,0,False)]


def test_restart_expired_reservation_resumes_without_losing_source(backend_state,tmp_path,monkeypatch):
    console=state(tmp_path);author,reviewer=accounts(console)
    app=create_console_app(console)
    with TestClient(app,base_url='https://testserver') as client:
        login(client);upload(client,reviewer)
    sid=console.list_envelopes()[0]['snapshot_id']
    attempt,fresh=console.reserve_source_selection(actor_id=author,snapshot_id=sid,command_id='lost-worker',expected_revision=console.objects_revision(sid))
    assert fresh
    restarted=state(tmp_path);bind(restarted,provider)
    from datetime import datetime
    future=datetime.fromisoformat(attempt['expires_at'])+timedelta(seconds=1)
    monkeypatch.setattr('src.processing_retry_v1.now',lambda:future)
    monkeypatch.setattr('src.source_selection_v1.now',lambda:future)
    monkeypatch.setattr('src.source_processing_dispatch_v1.now',lambda:future)
    app=create_console_app(restarted)
    with TestClient(app,base_url='https://testserver') as client:
        login(client)
        screen=client.get('/source-selection',params={'document':sid}).text
        assert 'Status: onderbroken' in screen and '>Hervatten</button>' in screen
        assert start(client,restarted,sid,'resume').status_code==303
        drain(client,app)
        assert 'Status: voltooid' in client.get('/source-selection',params={'document':sid}).text
    final=state(tmp_path)
    assert [a['state'] for a in final._envelope(sid)['processing_attempts']]==['interrupted','succeeded']
    with pytest.raises(ConsoleError):
        final.execute_source_selection(actor_id=author,snapshot_id=sid,attempt=attempt)
    assert final.snapshot_objects(sid)


def test_layout_and_estimate_unknown(tmp_path):
    console=state(tmp_path);_,reviewer=accounts(console)
    with TestClient(create_console_app(console),base_url='https://testserver') as client:
        login(client)
        home=client.get('/').text
        positions=[home.index(f'title="{name}"') if f'title="{name}"' in home else home.index(f'>{name}<') for name in ('Inleveren','Bronselectie','Review','Publicatie','Documenten')]
        assert positions==sorted(positions)
        upload(client,reviewer)
        screen=client.get('/source-selection').text
        assert 'Onvoldoende vergelijkbare metingen' in screen and 'fixture.html' in screen and 'Bronversie 1' in screen


def test_unauthorized_start_and_storage_failure_never_call_provider(backend_state,tmp_path,monkeypatch):
    console=state(tmp_path);_,reviewer=accounts(console);calls=[]
    bind(console,lambda *args:calls.append(1))
    outsider=console.create_account(username='outsider',password='fixture-only',roles=('reviewer',))
    app=create_console_app(console)
    with TestClient(app,base_url='https://testserver',raise_server_exceptions=False) as client:
        login(client);upload(client,reviewer)
        sid=console.list_envelopes()[0]['snapshot_id']
        login(client,'outsider')
        assert start(client,console,sid).status_code==400
        assert console._envelope(sid).get('processing_attempts',[])==[]
        login(client)
        monkeypatch.setattr(console,'_commit_prepared_store',lambda **kwargs:(_ for _ in ()).throw(ConsoleError('workflow_document_write_failed')))
        assert upload(client,reviewer,command='broken').status_code==400
        assert len(console.list_envelopes())==1 and calls==[]


def installed_app(console):
    from src.publish_readiness_ui_v1 import install_publish_readiness_ui
    from src.document_status_ui_v1 import install_document_status_ui
    from src.review_workboard_v1 import install_review_workboard
    from src.proportionate_review_v1 import install_proportionate_review_routes
    from src.deterministic_review_repair_v1 import install_deterministic_review_repair_routes
    from src.closed_review_loop_v1 import install_closed_review_routes
    from src.console_navigation_simplify_v1 import install_navigation_simplification
    app=create_console_app(console)
    install_publish_readiness_ui(app,console);install_document_status_ui(app,console)
    install_review_workboard(app,console);install_proportionate_review_routes(app,console)
    install_deterministic_review_repair_routes(app,console);install_closed_review_routes(app,console)
    install_navigation_simplification(app)
    return app


@pytest.mark.parametrize('path,params',[
    ('/publish',{}),('/review',{'work':'all'}),('/review',{}),
    ('/review',{'task':'disposition'}),('/review',{'task':'individual'}),
    ('/review',{'task':'detail'}),('/review/bronpassage',{})])
def test_a02_installed_reads_bounded_equal_and_next_request_sees_changes(backend_state,tmp_path,monkeypatch,path,params):
    import re
    import src.knowledge_materialisation_v1 as materialisation
    import src.semantic_passage_v1 as semantic
    from src.source_accountability_v1 import is_source_record
    console=state(tmp_path);author,reviewer=accounts(console)
    texts=['Gebruik geen zalf.',*[f'Bronpassage {i} bevat aanvullende informatie voor menselijke beoordeling.' for i in range(30)]]
    def select(_url,_headers,payload,_timeout):
        data=json.loads(payload['input'][1]['content'])
        if not data.get('selection_targets') and any('Gebruik geen zalf.' in b['text'] for b in data['source_blocks']):
            return provider(_url,_headers,payload,_timeout)
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'objects':[],'relations':[],'abstain_reason':'uncertain'})}]}]}
    bind(console,select)
    sid=console.ingest(actor_id=author,filename='fixture.html',data=('<html><body>'+''.join(f'<p>{t}</p>' for t in texts)+'</body></html>').encode(),
        content_type='text/html',ingest_kind='new',title='Fixture',version='1',date='2026-10-08',live_url='',
        class_='richtlijn',family='fixture',named_reviewers=[author,reviewer])['snapshot_id']
    rows=console.snapshot_objects(sid)
    assert sum(is_source_record(o) for o in rows)==30
    source_obj=next(o for o in rows if is_source_record(o))
    candidate=next(o for o in rows if o.get('proposed_object_type')=='recommendation')
    query={**params}
    if path!='/publish' and (params.get('task') or path=='/review/bronpassage'):
        query['document']=sid
    if params.get('task')=='detail':
        query.pop('task');query['object']=candidate['object_id']
    if path=='/review/bronpassage':query['object']=source_obj['object_id']
    original=semantic._reconstructed_blocks;calls=[];representations=[]
    def counted(rows):
        rows=list(rows)
        calls.append(1);representations.append(deepcopy(rows));return original(rows)
    monkeypatch.setattr(semantic,'_reconstructed_blocks',counted)
    monkeypatch.setattr(materialisation,'_reconstructed_blocks',counted)
    app=installed_app(console)
    with TestClient(app,base_url='https://testserver') as client:
        login(client)
        response=client.get(path,params=query)
        assert response.status_code==200,response.text
        assert len(calls)<=2,(path,query,len(calls))
        observed=len(calls)
        read=materialisation._read_source_blocks
        def uncached(*args,**kwargs):
            token=materialisation._source_reconstruction.set(None)
            try:return read(*args,**kwargs)
            finally:materialisation._source_reconstruction.reset(token)
        def normalize(text):
            return re.sub(r'(name="(?:command_id|interaction_id)" value=")[^"]+',r'\1COMMAND',text)
        monkeypatch.setattr(materialisation,'_read_source_blocks',uncached)
        without=client.get(path,params=query)
        assert normalize(response.text)==normalize(without.text)
        monkeypatch.setattr(materialisation,'_read_source_blocks',read)
        calls.clear()
        assert client.get(path,params=query).status_code==200
        assert len(calls)<=2
        # A changed representation is rebuilt on the next request, never held
        # in an application-wide validation/authority cache.
        fragments=console.review_source_fragments(sid)
        fragments=deepcopy(fragments);fragments[-1]['raw_text']=fragments[-1]['clean_text']='Gewijzigde bron.'
        monkeypatch.setattr(console,'review_source_fragments',lambda *args,**kwargs:deepcopy(fragments))
        calls.clear();representations.clear()
        changed=client.get(path,params=query)
        assert changed.status_code==200
        assert len(calls)<=2
        if observed:
            assert calls
            assert any('Gewijzigde bron.' in json.dumps(rows,ensure_ascii=False) for rows in representations)
        print('SOURCE_REUSE_EVIDENCE='+json.dumps({'backend':'postgres' if getattr(console,'workflow_document_store',None) else 'fixture',
            'route':path,'query':query,'source_passages':30,'first_reconstructions':observed,'changed_reconstructions':len(calls)}))
        # Permission is checked anew even when preceding read succeeded.
        login(client,'reviewer')
        if path=='/publish':assert client.get(path,params=query).status_code==403


def test_installed_layout_receipt_and_automatic_selection(tmp_path):
    import re
    console=state(tmp_path);_,reviewer=accounts(console)
    with TestClient(installed_app(console),base_url='https://testserver') as client:
        login(client)
        home=client.get('/').text
        titles=re.findall(r'<span class="home-tile-title">(.*?)</span>',home)
        assert titles[:5]==['Inleveren','Bronselectie','Review','Publicatie','Documenten'],titles
        receipt=upload(client,reviewer)
        selected=client.get(receipt.headers['location'])
        sid=console.list_envelopes()[0]['snapshot_id']
        assert f'<option value="{sid}" selected>' in selected.text
        assert f'data-source-document="{sid}" data-selected="true"' in selected.text
        nav=re.search(r'<nav class="rooms">(.*?)</nav>',selected.text,re.S).group(1)
        labels=re.findall(r'<a[^>]*>(.*?)</a>',nav)
        assert labels[:5]==['Inleveren','Bronselectie','Review','Publicatie','Documenten']


def test_estimates_require_comparable_complete_observations_and_config(tmp_path):
    from src.source_selection_v1 import estimate
    configuration={'mode':'v3','model':'fixture'}
    env={'content_kind':'html','class':'richtlijn','received_source':{'bytes':1000},'processing_configuration':configuration}
    docs=[]
    for elapsed in (120,180,240):
        docs.append({**deepcopy(env),'processing_attempts':[{'state':'succeeded','kind':'ingest',
            'started_at':'2026-10-08T12:00:00+00:00','finished_at':( __import__('datetime').datetime.fromisoformat('2026-10-08T12:00:00+00:00')+timedelta(seconds=elapsed)).isoformat()}]})
    assert estimate(env,docs[:2])['range_seconds'] is None
    assert estimate(env,docs)['sample_count']==3
    assert estimate(env,docs)['range_seconds']==[90,360]
    docs[0]['semantic_replay']={'provider_evidence':{'formation_incomplete':True}}
    assert estimate(env,docs)['range_seconds'] is None
    docs[0].pop('semantic_replay');docs[0]['processing_attempts'][0]['kind']='resume'
    assert estimate(env,docs)['range_seconds'] is None
    assert estimate({**env,'processing_configuration':{'mode':'v4'}},docs)['range_seconds'] is None


def test_http_partial_attempt_success_is_not_complete_then_resume_only_open_ranges(tmp_path):
    from tests.test_recoverable_formation_v1 import system
    from tests.test_recommendation_coverage_v1 import FIRST,SECOND
    console,sid,actor,reviewer,calls,mode,make,rebind=system(tmp_path)
    before=deepcopy(console.snapshot_objects(sid))
    first=next(o for o in before if o['content']['clean_text']==FIRST)
    restarted=make();rebind(restarted);app=installed_app(restarted)
    with TestClient(app,base_url='https://testserver') as client:
        assert client.post('/login',data={'username':'author','password':'strong-test-password'},follow_redirects=False).status_code==303
        screen=client.get('/source-selection',params={'document':sid}).text
        assert 'Status: onderbroken' in screen
        assert 'Poging technisch geslaagd: ja' in screen
        assert 'Volledige bronverwerking: nog niet bevestigd' in screen
        mode['broken']=False;prior_calls=len(calls)
        assert start(client,restarted,sid,'resume-http').status_code==303
        drain(client,app)
        assert 'Status: voltooid' in client.get('/source-selection',params={'document':sid}).text
        assert len(calls)==prior_calls+1
        data=json.loads(calls[-1]['input'][1]['content'])
        assert [b['text'] for b in data['source_blocks']]==[SECOND]
        assert next(o for o in restarted.snapshot_objects(sid) if o['object_id']==first['object_id'])==first
        assert not restarted.publication_readiness(sid)['publish_allowed']


def test_next_http_read_observes_tampered_source_and_new_review_decision(tmp_path):
    from tests.test_recoverable_formation_v1 import system
    from tests.test_recommendation_coverage_v1 import FIRST
    console,sid,actor,reviewer,_,mode,_,_=system(tmp_path,broken=False)
    candidate=next(o for o in console.snapshot_objects(sid) if o['content']['clean_text']==FIRST)
    app=installed_app(console)
    with TestClient(app,base_url='https://testserver') as client:
        assert client.post('/login',data={'username':'reviewer','password':'strong-test-password'},follow_redirects=False).status_code==303
        before=client.get('/publish').text
        source,_=console._verified_source_bytes(console._envelope(sid));original=source.read_bytes()
        try:
            source.write_bytes(b'corrupted source')
            changed=client.get('/publish').text
            assert before!=changed  # genuine file change, no source-reader mock
        finally:source.write_bytes(original)
        assert client.get('/publish').text==before
        console.review_object(actor_id=reviewer,snapshot_id=sid,object_id=candidate['object_id'],decision='reject',comment='Bewaar mijn besluit')
        after=client.get('/publish').text
        assert before!=after
        assert not console.publication_readiness(sid)['publish_allowed']
        assert next(o for o in console.snapshot_objects(sid) if o['object_id']==candidate['object_id'])['governance']['validation_status']=='rejected'


def test_failed_receipt_sync_retries_same_registration(tmp_path,monkeypatch):
    import os
    console=state(tmp_path);_,reviewer=accounts(console)
    app=create_console_app(console)
    with TestClient(app,base_url='https://testserver',raise_server_exceptions=False) as client:
        login(client)
        original=os.fsync
        def fail(fd):raise OSError('fixture-sync-failure')
        monkeypatch.setattr('src.operations_console_v1.os.fsync',fail)
        response=upload(client,reviewer)
        assert response.status_code==500
        assert len(console.list_envelopes())==1
        monkeypatch.setattr('src.operations_console_v1.os.fsync',original)
        repeated=upload(client,reviewer)
        assert repeated.status_code==303 and len(console.list_envelopes())==1
        assert console.list_envelopes()[0].get('processing_attempts',[])==[]


def test_expired_first_selection_can_complete_with_only_retained_source(tmp_path,monkeypatch):
    console=state(tmp_path);author,reviewer=accounts(console)
    with TestClient(create_console_app(console),base_url='https://testserver') as client:
        login(client);upload(client,reviewer)
    sid=console.list_envelopes()[0]['snapshot_id']
    attempt,_=console.reserve_source_selection(actor_id=author,snapshot_id=sid,command_id='expired',expected_revision=console.objects_revision(sid))
    from datetime import datetime
    future=datetime.fromisoformat(attempt['expires_at'])+timedelta(seconds=1)
    monkeypatch.setattr('src.processing_retry_v1.now',lambda:future)
    monkeypatch.setattr('src.source_selection_v1.now',lambda:future)
    def abstain(*args):
        return {'output':[{'content':[{'type':'output_text','text':json.dumps({'objects':[],'relations':[],'abstain_reason':'uncertain'})}]}]}
    bind(console,abstain)
    app=create_console_app(console)
    with TestClient(app,base_url='https://testserver') as client:
        login(client);assert start(client,console,sid,'recover-empty').status_code==303;drain(client,app)
        text=client.get('/source-selection',params={'document':sid}).text
        assert 'Status: voltooid' in text
        assert '0 gevormde kandidaten' in text and '1 overige bronpassages' in text
        assert 'Naar Review' not in text
    assert console._envelope(sid)['processing_attempts'][-1]['state']=='succeeded'
    assert not console.publication_readiness(sid)['publish_allowed']
