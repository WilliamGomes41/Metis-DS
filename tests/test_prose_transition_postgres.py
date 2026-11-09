"""HA-4 explicit transition uses the real workflow and worker fences.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import psycopg
import pytest
from starlette.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.vorming import prose_transition_v1 as transition
from src.vorming.source_processing_dispatch_v1 import pending
from tests.production_support import application_for, restart_production
from tests.test_recommendation_context_v3 import response_for


def setup_command(tmp_path, production_console, monkeypatch, request_hook=None, *, task_storage='v1', source_class='richtlijn'):
    from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.vorming.source_bound_fields_v3 import MODE
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', task_storage)
    console = production_console(root=tmp_path, processing_binder=lambda console: None)
    actor = console.create_account(username='researcher.d54', password='d54-secret',
                                   roles=('researcher', 'reviewer'))['account_id']
    reviewer = console.create_account(username='named', password='fixture-secret', roles=('reviewer',))['account_id']
    tree = source_class == 'beslisboom'
    from tests.characterization.overview_support import TREE
    sid = console.receive_source(actor_id=actor, filename='transition.json' if tree else 'transition.html',
        content_type='application/json' if tree else 'text/html',
        data=TREE if tree else b'<html><body><h1>Een</h1><p>Gebruik geen zalf.</p><h1>Twee</h1><p>Controleer dagelijks de huid.</p></body></html>',
        ingest_kind='new', title='Overgang', version='1', date='2026-11-09', live_url='',
        class_=source_class, family='test', named_reviewers=[reviewer])['snapshot_id']
    calls = []
    def provider(_url, _headers, payload, _timeout):
        text = json.loads(payload['input'][1]['content'])['source_blocks'][0]['text']
        calls.append(text)
        if request_hook is not None:
            request_hook(text)
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(response_for(payload, text))}]}]}
    def bind(target):
        bind_pre_review_semantic_processing(target, environ={'METIS_PASSAGE_FORMATION_MODE': MODE,
            'METIS_LLM_API_KEY': 'fixture', 'METIS_LLM_MODEL': 'test'}, post_json=provider)
    bind(console)
    attempt, _ = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id='start-prose', expected_revision=console.objects_revision(sid))
    return console, actor, sid, attempt, calls, bind


def request(console, actor, sid, attempt):
    return dict(actor_id=actor, snapshot_id=sid, attempt_id=attempt['attempt_id'],
                command_id='explicit-prose-stop', expected_revision=console.objects_revision(sid),
                reason='Overgang naar menselijke bronselectie')


@pytest.mark.parametrize(('layout', 'task_storage'), [('legacy', 'legacy'), ('legacy', 'v1'), ('v1', 'v1')])
def test_http_stop_is_durable_idempotent_and_does_not_resume_old_work(tmp_path, production_console, monkeypatch, layout, task_storage):
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', layout)
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch, task_storage=task_storage)
    before = deepcopy(console._envelope(sid))
    client = TestClient(application_for(console))  # No startup delivery before the explicit stop.
    assert client.post('/login', data={'username': 'researcher.d54', 'password': 'd54-secret'}).status_code == 200
    view = client.get('/source-selection/transition', params={'document': sid})
    assert view.status_code == 200 and view.json()['transition'] is None
    command = request(console, actor, sid, attempt)
    command.pop('actor_id')
    stopped = client.post('/source-selection/transition', json=command)
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()['stopped_attempt_ids'] == [attempt['attempt_id']]
    assert stopped.json()['external_cancellation'] == 'not_guaranteed'
    assert client.post('/source-selection/transition', json=command).json() == stopped.json()
    assert client.post('/source-selection/transition', json={**command, 'reason': 'Andere reden'}).status_code == 409
    resumed = restart_production(console); bind(resumed)
    result = transition.inventory(resumed, actor_id=actor, snapshot_id=sid)
    assert result['transition'] == stopped.json()
    assert not pending(resumed)
    assert resumed._envelope(sid)['sha256'] == before['sha256']
    assert resumed.snapshot_objects(sid) == []
    status = resumed.processing_status(sid, actor_id=actor)
    assert not status['retry_allowed'] and not status['resume_allowed']
    with pytest.raises(ConsoleError, match=transition.STOPPED):
        resumed.reserve_source_selection(actor_id=actor, snapshot_id=sid, command_id='new-ai-job',
                                         expected_revision=resumed.objects_revision(sid))
    if task_storage == 'legacy':
        with pytest.raises(ConsoleError, match='processing_attempt_not_active'):
            resumed.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    else:
        resumed.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    assert resumed._processing_command_envelope(sid)['processing_attempts'][-1]['state'] == 'failed'
    assert calls == []


def test_unauthorized_stale_and_missing_guards_leave_work_unchanged(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, _ = setup_command(tmp_path, production_console, monkeypatch)
    command = request(console, actor, sid, attempt)
    stranger = console.create_account(username='outside', password='fixture-secret', roles=('reviewer',))['account_id']
    with pytest.raises(ConsoleError, match='reviewer_not_named_on_snapshot'):
        transition.stop(console, **{**command, 'actor_id': stranger})
    with pytest.raises(ConsoleError, match='prose_transition_revision_stale'):
        transition.stop(console, **{**command, 'expected_revision': 'stale'})
    with console.workflow_document_store._connect() as con:
        con.execute('ALTER TABLE workflow.documents DISABLE TRIGGER guard_prose_transition_document')
    try:
        with pytest.raises(ConsoleError, match='prose_transition_storage_not_ready'):
            transition.stop(console, **command)
    finally:
        with console.workflow_document_store._connect() as con:
            con.execute('ALTER TABLE workflow.documents ENABLE TRIGGER guard_prose_transition_document')
    assert transition.inventory(console, actor_id=actor, snapshot_id=sid)['transition'] is None
    assert console._processing_command_envelope(sid)['processing_attempts'][-1]['state'] == 'running'
    assert calls == []


@pytest.mark.parametrize('layout', ['legacy', 'v1'])
def test_native_guards_reject_rollback_writer_and_old_attempt_resurrection(tmp_path, production_console, monkeypatch, layout):
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', layout)
    console, actor, sid, attempt, calls, _ = setup_command(tmp_path, production_console, monkeypatch)
    receipt = transition.stop(console, **request(console, actor, sid, attempt))
    with console.workflow_document_store._connect() as con:
        with pytest.raises(psycopg.Error, match='prose_transition_history_immutable'):
            with con.transaction():
                if layout == 'v1':
                    con.execute("UPDATE workflow.document_inputs SET metadata=metadata-'prose_transitions' WHERE snapshot_id=%s", (sid,))
                else:
                    con.execute("UPDATE workflow.documents SET envelope_payload=envelope_payload-'prose_transitions' WHERE snapshot_id=%s", (sid,))
        with pytest.raises(psycopg.Error, match=transition.STOPPED):
            with con.transaction():
                con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{state}','\"running\"') WHERE attempt_id=%s", (attempt['attempt_id'],))
    assert transition.inventory(console, actor_id=actor, snapshot_id=sid)['transition'] == receipt
    assert calls == []


def test_stop_wins_against_provider_in_flight_and_retains_preparation(tmp_path, production_console, monkeypatch):
    entered, release = Event(), Event()
    def pause(_text):
        entered.set()
        assert release.wait(15)
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch, pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(console.execute_source_selection, actor_id=actor, snapshot_id=sid, attempt=attempt)
        if not entered.wait(10):
            future.result(timeout=1)
            pytest.fail('Provider hook was not reached')
        other = restart_production(console); bind(other)
        try:
            stopped = transition.stop(other, **request(other, actor, sid, attempt))
        finally:
            release.set()
        with pytest.raises(ConsoleError):
            future.result(timeout=15)
    assert transition.inventory(other, actor_id=actor, snapshot_id=sid)['transition'] == stopped
    assert len(calls) == 1 and other.snapshot_objects(sid) == []
    with other.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.prepared_extraction_versions WHERE snapshot_id=%s', (sid,)).fetchone()['n'] > 0


@pytest.mark.parametrize('layout', ['legacy', 'v1'])
def test_restore_retains_stop_and_requires_capable_storage(tmp_path, production_console, monkeypatch, layout):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.publication.publication_chain_recovery_v1 import PublicationChainRecoveryError
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter, _upgrade_workflow_state
    from tests.postgres_support import database, install_schema
    from tests.production_support import production_application
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', layout)
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    source = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(console.workflow_document_store.config))
    legacy = source.export_state()
    legacy['workflow_recovery_version'] = 12
    assert _upgrade_workflow_state(legacy) == {**legacy, 'workflow_recovery_version': 13}
    receipt = transition.stop(console, **request(console, actor, sid, attempt))
    archive = source.export_state()
    for version in (7, 11, 12):
        with pytest.raises(PublicationChainRecoveryError, match='workflow_prose_transition_reexport_required'):
            _upgrade_workflow_state({**archive, 'workflow_recovery_version': version})
    with database(console.workflow_document_store.config.dsn) as config:
        install_schema(config.dsn)
        target = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config))
        with target.store._connect() as con:
            con.execute('ALTER TABLE workflow.processing_attempts DISABLE TRIGGER guard_prose_transition_attempt')
        with pytest.raises(PublicationChainRecoveryError):
            target.restore_state(archive)
        target.assert_empty()
        with target.store._connect() as con:
            con.execute('ALTER TABLE workflow.processing_attempts ENABLE TRIGGER guard_prose_transition_attempt')
        target.restore_state(archive)
        restored = production_application(console.root, config, processing_binder=lambda console: None,
            runtime=console.runtime, source_store=console.source_store).state.operations_kernel
        bind(restored)
        assert transition.inventory(restored, actor_id=actor, snapshot_id=sid)['transition'] == receipt
        assert not pending(restored)
        with pytest.raises(ConsoleError, match=transition.STOPPED):
            restored.reserve_source_selection(actor_id=actor, snapshot_id=sid, command_id='restore-retry',
                                               expected_revision=restored.objects_revision(sid))
        assert calls == [] and restored.snapshot_objects(sid) == []


def test_failed_commit_rolls_back_stop_and_concurrent_duplicate_has_one_receipt(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, bind = setup_command(tmp_path, production_console, monkeypatch)
    command = request(console, actor, sid, attempt)
    with monkeypatch.context() as patch:
        def fail(**kwargs):
            raise RuntimeError('injected commit failure')
        patch.setattr(console, '_commit_prepared_store', fail)
        with pytest.raises(RuntimeError, match='injected commit failure'):
            transition.stop(console, **command)
    assert transition.inventory(console, actor_id=actor, snapshot_id=sid)['transition'] is None
    assert console._processing_command_envelope(sid)['processing_attempts'][-1]['state'] == 'running'
    other = restart_production(console); bind(other)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(transition.stop, target, **command) for target in (console, other)]
        receipts = [f.result(timeout=15) for f in futures]
    assert receipts[0] == receipts[1]
    assert len(other._envelope(sid)[transition.KEY]) == 1
    assert calls == []


def test_tree_and_human_build_are_not_prose_stop_targets(tmp_path, production_console, monkeypatch):
    from src.vorming import human_annotation_build_v1 as build
    from tests.test_human_annotation_build_postgres import saved_source, closing
    tree, actor, sid, attempt, calls, _ = setup_command(tmp_path, production_console, monkeypatch, source_class='beslisboom')
    with pytest.raises(ConsoleError, match='prose_transition_prose_required'):
        transition.stop(tree, **request(tree, actor, sid, attempt))
    human, actor, sid, _ = saved_source(lambda **opts: production_console(isolated=True, **opts), tmp_path / 'human')
    receipt = build.finalize(human, actor_id=actor, **closing(build.overview(human, actor_id=actor, snapshot_id=sid)))
    attempt = {'attempt_id': receipt['attempt_id']}
    with pytest.raises(ConsoleError, match='prose_transition_prose_required'):
        transition.stop(human, **request(human, actor, sid, attempt))
    assert calls == []


def test_malformed_http_command_is_rejected_without_provider_or_stop(tmp_path, production_console, monkeypatch):
    console, actor, sid, attempt, calls, _ = setup_command(tmp_path, production_console, monkeypatch)
    client = TestClient(application_for(console))
    client.post('/login', data={'username': 'researcher.d54', 'password': 'd54-secret'})
    assert client.post('/source-selection/transition', content='{').status_code == 422
    command = request(console, actor, sid, attempt)
    command.pop('actor_id')
    assert client.post('/source-selection/transition', json={**command, 'snapshot_id': []}).status_code == 409
    assert transition.inventory(console, actor_id=actor, snapshot_id=sid)['transition'] is None
    assert calls == []
