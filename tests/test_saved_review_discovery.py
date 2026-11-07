"""Saved KOs remain reachable while the reviewer still has open work.

# release-control-evidence: scope/belofte opslag concurrent stale toegang kwaliteit slop releasebewijs
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.test_ko_receipt_ui import prepared
from tests.test_review_command_bounded_http_v1 import physical_state


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
