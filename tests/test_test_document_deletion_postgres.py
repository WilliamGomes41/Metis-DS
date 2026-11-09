"""Publisher test reset at the native workflow/canonical boundary.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
from uuid import uuid4

import pytest
from src.documents import test_document_deletion_v1 as deletion
from src.operations_console_v1 import ConsoleError
from tests.production_support import restart_production
from tests.test_vsa_publish_readiness_ui_v1 import _console_with_document, _complete_review
from tests.test_vsa_publish_readiness_ui_v1 import HTML_FIXTURE, TEST_PASSWORD


def published(production_console, tmp_path):
    console, accounts, received, source = _console_with_document(tmp_path, production_console=production_console)
    _complete_review(console, accounts, received)
    release = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=received['snapshot_id'])
    return console, accounts, received['snapshot_id'], release, source


def command(console, accounts, sid):
    view = deletion.preview(console, actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    return dict(actor_id=accounts['publisher']['account_id'], snapshot_id=sid,
        command_id=uuid4().hex, expected_plan=view['fingerprint'], confirm_title=view['title'],
        reason='Testdocument opruimen voor een schone annotatieproef.', confirmed_test=True)


def receive(console, accounts, *, prior=None, version='2.0', title='Continentie fixture'):
    return console.receive_source(actor_id=accounts['researcher']['account_id'],
        filename='source-'+version+'.html',data=HTML_FIXTURE.read_bytes()+('<!--'+title+version+'-->').encode(),
        content_type='text/html',ingest_kind='new_version' if prior else 'new',
        replaces_snapshot_id=prior,title=title,version=version,date='2026-11-09',live_url='',
        class_='richtlijn',family='continentie',
        named_reviewers=[accounts['researcher']['account_id'],accounts['reviewer']['account_id']])['snapshot_id']


def form_source(console, accounts, sid):
    actor = accounts['researcher']['account_id']
    attempt, _ = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,
        command_id=uuid4().hex,expected_revision=console.objects_revision(sid))
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    _complete_review(console,accounts,{'snapshot_id':sid})
    return console.publish(actor_id=accounts['publisher']['account_id'],snapshot_id=sid)


def test_published_document_reset_is_durable_idempotent_and_preserves_review_chain(production_console, tmp_path, monkeypatch):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION', 'on')
    console, accounts, sid, release, source = published(production_console, tmp_path)
    before_events = console.workflow_review_store.read_events()
    request = command(console, accounts, sid)
    result = deletion.delete(console, **request)
    assert result['deleted'] and result['snapshot_ids'] == [sid] and result['publications'] == 1
    assert console.workflow_review_store.read_events()[:-1] == before_events
    assert console.canonical_publication_store.active_publication_rows() == []
    with console.workflow_document_store._connect() as con:
        for table in ('workflow.documents','workflow.document_objects','workflow.annotation_sets',
                      'workflow.publish_authorizations','public.source_snapshots','public.publication_releases',
                      'public.canonical_object_versions'):
            assert con.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] == 0
        assert con.execute('SELECT count(*) AS n FROM workflow.deleted_test_snapshots').fetchone()['n'] == 1
    resumed = restart_production(console)
    assert resumed.list_envelopes() == []
    assert deletion.delete(resumed, **request) == result
    assert deletion.receipt(resumed, actor_id=request['actor_id'], command_id=request['command_id']) == result
    with pytest.raises(ConsoleError, match='command_conflict'):
        deletion.delete(resumed, **{**request,'reason':'Een ander verzoek met dezelfde sleutel.'})


@pytest.mark.parametrize('storage',['legacy','v1'])
def test_whole_lineage_reset_removes_annotations_and_serving_but_preserves_other_document(
        production_console,tmp_path,monkeypatch,storage):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE',storage)
    if storage == 'v1': monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE','v1')
    console, accounts, first, release, source = published(production_console,tmp_path)
    second = receive(console,accounts,prior=first)
    form_source(console,accounts,second)
    draft = receive(console,accounts,prior=second,version='3.0')
    from src.vorming import human_annotation_v1 as annotation
    from tests.test_human_annotation_postgres import anchor, command as selection
    view = annotation.prepare(console,actor_id=accounts['researcher']['account_id'],snapshot_id=draft,
                              expected_revision=console.objects_revision(draft))
    annotation.save(console,actor_id=accounts['researcher']['account_id'],
                    **selection(view,ranges=[anchor(view,'Bespreek het onderwerp')]))
    other = receive(console,accounts,title='Ander document',version='1.0')
    other_release = form_source(console,accounts,other)
    other_rows = [r for r in console.canonical_publication_store.active_publication_rows()
                  if r['publication']['release_id'] == other_release['release_id']]
    with console.workflow_document_store._connect() as con:
        original = con.execute('SELECT to_jsonb(d) AS record FROM workflow.documents d WHERE snapshot_id=%s',(first,)).fetchone()['record']
        old_objects = con.execute('SELECT c.canonical_json FROM public.canonical_object_versions c '
            'JOIN public.canonical_object_sources s USING(object_id,object_version) WHERE s.snapshot_id=%s',(second,)).fetchall()
    from starlette.testclient import TestClient
    from src.product_api_v1 import create_product_app
    from tests.test_product_api_v1 import paths,registry,headers
    public = TestClient(create_product_app('real',paths=paths(tmp_path/'api'),tenant_registry=registry(docs=('*',)),
        canonical_publication_store=console.canonical_publication_store,immutable_source_store=source))
    assert public.get('/v1/knowledge/'+old_objects[0]['canonical_json']['object_id'],headers=headers()).status_code == 200
    result = deletion.delete(console,**command(console,accounts,first))
    assert set(result['snapshot_ids']) == {first,second,draft}
    assert result['versions'] == 3 and result['publications'] == 2
    resumed = restart_production(console)
    assert {e['snapshot_id'] for e in resumed.list_envelopes()} == {other}
    assert resumed.canonical_publication_store.active_publication_rows() == other_rows
    for row in old_objects:
        assert public.get('/v1/knowledge/'+row['canonical_json']['object_id'],headers=headers()).status_code == 404
    assert public.get('/v1/knowledge/'+other_rows[0]['knowledge_object']['object_id'],headers=headers()).status_code == 200
    with resumed.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_versions').fetchone()['n'] == 0
    # Old code cannot resurrect either workflow or publication source state,
    # including after the test-only UI has been disabled.
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','off')
    import psycopg
    from psycopg.types.json import Jsonb
    with pytest.raises(psycopg.Error,match='test_document_snapshot_deleted'):
        with resumed.workflow_document_store._connect() as con:
            con.execute('INSERT INTO workflow.documents SELECT (jsonb_populate_record(NULL::workflow.documents,%s)).*',(Jsonb(original),))
    with pytest.raises(psycopg.Error,match='test_document_snapshot_deleted'):
        with resumed.workflow_document_store._connect() as con:
            con.execute('INSERT INTO public.source_snapshots VALUES(%s,%s,%s,CURRENT_TIMESTAMP)',
                        (first,original['source_sha256'],original['source_locator']))
    fresh = receive(resumed,accounts,version='1.0')
    opened = annotation.prepare(resumed,actor_id=accounts['researcher']['account_id'],snapshot_id=fresh,
                                expected_revision=resumed.objects_revision(fresh))
    assert fresh not in {first,second,draft} and opened['entries'] == []
    assert resumed.object_review_bindings(fresh) == []


def test_sql_fault_rolls_back_serving_fences_receipt_and_workflow(production_console,tmp_path,monkeypatch):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    request = command(console,accounts,sid)
    before = deepcopy(console.canonical_publication_store.active_publication_rows())
    events = console.workflow_review_store.read_events()
    with console.workflow_document_store._connect() as con:
        con.execute("CREATE FUNCTION workflow.fail_test_reset() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected_test_reset_fault'; END $$")
        con.execute('CREATE TRIGGER fail_test_reset BEFORE DELETE ON workflow.documents FOR EACH ROW EXECUTE FUNCTION workflow.fail_test_reset()')
    import psycopg
    with pytest.raises(psycopg.Error,match='injected_test_reset_fault'):
        deletion.delete(console,**request)
    assert console.canonical_publication_store.active_publication_rows() == before
    assert console.workflow_review_store.read_events() == events
    assert restart_production(console)._envelope(sid)['snapshot_id'] == sid
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.test_document_deletions').fetchone()['n'] == 0
        assert con.execute('SELECT count(*) AS n FROM workflow.deleted_test_snapshots').fetchone()['n'] == 0


def test_preview_rejects_real_new_version_and_running_attempt(production_console,tmp_path,monkeypatch):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    request = command(console,accounts,sid)
    new = receive(console,accounts,prior=sid)
    with pytest.raises(ConsoleError,match='plan_changed'): deletion.delete(console,**request)
    console.reserve_source_selection(actor_id=accounts['researcher']['account_id'],snapshot_id=new,
        command_id=uuid4().hex,expected_revision=console.objects_revision(new))
    request = command(console,accounts,sid)
    with pytest.raises(ConsoleError,match='processing_running'): deletion.delete(console,**request)
    assert console.canonical_publication_store.active_publication_rows()


def test_concurrent_duplicate_from_independent_kernel_commits_once(production_console,tmp_path,monkeypatch):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    request = command(console,accounts,sid)
    other = restart_production(console)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda kernel:deletion.delete(kernel,**request),[console,other]))
    assert results[0] == results[1]
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.test_document_deletions').fetchone()['n'] == 1
    assert len([e for e in console.workflow_review_store.read_events() if e['event_type']=='test_document_deleted']) == 1


def test_mixed_release_is_refused_without_removing_other_document(production_console,tmp_path,monkeypatch):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    other = receive(console,accounts,title='Ander document',version='1.0')
    other_release = form_source(console,accounts,other)
    with console.workflow_document_store._connect() as con:
        con.execute('INSERT INTO public.publication_release_items(release_id,object_id,object_version,content_hash) '
            'SELECT %s,object_id,object_version,content_hash FROM public.publication_release_items WHERE release_id=%s',
            (release['release_id'],other_release['release_id']))
    before = deepcopy(console.canonical_publication_store.active_publication_rows())
    with pytest.raises(ConsoleError,match='shared_release'):
        deletion.preview(console,actor_id=accounts['publisher']['account_id'],snapshot_id=sid)
    assert console.canonical_publication_store.active_publication_rows() == before
    assert {e['snapshot_id'] for e in console.list_envelopes()} == {sid,other}


def test_canonical_only_historical_snapshot_is_included_in_confirmed_lineage(production_console,tmp_path,monkeypatch):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    from tests.test_logical_document_withdrawal_v1 import _object
    env = console._envelope(sid)
    console.canonical_publication_store.persist_published_release(logical_document_id=env['logical_document_id'],
        working_revision_id='historical-working-revision',snapshot_id='historical-snapshot',
        release_id='historical-release',release_version='0.9-historical',release_owner='historical-publisher',
        source_sha256='a'*64,source_locator='g2://sha256/'+'a'*64+'/history.html',
        published_at='2026-01-01T00:00:00+00:00',preserve_newer_registry=True,
        objects=[_object(object_id='historical-object',version='0.9',document_id='historical-document',
                         checksum='a'*64,text='Historische publicatie.')])
    plan = deletion.preview(console,actor_id=accounts['publisher']['account_id'],snapshot_id=sid)
    assert plan['historical_snapshot_ids'] == ['historical-snapshot']
    result = deletion.delete(console,**command(console,accounts,sid))
    assert result['versions'] == 2 and result['publications'] == 2
    assert set(result['snapshot_ids']) == {sid,'historical-snapshot'}
    assert console.canonical_publication_store.active_publication_rows() == []


def test_http_publisher_confirmation_and_denied_roles(production_console,tmp_path,monkeypatch):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    from starlette.testclient import TestClient
    from tests.production_support import application_for
    from tests.test_formation_repair_workplace import form_data
    with TestClient(application_for(console)) as client:
        client.post('/login',data={'username':accounts['researcher']['username'],'password':TEST_PASSWORD})
        assert 'Hele testdocument verwijderen' not in client.get('/tree').text
        assert client.get('/documents/test-delete',params={'document':sid}).status_code == 403
        request = command(console,accounts,sid)
        response = client.post('/documents/test-delete',data={k:v for k,v in request.items() if k!='actor_id'})
        assert response.status_code == 403
        client.post('/login',data={'username':accounts['publisher']['username'],'password':TEST_PASSWORD})
        assert 'Hele testdocument verwijderen' in client.get('/tree').text
        page = client.get('/documents/test-delete',params={'document':sid})
        assert page.status_code == 200 and 'Publicaties die verdwijnen: 1' in page.text
        fields = {**form_data(page,'/documents/test-delete'),'reason':'HTTP-testdocument opruimen.',
                  'confirm_title':'verkeerde titel','confirmed_test':'yes'}
        denied = client.post('/documents/test-delete',data=fields)
        assert denied.status_code == 400 and 'HTTP-testdocument opruimen.' in denied.text
        fields['confirm_title'] = console._envelope(sid)['title']
        response = client.post('/documents/test-delete',data=fields)
        assert response.status_code == 200 and 'Testdocument verwijderd' in response.text
        assert 'Continentie fixture' not in client.get('/tree').text
        assert client.post('/documents/test-delete',data=fields).status_code == 200


def test_current_backup_preserves_deleted_snapshot_fences_and_predelete_backup_recovers_data(
        production_console,tmp_path,monkeypatch):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    from src.workflows.workflow_chain_recovery_v1 import (
        PostgresWorkflowRecoveryAdapter,backup_workflow_chain,restore_workflow_chain,check_workflow_integrity)
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from tests.postgres_support import database,install_schema
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore
    adapter = PostgresWorkflowRecoveryAdapter(console.canonical_publication_store)
    blobs = FakeBlobStore(source.blobs)
    before = tmp_path/'before-delete.zip'
    backup_workflow_chain(before,database=adapter,source_store=blobs)
    rows_before = console.canonical_publication_store.active_publication_rows()
    request = command(console,accounts,sid)
    deletion.delete(console,**request)
    after_state = adapter.export_state()
    assert after_state['workflow_recovery_version'] == 14
    assert check_workflow_integrity(after_state)['ok']
    old = deepcopy(after_state);old['workflow_recovery_version'] = 13
    assert check_workflow_integrity(old)['errors'] == ['workflow_test_deletion_reexport_required']
    malformed = deepcopy(after_state);malformed['workflow_tables']['deleted_test_snapshots'] = []
    assert 'workflow_test_deletion_receipt_invalid' in check_workflow_integrity(malformed)['errors']
    after = tmp_path/'after-delete.zip'
    backup_workflow_chain(after,database=adapter,source_store=blobs)
    for archive in (after,before):
        with database(console.workflow_document_store.config.dsn) as config:
            install_schema(config.dsn)
            target_store = PostgresCanonicalPublicationStore(config)
            target = PostgresWorkflowRecoveryAdapter(target_store)
            result = restore_workflow_chain(archive,database=target,source_store=FakeBlobStore())
            assert result['ok']
            restored = target.export_state()
            if archive == after:
                assert restored['workflow_tables']['documents'] == []
                assert restored['workflow_tables']['test_document_deletions'] == after_state['workflow_tables']['test_document_deletions']
                assert restored['workflow_tables']['deleted_test_snapshots'] == after_state['workflow_tables']['deleted_test_snapshots']
                assert target_store.active_publication_rows() == []
            else:
                assert target_store.active_publication_rows() == rows_before
                assert restored['workflow_tables']['documents'][0]['snapshot_id'] == sid
                assert restored['workflow_tables']['deleted_test_snapshots'] == []


@pytest.mark.parametrize('guard,code', [('role','publisher_role_required'), ('mode','test_document_deletion_disabled'),
    ('confirm','test_document_deletion_confirmation_required'), ('title','delete_title_confirmation_required'),
    ('stale','test_document_deletion_plan_changed')])
def test_denied_test_reset_has_no_effect(production_console, tmp_path, monkeypatch, guard, code):
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION', 'on')
    console, accounts, sid, release, source = published(production_console, tmp_path)
    request = command(console, accounts, sid)
    before = deepcopy(console.canonical_publication_store.active_publication_rows())
    if guard == 'role': request['actor_id'] = accounts['researcher']['account_id']
    if guard == 'mode': monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','off')
    if guard == 'confirm': request['confirmed_test'] = False
    if guard == 'title': request['confirm_title'] = 'Ander document'
    if guard == 'stale': request['expected_plan'] = '0'*64
    with pytest.raises(ConsoleError, match=code):
        deletion.delete(console, **request)
    assert console._envelope(sid)['snapshot_id'] == sid
    assert console.canonical_publication_store.active_publication_rows() == before
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.test_document_deletions').fetchone()['n'] == 0
