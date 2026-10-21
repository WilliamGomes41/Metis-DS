"""V2 context refs retain literal layout and uncertainty through transform/admission.

# release-control-evidence: scope/belofte opslag kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json
import pytest
from tests.test_source_bound_fields_v2 import fragment, proposal, TEXT
from src.pre_review_semantic_v1 import semantic_spec_from_fragments
from src.semantic_transform_generic_v1 import transform
from src.admission_gate_v1 import apply_admission_gate
from src.source_bound_fields_v2 import CONTEXT_KEY, validated_context

CONDITION = 'Wanneer de oudere thuis woont, geldt de volgende beperking.'


def prepare_context(role='condition', reason=None, mutate=None):
    core = fragment()
    preceding = {**fragment(), 'fragment_id':'f0', 'fragment_hash':'h0',
                 'raw_text':CONDITION, 'clean_text':CONDITION}
    source = [preceding, core]
    def provider(_url, _headers, payload, _timeout):
        blocks = json.loads(payload['input'][1]['content'])
        # Reuse the existing complete literal field proposal for the core.
        core_input = deepcopy(payload)
        core_input['input'][1]['content'] = json.dumps({'source_blocks':[blocks['source_blocks'][1]]})
        prop = proposal(core_input)
        context = blocks['evidence_blocks'][0]
        prop['objects'][0]['context_evidence'] = [{'role':role,
             'span':{'block_id':context['block_id'], 'start':0, 'end':len(context['text'])}, 'unresolved_reason':reason}]
        if mutate: mutate(prop)
        return {'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(prop)}]}]}
    spec = semantic_spec_from_fragments(document_id='doc', title='Context', family='test', class_='richtlijn',
        fragments=source, content_kind='html', api_key='test', model='test', post_json=provider, field_contract_v2=True)
    manifest = {'canonical_source':{'source_id':'source','title':'Context','source_type':'html','source_url':'test',
       'source_level':'national','canonicality':'canonical','integrity_status':'verified','source_checksum':'a'*64,'version':'1'}}
    rows = transform(spec, manifest, source)
    rows = apply_admission_gate(rows, klasse='richtlijn', fragments=source, document_version='1', source_hash='a'*64)
    obj = next(r for r in rows if r.get('content',{}).get('clean_text') == TEXT)
    return spec, rows, obj, source, manifest


@pytest.mark.parametrize('role', ['condition', 'exception', 'scope', 'negation', 'list_introduction', 'row_header', 'column_header'])
def test_context_is_durable_source_bound_and_visible_without_changing_core(role):
    _, _, obj, source, _ = prepare_context(role)
    assert obj['content']['clean_text'] == TEXT
    assert obj['metadata']['admission']['gate_result'] == 'allowed'
    context = validated_context(obj, source, 'a'*64)[0]
    assert context['text'] == CONDITION and context['source_refs'][0]['fragment_id'] == 'f0'
    assert any(r['realization'] == 'source_bound_context' for r in obj['metadata']['admission']['context_realization']['realized'])
    from src.operations_console_app import _knowledge_review_html
    html = _knowledge_review_html(obj, [obj])
    assert CONDITION in html.split('data-essential-context',1)[1]
    assert '<details' not in html


def test_uncertainty_remains_even_with_valid_literal_ref():
    _, _, obj, _, _ = prepare_context(reason='layout_ambiguous')
    assert obj['metadata']['admission']['gate_result'] == 'blocked'
    assert any(r['reason'] == 'layout_ambiguous' for r in obj['metadata']['admission']['context_realization']['unresolved'])


@pytest.mark.parametrize('change', ['bounds', 'free_text', 'role', 'reason'])
def test_invalid_context_proposals_fail_before_persistence(change):
    def mutate(prop):
        entry = prop['objects'][0]['context_evidence'][0]
        if change=='bounds': entry['span']['end'] = 100000
        elif change=='free_text': entry['text'] = 'Invented'
        elif change=='role': entry['role'] = 'invented'
        else: entry['unresolved_reason'] = 'guess'
    with pytest.raises(ValueError, match='source_bound_context'):
        prepare_context(mutate=mutate)


@pytest.mark.parametrize('change', ['source', 'text', 'offset', 'target'])
def test_transform_and_admission_reject_forged_or_stale_context(change):
    spec, rows, obj, source, manifest = prepare_context()
    if change in {'text','offset'}:
        item = next(r for r in spec['objects'] if CONTEXT_KEY in r)
        if change=='text': item[CONTEXT_KEY][0]['text'] = 'forged'
        else: item[CONTEXT_KEY][0]['span']['end'] += 1
        with pytest.raises(ValueError, match='source_bound_context'):
            transform(spec, manifest, source)
    else:
        altered = deepcopy(rows)
        target = next(r for r in altered if r['object_id']==obj['object_id'])
        if change=='source': target['source']['version'] = '2'
        else: target['content']['clean_text'] += ' Andere betekenis.'
        gated = apply_admission_gate(altered, klasse='richtlijn', fragments=source, document_version='1', source_hash='a'*64)
        invalid = next(r for r in gated if r['object_id']==obj['object_id'])
        assert 'admission' not in invalid['metadata']
        from src.knowledge_path_v1 import content_reviewable
        assert not content_reviewable(invalid)


@pytest.mark.parametrize('limit', ['input','output','timeout'])
def test_processing_bounds_fail_explicitly_without_truncation(monkeypatch, limit):
    from src import pre_review_semantic_v1 as processing
    from src.operations_console_v1 import ConsoleError
    if limit=='input':
        monkeypatch.setattr(processing,'MAX_INPUT_BYTES',1)
    elif limit=='output':
        monkeypatch.setattr(processing,'MAX_RESPONSE_BYTES',1)
    else:
        monkeypatch.setattr(processing,'DEFAULT_TIMEOUT_SECONDS',-1)
    reason={'input':'input_limit_exceeded','output':'output_limit_exceeded','timeout':'processing_timeout'}[limit]
    with pytest.raises(ConsoleError,match=reason):
        prepare_context()


def test_new_v2_provider_contract_requires_explicit_context_array():
    from src.operations_console_v1 import ConsoleError
    def missing(prop):
        prop['objects'][0].pop('context_evidence')
    with pytest.raises(ConsoleError,match='source_bound_context_required'):
        prepare_context(mutate=missing)
