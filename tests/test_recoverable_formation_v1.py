"""Formation failure isolation, restart, targeted recovery and publication gates.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery version-compat
# release-control-evidence: beschikbaarheid toegang kwaliteit metrics slop releasebewijs
"""
from copy import deepcopy
import json

import pytest

from src.operations_console_v1 import ConsoleError
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.recoverable_formation_v1 import prepare, incomplete
from src.review_closure_v1 import ReviewClosureConsole
from src.source_accountability_v1 import evidence_of
from tests.test_recommendation_context_v3 import response_for, source
from tests.test_recommendation_coverage_v1 import FIRST, SECOND
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


def system(tmp_path, *, broken=True, make_console=None, containers=False):
    make_console = make_console or (lambda: ReviewClosureConsole(
        root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime'))
    state = make_console()
    author = state.create_account(username='author', password='strong-test-password', roles=('researcher',))
    reviewer = state.create_account(username='reviewer', password='strong-test-password', roles=('reviewer', 'publisher'))
    calls = []
    mode = {'broken': broken, 'dependency_failure': False}
    def provider(_url, _headers, payload, _timeout):
        calls.append(payload)
        data = json.loads(payload['input'][1]['content'])
        target = SECOND if data.get('selection_targets') else FIRST
        if mode.get('pause'):
            entered, release = mode['pause']
            entered.set()
            assert release.wait(10)
        if mode['dependency_failure']:
            raise ConsoleError('pre_review_llm_connection_failed')
        proposal = response_for(payload, target)
        if containers and target == FIRST:
            context = next(b for b in data['source_blocks'] + data['evidence_blocks'] if b['text'] == 'Bij volwassenen.')
            proposal['objects'][0]['context_evidence'] = [{'role': 'scope', 'span': {
                'block_id': context['block_id'], 'literal': context['text'], 'occurrence': 0}, 'unresolved_reason': None}]
        if mode['broken'] and target == SECOND:
            proposal['objects'][0]['field_evidence']['recommended_action']['span']['literal'] = 'invented'
        return {'id': f'call-{len(calls)}', 'status': 'completed', 'output': [
            {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(proposal)}]}]}
    def bind(state):
        bind_pre_review_semantic_processing(state, environ={'METIS_PASSAGE_FORMATION_MODE': 'semantic-source-bound-v3',
            'METIS_LLM_API_KEY': 'fixture', 'METIS_LLM_MODEL': 'fixture'}, post_json=provider)
    bind(state)
    extra = '<p>Versie: 1</p><p>Bij volwassenen.</p>' if containers else ''
    receipt = state.ingest(actor_id=author['account_id'], filename='test.html',
        data=f'<html><body><h1>Aanbevelingen</h1>{extra}<p>{FIRST}</p><p>{SECOND}</p></body></html>'.encode(),
        content_type='text/html', ingest_kind='new', title='Test', version='1.0', date='2026-10-05',
        live_url='', class_='richtlijn', family='test', named_reviewers=[reviewer['account_id']])
    return state, receipt['snapshot_id'], author['account_id'], reviewer['account_id'], calls, mode, make_console, bind


def partial_story(tmp_path, make_console=None):
    state, sid, actor, reviewer, calls, mode, make, bind = system(tmp_path, make_console=make_console)
    before = state.snapshot_objects(sid)
    first = next(o for o in before if o['content']['clean_text'] == FIRST)
    assert first['metadata']['admission']['gate_result'] == 'allowed'
    assert any(evidence_of(o).get('text') == SECOND for o in before)
    processing = state.processing_status(sid)
    assert processing['state'] == 'succeeded'
    assert processing['formation_state'] == 'pending'
    assert processing['formation_incomplete']
    assert processing['resume_allowed']
    assert processing['formation_progress']['pending_task_count'] > 0
    assert 'source_formation_incomplete' in state.publication_readiness(sid)['blockers']
    assert not state.publication_readiness(sid)['publish_allowed']

    restarted = make(); bind(restarted)
    assert restarted.snapshot_objects(sid) == before
    assert incomplete(restarted._envelope(sid))
    revision = restarted.objects_revision(sid)
    mode['broken'] = False
    command = dict(actor_id=actor, snapshot_id=sid, command_id='resume-1', expected_revision=revision)
    restarted.resume_formation(**command)
    assert len(calls) == 3  # no new primary call
    request = json.loads(calls[-1]['input'][1]['content'])
    assert [b['text'] for b in request['source_blocks']] == [SECOND]
    current = restarted.snapshot_objects(sid)
    assert next(o for o in current if o['object_id'] == first['object_id']) == first
    assert len([o for o in current if o.get('proposed_object_type') == 'recommendation']) == 2
    assert not incomplete(restarted._envelope(sid))
    processing = restarted.processing_status(sid)
    assert processing['formation_state'] == 'complete'
    assert processing['formation_progress']['pending_task_count'] == 0
    resume_attempt = restarted._envelope(sid)['processing_attempts'][-1]
    assert resume_attempt['kind'] == 'resume'
    assert resume_attempt['state'] == 'succeeded'
    assert resume_attempt['formation_progress_made'] is True
    assert 'source_formation_incomplete' not in restarted.publication_readiness(sid)['blockers']
    assert not restarted.publication_readiness(sid)['publish_allowed']  # reviews still required
    final = make(); bind(final)
    assert final.snapshot_objects(sid) == current
    assert final.resume_formation(**command)['snapshot_id'] == sid
    assert len(calls) == 3
    # Existing review authority remains exact; recovery cannot replace it.
    final.review_object(actor_id=reviewer, snapshot_id=sid, object_id=first['object_id'],
                        decision='approve', confirmed_object_type='recommendation',
                        recommendation_direction='for', recommendation_strength_level='not_stated')
    with pytest.raises(ConsoleError, match='pre_review_retry_existing_work'):
        final.resume_formation(**{**command, 'command_id': 'resume-reviewed',
                                'expected_revision': final.objects_revision(sid)})




def test_processing_status_projects_progress_for_pre_v10_bounded_evidence(tmp_path):
    state, sid, _, _, _, _, make, bind = system(tmp_path)
    envelope = deepcopy(state._envelope(sid))
    provider = envelope['semantic_replay']['provider_evidence']
    provider.pop('formation_progress', None)
    provider.pop('formation_state', None)
    state._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)

    restarted = make()
    bind(restarted)
    processing = restarted.processing_status(sid)
    assert processing['formation_state'] == 'pending'
    assert processing['formation_progress']['planned_task_count'] > 0
    assert processing['formation_progress']['pending_task_count'] > 0


def test_http_recovery_and_export_are_authorized_and_explicit(tmp_path):
    state, sid, actor, reviewer, calls, mode, _, _ = system(tmp_path)
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app, COOKIE
    from src.processing_evidence_export_v1 import processing_evidence_tables
    tables, _ = processing_evidence_tables(snapshot_id=sid, revision=state.objects_revision(sid),
        envelope=state._envelope(sid), objects=state.snapshot_objects(sid))
    assert tables['formation_findings'][0]['reason_code'] == 'semantic_evidence_literal_not_found'
    assert tables['formation_findings'][0]['evidence_kind'] == 'rejected_producer_proposal_not_approved_knowledge'
    assert len(tables['formation_progress']) == 1
    assert tables['formation_progress'][0]['formation_state'] == 'pending'
    assert tables['formation_progress'][0]['pending_task_count'] > 0
    client = TestClient(create_console_app(state))
    command = {'snapshot_id': sid, 'command_id': 'http-resume', 'expected_revision': state.objects_revision(sid)}
    assert client.post('/tree/resume-formation', data=command, follow_redirects=False).status_code in {302, 303, 401, 403}
    assert len(calls) == 2
    client.cookies.set(COOKIE, state.authenticate('author', 'strong-test-password')['token'])
    page = client.get('/settings/technical/processing', params={'document': sid})
    assert 'Naar Bronselectie voor Starten of Hervatten' in page.text and 'publicatie is geblokkeerd' in page.text
    assert 'Vormingstaken:' in page.text and 'nog open' in page.text
    mode['broken'] = False
    response = client.post('/tree/resume-formation', data=command, follow_redirects=False)
    assert response.status_code == 303 and response.headers['location'] == f'/source-selection?document={sid}'
    assert len(calls) == 2
    with client:
        from tests.test_availability_repair import drain
        assert client.post('/source-selection/start', data={'document': sid, 'command_id': command['command_id'],
            'expected_revision': command['expected_revision']}, follow_redirects=False).status_code == 303
        drain(client, client.app)
    assert len(calls) == 3


def test_recover_review_publish_restart_and_published_projection(tmp_path):
    from src.durable_publication_console_v1 import DurablePublicationConsole
    from src.product_api_v1 import create_product_app
    from src.usage_ledger_v1 import UsageLedger
    from fastapi.testclient import TestClient
    from tests.test_product_api_v1 import paths, registry, headers
    from tests.test_durable_publication_console_v1 import MemoryCanonicalStore, MemorySourceStore
    durable, source_store = MemoryCanonicalStore(), MemorySourceStore()
    def make():
        return DurablePublicationConsole(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime',
            immutable_source_store=source_store, canonical_publication_store=durable)
    state, sid, actor, reviewer, calls, mode, _, bind = system(tmp_path, make_console=make, containers=True)
    def product_client():
        ps = paths(tmp_path)
        return TestClient(create_product_app('real', paths=ps, tenant_registry=registry(docs=('*',)),
            canonical_publication_store=durable, immutable_source_store=source_store,
            usage_ledger=UsageLedger(ps.usage_db), api_access_mode='legacy'))
    api = product_client()
    candidate_id = next(obj['object_id'] for obj in state.snapshot_objects(sid)
                        if obj.get('proposed_object_type') == 'recommendation')
    assert api.get('/v1/knowledge/' + candidate_id, headers=headers()).status_code == 404
    assert state._projection_from_authority() == []
    assert state.publish(actor_id=reviewer, snapshot_id=sid)['status'] == 'BLOCKED'
    mode['broken'] = False
    state.resume_formation(actor_id=actor, snapshot_id=sid, command_id='recover', expected_revision=state.objects_revision(sid))
    for obj in state.snapshot_objects(sid):
        if obj.get('proposed_object_type') == 'recommendation':
            state.review_object(actor_id=reviewer, snapshot_id=sid, object_id=obj['object_id'],
                decision='approve', confirmed_object_type='recommendation', recommendation_direction='for',
                recommendation_strength_level='not_stated')
    assert state.publication_readiness(sid)['publication_ready']
    assert state.publish(actor_id=reviewer, snapshot_id=sid)['status'] == 'PASS'
    projection = state._projection_from_authority()
    assert len(projection) == 2
    served = api.get('/v1/knowledge/' + candidate_id, headers=headers())
    assert served.status_code == 200
    assert 'Bij volwassenen.' in json.dumps(served.json())
    containers = state.snapshot_containers(sid)
    assert {r['usage']['kind'] for r in containers['source']} == {'document_information', 'linked_context'}
    assert all(r['usage']['accounted'] for r in containers['source'])
    for r in containers['source']:
        assert api.get('/v1/knowledge/' + r['record']['object_id'], headers=headers()).status_code == 404
    restarted = make(); bind(restarted)
    assert restarted._projection_from_authority() == projection
    after_restart = product_client().get('/v1/knowledge/' + candidate_id, headers=headers())
    assert after_restart.status_code == 200
    assert {k: v for k, v in after_restart.json().items() if k != 'request_id'} == {
        k: v for k, v in served.json().items() if k != 'request_id'}
    assert not restarted.processing_status(sid)['resume_allowed']
    with pytest.raises(ConsoleError, match='pre_review_retry_existing_work'):
        restarted.resume_formation(actor_id=actor, snapshot_id=sid, command_id='published',
                                   expected_revision=restarted.objects_revision(sid))


def test_partial_restart_targeted_recovery_duplicate_and_review_guard(tmp_path):
    partial_story(tmp_path)


def test_postgres_partial_restart_targeted_recovery(workflow_postgres, tmp_path):
    from tests.test_review_batch_atomic_postgres import _console
    partial_story(tmp_path, lambda: _console(tmp_path, workflow_postgres))


def test_recovery_stale_permission_failure_and_no_silent_completion(tmp_path):
    state, sid, actor, reviewer, calls, mode, _, _ = system(tmp_path)
    before = state.snapshot_objects(sid)
    revision = state.objects_revision(sid)
    with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
        state.resume_formation(actor_id=actor, snapshot_id=sid, command_id='stale', expected_revision='stale')
    outsider = state.create_account(username='outsider', password='strong-test-password', roles=('reviewer',))
    with pytest.raises(ConsoleError, match='reviewer_not_named_on_snapshot'):
        state.resume_formation(actor_id=outsider['account_id'], snapshot_id=sid, command_id='outsider', expected_revision=revision)
    assert len(calls) == 2
    mode['dependency_failure'] = True
    state.resume_formation(actor_id=actor, snapshot_id=sid, command_id='provider-failed', expected_revision=revision)
    assert state.snapshot_objects(sid) == before
    assert incomplete(state._envelope(sid))
    assert not state.publication_readiness(sid)['publish_allowed']


def test_failed_activation_retains_previous_bundle_and_can_restart(tmp_path, monkeypatch):
    state, sid, actor, _, calls, mode, make, bind = system(tmp_path)
    before = state.snapshot_objects(sid)
    revision = state.objects_revision(sid)
    original = state._commit_prepared_store
    def fail(**kwargs):
        if kwargs.get('objects'):
            raise RuntimeError('injected durable activation failure')
        return original(**kwargs)
    monkeypatch.setattr(state, '_commit_prepared_store', fail)
    mode['broken'] = False
    with pytest.raises(RuntimeError, match='injected durable'):
        state.resume_formation(actor_id=actor, snapshot_id=sid, command_id='commit-failed', expected_revision=revision)
    assert state.snapshot_objects(sid) == before
    restarted = make(); bind(restarted)
    assert restarted.snapshot_objects(sid) == before
    assert restarted._envelope(sid)['processing_attempts'][-1]['state'] == 'failed'
    assert incomplete(restarted._envelope(sid))


def test_concurrent_resume_cannot_overwrite_active_attempt(tmp_path):
    from threading import Event, Thread
    state, sid, actor, _, calls, mode, _, _ = system(tmp_path)
    revision = state.objects_revision(sid)
    entered, release = Event(), Event()
    mode.update(broken=False, pause=(entered, release))
    outcomes = []
    def work():
        try:
            outcomes.append(state.resume_formation(actor_id=actor, snapshot_id=sid,
                command_id='one', expected_revision=revision))
        except BaseException as error:
            outcomes.append(error)
    thread = Thread(target=work); thread.start()
    try:
        assert entered.wait(10)
        for command_id in ('one', 'two'):
            with pytest.raises(ConsoleError, match='processing_attempt_in_progress'):
                state.resume_formation(actor_id=actor, snapshot_id=sid, command_id=command_id,
                                       expected_revision=revision)
    finally:
        release.set(); thread.join(15)
    assert len(outcomes) == 1 and isinstance(outcomes[0], dict), outcomes
    assert len(calls) == 3


def test_invalid_candidate_quarantines_related_candidate_not_independent_one():
    texts = [FIRST, SECOND, 'Bespreek de omstandigheden']
    fragments = [{**source(t)[0], 'fragment_id': str(i), 'fragment_hash': str(i)} for i, t in enumerate(texts)]
    from src.semantic_passage_v1 import semantic_source_blocks
    blocks = semantic_source_blocks(fragments)
    payload = {'input': [{'role': 'developer', 'content': ''}, {'role': 'user', 'content': json.dumps({'source_blocks': blocks, 'evidence_blocks': blocks})}]}
    objects = [response_for(payload, t)['objects'][0] for t in texts]
    objects[0]['field_evidence']['recommended_action']['span']['literal'] = 'invented'
    proposal = {'objects': objects, 'relations': [{'source_spans': objects[1]['spans'],
        'target_spans': objects[0]['spans'], 'evidence_spans': objects[1]['spans'], 'relation_type': 'applies_if'}],
        'source_assessments': [], 'abstain_reason': None}
    data = {'fragments': fragments, 'evidence_fragments': fragments, 'document_id': 'doc',
            'allowed_candidate_block_ids': {b['block_id'] for b in blocks}, 'field_contract_v3': True}
    result, evidence = prepare(proposal, blocks=blocks, evidence_blocks=blocks, validator_input=data)
    assert result['objects'][0]['spans'][0]['block_id'] == blocks[2]['block_id']
    assert len(result['objects']) == 1 and not result['relations']
    assert {r['reason_code'] for r in evidence['rejections']} == {'semantic_evidence_literal_not_found', 'semantic_dependency_rejected'}
    rejected_by_reason = {r['reason_code']: r for r in evidence['rejections']}
    assert rejected_by_reason['semantic_evidence_literal_not_found']['proposed_object_type'] == objects[0]['proposed_object_type']
    located = rejected_by_reason['semantic_evidence_literal_not_found']['spans']
    assert located[0]['block_id'] == objects[0]['spans'][0]['block_id']
    assert type(located[0]['start']) is int and type(located[0]['end']) is int
    assert 'literal' not in located[0]
    assert rejected_by_reason['semantic_dependency_rejected']['proposed_object_type'] == objects[1]['proposed_object_type']


def test_source_assessment_diagnostic_span_does_not_close_pending():
    from src.recoverable_formation_v1 import pending_rejections
    span = {'block_id': 'b', 'start': 0, 'end': 4}
    evidence = {'formation': {'rejections': [{
        'kind': 'source_assessment',
        'reason_code': 'semantic_source_assessment_invalid',
        'spans': [],
        'evidence_span': span,
        'source_assessment_role': 'background',
    }]}, 'supplementary_calls': []}
    proposal = {'objects': [{'spans': [span]}], 'source_assessments': []}
    pending = pending_rejections(evidence, proposal)
    assert pending[0]['spans'] == []
    assert pending[0]['evidence_span'] == span


def test_conflicting_reselection_cannot_replace_primary_or_clear_itself():
    from src.recoverable_formation_v1 import restrict_supplement, pending_rejections
    primary = {'objects': [{'spans': [{'block_id': 'b', 'start': 0, 'end': 5}], 'context_evidence': []}],
               'relations': [], 'source_assessments': [], 'abstain_reason': None}
    supplement = deepcopy(primary)
    supplement['objects'][0]['context_evidence'] = [{'unresolved_reason': 'uncertain'}]
    # Include independent new work: the conflicting duplicate may not discard it.
    supplement['objects'].append({'spans': [{'block_id': 'c', 'start': 0, 'end': 5}], 'context_evidence': []})
    supplement['source_assessments'] = [{
        'span': {'block_id': 'd', 'start': 0, 'end': 5},
        'role': 'background',
        'reason': 'historical_context',
    }]
    retained, rejected = restrict_supplement(supplement, primary=primary,
        targets=[{'span': {'block_id': 'c', 'start': 0, 'end': 5}}])
    assert [o['spans'][0]['block_id'] for o in retained['objects']] == ['c']
    source_rejection = next(r for r in rejected if r['kind'] == 'source_assessment')
    assert source_rejection['source_assessment_role'] == 'background'
    evidence = {'formation': {'rejections': rejected}, 'supplementary_calls': []}
    assert pending_rejections(evidence, primary)[0]['requires_review']
    assert primary['objects'][0]['context_evidence'] == []


def test_producer_cannot_supply_approval_or_omit_unknown_failures():
    from src.semantic_passage_v1 import SemanticPassageError
    with pytest.raises(SemanticPassageError, match='semantic_proposal_invalid'):
        prepare({'objects': [], 'relations': [], 'approved': True}, blocks=[], evidence_blocks=[], validator_input={})
    assert incomplete({'semantic_replay': {'provider_evidence': {
        'formation_incomplete': True, 'pending_rejections': [{'spans': [], 'reason_code': 'unknown_scope'}]}}}, objects=[])



def test_manual_source_reset_blocks_resume_and_reextract(tmp_path):
    state, sid, actor, reviewer, calls, mode, make, bind = system(tmp_path, containers=True)
    assert state.processing_status(sid)['resume_allowed']
    from src.source_context_review_v1 import confirm_source_context
    metadata = next(o for o in state.snapshot_objects(sid) if evidence_of(o).get('text') == 'Versie: 1')
    confirm_source_context(state, actor_id=reviewer, snapshot_id=sid, source_object_id=metadata['object_id'],
        role='reset', target_object_ids=[], reason='Bronbesluit opnieuw beoordelen', command_id='reset-metadata',
        expected_revision=state.objects_revision(sid))
    restarted = make(); bind(restarted)
    assert not restarted.processing_status(sid)['resume_allowed']
    with pytest.raises(ConsoleError, match='pre_review_retry_existing_work'):
        restarted.resume_formation(actor_id=actor, snapshot_id=sid, command_id='cannot-overwrite-reset',
            expected_revision=restarted.objects_revision(sid))
    with pytest.raises(ConsoleError, match='pre_review_retry_existing_work'):
        restarted.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    assert len(calls) == 2
    assert not next(r for r in restarted.snapshot_containers(sid)['source'] if r['record']['object_id'] == metadata['object_id'])['usage']['accounted']
