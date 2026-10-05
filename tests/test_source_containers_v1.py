"""Two containers, exact context usage and reversible machine source decisions.

# release-control-evidence: scope/belofte kwaliteit metrics slop releasebewijs
# release-control-evidence: opslag concurrent stale recovery toegang beschikbaarheid version-compat
"""
from copy import deepcopy
import json

import pytest

from src.passage_register_v1 import apply_passage_register
from src.publication_readiness_v1 import source_passage_closure, review_followup_queues
from src.source_accountability_v1 import evidence_of, KEY, record
from src.source_containers_v1 import partition, metadata_reason
from src.source_bound_fields_v3 import additional_context_codes
from tests.test_recommendation_context_v3 import prepare, source


def context_story():
    core = 'Gebruik geen zalf'
    context = 'Bij volwassenen. Bij kinderen geldt ander beleid.'
    fragments = source(core)
    fragments.append({**source(context)[0], 'fragment_id': 'context', 'fragment_hash': 'context-hash'})
    def mutate(proposal):
        from src.semantic_passage_v1 import semantic_source_blocks
        block = semantic_source_blocks(fragments)[1]
        proposal['objects'][0]['context_evidence'] = [{'role': 'scope', 'span': {
            'block_id': block['block_id'], 'literal': 'Bij volwassenen.', 'occurrence': 0}, 'unresolved_reason': None}]
    _, rows, _, _ = prepare(core, fragments=fragments, mutate=mutate)
    return apply_passage_register(rows)


def test_exact_context_is_separate_and_only_approved_current_target_closes_it():
    rows = context_story()
    groups = partition(rows)
    assert len(groups['knowledge']) == 1 and len(groups['source']) == 2
    linked = next(r for r in groups['source'] if r['usage']['kind'] == 'linked_context')
    unknown = next(r for r in groups['source'] if r['usage']['kind'] == 'unresolved')
    assert linked['record']['content']['clean_text'] == 'Bij volwassenen.'
    assert unknown['record']['content']['clean_text'] == 'Bij kinderen geldt ander beleid.'
    sid = linked['record']['object_id']
    assert not linked['usage']['accounted']
    assert sid in source_passage_closure(rows)['unresolved_source_passage_ids']
    followups = review_followup_queues(rows, review_path='richtlijn')
    assert sid not in {o['object_id'] for group in followups.values() for o in group}
    target = groups['knowledge'][0]
    target['governance']['validation_status'] = 'approved'
    assert partition(rows)['source'][0]['usage']['accounted']
    assert sid not in source_passage_closure(rows)['unresolved_source_passage_ids']
    target['governance']['validation_status'] = 'rejected'
    assert partition(rows)['source'][0]['usage']['kind'] == 'unresolved'
    target['governance']['validation_status'] = 'approved'
    target['content']['clean_text'] += ' veranderd'
    assert partition(rows)['source'][0]['usage']['kind'] == 'unresolved'


@pytest.mark.parametrize('text', ['Versie: 1', 'Datum: juli 2026', 'Inhoud......................3'])
def test_closed_metadata_rules(text):
    assert metadata_reason(text)


@pytest.mark.parametrize('text', ['Versie: 1; gebruik geen zalf', 'Gebruik versie 1 bij volwassenen',
    'Datum: juli 2026. Bij koorts: bel de arts', 'Richtlijn adviseert geen zalf',
    'Bij volwassenen: 1', 'Tabel 1. Preventieve maatregelen'])
def test_clinical_or_mixed_text_is_not_machine_metadata(text):
    assert metadata_reason(text) is None


def test_legacy_source_policy_is_not_reinterpreted_and_invalid_records_fail_closed():
    rows = context_story()
    source_row = partition(rows)['source'][0]['record']
    ev = evidence_of(source_row)
    source_row['metadata'][KEY] = record(text=ev['text'], spans=ev['spans'])
    assert partition(rows)['source'][0]['usage']['reason'] == 'legacy_source_policy'
    source_row['metadata'][KEY]['version'] = 'source-accountability-v2'
    assert not evidence_of(source_row)
    assert source_row['object_id'] in source_passage_closure(rows)['unresolved_source_passage_ids']


def test_scope_case_and_terminal_colon_do_not_require_duplicate_context():
    core = 'Pas minimaal 2 keer per dag de basismaatregelen toe bij smetten in de huidplooien.'
    row = {'section_path': ['Smetten in de huidplooien:'], 'recommendation_evidence_span': core}
    assert additional_context_codes(row, {'realized': []}) == []
    for scope in ['Smetten in de huidplooien bij kinderen:', 'Niet bij smetten:',
                  'Minimaal 3 keer per dag:', 'Huidplooi:']:
        assert additional_context_codes({**row, 'section_path': [scope]}, {'realized': []}) == ['recommendation_scope_context_missing']


def test_kernel_ui_export_and_manual_reset_survive_restart(tmp_path, make_console=None):
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.review_closure_v1 import ReviewClosureConsole
    from src.source_context_review_v1 import confirm_source_context
    from src.processing_evidence_export_v1 import processing_evidence_tables
    from src.operations_console_app import _render_review_index
    from tests.test_recommendation_context_v3 import response_for
    def make():
        return make_console() if make_console else ReviewClosureConsole(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime')
    state = make()
    author = state.create_account(username='author', password='strong-test-password', roles=('researcher',))
    reviewer = state.create_account(username='reviewer', password='strong-test-password', roles=('reviewer',))
    def provider(_url, _headers, payload, _timeout):
        return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(response_for(payload, 'Gebruik geen zalf'))}]}]}
    bind_pre_review_semantic_processing(state, environ={'METIS_PASSAGE_FORMATION_MODE': 'semantic-source-bound-v3',
        'METIS_LLM_API_KEY': 'fixture', 'METIS_LLM_MODEL': 'fixture'}, post_json=provider)
    result = state.ingest(actor_id=author['account_id'], filename='source.html',
        data=b'<html><body><h1>Aanbevelingen</h1><p>Versie: 1</p><p>Gebruik geen zalf</p></body></html>',
        content_type='text/html', ingest_kind='new', title='Test', version='1', date='2026-10-05', live_url='',
        class_='richtlijn', family='test', named_reviewers=[reviewer['account_id']])
    sid = result['snapshot_id']
    containers = state.snapshot_containers(sid)
    assert len(containers['knowledge']) == 1 and len(containers['source']) == 1
    info = containers['source'][0]
    assert info['usage']['accounted']
    source_id = info['record']['object_id']
    rows = state.snapshot_objects(sid)
    page = _render_review_index(sid, rows, 'richtlijn', task='inventory')
    assert 'data-source-group' in page and 'Documentinformatie' in page
    assert f'data-passage-id="{source_id}"' not in page
    assert f'data-source-record="{source_id}"' in page
    tables, _ = processing_evidence_tables(snapshot_id=sid, revision=state.objects_revision(sid), envelope=state._envelope(sid), objects=rows)
    assert tables['source_usage'][0]['accounted'] and tables['formation_tasks'][0]['status'] == 'completed'
    command = dict(actor_id=reviewer['account_id'], snapshot_id=sid, source_object_id=source_id,
        role='reset', target_object_ids=[], reason='Controleer dit bronbesluit opnieuw.', command_id='reopen', expected_revision=state.objects_revision(sid))
    confirm_source_context(state, **command)
    reopened = make()
    assert not reopened.snapshot_containers(sid)['source'][0]['usage']['accounted']
    assert source_id in source_passage_closure(reopened.snapshot_objects(sid))['unresolved_source_passage_ids']
    assert confirm_source_context(reopened, **command)['idempotent']


from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


def test_native_container_reset_restart(workflow_postgres, tmp_path):
    from tests.test_review_batch_atomic_postgres import _console
    test_kernel_ui_export_and_manual_reset_survive_restart(tmp_path, lambda: _console(tmp_path, workflow_postgres))


def test_published_context_projection_rejects_stale_and_unresolved_context():
    from tests.test_retrieval_projection_v2 import published_envelope
    from src.retrieval.retrieval_projection_v2 import build_projection
    from src.integrity_kernel import stamp_canonical_hashes
    rows = context_story()
    obj = partition(rows)['knowledge'][0]
    obj['confirmed_object_type'] = 'recommendation'
    obj['confirmed_recommendation_semantics'] = obj['proposed_recommendation_semantics']
    env = published_envelope(obj)
    stamp_canonical_hashes(env['knowledge_object'])
    records, errors = build_projection([env])
    assert records and not errors
    assert 'Bij volwassenen.' in records[0]['retrieval_text']
    for change in ('literal', 'reason', 'bounds'):
        altered = deepcopy(env)
        target = altered['knowledge_object']
        if change == 'literal':
            target['content']['clean_text'] += ' veranderd'
        elif change == 'reason':
            target['metadata']['source_bound_context']['entries'][0]['unresolved_reason'] = 'context_uncertain'
        else:
            target['metadata']['source_bound_context']['entries'][0]['span']['end'] += 1
        result, blocked = build_projection([altered])
        assert not result and 'source_bound_context_invalid' in blocked[0]['errors']
