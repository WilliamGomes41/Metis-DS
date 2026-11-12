"""#1060: missing sentence parts are signals for human annotation, never for anything else.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

from src.vorming.admission_gate_v1 import (HUMAN_SIGNAL_CODES, admission_of, admit_candidate,
                                           split_human_signals)
from tests.test_human_annotation_materialisation import canonical, inputs
from tests.test_t7_creator_cut import _gate


def admitted(change=lambda fields: None, kind='explanation'):
    fragments, decision = inputs()
    decision['proposed_object_type'] = kind
    fields = decision['field_evidence']
    fields['factual_claim_span'] = {'span': None, 'missing_reason': 'uncertain'}
    fields['support_span'] = {'core': True}
    change(fields)
    return admission_of(_gate([canonical(fragments, decision)], fragments)[0])


def complete(fields):
    fields['supported_object'] = {'span': fields['subject_span']['span'], 'missing_reason': None}


def test_statement_leaning_on_other_text_is_reviewable_with_its_signals_recorded():
    # The list item from the practice case: nothing in the sentence names what it explains.
    record = admitted()
    assert record['gate_result'] == 'allowed' and record['reason_codes'] == []
    assert record['signals'] == ['type_contract_incomplete', 'supported_object_missing', 'no_independent_claim']


def test_complete_annotation_recomputes_to_the_same_record_without_a_signals_key():
    fragments, decision = inputs()
    decision['proposed_object_type'] = 'explanation'
    fields = decision['field_evidence']
    fields['factual_claim_span'] = {'span': None, 'missing_reason': 'uncertain'}
    fields['support_span'] = {'core': True}
    complete(fields)
    first = _gate([canonical(fragments, decision)], fragments)[0]
    record = admission_of(first)
    assert record['gate_result'] == 'allowed' and 'signals' not in record
    assert admission_of(_gate([deepcopy(first)], fragments)[0]) == record


def test_source_fidelity_still_blocks_and_keeps_its_companion_code():
    blocking, signals = split_human_signals(['type_contract_incomplete', 'span_not_in_source',
                                             'source_fidelity_failure', 'predicate_missing'])
    assert blocking == ['type_contract_incomplete', 'span_not_in_source', 'source_fidelity_failure']
    assert signals == ['predicate_missing']
    for code in ('span_not_in_source', 'source_fidelity_failure', 'type_evidence_missing',
                 'recommendation_core_omits_source', 'recommendation_core_field_mismatch',
                 'recommendation_semantics_invalid', 'recommendation_direction_missing',
                 'recommendation_strength_unmapped', 'context_necessary_unresolved',
                 'annotation_core_required', 'annotation_evidence_required', 'annotation_core_duplicate'):
        assert code not in HUMAN_SIGNAL_CODES


def test_signal_beside_a_blocking_code_stays_blocked_with_the_signal_kept_apart():
    def unresolved(fields):
        fields['predicate_span'] = {'span': None, 'missing_reason': 'uncertain'}
    fragments, decision = inputs()
    decision['proposed_object_type'] = 'recommendation'  # no direction recorded: must keep blocking
    fields = decision['field_evidence']
    fields['factual_claim_span'] = {'span': None, 'missing_reason': 'uncertain'}
    fields['recommendation_evidence_span'] = {'core': True}
    unresolved(fields)
    record = admission_of(_gate([canonical(fragments, decision)], fragments)[0])
    assert record['gate_result'] == 'blocked' and record['reason_codes']
    assert not set(record['reason_codes']) & HUMAN_SIGNAL_CODES
    assert 'predicate_missing' in record['signals']


def test_non_human_candidate_keeps_every_code_blocking():
    row = {'candidate_text': 'De huid is droog.', 'source_text_exact': 'De huid is droog.',
           'proposed_type': 'explanation', 'subject_span': 'De huid', 'predicate_span': '',
           'type_evidence_spans': ['De huid is droog.'], 'support_span': 'De huid is droog.',
           'source_locator_start': 'lines:1-1', 'source_locator_end': 'lines:1-1', 'skip_context_scan': False}
    record = admit_candidate(deepcopy(row))
    assert record['gate_result'] == 'blocked' and 'signals' not in record
    assert set(record['reason_codes']) & HUMAN_SIGNAL_CODES  # the same codes block here


def test_list_item_leaning_on_its_introduction_goes_from_annotation_to_approved_review(tmp_path, production_console):
    """The practice case end to end on the real workflow store."""
    from src.vorming import human_annotation_build_v1 as build
    from src.vorming import human_annotation_v1 as annotation
    from src.vorming.source_bound_fields_v3 import FIELDS
    from tests.test_human_annotation_postgres import anchor, command
    from tests.test_human_annotation_review_postgres import approve, candidate, execute_build

    console = production_console(root=tmp_path)
    actor = console.create_account(username='lijst', password='human-list-secret',
                                   roles=('researcher', 'reviewer'))['account_id']
    sid = console.receive_source(actor_id=actor, filename='smetten.html', content_type='text/html',
        data=('<html><body><p>De volgende mechanismen spelen mogelijk een rol bij het risico op smetten:</p>'
              '<p>Bij diabetes mellitus zou de huid vatbaarder kunnen zijn voor irritatie en infecties.</p>'
              '</body></html>').encode(),
        ingest_kind='new', title='Smetten', version='1.0', date='2026-11-12', live_url='',
        class_='richtlijn', family='test', named_reviewers=[],
        review_choice={'contract': 'review-configuration-v2', 'option': 'uploader_sole',
                       'four_eyes_required': False, 'reviewers': [], 'readers': []})['snapshot_id']
    view = annotation.prepare(console, actor_id=actor, snapshot_id=sid, expected_revision=console.objects_revision(sid))
    core = anchor(view, 'Bij diabetes')
    introduction = {**anchor(view, 'De volgende mechanismen', role='list_introduction'), 'required_for_meaning': True}
    # The worker marked the statement and the text that belongs to it. No sentence part is filled in and
    # no evidence choice is made: with nothing linked, that decision is the reviewer's.
    fields = {key: {'span': None, 'missing_reason': 'uncertain'} for key in FIELDS}
    fields.update(type_evidence_spans={'core': True}, support_span={'core': True})
    request = command(view, ranges=[core, introduction], status='ready')
    request['selection'].update(object_type='explanation', evidence_not_applicable=False,
                                field_evidence=fields, required_links=[])
    annotation.save(console, actor_id=actor, **request)

    checked = annotation.check_current(console, actor_id=actor, snapshot_id=sid, annotation_id=request['annotation_id'])
    assert checked['codes'] == []
    assert {'subject_missing', 'predicate_missing', 'supported_object_missing'} <= set(checked['signals'])
    overview = build.overview(console, actor_id=actor, snapshot_id=sid)
    assert overview['can_finalize'] and overview['inspection']['findings'] == []

    execute_build(console, actor, sid)
    obj = candidate(console, sid)
    assert obj['content']['clean_text'] == core['quote']
    admission = obj['metadata']['admission']
    assert admission['gate_result'] == 'allowed' and admission['reason_codes'] == []
    assert {'subject_missing', 'predicate_missing', 'supported_object_missing'} <= set(admission['signals'])
    assert [entry['text'] for entry in obj['metadata']['source_bound_context']['entries']] == [introduction['quote']]

    # Slice 3: the reviewer reads the signals under the existing completeness question.
    from starlette.testclient import TestClient
    from tests.production_support import application_for
    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username': 'lijst', 'password': 'human-list-secret'})
        card = client.get('/review', params={'document': sid, 'object': obj['object_id']}).text
    question = card[card.index('Is dit compleet?'):card.index('Staat dit op de juiste plek?')]
    assert 'De uitspraak leunt mogelijk op andere tekst. Controleer of de gekoppelde tekst volstaat.' in question
    assert 'Niet vastgesteld over wie of wat de uitspraak gaat.' in question
    assert 'Toelichting · voorgesteld type' in card
    assert card.count('<fieldset class="ko-question">') == 3 and card.count('data-ko-signals') == 1

    # Approval without linked evidence is refused until the reviewer decides it is not applicable.
    import pytest
    from src.operations_console_v1 import ConsoleError
    from tests.ko_review_fixture_support import affirmative_assessment
    with pytest.raises(ConsoleError) as refused:
        console.review_object(actor_id=actor, snapshot_id=sid, object_id=obj['object_id'], decision='approve',
                              confirmed_object_type='explanation', assessment=affirmative_assessment())
    assert refused.value.code == 'knowledge_evidence_required'
    approve(console, sid, obj['object_id'], actor)
    from src.review.knowledge_object_state_v1 import derive_ko_state
    state = derive_ko_state(candidate(console, sid), review_path='richtlijn',
                            bindings=console.object_review_bindings(sid),
                            fragments=console.review_source_fragments(sid))
    assert state['state'] == 'Goedgekeurd', state
