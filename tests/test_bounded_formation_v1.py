"""Bounded task ownership, context references, budget failure and recovery.

# release-control-evidence: scope/belofte kwaliteit metrics slop releasebewijs
# release-control-evidence: opslag stale recovery beschikbaarheid toegang version-compat
"""
import json
from copy import deepcopy

from src.bounded_formation_v1 import tasks_for, execute, formation_progress, pending_source_extent, MAX_CANDIDATE_CHARS
from src.bounded_model_call_v1 import ModelCallLimits
from src.semantic_passage_v1 import semantic_source_blocks
from tests.test_recommendation_context_v3 import source, response_for
from src.pre_review_semantic_v1 import _semantic_execution_before_review


def block(bid, text, path):
    return {'block_id': bid, 'text': text, 'section_path': path, 'heading': None, 'position': 0}


def test_tasks_partition_candidates_and_keep_referenced_table_content_as_context():
    a = block('a', 'Overweeg maatregelen uit Tabel 1.', ['Aanbevelingen'])
    b = block('b', 'Tabel 1. Preventieve maatregelen', ['Bijlagen', 'Tabel 1'])
    c = block('c', 'Houd de huid droog.', ['Bijlagen', 'Tabel 1'])
    tasks = tasks_for([a, b, c], [a, b, c])
    assert len(tasks) == 2
    assert [r['block_id'] for r in tasks[0]['source_blocks']] == ['a']
    assert {r['block_id'] for r in tasks[0]['evidence_blocks']} == {'b', 'c'}
    assert [s['block_id'] for task in tasks for s in task['target_spans']] == ['a', 'b', 'c']
    for task in tasks:
        assert not ({b['block_id'] for b in task['source_blocks']} & {b['block_id'] for b in task['evidence_blocks']})


def test_oversized_source_remains_explicit_instead_of_truncation():
    b = block('long', 'x' * (MAX_CANDIDATE_CHARS + 1), ['One'])
    task = tasks_for([b], [b])[0]
    assert task['error_code'] == 'source_task_context_limit_exceeded'
    assert task['source_blocks'][0]['text'] == b['text']
    assert task['target_spans'][0]['end'] == len(b['text'])


def test_budget_exhaustion_accounts_for_every_unstarted_task_and_cannot_publish():
    fragments = [dict(source(t)[0], fragment_id=str(i), fragment_hash=str(i), section_path=[str(i)])
                 for i,t in enumerate(['Gebruik geen zalf', 'Controleer dagelijks de huid'])]
    blocks = semantic_source_blocks(fragments)
    def fail(**kwargs):
        raise AssertionError('No provider call allowed with exhausted budget')
    proposal, evidence = execute(blocks=blocks, evidence_blocks=blocks,
        validator_input={'fragments': fragments, 'document_id': 'test', 'evidence_fragments': fragments,
                         'allowed_candidate_block_ids': [b['block_id'] for b in blocks], 'field_contract_v3': True},
        provider=fail, limits=ModelCallLimits(total=0))
    assert not proposal['objects'] and evidence['formation_incomplete']
    assert {s['block_id'] for r in evidence['pending_rejections'] for s in r['spans']} == {b['block_id'] for b in blocks}
    assert all(t['status'] == 'not_started' for t in evidence['tasks'])
    assert evidence['formation_state'] == 'pending'
    progress = evidence['formation_progress']
    assert progress['planned_task_count'] == 2
    assert progress['terminal_task_count'] == 0
    assert progress['pending_task_count'] == 2
    assert progress['failed_task_count'] == 0
    assert progress['partial_task_count'] == 0
    assert progress['not_started_task_count'] == 2
    assert progress['unknown_pending_count'] == 0
    assert progress['pending_source_range_count'] == 2
    assert progress['pending_source_char_count'] == sum(len(block['text']) for block in blocks)


def test_budget_exhaustion_bulk_records_remaining_tasks_with_single_checkpoint():
    fragments = [
        dict(source(f'Bronpassage {i} met voldoende klinische tekst voor een eigen taak.')[0],
             fragment_id=str(i), fragment_hash=str(i), section_path=[str(i)])
        for i in range(50)
    ]
    blocks = semantic_source_blocks(fragments)
    checkpoints = []

    def forbidden(**kwargs):
        raise AssertionError('provider must not run after the bounded budget is exhausted')

    proposal, evidence = execute(
        blocks=blocks,
        evidence_blocks=blocks,
        validator_input={
            'fragments': fragments,
            'document_id': 'test',
            'evidence_fragments': fragments,
            'allowed_candidate_block_ids': [b['block_id'] for b in blocks],
            'field_contract_v3': True,
        },
        provider=forbidden,
        limits=ModelCallLimits(total=0),
        checkpoint=lambda phase, values: checkpoints.append((phase, deepcopy(values))),
    )

    assert proposal['objects'] == []
    assert len(evidence['tasks']) == 50
    assert all(task['status'] == 'not_started' for task in evidence['tasks'])
    assert len(checkpoints) == 1
    assert checkpoints[0][0] == 'proposal_received'
    checkpoint_evidence = checkpoints[0][1]['provider_evidence']
    calls = [checkpoint_evidence, *checkpoint_evidence.get('supplementary_calls', [])]
    assert len(calls) == 50
    assert all(call.get('error_code') == 'source_task_budget_exhausted' for call in calls)
    assert evidence['formation_incomplete']
    assert evidence['formation_progress']['pending_task_count'] == 50


def test_progress_tracks_original_task_when_recovery_regroups_source_ranges():
    whole = {'block_id': 'b', 'start': 0, 'end': 100}
    left = {'block_id': 'b', 'start': 0, 'end': 50}
    right = {'block_id': 'b', 'start': 50, 'end': 100}
    evidence = {
        'tasks': [
            {'task_id': 'initial', 'phase': 'initial', 'target_spans': [whole], 'status': 'not_started'},
            {'task_id': 'recovery-left', 'phase': 'recovery', 'target_spans': [left], 'status': 'completed'},
        ],
        'pending_rejections': [{'kind': 'call', 'reason_code': 'source_task_budget_exhausted', 'spans': [right]}],
    }
    progress = formation_progress(evidence)
    assert progress['planned_task_count'] == 1
    assert progress['terminal_task_count'] == 0
    assert progress['pending_task_count'] == 1
    assert progress['partial_task_count'] == 1
    assert progress['pending_source_range_count'] == 1
    assert progress['pending_source_char_count'] == 50
    evidence['tasks'].append(
        {'task_id': 'recovery-right', 'phase': 'recovery', 'target_spans': [right], 'status': 'completed'}
    )
    evidence['pending_rejections'] = []
    progress = formation_progress(evidence)
    assert progress['planned_task_count'] == 1
    assert progress['terminal_task_count'] == 1
    assert progress['pending_task_count'] == 0
    assert progress['pending_source_range_count'] == 0
    assert progress['pending_source_char_count'] == 0


def test_pending_source_extent_detects_progress_inside_one_original_task():
    evidence = {'pending_rejections': [
        {'spans': [{'block_id': 'b', 'start': 0, 'end': 100}]},
    ]}
    assert pending_source_extent(evidence) == {
        'unknown_pending_count': 0,
        'pending_source_range_count': 1,
        'pending_source_char_count': 100,
    }
    evidence['pending_rejections'] = [
        {'spans': [{'block_id': 'b', 'start': 25, 'end': 100}]},
    ]
    assert pending_source_extent(evidence)['pending_source_char_count'] == 75


def test_context_only_block_cannot_become_candidate_and_valid_prior_selection_survives():
    first = 'Gebruik geen zalf'
    second = 'Controleer dagelijks de huid'
    fragments = [dict(source(t)[0], fragment_id=str(i), fragment_hash=str(i), section_path=['Same'])
                 for i,t in enumerate([first, second])]
    calls = []
    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload['input'][1]['content']); calls.append(data)
        if not data.get('selection_targets'):
            proposal = response_for(payload, first)
        else:
            # Malicious/erroneous producer selects an already formed core from
            # context-only input, while also returning an independent valid core.
            fake = deepcopy(payload)
            fake['input'][1]['content'] = json.dumps({**data, 'source_blocks': data['source_blocks'] + data['evidence_blocks']})
            proposal = response_for(fake, first)
            proposal['objects'].extend(response_for(payload, second)['objects'])
        return {'output': [{'content': [{'type': 'output_text', 'text': json.dumps(proposal)}]}]}
    units, replay = _semantic_execution_before_review(fragments, document_id='test', api_key='fixture', model='fixture',
        field_contract_v3=True, post_json=provider, formation_context={'snapshot_id': 'snap', 'source_sha256': 'a'*64})
    selected = [u for u in units if u['semantic_passage']['selection_origin'] == 'proposal_selected']
    assert [u['text'] for u in selected] == [first, second]
    recovery = calls[-1]
    assert [b['text'] for b in recovery['source_blocks']] == [second]
    assert [b['text'] for b in recovery['evidence_blocks']] == [first]
    assert replay['provider_evidence']['supplementary_calls'][0]['formation']['rejections']
    assert replay['provider_evidence']['task_policy'] == 'bounded-formation-v1'


def test_reconstruction_cache_preserves_mutation_isolation_and_invalidates_changed_input(monkeypatch):
    from src import source_reconstruction_v1 as reconstruction
    original = reconstruction._with_status
    calls = []
    def observed(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(reconstruction, '_with_status', observed)
    fragments = source('Gebruik geen zalf')
    @reconstruction.with_reconstruction_cache
    def operation():
        first = reconstruction.reconstruct_source_fragments(fragments)
        pristine = deepcopy(first)
        first[0]['clean_text'] = 'mutated return value'
        assert reconstruction.reconstruct_source_fragments(fragments) == pristine
        assert len(calls) == 1
        changed = deepcopy(fragments)
        changed[0]['clean_text'] = changed[0]['raw_text'] = 'Controleer de huid'
        assert reconstruction.reconstruct_source_fragments(changed)[0]['clean_text'] == 'Controleer de huid'
        assert len(calls) == 2
    operation()
    reconstruction.reconstruct_source_fragments(fragments)
    assert len(calls) == 3  # no cache survives an operation/restart


def test_answered_task_clears_transport_failure_but_does_not_dispose_unknown_source():
    from src.recoverable_formation_v1 import pending_rejections
    span = {'block_id': 'b', 'start': 0, 'end': 40}
    evidence = {'task_policy': 'bounded-formation-v1', 'task_id': 't',
        'error_code': 'source_task_budget_exhausted', 'target_spans': [span],
        'supplementary_calls': [{'task_id': 't', 'target_spans': [span],
            'formation': {'status': 'validated', 'rejections': [], 'accepted_object_count': 0}}]}
    proposal = {'objects': [], 'source_assessments': []}
    assert pending_rejections(evidence, proposal) == []
    assert proposal == {'objects': [], 'source_assessments': []}  # no exclusion or invented knowledge
    evidence['supplementary_calls'][0]['formation']['rejections'] = [{'kind': 'object', 'reason_code': 'semantic_evidence_literal_not_found', 'spans': [span]}]
    assert len(pending_rejections(evidence, proposal)) == 2
