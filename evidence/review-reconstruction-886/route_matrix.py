import json
import os
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient
from tests.test_review_render_source_reuse import review_client
from tests.test_review_formation_problems import received, execute
from tests.test_availability_repair import login
from tests.semantic_fixture_support import bind_fixture_selections


def measure(client, sid, object_id):
    results = {}
    for name, params in [('overview', {}), ('document', {'document': sid, 'task': 'individual'}),
                         ('passage', {'document': sid, 'object': object_id})]:
        samples = []
        for _ in range(5):
            start = perf_counter()
            response = client.get('/review', params=params)
            samples.append({'seconds': perf_counter() - start, 'bytes': len(response.content),
                            'status': response.status_code})
            assert response.status_code == 200
        results[name] = samples
    return results


def save(name, data):
    directory = Path(os.environ['MATRIX_OUTPUT'])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (name + '.json')).write_text(json.dumps(data, indent=2))


@pytest.mark.parametrize('review_client', [300], indirect=True)
def test_complete_and_multiple_documents(review_client):
    console, client, sid = review_client
    rows = console.snapshot_objects(sid)
    obj = next(o for o in rows if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    save('complete-300', measure(client, sid, obj['object_id']))
    accounts = {a['username']: a['account_id'] for a in console.list_accounts()}
    bind_fixture_selections(console, [('Een begrip is een afzonderlijke waarneming.', 'definition')])
    other = console.ingest(actor_id=accounts['author'], filename='second.html', content_type='text/html',
        data=b'<html><body><p>Een begrip is een afzonderlijke waarneming.</p></body></html>',
        ingest_kind='new', title='Second review benchmark', version='1', date='2026-10-08',
        live_url='', class_='richtlijn', family='fixture', named_reviewers=[accounts['reviewer']])['snapshot_id']
    # The fixture stubs lifecycle projection: include the actual second document.
    console.list_document_lifecycle_statuses = lambda: {x: {'workflow_status': 'in_review',
        'release_status': 'none', 'serving_status': 'inactive', 'presentation_status': 'in_review'} for x in (sid, other)}
    save('two-documents', measure(client, sid, obj['object_id']))
    fragments = ['De patiënt heeft'] + ['ondersteuning nodig bij dagelijkse verzorging'] * 148 + ['bij zorg.']
    body = '<p>Een begrip is een afzonderlijke waarneming.</p>' + ''.join(f'<p>{text}</p>' for text in fragments)
    continued = console.ingest(actor_id=accounts['author'], filename='continued.html', content_type='text/html',
        data=('<html><body>' + body + '</body></html>').encode(), ingest_kind='new',
        title='Continued source benchmark', version='1', date='2026-10-08', live_url='',
        class_='richtlijn', family='fixture', named_reviewers=[accounts['reviewer']])['snapshot_id']
    console.list_document_lifecycle_statuses = lambda: {x: {'workflow_status': 'in_review',
        'release_status': 'none', 'serving_status': 'inactive', 'presentation_status': 'in_review'}
        for x in (sid, other, continued)}
    continued_rows = console.snapshot_objects(continued)
    continued_obj = next(o for o in continued_rows if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    save('continued-150', measure(client, continued, continued_obj['object_id']))


def test_incomplete(tmp_path, production_console, monkeypatch):
    console, sid, author, reviewer, _, _, _ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'matrix-baseline')
    assert console.processing_status(sid)['formation_incomplete']
    obj = next(o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    with TestClient(console._metis_test_application) as client:
        login(client, 'reviewer')
        save('incomplete', measure(client, sid, obj['object_id']))
