"""#1067 part A (Class A): the worker never sets direction or strength; the reviewer confirms or corrects them.

Black-box scenario of docs/change-contracts/slice5-reviewer-recommendation-semantics.md on native PostgreSQL.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import re

import pytest
from starlette.testclient import TestClient

from src.vorming.recommendation_semantics_v1 import complete_annotation_semantics
from tests.production_support import application_for

STATEMENT = 'Zwakke aanbeveling: gebruik geen talkpoeder in huidplooien.'


@pytest.mark.parametrize('raw,complete', [
    (None, False),
    ({'direction': None, 'direction_evidence': None, 'strength_status': None, 'strength': None, 'strength_evidence': None}, False),
    ({'direction': 'against', 'direction_evidence': {'block_id': 'b', 'start': 0, 'end': 3}, 'strength_status': 'unmapped',
      'strength': None, 'strength_evidence': None}, False),
    ({'direction': 'against', 'direction_evidence': {'block_id': 'b', 'start': 0, 'end': 3}, 'strength_status': 'explicit',
      'strength': 'weak', 'strength_evidence': None}, False),
    ({'direction': 'against', 'direction_evidence': {'block_id': 'b', 'start': 0, 'end': 3}, 'strength_status': 'not_stated',
      'strength': None, 'strength_evidence': None}, True),
    ({'direction': 'for', 'direction_evidence': {'block_id': 'b', 'start': 0, 'end': 3}, 'strength_status': 'explicit',
      'strength': 'weak', 'strength_evidence': {'block_id': 'b', 'start': 0, 'end': 3}}, True),
])
def test_only_a_complete_proposal_travels_with_the_annotation(raw, complete):
    assert complete_annotation_semantics(raw) is complete


def test_recommendation_without_direction_and_strength_reaches_review_and_the_reviewer_sets_them(tmp_path, production_console):
    from src.vorming import human_annotation_v1 as annotation
    from src.vorming.admission_gate_v1 import admission_of
    from src.vorming.source_bound_fields_v3 import FIELDS
    from tests.test_human_annotation_postgres import anchor, command
    from tests.test_human_annotation_review_postgres import candidate, execute_build
    from tests.test_human_annotation_build_postgres import closing  # noqa: F401  (same build helpers)

    console = production_console(root=tmp_path)
    actor = console.create_account(username='richting', password='human-semantics-secret',
                                   roles=('researcher', 'reviewer'))['account_id']
    sid = console.receive_source(actor_id=actor, filename='talk.html', content_type='text/html',
        data=('<html><body><p>' + STATEMENT + '</p></body></html>').encode(),
        ingest_kind='new', title='Huidplooien', version='1.0', date='2026-11-13', live_url='',
        class_='richtlijn', family='test', named_reviewers=[],
        review_choice={'contract': 'review-configuration-v2', 'option': 'uploader_sole',
                       'four_eyes_required': False, 'reviewers': [], 'readers': []})['snapshot_id']
    view = annotation.prepare(console, actor_id=actor, snapshot_id=sid, expected_revision=console.objects_revision(sid))
    core = anchor(view, 'Zwakke aanbeveling')
    fields = {key: {'span': None, 'missing_reason': 'uncertain'} for key in FIELDS}
    fields.update(type_evidence_spans={'core': True}, recommendation_evidence_span={'core': True})
    request = command(view, ranges=[core], status='ready')
    request['selection'].update(object_type='recommendation', field_evidence=fields, required_links=[],
                                recommendation_semantics=None)
    # The worker sets nothing about direction or strength, and that does not stop the annotation.
    annotation.save(console, actor_id=actor, **request)
    checked = annotation.check_current(console, actor_id=actor, snapshot_id=sid, annotation_id=request['annotation_id'])
    assert checked['codes'] == [] and 'recommendation_semantics_open' in checked['signals']

    execute_build(console, actor, sid)
    obj = candidate(console, sid)
    admission = admission_of(obj)
    assert admission['gate_result'] == 'allowed' and 'recommendation_semantics_open' in admission['signals']
    assert not obj.get('proposed_recommendation_semantics')

    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username': 'richting', 'password': 'human-semantics-secret'})
        page = client.get('/review', params={'document': sid, 'object': obj['object_id']}).text
        assert 'data-ko-semantics-choice' in page and 'Metis kon dit niet vaststellen.' in page
        assert re.search(r'<button class="ko-primary" type="submit" name="review_action" value="approve">', page)
        assert 'Richting en sterkte van deze aanbeveling' not in page  # no extra signal line on the card
        form = page[page.index('<form method="post" action="/review"'):]
        form = form[:form.index('</form>')]
        data = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form))
        data.update(applicable='yes', complete='yes', placed_correctly='yes', evidence_not_applicable='yes',
                    review_action='approve')
        # A choice the source does not carry is refused, and nothing changes.
        before = candidate(console, sid)
        refused = client.post('/review', data={**data, 'recommendation_direction': 'against',
                              'recommendation_strength_level': 'strong'}, follow_redirects=False)
        assert refused.status_code == 400
        assert 'Metis herkent in de bron geen expliciete aanduiding die je keuze Sterk of Zwak ondersteunt' in refused.text
        assert candidate(console, sid) == before
        approved = client.post('/review', data={**data, 'recommendation_direction': 'against',
                               'recommendation_strength_level': 'weak'}, follow_redirects=False)
        assert approved.status_code == 303, approved.text
    result = candidate(console, sid)
    semantics = result['confirmed_recommendation_semantics']
    assert semantics['direction'] == 'against' and semantics['strength'] == 'weak'
    assert result['governance']['validation_status'] == 'approved'
