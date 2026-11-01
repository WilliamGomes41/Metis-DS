"""HTTP behavior proof for the actual path; no production completion claim.

# release-control-evidence: scope/belofte opslag kwaliteit toegang releasebewijs metrics
"""
from copy import deepcopy
import json
import re
import time

import pytest
from tests.test_review_render_source_reuse import review_client  # noqa: F401


@pytest.mark.parametrize('review_client', [1100], indirect=True)
def test_large_review_get_post_redirect_reopen_preserves_unrelated_work(review_client):
    console, client, sid = review_client
    before = deepcopy(console.snapshot_objects(sid))
    focal = next(o for o in before if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    assert console.canonical_publication_store.release_for_snapshot(sid) is None
    timings = {}
    def measured(name, method, *args, **kwargs):
        start = time.monotonic()
        response = getattr(client, method)(*args, **kwargs)
        timings[name] = round(time.monotonic()-start, 4)
        return response
    params = {'document': sid, 'object': focal['object_id'], 'task': 'contextual'}
    page = measured('open', 'get', '/review', params=params)
    assert page.status_code == 200
    revision = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text)
    assert revision, 'Use the actual rendered mutation precondition'
    data = {'snapshot_id': sid, 'object_id': focal['object_id'], 'snapshot_revision': revision.group(1),
            'suitability': 'ja', 'documentpositie_action': 'dit_klopt', 'type_action': 'dit_klopt',
            'confirmed_object_type': 'definition', 'eindoordeel': 'goedkeuren', 'decision': 'approve',
            'relation_review_ack': '1'}
    response = measured('save', 'post', '/review', data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    redirected = measured('redirect', 'get', response.headers['location'])
    assert redirected.status_code == 200
    reopened = measured('reopen', 'get', '/review', params=params)
    assert reopened.status_code == 200
    current = console.snapshot_objects(sid)
    saved = next(o for o in current if o['object_id'] == focal['object_id'])
    assert saved['governance']['validation_status'] == 'approved'
    assert [o for o in current if o['object_id'] != focal['object_id']] == [o for o in before if o['object_id'] != focal['object_id']]
    assert console.canonical_publication_store.release_for_snapshot(sid) is None
    assert not console.publication_readiness(sid)['publish_allowed'], 'Unreviewed work must still block publication'
    # Existing #888 local engineering goals, not an Azure production SLO.
    assert timings['save'] <= 3, timings
    assert all(timings[name] <= 5 for name in ('open', 'redirect', 'reopen')), timings
    print(json.dumps({'proof': 'native_http_review_1100', 'seconds': timings}))

