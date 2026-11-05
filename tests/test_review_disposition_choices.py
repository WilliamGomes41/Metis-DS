"""The review form only offers final judgements that fit the chosen suitability.

A conflicting combination that still reaches the server (old form, no
JavaScript, crafted request) is refused as before, and the error page names
the combination and the judgements that do fit. Expected sets and copy are
literal, so a drift of the rule or of the rendering fails here.

# release-control-evidence: scope/belofte
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

OFFERED = {
    "ja": {"goedkeuren", "goedkeuren_na_correctie", "afwijzen", "later_beoordelen"},
    "mist_context": {"goedkeuren_na_correctie", "afwijzen", "later_beoordelen"},
    "samenvoegen": {"goedkeuren_na_correctie", "afwijzen", "later_beoordelen"},
    "alleen_onderbouwing": {"goedkeuren", "goedkeuren_na_correctie", "afwijzen", "later_beoordelen"},
    "geen_kenniseenheid": {"afwijzen", "later_beoordelen"},
}

SCOPE_NOTE = {
    "ja": "Bij ‘Ja, als zelfstandig stukje kennis’ kun je kiezen uit ‘Goedkeuren’, "
          "‘Correctie specificeren’, ‘Afwijzen’ of ‘Later beoordelen’.",
    "mist_context": "Bij ‘Nee, ik mis uitleg eromheen’ kun je kiezen uit "
                    "‘Correctie specificeren’, ‘Afwijzen’ of ‘Later beoordelen’.",
    "samenvoegen": "Bij ‘Nee, deze hoort samen met een andere passage’ kun je kiezen uit "
                   "‘Correctie specificeren’, ‘Afwijzen’ of ‘Later beoordelen’.",
    "alleen_onderbouwing": "Bij ‘Alleen als onderbouwing van een andere passage’ kun je kiezen uit "
                           "‘Goedkeuren’, ‘Correctie specificeren’, ‘Afwijzen’ of ‘Later beoordelen’.",
    "geen_kenniseenheid": "Bij ‘Geen zelfstandig stukje kennis’ kun je kiezen uit "
                          "‘Afwijzen’ of ‘Later beoordelen’.",
}


class _Form(HTMLParser):
    """Collect each final-judgement radio with the suitabilities it is offered for."""

    def __init__(self):
        super().__init__()
        self.allowed_for = {}
        self.notes = {}
        self.legends = []
        self._label = None
        self._note = None
        self._legend = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "label" and "data-allowed-for" in attrs:
            self._label = attrs["data-allowed-for"].split()
        if tag == "input" and attrs.get("name") == "eindoordeel":
            self.allowed_for[attrs["value"]] = self._label
        if "data-decision-scope" in attrs:
            self._note = attrs["data-decision-scope"]
            self.notes[self._note] = ""
        if tag == "legend":
            self._legend = ""

    def handle_endtag(self, tag):
        if tag == "label":
            self._label = None
        if tag == "span" and self._note is not None:
            self._note = None
        if tag == "legend" and self._legend is not None:
            self.legends.append(" ".join(self._legend.split()))
            self._legend = None

    def handle_data(self, data):
        if self._note is not None:
            self.notes[self._note] += data
        if self._legend is not None:
            self._legend += data


def _rendered_form(client, sid, oid):
    page = client.get("/review", params={"document": sid, "object": oid})
    assert page.status_code == 200
    form = _Form()
    form.feed(page.text)
    return form


@pytest.mark.parametrize("suitability", sorted(OFFERED))
def test_form_offers_only_final_judgements_that_fit_the_suitability(review_system, suitability):
    _console, client, sid, _actor, ids = review_system
    form = _rendered_form(client, sid, ids[0])
    offered = {value for value, scope in form.allowed_for.items() if scope and suitability in scope}
    assert offered == OFFERED[suitability]
    assert " ".join(form.notes[suitability].split()) == SCOPE_NOTE[suitability]


def test_both_questions_are_named_groups(review_system):
    _console, client, sid, _actor, ids = review_system
    form = _rendered_form(client, sid, ids[0])
    assert "Is deze passage op zichzelf bruikbaar?" in form.legends
    assert "Wat is je besluit?" in form.legends
    assert set(form.allowed_for) == {"goedkeuren", "goedkeuren_na_correctie", "afwijzen", "later_beoordelen"}


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

