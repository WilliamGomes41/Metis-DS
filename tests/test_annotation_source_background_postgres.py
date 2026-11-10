"""Native HTTP preparation stays responsive while extraction is held.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from threading import Event
from time import monotonic, sleep

import pytest
from starlette.testclient import TestClient
from tests.production_support import application_for
from tests.test_formation_repair_workplace import form_data
from tests.test_workflow_runtime_privileges_v1 import runtime_role  # noqa: F401


def received(production_console, tmp_path):
    console = production_console(root=tmp_path)
    actor = console.create_account(username='source-worker', password='fixture-only', roles=('researcher',))
    reviewer = console.create_account(username='source-observer', password='fixture-only', roles=('reviewer',))
    sid = console.receive_source(actor_id=actor['account_id'], filename='source.html',
        data=b'<html><body><h1>Bron</h1><p>Controleer de huid.</p></body></html>',
        content_type='text/html', ingest_kind='new', title='Bron voorbereiden', version='1.0',
        date='2026-11-10', live_url='', class_='richtlijn', family='test',
        named_reviewers=[reviewer['account_id']])['snapshot_id']
    return console, actor, reviewer, sid


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_source_open_returns_progress_before_extractor_finishes(production_console, tmp_path, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, reviewer, sid = received(production_console, tmp_path)
    entered, release = Event(), Event()
    extract = console._extract
    def held(*args, **kwargs):
        entered.set()
        assert release.wait(10), 'diagnostic extractor was not released'
        return extract(*args, **kwargs)
    monkeypatch.setattr(console, '_extract', held)
    with TestClient(application_for(console)) as client, ThreadPoolExecutor(1) as pool:
        client.post('/login', data={'username':'source-worker','password':'fixture-only'})
        page = client.get('/annotations', params={'document':sid})
        fields = form_data(page, '/annotations/source')
        future = pool.submit(client.post, '/annotations/source', data=fields, follow_redirects=False)
        try:
            assert entered.wait(3)
            try:
                accepted = future.result(timeout=1)
            except FutureTimeout:
                raise AssertionError('annotation source POST waits for the converter instead of returning progress') from None
            assert accepted.status_code == 303
            progress = client.get(accepted.headers['location'])
            assert progress.status_code == 200
            assert 'Bron wordt voorbereid' in progress.text
            assert 'refresh' in progress.text
            assert 'data-source-block=' not in progress.text
            assert client.get('/tree').status_code == 200
        finally:
            release.set()
            future.result(timeout=5)
        deadline = monotonic()+5
        while monotonic() < deadline:
            opened = client.get('/annotations', params={'document':sid})
            if 'data-source-block=' in opened.text:
                break
            sleep(.05)
        from src.vorming.human_annotation_source_v1 import progress as preparation_progress
        assert 'data-source-block=' in opened.text, preparation_progress(console, actor_id=actor['account_id'], snapshot_id=sid)
        assert console.snapshot_objects(sid) == []


def reservation(console, actor, sid, command='prepare-source'):
    from src.vorming import human_annotation_source_v1 as source
    return source.reserve(console, actor_id=actor['account_id'], snapshot_id=sid,
        command_id=command, expected_revision=console.objects_revision(sid))[0]


def test_duplicate_and_concurrent_clicks_reserve_one_attempt(production_console, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from src.vorming import human_annotation_source_v1 as source
    from tests.production_support import restart_production
    console, actor, reviewer, sid = received(production_console, tmp_path)
    peer = restart_production(console)
    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(reservation, console, actor, sid, 'one-click')
        b = pool.submit(reservation, peer, actor, sid, 'other-click')
        first, second = a.result(timeout=5), b.result(timeout=5)
    assert first['attempt_id'] == second['attempt_id']
    assert reservation(peer, actor, sid, first['command_id'])['attempt_id'] == first['attempt_id']
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.processing_attempts').fetchone()['n'] == 1
    console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=first)
    assert source.reserve(peer, actor_id=actor['account_id'], snapshot_id=sid,
        command_id='already-ready', expected_revision=console.objects_revision(sid)) == (None, False)
    assert source.progress(peer, actor_id=actor['account_id'], snapshot_id=sid)['ready']


def test_failed_extraction_is_visible_and_explicit_retry_preserves_source(production_console, tmp_path, monkeypatch):
    import pytest
    from src.operations_console_v1 import ConsoleError
    from src.vorming import human_annotation_source_v1 as source
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    def unavailable(*args, **kwargs):
        raise ConsoleError('docling_timeout')
    with monkeypatch.context() as patch:
        patch.setattr(console, '_extract', unavailable)
        with pytest.raises(ConsoleError, match='docling_timeout'):
            console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=attempt)
    state = source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)
    assert state['state'] == 'failed' and not state['ready'] and state['error_code'] == 'docling_timeout'
    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username':'source-worker','password':'fixture-only'})
        failed = client.get('/annotations', params={'document':sid})
        assert 'Bronvoorbereiding gestopt' in failed.text
        assert 'Bronvoorbereiding opnieuw proberen' in failed.text
        assert 'http-equiv="refresh"' not in failed.text
    retry = reservation(console, actor, sid, 'explicit-retry')
    console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=retry)
    assert source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)['ready']
    assert console.snapshot_objects(sid) == []


def test_checkpoint_survives_real_process_exit_and_fences_old_claim(production_console, tmp_path, monkeypatch):
    import json, subprocess, sys
    from dataclasses import asdict
    from src.vorming import human_annotation_source_v1 as source
    from src.vorming.source_processing_dispatch_v1 import pending
    from tests.production_support import restart_production
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    script = '''
import json,os,sys
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from tests.production_support import production_application
from src.vorming import human_annotation_v1 as annotations
p=json.load(sys.stdin)
c=production_application(p['root'],PostgresCanonicalConfig(**p['config']),source_store=p['source_store'],runtime=p['runtime']).state.operations_kernel
def exit_after_committed_checkpoint(*args,**kwargs): os._exit(23)
annotations.pin_source=exit_after_committed_checkpoint
c.execute_source_selection(actor_id=p['actor'],snapshot_id=p['sid'],attempt=p['attempt'])
'''
    process = subprocess.run([sys.executable, '-c', script], input=json.dumps({
        'root':str(console.root), 'config':asdict(console.workflow_document_store.config),
        'source_store':str(console.source_store), 'runtime':str(console.runtime),
        'actor':actor['account_id'], 'sid':sid, 'attempt':attempt}), text=True, capture_output=True, timeout=30)
    assert process.returncode == 23, process.stderr[-1000:]
    with console.workflow_document_store._connect() as con:
        active = con.execute('SELECT payload FROM workflow.processing_attempts WHERE attempt_id=%s',
                             (attempt['attempt_id'],)).fetchone()['payload']
        reference = active['diagnostic']['staged_extraction_hash']
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_sets').fetchone()['n'] == 0
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch,lease_expires_at}',"
                    "to_jsonb((now()-interval '1 minute')::text)) WHERE attempt_id=%s", (attempt['attempt_id'],))
    resumed = restart_production(console)
    available = pending(resumed)
    assert available and available[0][1]['attempt_id'] == attempt['attempt_id']
    def no_repeat(*args, **kwargs):
        raise AssertionError('committed extraction must survive a real process exit')
    monkeypatch.setattr(resumed, '_extract', no_repeat)
    resumed.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=available[0][1])
    assert source.progress(resumed, actor_id=actor['account_id'], snapshot_id=sid)['ready']
    with resumed.workflow_document_store._connect() as con:
        pin = con.execute('SELECT extraction_hash FROM workflow.annotation_sets WHERE snapshot_id=%s',(sid,)).fetchone()
        final = con.execute('SELECT payload FROM workflow.processing_attempts WHERE attempt_id=%s',(attempt['attempt_id'],)).fetchone()['payload']
    assert pin['extraction_hash'] == reference
    assert final['attempt_id'] == attempt['attempt_id'] and final['expires_at'] == attempt['expires_at']
    assert final['dispatch']['claim_number'] == 2 and final['state'] == 'succeeded'
    # A former owner cannot overwrite the winning terminal result or its pin.
    import pytest
    from src.operations_console_v1 import ConsoleError
    with pytest.raises(ConsoleError):
        source.execute(resumed, actor_id=actor['account_id'], snapshot_id=sid, attempt=active, deadline=monotonic()+5)
    assert source.progress(resumed, actor_id=actor['account_id'], snapshot_id=sid)['state'] == 'succeeded'


def test_role_revoked_during_extraction_cannot_pin_source(production_console, tmp_path, monkeypatch):
    import pytest
    from src.operations_console_v1 import ConsoleError
    from src.vorming import human_annotation_source_v1 as source
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    extract = console._extract
    def revoke(*args, **kwargs):
        fragments = extract(*args, **kwargs)
        with console.workflow_document_store._connect() as con:
            con.execute("UPDATE workflow.accounts SET roles=ARRAY['publisher'] WHERE account_id=%s",(actor['account_id'],))
        return fragments
    monkeypatch.setattr(console, '_extract', revoke)
    with pytest.raises(ConsoleError, match='researcher_role_required'):
        console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=attempt)
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_sets').fetchone()['n'] == 0
        assert con.execute('SELECT payload FROM workflow.processing_attempts').fetchone()['payload']['state'] == 'failed'


def test_long_source_conversion_outlives_soft_worker_boundary(production_console, tmp_path, monkeypatch):
    from datetime import timedelta
    from src.vorming import human_annotation_source_v1 as source
    from src.vorming import processing_retry_v1 as retry
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    clock = [retry.now()]
    monkeypatch.setattr(retry, 'now', lambda: clock[0])
    monkeypatch.setattr(source, 'now', lambda: clock[0])
    extract = console._extract
    def long_conversion(*args, **kwargs):
        clock[0] += timedelta(seconds=340)
        return extract(*args, **kwargs)
    monkeypatch.setattr(console, '_extract', long_conversion)
    console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=attempt)
    assert source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)['ready']
    with console.workflow_document_store._connect() as con:
        final = con.execute('SELECT payload FROM workflow.processing_attempts').fetchone()['payload']
    assert final['state'] == 'succeeded' and final['expires_at'] == attempt['expires_at']


def test_pin_failure_rolls_back_completion_and_retries_reuse_checkpoint(production_console, tmp_path, monkeypatch):
    from src.operations_console_v1 import ConsoleError
    from src.vorming import human_annotation_source_v1 as source
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    with console.workflow_document_store._connect() as con:
        con.execute("CREATE FUNCTION workflow.reject_annotation_pin_test() RETURNS trigger LANGUAGE plpgsql AS $$ "
                    "BEGIN RAISE EXCEPTION 'injected_pin_failure'; END $$")
        con.execute('CREATE TRIGGER reject_annotation_pin_test BEFORE INSERT ON workflow.annotation_sets '
                    'FOR EACH ROW EXECUTE FUNCTION workflow.reject_annotation_pin_test()')
    import psycopg
    with pytest.raises(psycopg.errors.RaiseException, match='injected_pin_failure'):
        console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=attempt)
    state = source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)
    assert state['state'] == 'failed' and not state['ready']
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_sets').fetchone()['n'] == 0
        assert con.execute('SELECT count(*) AS n FROM workflow.prepared_extraction_versions').fetchone()['n'] == 1
        con.execute('DROP TRIGGER reject_annotation_pin_test ON workflow.annotation_sets')
    def no_repeat(*args, **kwargs):
        raise AssertionError('failed pin must retain the committed extraction checkpoint')
    monkeypatch.setattr(console, '_extract', no_repeat)
    retry = reservation(console, actor, sid, 'retry-pin')
    console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=retry)
    assert source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)['ready']


def test_preparation_reservation_denies_stale_and_non_authorized_commands(production_console, tmp_path):
    from src.operations_console_v1 import ConsoleError
    from src.vorming import human_annotation_source_v1 as source
    console, actor, reviewer, sid = received(production_console, tmp_path)
    publisher = console.create_account(username='source-publisher', password='fixture-only', roles=('publisher',))
    with pytest.raises(ConsoleError, match='researcher_role_required'):
        reservation(console, publisher, sid)
    with pytest.raises(ConsoleError, match='annotation_objects_stale'):
        source.reserve(console, actor_id=actor['account_id'], snapshot_id=sid,
            command_id='stale-page', expected_revision='old-page')
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.processing_attempts').fetchone()['n'] == 0
        con.execute('ALTER TABLE workflow.processing_attempts DISABLE TRIGGER guard_annotation_source_attempt')
    with pytest.raises(ConsoleError, match='annotation_source_storage_not_ready'):
        reservation(console, actor, sid)


def test_compact_source_worker_pins_preparation(production_console, tmp_path, monkeypatch):
    from src.vorming import human_annotation_source_v1 as source
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', 'v1')
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=attempt)
    assert source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)['ready']


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_source_preparation_uses_existing_narrow_runtime_grants(production_console, tmp_path, monkeypatch, runtime_role, storage):
    import psycopg
    from psycopg import sql
    from src.vorming import human_annotation_source_v1 as source
    from tests.test_workflow_runtime_privileges_v1 import _grant_expected, _observe
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, reviewer, sid = received(production_console, tmp_path)
    admin, role = runtime_role
    _grant_expected(admin, role)
    # Existing canonical publication reads are provisioned separately from workflow grants.
    admin.execute(sql.SQL('GRANT SELECT ON public.audit_events, public.publication_releases, '
                         'public.publication_release_items, public.canonical_object_versions TO {}').format(sql.Identifier(role)))
    assert _observe(admin, role)['status'] == 'PASS'
    connect = psycopg.connect
    def runtime_connect(*args, **kwargs):
        con = connect(*args, **kwargs)
        previous = con.autocommit
        con.autocommit = True
        con.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
        con.autocommit = previous
        return con
    monkeypatch.setattr(psycopg, 'connect', runtime_connect)
    attempt = reservation(console, actor, sid)
    console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=attempt)
    assert source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)['ready']
    assert console.snapshot_objects(sid) == []


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_source_preparation_after_retiring_old_ai_keeps_ai_fenced(production_console, tmp_path, monkeypatch, storage):
    from tests.test_prose_transition_postgres import setup_command, request
    from src.vorming import prose_transition_v1 as transition
    from src.vorming import human_annotation_source_v1 as source
    from src.operations_console_v1 import ConsoleError
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    console, actor_id, sid, old, calls, _ = setup_command(tmp_path, production_console, monkeypatch)
    stopped = transition.stop(console, **request(console, actor_id, sid, old))
    with pytest.raises(ConsoleError, match=transition.STOPPED):
        console.reserve_source_selection(actor_id=actor_id, snapshot_id=sid,
            command_id='old-ai-before-pin', expected_revision=console.objects_revision(sid))
    attempt = reservation(console, {'account_id':actor_id}, sid)
    console.execute_source_selection(actor_id=actor_id, snapshot_id=sid, attempt=attempt)
    assert source.progress(console, actor_id=actor_id, snapshot_id=sid)['ready']
    assert transition.inventory(console, actor_id=actor_id, snapshot_id=sid)['transition'] == stopped
    with pytest.raises(ConsoleError, match='annotation_source_owned'):
        console.reserve_source_selection(actor_id=actor_id, snapshot_id=sid,
            command_id='old-ai-again', expected_revision=console.objects_revision(sid))
    assert calls == [] and console.snapshot_objects(sid) == []


def test_source_contract_change_during_conversion_rejects_pin(production_console, tmp_path, monkeypatch):
    from src.vorming import human_annotation_source_v1 as source
    from src.vorming import human_annotation_v1 as annotations
    from src.operations_console_v1 import ConsoleError
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    extract = console._extract
    def changed_contract(*args, **kwargs):
        fragments = extract(*args, **kwargs)
        monkeypatch.setattr(annotations, 'extractor_contract', lambda kind:'changed-extractor-contract')
        return fragments
    monkeypatch.setattr(console, '_extract', changed_contract)
    with pytest.raises(ConsoleError, match='processing_configuration_changed'):
        console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=attempt)
    assert not source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)['ready']


def test_explicit_retry_after_expired_attempt_does_not_reuse_dead_job(production_console, tmp_path, monkeypatch):
    from datetime import timedelta
    from src.vorming import human_annotation_source_v1 as source
    from src.vorming import processing_retry_v1 as retry
    console, actor, reviewer, sid = received(production_console, tmp_path)
    first = reservation(console, actor, sid)
    expired = retry.now()+timedelta(seconds=console._processing_limits().attempt+1)
    monkeypatch.setattr(source, 'now', lambda:expired)
    second = reservation(console, actor, sid, 'after-expiry')
    assert second['attempt_id'] != first['attempt_id']
    with console.workflow_document_store._connect() as con:
        prior = con.execute('SELECT payload FROM workflow.processing_attempts WHERE attempt_id=%s',(first['attempt_id'],)).fetchone()['payload']
    assert prior['state'] == 'interrupted' and prior['error_code'] == 'processing_attempt_expired'


def test_source_job_input_is_immutable_and_not_a_semantic_job(production_console, tmp_path):
    import psycopg
    from src.vorming import human_annotation_source_v1 as source
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    assert attempt['producer_contract'] == source.MODE
    assert 'reserved_semantic_contract_version' not in attempt
    assert 'model' not in attempt['processing_configuration']
    with console.workflow_document_store._connect() as con:
        for path, value in [('kind','"retry"'),('actor_id','"forged"'),
                            ('expires_at','"2099-01-01T00:00:00+00:00"'),
                            ('processing_configuration,mode','"semantic-source-bound-v3"')]:
            with pytest.raises(psycopg.Error, match='annotation_source_attempt_changed'):
                with con.transaction():
                    con.execute('UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,%s,%s::jsonb) '
                                'WHERE attempt_id=%s',('{'+path+'}',value,attempt['attempt_id']))


def test_missing_extraction_checkpoint_fails_without_silent_reconversion(production_console, tmp_path, monkeypatch):
    from src.vorming import human_annotation_source_v1 as source, human_annotation_v1 as annotations
    from src.operations_console_v1 import ConsoleError
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    def pin_failure(*args, **kwargs):
        raise ConsoleError('fixture_pin_failure')
    with monkeypatch.context() as patch:
        patch.setattr(annotations, 'pin_source', pin_failure)
        with pytest.raises(ConsoleError, match='fixture_pin_failure'):
            console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=attempt)
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,"
                    "'{diagnostic,staged_extraction_hash}',to_jsonb(%s::text)) WHERE attempt_id=%s",
                    ('0'*64,attempt['attempt_id']))
    def no_repeat(*args, **kwargs):
        raise AssertionError('broken checkpoint must not silently repeat conversion')
    monkeypatch.setattr(console, '_extract', no_repeat)
    retry = reservation(console, actor, sid, 'missing-checkpoint')
    with pytest.raises(ConsoleError, match='source_extraction_integrity_failed'):
        console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=retry)
    assert not source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)['ready']


def test_busy_pdf_capacity_keeps_same_preparation_pending(production_console, tmp_path, monkeypatch):
    from src.vorming.docling_pdf_v1 import reserve_conversion_capacity
    from src.vorming.source_processing_dispatch_v1 import SourceProcessingDispatcher
    from src.vorming import human_annotation_source_v1 as source
    console, actor, reviewer, _ = received(production_console, tmp_path)
    monkeypatch.setenv('METIS_PDF_EXTRACTOR', 'docling')
    monkeypatch.setenv('METIS_DOCLING_LOCK_PATH', str(tmp_path/'source-conversion.lock'))
    sid = console.receive_source(actor_id=actor['account_id'], filename='pending.pdf',
        data=b'%PDF-1.4\nsynthetic', content_type='application/pdf', ingest_kind='new',
        title='Wachtende PDF', version='1', date='2026-11-10', live_url='', class_='richtlijn',
        family='test', named_reviewers=[reviewer['account_id']])['snapshot_id']
    attempt = reservation(console, actor, sid)
    def no_extract(*args, **kwargs):
        raise AssertionError('busy PDF must not claim/extract')
    monkeypatch.setattr(console, '_extract', no_extract)
    with reserve_conversion_capacity() as available:
        assert available
        SourceProcessingDispatcher(console)._execute(sid, attempt)
    with console.workflow_document_store._connect() as con:
        current = con.execute('SELECT payload FROM workflow.processing_attempts WHERE attempt_id=%s',
                              (attempt['attempt_id'],)).fetchone()['payload']
    assert current == attempt
    state = source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)
    assert state['phase'] == 'annotation_source_pending' and state['state'] == 'running'


def test_guard_removed_after_admission_blocks_worker_before_extraction(production_console, tmp_path, monkeypatch):
    from src.vorming import human_annotation_source_v1 as source
    from src.operations_console_v1 import ConsoleError
    console, actor, reviewer, sid = received(production_console, tmp_path)
    attempt = reservation(console, actor, sid)
    with console.workflow_document_store._connect() as con:
        con.execute('ALTER TABLE workflow.processing_attempts DISABLE TRIGGER guard_annotation_source_attempt')
    def no_extract(*args, **kwargs):
        raise AssertionError('partial schema cutover must not run extraction')
    monkeypatch.setattr(console, '_extract', no_extract)
    with pytest.raises(ConsoleError, match='annotation_source_storage_not_ready'):
        console.execute_source_selection(actor_id=actor['account_id'], snapshot_id=sid, attempt=attempt)
    state = source.progress(console, actor_id=actor['account_id'], snapshot_id=sid)
    assert state['state'] == 'failed' and state['error_code'] == 'annotation_source_storage_not_ready'
    assert not state['ready']
