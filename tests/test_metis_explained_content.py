"""Traceability and URL integrity for the read-only explanation collection.

# release-control-evidence: scope/belofte kwaliteit slop releasebewijs
"""
from pathlib import Path
from html import escape
from html.parser import HTMLParser

import pytest

from src.settings.metis_explained_content import MODELS, SECTIONS
from src.settings.metis_dictionary_ui import render, search


pytestmark = pytest.mark.pure_function
ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        href = attributes.get("href", "")
        if tag == "a" and href.startswith("#"):
            self.anchors.append(href[1:])


def test_content_references_and_bookmark_targets_are_complete():
    glossary = Links()
    glossary.feed(render(escape, section="begrippen"))
    assert len(glossary.ids) == len(set(glossary.ids))
    assert set(glossary.anchors) <= set(glossary.ids)
    term_ids = {term.id for category in SECTIONS for term in category.terms}
    assert len(term_ids) == sum(len(category.terms) for category in SECTIONS)
    assert len({model.id for model in MODELS}) == len(MODELS)
    for model in MODELS:
        assert set(model.term_ids) <= term_ids
        assert all((ROOT / reference.path).is_file() for reference in model.references)
        page = Links()
        page.feed(render(escape, section="modellen", model_id=model.id))
        assert len(page.ids) == len(set(page.ids))
        assert set(page.anchors) <= set(page.ids)


def test_search_uses_aliases_and_requires_all_words_without_interpreting_html():
    assert any(hit.title == "Referentieset" for hit in search("GOLD standard"))
    assert any(hit.title == "AI-model" for hit in search("taalmodel"))
    assert any(hit.kind == "Model" for hit in search("uitzondering"))
    assert search("brontrouw zzzonbestaand") == ()
    assert search("  ") == ()
    assert search("<script>") == ()


def test_the_knowledge_object_is_defined_first_and_matches_the_current_way_of_working():
    """#1066: the explanation follows the code: one card per statement, documentcontrole, build, review in the card."""
    first = SECTIONS[0]
    assert first.id == 'het-kennisobject'
    terms = {term.id: term for term in first.terms}
    assert list(terms)[0] == 'kennisstuk-kennisobject'
    definition = terms['kennisstuk-kennisobject'].definition
    for part in ('uitspraak', 'letterlijk', 'onderbouwing', 'vindplaats', 'versie'):
        assert part in definition
    from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES
    from src.operations_console_app import OBJECT_TYPE_LABELS
    kinds = terms['voorgesteld-en-bevestigd-type'].definition.casefold()
    assert all(OBJECT_TYPE_LABELS[kind].casefold() in kinds for kind in CLOSED_OBJECT_TYPES if kind != 'heading')
    from src.review.knowledge_object_state_v1 import KO_STATES
    states = terms['status-van-een-kennisobject'].definition
    assert all(state in states for state in KO_STATES if state != 'Samengesteld')
    everything = ' '.join(t.definition + ' ' + t.example for c in SECTIONS for t in c.terms)
    assert 'terugstuurt' not in everything and 'stuurt het voorstel terug' not in everything
    start = render(escape, section='start')
    assert start.index('Het kennisobject: de bouwsteen van Metis') < start.index('Van bron naar bruikbare kennis')
