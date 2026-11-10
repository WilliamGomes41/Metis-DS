"""Held real HTML extractor over PostgreSQL; test-only release route."""
from threading import Event

from tests.browser_postgres_support import browser_application

app = browser_application('annotation-source-progress')
console = app.state.operations_kernel
actor = console.create_account(username='annotator', password='annotation-secret', roles=('researcher','reviewer'))
reviewer = console.create_account(username='observer', password='annotation-secret', roles=('reviewer',))
sid = console.receive_source(actor_id=actor['account_id'], filename='source.html',
    data=b'<html><body><h1>Bron</h1><p>Controleer de huid.</p></body></html>',
    content_type='text/html', ingest_kind='new', title='Bron voorbereiden', version='1.0',
    date='2026-11-10', live_url='', class_='richtlijn', family='test',
    named_reviewers=[reviewer['account_id']])['snapshot_id']
release = Event()
extract = console._extract


def held(*args, **kwargs):
    if not release.wait(60):
        raise RuntimeError('browser fixture was not released')
    return extract(*args, **kwargs)


console._extract = held


@app.get('/browser-manifest')
def manifest():
    return {'username':'annotator','password':'annotation-secret','document':sid}


@app.post('/browser-release')
def release_extractor():
    release.set()
    return {'released':True}
