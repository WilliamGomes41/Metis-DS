"""Vorming updates status in place and reads only visible requested documents.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from fastapi.testclient import TestClient

import src.vorming.source_selection_ui_v1 as ui
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
    summary = ui.summary_projection
    monkeypatch.setattr(ui, 'summary_projection', lambda *args, **kwargs: {**summary(*args, **kwargs), 'state': 'bezig'})
    client = TestClient(production_app(console))
    client.cookies.set(COOKIE, console.authenticate('author', 'strong-test-password')['token'])

    html = client.get('/source-selection', params={'document': first}).text

    cards = {sid: html.split(f'id="source-{sid}"', 1)[1].split('</article>', 1)[0] for sid in (first, second)}
    assert 'Voortgang bekijken' not in cards[first]
    assert 'data-source-attempt' in cards[first]
    assert f'href="/source-selection?document={second}" data-source-detail-link>Voortgang bekijken</a>' in cards[second]
    assert 'data-source-pause' in html and 'window.location.reload()' not in html

    before = console._processing_history_envelope(first)['processing_attempts']
    original = console.workflow_document_store.list_source_selection_summaries
    scopes = []

    def record_reads(*, snapshot_ids=None):
        scopes.append(snapshot_ids)
        return original(snapshot_ids=snapshot_ids)

    monkeypatch.setattr(console.workflow_document_store, 'list_source_selection_summaries', record_reads)
    progress = client.get('/source-selection/progress', params={'snapshot': first})
    assert progress.status_code == 200 and progress.headers['cache-control'] == 'no-store'
    row, = progress.json()['rows']
    assert row['snapshot'] == first and row['running'] and row['attempt']
    assert 'detail' not in row
    assert scopes == [[first]]
    assert console._processing_history_envelope(first)['processing_attempts'] == before

    console.create_account(username='outside-progress', password='strong-test-password', roles=('reviewer',))
    client.cookies.set(COOKIE, console.authenticate('outside-progress', 'strong-test-password')['token'])
    protected = client.get('/source-selection/progress', params={'snapshot': first})
    assert protected.json() == {'rows': []}
    client.cookies.clear()
    assert client.get('/source-selection/progress', params={'snapshot': first}).status_code == 401
