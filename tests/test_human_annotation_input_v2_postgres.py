"""Exact meaning selections and essential duties use the durable input owner.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from uuid import uuid4

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_v1 as annotation
from src.vorming.source_bound_fields_v3 import FIELDS
from tests.production_support import restart_production
from tests.test_human_annotation_postgres import source, anchor, command


def field_input(view):
    fields={key:{'span':None,'missing_reason':'uncertain'} for key in FIELDS}
    marked=anchor(view,'Controleer',end=len('Controleer'))
    fields['recommended_action']={'span':{k:marked[k] for k in ('block_id','start','end')},'missing_reason':None,'quote':marked['quote']}
    fields['type_evidence_spans']={'core':True}
    fields['recommendation_evidence_span']={'core':True}
    return fields


def next_command(request, result):
    return {**deepcopy(request),'command_id':str(uuid4()),'expected_revision':result['revision'],
            'expected_generation':result['generation']}


@pytest.mark.parametrize('storage',['legacy','v1'])
def test_exact_fields_resume_without_quotes_or_candidates(tmp_path,production_console,monkeypatch,storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE',storage)
    if storage=='v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE','v1')
    console,actor,_,sid,view,_=source(production_console,tmp_path)
    request=command(view,ranges=[anchor(view,'Controleer'),anchor(view,'Alleen',role='condition')])
    request['selection']['field_evidence']=field_input(view)
    request['selection']['required_links']=[]
    saved=annotation.save(console,actor_id=actor,**request)
    assert annotation.save(restart_production(console),actor_id=actor,**request)==saved
    loaded=annotation.overview(restart_production(console),actor_id=actor,snapshot_id=sid)['entries'][0]
    assert loaded['selection_version']=='human-annotation-input-v2'
    assert loaded['field_evidence']['recommended_action']=={k:v for k,v in field_input(view)['recommended_action'].items() if k!='quote'}
    assert loaded['ranges'][1]['relationship_id']==annotation.relationship_id(request['annotation_id'],request['selection']['ranges'][1])
    assert console.snapshot_objects(sid,include_blocked=True)==[]
    with console.workflow_document_store._connect() as con:
        payload=con.execute('SELECT payload FROM workflow.annotation_versions WHERE snapshot_id=%s',(sid,)).fetchone()['payload']
    annotation.validate_stored_selection(payload,fragments=annotation._read_set(console,sid)[1],annotation_id=request['annotation_id'])
    assert 'quote' not in payload['field_evidence']['recommended_action']
    stale=next_command(request,saved)
    del stale['selection']['field_evidence'];del stale['selection']['required_links']
    with pytest.raises(ConsoleError,match='annotation_client_contract_stale'):
        annotation.save(console,actor_id=actor,**stale)
    same_version=next_command(request,saved)
    del same_version['selection']['field_evidence']
    with pytest.raises(ConsoleError,match='annotation_client_contract_stale'):
        annotation.save(console,actor_id=actor,**same_version)
    altered=next_command(request,saved)
    altered['selection']['field_evidence']['recommended_action']['quote']='Andere tekst'
    with pytest.raises(ConsoleError,match='annotation_anchor_mismatch'):
        annotation.save(console,actor_id=actor,**altered)
    marker=next_command(request,saved)
    marker['selection']['field_evidence']['type_evidence_spans']={'core':1}
    with pytest.raises(ConsoleError,match='source_bound_field_invalid'):
        annotation.save(console,actor_id=actor,**marker)


def test_essential_relationship_cannot_disappear_and_can_be_reanchored_or_discharged(tmp_path,production_console):
    console,actor,_,sid,view,_=source(production_console,tmp_path)
    request=command(view,ranges=[anchor(view,'Controleer'),anchor(view,'Alleen',role='condition')])
    request['selection'].update(required_links=[],evidence_not_applicable=True)
    result=annotation.save(console,actor_id=actor,**request)
    condition=request['selection']['ranges'][1]
    key=annotation.relationship_id(request['annotation_id'],condition)
    removed=next_command(request,result);removed['selection']['ranges'].pop()
    with pytest.raises(ConsoleError,match='annotation_required_relationship_missing'):
        annotation.save(console,actor_id=actor,**removed)
    open_link={'relationship_id':key,'role':'condition','evidence_function':None,'required_for_meaning':True,'withdrawal_reason':None}
    removed['selection']['required_links']=[open_link]
    result=annotation.save(console,actor_id=actor,**removed)
    ready=next_command(removed,result);ready['selection']['status']='ready'
    with pytest.raises(ConsoleError,match='annotation_required_relationship_missing'):
        annotation.save(console,actor_id=actor,**ready)
    pending=next_command(removed,result)
    pending['selection']['pending_range']={**condition,'relationship_id':key}
    result=annotation.save(console,actor_id=actor,**pending)
    paused=annotation.overview(restart_production(console),actor_id=actor,snapshot_id=sid)['entries'][0]
    assert paused['pending_range']['relationship_id']==paused['required_links'][0]['relationship_id']
    repaired=next_command(removed,result)
    repaired['selection']['ranges'].append({**condition,'start':len('Alleen '),'quote':'bij klachten.','relationship_id':key})
    repaired['selection']['required_links']=[];repaired['selection']['status']='ready'
    result=annotation.save(restart_production(console),actor_id=actor,**repaired)
    assert result['status']=='ready'
    # Merely unchecking essentiality is also a loss of the recorded duty.
    downgrade=next_command(repaired,result)
    downgrade['selection']['ranges'][1]['required_for_meaning']=False
    with pytest.raises(ConsoleError,match='annotation_required_relationship_missing'):
        annotation.save(console,actor_id=actor,**downgrade)
    downgrade['selection']['required_links']=[{**open_link,'required_for_meaning':False,'withdrawal_reason':'Deze koppeling was per vergissing essentieel gemarkeerd.'}]
    result=annotation.save(console,actor_id=actor,**downgrade)
    loaded=annotation.overview(restart_production(console),actor_id=actor,snapshot_id=sid)['entries'][0]
    assert loaded['required_links'][0]['withdrawal_reason']==downgrade['selection']['required_links'][0]['withdrawal_reason']
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_versions WHERE snapshot_id=%s',(sid,)).fetchone()['n']==5


@pytest.mark.parametrize('role,reason,status',[('metadata','document_metadata','ready'),('structure','document_structure','ready'),('unresolved','uncertain_source_role','draft')])
def test_source_accounting_proposal_is_not_a_candidate(tmp_path,production_console,role,reason,status):
    console,actor,_,sid,view,_=source(production_console,tmp_path)
    # Headings are valid source-accounting input, but never a prose candidate.
    request=command(view,ranges=[anchor(view,'Advies')],status=status)
    request['selection'].update(object_type=None,disposition={'role':role,'reason':reason})
    result=annotation.save(console,actor_id=actor,**request)
    loaded=annotation.overview(restart_production(console),actor_id=actor,snapshot_id=sid)['entries'][0]
    assert loaded['disposition']=={'role':role,'reason':reason}
    assert console.snapshot_objects(sid,include_blocked=True)==[]
    if role=='unresolved':
        ready=next_command(request,result);ready['selection']['status']='ready'
        with pytest.raises(ConsoleError,match='annotation_source_disposition_unresolved'):
            annotation.save(console,actor_id=actor,**ready)


@pytest.mark.parametrize('change',['legacy','drop','downgrade','open_ready','reanchor_wrong_id','drop_fields'])
def test_native_guard_rejects_older_or_bypassing_writer(tmp_path,production_console,change):
    import psycopg
    from src.integrity_kernel import stable_hash
    from src.workflows.workflow_documents_postgres_v1 import _json_text
    console,actor,_,sid,view,_=source(production_console,tmp_path)
    request=command(view,ranges=[anchor(view,'Controleer'),anchor(view,'Alleen',role='condition')])
    request['selection'].update(required_links=[],field_evidence=field_input(view))
    annotation.save(console,actor_id=actor,**request)
    with console.workflow_document_store._connect() as con:
        payload=con.execute('SELECT payload FROM workflow.annotation_versions WHERE snapshot_id=%s',(sid,)).fetchone()['payload']
    bad=deepcopy(payload)
    expected='annotation_required_relationship_missing'
    if change=='legacy':
        del bad['selection_version'];del bad['required_links']
        expected='annotation_client_contract_stale'
    elif change=='drop_fields':
        del bad['field_evidence']
        expected='annotation_client_contract_stale'
    elif change=='drop': bad['ranges'].pop()
    elif change=='downgrade': bad['ranges'][1]['required_for_meaning']=False
    elif change=='open_ready':
        condition=bad['ranges'].pop();bad['status']='ready'
        bad['required_links']=[{k:condition[k] for k in ('relationship_id','role','evidence_function','required_for_meaning')} | {'withdrawal_reason':None}]
    else:
        bad['ranges'][1]['start']=1
        bad['ranges'][1]['relationship_id']=annotation.relationship_id(request['annotation_id'],bad['ranges'][1])
    with pytest.raises(psycopg.errors.RaiseException,match=expected):
        with console.workflow_document_store._connect() as con:
            con.execute('INSERT INTO workflow.annotation_versions(snapshot_id,annotation_id,revision,status,author_id,payload,payload_hash) VALUES(%s,%s,2,%s,%s,%s::jsonb,%s)',
                (sid,request['annotation_id'],bad['status'],actor,_json_text(bad),stable_hash(bad)))
    assert annotation.overview(restart_production(console),actor_id=actor,snapshot_id=sid)['generation']==1


def test_concurrent_field_and_essential_corrections_keep_one_committed_revision(tmp_path,production_console):
    from concurrent.futures import ThreadPoolExecutor
    console,actor,_,sid,view,_=source(production_console,tmp_path)
    request=command(view,ranges=[anchor(view,'Controleer'),anchor(view,'Alleen',role='condition')])
    request['selection'].update(required_links=[],field_evidence=field_input(view))
    result=annotation.save(console,actor_id=actor,**request)
    a=next_command(request,result);b=next_command(request,result)
    a['selection']['field_evidence']['recommended_action']={'span':None,'missing_reason':'not_stated'}
    condition=b['selection']['ranges'].pop()
    b['selection']['required_links']=[{'relationship_id':annotation.relationship_id(request['annotation_id'],condition),
        'role':'condition','evidence_function':None,'required_for_meaning':True,'withdrawal_reason':None}]
    other=restart_production(console)
    def send(pair):
        kernel,body=pair
        try: return annotation.save(kernel,actor_id=actor,**body)
        except ConsoleError as error: return error.code
    with ThreadPoolExecutor(2) as pool: outcomes=list(pool.map(send,[(console,a),(other,b)]))
    assert sum(isinstance(outcome,dict) for outcome in outcomes)==1
    assert 'annotation_write_conflict' in outcomes
    winner=a if isinstance(outcomes[0],dict) else b
    receipt=next(outcome for outcome in outcomes if isinstance(outcome,dict))
    assert annotation.save(restart_production(console),actor_id=actor,**winner)==receipt
    loaded=annotation.overview(console,actor_id=actor,snapshot_id=sid)
    assert loaded['generation']==2
    if winner is b: assert loaded['entries'][0]['required_links'][0]['required_for_meaning']
    else: assert loaded['entries'][0]['ranges'][1]['required_for_meaning']


def test_v2_history_backup_restore_and_self_consistent_relation_loss_refused(tmp_path,production_console):
    from src.integrity_kernel import stable_hash
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.publication.publication_chain_recovery_v1 import PublicationChainRecoveryError
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from tests.postgres_support import database,install_schema
    from tests.production_support import production_application
    console,actor,_,sid,view,_=source(production_console,tmp_path)
    request=command(view,ranges=[anchor(view,'Controleer'),anchor(view,'Alleen',role='condition')])
    request['selection'].update(field_evidence=field_input(view),required_links=[])
    first=annotation.save(console,actor_id=actor,**request)
    annotation.save(console,actor_id=actor,**next_command(request,first))
    adapter=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config))
    state=adapter.export_state()
    reversed_rows=deepcopy(state)
    for rows in reversed_rows['formation_recovery']['tables'].values(): rows.reverse()
    with database(console.workflow_document_store.config.dsn) as target_config:
        install_schema(target_config.dsn)
        restored=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target_config))
        restored.restore_state(reversed_rows)
        kernel=production_application(console.root,target_config,runtime=console.runtime,source_store=console.source_store).state.operations_kernel
        assert annotation.overview(kernel,actor_id=actor,snapshot_id=sid)==annotation.overview(console,actor_id=actor,snapshot_id=sid)
        assert annotation.save(kernel,actor_id=actor,**request)==first
    corrupted=deepcopy(state)
    tables=corrupted['formation_recovery']['tables']
    row=next(r for r in tables['annotation_versions'] if r['revision']==2)
    row['payload']['ranges'].pop();row['payload_hash']=stable_hash(row['payload'])
    receipt=next(r for r in tables['annotation_commands'] if r['result']['revision']==2)
    receipt['request_hash']=stable_hash({'actor_id':actor,'annotation_id':request['annotation_id'],
        'expected_revision':1,'expected_generation':1,'extraction_hash':request['extraction_hash'],
        'normalization':request['normalization'],'selection':row['payload']})
    with database(console.workflow_document_store.config.dsn) as target_config:
        install_schema(target_config.dsn)
        target=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target_config))
        with pytest.raises(PublicationChainRecoveryError): target.restore_state(corrupted)
        target.assert_empty()


def test_native_old_head_cannot_hide_new_input(tmp_path,production_console):
    import psycopg
    console,actor,_,sid,view,_=source(production_console,tmp_path)
    request=command(view,ranges=[anchor(view,'Controleer')])
    first=annotation.save(console,actor_id=actor,**request)
    upgraded=next_command(request,first)
    upgraded['selection']['field_evidence']=field_input(view)
    annotation.save(console,actor_id=actor,**upgraded)
    with pytest.raises(psycopg.errors.RaiseException,match='annotation_head_stale'):
        with console.workflow_document_store._connect() as con:
            con.execute('UPDATE workflow.annotation_heads SET revision=1 WHERE snapshot_id=%s AND annotation_id=%s',
                (sid,request['annotation_id']))
    loaded=annotation.overview(restart_production(console),actor_id=actor,snapshot_id=sid)
    assert loaded['entries'][0]['revision']==2
    assert loaded['entries'][0]['field_evidence']


@pytest.mark.parametrize('capability',['role','relationship_id','pending_role'])
def test_new_capability_always_pins_v2_without_other_optional_fields(tmp_path,production_console,capability):
    console,actor,_,sid,view,_=source(production_console,tmp_path)
    marked=anchor(view,'Alleen',role='actor' if capability in {'role','pending_role'} else 'condition')
    request=command(view,ranges=[anchor(view,'Controleer')])
    if capability=='relationship_id': marked['relationship_id']=annotation.relationship_id(request['annotation_id'],marked)
    if capability=='pending_role': request['selection']['pending_range']=marked
    else: request['selection']['ranges'].append(marked)
    result=annotation.save(console,actor_id=actor,**request)
    loaded=annotation.overview(restart_production(console),actor_id=actor,snapshot_id=sid)['entries'][0]
    assert loaded['selection_version']=='human-annotation-input-v2'
    stale=next_command(request,result)
    stale['selection']['ranges']=[stale['selection']['ranges'][0]]
    stale['selection'].pop('pending_range',None)
    with pytest.raises(ConsoleError,match='annotation_client_contract_stale'):
        annotation.save(console,actor_id=actor,**stale)
