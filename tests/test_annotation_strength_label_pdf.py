"""PDF → human annotation → Admission → Review strength-binding regression.

Source wording is from the repository's preserved page 18 Smetten excerpt.
The generated PDFs exercise two layouts independently of the full source PDF.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import os
from pathlib import Path
import re

import fitz
import pytest
from starlette.testclient import TestClient

from src.integrity_kernel import compute_canonical_object_hash
from src.vorming import human_annotation_v1 as annotation
from src.vorming.admission_gate_v1 import admission_of, apply_admission_gate
from src.vorming.semantic_passage_v1 import STRENGTH_LABEL_EVIDENCE, validate_bound_recommendation_semantics
from src.vorming.source_bound_fields_v3 import FIELDS
from tests.production_support import application_for, restart_production
from tests.test_human_annotation_postgres import anchor, command
from tests.test_human_annotation_review_postgres import candidate, execute_build
from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore


STATEMENT = ('Breng bij iedere patiënt de risicofactoren voor smetten in kaart, '
             'om te bepalen of preventieve maatregelen nodig zijn.')
LABEL = 'Sterk – voor'


def pdf_source(layout, labels=(LABEL,)):
    with fitz.open() as document:
        page = document.new_page(width=840)
        page.insert_font(fontname='Fixture', fontbuffer=fitz.Font('helv').buffer)
        lines = [STATEMENT + ' ' + labels[0], *labels[1:]] if layout == 'same' and labels else [STATEMENT, *labels]
        for index, text in enumerate(lines):
            page.insert_text((44, 72 + index * 44), text, fontname='Fixture', fontsize=11)
        return document.tobytes()


def prepare_recommendation_pdf(console, layout, *, labels=(LABEL,), source_bytes=None):
    actor = console.create_account(username='sterkte', password='fixture-only',
                                   roles=('researcher', 'reviewer'))['account_id']
    data = pdf_source(layout, labels) if source_bytes is None else source_bytes
    sid = console.receive_source(actor_id=actor, filename='smetten-proef.pdf',
        data=data, content_type='application/pdf',
        ingest_kind='new', title='Smetten — bronproef', version='1.0', date='2026-11-25',
        live_url='', class_='richtlijn', family='test', named_reviewers=[],
        review_choice={'contract': 'review-configuration-v2', 'option': 'uploader_sole',
                       'four_eyes_required': False, 'reviewers': [], 'readers': []})['snapshot_id']
    view = annotation.prepare(console, actor_id=actor, snapshot_id=sid, expected_revision=console.objects_revision(sid))
    block = next(block for block in view['blocks'] if STATEMENT in block['text'])
    start = block['text'].index(STATEMENT)
    core = anchor({'blocks': [block]}, STATEMENT, start=start, end=start + len(STATEMENT))
    assert core['quote'] == STATEMENT
    selection = command(view, ranges=[core], status='ready')
    fields = {name: {'span': None, 'missing_reason': 'uncertain'} for name in FIELDS}
    fields.update(type_evidence_spans={'core': True}, recommendation_evidence_span={'core': True})
    selection['selection'].update(field_evidence=fields, recommendation_semantics=None)
    return actor, sid, view, selection


def label_anchor(view, label=LABEL):
    block = next(block for block in view['blocks'] if label in block['text'])
    start = block['text'].index(label)
    return {'block_id': block['block_id'], 'start': start, 'end': start + len(label), 'quote': label}


@pytest.mark.parametrize('layout,manual,label', [
    ('same', False, LABEL),
    ('following', False, LABEL),
    ('same', True, LABEL),
    ('following', True, LABEL),
    ('following', True, 'Sterke aanbeveling'),
], ids=['automatic-same', 'automatic-following', 'manual-same', 'manual-following', 'manual-no-direction'])
def test_pdf_strength_label_survives_annotation_build_admission_and_review(
        tmp_path, production_console, monkeypatch, layout, manual, label):
    monkeypatch.setenv('METIS_PDF_EXTRACTOR', 'legacy-comparison')
    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    actor, sid, view, selection = prepare_recommendation_pdf(console, layout, labels=(label,))
    witness = label_anchor(view, label)
    complete_proposal = manual and label == LABEL
    core = selection['selection']['ranges'][0]
    assert (witness['block_id'] == core['block_id']) is (layout == 'same')
    if manual:
        selection['selection']['recommendation_strength_label'] = witness
    annotation.save(console, actor_id=actor, **selection)
    if manual:
        saved, = annotation.overview(restart_production(console), actor_id=actor, snapshot_id=sid)['entries']
        assert saved['recommendation_strength_label']['quote'] == label
    execute_build(console, actor, sid)
    console = restart_production(console)
    obj = candidate(console, sid)
    assert obj['content']['clean_text'] == STATEMENT
    proof = obj['metadata'][STRENGTH_LABEL_EVIDENCE]
    assert proof['selection'] == ('manual' if manual else 'automatic')
    assert proof['text'] == label
    assert proof['label']['source_fragment_ids']
    assert proof['direction_anchor']['block_id'] == core['block_id']
    assert proof['direction_anchor']['end'] == core['end']
    assert admission_of(obj)['gate_result'] == 'allowed'
    assert bool(obj.get('proposed_recommendation_semantics')) is complete_proposal
    assert not obj.get('confirmed_recommendation_semantics')
    fragments = console.review_source_fragments(sid)
    validate_bound_recommendation_semantics(obj, fragments=fragments)
    tampered = deepcopy(obj)
    tampered['metadata'][STRENGTH_LABEL_EVIDENCE]['text'] = 'Zwak – voor'
    assert compute_canonical_object_hash(tampered) != compute_canonical_object_hash(obj)
    with pytest.raises(ValueError, match='recommendation_strength_label_binding_mismatch'):
        validate_bound_recommendation_semantics(tampered, fragments=fragments)

    blocked, = apply_admission_gate([tampered], klasse='richtlijn', fragments=fragments,
                                    document_version=obj['source']['version'],
                                    source_hash=obj['source']['source_checksum'])
    assert 'recommendation_strength_label_binding_mismatch' in admission_of(blocked)['reason_codes']

    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username': 'sterkte', 'password': 'fixture-only'})
        page = client.get('/review', params={'document': sid, 'object': obj['object_id']})
        assert f'Sterktelabel uit de bron: {label}' in page.text
        form = page.text.split('<form method="post" action="/review"', 1)[1].split('</form>', 1)[0]
        fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form))
        fields.update(applicable='yes', complete='yes', placed_correctly='yes',
                      review_action='approve', evidence_not_applicable='yes')
        if complete_proposal:
            fields['recommendation_review_action'] = 'accept'
        else:
            fields.update(recommendation_review_action='decline', recommendation_direction='for',
                          recommendation_strength_level='strong')
        result = client.post('/review', data=fields, follow_redirects=False)
        assert result.status_code == 303, result.text
    stored = candidate(console, sid)
    assert stored['confirmed_recommendation_semantics']['strength'] == 'strong'
    assert stored['confirmed_recommendation_semantics']['strength_evidence_span'] == label


@pytest.mark.parametrize('labels,reason', [
    ((), None),
    (('Een volgende, afzonderlijke uitspraak.', LABEL), 'recommendation_strength_label_not_applicable'),
    ((LABEL, 'Zwak – voor'), 'recommendation_strength_evidence_conflict'),
])
def test_pdf_strength_label_does_not_bind_when_missing_distant_or_conflicting(tmp_path, production_console,
                                                                           monkeypatch, labels, reason):
    from src.vorming.semantic_passage_v1 import annotation_strength_label

    monkeypatch.setenv('METIS_PDF_EXTRACTOR', 'legacy-comparison')
    console = production_console(root=tmp_path)
    actor, sid, view, request = prepare_recommendation_pdf(console, 'following', labels=labels)
    payload = request['selection']
    fragments = console.review_source_fragments(sid)
    assert annotation_strength_label(payload, fragments=fragments) is None
    if reason:
        payload['recommendation_strength_label'] = label_anchor(view)
        annotation.save(console, actor_id=actor, **request)
        check = annotation.check_current(console, actor_id=actor, snapshot_id=sid,
                                         annotation_id=request['annotation_id'])
        assert reason in check['codes']
    else:
        annotation.save(console, actor_id=actor, **request)
        execute_build(console, actor, sid)
        assert STRENGTH_LABEL_EVIDENCE not in candidate(console, sid)['metadata']


@pytest.mark.parametrize('table_cell,expect_label', [(None, True), (0, False)])
def test_pdf_strength_label_requires_a_non_table_source_binding(tmp_path, table_cell, expect_label):
    from src.vorming.docling_contract_v1 import CONTRACT, ExtractedFragments
    from src.vorming.extract_pdf_v2 import extract
    from src.vorming.semantic_passage_v1 import annotation_strength_label, semantic_source_blocks

    path = tmp_path / 'case.pdf'
    path.write_bytes(pdf_source('following'))
    rows = extract(path, document_id='document', source_id='source')
    for row in rows:
        row['parser_version'] = CONTRACT + '/fixture'
    core, stamp = semantic_source_blocks(rows)
    payload = {'object_type': 'recommendation',
               'ranges': [{'role': 'core', 'block_id': core['block_id'], 'start': 0, 'end': len(STATEMENT)}]}
    record = {'bindings': [{'fragment_id': rows[0]['fragment_id'], 'table_cell': None},
                           {'fragment_id': rows[1]['fragment_id'], 'table_cell': table_cell}]}
    fragments = ExtractedFragments(rows, record)
    assert bool(annotation_strength_label(payload, fragments=fragments)) is expect_label
    assert annotation_strength_label(payload, fragments=rows) is None
    if not expect_label:
        payload['recommendation_strength_label'] = {'block_id': stamp['block_id'], 'start': 0, 'end': len(LABEL)}
        with pytest.raises(ValueError, match='recommendation_strength_label_not_applicable'):
            annotation_strength_label(payload, fragments=fragments)



@pytest.mark.skipif(not os.environ.get('METIS_SMETTEN_PDF'), reason='Provide the original Smetten PDF locally')
@pytest.mark.parametrize('manual', [False, True], ids=['automatic', 'manual'])
def test_original_smetten_pdf_strength_label_reaches_review(tmp_path, production_console, monkeypatch, manual):
    from src.vorming import annotation_document_check_v1 as document_check
    from src.vorming import confirmed_document_structure_v1 as structure
    from src.vorming.semantic_passage_v1 import annotation_strength_label

    source = Path(os.environ['METIS_SMETTEN_PDF'])
    monkeypatch.setenv('METIS_PDF_EXTRACTOR', os.getenv('METIS_PDF_EXTRACTOR', 'docling'))
    monkeypatch.setenv('METIS_ANNOTATION_CONFIRMED_STRUCTURE', '1')
    monkeypatch.setenv('METIS_ANNOTATION_DOCUMENT_CHECK', '1')
    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    actor, sid, view, request = prepare_recommendation_pdf(console, 'same', source_bytes=source.read_bytes())
    inputs = {'actor_id': actor, 'snapshot_id': sid}
    structure.confirm(console, **inputs, extraction_hash=view['extraction_hash'],
                      entries=structure.proposed(view['blocks']))
    fragments = console.review_source_fragments(sid)
    selection = request['selection']
    proof = annotation_strength_label(selection, fragments=fragments)
    assert proof is not None and proof['text'] == LABEL
    assert {fragment['source_page'] for fragment in fragments
            if fragment['fragment_id'] in proof['label']['source_fragment_ids']} == {18}
    if manual:
        witness = proof['label']
        selection['recommendation_strength_label'] = {
            **{key: witness[key] for key in ('block_id', 'start', 'end')}, 'quote': LABEL}
    proposals = annotation.open_proposals(view['blocks'], selection)
    if proposals:
        selection['declined_context'] = [
            {key: proposal[key] for key in ('block_id', 'start', 'end', 'quote')} for proposal in proposals]
    annotation.save(console, actor_id=actor, **request)
    view = annotation.overview(console, **inputs)
    document_check.transition(console, **inputs, phase='checking',
                              expected_generation=view['generation'], expected_round=0)
    execute_build(console, actor, sid)
    console = restart_production(console)
    obj = candidate(console, sid)
    assert obj['content']['clean_text'] == STATEMENT
    assert admission_of(obj)['gate_result'] == 'allowed'
    assert obj['metadata'][STRENGTH_LABEL_EVIDENCE]['selection'] == ('manual' if manual else 'automatic')
    validate_bound_recommendation_semantics(obj, fragments=console.review_source_fragments(sid))
    assert not obj.get('confirmed_recommendation_semantics')
    with TestClient(application_for(console)) as client:
        assert client.post('/login', data={'username': 'sterkte', 'password': 'fixture-only'},
                           follow_redirects=False).status_code == 303
        review = client.get('/review', params={'document': sid, 'object': obj['object_id']})
        assert review.status_code == 200 and f'Sterktelabel uit de bron: {LABEL}' in review.text
        form = review.text.split('<form method="post" action="/review"', 1)[1].split('</form>', 1)[0]
        fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form))
        fields.update(applicable='yes', complete='yes', placed_correctly='yes',
                      evidence_not_applicable='yes', review_action='approve')
        if manual:
            fields['recommendation_review_action'] = 'accept'
        else:
            fields.update(recommendation_review_action='decline', recommendation_direction='for',
                          recommendation_strength_level='strong')
        assert client.post('/review', data=fields, follow_redirects=False).status_code == 303
    confirmed = candidate(console, sid)['confirmed_recommendation_semantics']
    assert (confirmed['direction'], confirmed['strength'], confirmed['strength_evidence_span']) == ('for', 'strong', LABEL)
