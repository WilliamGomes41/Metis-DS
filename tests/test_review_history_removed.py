"""Retired history bookmarks must never load document history or audit.

# release-control-evidence: scope/belofte toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy

import pytest

from tests.test_review_direct_workspace_v1 import Console, client, document
from tests.test_review_render_source_reuse import review_client  # noqa: F401


@pytest.mark.parametrize('task', ['history', 'decisions'])
@pytest.mark.parametrize('object_id', ['', 'previous-object'])
def test_history_bookmarks_redirect_before_document_reads(monkeypatch, task, object_id):
    console = Console(documents=[('one', document('Document'))])

    def forbidden(*args, **kwargs):
        raise AssertionError('retired page read document history or audit')

    monkeypatch.setattr(console, '_envelope', forbidden)
    import src.review.review_passage_read_v1 as reads
    for name in ('read_review_document', 'read_review_passage', 'read_review_navigation'):
        monkeypatch.setattr(reads, name, forbidden)
    monkeypatch.setattr('src.review.review_workboard_v1._render_review_room', forbidden)
    response = client(console).get('/review', params={
        'document': 'one', 'object': object_id, 'task': task,
        'after': 'previous', 'context_mode': 'source',
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/review?document=one'


@pytest.mark.parametrize('task', ['history', 'decisions'])
def test_history_bookmarks_still_require_authentication(task):
    response = client(Console(), login=False).get(
        '/review', params={'task': task}, follow_redirects=False)
    assert response.status_code == 403


@pytest.mark.parametrize('route', ['/review', '/review/bronpassage'])
def test_native_retired_page_does_not_read_or_mutate_review_evidence(review_client, monkeypatch, route):
    from src.review.review_ledger import read_events
    console, browser, sid = review_client
    before = deepcopy(console.snapshot_objects(sid))
    bindings = deepcopy(console.object_review_bindings(sid))
    events = deepcopy(read_events(console._ledger_path))

    def forbidden(*args, **kwargs):
        raise AssertionError('retired page captured objects, source or audit')

    with monkeypatch.context() as patch:
        for name in ('snapshot_objects_and_revision', 'audit_review_signals', '_envelope', 'open_source_passage'):
            patch.setattr(console, name, forbidden)
        import src.review.review_passage_read_v1 as reads
        for name in ('read_review_document', 'read_review_passage', 'read_review_navigation'):
            patch.setattr(reads, name, forbidden)
        for task in ('history', 'decisions'):
            response = browser.get(route, params={
                'document': sid, 'task': task, 'object': before[-1]['object_id'],
            }, follow_redirects=False)
            assert response.status_code == 303
            assert response.headers['location'] == '/review?document=' + sid
        browser.cookies.clear()
        response = browser.get(route, params={
            'document': sid, 'task': 'history', 'object': before[-1]['object_id'],
        }, follow_redirects=False)
        assert response.status_code == 401
    assert console.snapshot_objects(sid) == before
    assert console.object_review_bindings(sid) == bindings
    assert read_events(console._ledger_path) == events
