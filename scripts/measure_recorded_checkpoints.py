"""Read-only incident fixture -> isolated native-PostgreSQL storage benchmark.

Uses recorded validator inputs and task metadata, never a live model or source
re-extraction. This measures checkpoints, not clinical acceptance of the output.
"""
import argparse
import atexit
import csv
from copy import deepcopy
import io
import json
import os
from pathlib import Path
from statistics import median
import sys
import shutil
import tempfile
import time
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.postgres_support import database,install_schema
from tests.production_support import production_application
from tests.semantic_fixture_support import bind_fixture_selections
from src.console_performance_v1 import performance_scope
from src.vorming.processing_retry_v1 import reserve,now
from src.vorming.source_selection_v1 import configuration
from src.vorming.source_preparation_context_v1 import extraction_record
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.vorming.attempt_diagnostics_v1 import validator_identity
from scripts.migrate_processing_attempts import migrate
from src.vorming.semantic_replay_v1 import stable_json_hash

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-zip',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    work=Path(tempfile.mkdtemp(prefix='metis-recorded-checkpoint-'))
    atexit.register(shutil.rmtree,work)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    csv.field_size_limit(64_000_000)
    archive=args.evidence_zip
    with ZipFile(archive) as z:
        recorded=list(csv.DictReader(io.StringIO(z.read('attempt_diagnostics.csv').decode('utf-8-sig'))))
    diagnostics=[json.loads(row['diagnostic']) for row in recorded]
    original=diagnostics[0]
    data=original['validator_input']
    tasks=original['provider_evidence']['tasks']
    report={'source':'user-supplied Smetten processing-evidence export','fragments':len(data['fragments']),
            'evidence_fragments':len(data['evidence_fragments']),'planned_tasks':len(tasks),
            'scope':'storage checkpoint replay; no provider or clinical-acceptance claim','legacy':[],'task_store':[]}

    def sample(writer,task):
        with performance_scope() as metrics:
            start=time.perf_counter()
            writer('model_request',{'current_task':task})
            duration=time.perf_counter()-start
        return dict(seconds=duration,queries=metrics.queries,json_bytes=metrics.json_bytes)

    dsn=os.environ['METIS_TEST_POSTGRES_DSN']
    with database(dsn) as config:
        install_schema(config.dsn)
        console=production_application(work/'recorded-runtime',config,processing_binder=bind_fixture_selections).state.operations_kernel
        actor=console.create_account(username='recorded-fixture',password='fixture-password',roles=('researcher',))['account_id']
        reviewer=console.create_account(username='recorded-reviewer',password='fixture-password',roles=('reviewer',))['account_id']
        receipt=console.receive_source(actor_id=actor,filename='placeholder.html',content_type='text/html',
            data=b'<html><body><p>Isolated checkpoint fixture</p></body></html>',ingest_kind='new',title='Fixture',
            version='1',date='2026-10-24',live_url='',class_='richtlijn',family='test',named_reviewers=[reviewer])
        seed=console._envelope(receipt['snapshot_id'])
        envelope={k:v for k,v in seed.items() if k not in {'logical_document_id','working_revision_id',
            'working_revision_number','source_snapshot_id','source_version','processing_attempts'}}
        sid=original['semantic_identity']['components']['snapshot_id']
        fragments=data['evidence_fragments']
        envelope.update(snapshot_id=sid,document_id=data['document_id'],source_id=fragments[0]['source_id'],
            sha256=original['source_hash'],version=original['source_version'],content_kind='pdf',title='Recorded Smetten checkpoint fixture')
        envelope['prepared_source_extraction']=extraction_record(envelope,fragments,'recorded-incident-extraction')
        envelope['processing_configuration']=configuration(console)
        revision=console.workflow_document_store.revision_for_rows([])
        history=[]
        for i,(row,diagnostic) in enumerate(zip(recorded[:3],diagnostics[:3])):
            history.append({'attempt_id':row['attempt_id'],'command_id':f'recorded-{i}','actor_id':actor,
                'source_hash':envelope['sha256'],'source_version':envelope['version'],'expected_revision':revision,
                'state':row['state'],'formation_progress_made':i==1,'started_at':f'2026-10-24T18:{i:02}:00+00:00','finished_at':f'2026-10-24T18:{i:02}:01+00:00',
                'expires_at':f'2026-10-24T18:{i:02}:01+00:00','kind':'retry','diagnostic':deepcopy(diagnostic)})
        envelope['processing_attempts']=history
        report['historical_attempts']=len(history)
        active,_=reserve(envelope,command_id='recorded-old-checkpoint',actor_id=actor,revision=revision,
            clock=now(),limits=console._processing_limits())
        active['processing_configuration']=configuration(console)
        active['diagnostic']=deepcopy(original)
        console.workflow_document_store.write_bundle(envelope=envelope)
        legacy=console._diagnostic_writer(sid,active['attempt_id'])
        calls=[original['provider_evidence'],*original['provider_evidence'].get('supplementary_calls',[])]
        for count in (10,50,100,130):
            active['diagnostic']['provider_evidence']={**calls[0],'tasks':tasks[:count],'supplementary_calls':calls[1:count]}
            console.workflow_document_store.write_bundle(envelope=envelope)
            values=[sample(legacy,{**tasks[count-1],'status':'running'}) for _ in range(3)]
            report['legacy'].append({'task_count':count,'median_seconds':median(v['seconds'] for v in values),
                'json_bytes':values[0]['json_bytes'],'queries':values[0]['queries']})
        current=console._envelope(sid)
        current['processing_attempts'][-1].update(state='interrupted',finished_at=now().isoformat())
        console.workflow_document_store.write_bundle(envelope=current)
        migrate(console.workflow_document_store,sid,apply=True)
        current=console._envelope(sid)
        active,_=reserve(current,command_id='recorded-new-checkpoint',actor_id=actor,revision=revision,
            clock=now(),limits=console._processing_limits())
        active['processing_configuration']=configuration(console)
        console.workflow_document_store.write_bundle(envelope=current)
        targeted=console._diagnostic_writer(sid,active['attempt_id'])
        targeted('source_reconstructed',{'validator_input':data,'validator_input_hash':stable_json_hash(data),
            'validator_identity':validator_identity(),'semantic_identity':original['semantic_identity']})
        assert targeted.store.resolve_input(targeted.input_reference)==data
        targeted.plan_tasks(len(tasks))
        for count,task in enumerate(tasks,1):
            measured=sample(targeted,{**task,'status':'running'})
            if count in (10,50,100,130):
                values=[sample(targeted,{**task,'status':'running'}) for _ in range(3)]
                report['task_store'].append({'task_count':count,'median_seconds':median(v['seconds'] for v in values),
                    'json_bytes':values[0]['json_bytes'],'queries':values[0]['queries']})
        assert len({v['json_bytes'] for v in report['task_store']})==1
        with console.workflow_document_store._connect() as con:
            raw=con.execute('SELECT envelope_payload FROM workflow.documents WHERE snapshot_id=%s',(sid,)).fetchone()['envelope_payload']
        assert 'processing_attempts' not in raw
    report['exact_validator_input_hash']=stable_json_hash(data)
    args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
