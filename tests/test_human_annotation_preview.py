"""Pre-seal source inspection never invokes candidate creation or review.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
"""
import hashlib
from copy import deepcopy

import pytest

from src.integrity_kernel import stable_hash
from src.vorming.human_annotation_preview_v1 import inspect_document
from tests.test_human_annotation_materialisation import inputs
from tests.test_t7_creator_cut import _fragment


def stored():
    fragments, decision = inputs()
    from src.vorming.semantic_passage_v1 import semantic_source_blocks
    blocks = {b['block_id']: b for b in semantic_source_blocks(fragments)}
    ranges = deepcopy(decision['annotation_ranges'])
    for anchor in ranges:
        anchor['quote_sha256'] = hashlib.sha256(blocks[anchor['block_id']]['text'][anchor['start']:anchor['end']].encode()).hexdigest()
    decision['field_evidence'].update(factual_claim_span={'span': None, 'missing_reason': 'not_applicable'},
                                      support_span={'core': True},
                                      supported_object=deepcopy(decision['field_evidence']['subject_span']))
    payload = {'status': 'ready', 'object_type': 'explanation', 'ranges': ranges,
               'pending_range': None, 'evidence_not_applicable': False,
               'selection_version': 'human-annotation-input-v2',
               'field_evidence': decision['field_evidence'], 'required_links': []}
    return fragments, {'annotation_id': decision['human_annotation']['annotation_id'], 'revision': 1,
                       'payload': payload, 'payload_hash': stable_hash(payload)}


def inspect(entry, fragments):
    entry['payload_hash'] = stable_hash(entry['payload'])
    return inspect_document([entry], fragments=fragments)


def test_inspection_has_no_candidate_creator_or_mutations(monkeypatch):
    from src.vorming import knowledge_materialisation_v1 as creator
    def forbidden(*args, **kwargs):
        raise AssertionError('preview invoked candidate creator')
    monkeypatch.setattr(creator, 'materialise_knowledge_candidates', forbidden)
    fragments, entry = stored()
    original = deepcopy((fragments, entry))
    result = inspect_document([entry], fragments=fragments)
    assert result['findings'] == result['unaccounted_ranges'] == []
    assert (fragments, entry) == original
    assert result['entries'] == [{'annotation_id': entry['annotation_id'], 'revision': 1, 'codes': []}]
    assert all(key not in str(result) for key in ('object_id', 'candidate_text', 'source_mapping'))


def test_unaccounted_repeated_text_has_distinct_exact_source_locations():
    fragments, entry = stored()
    fragments += [_fragment('extra1', 'Gelijke tekst.'), _fragment('extra2', 'Gelijke tekst.')]
    result = inspect(entry, fragments)
    gaps = result['unaccounted_ranges']
    assert len(gaps) == 2 and gaps[0]['block_id'] != gaps[1]['block_id']
    assert [g['quote'] for g in gaps] == ['Gelijke tekst.', 'Gelijke tekst.']
    assert result['findings'] == [{'annotation_id': None, 'code': 'annotation_source_unaccounted'}]


def test_draft_and_open_essential_relationship_return_to_original_annotation():
    fragments, entry = stored()
    payload = entry['payload']
    condition = payload['ranges'].pop(1)
    payload['status'] = 'draft'
    payload['required_links'] = [{key: condition[key] for key in
                                  ('relationship_id', 'role', 'evidence_function', 'required_for_meaning')}]
    payload['required_links'][0]['withdrawal_reason'] = None
    result = inspect(entry, fragments)
    assert {'annotation_id': entry['annotation_id'], 'code': 'annotation_required_relationship_missing'} in result['findings']
    assert result['unaccounted_ranges']  # A draft does not account for its core.


def test_missing_field_is_reported_without_inference_or_overwriting():
    fragments, entry = stored()
    entry['payload']['field_evidence']['predicate_span'] = {'span': None, 'missing_reason': 'uncertain'}
    result = inspect(entry, fragments)
    # #1060: reported as a signal for worker and reviewer; it no longer blocks sealing.
    assert result['entries'][0]['signals'] == ['predicate_missing']
    assert {'annotation_id': entry['annotation_id'], 'code': 'predicate_missing'} not in result['findings']
    assert entry['payload']['field_evidence']['predicate_span'] == {'span': None, 'missing_reason': 'uncertain'}


def test_withdrawn_input_keeps_source_unaccounted_and_rejects_tampered_manifest():
    fragments, entry = stored()
    entry['payload']['status'] = 'withdrawn'
    result = inspect(entry, fragments)
    assert result['entries'][0]['codes'] == [] and len(result['unaccounted_ranges']) == 3
    entry['payload']['status'] = 'ready'
    with pytest.raises(ValueError, match='annotation_integrity_failed'):
        inspect_document([entry], fragments=fragments)


@pytest.mark.parametrize('function', ['supported_by', 'explains'])
def test_both_evidence_functions_are_preserved_without_review_approval(function):
    fragments, entry = stored()
    entry['payload']['ranges'][-1]['evidence_function'] = function
    result = inspect(entry, fragments)
    assert result['findings'] == []
    assert entry['payload']['ranges'][-1]['evidence_function'] == function


def another_entry(entry):
    from uuid import uuid4
    from src.vorming.human_annotation_v1 import relationship_id
    duplicate = deepcopy(entry)
    duplicate['annotation_id'] = str(uuid4())
    for anchor in duplicate['payload']['ranges']:
        if anchor['role'] != 'core':
            anchor['relationship_id'] = relationship_id(duplicate['annotation_id'], anchor)
    duplicate['payload_hash'] = stable_hash(duplicate['payload'])
    return duplicate


def test_duplicate_cores_name_both_original_annotations_without_merging():
    fragments, entry = stored()
    duplicate = another_entry(entry)
    result = inspect_document([entry, duplicate], fragments=fragments)
    collisions = [finding for finding in result['findings'] if finding['code'] == 'annotation_core_duplicate']
    assert collisions == [
        {'annotation_id': entry['annotation_id'], 'code': 'annotation_core_duplicate',
         'related_annotation_ids': [duplicate['annotation_id']]},
        {'annotation_id': duplicate['annotation_id'], 'code': 'annotation_core_duplicate',
         'related_annotation_ids': [entry['annotation_id']]},
    ]
    duplicate['payload']['status'] = 'withdrawn'
    duplicate['payload_hash'] = stable_hash(duplicate['payload'])
    assert inspect_document([entry, duplicate], fragments=fragments)['findings'] == []


def test_equal_text_at_another_location_can_share_context_and_evidence():
    fragments, entry = stored()
    duplicate = another_entry(entry)
    fragments.append(_fragment('other-core', 'De huid is droog.'))
    from src.vorming.semantic_passage_v1 import semantic_source_blocks
    block = semantic_source_blocks(fragments)[-1]
    duplicate['payload']['ranges'][0]['block_id'] = block['block_id']
    for evidence in duplicate['payload']['field_evidence'].values():
        if evidence.get('span'):
            evidence['span']['block_id'] = block['block_id']
    duplicate['payload_hash'] = stable_hash(duplicate['payload'])
    assert inspect_document([entry, duplicate], fragments=fragments)['findings'] == []


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_preview_reads_persisted_versions_after_restart_without_writing_objects(
        tmp_path, production_console, monkeypatch, storage):
    from src.vorming import human_annotation_v1 as annotation
    from src.vorming.source_bound_fields_v3 import FIELDS
    from tests.test_human_annotation_postgres import source, anchor, command
    from tests.production_support import restart_production
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, _, sid, view, _ = source(production_console, tmp_path)
    core = anchor(view, 'Onderzoek')
    fields = {key: {'span': None, 'missing_reason': 'not_applicable'} for key in FIELDS}
    for field, text in [('subject_span', 'Onderzoek'), ('predicate_span', 'beschrijft'),
                        ('supported_object', 'de bevinding')]:
        start = core['quote'].index(text)
        fields[field] = {'span': {'block_id': core['block_id'], 'start': start, 'end': start + len(text)},
                         'missing_reason': None, 'quote': text}
    fields.update(type_evidence_spans={'core': True}, support_span={'core': True})
    request = command(view, ranges=[core], status='ready')
    request['selection'].update(object_type='explanation', evidence_not_applicable=True,
                                field_evidence=fields, required_links=[])
    annotation.save(console, actor_id=actor, **request)
    resumed = restart_production(console)
    with resumed.workflow_document_store._connect() as con:
        entries = con.execute('SELECT v.annotation_id,v.revision,v.payload,v.payload_hash '
            'FROM workflow.annotation_heads h JOIN workflow.annotation_versions v '
            'USING(snapshot_id,annotation_id,revision) WHERE h.snapshot_id=%s ORDER BY h.position',
            (sid,)).fetchall()
    result = inspect_document(entries, fragments=annotation._read_set(resumed, sid)[1])
    assert result['entries'][0]['codes'] == []
    assert result['findings'] == [{'annotation_id': None, 'code': 'annotation_source_unaccounted'}]
    assert all(gap['block_id'] != core['block_id'] for gap in result['unaccounted_ranges'])
    assert resumed.snapshot_objects(sid, include_blocked=True) == []
    assert resumed.object_review_bindings(sid) == []


def test_annotation_preflight_checks_draft_content_without_status_or_document_gate():
    from src.vorming.human_annotation_preview_v1 import inspect_annotation
    fragments, entry = stored()
    entry['payload']['status'] = 'draft'
    entry['payload_hash'] = stable_hash(entry['payload'])
    before = deepcopy(entry)
    assert inspect_annotation(entry, fragments=fragments, require_ready=False) == []
    assert entry == before
    assert inspect_document([entry], fragments=fragments)['entries'][0]['codes'] == ['annotation_not_ready']
    entry['payload']['ranges'] = [r for r in entry['payload']['ranges'] if r['role'] != 'evidence']
    entry['payload_hash'] = stable_hash(entry['payload'])
    assert 'annotation_evidence_required' in inspect_annotation(entry, fragments=fragments, require_ready=False)
