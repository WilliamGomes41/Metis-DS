"""#1067 part C: the route line tells where a knowledge object is and what happens next, from real state."""
import re

import pytest

from src.review.knowledge_object_state_v1 import AFGEWEZEN, GEPUBLICEERD, GOEDGEKEURD, IN_REVIEW, TWEEDE_REVIEW
from src.review.knowledge_route_v1 import annotation_route, review_route, route_html


def milestones(html):
    return re.findall(r'<li[^>]*>([^<]+)</li>', html)


def current(html):
    return re.search(r'<li aria-current="step">([^<]+)</li>', html).group(1)


def following(html):
    return re.search(r'<p class="ko-route-next">([^<]+)</p>', html).group(1)


def test_the_second_review_appears_only_when_it_applies():
    assert 'Tweede review' not in milestones(annotation_route(overview=False, second_review=False))
    assert milestones(annotation_route(overview=False, second_review=True)) == [
        'Inleveren', 'Annoteren', 'Documentcontrole', 'Bouwen', 'Review', 'Tweede review', 'Publicatie']


def test_earlier_milestones_are_marked_done_and_one_is_current():
    html = annotation_route(overview=True, second_review=False)
    assert current(html) == 'Documentcontrole'
    assert html.count('data-route-done') == 2 and html.count('aria-current') == 1


@pytest.mark.parametrize('kwargs,expected_current,expected_next', [
    (dict(overview=False, second_review=False), 'Annoteren', 'controleer je het document'),
    (dict(overview=True, second_review=False), 'Documentcontrole', 'bouwt Metis de kennisobjecten'),
    (dict(overview=True, second_review=False, finalized='running'), 'Bouwen', 'Daarna gaan ze naar de review'),
    (dict(overview=True, second_review=True, finalized='succeeded'), 'Review', 'de reviewer beoordeelt'),
])
def test_annotation_pages_say_what_follows(kwargs, expected_current, expected_next):
    html = annotation_route(**kwargs)
    assert current(html) == expected_current
    assert following(html).startswith('Hierna: ') and expected_next in following(html)


@pytest.mark.parametrize('state,kwargs,expected_current,expected_next', [
    (IN_REVIEW, dict(stage_second=False, required_second=False), 'Review', 'klaar voor publicatie'),
    (IN_REVIEW, dict(stage_second=False, required_second=True), 'Review', 'beoordeelt een tweede reviewer'),
    (TWEEDE_REVIEW, dict(stage_second=True, required_second=True), 'Tweede review', 'klaar voor publicatie'),
    (IN_REVIEW, dict(stage_second=False, required_second=False, rebuilding='saved'), 'Bouwen', 'bouw het kennisobject opnieuw'),
    (IN_REVIEW, dict(stage_second=False, required_second=False, rebuilding='building'), 'Bouwen', 'komt terug in de review'),
    (GOEDGEKEURD, dict(stage_second=False, required_second=False), 'Publicatie', 'gepubliceerd met het document'),
    (GEPUBLICEERD, dict(stage_second=False, required_second=False), 'Publicatie', 'is gepubliceerd'),
    (AFGEWEZEN, dict(stage_second=False, required_second=False), 'Review', 'wordt niet gepubliceerd'),
])
def test_review_card_says_what_follows_from_real_state(state, kwargs, expected_current, expected_next):
    html = review_route(state, **kwargs)
    assert current(html) == expected_current
    assert expected_next in following(html)


def test_the_line_adds_no_control():
    html = review_route(IN_REVIEW, stage_second=False, required_second=True)
    assert not re.search(r'<(button|a|input|select|form)\b', html)


def test_unknown_milestone_is_refused():
    with pytest.raises(ValueError):
        route_html('second_review', 'x', second_review=False)


def test_document_check_route_follows_the_real_build(tmp_path, production_console):
    """Black-box: before the build the check is current; after an unchanged successful build it is the review."""
    from starlette.testclient import TestClient
    from src.vorming import human_annotation_v1 as annotation
    from tests.production_support import application_for
    from tests.test_human_annotation_postgres import anchor, command
    from tests.test_human_annotation_review_postgres import execute_build
    console = production_console(root=tmp_path)
    actor = console.create_account(username='route', password='route-secret-1067',
                                   roles=('researcher', 'reviewer'))['account_id']
    sid = console.receive_source(actor_id=actor, filename='route.html', content_type='text/html',
        data=b'<html><body><p>De huid wordt dagelijks gecontroleerd.</p></body></html>',
        ingest_kind='new', title='Route', version='1.0', date='2026-11-14', live_url='',
        class_='richtlijn', family='test', named_reviewers=[],
        review_choice={'contract': 'review-configuration-v2', 'option': 'uploader_sole',
                       'four_eyes_required': False, 'reviewers': [], 'readers': []})['snapshot_id']
    view = annotation.prepare(console, actor_id=actor, snapshot_id=sid, expected_revision=console.objects_revision(sid))
    request = command(view, ranges=[anchor(view, 'De huid wordt dagelijks')], status='ready')
    from src.vorming.human_annotation_v1 import TYPE_CORE_FIELDS
    from src.vorming.source_bound_fields_v3 import FIELDS
    fields = {key: {'span': None, 'missing_reason': 'uncertain'} for key in FIELDS}
    fields.update(type_evidence_spans={'core': True}, **{TYPE_CORE_FIELDS['explanation']: {'core': True}})
    request['selection'].update(object_type='explanation', field_evidence=fields, required_links=[])
    annotation.save(console, actor_id=actor, **request)
    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username': 'route', 'password': 'route-secret-1067'})
        page = lambda: client.get('/annotations', params={'document': sid, 'overview': 'true'}).text
        assert current(page()) == 'Documentcontrole'
        execute_build(console, actor, sid)
        after = page()
        assert current(after) == 'Review' and 'de reviewer beoordeelt' in following(after)


@pytest.mark.parametrize('entries,bindings,current_build', [
    ([{'annotation_id': 'a', 'status': 'ready'}], {'a': {'pending': False}}, True),
    ([{'annotation_id': 'a', 'status': 'ready'}, {'annotation_id': 'b', 'status': 'withdrawn'}], {'a': {}}, True),
    # A new statement started after the build is unfinished document work.
    ([{'annotation_id': 'a', 'status': 'ready'}, {'annotation_id': 'b', 'status': 'draft'}], {'a': {}}, False),
    # A correction saved but not rebuilt.
    ([{'annotation_id': 'a', 'status': 'ready'}], {'a': {'pending': True}}, False),
    # A ready statement without its object.
    ([{'annotation_id': 'a', 'status': 'ready'}], {}, False),
    # Source text that is no statement never has an object, but must be ready.
    ([{'annotation_id': 'a', 'status': 'ready'}, {'annotation_id': 'h', 'status': 'ready',
      'disposition': {'role': 'structure', 'reason': 'heading'}}], {'a': {}}, True),
    ([{'annotation_id': 'a', 'status': 'ready'}, {'annotation_id': 'h', 'status': 'draft',
      'disposition': {'role': 'structure', 'reason': 'heading'}}], {'a': {}}, False),
])
def test_a_build_is_current_only_while_nothing_changed_since(entries, bindings, current_build):
    from src.review.knowledge_route_v1 import build_is_current
    assert build_is_current(entries, bindings) is current_build


def test_review_card_route_shows_the_four_eyes_review_chosen_at_intake(production_console, tmp_path):
    """Black-box: with four-eyes chosen at intake the first reviewer sees the second review coming."""
    from starlette.testclient import TestClient
    from tests.production_support import application_for
    from tests.test_second_review_reject_1064 import four_eyes
    console, _, sid, _, first, _, oid, _ = four_eyes(production_console, tmp_path)
    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username': console._account(first)['username'], 'password': 'human-build-secret'})
        page = client.get('/review', params={'document': sid, 'object': oid}).text
    assert 'Tweede review' in milestones(page) and current(page) == 'Review'
    assert 'beoordeelt een tweede reviewer' in following(page)
