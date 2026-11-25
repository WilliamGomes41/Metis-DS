"""#1067 part A (Class A): the worker never sets direction or strength; the reviewer confirms or corrects them.

Black-box scenario of docs/change-contracts/slice5-reviewer-recommendation-semantics.md on native PostgreSQL.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import re

import pytest
from starlette.testclient import TestClient

from src.vorming.recommendation_semantics_v1 import complete_annotation_semantics
from tests.production_support import application_for

STATEMENT = 'Gebruik geen talkpoeder in huidplooien. Zwak – tegen'


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


def prepared_recommendation(console, *, explicitly_proposed, second_required=False):
    from src.vorming import human_annotation_v1 as annotation
    from src.vorming.admission_gate_v1 import admission_of
    from src.vorming.source_bound_fields_v3 import FIELDS
    from tests.test_human_annotation_postgres import anchor, command
    from tests.test_human_annotation_review_postgres import candidate, execute_build

    actor = console.create_account(username='richting', password='human-semantics-secret',
                                   roles=('researcher', 'reviewer'))['account_id']
    second = (console.create_account(username='tweede', password='human-semantics-secret', roles=('reviewer',))['account_id']
              if second_required else None)
    sid = console.receive_source(actor_id=actor, filename='talk.html', content_type='text/html',
        data=('<html><body><p>' + STATEMENT + '</p></body></html>').encode(),
        ingest_kind='new', title='Huidplooien', version='1.0', date='2026-11-13', live_url='',
        class_='richtlijn', family='test', named_reviewers=[], source_status='established',
        review_choice={'contract': 'review-configuration-v2',
                       'option': 'uploader_and_other' if second_required else 'uploader_sole',
                       'four_eyes_required': second_required, 'reviewers': [second] if second_required else [],
                       'readers': []})['snapshot_id']
    view = annotation.prepare(console, actor_id=actor, snapshot_id=sid, expected_revision=console.objects_revision(sid))
    core = anchor(view, STATEMENT)
    fields = {key: {'span': None, 'missing_reason': 'uncertain'} for key in FIELDS}
    fields.update(type_evidence_spans={'core': True}, recommendation_evidence_span={'core': True})
    request = command(view, ranges=[core], status='ready')
    def witness(start, end):
        return {'span': {'block_id': core['block_id'], 'start': start, 'end': end},
                'quote': STATEMENT[start:end]}
    proposal = {'direction': 'against',
                'direction_evidence': witness(0, len('Gebruik geen talkpoeder')),
                'strength': 'weak', 'strength_status': 'explicit',
                'strength_evidence': witness(STATEMENT.index('Zwak'), len(STATEMENT))}
    request['selection'].update(object_type='recommendation', field_evidence=fields,
                                recommendation_semantics=proposal if explicitly_proposed else None)
    annotation.save(console, actor_id=actor, **request)
    checked = annotation.check_current(console, actor_id=actor, snapshot_id=sid, annotation_id=request['annotation_id'])
    assert checked['codes'] == []
    assert ('recommendation_semantics_open' in checked['signals']) is not explicitly_proposed
    execute_build(console, actor, sid)
    obj = candidate(console, sid)
    assert admission_of(obj)['gate_result'] == 'allowed'
    assert bool(obj.get('proposed_recommendation_semantics')) is explicitly_proposed
    return sid, obj, second, request


@pytest.mark.parametrize('outcome', ['skip', 'skip_with_proposal', 'decline', 'decline_with_choice', 'accept'])
def test_recommendation_review_choice_is_explicit_and_durable(tmp_path, production_console, outcome):
    from tests.test_human_annotation_review_postgres import candidate
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore

    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    explicitly_proposed = outcome in {'skip_with_proposal', 'decline', 'decline_with_choice', 'accept'}
    sid, obj, second, _ = prepared_recommendation(console, explicitly_proposed=explicitly_proposed,
                                               second_required=outcome == 'skip_with_proposal')
    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username': 'richting', 'password': 'human-semantics-secret'})
        page = client.get('/review', params={'document': sid, 'object': obj['object_id']}).text
        assert 'data-ko-semantics-choice' in page
        assert ('Voorstel van Metis: Afraden · Zwak' in page) is explicitly_proposed
        assert '<select name="recommendation_direction">' in page
        assert '<option value="skip" selected>Overslaan</option>' in page
        assert '<option value="against" selected>' not in page
        assert re.search(r'<button class="ko-primary" type="submit" name="review_action" value="approve">', page)
        assert 'Richting en sterkte van deze aanbeveling' not in page  # no extra signal line on the card
        form = page[page.index('<form method="post" action="/review"'):]
        form = form[:form.index('</form>')]
        data = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form))
        data.update(applicable='yes', complete='yes', placed_correctly='yes', evidence_not_applicable='yes',
                    review_action='approve')
        from tests.test_review_command_bounded_http_v1 import physical_state
        before = physical_state(console, sid)
        token = data['recommendation_proposal_token']
        assert bool(token) is explicitly_proposed
        if outcome == 'accept':
            console.create_account(username='onbevoegd', password='fixture-only', roles=('reviewer',))
            with TestClient(application_for(console)) as outsider:
                outsider.post('/login', data={'username': 'onbevoegd', 'password': 'fixture-only'})
                forbidden = outsider.post('/review', data={**data, 'recommendation_review_action': 'accept'},
                                          follow_redirects=False)
            assert forbidden.status_code in {400, 403, 404}
            assert physical_state(console, sid) == before
        if explicitly_proposed:
            stale = client.post('/review', data={**data, 'recommendation_review_action': 'accept',
                                'recommendation_proposal_token': '0' * 64}, follow_redirects=False)
            assert stale.status_code == 400
            assert 'Het voorstel komt niet meer overeen' in stale.text
            assert physical_state(console, sid) == before
        # A half choice or contradicted evidence cannot create an approval.
        half = client.post('/review', data={**data, 'recommendation_review_action': 'decline',
                           'recommendation_direction': 'against',
                           'recommendation_strength_level': ''}, follow_redirects=False)
        assert half.status_code == 400
        assert 'Kies richting én sterkte of laat beide velden leeg.' in half.text
        assert physical_state(console, sid) == before
        # A choice the source does not carry is refused, and nothing changes.
        refused = client.post('/review', data={**data, 'recommendation_review_action': 'decline',
                              'recommendation_direction': 'against',
                              'recommendation_strength_level': 'strong'}, follow_redirects=False)
        assert refused.status_code == 400
        assert 'Metis herkent in de bron geen expliciete aanduiding die je keuze Sterk of Zwak ondersteunt' in refused.text
        assert physical_state(console, sid) == before
        for wrong_direction, strength, message in [
            ('against', 'not_stated', 'De bron bevat wel een expliciete sterkteaanduiding'),
            ('for', 'weak', 'De gekozen richting spreekt het expliciete bronlabel tegen'),
        ]:
            contradiction = client.post('/review', data={**data, 'recommendation_review_action': 'decline',
                'recommendation_direction': wrong_direction, 'recommendation_strength_level': strength},
                follow_redirects=False)
            assert contradiction.status_code == 400
            assert message in contradiction.text
            assert physical_state(console, sid) == before
        if outcome == 'decline_with_choice':
            data.update(recommendation_review_action='decline', recommendation_direction='against',
                        recommendation_strength_level='weak')
        elif outcome in {'decline', 'accept'}:
            data['recommendation_review_action'] = outcome
        approved = client.post('/review', data=data, follow_redirects=False)
        assert approved.status_code == 303, approved.text
        repeated = client.post('/review', data=data, follow_redirects=False)
        assert repeated.status_code == 409
        if second:
            client.post('/login', data={'username': 'tweede', 'password': 'human-semantics-secret'})
            second_page = client.get('/review', params={'document': sid, 'object': obj['object_id']}).text
            assert 'Onafhankelijke tweede review' in second_page
            assert 'Richting en sterkte onbevestigd.' in second_page
            assert 'data-ko-semantics-choice' not in second_page
            second_form = second_page.split('<form method="post" action="/review/second-review"', 1)[1].split('</form>', 1)[0]
            second_data = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', second_form))
            approved_second = client.post('/review/second-review', data={**second_data, 'applicable': 'yes',
                'complete': 'yes', 'placed_correctly': 'yes', 'review_action': 'approve',
                'evidence_not_applicable': 'yes'}, follow_redirects=False)
            assert approved_second.status_code == 303, approved_second.text
    from tests.production_support import restart_production
    console = restart_production(console)
    result = candidate(console, sid)
    has_confirmation = outcome in {'accept', 'decline_with_choice'}
    semantics = result.get('confirmed_recommendation_semantics')
    assert bool(semantics) is has_confirmation
    if has_confirmation:
        assert semantics['direction'] == 'against' and semantics['strength'] == 'weak'
    assert result['governance']['validation_status'] == 'approved'
    events = console.workflow_review_store.read_review_command_events(
        sid, [], interaction_id=data['interaction_id'], include_pending=False)
    event, = [row for row in events if row['event_type'].endswith('_review_approve')]
    assert event['details']['recommendation_review'] == {
        'outcome': outcome.split('_', 1)[0],
        'proposal_available': explicitly_proposed, 'proposal_token': token or None,
        'own_choice': outcome == 'decline_with_choice'}
    from src.review.review_interaction_v1 import review_burden_projection
    metric = review_burden_projection([*events, event], snapshot_id=sid)['recommendation_proposal_decisions']
    assert metric == {action: int(explicitly_proposed and action == outcome.split('_', 1)[0])
                      for action in ('accept', 'decline', 'skip')}
    if outcome in {'skip', 'skip_with_proposal', 'accept'}:
        publisher = console.create_account(username='publisher', password='fixture-only', roles=('publisher',))
        published = console.publish(actor_id=publisher['account_id'], snapshot_id=sid)
        assert published.get('release_id'), published
        from src.product_api_v1 import create_product_app
        from tests.test_product_api_v1 import paths, registry, headers
        console = restart_production(console)
        public = TestClient(create_product_app('real', paths=paths(tmp_path), tenant_registry=registry(docs=('*',)),
            canonical_publication_store=console.canonical_publication_store,
            immutable_source_store=console.immutable_source_store))
        response = public.get('/v1/knowledge/' + result['object_id'], headers=headers())
        assert response.status_code == 200, response.text
        retrieved = public.post('/v1/retrieve', headers=headers(),
            json={'query': 'Gebruik geen talkpoeder in huidplooien.'})
        assert retrieved.status_code == 200, retrieved.text
        retrieved_row, = [row for row in retrieved.json()['results']
                          if row['knowledge_object_id'] == result['object_id']]
        for payload in (response.json(), retrieved_row):
            assert ('recommendation_semantics' in payload) is has_confirmation
            assert ('Zwak – tegen' in payload['content']) is has_confirmation


def test_rebuilt_recommendation_retains_only_confirmation_still_bound_to_its_source(tmp_path, production_console):
    from src.vorming import human_annotation_v1 as annotation
    from src.vorming.recommendation_semantics_v1 import annotation_review_proposal, CONFIRMED_FIELD
    from tests.ko_review_fixture_support import affirmative_assessment
    from tests.test_human_annotation_review_postgres import candidate, correction_request, execute_build
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore

    console = production_console(root=tmp_path, immutable_source_store=MemorySourceStore())
    sid, obj, _, original = prepared_recommendation(console, explicitly_proposed=True)
    actor = console._envelope(sid)['uploader_account_id']
    console.review_object(actor_id=actor, snapshot_id=sid, object_id=obj['object_id'],
        decision='approve', confirmed_object_type='recommendation',
        recommendation_review_action='accept', recommendation_proposal_token=annotation_review_proposal(obj)[0],
        assessment=affirmative_assessment(), evidence_not_applicable=True)
    prior = candidate(console, sid)
    confirmation = prior[CONFIRMED_FIELD]
    correction = correction_request(console, sid, original)
    core = correction['selection']['ranges'][0]
    context_start = STATEMENT.index('huidplooien')
    label_start = STATEMENT.index('Zwak')
    correction['selection']['ranges'].append({**core, 'role': 'context', 'start': context_start,
        'end': label_start - 1, 'quote': STATEMENT[context_start:label_start - 1]})
    annotation.save(console, actor_id=actor, **correction)
    execute_build(console, actor, sid)
    successor = candidate(console, sid)
    assert successor['object_version'] != prior['object_version']
    assert successor[CONFIRMED_FIELD] == confirmation
    assert not any(row['valid'] for row in console.object_review_bindings(sid))
    console.review_object(actor_id=actor, snapshot_id=sid, object_id=successor['object_id'],
        decision='approve', confirmed_object_type='recommendation', recommendation_review_action='skip',
        assessment=affirmative_assessment(), evidence_not_applicable=True)
    assert candidate(console, sid)[CONFIRMED_FIELD] == confirmation

    changed = correction_request(console, sid, correction)
    changed['selection']['recommendation_semantics'] = None
    core = changed['selection']['ranges'][0]
    original_end = core['end']
    core.update(end=label_start - 1, quote=STATEMENT[:label_start - 1])
    changed['selection']['ranges'].append({**core, 'role': 'context', 'start': label_start,
        'end': original_end, 'quote': STATEMENT[label_start:]})
    annotation.save(console, actor_id=actor, **changed)
    execute_build(console, actor, sid)
    new_object = candidate(console, sid)
    assert new_object['object_version'] != successor['object_version']
    assert CONFIRMED_FIELD not in new_object
    assert not any(row['valid'] for row in console.object_review_bindings(sid))
    historical = console.workflow_document_store.list_document_objects(sid)
    assert next(row for row in historical if row['object_id'] == prior['object_id']
                and row['object_version'] == prior['object_version'])[CONFIRMED_FIELD] == confirmation
