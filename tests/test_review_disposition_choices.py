"""Compact review answers and existing legacy disposition rules remain explicit.

The new card submits three native answer groups. A crafted approval with an
adjustment is refused without writes. Existing legacy/raw HTTP disposition
conflicts and closed-field behavior remain covered independently.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang no route or auth change; the conflict copy renders only after sign-in and reviewer checks (test_authorization_still_precedes_the_disposition_rule)
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from html.parser import HTMLParser
import re

import pytest

from tests.test_review_disposition_precheck import (
    _legacy_review_window,
    _review_event_count,
    _review_form,
)
from tests.test_v233_review_audit_regressions import review_system  # noqa: F401  (fixture)

CONFLICT = "review_disposition_conflict"


class _Form(HTMLParser):
    def __init__(self):
        super().__init__()
        self.answers = {}
        self.legends = []
        self._legend = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('type') == 'radio':
            self.answers.setdefault(attrs['name'], []).append(attrs['value'])
        if tag == 'legend':
            self._legend = ''

    def handle_endtag(self, tag):
        if tag == 'legend' and self._legend is not None:
            self.legends.append(' '.join(self._legend.split()))
            self._legend = None

    def handle_data(self, data):
        if self._legend is not None:
            self._legend += data


def _rendered_form(client, sid, oid):
    page = client.get("/review", params={"document": sid, "object": oid})
    assert page.status_code == 200
    form = _Form()
    form.feed(page.text)
    return form


@pytest.mark.parametrize('answer', ['applicable', 'complete', 'placed_correctly'])
def test_compact_approval_refuses_each_adjustment_without_writing(review_system, answer):
    from tests.test_ko_new_pages import compact_submission
    from tests.test_review_command_bounded_http_v1 import physical_state
    console, client, sid, _actor, ids = review_system
    page = client.get('/review', params={'document': sid, 'object': ids[0]})
    before = physical_state(console, sid)
    response = client.post('/review', data={**compact_submission(page), answer: 'adjust'}, follow_redirects=False)
    assert response.status_code == 400
    assert physical_state(console, sid) == before
    assert 'data-review-receipt' not in response.text


def test_three_questions_are_named_native_groups(review_system):
    _console, client, sid, _actor, ids = review_system
    form = _rendered_form(client, sid, ids[0])
    assert form.legends == ['Is dit toepasbaar?', 'Is dit compleet?', 'Staat dit op de juiste plek?']
    assert form.answers == {name: ['yes', 'adjust']
                            for name in ('applicable', 'complete', 'placed_correctly')}


CONFLICT_COPY = {
    ("mist_context", "goedkeuren"):
        "Je koos ‘Nee, ik mis uitleg eromheen’ met het besluit ‘Goedkeuren’. Die combinatie kan niet. "
        "Bij ‘Nee, ik mis uitleg eromheen’ kun je kiezen uit ‘Correctie specificeren’, ‘Afwijzen’ of "
        "‘Later beoordelen’. Je beoordeling is niet opgeslagen. Ga terug naar de passage en kies een "
        "besluit dat past.",
    ("samenvoegen", "goedkeuren"):
        "Je koos ‘Nee, deze hoort samen met een andere passage’ met het besluit ‘Goedkeuren’. Die "
        "combinatie kan niet. Bij ‘Nee, deze hoort samen met een andere passage’ kun je kiezen uit "
        "‘Correctie specificeren’, ‘Afwijzen’ of ‘Later beoordelen’. Je beoordeling is niet "
        "opgeslagen. Ga terug naar de passage en kies een besluit dat past.",
    ("geen_kenniseenheid", "goedkeuren"):
        "Je koos ‘Geen zelfstandig stukje kennis’ met het besluit ‘Goedkeuren’. Die combinatie kan "
        "niet. Bij ‘Geen zelfstandig stukje kennis’ kun je kiezen uit ‘Afwijzen’ of ‘Later "
        "beoordelen’. Je beoordeling is niet opgeslagen. Ga terug naar de passage en kies een "
        "besluit dat past.",
}


@pytest.mark.parametrize("legacy", [False, True], ids=["prepared", "serial"])
@pytest.mark.parametrize(("suitability", "eindoordeel"), sorted(CONFLICT_COPY))
def test_conflicting_post_explains_the_combination(review_system, monkeypatch, suitability,
                                                   eindoordeel, legacy):
    console, client, sid, _actor, ids = review_system
    if legacy:
        _legacy_review_window(monkeypatch, console)
    data = _review_form(client, sid, ids[0], suitability=suitability, eindoordeel=eindoordeel,
                        decision="", comment="")
    before = _review_event_count(console)
    response = client.post("/review", data=data, follow_redirects=False)
    assert response.status_code == 400, response.text[:300]
    banner = re.search(r'<div class="banner err" data-error-code="([^"]+)"[^>]*>(.*?)</div>',
                       response.text, re.S)
    assert banner.group(1) == CONFLICT
    assert " ".join(banner.group(2).split()) == CONFLICT_COPY[(suitability, eindoordeel)]
    assert _review_event_count(console) == before


@pytest.mark.parametrize("approval", [None, " disabled"])
def test_help_text_never_names_an_approval_the_form_cannot_offer(approval):
    from src.review.review_disposition_choices_ui_v1 import decision_choices_html

    html = decision_choices_html("obj-1", "", approval=approval)
    scope = re.search(r'<span data-decision-scope="ja">([^<]*)</span>', html).group(1)
    assert scope == ("Bij ‘Ja, als zelfstandig stukje kennis’ kun je kiezen uit "
                     "‘Correctie specificeren’, ‘Afwijzen’ of ‘Later beoordelen’.")


def test_help_text_names_approval_when_it_can_be_selected():
    from src.review.review_disposition_choices_ui_v1 import decision_choices_html

    html = decision_choices_html("obj-1", "", approval="")
    scope = re.search(r'<span data-decision-scope="ja">([^<]*)</span>', html).group(1)
    assert scope == ("Bij ‘Ja, als zelfstandig stukje kennis’ kun je kiezen uit ‘Goedkeuren’, "
                     "‘Correctie specificeren’, ‘Afwijzen’ of ‘Later beoordelen’.")


def test_follow_up_repairs_are_separate_from_compact_confirmation(review_system):
    _console, client, sid, _actor, ids = review_system
    page = client.get('/review', params={'document': sid, 'object': ids[0]})
    form = re.search(r'<form[^>]*data-ko-assessment-form[^>]*>.*?</form>', page.text, re.S)
    assert form
    for field in ('confirmed_object_type', 'documentpositie_action', 'recommendation_strength_level', 'relation_choice', 'eindoordeel'):
        assert 'name="' + field + '"' not in form.group()
    assert 'Correctie nodig' in form.group() and '/source-selection?' in form.group()
    assert 'class="ko-adjustment"' in form.group()


def _current(console, sid, oid):
    return next(row for row in console.snapshot_objects(sid) if row["object_id"] == oid)


@pytest.mark.parametrize("legacy", [False, True], ids=["prepared", "serial"])
def test_no_knowledge_rejection_ignores_stale_follow_up_answers(review_system, monkeypatch, legacy):
    console, client, sid, _actor, ids = review_system
    if legacy:
        _legacy_review_window(monkeypatch, console)
    data = _review_form(client, sid, ids[0], suitability="geen_kenniseenheid",
                        eindoordeel="afwijzen", decision="", comment="Literatuurvoorwaarde, geen kennis",
                        source_discrepancy=["context_ontbreekt"])
    response = client.post("/review", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text[:300]
    passage = (_current(console, sid, ids[0]).get("metadata") or {}).get("review_passage") or {}
    assert passage.get("suitability") == "geen_kenniseenheid"
    assert passage.get("type_action") == ""
    assert passage.get("documentpositie_action") == ""
    from src.review.source_discrepancy_v1 import DETAILS_KEY
    assert DETAILS_KEY not in (_current(console, sid, ids[0]).get("metadata") or {})


def test_no_knowledge_with_correction_is_refused_with_the_explanation(review_system):
    console, client, sid, _actor, ids = review_system
    data = _review_form(client, sid, ids[0], suitability="geen_kenniseenheid",
                        eindoordeel="goedkeuren_na_correctie", decision="", comment="c")
    before = _review_event_count(console)
    response = client.post("/review", data=data, follow_redirects=False)
    assert response.status_code == 400, response.text[:300]
    banner = re.search(r'<div class="banner err" data-error-code="([^"]+)"[^>]*>(.*?)</div>',
                       response.text, re.S)
    assert banner.group(1) == CONFLICT
    assert " ".join(banner.group(2).split()) == (
        "Je koos ‘Geen zelfstandig stukje kennis’ met het besluit ‘Correctie specificeren’. Die "
        "combinatie kan niet. Bij ‘Geen zelfstandig stukje kennis’ kun je kiezen uit ‘Afwijzen’ of "
        "‘Later beoordelen’. Je beoordeling is niet opgeslagen. Ga terug naar de passage en kies een "
        "besluit dat past.")
    assert _review_event_count(console) == before


@pytest.mark.parametrize("legacy", [False, True], ids=["prepared", "serial"])
def test_no_knowledge_deferral_ignores_a_stale_discrepancy(review_system, monkeypatch, legacy):
    # Without JavaScript a discrepancy ticked before choosing "no knowledge unit" is still posted.
    console, client, sid, _actor, ids = review_system
    if legacy:
        _legacy_review_window(monkeypatch, console)
    data = _review_form(client, sid, ids[0], suitability="geen_kenniseenheid",
                        eindoordeel="later_beoordelen", decision="", comment="",
                        source_discrepancy=["context_ontbreekt"])
    response = client.post("/review", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text[:300]
