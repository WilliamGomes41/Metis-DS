"""Legacy headings are read-only in the guideline review workflow.

# release-control-evidence: scope/belofte opslag concurrent stale toegang kwaliteit slop releasebewijs
"""
from tests.test_a08_heading_batch_atomic import _client, _setup, _state


def test_guideline_review_cannot_confirm_headings_again(tmp_path, production_console, production_app):
    console, _, sid, ids = _setup(tmp_path, production_console=production_console)
    client = _client(console, production_app=production_app)
    before = _state(console, sid)
    for route in ('/source-selection', '/review'):
        response = client.get(route, params={'document': sid, 'task': 'structure'}, follow_redirects=False)
        assert response.status_code == 404
    detail = client.get('/review', params={'document': sid, 'object': ids[0]})
    assert detail.status_code == 200
    assert 'action="/review/headings/batch-confirm"' not in detail.text
    assert 'name="eindoordeel" value="goedkeuren"' not in detail.text
    assert 'name="eindoordeel" value="afwijzen"' in detail.text
    post = client.post('/review/headings/batch-confirm', data={
        'snapshot_id': sid, 'object_ids': ids, 'snapshot_revision': before[3],
    }, follow_redirects=False)
    assert post.status_code == 404
    assert _state(console, sid) == before
