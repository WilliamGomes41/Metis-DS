"""External native KO5 rollback evidence; no production-code edits."""
import argparse, json, os, subprocess, sys
from pathlib import Path
from copy import deepcopy
import psycopg
from src.g2_source_store import AzureBlobSourceStore
from src.integrity_kernel import schema_errors, stamp_canonical_hashes
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from tests.test_a10_source_cache_repair import DiskBlobTransport
from tests.complete_workflow_support import complete_console
from tests.postgres_support import database, install_schema
from tests.test_vsa_publish_document_v1 import _ready_console, canonical_store
from tests.test_v225_beslisboom_path import _ingest_boom
from tests.semantic_fixture_support import install_fixture_history
from src.review.ko_transitions_v1 import command_assessment
from tests.ko_review_fixture_support import affirmative_assessment
from src.review.knowledge_object_state_v1 import snapshot_ko_states
from tests.test_review_command_bounded_http_v1 import physical_state

TABLES=['workflow.documents','workflow.document_objects','workflow.publish_authorizations','workflow.review_events','canonical_object_versions','canonical_object_sources','publication_releases','publication_release_items','publication_registry','audit_events']
def physical(config):
    with psycopg.connect(config.dsn) as con:
        return {table: sorted([json.dumps(r[0], sort_keys=True,default=str) for r in con.execute('SELECT jsonb_build_object(\'row\',to_jsonb(t),\'ctid\',t.ctid::text,\'xmin\',t.xmin::text) FROM '+table+' t')]) for table in TABLES}
def comparable(state):
    result=deepcopy(state)
    # Existing canonical publication reconciliation rewrites published envelope rows at startup.
    result['workflow.documents']=sorted(json.dumps({k:v for k,v in json.loads(row)['row'].items() if k not in ('revision','updated_at')},sort_keys=True) for row in result['workflow.documents'])
    return result

def startup_delta(before,after,cfg):
    changes=[]
    b={json.loads(r)['row']['snapshot_id']:json.loads(r) for r in before['workflow.documents']}
    a={json.loads(r)['row']['snapshot_id']:json.loads(r) for r in after['workflow.documents']}
    assert a.keys()==b.keys()
    for sid,old in b.items():
        new=a[sid]
        if new==old: continue
        fields=[k for k in old['row'] if old['row'][k]!=new['row'][k]]
        assert sid==cfg['sids'][0], ('unexpected startup write',sid,fields)
        assert set(fields)=={'revision','updated_at'},fields
        assert new['row']['revision']==old['row']['revision']+1
        assert new['ctid']!=old['ctid'] and new['xmin']!=old['xmin']
        changes.append({'sid':sid,'fields':fields,'revision_increment':1})
    assert len(changes)==1,changes
    return changes

def view(console, sids):
    result={}
    for sid in sids:
        objs=console.snapshot_objects(sid)
        result[sid]={'objects':objs,'bindings':console.object_review_bindings(sid),'states':snapshot_ko_states(console,console._envelope(sid)), 'readiness':console.publication_readiness(sid), 'schema_errors':{r['object_id']+':'+str(r['object_version']):schema_errors(r,console.schema_path) for r in console._load_objects(sid)}}
    return result

def probe(cfg, output):
    config=PostgresCanonicalConfig(dsn=cfg['dsn']); before=physical(config)
    source=AzureBlobSourceStore(blob_service_client=DiskBlobTransport(Path(cfg['root'])/'immutable'))
    console=complete_console(Path(cfg['root']),config,immutable_source_store=source)
    result={'before':before,'view':view(console,cfg['sids']),'badges':{actor:console.waiting_task_counts(actor) for actor in cfg['ids']},'after':physical(config)}
    result['read_only']=comparable(result['before'])==comparable(result['after'])
    result['startup_physical_document_changes']=startup_delta(result['before'],result['after'],cfg)
    Path(output).write_text(json.dumps(result,default=str,indent=2))
    assert result['read_only'], 'startup/read physically mutated authoritative rows'
    assert all(not errs for sid in result['view'].values() for errs in sid['schema_errors'].values()), 'old-schema validation errors'

def act(cfg,output):
    config=PostgresCanonicalConfig(dsn=cfg['dsn'])
    root=Path(cfg['root'])
    source=AzureBlobSourceStore(blob_service_client=DiskBlobTransport(root/'immutable'))
    console=complete_console(root,config,immutable_source_store=source)
    before=physical(config)
    responses=[]
    from src.review.review_duty_v1 import exact_current_approver_ids,review_stage
    for sid,oid in [(cfg['boom'],cfg['target']),(cfg['ordinary'],cfg['ordinary_target'])]:
        previous=console._current_object(sid,oid)
        assert review_stage(previous,review_path='boom' if sid==cfg['boom'] else 'richtlijn',bindings=console.object_review_bindings(sid),fragments=console.review_source_fragments(sid))=='second_review'
        response=console.approve_second_review(actor_id=cfg['ids'][1],snapshot_id=sid,object_id=oid,expected_revision=console.objects_revision(sid),assessment=affirmative_assessment(),evidence_not_applicable=True)
        assert response['object_version']==previous['object_version']
        assert set(exact_current_approver_ids(response,console.object_review_bindings(sid)))==set(cfg['ids'])
        assert not schema_errors(response,console.schema_path)
        responses.append(response)
    after=physical(config)
    for table in TABLES[4:]: assert before[table]==after[table], ('canonical mutation',table)
    def published(rows):
        return [r for r in rows if json.loads(r)['row'].get('snapshot_id')==cfg['sids'][0]]
    for table in TABLES[:4]: assert published(before[table])==published(after[table]),('published history mutation',table)
    result={'before':before,'after':after,'responses':responses,'view':view(console,cfg['sids'])}
    Path(output).write_text(json.dumps(result,default=str,indent=2))

def run(args):
    with database(os.environ['METIS_TEST_POSTGRES_DSN']) as config:
        install_schema(config.dsn)
        root=Path(args.output)/'runtime'; root.mkdir(parents=True,exist_ok=True)
        source=AzureBlobSourceStore(blob_service_client=DiskBlobTransport(root/'immutable'))
        console,people,receipt=_ready_console(root,config,canonical_store(config),source)
        sid=receipt['snapshot_id']; published=console.publish(actor_id=people['publisher']['account_id'],snapshot_id=sid)
        assert published['status']=='PASS'
        second=console.create_account(username='independent.second',password='fixture-only',roles=('reviewer',))
        ids=[people['reviewer']['account_id'],second['account_id']]
        boom=_ingest_boom(console,people,named_reviewers=ids)['snapshot_id']
        from src.review.review_duty_v1 import authoritative_review_type
        rows=console._load_objects(boom); target=next(r for r in rows if authoritative_review_type(r)=='node')
        target['risk']['risk_level']='high'; target['risk']['requires_second_review']=True
        # Fixture setup establishes hash-bound high risk before the actual native review command.
        target['governance']['second_review']['required']=True
        stamp_canonical_hashes(target); install_fixture_history(console,boom,rows)
        prior_version=target['object_version']
        console.review_object(actor_id=ids[0],snapshot_id=boom,object_id=target['object_id'],decision='approve',confirmed_object_type='node',assessment=affirmative_assessment(),evidence_not_applicable=True)
        current=next(r for r in console.snapshot_objects(boom) if r['object_id']==target['object_id'])
        from tests.semantic_fixture_support import bind_fixture_selections
        text='Oedeem is een ophoping van vocht.'
        bind_fixture_selections(console,[(text,'definition')])
        ordinary=console.ingest(actor_id=people['researcher']['account_id'],filename='high-risk.html',content_type='text/html',data=('<h1>Begrippen</h1><p>'+text+'</p>').encode(),ingest_kind='new',title='High-risk ordinary',version='1.0',date='2026-11-07',live_url='',class_='richtlijn',family='rollback-highrisk',named_reviewers=ids)['snapshot_id']
        ordinary_rows=console._load_objects(ordinary)
        from src.review.knowledge_path_v1 import content_reviewable
        ordinary_target=next(r for r in ordinary_rows if content_reviewable(r))
        ordinary_target['risk']['risk_level']='high';ordinary_target['risk']['requires_second_review']=True
        ordinary_target['governance']['second_review']['required']=True
        stamp_canonical_hashes(ordinary_target);install_fixture_history(console,ordinary,ordinary_rows)
        console.review_object(actor_id=ids[0],snapshot_id=ordinary,object_id=ordinary_target['object_id'],decision='approve',confirmed_object_type='definition',assessment=affirmative_assessment(),evidence_not_applicable=True)
        cfg={'root':str(root),'dsn':config.dsn,'sids':[sid,boom,ordinary],'ordinary':ordinary,'ordinary_target':ordinary_target['object_id'],'boom':boom,'target':target['object_id'],'ids':ids,'prior_version':prior_version,'version':current['object_version']}
        Path(args.output,'seed.json').write_text(json.dumps(cfg))
        for phase in ('open-second','closed-second'):
            if phase=='closed-second' and args.old_act:
                old_output=str(Path(args.output,'old-action.json'))
                completed=subprocess.run([sys.executable,__file__,'act',str(Path(args.output,'seed.json')),old_output],cwd=args.old_act,env={**os.environ,'PYTHONPATH':args.old_act},text=True,capture_output=True,timeout=120)
                Path(args.output,'old-action.log').write_text(completed.stdout+completed.stderr)
                assert completed.returncode==0, completed.stderr[-5000:]
            if phase=='closed-second' and not args.old_act:
                from tests.production_support import restart_production
                console=restart_production(console)
                for doc,oid in [(boom,target['object_id']),(ordinary,ordinary_target['object_id'])]:
                    console.approve_second_review(actor_id=ids[1],snapshot_id=doc,object_id=oid,expected_revision=console.objects_revision(doc),assessment=affirmative_assessment(),evidence_not_applicable=True)
            reference=physical(config)
            reference_view=None
            for name,checkout in [('head',args.head),('base',args.base),*([('ko4',args.ko4)] if args.ko4 else [])]:
                env={**os.environ,'PYTHONPATH':checkout}
                output=str(Path(args.output,phase+'-'+name+'.json'))
                cmd=[sys.executable,__file__,'probe',str(Path(args.output,'seed.json')),output]
                completed=subprocess.run(cmd,cwd=checkout,env=env,text=True,capture_output=True,timeout=120)
                Path(args.output,phase+'-'+name+'.log').write_text(completed.stdout+completed.stderr)
                assert completed.returncode==0, name+': '+completed.stderr[-5000:]
                result=json.loads(Path(output).read_text())
                if reference_view is None: reference_view=result['view']
                else: assert result['view']==reference_view, name+': changed states/readiness/bindings/schema or objects'
                assert comparable(result['before'])==comparable(reference) and comparable(result['after'])==comparable(reference)
        print(json.dumps({'status':'PASS','output':args.output,'seed':cfg},default=str))

if __name__=='__main__':
    if sys.argv[1]=='probe': probe(json.loads(Path(sys.argv[2]).read_text()),sys.argv[3])
    elif sys.argv[1]=='act': act(json.loads(Path(sys.argv[2]).read_text()),sys.argv[3])
    else:
        p=argparse.ArgumentParser();p.add_argument('--head',required=True);p.add_argument('--base',required=True);p.add_argument('--ko4');p.add_argument('--old-act');p.add_argument('--output',required=True);run(p.parse_args())
