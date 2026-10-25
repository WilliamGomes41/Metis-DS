"""Native PostgreSQL proposal-validation benchmark with a deterministic model fixture."""
import argparse
import atexit
import json
import os
from pathlib import Path
import sys
import shutil
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.postgres_support import database,install_schema
from tests.production_support import production_application
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.source_bound_fields_v3 import MODE
from tests.test_recommendation_context_v3 import response_for
import src.semantic_passage_v1 as semantic

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='metis-validation-scaling-'))
    atexit.register(shutil.rmtree,work)
    observed=[]
    project=semantic._project_semantic_selection
    def counted(*args,**kwargs):
        started=time.perf_counter()
        try:
            return project(*args,**kwargs)
        finally:
            observed.append({'objects':len(kwargs['proposal']['objects']),'seconds':time.perf_counter()-started})
    semantic._project_semantic_selection=counted
    def provider(_url,_headers,payload,_timeout):
        text=json.loads(payload['input'][1]['content'])['source_blocks'][0]['text']
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(response_for(payload,text))}]}]}
    def bind(console):
        bind_pre_review_semantic_processing(console,environ={'METIS_PASSAGE_FORMATION_MODE':MODE,
            'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'test'},post_json=provider)
    report=[]
    with database(os.environ['METIS_TEST_POSTGRES_DSN']) as config:
        install_schema(config.dsn)
        console=production_application(work/'validation-runtime',config,processing_binder=bind).state.operations_kernel
        actor=console.create_account(username='validation-fixture',password='fixture-password',roles=('researcher',))['account_id']
        reviewer=console.create_account(username='validation-reviewer',password='fixture-password',roles=('reviewer',))['account_id']
        for count in (10,50,100,130):
            for storage in ('legacy','task-v1'):
                if storage=='task-v1': os.environ['METIS_FORMATION_TASK_STORAGE']='v1'
                else: os.environ.pop('METIS_FORMATION_TASK_STORAGE',None)
                html='<html><body>'+''.join(f'<h1>Stap {i}</h1><p>Controleer dagelijks de huid.</p>' for i in range(count))+'</body></html>'
                sid=console.receive_source(actor_id=actor,filename=f'validation-{storage}-{count}.html',
                    content_type='text/html',data=html.encode(),ingest_kind='new',title=f'Validation {storage} {count}',
                    version='1',date='2026-10-24',live_url='',class_='richtlijn',family='test',named_reviewers=[reviewer])['snapshot_id']
                attempt,_=console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id=f'{storage}-{count}',
                    expected_revision=console.objects_revision(sid))
                observed.clear()
                started=time.perf_counter()
                console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
                assert console._envelope(sid)['processing_attempts'][-1]['state']=='succeeded'
                joint=[row['objects'] for row in observed if row['objects']>1]
                if storage=='task-v1': assert joint==[count],joint
                result={'task_count':count,'storage':storage,'total_seconds':time.perf_counter()-started,
                        'selection_validation_seconds':sum(row['seconds'] for row in observed),
                        'selection_validation_calls':len(observed),'objects_examined':sum(row['objects'] for row in observed),
                        'joint_calls':len(joint)}
                report.append(result)
                print(json.dumps(result),flush=True)
                args.output.write_text(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
