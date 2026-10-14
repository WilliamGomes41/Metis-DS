"""#616 durable request-to-attempt evidence, never another workflow authority.

# release-control-evidence: scope/belofte opslag concurrent stale interrupt retry version-compat recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit metrics slop releasebewijs
"""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.request_diagnostics_v1 import RequestDiagnostics
from src.source_processing_dispatch_v1 import SourceProcessingDispatcher
from tests.test_source_dispatch_hardening import console, receive
from tests.test_availability_repair import accounts, bind, provider, login
from tests.test_workflow_transaction_v1 import workflow_postgres


def test_http_origin_survives_restart_duplicate_and_read_only_export(console, tmp_path, monkeypatch):
    actor, reviewer = accounts(console)
    bind(console, provider)
    sid = receive(console, actor, reviewer, 'trace')
    monkeypatch.setattr(SourceProcessingDispatcher, 'notify', lambda *args: False)
    app = create_console_app(console)
    app.add_middleware(RequestDiagnostics)
    with TestClient(app, base_url='https://testserver') as client:
        login(client)
        data = {'document': sid, 'command_id': 'private-command',
                'expected_revision': console.objects_revision(sid)}
        response = client.post('/source-selection/start', data=data, follow_redirects=False)
        assert response.status_code == 303
        request_id = response.headers['x-metis-request-id']
        attempt = deepcopy(console._envelope(sid)['processing_attempts'][-1])
        assert attempt['diagnostic']['origin_request_id'] == request_id
        duplicate = client.post('/source-selection/start', data=data, follow_redirects=False)
        assert duplicate.headers['x-metis-request-id'] != request_id
        assert console._envelope(sid)['processing_attempts'] == [attempt]
        before = deepcopy(console._envelope(sid))
        def forbidden(*args, **kwargs):
            raise AssertionError('diagnostic read must not reconstruct or process')
        monkeypatch.setattr(console, '_read_source_fragments', forbidden)
        monkeypatch.setattr(console, '_fragments_and_spec', forbidden)
        monkeypatch.setattr(console, 'snapshot_objects', forbidden)
        exported = client.get('/source-selection/processing-trace', params={'document':sid})
        assert exported.status_code == 200
        assert exported.headers['cache-control'] == 'no-store'
        trace = exported.json()
        assert trace['attempts'][0]['origin_request_id'] == request_id
        assert trace['attempts'][0]['dispatch_state'] == 'pending'
        assert trace['domain_completion'] == 'not_assessed'
        assert 'private-command' not in json.dumps(trace)
        assert console._envelope(sid) == before
    restarted = restart(console)
    assert restarted._envelope(sid)['processing_attempts'] == [attempt]
    from src.processing_trace_v1 import processing_trace
    assert processing_trace(restarted._envelope(sid))['attempts'][0]['origin_request_id'] == request_id


def restart(console):
    if hasattr(console, 'workflow_document_store'):
        from tests.test_review_batch_atomic_postgres import _console
        return _console(console.root, console.workflow_document_store.config)
    from tests.test_availability_repair import state
    return state(console.root)


def test_checkpoint_restart_and_retry_reuses_exact_extraction(console, monkeypatch):
    from src.operations_console_v1 import ConsoleError
    from src.processing_trace_v1 import processing_trace
    actor, reviewer = accounts(console)
    sid = receive(console, actor, reviewer, 'reuse')
    def fail(*args):
        raise ConsoleError('processing_dependency_failed')
    bind(console, fail)
    first, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='first', expected_revision=console.objects_revision(sid))
    with pytest.raises(ConsoleError):
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=first)
    stopped = restart(console)
    before = deepcopy(stopped._envelope(sid))
    original = before['processing_attempts'][0]
    assert original['state'] == 'failed'
    retained_hash = before['prepared_source_extraction']['record_hash']
    assert original['diagnostic']['extraction_checkpoint']['record_hash'] == retained_hash
    bind(stopped, provider)
    def forbidden(*args, **kwargs):
        raise AssertionError('committed extraction must be reused')
    monkeypatch.setattr(stopped, '_extract', forbidden)
    second, _ = stopped.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='second', expected_revision=stopped.objects_revision(sid))
    stopped.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=second)
    after = restart(stopped)._envelope(sid)
    assert after['processing_attempts'][0] == original
    latest = after['processing_attempts'][-1]
    assert latest['state'] == 'succeeded' and latest['retry_of'] == first['attempt_id']
    assert 'extraction_reused' in [c['phase'] for c in latest['diagnostic']['checkpoints']]
    assert after['prepared_source_extraction']['record_hash'] == retained_hash
    trace = processing_trace(after)
    assert trace['attempts'][-1]['extraction_checkpoint_hash'] == retained_hash
    assert trace['domain_completion'] == 'not_assessed'


def fail_write(console, monkeypatch):
    # PostgreSQL failure occurs AFTER real SQL writes but BEFORE outer commit.
    # The local adapter control fails before write; it is not SQL rollback proof.
    if hasattr(console, 'workflow_document_store'):
        original = console.workflow_document_store.write_bundle
        def broken(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError('private storage failure')
        monkeypatch.setattr(console.workflow_document_store, 'write_bundle', broken)
    else:
        def broken(*args, **kwargs):
            raise OSError('private storage failure')
        monkeypatch.setattr(console, '_commit_prepared_store', broken)


def test_failed_reservation_does_not_persist_attempt_or_accepted_observation(console, monkeypatch):
    from src.request_diagnostics_v1 import _LOGGER
    actor, reviewer = accounts(console)
    sid = receive(console, actor, reviewer, 'reserve-failure')
    records = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: records.append(json.loads(msg)))
    fail_write(console, monkeypatch)
    with pytest.raises(OSError, match='private storage failure'):
        console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
            command_id='not-accepted', expected_revision=console.objects_revision(sid))
    assert restart(console)._envelope(sid).get('processing_attempts', []) == []
    assert not any(r['event'] == 'processing_reserved' for r in records)


def test_failed_checkpoint_rolls_back_without_success_observation(console, monkeypatch):
    from src.operations_console_v1 import ConsoleError
    from src.request_diagnostics_v1 import _LOGGER
    actor, reviewer = accounts(console)
    sid = receive(console, actor, reviewer, 'checkpoint-failure')
    attempt, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='accepted', expected_revision=console.objects_revision(sid))
    before = deepcopy(console._envelope(sid))
    records = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: records.append(json.loads(msg)))
    fail_write(console, monkeypatch)
    with pytest.raises(ConsoleError, match='processing_diagnostic_write_failed'):
        console._diagnostic_writer(sid, attempt['attempt_id'])('model_request', {'provider_evidence':{'private':'never-log'}})
    assert restart(console)._envelope(sid) == before
    assert not any(r['event'] == 'processing_checkpoint' for r in records)


def test_two_runtimes_claim_once_and_trace_hides_claim_token(console):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from src.source_processing_dispatch_v1 import claim
    from src.processing_trace_v1 import processing_trace
    actor, reviewer = accounts(console)
    sid = receive(console, actor, reviewer, 'claims')
    attempt, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='claim-once', expected_revision=console.objects_revision(sid))
    readers = [restart(console), restart(console)]
    barrier = Barrier(2)
    def run(reader):
        barrier.wait(timeout=5)
        return claim(reader, snapshot_id=sid, attempt_id=attempt['attempt_id'], actor_id=actor)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, readers))
    assert sum(result is not None for result in results) == 1
    stored = restart(console)._envelope(sid)
    trace = processing_trace(stored)
    token = stored['processing_attempts'][0]['dispatch']['token']
    assert trace['attempts'][0]['dispatch_state'] == 'claimed'
    assert trace['attempts'][0]['execution_runtime']['runtime_id']
    assert token not in json.dumps(trace)


def test_export_authorization_and_observer_failure_do_not_change_command(console, monkeypatch):
    from src.request_diagnostics_v1 import _LOGGER
    actor, reviewer = accounts(console)
    sid = receive(console, actor, reviewer, 'permissions')
    monkeypatch.setattr(SourceProcessingDispatcher, 'notify', lambda *args: False)
    outsider = console.create_account(username='outsider', password='fixture-only', roles=('reviewer',))
    def broken(*args):
        raise OSError('private telemetry failure')
    monkeypatch.setattr(_LOGGER, 'info', broken)
    bind(console, provider)
    app = create_console_app(console)
    app.add_middleware(RequestDiagnostics)
    with TestClient(app, base_url='https://testserver') as client:
        denied = client.get('/source-selection/processing-trace', params={'document':sid}, follow_redirects=False)
        assert denied.status_code in (303, 401)
        login(client, 'outsider')
        denied = client.get('/source-selection/processing-trace', params={'document':sid})
        assert denied.status_code == 400  # existing ConsoleError mapping for unassigned reviewers
        assert 'processing-trace-v1' not in denied.text
        login(client)
        attempt, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
            command_id='works-without-logs', expected_revision=console.objects_revision(sid))
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
        assert client.get('/source-selection/processing-trace', params={'document':sid}).json()['attempts'][-1]['stored_state'] == 'succeeded'


def _crash_worker(root, config, actor, sid, attempt, reached):
    from tests.test_availability_repair import state, bind
    from tests.test_review_batch_atomic_postgres import _console
    child = _console(root, config) if config is not None else state(root)
    def blocked(*args):
        reached.set()  # existing extraction/checkpoint has committed before model I/O
        import time
        time.sleep(30)
        raise RuntimeError('test process should have been terminated')
    bind(child, blocked)
    child.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)


def test_process_death_preserves_origin_and_checkpoint_then_authorized_retry(console, monkeypatch):
    import multiprocessing
    from datetime import timedelta
    from src.processing_retry_v1 import expire_running, now
    from src.processing_trace_v1 import processing_trace, processing_incident
    actor, reviewer = accounts(console)
    sid = receive(console, actor, reviewer, 'crash')
    bind(console, provider)
    monkeypatch.setattr(SourceProcessingDispatcher, 'notify', lambda *args: False)
    app = create_console_app(console); app.add_middleware(RequestDiagnostics)
    with TestClient(app, base_url='https://testserver') as client:
        login(client)
        response = client.post('/source-selection/start', data={'document':sid, 'command_id':'crash-command',
            'expected_revision':console.objects_revision(sid)}, follow_redirects=False)
        assert response.status_code == 303
        origin = response.headers['x-metis-request-id']
    attempt = deepcopy(console._envelope(sid)['processing_attempts'][-1])
    ctx = multiprocessing.get_context('spawn'); reached = ctx.Event()
    config = console.workflow_document_store.config if hasattr(console, 'workflow_document_store') else None
    process = ctx.Process(target=_crash_worker, args=(console.root, config, actor, sid, attempt, reached))
    process.start()
    try:
        assert reached.wait(15), 'child never reached the actual post-checkpoint provider boundary'
        process.terminate(); process.join(5)
        assert not process.is_alive() and process.exitcode != 0
        recovered = restart(console)
        frozen = deepcopy(recovered._envelope(sid))
        trace = processing_trace(frozen)
        assert trace['attempts'][0]['origin_request_id'] == origin
        assert trace['attempts'][0]['stored_state'] == 'running'
        assert trace['attempts'][0]['execution_runtime']['runtime_id'] != trace['attempts'][0]['origin_runtime']['runtime_id']
        assert trace['attempts'][0]['extraction_checkpoint_hash'] == trace['artifacts']['extraction_record_hash']
        assert 'terminal_durable_result_not_recorded' in processing_incident(trace)['missing_evidence']
        assert recovered._envelope(sid) == frozen
        # Invoke existing expiry/transaction owner with a controlled test clock.
        with recovered._reprocessing_transaction(sid):
            expired = deepcopy(recovered._envelope(sid))
            expire_running(expired, now()+timedelta(days=1))
            recovered._commit_prepared_store(envelopes={sid:expired}, snapshot_id=sid)
        bind(recovered, provider)
        def forbidden(*args, **kwargs):
            raise AssertionError('retry must reuse committed extraction')
        monkeypatch.setattr(recovered, '_extract', forbidden)
        retry, _ = recovered.reserve_source_selection(actor_id=actor, snapshot_id=sid,
            command_id='after-crash', expected_revision=recovered.objects_revision(sid))
        recovered.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=retry)
        final = restart(recovered)._envelope(sid)
        assert final['processing_attempts'][0]['diagnostic']['origin_request_id'] == origin
        assert final['processing_attempts'][-1]['state'] == 'succeeded'
        assert final['processing_attempts'][-1]['retry_of'] == attempt['attempt_id']
        assert final['prepared_source_extraction']['record_hash'] == frozen['prepared_source_extraction']['record_hash']
    finally:
        if process.is_alive():
            process.terminate(); process.join(5)


def test_expired_diagnostic_read_is_nonmutating_and_late_writer_remains_fenced(console):
    from datetime import timedelta
    from src.processing_retry_v1 import now
    from src.operations_console_v1 import ConsoleError
    from src.processing_trace_v1 import processing_trace, processing_incident
    actor, reviewer = accounts(console)
    sid = receive(console, actor, reviewer, 'expired')
    attempt, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='expires', expected_revision=console.objects_revision(sid))
    with console._reprocessing_transaction(sid):
        expired = deepcopy(console._envelope(sid))
        expired['processing_attempts'][0]['expires_at'] = (now()-timedelta(seconds=1)).isoformat()
        console._commit_prepared_store(envelopes={sid:expired}, snapshot_id=sid)
    fresh = restart(console)
    before = deepcopy(fresh._envelope(sid))
    incident = processing_incident(processing_trace(before))
    assert incident['assessment']['stored_state'] == 'running'
    assert 'attempt_deadline_elapsed_reconcile_existing_authority' in incident['missing_evidence']
    with pytest.raises(ConsoleError, match='processing_attempt_expired'):
        fresh._diagnostic_writer(sid, attempt['attempt_id'])('model_response', {})
    assert restart(fresh)._envelope(sid) == before


def recorded_attempt():
    return {'attempt_id':'pa_'+'a'*32, 'command_id':'private-command', 'source_hash':'b'*64,
        'source_version':'private-version', 'expected_revision':'private-revision', 'state':'succeeded',
        'started_at':'2026-10-14T08:00:00Z', 'expires_at':'2026-10-14T09:00:00Z',
        'diagnostic':{'origin_request_id':'c'*32, 'provider_evidence':{'text':'private-source'},
            'checkpoints':[{'phase':'model_request','at':'2026-10-14T08:00:01Z'}]}}


def test_offline_projection_is_bounded_redacted_and_never_guesses_latest_attempt():
    from src.processing_trace_v1 import processing_trace, processing_incident
    attempt = recorded_attempt()
    attempt['diagnostic']['checkpoints'] *= 150
    envelope = {'snapshot_id':'snap-'+'d'*16+'-'+'e'*8, 'sha256':'b'*64,
                'processing_attempts':[deepcopy(attempt) for _ in range(70)]}
    for i, row in enumerate(envelope['processing_attempts']):
        row['attempt_id'] = 'pa_'+f'{i:032x}'
    before = deepcopy(envelope)
    trace = processing_trace(envelope)
    assert len(trace['attempts']) == 64 and trace['omitted_attempts'] == 6
    assert len(trace['attempts'][0]['checkpoints']) == 128
    assert trace['attempts'][0]['omitted_checkpoints'] == 22
    assert 'private' not in json.dumps(trace)
    assert envelope == before
    assert processing_incident(trace)['selected_attempt_id'] is None
    chosen = processing_incident(trace, selected_attempt='pa_'+f'{69:032x}')
    assert chosen['selected_attempt_id'] == 'pa_'+f'{69:032x}'
    assert 'attempt_history_truncated' in chosen['missing_evidence']
    assert chosen['domain_completion'] == 'not_assessed'
    with pytest.raises(ValueError):
        processing_incident(trace, selected_request='private-input')


def test_matching_operational_observations_are_not_durable_commit_proof(monkeypatch):
    from src.processing_trace_v1 import processing_trace, processing_incident, observe
    from src.request_diagnostics_v1 import _LOGGER
    attempt = recorded_attempt()
    trace = processing_trace({'snapshot_id':'snap-'+'d'*16+'-'+'e'*8,
        'sha256':'b'*64, 'processing_attempts':[attempt]})
    rows = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: rows.append(json.loads(msg)))
    observe('processing_finished', trace['snapshot_id'], attempt)
    assert rows[0]['observation_kind'] == 'non_authoritative_operation_return'
    assert 'private' not in json.dumps(rows)
    wrong = dict(rows[0], source_hash='f'*64)
    joined = processing_incident(trace, [wrong, rows[0]])
    assert len(joined['observations']) == 1
    assert joined['assessment']['cause'] == 'unknown'
    assert joined['assessment']['stored_state'] == 'succeeded'
    assert joined['domain_completion'] == 'not_assessed'
    legacy = recorded_attempt(); legacy['diagnostic'].pop('origin_request_id')
    old = processing_trace({'processing_attempts':[legacy]})
    assert 'origin_request_not_recorded' in processing_incident(old)['missing_evidence']


def test_processing_only_cli_exports_redacted_trace_without_browser(tmp_path):
    import subprocess
    import sys
    from src.processing_trace_v1 import processing_trace
    trace = processing_trace({'processing_attempts':[recorded_attempt()]})
    trace['secret'] = 'private-content'
    source = tmp_path / 'processing.json'; source.write_text(json.dumps(trace))
    output = tmp_path / 'incident'
    result = subprocess.run([sys.executable, 'scripts/export_section_incident.py',
        '--processing', str(source), '--output', str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    data = json.loads((output/'incident.json').read_text())
    assert data['processing']['selected_attempt_id'] == 'pa_'+'a'*32
    assert 'private' not in (output/'incident.json').read_text()
    assert len(data['input_sha256']['processing']) == 64
    assert 'Stored processing state: succeeded' in (output/'summary.txt').read_text()


def test_semantic_resume_trace_keeps_completed_candidate_and_targets_only_open_work(console, monkeypatch):
    from tests.test_recoverable_formation_v1 import system
    from tests.test_recommendation_coverage_v1 import FIRST, SECOND
    from src.processing_trace_v1 import processing_trace
    state, sid, actor, reviewer, calls, mode, make, bind_semantics = system(
        console.root, make_console=lambda: restart(console))
    before = state.snapshot_objects(sid)
    complete = next(o for o in before if o['content']['clean_text'] == FIRST)
    initial = processing_trace(state._envelope(sid))
    assert initial['artifacts']['formation_incomplete'] is True
    current = make(); bind_semantics(current); mode['broken'] = False
    def forbidden(*args, **kwargs):
        raise AssertionError('resume must retain extraction')
    monkeypatch.setattr(current, '_extract', forbidden)
    monkeypatch.setattr(SourceProcessingDispatcher, 'notify', lambda *args: False)
    app = create_console_app(current); app.add_middleware(RequestDiagnostics)
    with TestClient(app, base_url='https://testserver') as client:
        assert client.post('/login', data={'username':'author', 'password':'strong-test-password'}, follow_redirects=False).status_code == 303
        response = client.post('/source-selection/start', data={'document':sid,
            'command_id':'targeted-resume', 'expected_revision':current.objects_revision(sid)}, follow_redirects=False)
        assert response.status_code == 303
        attempt = deepcopy(current._envelope(sid)['processing_attempts'][-1])
        assert attempt['kind'] == 'resume'
        current.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
        trace = client.get('/source-selection/processing-trace', params={'document':sid}).json()
        assert trace['attempts'][-1]['origin_request_id'] == response.headers['x-metis-request-id']
        assert trace['attempts'][-1]['stored_state'] == 'succeeded'
        assert trace['artifacts']['semantic_identity_hash']
    final = make()
    assert next(o for o in final.snapshot_objects(sid) if o['object_id'] == complete['object_id']) == complete
    assert len(calls) == 3
    assert [b['text'] for b in json.loads(calls[-1]['input'][1]['content'])['source_blocks']] == [SECOND]


def test_background_phases_do_not_reopen_finished_http_evidence(console, monkeypatch):
    from threading import Event
    from src.request_diagnostics_v1 import _LOGGER
    from tests.test_availability_repair import drain
    actor, reviewer = accounts(console)
    sid = receive(console, actor, reviewer, 'background')
    entered, release = Event(), Event()
    inherited_metrics = []
    def blocked(*args):
        from src.console_performance_v1 import _CURRENT as performance_current
        inherited_metrics.append(performance_current.get())
        entered.set(); assert release.wait(10)
        return provider(*args)
    bind(console, blocked)
    events = []
    monkeypatch.setattr(_LOGGER, 'info', lambda fmt, msg: events.append(json.loads(msg)))
    app = create_console_app(console)
    from src.console_performance_v1 import install_console_performance
    install_console_performance(app)
    with TestClient(app, base_url='https://testserver') as client:
        login(client)
        response = client.post('/source-selection/start', data={'document':sid,
            'command_id':'separate-http-work', 'expected_revision':console.objects_revision(sid)}, follow_redirects=False)
        rid = response.headers['x-metis-request-id']
        try:
            assert entered.wait(3)
            assert any(r['event'] == 'request_finished' and r.get('request_id') == rid for r in events)
        finally:
            release.set()
        drain(client, app)
    http = [r for r in events if r.get('request_id') == rid and r['event'] in
            {'request_started','phase_started','request_running','response_started','response_completed','request_finished'}]
    assert http[-1]['event'] == 'request_finished'
    assert inherited_metrics == [None]
    assert any(r['event'] == 'processing_finished' and r['request_id'] == rid for r in events)
    assert restart(console)._envelope(sid)['processing_attempts'][-1]['diagnostic']['origin_request_id'] == rid
