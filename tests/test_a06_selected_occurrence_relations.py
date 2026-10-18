"""A06: real V3 ingest must preserve exact selected occurrence endpoints.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
# release-control-evidence: opslag durable recovery concurrent stale interrupt retry version-compat
"""
from copy import deepcopy
import hashlib
import json
import subprocess
import sys

import pytest

from src.knowledge_path_v1 import content_reviewable, source_lineage_resolves
from src.operations_console_v1 import OperationsConsole, ConsoleError
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.source_bound_fields_v3 import MODE
from tests.test_recommendation_context_v3 import response_for
from tests.complete_workflow_support import complete_postgres as workflow_postgres  # noqa: F401

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
        # The old selector keeps the first equal-text row and removes this endpoint.
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


def durable_story(root, monkeypatch, make=None):
    state, sid, actor, reviewer, calls, _, control, env, make, bind = system(root, make)
    rows, candidates = assert_bundle(state, sid)
    repeated = [o for o in candidates if o['content']['clean_text'] == TEXT]
    assert len(repeated) == 2
    assert {o['metadata']['source_bound_fields']['values']['action_object_or_goal'] for o in repeated} == {'voorkeuren', 'de voorkeuren'}
    assert {o['metadata']['source_bound_context']['entries'][0]['text'] for o in repeated} == {'Bij volwassenen:', 'Bij kinderen:'}
    for o in repeated:
        fields = o['metadata']['source_bound_fields']
        assert fields['evidence']['recommended_action']['span']['block_id'] == o['metadata']['semantic_passage']['spans'][0]['block_id']
        context = o['metadata']['source_bound_context']
        assert context['target_object_id'] == o['object_id']
        assert context['entries'][0]['span'] == fields['evidence']['scope_span']['span']
        assert fields['values']['action_object_or_goal'] == (
            'voorkeuren' if context['entries'][0]['text'] == 'Bij volwassenen:' else 'de voorkeuren')
    assert set(r['raw_object_id'] for r in repeated[0]['provenance']['source_fragments']).isdisjoint(
        r['raw_object_id'] for r in repeated[1]['provenance']['source_fragments'])
    def projection(rows):
        return {o['object_id']: {k: deepcopy(o.get(k)) for k in
            ('content', 'metadata', 'source', 'provenance', 'proposed_knowledge_relations')}
            for o in rows if content_reviewable(o)}
    restarted = make(); bind(restarted)
    call_count = len(calls)
    restarted.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    assert len(calls) == call_count
    current, _ = assert_bundle(restarted, sid)
    # Provenance may include execution diagnostics; source occurrence data may not change.
    for oid, obj in projection(rows).items():
        actual = projection(current)[oid]
        for key in ('content', 'source', 'proposed_knowledge_relations'):
            assert actual[key] == obj[key]
        for key in ('semantic_passage', 'source_bound_fields', 'source_bound_context', 'knowledge_relation_evidence'):
            assert actual['metadata'].get(key) == obj['metadata'].get(key)
        assert actual['provenance']['source_fragments'] == obj['provenance']['source_fragments']
    command = restarted._envelope(sid)['processing_attempts'][-1]['command_id']
    restarted.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id=command)
    assert restarted.snapshot_objects(sid, include_blocked=True) == current
    assert len(calls) == call_count
    control['fail'] = True; env['METIS_LLM_MODEL'] = 'changed-model'
    with pytest.raises(ConsoleError, match='pre_review_llm_response_not_completed'):
        restarted.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    assert make().snapshot_objects(sid, include_blocked=True) == current
    control['fail'] = False
    store = getattr(restarted, 'workflow_document_store', None)
    if store is not None:
        write = store.write_bundle
        def fail_commit(**kwargs):
            result = write(**kwargs)
            if kwargs.get('objects') is not None:
                from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
                raise WorkflowDocumentStoreError('injected_a06_commit_failure')
            return result
        monkeypatch.setattr(store, 'write_bundle', fail_commit)
        expected = 'injected_a06_commit_failure'
    else:
        saved = []
        write_objects = restarted._save_objects_pinned
        write_envelopes = restarted._save_envelopes
        def save_objects(*args, **kwargs):
            write_objects(*args, **kwargs); saved.append(True)
        def fail_envelope():
            if saved:
                raise RuntimeError('injected_a06_commit_failure')
            return write_envelopes()
        monkeypatch.setattr(restarted, '_save_objects_pinned', save_objects)
        monkeypatch.setattr(restarted, '_save_envelopes', fail_envelope)
        expected = 'injected_a06_commit_failure'
    with pytest.raises((RuntimeError, ConsoleError), match=expected) as rejected:
        restarted.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    if store is not None:
        assert isinstance(rejected.value, ConsoleError)
        assert rejected.value.code == 'workflow_document_write_failed'
        assert str(rejected.value.__cause__) == 'injected_a06_commit_failure'
    restored = make()
    assert restored.snapshot_objects(sid, include_blocked=True) == current
    # An approval on one occurrence still grants no approval on the other.
    restored.review_object(actor_id=reviewer, snapshot_id=sid, object_id=repeated[0]['object_id'],
        decision='approve', confirmed_object_type='recommendation', recommendation_direction='for',
        recommendation_strength_level='not_stated')
    bindings = restored.object_review_bindings(sid)
    assert any(b['valid'] and b['object_id'] == repeated[0]['object_id'] for b in bindings)
    assert not any(b['valid'] and b['object_id'] == repeated[1]['object_id'] for b in bindings)
    final = make()
    assert final.snapshot_objects(sid, include_blocked=True) == restored.snapshot_objects(sid, include_blocked=True)
    assert final.object_review_bindings(sid) == bindings
    process = subprocess.run([sys.executable, '-c', """
import json, os, sys
from pathlib import Path
from src.operations_console_v1 import OperationsConsole
root = Path(sys.argv[1])
if sys.argv[3] == 'postgres':
    from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
    from tests.test_review_batch_atomic_postgres import _console
    console = _console(root, PostgresCanonicalConfig(dsn=os.environ['METIS_TEST_POSTGRES_DSN']))
else:
    console = OperationsConsole(root=root, source_store=root/'sources', runtime=root/'runtime')
print(json.dumps({'objects': console.snapshot_objects(sys.argv[2], include_blocked=True),
                  'bindings': console.object_review_bindings(sys.argv[2])}))
""", str(root), sid, 'postgres' if store is not None else 'file'],
        capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {'objects': final.snapshot_objects(sid, include_blocked=True), 'bindings': bindings}


def test_file_v3_evidence_isolation_replay_retry_failure_and_review(tmp_path, monkeypatch):
    durable_story(tmp_path, monkeypatch)


def test_postgres_v3_evidence_isolation_replay_retry_failure_and_review(workflow_postgres, tmp_path, monkeypatch):
    from tests.test_review_batch_atomic_postgres import _console
    durable_story(tmp_path, monkeypatch, lambda: _console(tmp_path, workflow_postgres))


@pytest.mark.parametrize('fault', ['unknown_block', 'bounds', 'not_selected', 'type', 'ambiguous'])
def test_exact_relation_validation_still_rejects_invalid_endpoints(fault):
    from tests.test_t7_duplicate_candidate_integrity import selection_fixture
    from src.semantic_passage_v1 import attach_relation_proposals, SemanticPassageError
    from src.source_occurrence_authority_v1 import prefer_authoritative_exact_occurrences
    fragments, candidates, coverage = selection_fixture((0, 1))
    units = prefer_authoritative_exact_occurrences(candidates + coverage)
    source = deepcopy(candidates[0]['semantic_passage']['spans'])
    target = deepcopy(candidates[1]['semantic_passage']['spans'])
    relation = {'source_spans': source, 'target_spans': target, 'evidence_spans': deepcopy(source), 'relation_type': 'supported_by'}
    if fault == 'unknown_block':
        target[0]['block_id'] = 'unknown'
    elif fault == 'bounds':
        target[0]['end'] += 100
    elif fault == 'not_selected':
        units = units[:1]
    elif fault == 'type':
        relation['relation_type'] = 'invented'
    else:
        units.append(deepcopy(units[0]))
    before = deepcopy(units)
    with pytest.raises(SemanticPassageError):
        attach_relation_proposals(units, raw_relations=[relation], evidence_fragments=fragments, object_version='1.0')
    assert units == before


def test_older_occurrence_replay_requires_fresh_inference(tmp_path):
    from src.semantic_replay_v1 import stable_json_hash
    from src.source_occurrence_authority_v1 import SOURCE_OCCURRENCE_AUTHORITY_VERSION
    state, sid, actor, _, calls, _, _, _, make, bind = system(tmp_path)
    envelope = deepcopy(state._envelope(sid))
    identity = envelope['semantic_replay']['identity']
    identity['components']['semantic_contract_version'] = identity['components']['semantic_contract_version'].removesuffix('/' + SOURCE_OCCURRENCE_AUTHORITY_VERSION)
    identity['hash'] = stable_json_hash(identity['components'])
    state._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    before = state.snapshot_objects(sid, include_blocked=True)
    restored = make(); bind(restored)
    assert restored.snapshot_objects(sid, include_blocked=True) == before
    count = len(calls)
    restored.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    assert len(calls) > count
    assert restored._envelope(sid)['semantic_replay']['identity']['components']['semantic_contract_version'].endswith('/' + SOURCE_OCCURRENCE_AUTHORITY_VERSION)
    assert_bundle(restored, sid)


def test_older_occurrence_checkpoint_cannot_resume_silently(tmp_path):
    from tests.test_recoverable_formation_v1 import system as partial_system
    from src.semantic_replay_v1 import stable_json_hash
    from src.source_occurrence_authority_v1 import SOURCE_OCCURRENCE_AUTHORITY_VERSION
    state, sid, actor, _, calls, _, make, bind = partial_system(tmp_path)
    envelope = deepcopy(state._envelope(sid))
    identity = envelope['semantic_replay']['identity']
    identity['components']['semantic_contract_version'] = identity['components']['semantic_contract_version'].removesuffix('/' + SOURCE_OCCURRENCE_AUTHORITY_VERSION)
    identity['hash'] = stable_json_hash(identity['components'])
    state._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    before = state.snapshot_objects(sid, include_blocked=True)
    restored = make(); bind(restored)
    count = len(calls)
    with pytest.raises(ConsoleError, match='processing_resume_configuration_incompatible'):
        restored.resume_formation(actor_id=actor, snapshot_id=sid, command_id='old-rule', expected_revision=restored.objects_revision(sid))
    assert len(calls) == count
    assert make().snapshot_objects(sid, include_blocked=True) == before


def stale_story(root, monkeypatch, make=None, *, mutation):
    state, sid, actor, _, _, _, control, env, make, _ = system(root, make)
    before, _ = assert_bundle(state, sid)
    second = make()
    publisher = second.create_account(username='publisher', password='strong-test-password', roles=('publisher',))
    changed = []
    def concurrent_edit(proposal):
        if changed:
            return
        if mutation == 'permission':
            second.assign_roles(actor_id=publisher['account_id'], account_id=actor, roles=('publisher',))
        else:
            winner = deepcopy(second.snapshot_objects(sid, include_blocked=True))
            winner[0]['content']['clean_text'] = 'Concurrent title correction'
            second._commit_prepared_store(objects=(sid, winner), expected_revision=second.objects_revision(sid), snapshot_id=sid)
            changed.extend(winner)
        changed.append(True)
    control['mutate'] = concurrent_edit
    env['METIS_LLM_MODEL'] = 'fresh-model'
    with pytest.raises(ConsoleError):
        state.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    restored = make()
    assert restored.snapshot_objects(sid, include_blocked=True) == (before if mutation == 'permission' else changed[:-1])
    assert not any(a['state'] == 'succeeded' for a in restored._envelope(sid)['processing_attempts'][1:])


@pytest.mark.parametrize('mutation', ['permission', 'revision'])
def test_file_stale_activation_cannot_replace_selected_endpoints(tmp_path, monkeypatch, mutation):
    stale_story(tmp_path, monkeypatch, mutation=mutation)


@pytest.mark.parametrize('mutation', ['permission', 'revision'])
def test_postgres_stale_activation_cannot_replace_selected_endpoints(workflow_postgres, tmp_path, monkeypatch, mutation):
    from tests.test_review_batch_atomic_postgres import _console
    stale_story(tmp_path, monkeypatch, lambda: _console(tmp_path, workflow_postgres), mutation=mutation)


def test_same_block_distinct_offsets_remain_distinct_and_same_span_stays_ambiguous():
    from tests.test_t7_creator_cut import _fragment
    from src.semantic_passage_v1 import semantic_source_blocks, semantic_units_from_proposal, attach_relation_proposals, SemanticPassageError
    from src.knowledge_materialisation_v1 import materialise_knowledge_candidates
    from src.source_occurrence_authority_v1 import prefer_authoritative_exact_occurrences
    text = 'Oedeem is een ophoping van vocht.'
    fragments = [_fragment('one', text + ' ' + text)]
    block, = semantic_source_blocks(fragments)
    spans = [[{'block_id': block['block_id'], 'start': start, 'end': start + len(text)}]
             for start in (0, len(text) + 1)]
    proposal = {'objects': [{'spans': span, 'proposed_object_type': 'definition'} for span in spans],
                'relations': [], 'abstain_reason': None}
    decisions = semantic_units_from_proposal(fragments, document_id='doc', proposal=proposal)
    units = prefer_authoritative_exact_occurrences(materialise_knowledge_candidates(decisions, document_id='doc', fragments=fragments))
    assert len(units) == 2 and units[0]['object_id'] != units[1]['object_id']
    assert [o['semantic_passage']['spans'] for o in units] == spans
    units.append(deepcopy(units[0]))
    with pytest.raises(SemanticPassageError, match='relation_target_ambiguous'):
        attach_relation_proposals(units, raw_relations=[], evidence_fragments=fragments, object_version='1.0')
