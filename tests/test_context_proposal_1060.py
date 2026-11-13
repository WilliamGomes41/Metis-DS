"""#1060 slice 4: Metis points at the introduction a list item leans on; the worker answers.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming.human_annotation_context_proposal_v1 import MAX_BETWEEN, proposals

INTRO = 'Smetten komt vaak voor. De volgende mechanismen spelen mogelijk een rol:'


def block(block_id, text, section=()):
    return {'block_id': block_id, 'text': text, 'section_path': list(section)}


def core(block_id, text):
    return {'block_id': block_id, 'start': 0, 'end': len(text), 'role': 'core'}


ITEMS = [block('a', INTRO), block('b', 'Bij diabetes is de huid vatbaarder.'), block('c', 'Overgewicht vergroot huidplooien.')]


def test_list_item_gets_only_the_last_sentence_of_its_introduction_as_exact_source():
    [proposal] = proposals(ITEMS, [core('c', ITEMS[2]['text'])])
    assert proposal['quote'] == 'De volgende mechanismen spelen mogelijk een rol:'
    assert INTRO[proposal['start']:proposal['end']] == proposal['quote']  # literal, never rewritten
    assert proposal['block_id'] == 'a' and proposal['role'] == 'list_introduction'


def test_no_proposal_once_linked_overlapping_or_declined():
    [proposal] = proposals(ITEMS, [core('b', ITEMS[1]['text'])])
    linked = {**proposal, 'role': 'list_introduction'}
    whole_block = {'block_id': 'a', 'start': 0, 'end': len(INTRO), 'role': 'context'}
    assert proposals(ITEMS, [core('b', ITEMS[1]['text']), linked]) == []
    assert proposals(ITEMS, [core('b', ITEMS[1]['text']), whole_block]) == []
    assert proposals(ITEMS, [core('b', ITEMS[1]['text'])], declined=[proposal]) == []


@pytest.mark.parametrize('blocks', [
    [block('a', INTRO, ('Oorzaken',)), block('b', 'Bij diabetes is de huid vatbaarder.', ('Behandeling',))],
    [block('a', INTRO)] + [block(f'x{i}', f'Punt {i}.') for i in range(MAX_BETWEEN + 1)] + [block('b', 'Bij diabetes.')],
    [block('a', 'Een gewone alinea.'), block('b', 'Bij diabetes is de huid vatbaarder.')],
    [block('b', 'Bij diabetes is de huid vatbaarder.')],
])
def test_no_proposal_across_a_section_beyond_the_limit_without_a_colon_or_before_the_start(blocks):
    assert proposals(blocks, [core('b', blocks[-1]['text'])]) == []


def test_without_a_statement_nothing_is_proposed():
    assert proposals(ITEMS, []) == []


@pytest.fixture
def smetten(tmp_path, production_console):
    from src.vorming import human_annotation_v1 as annotation
    from src.vorming.source_bound_fields_v3 import FIELDS
    from tests.test_human_annotation_postgres import anchor, command

    console = production_console(root=tmp_path)
    actor = console.create_account(username='voorstel', password='human-proposal-secret',
                                   roles=('researcher', 'reviewer'))['account_id']
    sid = console.receive_source(actor_id=actor, filename='smetten.html', content_type='text/html',
        data=('<html><body><p>De volgende mechanismen spelen mogelijk een rol bij het risico op smetten:</p>'
              '<p>Bij diabetes mellitus zou de huid vatbaarder kunnen zijn voor irritatie en infecties.</p>'
              '</body></html>').encode(),
        ingest_kind='new', title='Smetten', version='1.0', date='2026-11-13', live_url='',
        class_='richtlijn', family='test', named_reviewers=[],
        review_choice={'contract': 'review-configuration-v2', 'option': 'uploader_sole',
                       'four_eyes_required': False, 'reviewers': [], 'readers': []})['snapshot_id']
    view = annotation.prepare(console, actor_id=actor, snapshot_id=sid, expected_revision=console.objects_revision(sid))
    fields = {key: {'span': None, 'missing_reason': 'uncertain'} for key in FIELDS}
    fields.update(type_evidence_spans={'core': True}, support_span={'core': True})

    def save(ranges=(), *, declined=None, status='ready', previous=None):
        request = command(view, ranges=[anchor(view, 'Bij diabetes'), *ranges], status=status)
        request['selection'].update(object_type='explanation', field_evidence=fields, required_links=[])
        if declined is not None:
            request['selection']['declined_context'] = declined
        if previous:
            request.update(annotation_id=previous['annotation_id'], expected_revision=previous['revision'],
                           expected_generation=previous['generation'])
        return request['annotation_id'], annotation.save(console, actor_id=actor, **request)

    def check(annotation_id):
        return annotation.check_current(console, actor_id=actor, snapshot_id=sid, annotation_id=annotation_id)

    intro = anchor(view, 'De volgende mechanismen', role='list_introduction')
    return annotation, save, check, intro, {'console': console, 'actor': actor, 'sid': sid}


def test_ready_is_refused_while_the_proposal_is_open_and_a_draft_shows_it(smetten):
    annotation, save, check, intro, _ = smetten
    with pytest.raises(ConsoleError) as refused:
        save()
    assert refused.value.code == 'annotation_context_proposal_open'
    annotation_id, draft = save(status='draft')
    checked = check(annotation_id)
    assert 'annotation_context_proposal_open' in checked['codes']
    [proposal] = checked['proposals']
    assert {k: proposal[k] for k in ('block_id', 'start', 'end', 'quote')} == {k: intro[k] for k in ('block_id', 'start', 'end', 'quote')}


def test_adding_the_proposal_answers_it(smetten):
    _, save, check, intro, _ = smetten
    annotation_id, result = save([intro])
    assert result['status'] == 'ready'
    assert check(annotation_id)['proposals'] == []


def test_declining_is_kept_and_answers_it_without_changing_what_is_built(smetten):
    annotation, save, check, intro, env = smetten
    declined = [{k: intro[k] for k in ('block_id', 'start', 'end', 'quote')}]
    annotation_id, result = save(declined=declined)
    assert result['status'] == 'ready'
    checked = check(annotation_id)
    assert checked['proposals'] == [] and 'annotation_context_proposal_open' not in checked['codes']
    entry = next(e for e in annotation.overview(env['console'], actor_id=env['actor'], snapshot_id=env['sid'])['entries']
                 if e['annotation_id'] == annotation_id)
    assert [row['quote'] for row in entry['declined_context']] == [intro['quote']]
    assert entry['ranges'][0]['role'] == 'core' and len(entry['ranges']) == 1


@pytest.mark.parametrize('declined', [
    [{'block_id': 'missing', 'start': 0, 'end': 3, 'quote': 'abc'}],
    [{'block_id': None, 'start': 0, 'end': 3}],
    'not a list',
])
def test_a_declined_position_must_be_exact_source(smetten, declined):
    _, save, _, _, _ = smetten
    with pytest.raises(ConsoleError) as refused:
        save(declined=declined, status='draft')
    assert refused.value.code in {'annotation_declined_context_invalid', 'annotation_anchor_invalid'}


def test_a_changed_quote_for_a_declined_position_is_refused(smetten):
    _, save, _, intro, _ = smetten
    with pytest.raises(ConsoleError) as refused:
        save(declined=[{k: intro[k] for k in ('block_id', 'start', 'end')} | {'quote': 'Iets anders'}], status='draft')
    assert refused.value.code == 'annotation_anchor_mismatch'
