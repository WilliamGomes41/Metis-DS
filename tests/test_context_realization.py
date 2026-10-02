"""Identified context must be realized; flags never waive integrity.

# release-control-evidence: scope/belofte opslag kwaliteit slop releasebewijs toegang
"""
from copy import deepcopy
import pytest
from src.admission_gate_v1 import admit_candidate, apply_admission_gate
from src.source_context_review_v1 import context_realization, context_issues
from tests.test_v230_phase2_deep_context_scan import _complete_adviseert_candidate

EXCEPTION = 'Tenzij er hypercalciëmie bestaat.'
CONDITION = 'Wanneer de cliënt thuis woont.'


@pytest.mark.parametrize('before,after', [('', EXCEPTION), (CONDITION, '')])
def test_neighbor_constraint_stays_unresolved_without_real_inclusion(before, after):
    row = _complete_adviseert_candidate(context_before=before, context_after=after)
    row['expand_merge'] = {'performed': True, 'resolved': True, 'merged_text': row['candidate_text'] + after}
    row['context_bindings'] = [{'resolved': True, 'text': before or after}]
    result = admit_candidate(row)
    assert result['gate_result'] == 'blocked'
    assert 'context_necessary_unresolved' in result['reason_codes']
    assert result['context_realization']['unresolved'][0]['text'] == (before or after)
    assert admit_candidate(row) == result  # deterministic replay, no mutation


def test_actual_inline_source_inclusion_is_proof_and_preserves_negation():
    row = _complete_adviseert_candidate(context_before='', context_after=EXCEPTION)
    row['candidate_text'] = row['source_text_exact'] = row['candidate_text'] + ' ' + EXCEPTION
    result = admit_candidate(row)
    assert not result['context_realization']['unresolved']
    assert any(r['realization'] == 'inline' for r in result['context_realization']['realized'])
    row['candidate_text'] = row['candidate_text'].replace(EXCEPTION, '')
    result = admit_candidate(row)
    assert 'source_fidelity_failure' in result['reason_codes']
    assert 'context_necessary_unresolved' in result['reason_codes']


def test_existing_binding_is_verified_not_inferred_from_proposal(tmp_path):
    from tests.test_source_context_review_v1 import _system
    state, _, _, source, target, command = _system(tmp_path)
    state.confirm_source_context(**command)
    rows = state.snapshot_objects(command['snapshot_id'])
    target = next(r for r in rows if r['object_id'] == target['object_id'])
    source = next(r for r in rows if r['object_id'] == source['object_id'])
    # Requirement explicitly refers to the same literal source label.
    from unittest.mock import patch
    path, _ = state._verified_source_bytes(state._envelope(command['snapshot_id']))
    env = state._envelope(command['snapshot_id'])
    fragments = state._extract(env['content_kind'], path, document_id=env['document_id'], source_id=env['source_id'])
    candidate = {'candidate_id': target['object_id'], 'candidate_text': target['content']['clean_text'],
                 'source_hash': env['sha256'], 'document_version':env['version'], 'context_scan': {}}
    with patch('src.context_scan_v1.required_context', return_value=[{'role':'scope','origin':'proposal','text':source['content']['clean_text']}]):
        result = context_realization(candidate, obj=target, objects=rows, fragments=fragments)
        assert not result['unresolved']
        assert result['realized'][0]['realization'] == 'source_context_binding'
        stale = deepcopy(rows)
        next(r for r in stale if r['object_id'] == source['object_id'])['object_version'] = '9.0'
        assert context_realization(candidate, obj=target, objects=stale, fragments=fragments)['unresolved']
        changed = deepcopy(fragments)
        next(f for f in changed if f['fragment_id'] == source['provenance']['source_fragments'][0]['raw_object_id'])['fragment_hash'] = 'changed'
        assert context_realization(candidate, obj=target, objects=rows, fragments=changed)['unresolved']
        candidate['source_hash'] = 'changed'
        assert context_realization(candidate, obj=target, objects=rows, fragments=fragments)['unresolved']


def test_direct_reextract_cannot_destroy_review_or_context(tmp_path):
    from tests.test_source_context_review_v1 import _system
    from src.operations_console_v1 import ConsoleError
    from src.review_ledger import read_events
    state, researcher, _, _, _, command = _system(tmp_path)
    state.confirm_source_context(**command)
    before = deepcopy(state._load_objects(command['snapshot_id'], remember=False))
    events = read_events(state._ledger_path)
    with pytest.raises(ConsoleError, match='pre_review_retry_existing_work'):
        state.reextract_unpublished(actor_id=researcher['account_id'], snapshot_id=command['snapshot_id'])
    assert state._load_objects(command['snapshot_id'], remember=False) == before
    assert read_events(state._ledger_path) == events


def test_partial_audit_failure_rolls_back_object_bindings_and_all_new_events(tmp_path, monkeypatch):
    from tests.test_source_context_review_v1 import _system
    from src.review_ledger import read_events, append_event
    state, _, _, source, target, command = _system(tmp_path)
    sid = command['snapshot_id']
    rows = deepcopy(state._load_objects(sid, remember=False))
    events = read_events(state._ledger_path)
    bindings = deepcopy(state.object_review_bindings(sid))
    rows[0].setdefault('metadata', {})['attempted_write'] = True
    def write_then_fail():
        append_event(state._ledger_path, event_type='test_partial_audit', object_id=source['object_id'],
                     object_version=source['object_version'], actor='test', details={})
        raise OSError('second audit write fails')
    with pytest.raises(OSError):
        state._commit_prepared_store(objects=(sid, rows), bindings={**state._bindings, sid:[]},
                                    expected_revision=state.objects_revision(sid), snapshot_id=sid,
                                    ledger_fn=write_then_fail)
    assert state._load_objects(sid, remember=False) != rows
    assert read_events(state._ledger_path) == events
    assert state.object_review_bindings(sid) == bindings


def test_real_neighbor_bindings_resolve_only_after_both_source_contexts(tmp_path):
    from tests.test_source_context_review_v1 import _bind_semantic_fixture
    from src.operations_console_v1 import OperationsConsole, ConsoleError
    from src.admission_gate_v1 import admission_of
    from src.review_ledger import read_events
    state = OperationsConsole(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime')
    researcher = state.create_account(username='researcher',password='test-only-secret',roles=('researcher',))
    reviewer = state.create_account(username='reviewer',password='test-only-secret',roles=('reviewer',))
    _bind_semantic_fixture(state)
    core = 'Een observatie is een systematische waarneming van gedrag.'
    data = ('<html><body><h1>Waarneming</h1><p>'+CONDITION+'</p><p>'+core+'</p><p>'+EXCEPTION+'</p></body></html>').encode()
    sid = state.ingest(actor_id=researcher['account_id'],filename='context.html',content_type='text/html',data=data,
        ingest_kind='new',title='Context',version='1',date='2026-10-02',live_url='',class_='richtlijn',family='test',
        named_reviewers=[reviewer['account_id']])['snapshot_id']
    def target(): return next(o for o in state.snapshot_objects(sid) if o['content']['clean_text']==core)
    before = deepcopy(state._load_objects(sid, remember=False))
    assert admission_of(target())['gate_result']=='blocked'
    with pytest.raises(ConsoleError, match='blocked_candidate_not_reviewable'):
        state.review_object(actor_id=reviewer['account_id'],snapshot_id=sid,object_id=target()['object_id'],
                            decision='approve',confirmed_object_type='definition')
    commands=[]
    for index, text in enumerate([CONDITION,EXCEPTION]):
        source=next(o for o in state.snapshot_objects(sid) if o['content']['clean_text']==text)
        cmd=dict(actor_id=reviewer['account_id'],snapshot_id=sid,source_object_id=source['object_id'],role='context',
                 target_object_ids=[target()['object_id']],reason='Letterlijke noodzakelijke broncontext.',
                 command_id=f'context-{index}',expected_revision=state.objects_revision(sid))
        commands.append(cmd); state.confirm_source_context(**cmd)
        assert admission_of(target())['gate_result']==('blocked' if index==0 else 'allowed')
    events=read_events(state._ledger_path)
    assert state.confirm_source_context(**commands[-1])['idempotent']
    assert read_events(state._ledger_path)==events
    with pytest.raises(ConsoleError,match='snapshot_object_write_conflict'):
        state.confirm_source_context(**{**commands[0],'command_id':'stale'})
    assert all(row in state._load_objects(sid,remember=False) for row in before)
    state.review_object(actor_id=reviewer['account_id'],snapshot_id=sid,object_id=target()['object_id'],
                        decision='approve',confirmed_object_type='definition')
    binding=next(b for b in state.object_review_bindings(sid) if b['valid'] and b['object_id']==target()['object_id'])
    reviewed_version=target()['object_version']
    assert binding['object_version']==reviewed_version
    state.confirm_source_context(**{**commands[-1],'command_id':'explicit-correction','expected_revision':state.objects_revision(sid)})
    assert any(row['object_version']==reviewed_version for row in state._load_objects(sid,remember=False)
               if row['object_id']==target()['object_id'])
    assert not any(b['valid'] for b in state.object_review_bindings(sid) if b['object_id']==target()['object_id'])
    assert all(event in read_events(state._ledger_path) for event in events)
