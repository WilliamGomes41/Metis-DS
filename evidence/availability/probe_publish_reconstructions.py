"""Synthetic V3 overview reproduction. Never reads or modifies production."""
import json
import os
import sys
import tempfile
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

REPO = Path(os.environ.get('METIS_PROBE_REPO', str(Path(__file__).resolve().parents[1]/'metis-review')))
sys.path[:0] = [str(REPO), str(REPO/'tests')]
from fastapi.testclient import TestClient
from src.review_closure_v1 import ReviewClosureConsole
from src.operations_console_app import create_console_app
from src.document_status_ui_v1 import install_document_status_ui
from src.publish_readiness_ui_v1 import install_publish_readiness_ui
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from tests.test_recommendation_context_v3 import response_for
from src.source_accountability_v1 import is_source_record
import src.semantic_passage_v1 as semantic
import src.knowledge_materialisation_v1 as materialisation

count = int(sys.argv[1]) if len(sys.argv)>1 else 20
with tempfile.TemporaryDirectory(prefix='metis-overview-probe-') as folder:
    root=Path(folder)
    console=ReviewClosureConsole(root=root,source_store=root/'sources',runtime=root/'runtime')
    author=console.create_account(username='author',password='fixture-only',roles=('researcher',))
    reviewer=console.create_account(username='reviewer',password='fixture-only',roles=('reviewer','publisher'))
    core='Gebruik geen zalf.'
    texts=[core,*[f'Bronpassage {i} bevat aanvullende informatie voor menselijke beoordeling.' for i in range(count)]]
    def provider(_url,_headers,payload,_timeout):
        data=json.loads(payload['input'][1]['content'])
        if not data.get('selection_targets') and any(core in b['text'] for b in data['source_blocks']):
            proposal=response_for(payload,core)
        else:
            proposal={'objects':[],'relations':[],'abstain_reason':'uncertain'}
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal)}]}]}
    bind_pre_review_semantic_processing(console,environ={
        'METIS_PASSAGE_FORMATION_MODE':'semantic-source-bound-v3',
        'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'fixture'},post_json=provider)
    sid=console.ingest(actor_id=author['account_id'],filename='source.html',content_type='text/html',
        data=('<html><body>'+''.join(f'<p>{text}</p>' for text in texts)+'</body></html>').encode(),
        ingest_kind='new',title='V3 overview proof',version='1',date='2026-10-08',live_url='',
        class_='richtlijn',family='fixture',named_reviewers=[reviewer['account_id']])['snapshot_id']
    objects=console.snapshot_objects(sid)
    source_count=sum(is_source_record(obj) for obj in objects)
    assert source_count==count,(source_count,count)
    console.list_document_lifecycle_statuses=lambda:{sid:{
        'workflow_status':'in_review','release_status':'none','serving_status':'inactive','presentation_status':'in_review'}}
    app=create_console_app(console);install_document_status_ui(app,console);install_publish_readiness_ui(app,console)
    client=TestClient(app,base_url='https://testserver')
    assert client.post('/login',data={'username':'reviewer','password':'fixture-only'},follow_redirects=False).status_code==303
    original=semantic._reconstructed_blocks
    calls=Counter()
    cached={}
    def measured(rows):
        rows=list(rows)
        if '--cache-full' in sys.argv and cached.get('input')==rows:
            return cached['blocks']
        calls[sys._getframe(1).f_code.co_name]+=1
        result=original(rows)
        if '--cache-full' in sys.argv:
            cached.update(input=deepcopy(rows),blocks=result)
        return result
    with patch.object(semantic,'_reconstructed_blocks',measured), patch.object(materialisation,'_reconstructed_blocks',measured):
        started=time.perf_counter();response=client.get('/publish');elapsed=time.perf_counter()-started
    print(json.dumps({'route':'/publish','source_records':source_count,'http':response.status_code,
        'seconds':round(elapsed,3),'full_source_reconstructions':dict(calls)}),flush=True)
    assert response.status_code==200
    assert sum(calls.values())<=2,'RECONSTRUCTION_GROWS_WITH_SOURCE_RECORDS'
