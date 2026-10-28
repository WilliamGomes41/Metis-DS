"""#839: native source/selection reuse across a fresh kernel, not a process cache.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery version-compat
# release-control-evidence: kwaliteit
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from copy import deepcopy

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.vorming.source_bound_fields_v3 import MODE
from tests.production_support import restart_production
from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_recommendation_context_v3 import response_for


def interrupted(tmp_path,production_console,monkeypatch):
    console,users,_,_ = _system(tmp_path,production_console=production_console)
    actor = users['researcher']['account_id']
    sid = console.receive_source(actor_id=actor,filename='reuse.html',content_type='text/html',
        data=b'<html><body><h1>Een</h1><p>Gebruik geen zalf.</p><h1>Twee</h1><p>Controleer dagelijks de huid.</p><h1>Drie</h1><p>Was dagelijks de handen.</p></body></html>',
        ingest_kind='new',title='Reuse',version='1',date='2026-10-25',live_url='',class_='richtlijn',family='test',
        named_reviewers=[users['reviewer_a']['account_id']])['snapshot_id']
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE','v1')
    calls=[]
    def provider(_url,_headers,payload,_timeout):
        request=json.loads(payload['input'][1]['content'])
        text=request['source_blocks'][0]['text'];calls.append(text)
        if len(calls)==2:
            raise ConsoleError('processing_test_interrupted')
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text',
            'text':json.dumps(response_for(payload,text))}]}]}
    def bind(target):
        bind_pre_review_semantic_processing(target,environ={'METIS_PASSAGE_FORMATION_MODE':MODE,
            'METIS_LLM_API_KEY':'fixture','METIS_LLM_MODEL':'test'},post_json=provider)
    bind(console)
    attempt,_=console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='initial',
        expected_revision=console.objects_revision(sid))
    with pytest.raises(ConsoleError,match='processing_test_interrupted'):
        console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    return console,actor,sid,calls,bind


def test_new_worker_reuses_exact_sources_and_tasks_with_extractor_and_reconstructor_forbidden(tmp_path,production_console,monkeypatch):
    console,actor,sid,calls,bind=interrupted(tmp_path,production_console,monkeypatch)
    before=deepcopy(console._envelope(sid))
    with console.workflow_document_store._connect() as con:
        first=con.execute('SELECT context_id,ranges_hash,result_hash,payload FROM workflow.formation_task_results').fetchone()
    restarted=restart_production(console);bind(restarted)
    def forbidden(*args,**kwargs):
        raise AssertionError('Compatible source preparation must be read, not extracted or reconstructed')
    monkeypatch.setattr(restarted,'_extract',forbidden)
    monkeypatch.setattr('src.vorming.source_reconstruction_v1._with_status',forbidden)
    following,_=restarted.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='resume',
        expected_revision=restarted.objects_revision(sid))
    restarted.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=following)
    assert calls==['Gebruik geen zalf.','Controleer dagelijks de huid.','Controleer dagelijks de huid.','Was dagelijks de handen.']
    with restarted.workflow_document_store._connect() as con:
        same=con.execute('SELECT context_id,ranges_hash,result_hash,payload FROM workflow.formation_task_results '
            'WHERE context_id=%s AND ranges_hash=%s',(first['context_id'],first['ranges_hash'])).fetchone()
    assert same==first
    final=restarted._envelope(sid)
    assert final['processing_attempts'][-1]['state']=='succeeded'
    assert final['prepared_source_extraction']==before['prepared_source_extraction']
    assert final['processing_attempts'][-1]['diagnostic']['source_views_ref']==before['processing_attempts'][-1]['diagnostic']['source_views_ref']


@pytest.mark.parametrize('damage,expected',[
    ('missing','source_views_missing'),('payload','source_views_integrity_failed'),
    ('reference','source_views_reference_invalid'),('extractor','source_extraction_contract_mismatch'),
    ('task','formation_record_integrity_failed')])
def test_invalid_committed_evidence_stops_before_model_work(tmp_path,production_console,monkeypatch,damage,expected):
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console,actor,sid,calls,bind=interrupted(tmp_path,production_console,monkeypatch)
    attempt=console._envelope(sid)['processing_attempts'][-1]
    ref=attempt['diagnostic']['source_views_ref']
    source=deepcopy(console._envelope(sid)['prepared_source_extraction'])
    with console.workflow_document_store._connect() as con:
        if damage=='missing':
            con.execute('DELETE FROM workflow.formation_source_views WHERE views_id=%s',(ref['views_id'],))
        elif damage=='payload':
            con.execute("UPDATE workflow.formation_source_views SET payload=jsonb_set(payload,'{fragments_hash}','\"corrupt\"') WHERE views_id=%s",(ref['views_id'],))
        elif damage=='reference':
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{diagnostic,source_views_ref,extraction_hash}','\"foreign-source\"') WHERE attempt_id=%s",(attempt['attempt_id'],))
        elif damage=='task':
            con.execute("UPDATE workflow.formation_task_results SET payload=jsonb_set(payload,'{proposal,objects}','[]') WHERE context_id=%s",
                (attempt['diagnostic']['validator_input_ref']['context_id'],))
    restarted=restart_production(console);bind(restarted)
    if damage=='extractor':
        monkeypatch.setattr('src.vorming.source_preparation_context_v1.extractor_contract',lambda kind:'different-extractor')
    following,_=restarted.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='damage-resume',
        expected_revision=restarted.objects_revision(sid))
    with pytest.raises((ConsoleError,WorkflowDocumentStoreError),match=expected):
        restarted.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=following)
    assert len(calls)==2
    assert restarted._envelope(sid)['prepared_source_extraction']==source


def test_old_unmarked_context_is_prepared_once_without_reextracting_or_losing_work(tmp_path,production_console,monkeypatch):
    console,actor,sid,calls,bind=interrupted(tmp_path,production_console,monkeypatch)
    attempt=console._envelope(sid)['processing_attempts'][-1]
    # Simulate the precise pre-#839 durable shape: input/results/plan exist,
    # source-view marker and table row have never been recorded.
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=payload #- '{diagnostic,source_views_ref}' WHERE attempt_id=%s",(attempt['attempt_id'],))
        con.execute("DELETE FROM workflow.processing_checkpoints WHERE attempt_id=%s AND phase='source_views_pinned'",(attempt['attempt_id'],))
        con.execute('DELETE FROM workflow.formation_source_views WHERE views_id=%s',(attempt['diagnostic']['source_views_ref']['views_id'],))
        result_hash=con.execute('SELECT result_hash FROM workflow.formation_task_results').fetchone()['result_hash']
    restarted=restart_production(console);bind(restarted)
    def forbidden(*args,**kwargs):
        raise AssertionError('Legacy preparation must derive from committed extraction, never raw re-extraction')
    monkeypatch.setattr(restarted,'_extract',forbidden)
    following,_=restarted.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='upgrade-resume',
        expected_revision=restarted.objects_revision(sid))
    restarted.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=following)
    final=restarted._envelope(sid)
    assert final['processing_attempts'][-1]['diagnostic']['source_views_ref']
    assert calls.count('Gebruik geen zalf.')==1
    with restarted.workflow_document_store._connect() as con:
        assert con.execute('SELECT COUNT(*) AS n FROM workflow.formation_task_results WHERE result_hash=%s',(result_hash,)).fetchone()['n']==1


def test_explicit_authorized_reextraction_remains_available(tmp_path,production_console,monkeypatch):
    console,actor,sid,calls,bind=interrupted(tmp_path,production_console,monkeypatch)
    following,_=console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='finish',
        expected_revision=console.objects_revision(sid))
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=following)
    original=console._extract
    extracted=[]
    def counted(*args,**kwargs):
        extracted.append(True)
        return original(*args,**kwargs)
    monkeypatch.setattr(console,'_extract',counted)
    console.reextract_unpublished(actor_id=actor,snapshot_id=sid)
    assert extracted==[True]
    assert console._envelope(sid)['processing_attempts'][-1]['kind']=='reextract'
    assert console._envelope(sid)['processing_attempts'][-1]['state']=='succeeded'


def test_immutable_views_match_existing_source_projections_and_mutable_inputs_stay_checked():
    from src.vorming.prepared_source_views_v1 import prepare,stored_blocks
    from src.vorming.semantic_passage_v1 import _reconstructed_blocks
    from src.vorming.pre_review_semantic_v1 import _content_fragments,_candidate_fragments,_evidence_fragments
    from src.integrity_kernel import stable_hash
    from tests.test_recommendation_context_v3 import source
    raw=source('Gebruik geen zalf.',heading='Bij een natte huid:')
    raw.extend([{**source('Sterk – tegen')[0],'fragment_id':'strength'},
                {**source('Controleer dagelijks de huid.')[0],'fragment_id':'other'}])
    root=prepare(raw)
    for name,projection in [('full',raw),('content',_content_fragments(raw)),
                            ('candidate',_candidate_fragments(raw)),('evidence',_evidence_fragments(raw))]:
        assert stable_hash(_reconstructed_blocks(root.carriers[name]))==stable_hash(_reconstructed_blocks(projection))
        assert stable_hash(root.carriers[name])==stable_hash(projection)
    immutable=root.fragments
    with pytest.raises(ConsoleError,match='source_views_carrier_immutable'):
        immutable[0]['raw_text']='changed'
    with pytest.raises(ConsoleError,match='source_views_carrier_immutable'):
        immutable.append({})
    from src.vorming.prepared_source_views_v1 import PreparedSource
    damaged=json.loads(json.dumps(root.payload))
    damaged['views']['full']['blocks'][0][1]['_raw_source_mapping'][0]['raw_end']=999999
    with pytest.raises(ConsoleError,match='source_views_integrity_failed'):
        PreparedSource(raw,damaged)
    clone=json.loads(json.dumps(immutable))
    assert stored_blocks(clone) is None
    before=stable_hash(_reconstructed_blocks(clone))
    clone[1]['clean_text']=clone[1]['raw_text']='Een andere instructie.'
    assert stable_hash(_reconstructed_blocks(clone))!=before


def test_source_view_acceptance_is_atomic_unique_and_claim_fenced(tmp_path,production_console):
    from concurrent.futures import ThreadPoolExecutor
    from src.vorming.prepared_source_views_v1 import prepare
    from src.vorming.source_preparation_context_v1 import stored_extraction
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    from tests.test_formation_task_store_postgres import prepared,checkpoint_context
    console,envelope,data=prepared(tmp_path,production_console)
    writer=checkpoint_context(console,envelope,data)
    payload=prepare(stored_extraction(envelope)).payload
    def retain():
        with writer._locked() as (con,active):
            return writer.store.retain_source_views(con,writer.input_reference,payload)
    with pytest.raises(RuntimeError,match='rollback-source-views'):
        with writer._locked() as (con,active):
            writer.store.retain_source_views(con,writer.input_reference,payload)
            raise RuntimeError('rollback-source-views')
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT COUNT(*) AS n FROM workflow.formation_source_views').fetchone()['n']==0
    token=writer.claim_token
    writer.claim_token='obsolete-claim'
    with pytest.raises(ConsoleError,match='processing_command_conflict'):
        retain()
    writer.claim_token=token
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(retain) for _ in range(2)]
        refs=[future.result() for future in futures]
    assert refs[0]==refs[1]
    changed=json.loads(json.dumps(payload))
    first=changed['views']['full']['blocks'][0]
    first[0]['text']=first[1]['clean_text']='Afwijkende broninhoud.'
    with pytest.raises(WorkflowDocumentStoreError,match='formation_immutable_record_conflict'):
        with writer._locked() as (con,active):
            writer.store.retain_source_views(con,writer.input_reference,changed)
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT COUNT(*) AS n FROM workflow.formation_source_views').fetchone()['n']==1
