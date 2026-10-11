"""A07: public selection and real provider/transform/admission, synthetic source.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import pytest
from src.semantic_passage_v1 import semantic_source_blocks, semantic_units_from_proposal, SemanticPassageError
from tests.test_recommendation_context_v3 import prepare, source
from tests.test_d3_2_recommendation_semantics_proposal import _fragment
from src.source_bound_fields_v3 import FIELDS

CORE = 'Gebruik geen zalf.'


def case(a_label='', *, own='', ancestor=False, same_block=False, explicit=None, heading=None, gap=''):
    path = ['Aanbevelingen'] + (['B'] if ancestor else [])
    a = _fragment('a', 'Vermijd behandeling A.' + (' ' + a_label if a_label else ''), section_path=['Aanbevelingen'])
    b = _fragment('b', CORE + (' ' + own if own else ''), section_path=path)
    fragments = [a, b]
    if same_block:
        fragments = [_fragment('ab', a['clean_text'] + ' ' + b['clean_text'], section_path=path)]
    if gap:
        fragments[-1]['clean_text'] += ' ' + gap + ' Sterk – tegen'
        fragments[-1]['raw_text'] = fragments[-1]['clean_text']
    if heading:
        fragments.insert(0, _fragment('h', heading, object_type='heading', section_path=['Aanbevelingen']))
    candidates = [f for f in fragments if f.get('object_type') != 'heading']
    blocks = semantic_source_blocks(candidates)
    evidence = semantic_source_blocks(fragments)
    block = next(x for x in blocks if CORE in x['text'])
    def ref(text, owner=block):
        start = owner['text'].index(text)
        return {'block_id': owner['block_id'], 'start': start, 'end': start + len(text)}
    fields = {f: {'span': None, 'missing_reason': 'not_applicable'} for f in FIELDS}
    for f, text in {'predicate_span': 'Gebruik', 'type_evidence_spans': CORE,
                    'recommended_action': 'Gebruik geen', 'action_object_or_goal': 'zalf',
                    'recommendation_evidence_span': CORE}.items():
        fields[f] = {'span': ref(text), 'missing_reason': None}
    strength_ref = None
    if explicit:
        label, owner_id = explicit
        owner = next(x for x in evidence if owner_id in x['source_fragment_ids'])
        strength_ref = ref(label, owner)
    p = {'objects': [{'spans': [ref(b['clean_text'] if not gap else CORE)], 'proposed_object_type': 'recommendation',
         'recommendation_semantics': {'direction': 'against', 'direction_evidence': ref(CORE),
             'strength_status': 'explicit' if explicit else 'not_stated',
             'strength': ('weak' if 'Zwak' in explicit[0] else 'strong') if explicit else None,
             'strength_evidence': strength_ref}, 'field_evidence': fields, 'context_evidence': []}],
         'relations': [], 'abstain_reason': None}
    return fragments, candidates, p


def validate(fragments, candidates, proposal, version='v3'):
    p = deepcopy(proposal)
    if version == 'v1':
        p['objects'][0].pop('field_evidence'); p['objects'][0].pop('context_evidence')
    elif version == 'v2':
        f = p['objects'][0]['field_evidence']
        for name in ('actor_span', 'target_group_span', 'scope_span'): f.pop(name)
        f['actor_of_scope'] = {'span': None, 'missing_reason': 'not_stated'}
    before = deepcopy((fragments, p))
    try:
        decisions = semantic_units_from_proposal(candidates, document_id='a07', proposal=p,
            evidence_fragments=fragments, field_contract_v3=version == 'v3', field_contract_v2=version == 'v2')
        return decisions
    finally:
        assert (fragments, p) == before


@pytest.mark.parametrize('version', ['v1', 'v2', 'v3'])
@pytest.mark.parametrize('same_block,ancestor', [(True, False), (False, False), (False, True)])
def test_a_label_cannot_change_b_absence(version, same_block, ancestor):
    baseline = validate(*case(same_block=same_block, ancestor=ancestor), version)
    changed = validate(*case('Sterk – tegen', same_block=same_block, ancestor=ancestor), version)
    assert baseline[0]['proposed_recommendation_semantics'] == changed[0]['proposed_recommendation_semantics']


@pytest.mark.parametrize('same_block,ancestor', [(True, False), (False, False), (False, True)])
def test_b_cannot_borrow_a_label(same_block, ancestor):
    owner = 'ab' if same_block else 'a'
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_not_applicable'):
        validate(*case('Sterk – tegen', same_block=same_block, ancestor=ancestor, explicit=('Sterk – tegen', owner)))


@pytest.mark.parametrize('own', ['Sterk – tegen', 'Zwak – tegen', 'Sterk – tegen Zwak – tegen'])
@pytest.mark.parametrize('a_label', ['', 'Sterk – tegen'])
def test_own_label_and_conflicts_never_become_absence(own, a_label):
    with pytest.raises(SemanticPassageError, match='recommendation_strength_not_stated_conflict'):
        validate(*case(a_label, own=own))


def test_explicit_strength_cannot_hide_conflicting_own_labels():
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_conflict'):
        validate(*case(own='Sterk – tegen Zwak – tegen', explicit=('Sterk – tegen', 'b')))


@pytest.mark.parametrize('ancestor', [False, True])
def test_genuine_shared_heading_is_external_evidence(ancestor):
    rows = validate(*case(heading='Sterke aanbeveling', ancestor=ancestor, explicit=('Sterke aanbeveling', 'h')))
    assert rows[0]['proposed_recommendation_semantics']['strength'] == 'strong'
    with pytest.raises(SemanticPassageError, match='recommendation_strength_not_stated_conflict'):
        validate(*case(heading='Sterke aanbeveling', ancestor=ancestor))


def test_intervening_prose_cannot_bind_external_label():
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_not_applicable'):
        validate(*case(gap='Dit is achtergrond.', explicit=('Sterk – tegen', 'b')))


def test_v3_provider_to_candidate_and_admission_is_independent():
    fragments = [_fragment('a', 'Vermijd behandeling A. Sterk – tegen', section_path=['Aanbevelingen']),
                 _fragment('b', CORE, section_path=['Aanbevelingen'])]
    _, _, obj, _ = prepare(CORE, fragments=fragments)
    assert obj['metadata']['admission']['gate_result'] == 'allowed'
    assert obj['proposed_recommendation_semantics']['strength_status'] == 'not_stated'
    assert obj['governance']['validation_status'] == 'needs_review'
    assert not obj.get('confirmed_recommendation_semantics')


@pytest.mark.parametrize("separator", [" ", "; ", ". "])
def test_explicit_trailing_stamp_cannot_hide_another_strength(separator):
    fragments, candidates, p = case(gap="Sterk – tegen" + separator + "Zwak – tegen", explicit=('Sterk – tegen', 'b'))
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_conflict'):
        validate(fragments, candidates, p)


def test_heading_after_b_and_closed_heading_do_not_bind():
    for mutation in ('after', 'closed', 'sibling'):
        fragments, candidates, p = case(heading='Sterke aanbeveling', explicit=('Sterke aanbeveling', 'h'))
        if mutation == 'after': fragments.append(fragments.pop(0))
        if mutation == 'closed':
            fragments.insert(2, _fragment('close', 'Andere aanbevelingen', object_type='heading', section_path=['Aanbevelingen']))
        if mutation == 'sibling': fragments[0]['section_path'] = ['Ander domein']
        with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_(not_applicable|cross_section)'):
            validate(fragments, candidates, p)


@pytest.mark.parametrize('ancillary_metadata', [False, True])
def test_new_binding_is_rechecked_at_transform_and_admission(ancillary_metadata):
    from src.semantic_transform_generic_v1 import transform
    from src.admission_gate_v1 import apply_admission_gate
    fragments = source(CORE + ' Sterk – tegen')
    spec, rows, obj, _ = prepare(CORE + ' Sterk – tegen', stamp='Sterk – tegen', fragments=fragments)
    manifest = {'canonical_source': obj['source']}
    bad = deepcopy(spec)
    target = next(o for o in bad['objects'] if o.get('proposed_recommendation_semantics'))
    target['proposed_recommendation_semantics']['strength'] = 'weak'
    if ancillary_metadata:
        target['metadata'] = {'passage_formation': {'test': 'ancillary'}}
    with pytest.raises(SemanticPassageError, match='recommendation_strength_literal_mismatch'):
        transform(bad, manifest, fragments)
    forged = deepcopy(rows)
    target = next(o for o in forged if o['object_id'] == obj['object_id'])
    target['proposed_recommendation_semantics']['strength'] = 'weak'
    gated = apply_admission_gate(forged, klasse='richtlijn', fragments=fragments,
                                document_version='1', source_hash='a'*64)
    target = next(o for o in gated if o['object_id'] == obj['object_id'])
    assert (target['metadata'].get('admission') or {}).get('gate_result') != 'allowed'


def test_console_persists_independence_quarantine_and_failed_replacement(tmp_path):
    import json
    from src.operations_console_v1 import OperationsConsole, ConsoleError
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing, PASSAGE_FORMATION_MODE_ENV
    from src.llm_provider_v1 import LLM_API_KEY_ENV, LLM_MODEL_ENV
    from src.source_bound_fields_v3 import MODE
    from tests.test_recommendation_context_v3 import response_for
    mode = ['valid']
    calls = []
    def post(url, headers, payload, timeout):
        calls.append(payload)
        data = json.loads(payload['input'][1]['content'])
        if mode[0] == 'fatal': p = {'objects': None}
        elif data.get('selection_targets'):
            p = {'objects': [], 'relations': [], 'abstain_reason': 'uncertain'}
        else:
            p = response_for(payload, CORE)
            if mode[0] == 'borrowed':
                owner = next(b for b in [*data['source_blocks'], *data['evidence_blocks']] if 'Vermijd behandeling A.' in b['text'])
                p['objects'][0]['recommendation_semantics'].update(
                    strength='strong', strength_status='explicit', strength_evidence={
                        'block_id': owner['block_id'], 'literal': 'Sterk – tegen', 'occurrence': None})
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(p)}]}]}
    env = {PASSAGE_FORMATION_MODE_ENV: MODE, LLM_API_KEY_ENV: 'test', LLM_MODEL_ENV: 'a07-test'}
    def reopen():
        c = OperationsConsole(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime')
        bind_pre_review_semantic_processing(c, environ=env, post_json=post)
        return c
    c = reopen()
    author = c.create_account(username='author', password='test-password-strong', roles=('researcher',))
    reviewer = c.create_account(username='reviewer', password='test-password-strong', roles=('reviewer',))
    receipt = c.ingest(actor_id=author['account_id'], filename='a07.html',
        data=f'<html><body><h1>Aanbevelingen</h1><p>Vermijd behandeling A. Sterk – tegen</p><p>{CORE}</p></body></html>'.encode(),
        content_type='text/html', ingest_kind='new', title='A07 synthetic', version='1', date='2026-10-11',
        live_url='', class_='richtlijn', family='a07', named_reviewers=[reviewer['account_id']])
    sid = receipt['snapshot_id']
    stored = c.snapshot_objects(sid, include_blocked=True)
    b = next(o for o in stored if (o.get('metadata') or {}).get('source_bound_fields'))
    assert b['metadata']['admission']['gate_result'] == 'allowed'
    assert b['proposed_recommendation_semantics']['strength_status'] == 'not_stated'
    c = reopen()
    assert c.snapshot_objects(sid, include_blocked=True) == stored
    count = len(calls)
    c.reextract_unpublished(actor_id=author['account_id'], snapshot_id=sid)
    assert len(calls) == count  # exact replay, no new provider request
    mode[0] = 'borrowed'; env[LLM_MODEL_ENV] = 'a07-borrowed'
    c.reextract_unpublished(actor_id=author['account_id'], snapshot_id=sid)
    quarantined = c.snapshot_objects(sid, include_blocked=True)
    from src.revision_workflow import current_revisions
    current = current_revisions(quarantined, snapshot_id=sid)
    assert not any((o.get('metadata') or {}).get('admission', {}).get('gate_result') == 'allowed' and CORE in (o.get('content') or {}).get('clean_text', '') and (o.get('governance') or {}).get('validation_status') != 'superseded' for o in current)
    from src.source_accountability_v1 import evidence_of
    assert any(CORE in (evidence_of(o).get('text') or '') for o in quarantined)
    assert 'recommendation_strength_evidence_not_applicable' in json.dumps(c._envelope(sid))
    from src.processing_evidence_export_v1 import processing_evidence_tables
    tables, _ = processing_evidence_tables(snapshot_id=sid, revision='test',
        envelope=c._envelope(sid), objects=quarantined)
    findings = [r['finding']['strength_applicability'] for r in tables['formation_findings']
                if r['reason_code'] == 'recommendation_strength_evidence_not_applicable']
    assert findings and all(f['outcome'] == 'absent' and f['reference_applicable'] is False for f in findings)
    before_replay = deepcopy(c._envelope(sid)['semantic_replay'])
    mode[0] = 'fatal'; env[LLM_MODEL_ENV] = 'a07-fatal'
    with pytest.raises(ConsoleError):
        c.reextract_unpublished(actor_id=author['account_id'], snapshot_id=sid)
    c = reopen()
    assert c.snapshot_objects(sid, include_blocked=True) == quarantined
    assert c._envelope(sid)['semantic_replay'] == before_replay


def test_plain_label_with_matching_section_is_not_a_group_heading():
    fragments, candidates, p = case(heading='Sterke aanbeveling', explicit=('Sterke aanbeveling', 'h'))
    fragments[0].pop('object_type'); fragments[0].pop('heading')
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_not_applicable'):
        validate(fragments, candidates, p)


def test_shared_heading_can_bind_two_independent_recommendations():
    fragments, candidates, p = case(heading='Sterke aanbeveling', explicit=('Sterke aanbeveling', 'h'))
    # B's source-bound proposal is reused for a second literal recommendation
    # with a different source identity; both remain inside the heading scope.
    second = _fragment('c', 'Gebruik geen crème.', section_path=['Aanbevelingen'])
    fragments.append(second); candidates.append(second)
    cblock = semantic_source_blocks(candidates)[-1]
    c = deepcopy(p['objects'][0])
    def replace(ref):
        if ref and ref['block_id'] == p['objects'][0]['spans'][0]['block_id']:
            literal = next(b for b in semantic_source_blocks(candidates) if b['block_id'] == ref['block_id'])['text'][ref['start']:ref['end']]
            literal = literal.replace('zalf', 'crème')
            start = cblock['text'].index(literal)
            ref.update(block_id=cblock['block_id'], start=start, end=start+len(literal))
    for ref in [*c['spans'], c['recommendation_semantics']['direction_evidence'],
                *(entry['span'] for entry in c['field_evidence'].values())]: replace(ref)
    p['objects'].append(c)
    rows = validate(fragments, candidates, p)
    assert len(rows) == 2
    assert all(r['proposed_recommendation_semantics']['strength'] == 'strong' for r in rows)


@pytest.mark.parametrize('version', ['v1', 'v2', 'v3'])
def test_complete_recommendation_binds_only_following_standalone_stamps(version):
    fragments, candidates, p = case()
    labels = [_fragment('label', 'Sterk – tegen', section_path=['Aanbevelingen'])]
    fragments.extend(labels)
    label = semantic_source_blocks(fragments)[-1]
    p['objects'][0]['recommendation_semantics'].update(strength='strong', strength_status='explicit',
        strength_evidence={'block_id': label['block_id'], 'start': 0, 'end': len(label['text'])})
    assert validate(fragments, candidates, p, version)[0]['proposed_recommendation_semantics']['strength'] == 'strong'
    fragments.append(_fragment('weak', 'Zwak – tegen', section_path=['Aanbevelingen']))
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_conflict'):
        validate(fragments, candidates, p, version)
    p['objects'][0]['recommendation_semantics'].update(strength=None, strength_status='not_stated', strength_evidence=None)
    with pytest.raises(SemanticPassageError, match='recommendation_strength_not_stated_conflict'):
        validate(fragments, candidates, p, version)


@pytest.mark.parametrize('version', ['v1', 'v2', 'v3'])
@pytest.mark.parametrize('labels', ['Sterk – tegen; Zwak – tegen',
                                  'Sterke aanbeveling. Zwakke aanbeveling',
                                  'Sterk – tegen, Sterk – voor'])
def test_combined_standalone_labels_do_not_become_absence(version, labels):
    fragments, candidates, p = case()
    fragments.append(_fragment('labels', labels, section_path=['Aanbevelingen']))
    with pytest.raises(SemanticPassageError, match='recommendation_strength_not_stated_conflict'):
        validate(fragments, candidates, p, version)
    block = semantic_source_blocks(fragments)[-1]
    literal = labels.split(';')[0].split('.')[0].split(',')[0]
    p['objects'][0]['recommendation_semantics'].update(strength='strong', strength_status='explicit',
        strength_evidence={'block_id': block['block_id'], 'start': 0, 'end': len(literal)})
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_conflict'):
        validate(fragments, candidates, p, version)


def test_combined_stamp_block_is_rejected_by_real_v3_formation():
    fragments = source(CORE)
    fragments.append(_fragment('labels', 'Sterk – tegen; Zwak – tegen', section_path=['Aanbevelingen']))
    _, rows, obj, _ = prepare(CORE, fragments=fragments, allow_empty=True)
    assert obj is None
    assert not any((o.get('metadata') or {}).get('admission', {}).get('gate_result') == 'allowed'
                   and o.get('proposed_object_type') == 'recommendation' for o in rows)


@pytest.mark.parametrize('labels', ['Sterk – tegen; Sterk – tegen', 'Sterke aanbeveling. Sterke aanbeveling'])
def test_consistent_stamp_sequence_remains_usable_without_binding_prose(labels):
    fragments, candidates, p = case()
    fragments.append(_fragment('labels', labels, section_path=['Aanbevelingen']))
    block = semantic_source_blocks(fragments)[-1]
    literal = labels.split(';')[0].split('.')[0]
    p['objects'][0]['recommendation_semantics'].update(strength='strong', strength_status='explicit',
        strength_evidence={'block_id': block['block_id'], 'start': 0, 'end': len(literal)})
    assert validate(fragments, candidates, p)[0]['proposed_recommendation_semantics']['strength'] == 'strong'
    fragments[-1]['raw_text'] = fragments[-1]['clean_text'] = labels + ' Dit betreft behandeling A.'
    p['objects'][0]['recommendation_semantics']['strength_evidence']['block_id'] = semantic_source_blocks(fragments)[-1]['block_id']
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_not_applicable'):
        validate(fragments, candidates, p)


@pytest.mark.parametrize('version', [None, '', 'recommendation-semantics-evidence-v999'])
def test_unknown_evidence_version_cannot_skip_transform_or_admission(version):
    from src.semantic_transform_generic_v1 import transform
    from src.admission_gate_v1 import apply_admission_gate
    spec, rows, obj, fragments = prepare(CORE + ' Sterk – tegen', stamp='Sterk – tegen')
    target = next(o for o in spec['objects'] if o.get('proposed_recommendation_semantics'))
    target['proposed_recommendation_semantics']['strength'] = 'weak'
    target['recommendation_semantics_evidence']['version'] = version
    with pytest.raises(SemanticPassageError, match='recommendation_semantics_evidence_version_invalid'):
        transform(spec, {'canonical_source': obj['source']}, fragments)
    target = next(o for o in rows if o['object_id'] == obj['object_id'])
    target['proposed_recommendation_semantics']['strength'] = 'weak'
    target['metadata']['recommendation_semantics_evidence']['version'] = version
    gated = apply_admission_gate(rows, klasse='richtlijn', fragments=fragments,
                                document_version='1', source_hash='a'*64)
    target = next(o for o in gated if o['object_id'] == obj['object_id'])
    assert target['metadata']['admission']['gate_result'] == 'blocked'
    assert 'recommendation_semantics_evidence_version_invalid' in target['metadata']['admission']['reason_codes']


@pytest.mark.parametrize('ancillary_metadata', [False, True])
def test_historical_v1_evidence_is_preserved_at_transform_and_admission(ancillary_metadata):
    from src.semantic_transform_generic_v1 import transform
    from src.admission_gate_v1 import apply_admission_gate
    spec, _, obj, fragments = prepare(CORE + ' Sterk – tegen', stamp='Sterk – tegen')
    target = next(o for o in spec['objects'] if o.get('proposed_recommendation_semantics'))
    target['recommendation_semantics_evidence']['version'] = 'recommendation-semantics-evidence-v1'
    if ancillary_metadata:
        target['metadata'] = {'passage_formation': {'test': 'ancillary'}}
    before = deepcopy(spec)
    rows = transform(spec, {'canonical_source': obj['source']}, fragments)
    rows = apply_admission_gate(rows, klasse='richtlijn', fragments=fragments,
                               document_version='1', source_hash='a'*64)
    target = next(o for o in rows if o['object_id'] == obj['object_id'])
    assert target['metadata']['admission']['gate_result'] == 'allowed'
    assert target['metadata']['recommendation_semantics_evidence']['version'] == 'recommendation-semantics-evidence-v1'
    assert spec == before


@pytest.mark.parametrize('version', ['v1', 'v2', 'v3'])
def test_shared_strength_heading_must_cover_entire_selection(version):
    fragments, candidates, p = case(heading='Sterke aanbeveling', explicit=('Sterke aanbeveling', 'h'))
    fragments = [f for f in fragments if f['fragment_id'] != 'a']
    candidates = [f for f in candidates if f['fragment_id'] != 'a']
    fragments.append(_fragment('close', 'Andere aanbevelingen', object_type='heading', section_path=['Aanbevelingen']))
    tail = _fragment('tail', 'Bespreek alternatieven.', section_path=['Aanbevelingen'])
    fragments.append(tail)
    candidates.append(tail)
    block = semantic_source_blocks(candidates)[-1]
    p['objects'][0]['spans'].append({'block_id': block['block_id'], 'start': 0, 'end': len(block['text'])})
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_not_applicable'):
        validate(fragments, candidates, p, version)


@pytest.mark.parametrize('kind', ['selected_text', 'adjacent_strength_label', 'shared_heading'])
def test_recovery_finding_explains_applicable_strength(kind):
    if kind == 'selected_text':
        args = case(own='Sterk – tegen')
    elif kind == 'adjacent_strength_label':
        args = case(gap='Sterk – tegen')
    else:
        args = case(heading='Sterke aanbeveling')
    with pytest.raises(SemanticPassageError, match='recommendation_strength_not_stated_conflict') as error:
        validate(*args)
    assessment = error.value.finding['strength_applicability']
    assert assessment['outcome'] == 'matching'
    assert kind in {row['reason'] for row in assessment['ranges']}
    assert all(set(row) >= {'block_id', 'start', 'end', 'reason'} for row in assessment['ranges'])


def test_conflicting_labels_have_conflicting_finding_not_absent():
    with pytest.raises(SemanticPassageError) as error:
        validate(*case(own='Sterk – tegen Zwak – tegen'))
    assert error.value.finding['strength_applicability']['outcome'] == 'conflicting'


def test_non_applicable_label_is_not_uncertainty():
    with pytest.raises(SemanticPassageError) as error:
        validate(*case('Sterk – tegen', explicit=('Sterk – tegen', 'a')))
    assessment = error.value.finding['strength_applicability']
    assert assessment['outcome'] == 'absent'
    assert assessment['reference_applicable'] is False


def test_ambiguous_strength_literal_is_recorded_as_uncertain():
    from src.source_evidence_resolution_v1 import resolve_proposal_evidence
    fragments, candidates, p = case(own='Sterk – tegen; Sterk – tegen')
    block = semantic_source_blocks(candidates)[-1]
    p['objects'][0]['recommendation_semantics'].update(strength='strong', strength_status='explicit',
        strength_evidence={'block_id': block['block_id'], 'literal': 'Sterk – tegen', 'occurrence': None})
    with pytest.raises(SemanticPassageError, match='semantic_evidence_literal_ambiguous') as error:
        resolve_proposal_evidence(p, blocks=semantic_source_blocks(candidates), evidence_blocks=semantic_source_blocks(fragments))
    assert error.value.finding['strength_applicability']['outcome'] == 'uncertain'


@pytest.mark.parametrize('ancillary_metadata', [False, True])
def test_whole_heading_scope_at_real_materialisation_transform_and_admission(ancillary_metadata):
    from src.semantic_transform_generic_v1 import transform
    from src.admission_gate_v1 import apply_admission_gate
    fragments, _, _ = case(heading='Sterke aanbeveling')
    tail = _fragment('tail', 'Bespreek alternatieven.', section_path=['Aanbevelingen'])
    fragments.append(tail)
    blocks = semantic_source_blocks(fragments)
    heading = next(b for b in blocks if 'h' in b['source_fragment_ids'])
    last = blocks[-1]
    def provider_output(p):
        obj = p['objects'][0]
        obj['spans'].append({'block_id': last['block_id'], 'literal': last['text'], 'occurrence': None})
        obj['recommendation_semantics'].update(strength='strong', strength_status='explicit',
            strength_evidence={'block_id': heading['block_id'], 'literal': heading['text'], 'occurrence': None})
    spec, rows, obj, _ = prepare(CORE, fragments=fragments, mutate=provider_output)
    unit = next(u for u in spec['objects'] if u['object_id'] == obj['object_id'])
    assert unit['clean_text'] == CORE + ' Bespreek alternatieven.'
    assert obj['content']['clean_text'] == unit['clean_text']
    assert set(unit['recommendation_semantics_evidence']) == {'version', 'direction', 'strength'}
    if ancillary_metadata:
        unit['metadata'] = {'passage_formation': {'test': 'ancillary'}}
    manifest = {'canonical_source': obj['source']}
    closing = _fragment('close', 'Andere aanbevelingen', object_type='heading', section_path=['Aanbevelingen'])
    outside = fragments[:-1] + [closing, fragments[-1]]
    before = deepcopy((spec, rows))
    with pytest.raises(SemanticPassageError, match='recommendation_strength_evidence_not_applicable'):
        transform(spec, manifest, outside)
    gated = apply_admission_gate(rows, klasse='richtlijn', fragments=outside,
                                document_version='1', source_hash='a'*64)
    target = next(o for o in gated if o['object_id'] == obj['object_id'])
    assert 'recommendation_strength_evidence_not_applicable' in target['metadata']['admission']['reason_codes']
    assert target['metadata']['admission']['gate_result'] == 'blocked'
    assert (spec, rows) == before
    _, rejected_rows, rejected, _ = prepare(CORE, fragments=outside, mutate=provider_output, allow_empty=True)
    assert rejected is None
    assert not any(o.get('proposed_object_type') == 'recommendation' and
                   o.get('metadata', {}).get('admission', {}).get('gate_result') == 'allowed'
                   for o in rejected_rows)


def test_ordinary_provider_cannot_claim_historical_evidence_version():
    fragments, candidates, p = case()
    p['objects'][0]['recommendation_semantics_evidence'] = {'version': 'recommendation-semantics-evidence-v1'}
    with pytest.raises(SemanticPassageError, match='semantic_object_contains_untrusted_fields'):
        validate(fragments, candidates, p)
