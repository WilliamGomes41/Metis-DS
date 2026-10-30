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
