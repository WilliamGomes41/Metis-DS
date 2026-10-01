"""Participation lifecycle evidence, HTTP authorization and exact review preservation.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.integrity_kernel import canonical_object_payload
from src.review_policy_v1 import object_policy, participants, missing_reviewers
from tests.test_decision_graph_chain import _console, _accounts, ingest, finish, command


@pytest.fixture(params=['local', 'postgres'])
def setup(request, tmp_path):
    if request.param == 'postgres':
        from tests.decision_graph_native_support import native_state
        state, store, source = native_state(tmp_path)
    else:
        state = lambda node='default': _console(tmp_path)
        store = None
    console = state()
    accounts = _accounts(console)
    sid = ingest(console, accounts)['snapshot_id']
    finish(console, accounts, sid)
    return state, accounts, sid, store


def person(console, name='replacement', roles=('reviewer',)):
    return console.create_account(username=name, password='test-only-password', roles=roles, display_name=name)['account_id']


def change(console, accounts, sid, action, reviewer, **extra):
    return console.manage_review_participation(actor_id=extra.pop('actor_id', accounts['publisher']['account_id']),
        snapshot_id=sid, action=action, reviewer_id=reviewer, reason='Collega afwezig; werk overnemen',
        command_id=extra.pop('command_id',uuid4().hex), expected_revision=extra.pop('expected_revision',console.objects_revision(sid)), **extra)


def passages(console,sid):
    return [o for o in console.snapshot_objects(sid) if o['object_type']!='document']


def approve_all(console, accounts, sid, actor):
    for o in passages(console,sid):
        console.approve_second_review(actor_id=actor, snapshot_id=sid, object_id=o['object_id'])
    c=command(console,accounts,sid,uuid4().hex);c['actor_id']=actor
    console.confirm_decision_graph(**c)


def test_optional_add_preserves_exact_evidence_restart_and_publication(setup):
    state, accounts, sid, store=setup
    console=state()
    old=[canonical_object_payload(o) for o in passages(console,sid)]
    approvals=deepcopy(console.object_review_bindings(sid))
    graphs=deepcopy(console._envelope(sid)['decision_graph_reviews'])
    change(console,accounts,sid,'add_optional',accounts['reviewer']['account_id'],actor_id=accounts['researcher']['account_id'])
    console=state('restart')
    assert [canonical_object_payload(o) for o in passages(console,sid)]==old
    assert console.object_review_bindings(sid)==approvals
    assert console._envelope(sid)['decision_graph_reviews']==graphs
    result=console.consider_publish(actor_id=accounts['publisher']['account_id'],snapshot_id=sid)
    assert 'decision_graph_review_incomplete' not in result['blockers']
    assert 'required_policy_review_missing' not in result['blockers']
    if store:
        result=console.publish(actor_id=accounts['publisher']['account_id'],snapshot_id=sid)
        assert result['status']=='PASS',result
        with pytest.raises(ConsoleError,match='published_working_revision_immutable'):
            change(state('after-publish'),accounts,sid,'archive',accounts['reviewer']['account_id'])


def test_archive_required_then_replace_keeps_primary_and_demands_new_person(setup):
    state,accounts,sid,store=setup;console=state()
    secondary=accounts['reviewer']['account_id'];primary=accounts['researcher']['account_id']
    change(console,accounts,sid,'add_required',secondary)
    approve_all(console,accounts,sid,secondary)
    old=[canonical_object_payload(o) for o in passages(console,sid)]
    change(console,accounts,sid,'archive',secondary)
    console=state('restart')
    assert secondary not in console._envelope(sid)['named_reviewers']
    result=console.consider_publish(actor_id=accounts['publisher']['account_id'],snapshot_id=sid)
    assert 'archived_required_review_unfilled' in result['blockers']
    assert all(secondary in missing_reviewers(o,console.object_review_bindings(sid)) for o in passages(console,sid))
    with pytest.raises(ConsoleError,match='reviewer_not_named'):
        console.approve_second_review(actor_id=secondary,snapshot_id=sid,object_id=passages(console,sid)[0]['object_id'])
    with pytest.raises(ConsoleError,match='independent_replacement_required'):
        change(console,accounts,sid,'replace',secondary,replacement_id=primary)
    replacement=person(console)
    change(console,accounts,sid,'replace',secondary,replacement_id=replacement)
    assert [canonical_object_payload(o) for o in passages(console,sid)]==old
    assert all(missing_reviewers(o,console.object_review_bindings(sid))=={replacement} for o in passages(console,sid))
    approve_all(console,accounts,sid,replacement)
    console=state('verify')
    assert len(console._envelope(sid)['review_participation_history'])==3
    assert console._envelope(sid)['review_participation_history'][1]['retired_bindings']
    assert not any(missing_reviewers(o,console.object_review_bindings(sid)) for o in passages(console,sid))
    if store:
        result=console.publish(actor_id=accounts['publisher']['account_id'],snapshot_id=sid)
        assert result['status']=='PASS',result


def test_command_permissions_replay_and_no_policy_editor_bypass(setup):
    state,accounts,sid,_=setup;console=state()
    other=accounts['reviewer']['account_id'];primary=accounts['researcher']['account_id']
    with pytest.raises(ConsoleError,match='participation_publisher_required'):
        change(console,accounts,sid,'add_optional',other,actor_id=other)
    with pytest.raises(ConsoleError,match='reviewer_role_required'):
        change(console,accounts,sid,'add_optional',accounts['publisher']['account_id'])
    cmd_id=uuid4().hex;rev=console.objects_revision(sid)
    change(console,accounts,sid,'add_optional',other,command_id=cmd_id,expected_revision=rev)
    assert change(console,accounts,sid,'add_optional',other,command_id=cmd_id,expected_revision=rev)['idempotent']
    with pytest.raises(ConsoleError,match='participation_command_conflict'):
        change(console,accounts,sid,'add_required',other,command_id=cmd_id,expected_revision=rev)
    with pytest.raises(ConsoleError,match='snapshot_object_write_conflict'):
        change(console,accounts,sid,'archive',other,expected_revision=rev)
    with pytest.raises(ConsoleError,match='managed_participation_command_required'):
        console.change_review_policy(**command(console,accounts,sid,'bypass',policy=console._envelope(sid)['review_policy']))
    with pytest.raises(ConsoleError,match='primary_replacement_required'):
        change(console,accounts,sid,'archive',primary)


def test_http_all_mine_theme_readonly_and_escalation(tmp_path):
    from src.operations_console_app import create_console_app
    from src.review_workboard_v1 import install_review_workboard
    console=_console(tmp_path);accounts=_accounts(console);sid=ingest(console,accounts)['snapshot_id']
    app=create_console_app(console);install_review_workboard(app,console)
    with TestClient(app,base_url='https://testserver') as client:
        client.post('/login',data={'username':'reviewer.bert','password':'bert-secret'})
        assert console._envelope(sid)['title'] not in client.get('/review').text
        all_work=client.get('/review?work=all');assert all_work.status_code==200
        assert console._envelope(sid)['title'] in all_work.text and 'Alleen lezen' in all_work.text
        assert console._envelope(sid)['title'] not in client.get('/review?work=all&theme=nonexistent').text
        before=deepcopy(console._envelope(sid));bindings=deepcopy(console.object_review_bindings(sid))
        assert client.get('/review/trajectory',params={'document':sid}).status_code==200
        assert client.get('/review',params={'document':sid,'task':'individual'}).status_code==200
        assert console._envelope(sid)==before and console.object_review_bindings(sid)==bindings
        denied=client.post('/review/participants',data={'document':sid,'action':'add_optional','reviewer_id':accounts['reviewer']['account_id'],'reason':'self','command_id':'bad','expected_revision':console.objects_revision(sid)})
        assert denied.status_code>=400
        client.post('/login',data={'username':'publisher.carla','password':'carla-secret'})
        assert client.get('/review?work=all').status_code==200
        assert client.get('/review/participants',params={'document':sid}).status_code==200
        added=client.post('/review/participants',data={'document':sid,'action':'add_optional','reviewer_id':accounts['reviewer']['account_id'],'reason':'Collega ondersteunt','command_id':'good','expected_revision':console.objects_revision(sid)})
        assert added.status_code==200
        assert accounts['reviewer']['account_id'] in console._envelope(sid)['named_reviewers']


def test_primary_replacement_and_readd_do_not_resurrect_evidence(setup):
    state,accounts,sid,_=setup;console=state();primary=accounts['researcher']['account_id']
    new=person(console,roles=('reviewer','publisher'))
    change(console,accounts,sid,'replace',primary,replacement_id=new,actor_id=new)
    assert all(new in missing_reviewers(o,console.object_review_bindings(sid)) for o in passages(console,sid))
    for o in passages(console,sid):
        console.review_object(actor_id=new,snapshot_id=sid,object_id=o['object_id'],decision='approve',confirmed_object_type='node')
    c=command(console,accounts,sid,'primary-confirm');c['actor_id']=new
    console.confirm_decision_graph(**c)
    change(console,accounts,sid,'add_required',primary)
    assert all(primary in missing_reviewers(o,console.object_review_bindings(sid)) for o in passages(console,sid))
    approve_all(console,accounts,sid,primary)
    change(console,accounts,sid,'archive',primary)
    change(console,accounts,sid,'add_required',primary)
    assert all(primary in missing_reviewers(o,console.object_review_bindings(sid)) for o in passages(console,sid))


def test_native_participation_publication_race_and_rollback(tmp_path,monkeypatch):
    from tests.decision_graph_native_support import native_state
    state,store,_=native_state(tmp_path);console=state('setup');accounts=_accounts(console)
    sid=ingest(console,accounts)['snapshot_id'];finish(console,accounts,sid)
    editor=state('editor');publisher=state('publisher');barrier=Barrier(2)
    rev=editor.objects_revision(sid)
    def race(i):
        barrier.wait(timeout=5)
        try:
            if i==0:
                return publisher.publish(actor_id=accounts['publisher']['account_id'],snapshot_id=sid)
            return change(editor,accounts,sid,'add_required',accounts['reviewer']['account_id'],expected_revision=rev)
        except ConsoleError as exc: return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        published, changed=list(pool.map(race,range(2)))
    if store.release_for_snapshot(sid):
        assert published['status']=='PASS';assert changed=='published_working_revision_immutable'
    else:
        assert published['status']=='BLOCKED';assert isinstance(changed,dict)
    # Independent new revision for rollback, regardless of which race won.
    other=ingest(state('new'),accounts)['snapshot_id']
    worker=state('rollback');before=deepcopy(worker._envelope(other));objects=deepcopy(worker.snapshot_objects(other));events=worker.workflow_review_store.read_events()
    original=worker._commit_prepared_store
    def fail(**kwargs):
        original(**kwargs);raise RuntimeError('after_writes_before_commit')
    monkeypatch.setattr(worker,'_commit_prepared_store',fail)
    with pytest.raises(RuntimeError,match='after_writes_before_commit'):
        change(worker,accounts,other,'add_optional',accounts['reviewer']['account_id'])
    restarted=state('verify')
    assert restarted._envelope(other)==before
    assert restarted.snapshot_objects(other)==objects
    assert restarted.workflow_review_store.read_events()==events


def test_native_concurrent_roster_changes_and_late_extraction(tmp_path,monkeypatch):
    from tests.decision_graph_native_support import native_state
    from threading import Event
    state,_,_=native_state(tmp_path);console=state('setup');accounts=_accounts(console)
    sid=ingest(console,accounts)['snapshot_id'];extra=person(console)
    workers=[state('one'),state('two')];barrier=Barrier(2);rev=console.objects_revision(sid)
    def race(i):
        barrier.wait(timeout=5)
        try:return change(workers[i],accounts,sid,'add_optional',[extra,accounts['reviewer']['account_id']][i],expected_revision=rev)
        except ConsoleError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(race,range(2)))
    assert sum(isinstance(r,dict) for r in results)==1
    assert results.count('snapshot_object_write_conflict')==1
    worker=state('extract');editor=state('edit');started=Event();proceed=Event();original=worker._fragments_and_spec
    def delayed(*args,**kwargs):
        started.set();assert proceed.wait(timeout=5);return original(*args,**kwargs)
    monkeypatch.setattr(worker,'_fragments_and_spec',delayed)
    target=next(i for i in [extra,accounts['reviewer']['account_id']] if i not in editor._envelope(sid)['named_reviewers'])
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(worker.reextract_unpublished,actor_id=accounts['researcher']['account_id'],snapshot_id=sid)
        assert started.wait(timeout=5)
        try:change(editor,accounts,sid,'add_required',target)
        finally:proceed.set()
        with pytest.raises(ConsoleError,match='snapshot_object_write_conflict'):future.result(timeout=10)
    assert target in state('after')._envelope(sid)['named_reviewers']


def test_legacy_requires_explicit_publisher_and_preserves_exact_old_approvals(tmp_path):
    from tests.test_v225_beslisboom_path import _ingest_boom
    console=_console(tmp_path);accounts=_accounts(console)
    sid=_ingest_boom(console,accounts)['snapshot_id']
    extra=person(console)
    before=[canonical_object_payload(o) for o in passages(console,sid)]
    named=console._envelope(sid)['named_reviewers']
    with pytest.raises(ConsoleError,match='legacy_participation_activation_requires_publisher'):
        change(console,accounts,sid,'add_optional',extra,actor_id=named[0])
    change(console,accounts,sid,'add_required',extra)
    assert [canonical_object_payload(o) for o in passages(console,sid)]==before
    assert set(named).issubset(set(participants(console._envelope(sid)['review_policy'])))
    assert all(object_policy(o)['review_basis'] is None for o in passages(console,sid))


def test_managed_route_correction_invalidates_evidence(setup):
    from tests.test_decision_graph_chain import complete_graph
    state,accounts,sid,_=setup;console=state()
    change(console,accounts,sid,'add_optional',accounts['reviewer']['account_id'])
    graph=complete_graph(console,sid);graph['nodes'][0]['mode']='unresolved'
    console.update_decision_graph(**command(console,accounts,sid,'changed-route',graph=graph))
    assert console._envelope(sid)['decision_graph_reviews']==[]
    result = console.consider_publish(actor_id=accounts['publisher']['account_id'],snapshot_id=sid)
    assert any(b.startswith('decision_graph_') for b in result['blockers'])


def _participant_forms(html):
    from html.parser import HTMLParser

    class Forms(HTMLParser):
        def __init__(self):
            super().__init__(); self.forms=[]; self.current=None; self.select=None
        def handle_starttag(self, tag, attrs):
            a=dict(attrs)
            if tag=='form':
                self.current={'inputs':{},'choices':{}}; self.forms.append(self.current)
            elif self.current is not None:
                if tag=='input':
                    self.current['inputs'][a.get('name')]=a.get('value','')
                elif tag=='select':
                    self.select=a.get('name'); self.current['choices'][self.select]=[]
                elif tag=='option' and self.select:
                    self.current['choices'][self.select].append(a.get('value'))
        def handle_endtag(self, tag):
            if tag=='form': self.current=None
            if tag=='select': self.select=None
    parser=Forms();parser.feed(html)
    return [f for f in parser.forms if 'action' in f['inputs']]


def test_participant_forms_offer_only_available_allowed_choices(tmp_path):
    from src.operations_console_app import create_console_app
    console=_console(tmp_path); accounts=_accounts(console); sid=ingest(console,accounts)['snapshot_id']
    primary=accounts['researcher']['account_id']; secondary=accounts['reviewer']['account_id']
    change(console,accounts,sid,'add_required',secondary)
    change(console,accounts,sid,'archive',secondary)
    optional=person(console,'archived.optional')
    change(console,accounts,sid,'add_optional',optional)
    change(console,accounts,sid,'archive',optional)
    available=person(console,'available')
    unavailable=[]
    for flag in ('retirement','blocked','disabled'):
        actor=person(console,flag);console._accounts[actor][flag]=True;unavailable.append(actor)
    console._save_accounts()
    with TestClient(create_console_app(console),base_url='https://testserver') as client:
        client.post('/login',data={'username':'publisher.carla','password':'carla-secret'})
        page=client.get('/review/participants',params={'document':sid})
        forms=_participant_forms(page.text)
        optional_add=next(f for f in forms if f['inputs']['action']=='add_optional')
        required_add=next(f for f in forms if f['inputs']['action']=='add_required')
        assert set(optional_add['choices']['reviewer_id'])=={optional,available}
        assert set(required_add['choices']['reviewer_id'])=={optional,available,secondary}
        assert not any(f['inputs']['action']=='archive' for f in forms)
        for f in forms:
            for ids in f['choices'].values():
                assert not set(ids)&set(unavailable+[accounts['publisher']['account_id'],primary])
            if f['inputs']['action']=='replace':
                target=f['inputs']['reviewer_id']
                assert set(f['choices']['replacement_id'])=={optional,available}-{target}
        # Crafted submissions still reach the authoritative command guard.
        before=deepcopy(console._envelope(sid))
        denied=client.post('/review/participants',data={**required_add['inputs'],'reviewer_id':primary,'reason':'already assigned'})
        assert denied.status_code==400 and 'neemt al deel' in denied.text
        assert console._envelope(sid)==before
        client.post('/login',data={'username':'researcher.anne','password':'anne-secret'})
        mine=_participant_forms(client.get('/review/participants',params={'document':sid}).text)
        assert [f['inputs']['action'] for f in mine]==['add_optional']


def test_trajectory_readable_history_navigation_and_archive_error(tmp_path):
    from src.operations_console_app import create_console_app
    console=_console(tmp_path);accounts=_accounts(console);sid=ingest(console,accounts)['snapshot_id'];finish(console,accounts,sid)
    primary=accounts['researcher']['account_id']; secondary=accounts['reviewer']['account_id']
    change(console,accounts,sid,'add_required',secondary);approve_all(console,accounts,sid,secondary)
    change(console,accounts,sid,'archive',secondary)
    replacement=person(console,'Daan Vervanger')
    change(console,accounts,sid,'replace',secondary,replacement_id=replacement)
    before=deepcopy(console._envelope(sid));bindings=deepcopy(console.object_review_bindings(sid))
    with TestClient(create_console_app(console),base_url='https://testserver') as client:
        client.post('/login',data={'username':'publisher.carla','password':'carla-secret'})
        trajectory=client.get('/review/trajectory',params={'document':sid})
        assert trajectory.status_code==200
        assert '2 goedgekeurd' in trajectory.text and 'Passage 1 (versie ' in trajectory.text
        assert 'Verplichte reviewer toegevoegd' in trajectory.text and 'Deelname gearchiveerd' in trajectory.text
        assert 'Reviewer vervangen' in trajectory.text and 'Daan Vervanger' in trajectory.text
        assert 'Bert Reviewer: Goedgekeurd' in trajectory.text and 'historisch' in trajectory.text
        assert 'Terug naar reviewoverzicht' in trajectory.text
        assert 'add_required' not in trajectory.text and "{'approved'" not in trajectory.text
        assert not any(o['object_id'] in trajectory.text for o in passages(console,sid))
        manage=client.get('/review/participants',params={'document':sid})
        assert 'Terug naar traject' in manage.text
        denied=client.post('/review/participants',data={'document':sid,'action':'archive','reviewer_id':primary,
            'reason':'test','command_id':uuid4().hex,'expected_revision':console.objects_revision(sid)})
        assert denied.status_code==400
        assert 'primaire reviewer niet archiveren' in denied.text and 'Reviewer vervangen' in denied.text
        assert '/review/participants?document='+sid in denied.text
        assert 'Terug naar deelnemersbeheer' in denied.text
        assert console._envelope(sid)==before and console.object_review_bindings(sid)==bindings


def test_participant_page_has_no_submit_when_no_candidate_available(tmp_path):
    from src.operations_console_app import create_console_app
    console=_console(tmp_path);accounts=_accounts(console);sid=ingest(console,accounts)['snapshot_id']
    change(console,accounts,sid,'add_required',accounts['reviewer']['account_id'])
    with TestClient(create_console_app(console),base_url='https://testserver') as client:
        client.post('/login',data={'username':'publisher.carla','password':'carla-secret'})
        page=client.get('/review/participants',params={'document':sid})
        forms=_participant_forms(page.text)
        assert [f['inputs']['action'] for f in forms]==['archive']
        assert forms[0]['choices']['reviewer_id']==[accounts['reviewer']['account_id']]
        assert 'Geen beschikbare reviewers voor deze handeling.' in page.text
