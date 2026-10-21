"""Isolated browser fixture; never installed by a production app.

Model proposals are deterministic test doubles, not semantic validation evidence.
"""
import json, tempfile
from pathlib import Path
from fastapi.responses import HTMLResponse, JSONResponse
from src.operations_console_app import create_console_app, _knowledge_review_html, _decision_paths_html, _page
from src.operations_console_v1 import OperationsConsole
PASSWORD="browser-fixture-secret"
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.source_bound_fields_v2 import MODE, FIELDS
from tests.context_test_support import bind_detected_context
from tests.test_decision_graph_structure import structure
from tests.test_decision_graph_chain import _console as graph_console
root=Path(tempfile.mkdtemp(prefix='metis-browser-'))
console=OperationsConsole(root=root/'prose',source_store=root/'prose/sources',runtime=root/'prose/runtime')
accounts={key:console.create_account(username=key,password=PASSWORD,roles=roles)
          for key,roles in [('researcher',('researcher',)),('reviewer_a',('reviewer',)),('reviewer_b',('reviewer',))]}
def provider(url,headers,payload,timeout):
    blocks=json.loads(payload['input'][1]['content'])['source_blocks']
    block=next(b for b in blocks if 'systematische waarneming' in b['text'])
    def span(text):
        start=block['text'].index(text)
        return {'block_id':block['block_id'],'start':start,'end':start+len(text)}
    fields={key:{'span':None,'missing_reason':'not_applicable'} for key in FIELDS}
    for key,text in {'subject_span':'Een observatie','predicate_span':'is','type_evidence_spans':'systematische waarneming',
                     'defined_term':'observatie','definiens_span':'systematische waarneming van gedrag'}.items():
        fields[key]={'span':span(text),'missing_reason':None}
    proposal={'objects':[{'spans':[span(block['text'])],'proposed_object_type':'definition','recommendation_semantics':None,
                         'field_evidence':fields,'context_evidence':[]}],'relations':[],'abstain_reason':None}
    return {'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal)}]}]}
bind_pre_review_semantic_processing(console,environ={'METIS_PASSAGE_FORMATION_MODE':MODE,'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'fixture'},post_json=provider)
core='Een observatie is een systematische waarneming van gedrag. ' + 'Leg de waarneming letterlijk vast zonder ontbrekende informatie in te vullen. '*8
condition='Wanneer de oudere thuis woont, geldt deze afbakening.'
exception='Tenzij de oudere toestemming weigert.'
receipt=console.ingest(actor_id=accounts['researcher']['account_id'],filename='context.html',content_type='text/html',data=('<html><body><h1>Context</h1><p>'+condition+'</p><p>'+core+'</p><p>'+exception+'</p></body></html>').encode(),ingest_kind='new',title='Context browser',version='1',date='2026-10-02',live_url='',class_='richtlijn',family='test',named_reviewers=[accounts['reviewer_a']['account_id'],accounts['reviewer_b']['account_id']],review_policy={'contract':'explicit-review-v1','revision':1,'primary':accounts['reviewer_a']['account_id'],'assignments':[{'reviewer_id':accounts['reviewer_b']['account_id'],'participation':'required'}]})
sid=receipt['snapshot_id']
bind_detected_context(console,sid,accounts['reviewer_a']['account_id'])
obj=next(o for o in console.snapshot_objects(sid) if 'systematische waarneming' in o['content']['clean_text'])
graph, nodes, inventory=structure(root/'graph','single')
gc=graph_console(root/'graph'); graph_sid=gc.list_envelopes()[0]['snapshot_id']
# Fixture supplies an explicit reviewer reconstruction; it does not assert PDF geometry.
gc._envelopes[graph_sid]['decision_graph']=graph; gc._save_envelopes()
outcome=next(o for o in nodes if o['object_id']==graph['edges'][0]['to'])
app=create_console_app(console)
manifest={'first':f'/review?document={sid}&object={obj["object_id"]}','second':f'/review?document={sid}&object={obj["object_id"]}&task=second_review','paths':'/browser-paths','core':core.strip(),'condition':condition,'exception':exception,'password':PASSWORD,'first_user':accounts['reviewer_a']['username'],'second_user':accounts['reviewer_b']['username']}
@app.get('/browser-manifest')
def meta(): return JSONResponse(manifest)
@app.get('/browser-paths')
def paths():
    return HTMLResponse(_page('<main class="canvas"><article class="review-card">'+_knowledge_review_html(outcome,nodes)+_decision_paths_html(gc,graph_sid,outcome,nodes)+'</article></main>'))

@app.post('/browser-approve-first')
def approve_first():
    state=console.review_object(actor_id=accounts['reviewer_a']['account_id'],snapshot_id=sid,object_id=obj['object_id'],decision='approve',confirmed_object_type='definition',relation_review_ack=True)
    current=next(o for o in console.snapshot_objects(sid) if o['object_id']==obj['object_id'])
    exact=next(b for b in console.object_review_bindings(sid) if b['valid'] and b['object_id']==obj['object_id'])
    assert exact['object_version']==current['object_version']
    return JSONResponse({'object_version':current['object_version'],'canonical_hash':exact['canonical_object_hash']})
