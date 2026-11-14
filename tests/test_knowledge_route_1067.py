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
