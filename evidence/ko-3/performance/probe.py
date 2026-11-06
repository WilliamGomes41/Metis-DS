"""KO3: real direct readiness and selected production HTTP, read-only fixture."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib
import json
import os
import socket
import ssl
import subprocess
import sys
import time

import httpx
import psycopg
from psycopg import sql
from tests.semantic_fixture_support import bind_fixture_selections

ROOT=Path(__file__).resolve().parents[1]


def db_fingerprint(dsn):
    """Parent-only setup/final proof; authorization login sessions excluded explicitly."""
    digest={}
    with psycopg.connect(dsn) as con:
        tables=con.execute("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE c.relkind='r' AND n.nspname IN ('workflow','public') ORDER BY 1,2").fetchall()
        for schema,table in tables:
            if (schema,table)==('workflow','sessions'):
                continue
            h=hashlib.sha256();count=0
            for row in con.execute(sql.SQL('SELECT to_jsonb(t)::text FROM {}.{} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(schema),sql.Identifier(table))):
                h.update(row[0].encode());h.update(b'\n');count+=1
            digest[f'{schema}.{table}']={'rows':count,'sha256':h.hexdigest()}
    return digest


def source_fingerprint(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*'))if p.is_file()}


class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.blockers=set();self.objects={};self.selected=set();self.states=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'data-blocker-code'in attrs:self.blockers.add(attrs['data-blocker-code'])
        if 'data-readiness-object'in attrs:self.objects[attrs['data-readiness-object']]=attrs.get('data-ko-state')
        if 'data-publish-document'in attrs:self.selected.add(attrs['data-publish-document'])
        if 'data-publication-state'in attrs:self.states.add(attrs['data-publication-state'])


def normalized(value,identities):
    if isinstance(value,dict):return {k:normalized(v,identities)for k,v in value.items()}
    if isinstance(value,list):return [normalized(v,identities)for v in value]
    if isinstance(value,str):
        for key,replacement in identities.items():value=value.replace(key,replacement)
    return value


def test_perf(tmp_path,production_console,request):
    head=os.environ.get('KO3_HEAD')=='1';side=os.environ['KO3_SIDE'];round_id=int(os.environ['KO3_ROUND'])
    out=Path(os.environ['KO3_OUT']);prefix=f'{side}-{round_id}';sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    console=production_console(root=tmp_path,processing_binder=bind_fixture_selections)
    author=console.create_account(username='author',password='fixture-only',roles=('researcher',))
    reviewer=console.create_account(username='reviewer',password='fixture-only',roles=('reviewer',))
    publisher=console.create_account(username='publisher',password='fixture-only',roles=('publisher',))
    texts=[f'Begrip {i} is een beschrijving van een afzonderlijke waarneming in de zorg. De verpleegkundige legt waarneming {i} vast.'for i in range(899)]
    bind_fixture_selections(console,[(text,'definition')for text in texts[::9][:92]])
    sid=console.ingest(actor_id=author['account_id'],filename='source.html',content_type='text/html',
        data=('<html><body><h1>Richtlijn</h1>'+''.join(f'<p>{t}</p>'for t in texts)+'</body></html>').encode(),
        ingest_kind='new',title='KO3 performance synthetic',version='1.0',date='2026-11-06',live_url='',
        class_='richtlijn',family='ko3-perf',named_reviewers=[reviewer['account_id']])['snapshot_id']
    objects=console.snapshot_objects(sid,include_blocked=True)
    assert len(console.review_source_fragments(sid))==900, 'Fixture must contain exactly900raw fragments'
    candidates=[o for o in objects if o.get('proposed_object_type')=='definition'];assert len(candidates)==92
    identities={sid:'@snapshot',author['account_id']:'@author',reviewer['account_id']:'@reviewer',publisher['account_id']:'@publisher'}
    envelope=console._envelope(sid)
    for key in ['source_id','document_id']:
        if envelope.get(key):identities[envelope[key]]='@'+key
    for obj in objects:identities[obj['object_id']]='@object:'+str(obj.get('proposed_object_type')or obj.get('object_type'))+':'+str(obj.get('content',{}).get('clean_text',''))
    # Initial state is captured in setup, before any child/timed path; no proof SQL between timed paths.
    before_db=db_fingerprint(console.workflow_document_store.config.dsn)
    before_source=source_fingerprint(Path(console.source_store))
    config={'root':str(console.root),'runtime':str(console.runtime),'source_store':str(console.source_store),
        'dsn':console.workflow_document_store.config.dsn,'publisher':publisher['account_id'],'snapshot':sid,'sha':sha}
    direct_files=[]
    for sample in range(1,4):
        output=out/f'{prefix}-direct-{sample}.json';direct_files.append(output)
        cfg=tmp_path/f'direct-{sample}.json';cfg.write_text(json.dumps({**config,'mode':'consider','output':str(output)}))
        with(out/f'{prefix}-direct-{sample}.log').open('w')as log:
            done=subprocess.run([sys.executable,'/tmp/ko3-perf/server.py',str(cfg)],cwd=ROOT,
                env={**os.environ,'PYTHONPATH':str(ROOT)},stdout=log,stderr=log)
        assert done.returncode==0
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    metadata=out/f'{prefix}-http-server.json';cfg=tmp_path/'http-config.json'
    cfg.write_text(json.dumps({**config,'mode':'http','port':port,'metadata':str(metadata)}))
    log_path=out/f'{prefix}-http-server.log';log=log_path.open('w')
    child=subprocess.Popen([sys.executable,'/tmp/ko3-perf/server.py',str(cfg)],cwd=ROOT,
        env={**os.environ,'PYTHONPATH':str(ROOT)},stdout=log,stderr=log)
    def stop():
        if child.poll()is None:
            child.terminate()
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
        log.close()
    request.addfinalizer(stop)
    deadline=time.monotonic()+30
    while True:
        assert child.poll()is None,log_path.read_text()[-1000:]
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):break
        except OSError:
            assert time.monotonic()<deadline;time.sleep(.05)
    client=httpx.Client(base_url=f'https://127.0.0.1:{port}',verify=ssl.create_default_context(cafile='/tmp/ko3-perf/server.crt'),timeout=60,trust_env=False)
    request.addfinalizer(client.close)
    assert client.post('/login',data={'username':'publisher','password':'fixture-only'},follow_redirects=False).status_code==303
    pages=[];http=[]
    for sample in range(1,4):
        started=time.perf_counter();response=client.get('/publish',params={'document':sid});wall_ms=(time.perf_counter()-started)*1000
        pages.append(response);http.append({'sample':sample,'wall_ms':wall_ms,'status':response.status_code,
            'request_id':response.headers['x-metis-request-id'],'response_bytes':len(response.content)})
    client.close()
    (out/f'{prefix}-http-transcript.json').write_text(json.dumps(http,indent=2))
    stop()  # Completion log may follow body delivery; parse only finalized logs.
    records={}
    for line in log_path.read_text().splitlines():
        if line.startswith('metis_diagnostic '):
            row=json.loads(line[len('metis_diagnostic '):])
            if row.get('event')=='request_finished':
                assert row['request_id']not in records;records[row['request_id']]=row
    # All proof IO/JSON parsing starts after all direct and HTTP timed paths.
    assert db_fingerprint(console.workflow_document_store.config.dsn)==before_db
    assert source_fingerprint(Path(console.source_store))==before_source
    direct=[json.loads(path.read_text())for path in direct_files]
    assert all(row['result']==row['attribution_result']for row in direct)
    compat=[]
    legacy_keys=[]
    for row in direct:
        value=row['result'];assert 'readiness_authority_unavailable'not in value.get('blockers',[])
        assert value['publish_allowed']is False and value['publication_ready']is False
        assert value['review_required_object_count']==92
        assert {'review_work_incomplete','source_passage_review_incomplete'}<=set(value['blockers'])
        assert value['publishable_object_count']==0
        if head:
            projected=value['object_readiness'];by_id={r['object_id']:r for r in projected}
            assert len(by_id)==len(projected)
            for obj in candidates:
                assert by_id[obj['object_id']]['state'] and by_id[obj['object_id']]['blockers']
        legacy={k:v for k,v in value.items()if k!='object_readiness'}
        legacy_keys.append(sorted(legacy))
        signature={k:v for k,v in legacy.items()if isinstance(v,(bool,int,float))or k in {'state','g2','blockers'}or k.endswith('_blockers')or k.endswith('_counts')}
        for key,item in signature.items():
            if isinstance(item,list):signature[key]=sorted(item)
        compat.append(normalized(signature,identities))
    assert compat[0]==compat[1]==compat[2]
    assert legacy_keys[0]==legacy_keys[1]==legacy_keys[2]
    with psycopg.connect(console.workflow_document_store.config.dsn)as con:
        sessions=con.execute('SELECT account_id,revoked_at FROM workflow.sessions').fetchall()
    assert sessions==[(publisher['account_id'],None)], 'Only the deliberate publisher login may create a session'
    for response,metric in zip(pages,http):
        assert metric['status']==200
        row=records[metric['request_id']];assert row['status']==200 and row['outcome']=='completed'and not row.get('error')
        metric.update(server_ms=row['elapsed_ms'],db_queries=row.get('db',{}).get('db_queries',0),
            db_json_bytes=row.get('db',{}).get('db_json_bytes',0),physical_connections=row.get('db',{}).get('db_connections',0),request=row)
        page=Page();page.feed(response.text)
        assert sid in page.selected and 'blocked'in page.states
        assert {'review_work_incomplete','source_passage_review_incomplete'}<=page.blockers<=set(direct[0]['result']['blockers'])
        if head:
            assert all(obj['object_id']in page.objects and page.objects[obj['object_id']]for obj in candidates)
    metas=[row['metadata']for row in direct]+[json.loads(metadata.read_text())]
    assert len({m['pid']for m in metas})==4
    for meta in metas:
        assert meta['pid']!=os.getpid()and meta['parent_pid']==os.getpid()and meta['sha']==sha
        assert meta['gc_enabled']and meta['gc_threshold']==[2000,10,10]
    result={'method_version':1,'side':side,'head':head,'round':round_id,'sha':sha,
        'fixture':{'source_paragraphs':899,'raw_source_fragments':900,'definition_candidates':92,'objects':len(objects)},
        'consider':[{'sample':i+1,'wall_ms':r['wall_ms'],'attribution_only':r['attribution_only'],'metadata':r['metadata']}for i,r in enumerate(direct)],
        'http':http,'compatibility_result':compat[0],'existing_result_keys':legacy_keys[0],
        'head_object_rows':len(direct[0]['result'].get('object_readiness',[])),
        'proofs':{'database_unchanged':True,'source_files_unchanged':True,'existing_results_stable':True,
            'real_consider_calls':3,'actual_http_pages':3,'head_rows_verified':head,'fresh_children':4},
        'http_child_exit':child.returncode,'http_forced_reap':child.returncode==-9,
        'attribution_note':'Separate untimed second call in each direct child, not counters of measured first call.',
        'immutability_exclusion':'Only workflow.sessions excluded: actual publisher login intentionally creates one session outside timed GETs.'}
    (out/f'{prefix}.json').write_text(json.dumps(result,indent=2))
