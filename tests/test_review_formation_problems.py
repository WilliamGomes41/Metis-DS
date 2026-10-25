"""#848: actual task-v1 → Review, problems, recovery and publication boundary.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit metrics slop releasebewijs
"""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from tests.test_availability_repair import accounts, bind, login, start, drain
from tests.test_recommendation_context_v3 import response_for
from tests.production_support import restart_production

FIRST = 'Gebruik geen zalf.'
SECOND = 'Controleer dagelijks de huid.'


def received(tmp_path, production_console, monkeypatch):
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console = production_console(root=tmp_path, processing_binder=lambda console: None)
    author, reviewer = accounts(console)
    calls, mode = [], {'broken': True}
    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload['input'][1]['content'])
        text = data['source_blocks'][0]['text']
        calls.append(deepcopy(data))
        if mode.get('pause'):
            entered, release = mode['pause']
            entered.set()
            assert release.wait(15)
        proposal = response_for(payload, text)
        if mode.get('missing_context') and text == SECOND:
            proposal['objects'][0]['context_evidence'] = [
                {'role': 'condition', 'span': None, 'unresolved_reason': 'context_uncertain'}]
        if mode['broken'] and text == SECOND:
            proposal['objects'][0]['field_evidence']['recommended_action']['span']['literal'] = 'verzonnen bronbewijs'
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(proposal)}]}]}
    bind(console, provider)
    sid = console.receive_source(actor_id=author, filename='smetten-pattern.html',
        data=f'<html><body><h1>Advies A</h1><p>{FIRST}</p><h1>Advies B</h1><p>{SECOND}</p></body></html>'.encode(),
        content_type='text/html', ingest_kind='new', title='Smetten patroon',
        version='1', date='2026-10-25', live_url='', class_='richtlijn', family='fixture',
        named_reviewers=[reviewer])['snapshot_id']
    return console, sid, author, reviewer, calls, mode, provider


def execute(console, sid, author, command):
    attempt, fresh = console.reserve_source_selection(actor_id=author, snapshot_id=sid,
        command_id=command, expected_revision=console.objects_revision(sid))
    if fresh:
        console.execute_source_selection(actor_id=author, snapshot_id=sid, attempt=attempt)
    return attempt


def test_durable_independent_valid_proposal_reaches_review(tmp_path, production_console, monkeypatch):
    console, sid, author, reviewer, calls, mode, provider = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'start')
    candidates = [o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == 'recommendation']
    assert len(candidates) == 1
    assert candidates[0]['content']['clean_text'] == FIRST
    assert candidates[0]['metadata']['admission']['gate_result'] == 'allowed'
    assert console.processing_status(sid)['formation_incomplete']
    assert console.processing_status(sid)['resume_allowed']
    assert 'source_formation_incomplete' in console.publication_readiness(sid)['blockers']
    client = TestClient(console._metis_test_application)
    login(client, 'reviewer')
    response = client.get('/review', params={'document': sid, 'object': candidates[0]['object_id'], 'task': 'contextual'})
    assert response.status_code == 200 and FIRST in response.text


def test_whitespace_ranges_are_not_model_work():
    from src.bounded_formation_v1 import _durable_targets
    block = {'block_id': 'b', 'text': '  Advies. \n\t '}
    proposal = {'objects': [{'spans': [{'block_id': 'b', 'start': 2, 'end': 9}]}], 'source_assessments': []}
    assert _durable_targets([block], proposal) == []
    assert _durable_targets([{'block_id': 'b', 'text': 'Voorwaarde. Advies.'}],
        {'objects': [{'spans': [{'block_id': 'b', 'start': 12, 'end': 19}]}], 'source_assessments': []})


def test_problems_restart_targeted_recovery_and_duplicate(tmp_path, production_console, monkeypatch):
    from src.formation_problems_v1 import collect
    console, sid, author, reviewer, calls, mode, provider = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'initial')
    before = console.snapshot_objects(sid)
    first = next(o for o in before if o.get('proposed_object_type') == 'recommendation')
    report = collect(console, actor_id=author, snapshot_id=sid)
    failures = [r for r in report['problems'] if r['code'] == 'semantic_evidence_literal_not_found']
    assert failures and all(r['spans'] and len(r['actions']) > 1 for r in failures)
    problem_ids = [r['problem_id'] for r in report['problems']]
    restarted = restart_production(console)
    bind(restarted, provider)
    assert restarted.snapshot_objects(sid) == before
    assert [r['problem_id'] for r in collect(restarted, actor_id=author, snapshot_id=sid)['problems']] == problem_ids
    client = TestClient(restarted._metis_test_application)
    login(client)
    page = client.get('/formation-problems', params={'document': sid})
    assert page.status_code == 200
    assert 'Open bronwerk hervatten' in page.text
    assert 'Bronbereik bekijken en behandelen' in page.text
    assert restarted.snapshot_objects(sid) == before and len(calls) == 3
    mode['broken'] = False
    revision = restarted.objects_revision(sid)
    with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
        restarted.reserve_source_selection(actor_id=author, snapshot_id=sid,
            command_id='stale', expected_revision='stale')
    recovered = execute(restarted, sid, author, 'recover')
    assert recovered['kind'] == 'resume'
    assert len(calls) == 4 and [b['text'] for b in calls[-1]['source_blocks']] == [SECOND]
    current = restarted.snapshot_objects(sid)
    assert next(o for o in current if o['object_id'] == first['object_id']) == first
    assert len([o for o in current if o.get('proposed_object_type') == 'recommendation']) == 2
    assert not restarted.processing_status(sid)['formation_incomplete']
    assert 'source_formation_incomplete' not in restarted.publication_readiness(sid)['blockers']
    assert not restarted.publication_readiness(sid)['publish_allowed']
    assert not [r for r in collect(restarted, actor_id=author, snapshot_id=sid)['problems'] if r['code'] == 'semantic_evidence_literal_not_found']
    same, fresh = restarted.reserve_source_selection(actor_id=author, snapshot_id=sid,
        command_id='recover', expected_revision=revision)
    assert not fresh and same['attempt_id'] == recovered['attempt_id'] and len(calls) == 4


def test_review_does_not_hide_remaining_problems_or_allow_reextract(tmp_path, production_console, monkeypatch):
    from src.formation_problems_v1 import collect
    console, sid, author, reviewer, calls, mode, provider = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'initial')
    first = next(o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == 'recommendation')
    console.review_object(actor_id=reviewer, snapshot_id=sid, object_id=first['object_id'],
        decision='approve', confirmed_object_type='recommendation',
        recommendation_direction='against', recommendation_strength_level='not_stated')
    reviewed = console.snapshot_objects(sid)
    report = collect(console, actor_id=reviewer, snapshot_id=sid)
    assert any(r['code'] == 'semantic_evidence_literal_not_found' for r in report['problems'])
    assert not report['processing']['resume_allowed']
    client = TestClient(console._metis_test_application)
    login(client, 'reviewer')
    page = client.get('/formation-problems', params={'document': sid})
    assert page.status_code == 200 and 'Modelherstel is nu niet beschikbaar' in page.text
    assert 'Bronbereik bekijken en behandelen' in page.text and 'Open bronwerk hervatten' not in page.text
    with pytest.raises(ConsoleError, match='pre_review_retry_existing_work'):
        execute(console, sid, author, 'guarded')
    assert console.snapshot_objects(sid) == reviewed
    assert not console.publication_readiness(sid)['publish_allowed']


def test_unauthorized_problem_read_is_denied(tmp_path, production_console, monkeypatch):
    console, sid, author, reviewer, calls, mode, provider = received(tmp_path, production_console, monkeypatch)
    outsider = console.create_account(username='outsider', password='fixture-only', roles=('reviewer',))
    client = TestClient(console._metis_test_application)
    login(client, 'outsider')
    denied = client.get('/formation-problems', params={'document': sid})
    assert denied.status_code == 400  # Existing ConsoleError HTTP contract.
    assert 'Smetten patroon' not in denied.text
    assert len(calls) == 0


def test_necessary_missing_context_stays_in_repair(tmp_path, production_console, monkeypatch):
    from src.formation_problems_v1 import collect
    console, sid, author, reviewer, calls, mode, provider = received(tmp_path, production_console, monkeypatch)
    mode.update(broken=False, missing_context=True)
    execute(console, sid, author, 'context')
    candidates = {o['content']['clean_text']: o for o in console.snapshot_objects(sid)
                  if o.get('proposed_object_type') == 'recommendation'}
    assert candidates[FIRST]['metadata']['admission']['gate_result'] == 'allowed'
    assert candidates[SECOND]['metadata']['admission']['gate_result'] == 'blocked'
    report = collect(console, actor_id=reviewer, snapshot_id=sid)
    assert any(row['kind'] == 'admission' and row['object_id'] == candidates[SECOND]['object_id']
               and row['code'] == 'context_necessary_unresolved' for row in report['problems'])
    with pytest.raises(ConsoleError):
        console.review_object(actor_id=reviewer, snapshot_id=sid, object_id=candidates[SECOND]['object_id'],
            decision='approve', confirmed_object_type='recommendation',
            recommendation_direction='for', recommendation_strength_level='not_stated')
    assert not console.publication_readiness(sid)['publish_allowed']


def test_exact_human_source_disposition_closes_only_its_problem(tmp_path, production_console, monkeypatch):
    from src.formation_problems_v1 import collect
    from src.source_accountability_v1 import is_source_record
    console, sid, author, reviewer, calls, mode, provider = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'initial')
    source = next(o for o in console.snapshot_objects(sid) if is_source_record(o) and o['content']['clean_text'] == SECOND)
    console.review_object(actor_id=reviewer, snapshot_id=sid, object_id=source['object_id'],
                          decision='reject', comment='Expliciet bronbesluit voor precies dit bereik.')
    # A generic rejection is not source-accountability closure in V2.
    assert console.processing_status(sid)['formation_incomplete']
    console.confirm_source_context(actor_id=reviewer, snapshot_id=sid,
        source_object_id=source['object_id'], role='excluded', target_object_ids=[],
        reason='Expliciete bronafhandeling voor dit exacte bereik.', command_id='source-disposition',
        expected_revision=console.objects_revision(sid))
    report = collect(console, actor_id=reviewer, snapshot_id=sid)
    assert not [r for r in report['problems'] if r['code'] == 'semantic_evidence_literal_not_found']
    assert not console.processing_status(sid)['formation_incomplete']
    assert not console.publication_readiness(sid)['publish_allowed']  # A still needs review.
    assert console._envelope(sid)['semantic_replay']['provider_evidence']['pending_rejections']
    assert len(calls) == 3


def test_old_whitespace_failure_closes_only_for_verified_empty_source():
    from src.recoverable_formation_v1 import pending_rejections
    ref = {'block_id': 'b', 'start': 0, 'end': 3}
    evidence = {'error_code': 'source_task_budget_exhausted', 'target_spans': [ref]}
    proposal = {'objects': [], 'source_assessments': []}
    assert pending_rejections(evidence, proposal)
    assert pending_rejections(evidence, proposal, blocks=[{'block_id': 'b', 'text': ' \n\t'}]) == []
    assert pending_rejections(evidence, proposal, blocks=[{'block_id': 'b', 'text': 'Als'}])
    assert pending_rejections(evidence, proposal, blocks=[{'block_id': 'other', 'text': '   '}])


def test_actual_start_does_not_call_model_for_whitespace_gaps(tmp_path, production_console, monkeypatch):
    console, _, author, reviewer, _, _, _ = received(tmp_path, production_console, monkeypatch)
    console = restart_production(console)
    requests = []
    def provider(_url, _headers, payload, _timeout):
        requests.append(json.loads(payload['input'][1]['content']))
        proposal = response_for(payload, FIRST)
        proposal['objects'].extend(response_for(payload, SECOND)['objects'])
        return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(proposal)}]}]}
    bind(console, provider)
    sid = console.receive_source(actor_id=author, filename='gap.html',
        data=f'<html><body><p>{FIRST} {SECOND}</p></body></html>'.encode(),
        content_type='text/html', ingest_kind='new', title='Witruimte', version='1',
        date='2026-10-25', live_url='', class_='richtlijn', family='fixture', named_reviewers=[reviewer])['snapshot_id']
    execute(console, sid, author, 'gap-start')
    assert len(requests) == 1
    assert requests[0]['source_blocks'][0]['text'] == FIRST + ' ' + SECOND
    assert len([o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == 'recommendation']) == 2
    assert not console.processing_status(sid)['formation_incomplete']


def test_real_browser_navigation_and_raad_read_only(tmp_path, production_console, monkeypatch):
    import os
    import socket
    import subprocess
    from threading import Event, Thread
    import time
    from uuid import uuid4
    import uvicorn
    from src.view_check import context
    from tests.test_view_check_postgres import configure
    module = os.environ['METIS_PLAYWRIGHT_MODULE']
    browser = os.environ['METIS_BROWSER_EXECUTABLE']
    console, sid, author, reviewer, calls, mode, provider = received(tmp_path, production_console, monkeypatch)
    entered, release = Event(), Event()
    mode['pause'] = entered, release
    app = console._metis_test_application
    sock = socket.socket(); sock.bind(('127.0.0.1', 0))
    origin = f'http://127.0.0.1:{sock.getsockname()[1]}'
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False))
    thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    process = None
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        marker = tmp_path / 'navigated'
        env = dict(os.environ, METIS_BROWSER_BASE=origin, METIS_PROBLEM_DOCUMENT=sid,
            METIS_PROBLEM_NAVIGATED=str(marker), METIS_PROBLEM_SCREENSHOT=str(tmp_path/'problems.png'))
        process = subprocess.Popen(['node', 'tests/browser_formation_problems.cjs'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        deadline = time.monotonic() + 20
        while not entered.is_set() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        if not entered.is_set() and process.poll() is not None:
            stdout, stderr = process.communicate(timeout=2)
            pytest.fail('Browser failed before processing: ' + stderr)
        assert entered.is_set(), 'Browser did not reach the existing processing command'
        deadline = time.monotonic() + 12
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        assert marker.exists(), 'Problem navigation failed during model processing'
        assert len(calls) == 1 and console._envelope(sid)['processing_attempts'][-1]['state'] == 'running'
        release.set()
        stdout, stderr = process.communicate(timeout=25)
        assert process.returncode == 0, stderr
        assert json.loads(stdout)['navigatedWhileProcessing']
        assert len(calls) == 3 and console.processing_status(sid)['formation_incomplete']
        # Run the actual Raad investigation worker with a scoped capability.
        service = configure(app, console, None, tmp_path/'raad-evidence', origin=origin, module=module, browser=browser)
        pinned = {**context(console, reviewer, sid), 'origin': origin}
        job = service.store.register(reviewer, sid, uuid4().hex, pinned)
        before = deepcopy(console._envelope(sid)), console.snapshot_objects(sid), console.object_review_bindings(sid)
        service.execute_one()
        result = service.store.get(job['id'])
        assert result['state'] == 'completed', result
        assert all(row['verdict'] == 'pass' for row in result['result']['checks'])
        assert result['result']['coverage']['formation_problems'] == 'first_page_read_only'
        assert before == (console._envelope(sid), console.snapshot_objects(sid), console.object_review_bindings(sid))
    finally:
        release.set()
        if process is not None and process.poll() is None:
            process.kill(); process.communicate(timeout=5)
        server.should_exit = True
        thread.join(6)
        sock.close()
