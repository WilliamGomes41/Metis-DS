"""Actual V3 ingest -> HTTP source-unit repair -> source validation / review."""
import os
import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,__import__('os').environ.get('METIS_PROBE_REPO', str(Path(__file__).resolve().parents[2])))
from fastapi.testclient import TestClient
from src.review_closure_v1 import ReviewClosureConsole
from src.operations_console_app import create_console_app
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.deterministic_review_repair_v1 import install_deterministic_review_repair_routes
from src.knowledge_materialisation_v1 import validate_materialised_candidate
from tests.test_recommendation_context_v3 import response_for

def scenario(expand, supply_selection=False):
 with tempfile.TemporaryDirectory() as folder:
  p=Path(folder);s=ReviewClosureConsole(root=p,source_store=p/'sources',runtime=p/'runtime')
  a=s.create_account(username='author',password='fixture-only',roles=('researcher',));r=s.create_account(username='reviewer',password='fixture-only',roles=('reviewer',))
  def provider(_url,_headers,payload,_timeout):
   data=json.loads(payload['input'][1]['content'])
   proposal={'objects':[],'relations':[],'abstain_reason':'uncertain'} if data.get('selection_targets') else response_for(payload,'Gebruik geen zalf.')
   return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal)}]}]}
  bind_pre_review_semantic_processing(s,environ={'METIS_PASSAGE_FORMATION_MODE':'semantic-source-bound-v3','METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'fixture'},post_json=provider)
  sid=s.ingest(actor_id=a['account_id'],filename='fixture.html',data=b'<html><body><p>Gebruik geen zalf. Bespreek de opties.</p></body></html>',content_type='text/html',ingest_kind='new',title='Fixture',version='1.0',date='2026-10-08',live_url='',class_='richtlijn',family='fixture',named_reviewers=[r['account_id']])['snapshot_id']
  obj=next(o for o in s.snapshot_objects(sid) if o['content']['clean_text']=='Gebruik geen zalf.')
  units=s.source_units(snapshot_id=sid,object_id=obj['object_id']);assert len(units)==2
  before_spans=obj['metadata']['semantic_passage']['spans'];before_gate=obj['metadata']['admission']['gate_result']
  from src.operations_console_v1 import OperationsConsole
  from src.semantic_passage_v1 import semantic_source_blocks
  original=OperationsConsole.correct_object
  def pass_selected_source(console,**kw):
   if supply_selection:
    block=next(b for b in semantic_source_blocks(console.review_source_fragments(sid)) if b['text']=='Gebruik geen zalf. Bespreek de opties.')
    kw['materialisation_decision']={'decision_kind':'semantic_selection','selection_origin':'proposal_selected','spans':[{'block_id':block['block_id'],'start':0,'end':len(block['text'])}],'source_text':block['text']}
   return original(console,**kw)
  OperationsConsole.correct_object=pass_selected_source
  app=create_console_app(s);install_deterministic_review_repair_routes(app,s)
  with TestClient(app,base_url='https://testserver',raise_server_exceptions=False) as c:
   c.post('/login',data={'username':'reviewer','password':'fixture-only'})
   response=c.post('/review/resolve',data={'snapshot_id':sid,'object_id':obj['object_id'],'snapshot_revision':s.objects_revision(sid),'suitability':'mist_context','comment':'Volledige bronzinnen selecteren.','repair_kind':'source_units','source_unit_ids':[u['unit_id'] for u in (units if expand else units[:1])]},follow_redirects=False)
   OperationsConsole.correct_object=original
   current=s._current_object(sid,obj['object_id']);validation='valid'
   try:validate_materialised_candidate(current,fragments=s.review_source_fragments(sid))
   except ValueError as e:validation=str(e)
   return {'http':response.status_code,'initial_gate':before_gate,'text':current['content']['clean_text'],'spans_changed':before_spans!=current['metadata']['semantic_passage']['spans'],'validation':validation,'final_gate':current['metadata'].get('admission',{}).get('gate_result'),'gate_reasons':current['metadata'].get('admission',{}).get('reason_codes'),'state':current['governance']['validation_status']}
control=scenario(False);expanded=scenario(True);intervention=scenario(True,True)
print(json.dumps({'same_source_units':control,'expanded_source_units':expanded,'selected_spans_passed_to_existing_materialiser':intervention}),flush=True)
assert control['validation']=='valid' and control['http']==303
assert expanded['http']==303
assert intervention['http']==303 and intervention['validation']=='valid'
assert expanded['validation']=='valid','REPAIR_SUCCESS_STORES_STALE_SOURCE_SPANS'
