"""#1067 part C: the route of a knowledge object from annotation, shown the same way on every workplace.

One line names the milestones and marks where the object is; one sentence says what happens next and who acts.
It is orientation only: it adds no step, question or button, and it derives everything from state the page
already holds. The second review appears only when it applies.
"""
from __future__ import annotations

from html import escape

from src.review.knowledge_object_state_v1 import (
    AFGEWEZEN, GEPUBLICEERD, GOEDGEKEURD, INGETROKKEN, TWEEDE_REVIEW, VERVANGEN,
)

MILESTONES = (
    ('ingest', 'Inleveren'),
    ('annotate', 'Annoteren'),
    ('check', 'Documentcontrole'),
    ('build', 'Bouwen'),
    ('review', 'Review'),
    ('second_review', 'Tweede review'),
    ('publish', 'Publicatie'),
)


def route_html(current: str, next_step: str, *, second_review: bool) -> str:
    """Render the milestones with ``current`` marked and the next step underneath."""
    shown = [(key, label) for key, label in MILESTONES if key != 'second_review' or second_review]
    keys = [key for key, _label in shown]
    if current not in keys:
        raise ValueError('unknown_route_milestone')
    position = keys.index(current)
    items = []
    for index, (key, label) in enumerate(shown):
        if index < position:
            items.append('<li data-route-done>' + label + '</li>')
        elif index == position:
            items.append('<li aria-current="step">' + label + '</li>')
        else:
            items.append('<li>' + label + '</li>')
    return ('<nav class="ko-route" aria-label="Route van het kennisobject" data-route="' + current + '">'
            '<ol>' + ''.join(items) + '</ol><p class="ko-route-next">' + escape(next_step) + '</p></nav>')


def build_is_current(entries, bindings) -> bool:
    """A successful build still describes the document: every statement is ready and built, none awaits a rebuild."""
    if any(binding.get('pending') for binding in bindings.values()):
        return False
    # Source text that is no statement (a disposition) is accounted for but never becomes an object.
    return all(entry.get('status') == 'ready' and (entry.get('disposition') or entry.get('annotation_id') in bindings)
               for entry in entries if entry.get('status') != 'withdrawn')


def annotation_route(*, overview: bool, second_review: bool, finalized: str = '') -> str:
    """The annotation card and the document check. ``finalized`` is the build state after closing, if any."""
    if finalized == 'running':
        return route_html('build', 'Hierna: Metis bouwt de kennisobjecten. Daarna gaan ze naar de review.',
                          second_review=second_review)
    if finalized == 'succeeded':
        return route_html('review', 'Hierna: de reviewer beoordeelt elk kennisobject.', second_review=second_review)
    if overview:
        return route_html('check', 'Hierna: na ‘Ik ben klaar met dit document’ bouwt Metis de kennisobjecten. '
                          'Daarna beoordeelt de reviewer ze.', second_review=second_review)
    return route_html('annotate', 'Hierna: als alle uitspraken gereed zijn, controleer je het document. '
                      'Daarna bouwt Metis de kennisobjecten.', second_review=second_review)


def review_route(state: str | None, *, stage_second: bool, required_second: bool, rebuilding: str = '') -> str:
    """The review card of a knowledge object from annotation."""
    second = required_second or stage_second or state == TWEEDE_REVIEW
    if rebuilding == 'building':
        return route_html('build', 'Hierna: de nieuwe versie komt terug in de review. Deze pagina ververst vanzelf.',
                          second_review=second)
    if rebuilding:
        return route_html('build', 'Hierna: bouw het kennisobject opnieuw in de kaart. '
                          'Tot dan kan deze versie niet worden goedgekeurd.', second_review=second)
    if state == GEPUBLICEERD:
        return route_html('publish', 'Dit kennisobject is gepubliceerd.', second_review=second)
    if state in {AFGEWEZEN, VERVANGEN, INGETROKKEN}:
        return route_html('second_review' if stage_second and second else 'review',
                          'Afgewezen: dit kennisobject wordt niet gepubliceerd. '
                          'Een correctie in de kaart maakt een nieuwe versie.', second_review=second)
    if state == GOEDGEKEURD:
        return route_html('publish', 'Hierna: het kennisobject wordt gepubliceerd met het document.',
                          second_review=second)
    if stage_second or state == TWEEDE_REVIEW:
        return route_html('second_review', 'Hierna: na goedkeuren is dit kennisobject klaar voor publicatie.',
                          second_review=True)
    if required_second:
        return route_html('review', 'Hierna: na goedkeuren beoordeelt een tweede reviewer deze versie.',
                          second_review=True)
    return route_html('review', 'Hierna: na goedkeuren is dit kennisobject klaar voor publicatie.',
                      second_review=False)
