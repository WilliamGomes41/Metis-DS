"""Human tree input through the production annotation worker and evidence store."""
import json
from uuid import uuid4

import pytest

from src.vorming import human_annotation_v1 as annotation, human_annotation_build_v1 as build
from src.vorming.human_annotation_decision_tree_v1 import export_entries
from src.vorming.worker_handover_v1 import native_attempt
from tests.test_decision_graph_chain import _accounts, command, policy
from tests.test_durable_publication_console_v1 import MemorySourceStore
from tests.ko_review_fixture_support import affirmative_assessment
from src.review.decision_review_commands_v1 import annotated_graph_for_review
from tests.test_human_annotation_build_postgres import closing
from src.operations_console_v1 import ConsoleError


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_export_tree_publishes_with_only_selection_and_entry_labelled(production_console, tmp_path, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    accounts = _accounts(console)
    actor = accounts['researcher']['account_id']
    data = {'kind': 'beslisboom-freeze', 'nodes': [{'id': 'q', 'text': 'Is er letsel?'}],
            'outcomes': [{'id':'a','text':'Beoordeel het letsel.'},{'id':'b','text':'Bespreek preventie.'}],
            'branches': [{'from':'q','to':'a','label':'Ja'},{'from':'q','to':'b','label':'Nee'}]}
    sid = console.receive_source(actor_id=actor, filename='tree.json', data=json.dumps(data).encode(),
        content_type='application/json', ingest_kind='new', title='Boom', version='1.0', date='2026-11-10',
        live_url='', class_='beslisboom', family='test', named_reviewers=[], review_policy=policy(accounts, 'required'))['snapshot_id']
    scope = {'actor_id': actor, 'snapshot_id': sid}
    view = annotation.prepare(console, **scope, expected_revision=console.objects_revision(sid))
    row, fragments = annotation._read_set(console, sid)
    graph = export_entries(fragments, row['extraction']['tree_source']['inventory'])
    graph['units'][0].update(entry=True, role='question', selection='single')
    console._decision_tree_proposer = lambda *_: (_ for _ in ()).throw(AssertionError('model invoked'))
    annotation.save(console, **scope, annotation_id=str(uuid4()), command_id=str(uuid4()), expected_revision=0,
                    expected_generation=0, extraction_hash=view['extraction_hash'], normalization=view['normalization'],
                    selection=graph)
    overview = build.overview(console, **scope)
    assert overview['can_finalize']
    receipt = build.finalize(console, actor_id=actor, **closing(overview))
    attempt = native_attempt(console, sid, receipt['attempt_id'])
    console.execute_source_selection(**scope, attempt=attempt)
    env = console._tree_envelope(sid, envelope=console._envelope(sid))
    assert env['decision_tree_formation']['route'] == 'decision-tree-annotation-v1'
    assert env['decision_tree_formation']['model'] is None
    assert env['decision_tree_formation']['annotation_seal_id'] == receipt['seal_id']

    assert {e['label'] for e in env['decision_graph']['edges']} == {'Ja', 'Nee'}
    publish_reviewed(console, accounts, sid, second_required=True)


def publish_reviewed(console, accounts, sid, *, second_required=False):
    scope = {'actor_id': accounts['researcher']['account_id'], 'snapshot_id': sid}
    def bind(command_id):
        graph = annotated_graph_for_review(console._tree_envelope(sid, envelope=console._envelope(sid)), console.snapshot_objects(sid))
        assert graph['unresolved'] == []
        console.update_decision_graph(**command(console, accounts, sid, command_id, graph=graph))
    bind('graph')
    for obj in console.snapshot_objects(sid):
        if obj['object_type'] != 'document':
            console.review_object(**scope, object_id=obj['object_id'], decision='approve',
                confirmed_object_type=obj.get('proposed_object_type') or 'node',
                recommendation_strength='doen' if obj.get('proposed_object_type') == 'outcome' else None,
                assessment=affirmative_assessment(), evidence_not_applicable=True)
    bind('reviewed')
    console.confirm_decision_graph(**command(console, accounts, sid, 'confirm'))
    if second_required:
        blocked = console.consider_publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
        assert 'decision_graph_review_incomplete' in blocked['blockers']
        secondary = accounts['reviewer']['account_id']
        for obj in console.snapshot_objects(sid):
            if obj['object_type'] != 'document':
                console.approve_second_review(actor_id=secondary, snapshot_id=sid, object_id=obj['object_id'],
                                              assessment=affirmative_assessment(), evidence_not_applicable=True)
        confirmation = command(console, accounts, sid, 'confirm-second')
        console.confirm_decision_graph(**{**confirmation, 'actor_id': secondary})
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    assert result['status'] == 'PASS', result


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_pdf_tree_publishes_without_a_model(production_console, tmp_path, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    from src.vorming.decision_tree_construction_v1 import proposal_inputs
    from src.vorming.human_annotation_decision_tree_v1 import empty_entries
    import fitz

    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    accounts = _accounts(console)
    actor = accounts['researcher']['account_id']
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((80,80), 'Bespreek de situatie.')
        page.insert_text((80,200), 'Maak een vervolgafspraak.')
        shape = page.new_shape()
        from tests.test_decision_tree_proposal_route_v1 import _arrow
        _arrow(shape, (120,85), (120,188))
        shape.finish(closePath=False)
        shape.commit()
        data = pdf.tobytes()
    sid = console.receive_source(actor_id=actor, filename='tree.pdf', data=data,
        content_type='application/pdf', ingest_kind='new', title='Boom', version='1.0', date='2026-11-10',
        live_url='', class_='beslisboom', family='test', named_reviewers=[], review_policy=policy(accounts))['snapshot_id']
    scope = {'actor_id': actor, 'snapshot_id': sid}
    view = annotation.prepare(console, **scope, expected_revision=console.objects_revision(sid))
    row, fragments = annotation._read_set(console, sid)
    graph = empty_entries()
    for i, block in enumerate(proposal_inputs(fragments)):
        graph['units'].append({'ref':f'u{i}', 'role':'action' if i == 0 else 'outcome', 'entry':i == 0,
            'selection':None, 'spans':[{'block_id':block['block_id'], 'start':0, 'end':len(block['text'])}]})
    graphic = next(k for k,v in row['extraction']['tree_source']['inventory']['items'].items() if v['kind']=='graphic')
    graph['connections'].append({'ref':'c1','kind':'continue','from':'u0','to':'u1','label_span':None,'evidence_ids':[graphic]})
    aid = str(uuid4())
    graph['unresolved'].append({'ref':'d1','subject':'u0','code':'role_ambiguous'})
    def save_and_build(generation):
        annotation.save(console, **scope, annotation_id=aid, command_id=str(uuid4()), expected_revision=generation,
                        expected_generation=generation, expected_objects_revision=console.objects_revision(sid),
                        extraction_hash=view['extraction_hash'], normalization=view['normalization'], selection=graph)
        receipt = build.finalize(console, actor_id=actor, **closing(build.overview(console, **scope)))
        console.execute_source_selection(**scope, attempt=native_attempt(console, sid, receipt['attempt_id']))
    save_and_build(0)
    env = console._tree_envelope(sid, envelope=console._envelope(sid))
    assert env['decision_tree_formation']['model'] is None
    ungrounded = annotated_graph_for_review(env, console.snapshot_objects(sid))
    assert ungrounded['unresolved']
    ungrounded['unresolved'] = []
    with pytest.raises(ConsoleError, match='decision_graph_annotation_correction_required'):
        console.update_decision_graph(**command(console, accounts, sid, 'bypass', graph=ungrounded))
    graph['unresolved'] = []
    save_and_build(1)
    publish_reviewed(console, accounts, sid)


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_direct_ingest_registers_tree_for_annotation(production_console, tmp_path, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    from tests.test_decision_graph_chain import source_pdf
    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    accounts = _accounts(console)
    actor = accounts['researcher']['account_id']
    def unexpected_model(*args, **kwargs):
        pytest.fail('A new decision-tree snapshot invoked the model.')
    console._decision_tree_proposer = unexpected_model
    command_data = dict(actor_id=actor, filename='tree.pdf', data=source_pdf(), content_type='application/pdf',
        ingest_kind='new', title='Bron', version='1.0', date='2026-11-28', live_url='', class_='beslisboom',
        family='test', named_reviewers=[], review_policy=policy(accounts), command_id='receive-1191')
    sid = console.ingest(**command_data)['snapshot_id']
    assert console.ingest(**command_data)['snapshot_id'] == sid
    scope = {'actor_id':actor, 'snapshot_id':sid}
    assert console._envelope(sid)['received_source']['formation_route'] == 'decision-tree-annotation-v1'
    revision = console.objects_revision(sid)
    commands = [(console.reserve_source_selection, {'command_id':'start','expected_revision':revision}),
                (console.retry_pre_review, {'command_id':'retry'}),
                (console.resume_formation, {'command_id':'resume','expected_revision':revision}),
                (console.reextract_unpublished, {})]
    for method, arguments in commands:
        with pytest.raises(ConsoleError, match='decision_tree_annotation_required'):
            method(**scope, **arguments)
    assert not console._processing_history_envelope(sid).get('processing_attempts')
    assert not console.snapshot_objects(sid, include_blocked=True)
    assert annotation.prepare(console, **scope, expected_revision=revision)['blocks']


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_open_tree_attempt_closes_once_and_successor_can_annotate(production_console, tmp_path, monkeypatch, storage):
    from src.vorming.processing_retry_v1 import reserve, now
    from src.vorming.source_processing_dispatch_v1 import retire_open_tree_attempts
    from tests.test_decision_graph_chain import source_pdf
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', storage)
    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    accounts = _accounts(console)
    actor = accounts['researcher']['account_id']
    sid = console.receive_source(actor_id=actor, filename='old.pdf', data=source_pdf(), content_type='application/pdf',
        ingest_kind='new', title='Oude boom', version='1', date='2026-11-28', live_url='', class_='beslisboom',
        family='test', named_reviewers=[], review_policy=policy(accounts))['snapshot_id']
    revision = console.objects_revision(sid)
    with console._reprocessing_transaction(sid):
        env = console._processing_command_envelope(sid)
        del env['received_source']['formation_route']
        reserve(env, command_id='old-model', actor_id=actor, revision=revision, clock=now(),
                limits=console._processing_limits(), kind='ingest')
        console._commit_prepared_store(envelopes={sid:env}, snapshot_id=sid)
    retire_open_tree_attempts(console)
    attempt, = console._processing_history_envelope(sid)['processing_attempts']
    assert (attempt['state'], attempt['error_code']) == ('failed', 'decision_tree_model_route_retired')
    retire_open_tree_attempts(console)
    assert console._processing_history_envelope(sid)['processing_attempts'] == [attempt]
    with pytest.raises(ConsoleError, match='decision_tree_model_route_retired'):
        annotation.prepare(console, actor_id=actor, snapshot_id=sid, expected_revision=revision)
    from starlette.testclient import TestClient
    from tests.production_support import application_for
    from tests.test_formation_repair_workplace import form_data
    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username':'researcher.anne', 'password':'anne-secret'})
        page = client.get('/source-selection', params={'document':sid})
        assert 'De AI-poging is afgesloten' in page.text
        action = '/source-selection/annotation-successor'
        response = client.post(action, data=form_data(page, action), follow_redirects=False)
        assert response.status_code == 303
        from urllib.parse import parse_qs, urlsplit
        assert urlsplit(response.headers['location']).path == '/annotations'
        child = parse_qs(urlsplit(response.headers['location']).query)['document'][0]
        assert client.get(response.headers['location']).status_code == 200
    assert child != sid and console._envelope(child)['replaces_snapshot_id'] == sid
    assert console._envelope(child)['sha256'] == console._envelope(sid)['sha256']
    assert annotation.prepare(console, actor_id=actor, snapshot_id=child,
                              expected_revision=console.objects_revision(child))['blocks']
