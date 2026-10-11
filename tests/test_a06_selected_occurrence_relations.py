"""A06: real V3 ingest must preserve exact selected occurrence endpoints.

# release-control-evidence: scope/belofte toegang beschikbaarheid kwaliteit slop releasebewijs
# release-control-evidence: opslag durable recovery concurrent stale interrupt retry version-compat
"""
from copy import deepcopy
import hashlib
import json

import pytest

from src.knowledge_path_v1 import content_reviewable, source_lineage_resolves
from src.operations_console_v1 import OperationsConsole, ConsoleError
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.source_bound_fields_v3 import MODE
from tests.test_recommendation_context_v3 import response_for
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401

TEXT = 'Bespreek de voorkeuren'
OTHER = 'Controleer de ondersteuning'


def system(root, make=None, *, reverse=False, swap_sections=False, direction='both', distinct=True):
    make = make or (lambda: OperationsConsole(root=root, source_store=root/'sources', runtime=root/'runtime'))
    state = make()
    author = state.create_account(username='author', password='strong-test-password', roles=('researcher',))
    reviewer = state.create_account(username='reviewer', password='strong-test-password', roles=('reviewer',))
    calls, proposals, control = [], [], {}
    env = {'METIS_PASSAGE_FORMATION_MODE': MODE, 'METIS_LLM_API_KEY': 'test', 'METIS_LLM_MODEL': 'test-model'}
    def provider(_url, _headers, payload, _timeout):
        calls.append(payload)
        if control.get('fail'):
            return {'status': 'incomplete', 'output': []}
        data = json.loads(payload['input'][1]['content'])
        objects = []
        for block in data['source_blocks']:
            if block['text'] not in {TEXT, OTHER, 'Bespreek alle voorkeuren'}:
                continue
            local = deepcopy(payload)
            local_data = {**data, 'source_blocks': [block], 'evidence_blocks': [*data['source_blocks'], *data['evidence_blocks']]}
            local['input'][1]['content'] = json.dumps(local_data)
            heading = 'Bij volwassenen:' if not objects else 'Bij kinderen:'
            obj = response_for(local, block['text'], heading=heading)['objects'][0]
            if heading == 'Bij kinderen:' and block['text'] == TEXT:
                obj['field_evidence']['action_object_or_goal']['span']['literal'] = 'de voorkeuren'
            objects.append(obj)
        if len(objects) != 3:
            return {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps({'objects': [], 'relations': [], 'abstain_reason': 'uncertain'})}]}]}
        repeated = [o for o in objects if o['spans'][0]['literal'] != OTHER]
        other = next(o for o in objects if o['spans'][0]['literal'] == OTHER)
        # The first duplicate has lower section authority unless explicitly swapped.
        endpoint = repeated[1]
        relations = []
        for source, target in ([(endpoint, other)] if direction == 'outgoing' else
                               [(other, endpoint)] if direction == 'incoming' else
                               [(endpoint, other), (other, endpoint)]):
            relations.append({'source_spans': deepcopy(source['spans']),
                'target_spans': deepcopy(target['spans']), 'relation_type': 'supported_by',
                'evidence_spans': deepcopy(source['spans'])})
        proposal = {'objects': list(reversed(objects)) if reverse else objects,
                    'relations': relations, 'abstain_reason': None}
        if control.get('mutate'):
            control['mutate'](proposal)
        proposals.append(deepcopy(proposal))
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(proposal)}]}]}
    def bind(console):
        bind_pre_review_semantic_processing(console, environ=env, post_json=provider)
    bind(state)
    sections = ['2 Aanbevelingen', 'Samenvatting'] if swap_sections else ['Samenvatting', '2 Aanbevelingen']
    first = TEXT if distinct else 'Bespreek alle voorkeuren'
    html = (f'<html><body><h1>Richtlijn</h1><h2>{sections[0]}</h2><p>Bij volwassenen:</p><p>{first}</p>'
            f'<p>Bij kinderen:</p><p>{TEXT}</p>'
            f'<p>{OTHER}</p></body></html>').encode()
    receipt = state.ingest(actor_id=author['account_id'], filename='duplicates.html', content_type='text/html',
        data=html, ingest_kind='new', title='Duplicates', version='1.0', date='2026-10-11', live_url='',
        class_='richtlijn', family='test', named_reviewers=[reviewer['account_id']])
    return state, receipt['snapshot_id'], author['account_id'], reviewer['account_id'], calls, proposals, control, env, make, bind


def assert_bundle(state, sid):
    rows = state.snapshot_objects(sid, include_blocked=True)
    candidates = [o for o in rows if content_reviewable(o)]
    envelope = state._envelope(sid)
    assert len(candidates) == 3, [(a.get('state'), a.get('error_code'), a.get('validation_code'))
        for a in envelope.get('processing_attempts', [])]
    path, _ = state._verified_source_bytes(envelope)
    fragments = state._read_source_fragments(envelope, path)
    by_block = {}
    for candidate in candidates:
        metadata = candidate['metadata']
        span, = metadata['semantic_passage']['spans']
        digest = hashlib.sha256(f'{span["block_id"]}:{span["start"]}:{span["end"]}'.encode()).hexdigest()[:16]
        assert candidate['object_id'] == envelope['document_id'] + '-sem-' + digest
        assert source_lineage_resolves(candidate, fragments=fragments)
        assert metadata['admission']['gate_result'] == 'allowed'
        by_block[span['block_id']] = candidate
        for proof in metadata.get('knowledge_relation_evidence', {}).get('relations', []):
            target = next(o for o in candidates if o['object_id'] == proof['target_object_id'])
            assert [{k: s[k] for k in ('block_id', 'start', 'end')} for s in proof['source_spans']] == metadata['semantic_passage']['spans']
            assert [{k: s[k] for k in ('block_id', 'start', 'end')} for s in proof['target_spans']] == target['metadata']['semantic_passage']['spans']
    assert len(by_block) == 3
    return rows, candidates


@pytest.mark.parametrize('direction', ['outgoing', 'incoming', 'both'])
@pytest.mark.parametrize('reverse,swap_sections', [(False, False), (True, False), (False, True), (True, True)])
def test_v3_ingest_selected_duplicate_relations_survive_restart(tmp_path, direction, reverse, swap_sections):
    state, sid, _, _, _, _, _, _, make, _ = system(tmp_path, direction=direction, reverse=reverse, swap_sections=swap_sections)
    rows, candidates = assert_bundle(state, sid)
    assert sum(len(o.get('proposed_knowledge_relations', [])) for o in candidates) == (2 if direction == 'both' else 1)
    restored = make()
    assert restored.snapshot_objects(sid, include_blocked=True) == rows
    assert_bundle(restored, sid)


def test_native_postgres_v3_duplicate_endpoints_restart(workflow_postgres, tmp_path):
    from tests.test_review_batch_atomic_postgres import _console
    state, sid, _, _, _, _, _, _, make, _ = system(tmp_path, lambda: _console(tmp_path, workflow_postgres))
    rows, _ = assert_bundle(state, sid)
    assert make().snapshot_objects(sid, include_blocked=True) == rows


def test_control_changing_only_first_text_allows_same_v3_ingest(tmp_path):
    state, sid, *_ = system(tmp_path, distinct=False)
    assert_bundle(state, sid)
