"""Alternative source-bound paths and bundles never become a flat conjunction.

# release-control-evidence: scope/belofte kwaliteit slop releasebewijs
"""
from copy import deepcopy
import pytest
from src.decision_graph_v1 import ordered_paths
from tests.test_decision_graph_structure import structure


def test_alternatives_reference_one_shared_outcome_without_modifying_graph(tmp_path):
    graph, objects, inventory = structure(tmp_path, 'single')
    before = deepcopy(graph)
    outcome = graph['edges'][0]['to']
    result = ordered_paths(graph, objects, inventory, outcome)
    assert result['issues'] == []
    assert [[s['label'] for s in p['steps'] if s['label']] for p in result['paths']] == [['Vaak'], ['Soms']]
    assert {p['outcome_id'] for p in result['paths']} == {outcome}
    assert len([n for n in result['nodes'] if n == outcome]) == 1
    assert graph == before
    assert ordered_paths(graph, objects, inventory, graph['entrypoints'][0])['issues'] == ['decision_graph_not_outcome']
    assert ordered_paths(graph, objects, inventory, outcome, max_paths=1)['paths'] == []


@pytest.mark.parametrize('change', ['unresolved', 'missing', 'stale', 'cycle', 'source'])
def test_uncertain_or_invalid_paths_are_not_asserted(tmp_path, change):
    graph, objects, inventory = structure(tmp_path, 'single')
    outcome = graph['edges'][0]['to']
    if change == 'unresolved': graph['unresolved'] = ['uncertain_pdf_connection']
    elif change == 'missing': graph['edges'].pop(1)
    elif change == 'stale': graph['nodes'][0]['object_version'] = '99.0'
    elif change == 'cycle': graph['edges'][-1]['to'] = graph['entrypoints'][0]
    else: graph['source_sha256'] = 'changed'
    result = ordered_paths(graph, objects, inventory, outcome)
    assert result['issues'] and not result['paths']


def test_bundle_members_inherit_each_alternative_without_copying_nodes(tmp_path):
    import fitz
    from tests.test_decision_graph_chain import _console, _accounts, _ingest_boom, policy
    with fitz.open() as doc:
        page=doc.new_page()
        for y,text in [(80,'Hoe vaak?'),(130,'Vaak'),(180,'Soms'),(260,'Plan:\n- Neem contact op.\n- Maak een afspraak.')]:
            page.insert_text((70,y),text)
        page.draw_line((110,90),(110,245)); data=doc.tobytes()
    console=_console(tmp_path); accounts=_accounts(console)
    sid=_ingest_boom(console,accounts,data=data,filename='bundle-paths.pdf',content_type='application/pdf',
                     named_reviewers=[],review_policy=policy(accounts))['snapshot_id']
    env=console._envelope(sid); rows=console.snapshot_objects(sid)
    by_text={o['content']['clean_text']:o for o in rows}
    container=next(o for o in rows if (o.get('metadata') or {}).get('result_bundle',{}).get('role')=='container')
    members=[o for o in rows if (o.get('metadata') or {}).get('result_bundle',{}).get('role')=='member']
    question=by_text['Hoe vaak?']['object_id']; graph=deepcopy(env['decision_graph'])
    for node in graph['nodes']:
        node['mode']='single' if node['object_id']==question else 'terminal' if node['object_id']==container['object_id'] else 'context'
    graphic=next(k for k,v in env['decision_graph_evidence']['items'].items() if v['kind']=='graphic')
    graph.update(entrypoints=[question],unresolved=[],edges=[
        {'id':str(index),'from':question,'to':container['object_id'],'kind':'answer','label':label,
         'evidence_ids':[graphic,by_text[label]['provenance']['source_fragments'][0]['raw_object_id']]}
        for index,label in enumerate(['Vaak','Soms'])])
    shared=ordered_paths(graph,rows,env['decision_graph_evidence'],container['object_id'])
    assert shared['issues']==[] and len(shared['paths'])==2
    for member in members:
        result=ordered_paths(graph,rows,env['decision_graph_evidence'],member['object_id'])
        assert result['issues']==[] and result['nodes']==shared['nodes']
        assert [p['steps'] for p in result['paths']]==[p['steps'] for p in shared['paths']]
        assert {p['route_outcome_id'] for p in result['paths']}=={container['object_id']}
        assert {p['outcome_id'] for p in result['paths']}=={member['object_id']}
