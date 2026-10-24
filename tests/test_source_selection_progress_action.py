"""Bronselectie: 'Voortgang bekijken' only appears where it changes what is shown.

The page already reloads the selected running document every five seconds, so a
link to that same page only reloads it. A running document that is not selected
keeps the link: it selects that document and starts polling it.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from fastapi.testclient import TestClient

import src.source_selection_ui_v1 as ui
from src.operations_console_app import COOKIE
from tests.test_recoverable_formation_v1 import FIRST, SECOND, system


def test_progress_link_only_for_running_documents_that_are_not_selected(tmp_path, monkeypatch, *, production_app, production_console):
    console, first, author, reviewer, *_ = system(tmp_path, production_console=production_console)
    second = console.ingest(actor_id=author, filename='second.html',
        data=f'<html><body><p>{FIRST}</p><p>{SECOND}</p></body></html>'.encode(), content_type='text/html',
        ingest_kind='new', title='Tweede', version='1.0', date='2026-10-05', live_url='', class_='richtlijn',
        family='second', named_reviewers=[reviewer])['snapshot_id']
    real = ui.projection
    monkeypatch.setattr(ui, 'projection', lambda *args, **kwargs: {**real(*args, **kwargs), 'state': 'bezig'})
    import src.source_selection_v1 as selection
    summary = selection.summary_projection
    monkeypatch.setattr(selection, 'summary_projection', lambda *args, **kwargs: {**summary(*args, **kwargs), 'state': 'bezig'})
    client = TestClient(production_app(console))
    client.cookies.set(COOKIE, console.authenticate('author', 'strong-test-password')['token'])

    html = client.get('/source-selection', params={'document': first}).text

    cards = {sid: html.split(f'id="source-{sid}"', 1)[1].split('</article>', 1)[0] for sid in (first, second)}
    assert 'Voortgang bekijken' not in cards[first]
    assert 'ververst elke 5 seconden' in cards[first]
    assert f'href="/source-selection?document={second}">Voortgang bekijken</a>' in cards[second]
    assert 'window.location.reload()' in html
