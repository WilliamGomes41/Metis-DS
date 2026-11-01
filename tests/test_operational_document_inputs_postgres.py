"""Native small-header/cutover contract; source/formation authority stays current.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json

import pytest


@pytest.fixture(params=[False, True], ids=['local-source', 'azure-source'])
def incomplete_document(tmp_path, production_console, monkeypatch, request):
    from tests.test_review_formation_problems import received, execute
    def factory(**options):
        return production_console(azure=request.param, **options)
    console, sid, author, reviewer, *_ = received(tmp_path, factory, monkeypatch)
    execute(console, sid, author, 'operational-inputs')
    return console, sid, author, reviewer


def test_explicit_cutover_keeps_formation_and_original_bytes_with_small_metadata(incomplete_document):
    console, sid, _, _ = incomplete_document
    store = console.workflow_document_store
    before = deepcopy(store.get_envelope(sid))
    status_before = console.processing_status(sid)
    assert status_before['formation_incomplete']
    with store._connect() as con:
        original = con.execute('SELECT envelope_payload::text AS body FROM workflow.documents WHERE snapshot_id=%s',
                               (sid,)).fetchone()['body']
    prepared = store.prepare_operational_inputs(sid)
    store.activate_operational_inputs(prepared)
    header = store.get_envelope(sid)
    assert header['_document_inputs']['layout'] == 1
    assert not {'semantic_replay','quality_processing_runs','processing_attempts'} & set(header)
    assert not {'fragments','docling_record'} & set(header.get('prepared_source_extraction') or {})
    assert len(json.dumps(header,ensure_ascii=False).encode()) < 16000
    assert console.processing_status(sid) == status_before
    assert store.processing_history_input(sid) == before
    changed = deepcopy(header)
    changed['title'] = 'Current metadata'
    store.write_bundle(envelope=changed)
    assert store.get_envelope(sid)['title'] == 'Current metadata'
    with store._connect() as con:
        assert con.execute('SELECT envelope_payload::text AS body FROM workflow.documents WHERE snapshot_id=%s',
                           (sid,)).fetchone()['body'] == original


def test_review_reads_commands_and_readiness_after_compact_cutover(incomplete_document):
    from fastapi.testclient import TestClient
    from tests.test_availability_repair import login
    from tests.test_review_formation_problems import FIRST
    console,sid,_,reviewer=incomplete_document
    store=console.workflow_document_store
    before=store.get_envelope(sid)
    store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    candidate=next(o for o in console.snapshot_objects(sid) if o.get('proposed_object_type')=='recommendation')
    expected=[{**r,'candidates':[c for c in r.get('candidates',[]) if c.get('object_id')==candidate['object_id']]}
              for r in before['quality_processing_runs'][-1:]]
    selected=store.review_command_quality_input(sid,[candidate['object_id']])
    assert selected[0]['candidates']==expected[0]['candidates']
    assert 'source_formation_incomplete' in console.publication_readiness(sid)['blockers']
    assert store.list_document_cards([sid])[0]['title']==before['title']
    client=TestClient(console._metis_test_application,base_url='https://console.example.test',headers={'Origin':'https://console.example.test'})
    login(client,'reviewer')
    page=client.get('/review',params={'document':sid,'object':candidate['object_id'],'task':'contextual'})
    assert page.status_code==200 and FIRST in page.text
    console.review_object(actor_id=reviewer,snapshot_id=sid,object_id=candidate['object_id'],
        decision='approve',confirmed_object_type='recommendation',recommendation_direction='against',
        recommendation_strength_level='not_stated')
    assert console.processing_status(sid)['formation_incomplete']
    assert not console.processing_status(sid)['resume_allowed']
    assert not console.publication_readiness(sid)['publish_allowed']


@pytest.mark.parametrize('azure',[False,True])
def test_native_resume_keeps_compact_storage_across_restart(tmp_path,production_console,monkeypatch,azure):
    from tests.test_review_formation_problems import received,execute,SECOND
    from tests.production_support import restart_production
    from tests.test_availability_repair import bind
    def factory(**options):
        return production_console(azure=azure,**options)
    console,sid,author,_,calls,mode,provider=received(tmp_path,factory,monkeypatch)
    execute(console,sid,author,'before-cutover')
    store=console.workflow_document_store
    store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    restarted=restart_production(console)
    bind(restarted,provider)
    mode['broken']=False
    attempt=execute(restarted,sid,author,'after-cutover')
    assert attempt['kind']=='resume'
    assert len(calls)==4 and calls[-1]['source_blocks'][0]['text']==SECOND
    assert '_document_inputs' in restarted.workflow_document_store.get_envelope(sid)
    assert not restarted.processing_status(sid)['formation_incomplete']
    assert 'source_formation_incomplete' not in restarted.publication_readiness(sid)['blockers']


@pytest.mark.parametrize('azure',[False,True])
def test_new_receipt_admission_then_native_formation_and_flag_rollback(tmp_path,production_console,monkeypatch,azure):
    from tests.test_review_formation_problems import received,execute
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE','v1')
    def factory(**options):
        return production_console(azure=azure,**options)
    console,sid,author,_,calls,mode,_=received(tmp_path,factory,monkeypatch)
    store=console.workflow_document_store
    assert store.get_envelope(sid)['_document_inputs']['formation_variant']=='absent'
    assert calls==[]
    execute(console,sid,author,'new-compact-document')
    assert store.get_envelope(sid)['_document_inputs']['formation_variant']=='semantic'
    assert console.processing_status(sid)['formation_incomplete']
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE','legacy')
    mode['broken']=False
    execute(console,sid,author,'after-admission-off')
    assert not console.processing_status(sid)['formation_incomplete']
    with store._connect() as con:
        row=con.execute("SELECT envelope_payload->'semantic_replay' AS replay,document_storage_version FROM workflow.documents WHERE snapshot_id=%s",(sid,)).fetchone()
    assert row['document_storage_version']==1 and row['replay'] is None


def test_preparation_is_cas_and_typed_attempt_projection_cannot_be_forged(incomplete_document):
    import psycopg
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console,sid,_,_=incomplete_document
    store=console.workflow_document_store
    prepared=store.prepare_operational_inputs(sid)
    changed=deepcopy(store.get_envelope(sid))
    changed['title']='Concurrent winner'
    store.write_bundle(envelope=changed)
    with pytest.raises(WorkflowDocumentStoreError,match='stale_preparation'):
        store.activate_operational_inputs(prepared)
    store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    with pytest.raises(psycopg.Error):
        with store._connect() as con:
            con.execute("UPDATE workflow.processing_attempt_inputs SET state='forged-state' WHERE snapshot_id=%s",(sid,))
    with pytest.raises(psycopg.Error):
        with store._connect() as con:
            con.execute("UPDATE workflow.document_inputs SET refs=jsonb_set(refs,'{formation_variant}','\"absent\"') WHERE snapshot_id=%s",(sid,))
    assert console.processing_status(sid)['formation_incomplete']
    assert store.get_envelope(sid)['title']=='Concurrent winner'


def test_converted_workflow_backup_preserves_current_metadata_and_exact_history(incomplete_document):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore,PostgresCanonicalConfig
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from src.workflows.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore
    from tests.postgres_support import database
    from tests.test_workflow_chain_recovery_v1 import _install_schema
    console,sid,_,_=incomplete_document
    store=console.workflow_document_store
    store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    changed=store.get_envelope(sid)
    changed['title']='Current title differs from frozen original'
    store.write_bundle(envelope=changed)
    state=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(store.config)).export_state()
    with database(store.config.dsn) as target_db:
        _install_schema(target_db.dsn)
        config=PostgresCanonicalConfig(dsn=target_db.dsn)
        adapter=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config))
        adapter.restore_state(state)
        assert adapter.export_state()['formation_recovery']==state['formation_recovery']
        restored=type(store)(config)
        assert restored.get_envelope(sid)==store.get_envelope(sid)
        assert restored.processing_history_input(sid)==store.processing_history_input(sid)


@pytest.mark.parametrize('azure',[False,True])
def test_tree_cutover_preserves_original_evidence_and_mutable_graph_commands(tmp_path,production_console,monkeypatch,azure):
    from tests.production_support import restart_production
    from tests.decision_tree_test_support import install_fragment_proposer
    from tests.test_decision_graph_chain import _accounts,ingest,complete_graph,command
    from src.vorming.decision_graph_v1 import verify_source_evidence
    from src.workflows.processing_archives_v1 import TREE_FIELDS
    from src.g2_source_store import AzureBlobSourceStore
    from tests.test_a10_source_cache_repair import DiskBlobTransport
    source=AzureBlobSourceStore(blob_service_client=DiskBlobTransport(tmp_path/'immutable'))
    console=production_console(root=tmp_path,azure=azure,processing_binder=install_fragment_proposer,
        immutable_source_store=source)
    accounts=_accounts(console)
    sid=ingest(console,accounts)['snapshot_id']
    store=console.workflow_document_store
    original=store.get_envelope(sid)
    graph=complete_graph(console,sid)
    store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    header=store.get_envelope(sid)
    assert not TREE_FIELDS & set(header)
    assert header['tree_source_route']
    assert store.processing_history_input(sid)==original
    verify_source_evidence(console,store.tree_input(header))
    submitted=command(console,accounts,sid,'compact-graph',graph=graph)
    console.update_decision_graph(**submitted)
    with monkeypatch.context() as broken:
        def unavailable(*args,**kwargs):
            raise AssertionError('Idempotent receipt must not re-read source bytes')
        broken.setattr(console,'_verified_source_bytes',unavailable)
        assert console.update_decision_graph(**submitted)['idempotent']
    saved=store.get_envelope(sid)['decision_graph']
    assert saved['edges']==graph['edges'] and saved['unresolved']==[]
    current={o['object_id']:o['object_version'] for o in console.snapshot_objects(sid)}
    assert all(n['object_version']==current[n['object_id']] for n in saved['nodes'])
    assert not TREE_FIELDS & set(store.get_envelope(sid))
    restarted=restart_production(console)
    assert restarted._tree_envelope(sid)['decision_graph_evidence']==original['decision_graph_evidence']
    assert not restarted.publication_readiness(sid)['publish_allowed']
    for obj in restarted.snapshot_objects(sid):
        if obj['object_type']!='document':
            restarted.review_object(actor_id=accounts['researcher']['account_id'],snapshot_id=sid,
                object_id=obj['object_id'],decision='approve',confirmed_object_type='node')
    refreshed=deepcopy(restarted._envelope(sid)['decision_graph'])
    current={o['object_id']:o['object_version'] for o in restarted.snapshot_objects(sid)}
    for node in refreshed['nodes']:
        node['object_version']=current[node['object_id']]
    restarted.update_decision_graph(**command(restarted,accounts,sid,'compact-final-graph',graph=refreshed))
    restarted.confirm_decision_graph(**command(restarted,accounts,sid,'compact-confirm'))
    source_reads=[]
    native_tree=restarted.workflow_document_store.tree_input
    def measured_tree(*args,**kwargs):
        from src.workflows.workflow_transaction_v1 import workflow_transaction_active
        source_reads.append(workflow_transaction_active())
        return native_tree(*args,**kwargs)
    monkeypatch.setattr(restarted.workflow_document_store,'tree_input',measured_tree)
    result=restarted.publish(actor_id=accounts['publisher']['account_id'],snapshot_id=sid)
    assert result['status']=='PASS',result
    assert source_reads==[False], 'Publication must prepare archive input before its lock'
    release=restarted.canonical_publication_store.release_for_snapshot(sid)
    assert release['decision_graph_release']['evidence']==original['decision_graph_evidence']
    assert restarted.publish(actor_id=accounts['publisher']['account_id'],snapshot_id=sid)['release_id']==result['release_id']


@pytest.mark.parametrize('runs',[1,25])
def test_operational_bytes_and_writes_stay_bounded_as_history_grows(incomplete_document,runs,monkeypatch):
    import time
    from psycopg.types.json import _JsonLoader,set_json_loads
    console,sid,_,_=incomplete_document
    store=console.workflow_document_store
    envelope=store.get_envelope(sid)
    envelope['quality_processing_runs'] += [dict(run_id=f'growth-{i}',raw_provider='synthetic evidence '*65536)
        for i in range(runs)]
    store.write_bundle(envelope=envelope)
    store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    with store._connect() as con:
        original=con.execute('SELECT md5(envelope_payload::text) AS hash,octet_length(envelope_payload::text) AS bytes FROM workflow.documents WHERE snapshot_id=%s',(sid,)).fetchone()
        physical=con.execute('SELECT pg_column_size(metadata)+pg_column_size(refs) AS bytes FROM workflow.document_inputs WHERE snapshot_id=%s',(sid,)).fetchone()['bytes']
    import psycopg
    from contextlib import contextmanager
    native_loads=_JsonLoader._loads
    native_execute=psycopg.Connection.execute
    native_connect=store._connect
    executes=[]
    fetches=[]
    transactions=[]
    class MeasuredCursor:
        def __init__(self,cursor):
            self.cursor=cursor
        def __getattr__(self,name):
            return getattr(self.cursor,name)
        def fetchone(self):
            result=self.cursor.fetchone()
            fetches.append(1 if result is not None else 0)
            return result
        def fetchall(self):
            result=self.cursor.fetchall()
            fetches.append(len(result))
            return result
    def measured_execute(connection,*args,**kwargs):
        started=time.perf_counter()
        result=native_execute(connection,*args,**kwargs)
        executes.append(time.perf_counter()-started)
        return MeasuredCursor(result)
    @contextmanager
    def measured_connection():
        started=time.perf_counter()
        with native_connect() as con:
            yield con
        transactions.append(time.perf_counter()-started)
    transferred=[]
    def measured(data):
        transferred.append(len(data))
        return native_loads(data)
    set_json_loads(measured)
    started=time.perf_counter()
    try:
        with monkeypatch.context() as measure:
            measure.setattr(psycopg.Connection,'execute',measured_execute)
            measure.setattr(store,'_connect',measured_connection)
            header=store.get_envelope(sid)
            header['title']='Metadata remains operational'
            store.write_bundle(envelope=header)
            assert store.get_envelope(sid)['title']==header['title']
            assert console.processing_status(sid)['formation_incomplete']
    finally:
        set_json_loads(native_loads)
    elapsed=time.perf_counter()-started
    assert max(transferred)<64000
    assert sum(transferred)<256000
    assert physical<16000
    with store._connect() as con:
        assert con.execute('SELECT md5(envelope_payload::text) AS hash FROM workflow.documents WHERE snapshot_id=%s',(sid,)).fetchone()['hash']==original['hash']
    print('OPERATIONAL_IO',dict(runs=runs,historical_bytes=original['bytes'],compact_bytes=physical,
        largest_json=max(transferred),total_json=sum(transferred),executes=len(executes),fetches=len(fetches),
        sql_seconds=round(sum(executes),4),lock_upper_bound_seconds=round(max(transactions),4),seconds=round(elapsed,4)))


@pytest.mark.parametrize('phase',['BEFORE','AFTER'])
def test_real_sql_failure_rolls_back_layout_pin_and_allows_same_preparation(incomplete_document,phase):
    import psycopg
    console,sid,_,_=incomplete_document
    store=console.workflow_document_store
    before=store.get_envelope(sid)
    prepared=store.prepare_operational_inputs(sid)
    with store._connect() as con:
        con.execute("CREATE FUNCTION workflow.test_refuse_cutover() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected_cutover_failure'; END $$")
        con.execute(f"CREATE TRIGGER test_refuse_cutover {phase} UPDATE OF document_storage_version ON workflow.documents FOR EACH ROW WHEN(NEW.document_storage_version=1) EXECUTE FUNCTION workflow.test_refuse_cutover()")
    with pytest.raises(psycopg.Error,match='injected_cutover_failure'):
        store.activate_operational_inputs(prepared)
    assert store.get_envelope(sid)==before
    with store._connect() as con:
        assert con.execute('SELECT document_storage_version FROM workflow.documents WHERE snapshot_id=%s',(sid,)).fetchone()['document_storage_version']==0
        con.execute('DROP TRIGGER test_refuse_cutover ON workflow.documents')
        con.execute('DROP FUNCTION workflow.test_refuse_cutover()')
    store.activate_operational_inputs(prepared)
    assert store.processing_history_input(sid)==before


def test_prepared_shapes_are_bound_to_original_history(incomplete_document):
    import psycopg
    console,sid,_,_=incomplete_document
    store=console.workflow_document_store
    prepared=store.prepare_operational_inputs(sid)
    with pytest.raises(psycopg.Error,match='preparation_shape_changed'):
        with store._connect() as con:
            con.execute("UPDATE workflow.document_inputs SET refs=jsonb_set(refs,'{shapes,quality_processing_runs}','\"absent\"') WHERE snapshot_id=%s",(sid,))
    store.activate_operational_inputs(prepared)
    with pytest.raises(psycopg.Error,match='reference_kind_invalid'):
        with store._connect() as con:
            con.execute("UPDATE workflow.document_inputs SET refs=jsonb_set(refs,'{quality}',refs->'replay') WHERE snapshot_id=%s",(sid,))
    assert store.processing_history_input(sid)['quality_processing_runs']


@pytest.mark.parametrize('azure',[False,True])
def test_full_ingest_uses_existing_worker_with_new_compact_admission(tmp_path,production_console,monkeypatch,azure):
    from tests.decision_tree_test_support import install_fragment_proposer
    from tests.test_decision_graph_chain import _accounts,ingest
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE','v1')
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE','v1')
    from src.g2_source_store import AzureBlobSourceStore
    from tests.test_a10_source_cache_repair import DiskBlobTransport
    source=AzureBlobSourceStore(blob_service_client=DiskBlobTransport(tmp_path/'immutable'))
    console=production_console(root=tmp_path,azure=azure,processing_binder=install_fragment_proposer,
        immutable_source_store=source)
    sid=ingest(console,_accounts(console))['snapshot_id']
    store=console.workflow_document_store
    header=store.get_envelope(sid)
    assert header['_document_inputs']['formation_variant']=='tree'
    assert header['decision_graph']
    assert store.tree_input(header)['decision_graph_evidence']['items']
    assert store.processing_command_input(header)['processing_attempts'][-1]['state']=='succeeded'
    with store._connect() as con:
        original=con.execute('SELECT envelope_payload FROM workflow.documents WHERE snapshot_id=%s',(sid,)).fetchone()['envelope_payload']
    assert not {'decision_graph_evidence','decision_tree_formation','semantic_replay'} & set(original)


def test_explicit_legacy_source_input_keeps_latest_accepted_extraction(tmp_path,production_console,monkeypatch):
    from tests.test_review_formation_problems import received
    from tests.test_docling_contract_v1 import result
    from src.vorming.docling_contract_v1 import translate,stored_fragments
    from src.settings.quality_evidence_v1 import record_processing
    console,sid,*_=received(tmp_path,production_console,monkeypatch)
    store=console.workflow_document_store
    envelope=store.get_envelope(sid)
    payload={**result(),'source_sha256':envelope['sha256']}
    fragments=translate(payload,document_id=envelope['document_id'],source_id=envelope['source_id'],source_sha256=envelope['sha256'])
    record_processing(envelope,[],fragments=fragments,replay=None,started_at='accepted')
    record_processing(envelope,[],fragments=[],replay=None,started_at='classification')
    record_processing(envelope,[],fragments=[],replay=None,started_at='failed',outcome='blocked',reason='docling_timeout')
    original=stored_fragments(envelope)
    store.write_bundle(envelope=envelope)
    store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    source=store.source_input(store.get_envelope(sid))
    assert stored_fragments(source)==original==fragments
    assert len(source['quality_processing_runs'])==1
    assert 'candidates' not in source['quality_processing_runs'][0]
