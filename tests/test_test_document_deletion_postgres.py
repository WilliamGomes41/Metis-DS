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
        event = con.execute("SELECT actor_account_id FROM workflow.review_events WHERE event_type='test_document_deleted'").fetchone()
        assert event['actor_account_id']==request['actor_id']
    resumed = restart_production(console)
    assert resumed.list_envelopes() == []
    assert deletion.delete(resumed, **request) == result
    with console.workflow_document_store._connect() as writer:
        writer.execute("SET LOCAL idle_in_transaction_session_timeout='5s'")
        writer.execute('LOCK TABLE workflow.documents IN ROW EXCLUSIVE MODE')
        assert deletion.delete(resumed, **request)==result
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
    peer = restart_production(console)
    assert first in peer._envelopes  # Its startup mirror deliberately predates deletion.
    result = deletion.delete(console,**command(console,accounts,first))
    assert set(result['snapshot_ids']) == {first,second,draft}
    assert result['versions'] == 3 and result['publications'] == 2
    assert {e['snapshot_id'] for e in peer.list_envelopes()} == {other}
    with pytest.raises(ConsoleError,match='unknown_snapshot'):
        peer._envelope(first)
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


def test_attempt_cannot_commit_running_after_deletion_inventory(production_console,tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from time import monotonic, sleep
    import psycopg
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    fresh = receive(console,accounts,prior=sid)
    request = command(console,accounts,sid)
    original = deletion._inventory
    pids = Queue()
    def start_attempt():
        with console.workflow_document_store._connect() as con:
            pids.put(con.info.backend_pid)
            try:
                con.execute("SET LOCAL statement_timeout='8s'")
                con.execute("INSERT INTO workflow.processing_attempts "
                    "(attempt_id,snapshot_id,command_id,started_at,object_generation,payload) "
                    "VALUES('late-start',%s,'late-start',now(),0,'{\"state\":\"running\",\"kind\":\"source_selection\"}')", (fresh,))
                con.commit()
                return 'committed'
            except psycopg.errors.ForeignKeyViolation:
                return 'document_absent'
    with ThreadPoolExecutor(1) as pool:
        pending = []
        def inventory_with_late_start(con, selected):
            plan = original(con,selected)
            pending.append(pool.submit(start_attempt))
            pid = pids.get(timeout=5)
            deadline = monotonic()+5
            with console.workflow_document_store._connect() as observer:
                while not pending[0].done():
                    row = observer.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',(pid,)).fetchone()
                    if row and row['wait_event_type']=='Lock': break
                    assert monotonic()<deadline, 'late writer neither committed nor reached the SQL lock boundary'
                    sleep(.01)
            return plan
        monkeypatch.setattr(deletion,'_inventory',inventory_with_late_start)
        assert deletion.delete(console,**request)['deleted']
        assert pending[0].result(timeout=10)=='document_absent'


@pytest.mark.parametrize('writer',['attempt','document','document-table','canonical-table','canonical-advisory'])
def test_uncommitted_writer_refuses_deletion_without_deadlock(production_console,tmp_path,monkeypatch,writer):
    from contextlib import contextmanager
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    fresh = receive(console,accounts,prior=sid)
    request = command(console,accounts,sid)
    original = deletion.workflow_transaction
    @contextmanager
    def bounded_transaction(store):
        with original(store) as con:
            con.execute("SET LOCAL lock_timeout='2s'")
            yield con
    monkeypatch.setattr(deletion,'workflow_transaction',bounded_transaction)
    with console.workflow_document_store._connect() as worker:
        if writer=='document':
            worker.execute('SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE',(fresh,))
        elif writer=='document-table':
            worker.execute('UPDATE workflow.documents SET title=title WHERE snapshot_id=%s',(fresh,))
        elif writer=='canonical-table':
            worker.execute('LOCK TABLE public.publication_registry IN ROW EXCLUSIVE MODE')
        elif writer=='canonical-advisory':
            logical = console._envelope(sid)['logical_document_id']
            worker.execute('SELECT pg_advisory_xact_lock(2110023,hashtext(%s))',(logical,))
        else:
            worker.execute("INSERT INTO workflow.processing_attempts "
                "(attempt_id,snapshot_id,command_id,started_at,object_generation,payload) "
                "VALUES('starting',%s,'starting',now(),0,'{\"state\":\"running\",\"kind\":\"source_selection\"}')", (fresh,))
        with pytest.raises(ConsoleError,match='test_document_deletion_busy'):
            deletion.delete(console,**request)
        worker.commit()
    view = deletion.preview(console,actor_id=request['actor_id'],snapshot_id=sid)
    assert view['running_snapshots']==([fresh] if writer=='attempt' else [])
    assert console.canonical_publication_store.active_publication_rows()
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.test_document_deletions').fetchone()['n']==0


def test_authorization_change_locks_before_account_and_refuses_delete(production_console,tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from queue import Queue
    from time import monotonic, sleep
    import psycopg
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    request = command(console,accounts,sid)
    original = deletion.workflow_transaction
    pids = Queue()
    @contextmanager
    def bounded_transaction(store):
        with original(store) as con:
            con.execute("SET LOCAL lock_timeout='3s'")
            pids.put(con.info.backend_pid)
            yield con
    monkeypatch.setattr(deletion,'workflow_transaction',bounded_transaction)
    dsn = console.workflow_document_store.config.dsn
    with ThreadPoolExecutor(1) as pool, psycopg.connect(dsn) as changer:
        changer.execute("SET LOCAL lock_timeout='2s'")
        console.workflow_review_store._lock_authorizations(changer)
        pending = pool.submit(deletion.delete,console,**request)
        try:
            pid = pids.get(timeout=5)
            deadline = monotonic()+5
            with psycopg.connect(dsn,autocommit=True) as observer:
                while True:
                    row = observer.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',(pid,)).fetchone()
                    if row and row[0]=='Lock': break
                    assert monotonic()<deadline, 'delete did not reach the authorization boundary'
                    sleep(.01)
            changer.execute("UPDATE workflow.accounts SET roles=ARRAY['researcher']::text[] WHERE account_id=%s",(request['actor_id'],))
            changer.commit()
        finally:
            changer.rollback()
        with pytest.raises(ConsoleError,match='publisher_role_required'):
            pending.result(timeout=5)
    with psycopg.connect(dsn) as con:
        assert con.execute('SELECT count(*) FROM workflow.documents WHERE snapshot_id=%s',(sid,)).fetchone()[0]==1
        assert con.execute('SELECT count(*) FROM workflow.test_document_deletions').fetchone()[0]==0


def test_annotation_edit_with_same_head_count_invalidates_confirmation(production_console,tmp_path,monkeypatch):
    from src.vorming import human_annotation_v1 as annotation
    from tests.test_human_annotation_postgres import anchor, command as selection
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    fresh = receive(console,accounts,prior=sid)
    actor = accounts['researcher']['account_id']
    view = annotation.prepare(console,actor_id=actor,snapshot_id=fresh,expected_revision=console.objects_revision(fresh))
    save = selection(view,ranges=[anchor(view,'Bespreek het onderwerp')])
    result = annotation.save(console,actor_id=actor,**save)
    request = command(console,accounts,sid)
    save.update(command_id=uuid4().hex,expected_revision=result['revision'],expected_generation=result['generation'])
    save['selection']['status']='uncertain'
    annotation.save(console,actor_id=actor,**save)
    with pytest.raises(ConsoleError,match='plan_changed'):
        deletion.delete(console,**request)
    assert annotation.overview(console,actor_id=actor,snapshot_id=fresh)['generation']==2


def test_inflight_view_registration_precedes_cleanup_and_late_operational_rows_are_fenced(
        production_console,tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from threading import Event
    import psycopg
    from src.settings.view_check_store import ViewCheckStore
    monkeypatch.setenv('CONSOLE_TEST_DOCUMENT_DELETION','on')
    console, accounts, sid, release, source = published(production_console,tmp_path)
    request = command(console,accounts,sid)
    inserted, finish = Event(), Event()
    dsn = console.workflow_document_store.config.dsn
    @contextmanager
    def paused_commit():
        with psycopg.connect(dsn) as con:
            yield con
            inserted.set()
            assert finish.wait(10), 'registration commit was not released'
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(ViewCheckStore(paused_commit).register,'publisher',sid,'before',{'revision':'fixture'})
        try:
            assert inserted.wait(10)
            with pytest.raises(ConsoleError,match='test_document_deletion_busy'):
                deletion.delete(console,**request)
        finally:
            finish.set()
        assert pending.result(timeout=10)['state']=='queued'
    assert deletion.delete(console,**request)['deleted']
    with pytest.raises(psycopg.errors.RaiseException,match='test_document_snapshot_deleted'):
        ViewCheckStore(lambda:psycopg.connect(dsn)).register('publisher',sid,'late',{'revision':'fixture'})
    with psycopg.connect(dsn) as con:
        assert con.execute('SELECT count(*) FROM workflow.view_checks WHERE snapshot_id=%s',(sid,)).fetchone()[0]==0
        with pytest.raises(psycopg.errors.RaiseException,match='test_document_snapshot_deleted'):
            con.execute("INSERT INTO workflow.publication_refusals(recorded_at,snapshot_id,object_version,actor,verdict,"
                "reason_codes,dedup_key,schema_version) VALUES(now(),%s,'1','publisher','refused','[]','late','v1')",(sid,))


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
    for table in ('test_document_deletions','deleted_test_snapshots'):
        old['workflow_tables'].pop(table)
    # An old exporter omits the new tables, but still exports the ledger marker.
    assert check_workflow_integrity(old)['errors'] == ['workflow_test_deletion_reexport_required']
    malformed = deepcopy(after_state);malformed['workflow_tables']['deleted_test_snapshots'] = []
    assert 'workflow_test_deletion_receipt_invalid' in check_workflow_integrity(malformed)['errors']
    malformed = deepcopy(after_state)
    malformed['workflow_tables']['test_document_deletions'][0]['result']['snapshot_ids'] = 1
    assert check_workflow_integrity(malformed)['errors'] == ['workflow_test_deletion_receipt_invalid']
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
    # Even a reader older than the current validator cannot commit its SQL
    # restore of that ledger event while silently omitting deletion authority.
    import psycopg
    from psycopg.types.json import Jsonb
    event = next(r for r in after_state['workflow_tables']['review_events'] if r['event_type']=='test_document_deleted')
    with database(console.workflow_document_store.config.dsn) as config:
        install_schema(config.dsn)
        with pytest.raises(psycopg.Error,match='test_document_deletion_recovery_required'):
            with psycopg.connect(config.dsn) as con:
                con.execute('INSERT INTO workflow.review_events(object_id,object_version,event_type,occurred_at,details,'
                    'previous_event_hash,event_hash,actor_text,event_payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (event['object_id'],event['object_version'],event['event_type'],event['occurred_at'],
                     Jsonb(event['details']),event['previous_event_hash'],event['event_hash'],event['actor_text'],Jsonb(event['event_payload'])))


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
