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


def test_export_tree_publishes_with_only_selection_and_entry_labelled(production_console, tmp_path):
    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    accounts = _accounts(console)
    actor = accounts['researcher']['account_id']
    data = {'kind': 'beslisboom-freeze', 'nodes': [{'id': 'q', 'text': 'Is er letsel?'}],
            'outcomes': [{'id':'a','text':'Beoordeel het letsel.'},{'id':'b','text':'Bespreek preventie.'}],
            'branches': [{'from':'q','to':'a','label':'Ja'},{'from':'q','to':'b','label':'Nee'}]}
    sid = console.receive_source(actor_id=actor, filename='tree.json', data=json.dumps(data).encode(),
        content_type='application/json', ingest_kind='new', title='Boom', version='1.0', date='2026-11-10',
        live_url='', class_='beslisboom', family='test', named_reviewers=[], review_policy=policy(accounts))['snapshot_id']
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
    env = console._envelope(sid)
    assert env['decision_tree_formation']['route'] == 'decision-tree-annotation-v1'
    assert env['decision_tree_formation']['model'] is None
    assert env['decision_tree_formation']['annotation_seal_id'] == receipt['seal_id']

    assert {e['label'] for e in env['decision_graph']['edges']} == {'Ja', 'Nee'}
    publish_reviewed(console, accounts, sid)


def publish_reviewed(console, accounts, sid):
    scope = {'actor_id': accounts['researcher']['account_id'], 'snapshot_id': sid}
    def bind(command_id):
        graph = annotated_graph_for_review(console._envelope(sid), console.snapshot_objects(sid))
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
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    assert result['status'] == 'PASS', result


def test_pdf_tree_publishes_without_a_model(production_console, tmp_path):
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
    env = console._envelope(sid)
    assert env['decision_tree_formation']['model'] is None
    ungrounded = annotated_graph_for_review(env, console.snapshot_objects(sid))
    assert ungrounded['unresolved']
    ungrounded['unresolved'] = []
    with pytest.raises(ConsoleError, match='decision_graph_annotation_correction_required'):
        console.update_decision_graph(**command(console, accounts, sid, 'bypass', graph=ungrounded))
    graph['unresolved'] = []
    save_and_build(1)
    publish_reviewed(console, accounts, sid)
