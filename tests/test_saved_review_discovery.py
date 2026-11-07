"""Saved KOs remain reachable while the reviewer still has open work.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.test_ko_receipt_ui import prepared
from tests.test_review_command_bounded_http_v1 import physical_state
from tests.test_availability_repair import login
from tests.test_ko_state_derivation_postgres import ready
from tests.test_vsa_publish_document_v1 import TEST_PASSWORD
from tests.test_ko3_publication_membership import publish as publish_canonical_fixture
from tests.test_ko3_publication_membership import physical_state as canonical_state
from fastapi.testclient import TestClient


@pytest.mark.parametrize('entry', ['workboard', 'receipt', 'inventory'])
def test_saved_object_can_be_reopened_without_writing(
    tmp_path, production_console, monkeypatch, entry,
):
    console, sid, reviewer, obj, client, page, data = prepared(
        tmp_path, production_console, monkeypatch)
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    before = physical_state(console, sid)
    if entry == 'receipt':
        result = client.get(saved.headers['location'])
        link = re.search(r'<a[^>]*data-ko-view-object[^>]*href="([^"]+)"', result.text)
        assert link, 'The receipt needs a route back to the saved knowledge object'
        target = html.unescape(link[1])
    else:
        workboard = client.get('/review', params={'document': sid})
        assert workboard.status_code == 200
        assert 'data-personal-review-action' in workboard.text, 'Another review must remain open'
        if entry == 'workboard':
            link = re.search(r'<a[^>]*data-review-inventory[^>]*href="([^"]+)"', workboard.text)
            assert link, 'The full inventory must remain reachable alongside open work'
            inventory = client.get(html.unescape(link[1]))
        else:
            inventory = client.get('/review', params={'document': sid, 'task': 'inventory'})
        assert inventory.status_code == 200
        row = re.search(r'<li data-passage-id="' + re.escape(obj['object_id']) + r'".*?</li>',
                        inventory.text, re.S)
        assert row, 'The reviewed object must still appear in the full inventory'
        link = re.search(r'<a class="review-row-title" href="([^"]+)"', row[0])
        assert link
        target = html.unescape(link[1])
    parsed = urlsplit(target)
    assert parsed.path == '/review', 'Open the knowledge object, not only its source passage'
    assert parse_qs(parsed.query)['object'] == [obj['object_id']]
    opened = client.get(target)
    assert opened.status_code == 200, opened.text
    assert html.escape(obj['content']['clean_text']) in opened.text
    assert 'data-ko-state>Goedgekeurd<' in opened.text
    assert 'data-ko-object-view' in opened.text
    assert 'data-ko-assessment-form' not in opened.text
    assert 'data-recorded-evidence-applicability="not_applicable"' in opened.text
    assert physical_state(console, sid) == before


def test_concurrent_saved_object_and_workboard_reads_preserve_the_decision(
    tmp_path, production_console, monkeypatch,
):
    console, sid, reviewer, obj, client, page, data = prepared(
        tmp_path, production_console, monkeypatch)
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303
    before = physical_state(console, sid)
    events = console.workflow_review_store.read_events_for_snapshots([sid])
    with ThreadPoolExecutor(max_workers=2) as workers:
        requests = [workers.submit(client.get, '/review', params=params) for params in (
            {'document': sid}, {'document': sid, 'object': obj['object_id'], 'task': 'inventory'})]
        results = [request.result() for request in requests]
    assert all(result.status_code == 200 for result in results)
    assert 'data-ko-object-view' in results[1].text
    assert physical_state(console, sid) == before
    assert console.workflow_review_store.read_events_for_snapshots([sid]) == events


def test_saved_knowledge_view_keeps_the_named_reviewer_boundary(
    tmp_path, production_console, monkeypatch,
):
    console, sid, reviewer, obj, client, page, data = prepared(
        tmp_path, production_console, monkeypatch)
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303
    console.create_account(username='outside-review', password='fixture-only',
                           roles=('reviewer',), display_name='Andere reviewer')
    login(client, 'outside-review')
    before = physical_state(console, sid)
    response = client.get('/review', params={'document': sid, 'object': obj['object_id'],
                          'task': 'inventory'}, follow_redirects=False)
    assert response.status_code == 303
    assert urlsplit(response.headers['location']).path == '/review/trajectory'
    assert 'data-ko-object-view' not in response.text
    assert physical_state(console, sid) == before


@pytest.mark.parametrize('released', ['published', 'withdrawn', 'superseded', 'different_tuple'])
def test_saved_view_uses_exact_canonical_publication_state(ready, released, monkeypatch):
    console, accounts, sid, _ = ready
    obj = next(row for row in console.snapshot_objects(sid)
               if row.get('confirmed_object_type') == 'explanation')
    store = console.canonical_publication_store
    if released == 'different_tuple':
        publish_canonical_fixture(store, sid='older-source', release='older-release',
                                  oid=obj['object_id'], version='0.9.0')
    else:
        published = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
        assert published['status'] == 'PASS'
    if released == 'withdrawn':
        console.withdraw_document(actor_id=accounts['publisher']['account_id'], snapshot_id=sid,
                                  expected_release_id=published['release_id'], reason='Synthetic read-view control')
    elif released == 'superseded':
        with store._connect() as connection:
            at = connection.execute('SELECT published_at FROM publication_releases WHERE release_id=%s',
                                    (published['release_id'],)).fetchone()['published_at']
        publish_canonical_fixture(store, sid='successor-source',
                                  release='successor-release', oid=obj['object_id'], version='2.0.0',
                                  checksum='b' * 64, at=(at + timedelta(seconds=1)).isoformat())
    client = TestClient(console._metis_test_application)
    assert client.post('/login', data={'username': 'reviewer.bert', 'password': TEST_PASSWORD},
                       follow_redirects=False).status_code == 303
    before = physical_state(console, sid)
    canonical_before = canonical_state(store)
    reads = []
    original = store.object_publication_membership
    def bounded(snapshot_id, selected):
        assert snapshot_id == sid
        assert len(selected) == 1
        assert selected[0][:2] == (obj['object_id'], obj['object_version'])
        reads.append(selected)
        return original(snapshot_id, selected)
    monkeypatch.setattr(store, 'object_publication_membership', bounded)
    result = client.get('/review', params={'document': sid, 'object': obj['object_id'], 'task': 'inventory'})
    assert result.status_code == 200, result.text
    expected = {'published': 'Gepubliceerd', 'withdrawn': 'Ingetrokken', 'superseded': 'Vervangen',
                'different_tuple': 'Goedgekeurd'}[released]
    assert f'data-ko-state>{expected}<' in result.text
    assert 'data-ko-assessment-form' not in result.text
    assert physical_state(console, sid) == before
    assert len(reads) == 1
    assert canonical_state(store) == canonical_before
