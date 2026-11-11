"""Human selections on the actual workflow database and production HTTP app.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4
from dataclasses import asdict
import json
import subprocess
import sys
import psycopg

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_v1 as annotation
from tests.production_support import restart_production
from starlette.testclient import TestClient


def source(production_console, tmp_path):
    console = production_console(root=tmp_path)
    researcher = console.create_account(username='annotator',password='annotation-secret',roles=('researcher',))
    reviewer = console.create_account(username='observer',password='annotation-secret',roles=('reviewer',))
    actor = researcher['account_id']
    sid = console.receive_source(actor_id=actor,filename='annotation.html',content_type='text/html',
        data='<html><body><h1>Advies</h1><p>Controleer 👩🏽‍⚕️ de huid bij café.</p><p>Alleen bij klachten.</p><p>Gelijke tekst. Gelijke tekst.</p><p>Herhaalde paragraaf.</p><p>Herhaalde paragraaf.</p><p>Onderzoek beschrijft de bevinding.</p></body></html>'.encode(),
        ingest_kind='new',title='Annotatieproef',version='1.0',date='2026-11-08',live_url='',class_='richtlijn',family='test',named_reviewers=[reviewer['account_id']])['snapshot_id']
    before = console.workflow_document_store.get_envelope(sid)
    view = annotation.prepare(console,actor_id=actor,snapshot_id=sid,expected_revision=console.objects_revision(sid))
    return console, actor, reviewer, sid, view, before


def anchor(view, text, *, role='core', start=0, end=None, function=None):
    block = next(b for b in view['blocks'] if text in b['text'])
    end = len(block['text']) if end is None else end
    return {'block_id':block['block_id'],'start':start,'end':end,'quote':block['text'][start:end],
        'role':role,'required_for_meaning':role in {'condition','exception'},'evidence_function':function}


def command(view, *, ranges=None, status='draft'):
    return dict(snapshot_id=view['snapshot_id'],command_id=str(uuid4()),annotation_id=str(uuid4()),expected_revision=0,
        expected_generation=view['generation'],extraction_hash=view['extraction_hash'],normalization=view['normalization'],
        selection={'status':status,'object_type':'recommendation','ranges':ranges or [],'evidence_not_applicable':False})


@pytest.mark.parametrize('storage',['legacy','v1'])
def test_save_pause_restart_multiple_ranges_overview_and_exact_commands(tmp_path, production_console, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE',storage)
    if storage=='v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE','v1')
    console, actor, reviewer, sid, view, before = source(production_console,tmp_path)
    ranges = [anchor(view,'Controleer'),anchor(view,'Alleen',role='condition'),
        anchor(view,'Onderzoek',role='evidence',function='supported_by')]
    request = command(view,ranges=ranges)
    result = annotation.save(console,actor_id=actor,**request)
    assert result['revision']==1 and result['generation']==1
    assert annotation.save(console,actor_id=actor,**request)==result
    changed = deepcopy(request); changed['selection']['status']='uncertain'
    with pytest.raises(ConsoleError,match='annotation_command_conflict'):
        annotation.save(console,actor_id=actor,**changed)
    # Fresh production composition and store; no old Python state is retained.
    resumed = restart_production(console)
    loaded = annotation.overview(resumed,actor_id=actor,snapshot_id=sid)
    probe = subprocess.run([sys.executable,'-c',
        "import json,sys; from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig; "
        "from tests.production_support import production_application; "
        "from src.vorming.human_annotation_v1 import overview; "
        "p=json.load(sys.stdin); c=production_application(p['root'],PostgresCanonicalConfig(**p['config'])).state.operations_kernel; "
        "print(json.dumps(overview(c,actor_id=p['actor'],snapshot_id=p['sid'])))"],
        input=json.dumps({'root':str(console.root),'config':asdict(console.workflow_document_store.config),'actor':actor,'sid':sid}),
        text=True,capture_output=True,timeout=60,check=True)
    assert json.loads(probe.stdout.splitlines()[-1])==loaded
    assert loaded['entries'][0]['ranges']==[{**a,'quote_sha256':loaded['entries'][0]['ranges'][i]['quote_sha256']} for i,a in enumerate(ranges)]
    assert loaded['entries'][0]['status']=='draft'
    ready = {**request,'command_id':str(uuid4()),'expected_revision':1,'expected_generation':1,
        'selection':{**request['selection'],'status':'ready'}}
    annotation.save(resumed,actor_id=actor,**ready)
    final = annotation.overview(resumed,actor_id=actor,snapshot_id=sid)
    assert final['entries'][0]['status']=='ready'
    assert final['overview_hash']!=loaded['overview_hash']
    assert final['entries'][0]['ranges'][1]['required_for_meaning']
    assert resumed.workflow_document_store.get_envelope(sid)==before
    assert resumed.snapshot_objects(sid,include_blocked=True)==[]
    assert resumed.object_review_bindings(sid)==[]
    with resumed.workflow_document_store._connect() as con:
        stored = con.execute('SELECT payload FROM workflow.annotation_versions WHERE snapshot_id=%s ORDER BY revision',(sid,)).fetchall()
        assert len(stored)==2
        assert all('quote' not in a for r in stored for a in r['payload']['ranges'])
    with pytest.raises(ConsoleError,match='annotation_source_owned'):
        resumed.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='old-ai',expected_revision=resumed.objects_revision(sid))
    with pytest.raises(ConsoleError,match='annotation_source_owned'):
        resumed._fragments_and_spec('html',None,formation_context={'snapshot_id':sid})


def test_concurrent_commands_serialize_and_retry_identically(tmp_path, production_console):
    console, actor, _, sid, view, _ = source(production_console,tmp_path)
    other = restart_production(console)
    a = command(view,ranges=[anchor(view,'Controleer')]); b = command(view,ranges=[anchor(view,'Alleen')])
    def send(kernel, request):
        try: return annotation.save(kernel,actor_id=actor,**request)
        except ConsoleError as exc: return exc.code
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda pair:send(*pair),[(console,a),(other,b)]))
    assert sum(isinstance(r,dict) for r in results)==1
    assert 'annotation_write_conflict' in results
    final = annotation.overview(console,actor_id=actor,snapshot_id=sid)
    assert final['generation']==1 and len(final['entries'])==1
    winning = a if isinstance(results[0],dict) else b
    with ThreadPoolExecutor(2) as pool:
        retries = list(pool.map(lambda kernel:send(kernel,winning),[console,other]))
    assert retries[0]==retries[1]
    assert annotation.overview(console,actor_id=actor,snapshot_id=sid)['generation']==1


def test_unicode_duplicate_positions_stale_witness_and_roles(tmp_path, production_console):
    console, actor, reviewer, sid, view, _ = source(production_console,tmp_path)
    repeated = next(b for b in view['blocks'] if b['text']=='Gelijke tekst. Gelijke tekst.')
    n = len('Gelijke tekst.')
    ranges = [anchor(view,'Gelijke',end=n),anchor(view,'Gelijke',start=n+1)]
    assert ranges[0]['quote']==ranges[1]['quote']
    annotation.save(console,actor_id=actor,**command(view,ranges=ranges))
    view = annotation.overview(console,actor_id=actor,snapshot_id=sid)
    assert len(view['entries'][0]['ranges'])==2
    assert view['entries'][0]['ranges'][0]['block_id']==repeated['block_id']
    copies=[b for b in view['blocks'] if b['text']=='Herhaalde paragraaf.']
    assert len(copies)==2 and copies[0]['block_id']!=copies[1]['block_id']
    multiple=[{'block_id':b['block_id'],'start':0,'end':len(b['text']),'quote':b['text'],
        'role':'core','required_for_meaning':False,'evidence_function':None} for b in copies]
    annotation.save(console,actor_id=actor,**command(view,ranges=multiple))
    view=annotation.overview(console,actor_id=actor,snapshot_id=sid)
    def rejected(change, code):
        request = command(view,ranges=[anchor(view,'Controleer')]); change(request)
        with pytest.raises(ConsoleError,match=code): annotation.save(console,actor_id=actor,**request)
        assert annotation.overview(console,actor_id=actor,snapshot_id=sid)['generation']==view['generation']
    rejected(lambda r:r.update(extraction_hash='old'), 'annotation_representation_stale')
    rejected(lambda r:r['selection']['ranges'][0].update(quote='Andere tekst'), 'annotation_anchor_mismatch')
    text = next(b['text'] for b in view['blocks'] if 'Controleer' in b['text'])
    rejected(lambda r:r['selection']['ranges'][0].update(end=text.index('👩')+1), 'annotation_grapheme_boundary_invalid')
    rejected(lambda r:r['selection'].update(status='ready'), 'annotation_evidence_required')
    rejected(lambda r:r['selection']['ranges'][0].update(role='evidence'), 'annotation_evidence_function_required')
    with pytest.raises(ConsoleError,match='reviewer_not_named_on_snapshot|researcher_role_required'):
        other = console.create_account(username='outsider',password='annotation-secret',roles=('reviewer',))
        annotation.save(console,actor_id=other['account_id'],**command(view))
    # Changing an evidence function revises the original annotation. Separate
    # entries with the same exact core are now explicitly refused (choice 1).
    evidence_request = None
    for function in annotation.EVIDENCE_FUNCTIONS:
        view = annotation.overview(console,actor_id=actor,snapshot_id=sid)
        if evidence_request is None:
            evidence_request=command(view,ranges=[anchor(view,'Controleer'),anchor(view,'Onderzoek',role='evidence',function=function)],status='ready')
        else:
            evidence_request.update(command_id=str(uuid4()),expected_generation=view['generation'],expected_revision=1)
            evidence_request['selection']['ranges'][-1]['evidence_function']=function
        annotation.save(console,actor_id=actor,**evidence_request)



def test_http_source_and_autosave_contract(tmp_path, production_console, production_app):
    console, actor, reviewer, sid, view, _ = source(production_console,tmp_path)
    client = TestClient(production_app(console),base_url='https://testserver')
    assert client.post('/login',data={'username':'annotator','password':'annotation-secret'},follow_redirects=False).status_code==303
    response = client.get('/annotations?document='+sid)
    assert response.status_code==200
    assert 'Gebruik als kernuitspraak' in response.text and 'data-source-block' in response.text
    request = command(view,ranges=[anchor(view,'Controleer'),anchor(view,'Alleen',role='condition')])
    saved = client.post('/annotations/api',json=request)
    assert saved.status_code==200, saved.text
    assert client.post('/annotations/api',json=request).json()==saved.json()
    stale = client.post('/annotations/api',json=command(view,ranges=[]))
    assert stale.status_code==409 and stale.json()['error']=='annotation_write_conflict'
    summary = client.get('/annotations?document='+sid+'&overview=true')
    assert summary.status_code==200 and 'Voorwaarde' in summary.text and 'Selectie nog niet gereed' in summary.text
    assert client.get('/annotations/api',params={'document':sid}).json()['entries'][0]['ranges'][0]['quote']==request['selection']['ranges'][0]['quote']
    original = client.get('/annotations/original',params={'document':sid})
    assert original.status_code==200 and original.headers['content-disposition'].startswith('attachment')
    script = client.get('/annotations/editor.js')
    assert script.status_code==200
    binding_script = client.get('/annotations/binding.mjs')
    assert binding_script.status_code == 200 and 'export function bindRange' in binding_script.text
    malformed=deepcopy(request);malformed['selection']['object_type']=[]
    assert client.post('/annotations/api',json=malformed).status_code==422
    malformed=deepcopy(request);malformed['selection']['ranges'][0]['block_id']=[]
    assert client.post('/annotations/api',json=malformed).status_code==422
    assert client.post('/annotations/api',content='invalid json',headers={'Content-Type':'application/json'}).status_code==422
    assert client.get('/source-selection',params={'document':sid}).url.path=='/annotations'


def test_failed_command_rolls_back_history_head_and_generation(tmp_path, production_console, monkeypatch):
    console, actor, _, sid, view, _ = source(production_console,tmp_path)
    original = annotation._json_text
    def fail_receipt(value):
        if 'generation' in value:
            raise RuntimeError('injected_before_receipt_commit')
        return original(value)
    with monkeypatch.context() as patch:
        patch.setattr(annotation,'_json_text',fail_receipt)
        with pytest.raises(RuntimeError,match='injected_before_receipt_commit'):
            annotation.save(console,actor_id=actor,**command(view,ranges=[anchor(view,'Controleer')]))
    assert annotation.overview(console,actor_id=actor,snapshot_id=sid)['generation']==0
    with console.workflow_document_store._connect() as con:
        for table in ('annotation_versions','annotation_heads','annotation_commands'):
            assert con.execute(f'SELECT count(*) AS n FROM workflow.{table} WHERE snapshot_id=%s',(sid,)).fetchone()['n']==0
    annotation.save(console,actor_id=actor,**command(view,ranges=[anchor(view,'Controleer')]))


def test_current_authorization_and_source_version_checked_on_every_save(tmp_path, production_console):
    console, actor, _, sid, view, _ = source(production_console,tmp_path)
    request=command(view,ranges=[anchor(view,'Controleer')])
    annotation.save(console,actor_id=actor,**request)
    console.workflow_identity_store.update_roles(actor,['publisher'])
    with pytest.raises(ConsoleError,match='researcher_role_required'):
        annotation.save(console,actor_id=actor,**request)  # Even an exact duplicate reauthorizes.
    console.workflow_identity_store.update_roles(actor,['researcher'])
    with pytest.raises(psycopg.errors.RaiseException,match='annotation_source_immutable'):
        with console.workflow_document_store._connect() as con:
            con.execute("UPDATE workflow.documents SET source_version='2.0' WHERE snapshot_id=%s",(sid,))
    assert annotation.save(console,actor_id=actor,**request)['generation']==1


def test_rollback_writer_cannot_activate_or_reserve_over_human_input(tmp_path, production_console):
    console, actor, _, sid, view, _ = source(production_console,tmp_path)
    with pytest.raises(psycopg.errors.RaiseException,match='annotation_activation_not_available'):
        with console.workflow_document_store._connect() as con:
            con.execute("INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,position) VALUES(%s,'bypass','1','{}',0)",(sid,))
    with pytest.raises(psycopg.errors.RaiseException,match='annotation_source_owned'):
        with console.workflow_document_store._connect() as con:
            con.execute("INSERT INTO workflow.processing_attempts(attempt_id,snapshot_id,command_id,started_at,object_generation,payload) VALUES('bypass',%s,'old-worker',CURRENT_TIMESTAMP,0,'{}')",(sid,))
    assert console.snapshot_objects(sid,include_blocked=True)==[]
    assert annotation.overview(console,actor_id=actor,snapshot_id=sid)['generation']==0
    # A pre-034 runtime has no privileges on annotation tables. The trigger
    # still enforces ownership, without granting that runtime annotation access.
    from psycopg import sql
    role='annotation_old_'+uuid4().hex
    with psycopg.connect(console.workflow_document_store.config.dsn,autocommit=True) as con:
        con.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
        try:
            con.execute(sql.SQL('GRANT USAGE ON SCHEMA workflow TO {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('GRANT SELECT,UPDATE ON workflow.documents TO {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('GRANT SELECT ON workflow.document_inputs TO {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE ON workflow.document_objects,workflow.object_revision_frontiers,'
                'workflow.review_fact_state,workflow.review_object_facts TO {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
            with pytest.raises(psycopg.errors.RaiseException,match='annotation_activation_not_available'):
                con.execute("INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,position) VALUES(%s,'old-role-bypass','1','{}',0)",(sid,))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                con.execute('SELECT * FROM workflow.annotation_sets')
        finally:
            con.execute('RESET ROLE')
            con.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            con.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


def test_unfinished_selection_resumes_and_cannot_be_marked_ready(tmp_path, production_console):
    console, actor, _, sid, view, _ = source(production_console,tmp_path)
    pending=anchor(view,'Controleer',end=len('Controleer 👩🏽‍⚕️'))
    request=command(view)
    request['selection']['pending_range']=pending
    annotation.save(console,actor_id=actor,**request)
    resumed=restart_production(console)
    saved=annotation.overview(resumed,actor_id=actor,snapshot_id=sid)
    assert saved['entries'][0]['pending_range']['quote']==pending['quote']
    assert saved['entries'][0]['ranges']==[]
    ready={**request,'command_id':str(uuid4()),'expected_revision':1,'expected_generation':1,
        'selection':{**request['selection'],'status':'ready','evidence_not_applicable':True}}
    with pytest.raises(ConsoleError,match='annotation_pending_range'):
        annotation.save(resumed,actor_id=actor,**ready)
    ready['selection']['ranges']=[pending];ready['selection']['pending_range']=None
    annotation.save(resumed,actor_id=actor,**ready)
    assert annotation.overview(resumed,actor_id=actor,snapshot_id=sid)['entries'][0]['status']=='ready'


def test_existing_unpublished_delete_cleans_annotation_input_atomically(tmp_path, production_console):
    console, actor, _, sid, view, _ = source(production_console,tmp_path)
    annotation.save(console,actor_id=actor,**command(view,ranges=[anchor(view,'Controleer')]))
    console.delete_unpublished_snapshot(actor_id=actor,snapshot_id=sid,confirmed=True,confirm_title='Annotatieproef')
    with console.workflow_document_store._connect() as con:
        for table in ('annotation_sets','annotation_versions','annotation_heads','annotation_commands'):
            assert con.execute(f'SELECT count(*) AS n FROM workflow.{table} WHERE snapshot_id=%s',(sid,)).fetchone()['n']==0


@pytest.mark.parametrize('storage',['legacy','v1'])
def test_annotation_backup_restores_history_pending_commands_and_ownership(tmp_path, production_console, monkeypatch, storage):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from tests.postgres_support import database, install_schema
    from tests.production_support import production_application
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE',storage)
    if storage=='v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE','v1')
    console, actor, _, sid, view, _ = source(production_console,tmp_path)
    request=command(view,ranges=[anchor(view,'Controleer'),anchor(view,'Alleen',role='condition')])
    first=annotation.save(console,actor_id=actor,**request)
    second={**request,'command_id':str(uuid4()),'expected_revision':1,'expected_generation':1,
        'selection':{**request['selection'],'pending_range':anchor(view,'Onderzoek',role='evidence',function='explains')}}
    annotation.save(console,actor_id=actor,**second)
    # A withdrawn entry is durable history too; physical archive row order is irrelevant.
    latest=annotation.overview(console,actor_id=actor,snapshot_id=sid)
    annotation.save(console,actor_id=actor,**command(latest,status='withdrawn'))
    expected=annotation.overview(console,actor_id=actor,snapshot_id=sid)
    adapter=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config))
    state=adapter.export_state()
    assert len(state['formation_recovery']['tables']['annotation_versions'])==3
    reordered=deepcopy(state)
    for rows in reordered['formation_recovery']['tables'].values():
        rows.reverse()
    with database(console.workflow_document_store.config.dsn) as target_config:
        install_schema(target_config.dsn)
        target=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target_config))
        target.restore_state(reordered)
        assert target.export_state()['formation_recovery']==state['formation_recovery']
        restored=production_application(console.root,target_config,runtime=console.runtime,
            source_store=console.source_store).state.operations_kernel
        assert annotation.overview(restored,actor_id=actor,snapshot_id=sid)==expected
        assert annotation.save(restored,actor_id=actor,**request)==first
        with pytest.raises(ConsoleError,match='annotation_source_owned'):
            restored.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id='restore-old-ai',
                expected_revision=restored.objects_revision(sid))
        third={**second,'command_id':str(uuid4()),'expected_revision':2,'expected_generation':3}
        assert annotation.save(restored,actor_id=actor,**third)['revision']==3
        assert annotation.overview(restart_production(restored),actor_id=actor,snapshot_id=sid)['generation']==4


@pytest.mark.parametrize('corruption',['table','section','null_section','history','head','receipt','witness','source','payload_hash'])
def test_annotation_backup_rejects_partial_or_changed_input_atomically(tmp_path, production_console, corruption):
    from src.integrity_kernel import stable_hash
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.publication.publication_chain_recovery_v1 import PublicationChainRecoveryError
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from tests.postgres_support import database, install_schema
    console, actor, _, sid, view, _ = source(production_console,tmp_path)
    request=command(view,ranges=[anchor(view,'Controleer'),anchor(view,'Alleen',role='condition')])
    annotation.save(console,actor_id=actor,**request)
    annotation.save(console,actor_id=actor,**{**request,'command_id':str(uuid4()),'expected_revision':1,'expected_generation':1})
    adapter=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config))
    state=adapter.export_state()
    tables=state['formation_recovery']['tables']
    if corruption=='table': del tables['annotation_commands']
    elif corruption=='section': del state['formation_recovery']
    elif corruption=='null_section': state['formation_recovery']=None
    elif corruption=='history': tables['annotation_versions'].pop(0)
    elif corruption=='head': tables['annotation_heads'][0]['revision']=1
    elif corruption=='receipt': tables['annotation_commands'].pop()
    elif corruption=='witness':
        # Even a self-consistent replacement payload hash cannot repair a
        # false quote witness in an older, no-longer-current entry version.
        row=tables['annotation_versions'][0]
        row['payload']['ranges'][0]['quote_sha256']='0'*64
        row['payload_hash']=stable_hash(row['payload'])
    elif corruption=='source': tables['annotation_sets'][0]['source_identity']['version']='wrong'
    elif corruption=='payload_hash': tables['annotation_versions'][0]['payload_hash']='0'*64
    with database(console.workflow_document_store.config.dsn) as target_config:
        install_schema(target_config.dsn)
        target=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target_config))
        with pytest.raises(PublicationChainRecoveryError):
            target.restore_state(state)
        target.assert_empty()


@pytest.mark.parametrize('old_version,section_version',[(7,None),(8,1),(9,2),(9,None)])
def test_pre_annotation_backup_upgrades_without_inventing_selections(tmp_path, production_console, old_version, section_version):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter, _upgrade_workflow_state
    from src.workflows.formation_recovery_v1 import ANNOTATION_TABLES, NEW_TABLES, BUILD_TABLES
    from tests.postgres_support import database, install_schema
    console=production_console(root=tmp_path)
    current=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config)).export_state()
    legacy=deepcopy(current)
    legacy['workflow_recovery_version']=old_version
    legacy['formation_recovery']['version']=section_version
    for name in (*ANNOTATION_TABLES, *BUILD_TABLES):
        del legacy['formation_recovery']['tables'][name]
    if section_version==1:
        for name in NEW_TABLES:
            del legacy['formation_recovery']['tables'][name]
    if section_version is None:
        del legacy['formation_recovery']
    original=deepcopy(legacy)
    upgraded=_upgrade_workflow_state(legacy)
    assert upgraded=={**current,'formation_recovery':None} if section_version is None else upgraded==current
    assert legacy==original
    with database(console.workflow_document_store.config.dsn) as target_config:
        install_schema(target_config.dsn)
        target=PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target_config))
        target.restore_state(legacy)
        assert target.export_state()['formation_recovery']==current['formation_recovery']
