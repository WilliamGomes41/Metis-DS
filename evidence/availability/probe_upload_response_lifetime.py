"""Real upload HTTP + real V3 worker with only the provider paused.

Hypotheses: H1 receipt waits for formation; H2 receipt follows durable source
storage; H3 the event loop is blocked. Concurrent health discriminates H3.
"""
import json,sys,tempfile,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,__import__('os').environ.get('METIS_PROBE_REPO', str(Path(__file__).resolve().parents[1]/'metis-review')))
from fastapi.testclient import TestClient
from src.review_closure_v1 import ReviewClosureConsole
from src.operations_console_app import create_console_app
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from tests.test_recommendation_context_v3 import response_for

with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);state=ReviewClosureConsole(root=root,source_store=root/'sources',runtime=root/'runtime')
 author=state.create_account(username='author',password='fixture-only',roles=('researcher',))
 reviewer=state.create_account(username='reviewer',password='fixture-only',roles=('reviewer',))
 entered=threading.Event();release=threading.Event();finished=threading.Event()
 def provider(_url,_headers,payload,_timeout):
  entered.set();assert release.wait(6),'HARNESS_RELEASE_TIMEOUT'
  data=json.loads(payload['input'][1]['content'])
  result=({'objects':[],'relations':[],'abstain_reason':'uncertain'} if data.get('selection_targets')
    else response_for(payload,'Gebruik geen zalf.'))
  return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(result)}]}]}
 bind_pre_review_semantic_processing(state,environ={'METIS_PASSAGE_FORMATION_MODE':'semantic-source-bound-v3','METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'fixture'},post_json=provider)
 with TestClient(create_console_app(state),base_url='https://testserver') as client,ThreadPoolExecutor(max_workers=2) as pool:
  client.post('/login',data={'username':'author','password':'fixture-only'})
  def upload():
   result=client.post('/ingest',data={'ingest_kind':'new','title':'Fixture','version':'1','date':'2026-10-08','class_':'richtlijn','family':'fixture','review_mode':'single','primary_reviewer':reviewer['account_id']},
    files={'file':('fixture.html',b'<html><body><p>Gebruik geen zalf.</p></body></html>','text/html')},follow_redirects=False)
   finished.set();return result
  future=pool.submit(upload);assert entered.wait(4)
  try:
   envelope=state.list_envelopes()[0]
   before={'snapshot_saved':bool(envelope['snapshot_id']),
    'attempt_state':envelope['processing_attempts'][-1]['state'],
    'eligibility':envelope['publication_eligibility'],
    'health_http':client.get('/health').status_code,
    'receipt_returned_while_provider_pending':finished.wait(.3)}
  finally:release.set()
  response=future.result(timeout=6)
  after=state.list_envelopes()[0]['processing_attempts'][-1]['state']
 print(json.dumps({'during_formation':before,'after_formation':{'http':response.status_code,'attempt_state':after}}),flush=True)
 assert before['snapshot_saved'] and before['health_http']==200
 assert response.status_code==200 and after=='succeeded','HARNESS_COMPLETION_CONTROL_FAILED'
 assert before['receipt_returned_while_provider_pending'],'UPLOAD_RECEIPT_WAITS_FOR_FULL_FORMATION'
