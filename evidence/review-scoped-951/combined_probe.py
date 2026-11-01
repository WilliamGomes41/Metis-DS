"""Explicit full-chain release probe. Known legacy POST budget failure is retained.

Run via the command in README.md; this is not production acceptance.
"""
from copy import deepcopy
import json
import re
import time

import pytest


@pytest.mark.parametrize("layout", ["legacy", "compact"])
def test_partial_formation_history_existing_decision_and_http_command_together(tmp_path, production_console, monkeypatch, layout):
    """Combined retained-history workload through the native HTTP and write owners."""
    from fastapi.testclient import TestClient
    from src.review.revision_workflow import revise_object
    from tests.test_review_formation_problems import received, execute, FIRST, SECOND
    from tests.test_availability_repair import login
    source = ('<html><body>' + ''.join(
        f'<h1>Onderdeel {i}</h1><p>{FIRST if i < 2 else SECOND}</p>'
        for i in range(11)) + '</body></html>').encode()
    console, sid, author, reviewer, *_ = received(tmp_path, production_console, monkeypatch, source_html=source)
    execute(console, sid, author, 'combined-formation')
    candidates = [o for o in console.snapshot_objects(sid) if o.get('proposed_object_type') == 'recommendation']
    assert len(candidates) == 2
    focal, other = candidates
    console.review_object(actor_id=reviewer, snapshot_id=sid, object_id=other['object_id'],
        decision='approve', confirmed_object_type='recommendation',
        recommendation_direction='against', recommendation_strength_level='not_stated')
    rows = console._load_objects(sid)
    previous = focal
    # Human revision helper preserves the actual materialised candidate identity,
    # source mapping and predecessor hashes. No second candidate creator.
    for _ in range(1100-len(rows)):
        previous = revise_object(previous, deepcopy(previous), snapshot_id=sid,
            reason='Retained synthetic review history', actor=reviewer, force=True)
        rows.append(previous)
    console._save_objects(sid, rows, expected_revision=console.objects_revision(sid))
    store = console.workflow_document_store
    envelope = store.get_envelope(sid)
    real_runs = envelope['quality_processing_runs']
    envelope['quality_processing_runs'] = [{**deepcopy(real_runs[0]), 'run_id': 'retained-history',
        'raw_processing_evidence': 'synthetic retained evidence ' * 1000000}, *real_runs]
    store.write_bundle(envelope=envelope)
    with store._connect() as con:
        shape = con.execute('SELECT octet_length(envelope_payload::text) AS bytes FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()
    assert shape['bytes'] > 25000000
    assert len(store.list_document_objects(sid)) == 1100
    if layout == 'compact':
        store.activate_operational_inputs(store.prepare_operational_inputs(sid))
    before = deepcopy(console.snapshot_objects(sid))
    other_before = next(o for o in before if o['object_id'] == other['object_id'])
    bindings_before = console.object_review_bindings(sid)
    status_before = console.processing_status(sid)
    assert status_before['formation_incomplete']
    timings = {}
    def measured(name, method, *args, **kwargs):
        started = time.monotonic()
        result = getattr(client, method)(*args, **kwargs)
        timings[name] = time.monotonic() - started
        return result
    params = {'document': sid, 'object': focal['object_id'], 'task': 'contextual'}
    with TestClient(console._metis_test_application, base_url='https://console.example.test',
                    headers={'Origin': 'https://console.example.test'}) as client:
        login(client, 'reviewer')
        page = measured('open', 'get', '/review', params=params)
        assert page.status_code == 200, page.text
        assert 'data-document-assessment="not_evaluated"' in page.text
        revision = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text).group(1)
        data = {'snapshot_id': sid, 'object_id': focal['object_id'], 'snapshot_revision': revision,
            'suitability': 'ja', 'documentpositie_action': 'dit_klopt', 'type_action': 'dit_klopt',
            'confirmed_object_type': 'recommendation', 'recommendation_direction': 'against',
            'recommendation_strength_level': 'not_stated', 'eindoordeel': 'goedkeuren',
            'decision': 'approve', 'relation_review_ack': '1'}
        saved = measured('save', 'post', '/review', data=data, follow_redirects=False)
        assert saved.status_code == 303, saved.text
        assert measured('redirect', 'get', saved.headers['location']).status_code == 200
        assert measured('reopen', 'get', '/review', params=params).status_code == 200
        after = deepcopy(console.snapshot_objects(sid))
        events = console.workflow_review_store.read_events()
        refused = measured('stale', 'post', '/review', data=data, follow_redirects=False)
        assert refused.status_code == 409
        assert console.snapshot_objects(sid) == after
        assert console.workflow_review_store.read_events() == events
    assert next(o for o in after if o['object_id'] == focal['object_id'])['governance']['validation_status'] == 'approved'
    assert next(o for o in after if o['object_id'] == other['object_id']) == other_before
    assert all(b in console.object_review_bindings(sid) for b in bindings_before if b['object_id'] == other['object_id'])
    assert console.processing_status(sid)['formation_incomplete']
    assert not console.publication_readiness(sid)['publish_allowed']
    assert console.canonical_publication_store.release_for_snapshot(sid) is None
    print(json.dumps({'proof': 'native_combined_history_partial_http', 'layout': layout, 'seconds': timings}))
    assert timings['save'] <= 3, timings
    assert all(timings[name] <= 5 for name in ('open', 'redirect', 'reopen', 'stale')), timings
