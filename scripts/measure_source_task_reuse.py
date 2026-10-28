"""Isolated native source-reuse proof; deterministic provider, no paid calls."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.postgres_support import database,install_schema
from tests.production_support import production_application,restart_production
from tests.test_recommendation_context_v3 import response_for
from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.vorming.source_bound_fields_v3 import MODE
from src.operations_console_v1 import ConsoleError
import src.vorming.source_reconstruction_v1 as reconstruction


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--counts',default='10,50,130')
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    root=Path(tempfile.mkdtemp(prefix='metis-source-reuse-proof-'))
    counts={}
    original_status=reconstruction._with_status
    original_hash=reconstruction.hashlib.sha256
    def status(*values,**kwargs):
        counts['reconstructed_fragments']+=1
        return original_status(*values,**kwargs)
    def digest(*values,**kwargs):
        counts['reconstruction_input_hashes']+=1
        return original_hash(*values,**kwargs)
    reconstruction._with_status=status
    reconstruction.hashlib=SimpleNamespace(sha256=digest)
    calls=[]
    def provider(_url,_headers,payload,_timeout):
        text=json.loads(payload['input'][1]['content'])['source_blocks'][0]['text']
        calls.append(text)
        if len(calls)==2:
            raise ConsoleError('processing_fixture_interrupted')
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text',
            'text':json.dumps(response_for(payload,text))}]}]}
    def bind(console):
        bind_pre_review_semantic_processing(console,environ={'METIS_PASSAGE_FORMATION_MODE':MODE,
            'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'test'},post_json=provider)
    results=[]
    try:
        with database(os.environ['METIS_TEST_POSTGRES_DSN']) as config:
            install_schema(config.dsn)
            console=production_application(root/'runtime',config,processing_binder=bind).state.operations_kernel
            actor=console.create_account(username='reuse-author',password='fixture-password',roles=('researcher',))['account_id']
            reviewer=console.create_account(username='reuse-reviewer',password='fixture-password',roles=('reviewer',))['account_id']
            os.environ['METIS_FORMATION_TASK_STORAGE']='v1'
            for total in map(int,args.counts.split(',')):
                html='<html><body>'+''.join(f'<h1>Stap {i}</h1><p>Controleer dagelijks de huid bij patiënt {i}.</p>' for i in range(total))+'</body></html>'
                sid=console.receive_source(actor_id=actor,filename=f'reuse-{total}.html',content_type='text/html',data=html.encode(),
                    ingest_kind='new',title=f'Reuse {total}',version='1',date='2026-10-25',live_url='',class_='richtlijn',family='test',named_reviewers=[reviewer])['snapshot_id']
                calls.clear()
                attempt,_=console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='initial',expected_revision=console.objects_revision(sid))
                counts.update(reconstructed_fragments=0,reconstruction_input_hashes=0)
                start=time.perf_counter()
                try:
                    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
                except ConsoleError as error:
                    assert error.code=='processing_fixture_interrupted',error.code
                else:
                    raise AssertionError('Fixture must interrupt after the first committed task')
                initial=dict(counts,seconds=round(time.perf_counter()-start,6))
                context=console._envelope(sid)['processing_attempts'][-1]['diagnostic']['validator_input_ref']['context_id']
                with console.workflow_document_store._connect() as con:
                    first=con.execute('SELECT ranges_hash,result_hash FROM workflow.formation_task_results WHERE context_id=%s',(context,)).fetchone()
                console=restart_production(console);bind(console)
                following,_=console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='resume',expected_revision=console.objects_revision(sid))
                counts.update(reconstructed_fragments=0,reconstruction_input_hashes=0)
                start=time.perf_counter()
                console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=following)
                resumed=dict(counts,seconds=round(time.perf_counter()-start,6))
                with console.workflow_document_store._connect() as con:
                    same=con.execute('SELECT result_hash FROM workflow.formation_task_results WHERE context_id=%s AND ranges_hash=%s',
                        (context,first['ranges_hash'])).fetchone()
                assert same['result_hash']==first['result_hash']
                assert len(calls)==total+1 and calls.count(calls[0])==1
                assert console._envelope(sid)['processing_attempts'][-1]['state']=='succeeded'
                row={'tasks':total,'initial':initial,'resume':resumed,'provider_calls':len(calls),
                     'first_committed_task_reused':True,'first_result_hash_unchanged':True}
                results.append(row);print(json.dumps(row),flush=True)
                args.output.write_text(json.dumps(results,indent=2)+'\n')
    finally:
        reconstruction._with_status=original_status
        import hashlib
        reconstruction.hashlib=hashlib
        shutil.rmtree(root)


if __name__=='__main__':
    main()
