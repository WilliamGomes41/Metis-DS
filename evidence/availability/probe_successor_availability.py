"""Actual HTTP routes; deterministic pause substitutes only extraction latency."""
import asyncio,json,sys,tempfile,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,__import__('os').environ.get('METIS_PROBE_REPO', str(Path(__file__).resolve().parents[1]/'metis-review')))
from fastapi.testclient import TestClient
from src.review_closure_v1 import ReviewClosureConsole
from src.operations_console_app import create_console_app
from src.review_policy_v1 import CONTRACT
from tests.semantic_fixture_support import bind_fixture_selections

def scenario(successor):
 with tempfile.TemporaryDirectory() as folder:
  root=Path(folder);s=ReviewClosureConsole(root=root,source_store=root/'sources',runtime=root/'runtime')
  a=s.create_account(username='author',password='fixture-only',roles=('researcher','reviewer','publisher'))
  aid=a['account_id'];bind_fixture_selections(s)
  policy={'contract':CONTRACT,'revision':1,'primary':aid,'assignments':[]}
  source=b'<html><body><p>Een observatie is een systematische waarneming.</p></body></html>'
  args=dict(actor_id=aid,filename='fixture.html',data=source,content_type='text/html',ingest_kind='new',title='Fixture',version='1.0',date='2026-10-08',live_url='',class_='richtlijn',family='fixture',named_reviewers=[],review_policy=policy)
  sid=s.ingest(**args)['snapshot_id']
  entered=threading.Event();release=threading.Event();original=s._fragments_and_spec;observations={}
  def paused(*a,**k):
   try: asyncio.get_running_loop();observations['extract_on_event_loop']=True
   except RuntimeError: observations['extract_on_event_loop']=False
   observations['store_lock_held']=s._store_lock_depth>0
   entered.set();assert release.wait(4),'HARNESS_RELEASE_TIMEOUT'
   return original(*a,**k)
  s._fragments_and_spec=paused
  with TestClient(create_console_app(s),base_url='https://testserver') as client,ThreadPoolExecutor(max_workers=3) as pool:
   client.post('/login',data={'username':'author','password':'fixture-only'})
   if successor:
    future=pool.submit(client.post,'/review/successor',data={'document':sid,'expected_revision':s.objects_revision(sid),'command_id':'successor','reason':'Fixture audit','primary':aid,'policy_revision':'2','new_class':'richtlijn'},follow_redirects=False)
   else:
    future=pool.submit(client.post,'/ingest',data={'ingest_kind':'new','title':'Independent','version':'1.0','date':'2026-10-08','class_':'richtlijn','family':'fixture','review_mode':'single','primary_reviewer':aid},files={'file':('fixture.html',source,'text/html')})
   assert entered.wait(4)
   health_started=threading.Event();health_finished=threading.Event()
   def health():
    health_started.set();r=client.get('/health');health_finished.set();return r
   h=pool.submit(health);assert health_started.wait(1)
   completed=health_finished.wait(.35)
   observations['health_responded_during_processing']=completed
   release.set()
   observations['operation_http']=future.result(timeout=4).status_code
   observations['health_http']=h.result(timeout=4).status_code
  return observations
control=scenario(False);actual=scenario(True)
print(json.dumps({'ordinary_ingest':control,'successor':actual}),flush=True)
assert control['health_responded_during_processing'] and not control['extract_on_event_loop']
assert actual['operation_http']==303
assert actual['health_responded_during_processing'],'SUCCESSOR_BLOCKS_HEALTH_EVENT_LOOP'
assert not actual['store_lock_held'],'SUCCESSOR_HOLDS_GLOBAL_WRITE_LOCK_DURING_EXTRACTION'
