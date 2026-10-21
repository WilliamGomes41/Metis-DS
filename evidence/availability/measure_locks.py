"""Measure actual lock hold in a synthetic installed successor route chain."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import perf_counter
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from tests.test_availability_repair import state,accounts,installed_app,login,start,drain
from tests.semantic_fixture_support import bind_fixture_selections

with TemporaryDirectory() as folder:
 console=state(Path(folder));actor,_=accounts(console);bind_fixture_selections(console)
 sid=console.ingest(actor_id=actor,filename='fixture.html',data=b'<html><body><p>Een observatie is een systematische waarneming.</p></body></html>',
  content_type='text/html',ingest_kind='new',title='Fixture',version='1',date='2026-10-08',live_url='',class_='richtlijn',family='fixture',
  named_reviewers=[],review_policy={'contract':'explicit-review-v1','revision':1,'primary':actor,'assignments':[]})['snapshot_id']
 lock=console._store_write_lock;durations=[]
 @contextmanager
 def measured():
  with lock():
   began=perf_counter()
   try:yield
   finally:durations.append(perf_counter()-began)
 console._store_write_lock=measured
 extract=console._fragments_and_spec;entered=Event();release=Event();outside=[]
 def paused(*args,**kwargs):
  outside.append(console._store_lock_depth==0);entered.set();assert release.wait(5)
  return extract(*args,**kwargs)
 console._fragments_and_spec=paused;app=installed_app(console)
 with TestClient(app,base_url='https://testserver') as client,ThreadPoolExecutor(2) as pool:
  login(client)
  receipt=client.post('/review/successor',data={'document':sid,'expected_revision':console.objects_revision(sid),
   'command_id':'measure','reason':'Fixture proof','primary':actor,'policy_revision':'2','new_class':'richtlijn'},follow_redirects=False)
  assert receipt.status_code==303
  sid2=receipt.headers['location'].split('document=')[1]
  try:
   assert start(client,console,sid2).status_code==303;assert entered.wait(3)
   began=perf_counter()
   assert pool.submit(client.get,'/health').result(timeout=1).status_code==200
   assert pool.submit(console.create_account,username='independent',password='fixture-only',roles=('researcher',)).result(timeout=1)
   independent=perf_counter()-began
  finally:release.set();drain(client,app)
 print(json.dumps({'lock_entries':len(durations),'max_hold_seconds':round(max(durations),6),
  'sum_hold_seconds_including_nested':round(sum(durations),6),'extract_without_lock':outside,
  'independent_health_and_write_seconds':round(independent,6),'successor_attempt':console.processing_status(sid2)['state']}))
 assert outside==[True] and console.processing_status(sid2)['state']=='succeeded'
