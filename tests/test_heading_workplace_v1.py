"""Existing heading command, one workplace, real PG and process restart.

# release-control-evidence: scope/belofte opslag concurrent stale toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json

from fastapi.testclient import TestClient

from src import operations_console_app as ui
from tests.test_a08_heading_batch_atomic import _setup, _state, _client, _new_process_state
from tests.test_source_context_review_ui_v1 import Forms


def _form(html):
    return next(f for f in Forms(html).forms if f['attrs'].get('action') == '/review/headings/batch-confirm')


def test_heading_form_post_refresh_native_restart_and_old_workplace(tmp_path, monkeypatch, *, production_app, production_console):
    state, accounts, sid, ids = _setup(tmp_path, production_console=production_console)
    client = _client(state, production_app=production_app)
    before = _state(state, sid)
    original_rows = state.snapshot_objects(sid)
    all_heading_ids = {r['object_id'] for r in original_rows if r.get('object_type') == 'heading'}
    calls = {}
    for name in ('snapshot_objects_and_revision', 'object_review_bindings', 'review_source_fragments'):
        original = getattr(state, name)
        def counted(*args, _name=name, _original=original, **kwargs):
            calls[_name] = calls.get(_name, 0) + 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(state, name, counted)
    # The previous document-task renderer supplies the same measured read baseline.
    old = ui._render_review_room(state, accounts['reviewer'], sid, task='structure')
    assert '/review/headings/batch-confirm' not in old
    assert not any(i.get('name') == 'object_ids' for f in Forms(old).forms for i in f['inputs'])
    baseline = dict(calls)
    for task in ('structure', 'headings'):
        response = client.get('/review', params={'document': sid, 'task': task}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'] == f'/source-selection?document={sid}&task=structure'
    detail = client.get('/review', params={'document': sid, 'object': ids[0]})
    assert detail.status_code == 200
    assert 'data-heading-owner' in detail.text
    assert 'name="eindoordeel" value="goedkeuren"' not in detail.text
    assert 'name="eindoordeel" value="afwijzen"' in detail.text  # distinct C1 action retained
    calls.clear()
    page = client.get('/source-selection', params={'document': sid, 'task': 'structure'})
    assert page.status_code == 200 and 'data-formation-structure' in page.text
    assert calls.get('snapshot_objects_and_revision') == 1
    assert all(calls.get(name, 0) <= baseline.get(name, 0) for name in calls)
    form = _form(page.text)
    choices = [i for i in form['inputs'] if i.get('name') == 'object_ids']
    assert {i['value'] for i in choices} == all_heading_ids
    assert all('checked' not in i for i in choices)
    data = {i['name']: i.get('value', '') for i in form['inputs'] if i.get('type') == 'hidden'}
    data['object_ids'] = [ids[0]]
    assert data['snapshot_revision'] == before[3]
    assert _state(state, sid) == before  # navigation and source/detail reads do not write
    stale = client.post('/review/headings/batch-confirm', data={**data, 'snapshot_revision': 'stale'}, follow_redirects=False)
    assert stale.status_code == 409 and 'data-formation-structure' in stale.text
    assert _form(stale.text)['attrs']['action'] == '/review/headings/batch-confirm'
    assert _state(state, sid) == before
    outsider_account = state.create_account(username='outside.heading', password='outside-secret', roles=('reviewer',))
    outsider = TestClient(client.app)
    assert outsider.post('/login', data={'username': outsider_account['username'], 'password': 'outside-secret'}, follow_redirects=False).status_code == 303
    # Existing generic ConsoleError mapping: named-reviewer denial is 400.
    denied = outsider.get('/source-selection', params={'document': sid, 'task': 'structure'})
    assert denied.status_code == 400 and 'Je bent niet aangewezen als beoordelaar' in denied.text
    assert outsider.post('/review/headings/batch-confirm', data=data, follow_redirects=False).status_code == 400
    assert _state(state, sid) == before
    with monkeypatch.context() as published:
        published.setattr(state, 'snapshot_is_published', lambda _: True)
        frozen = client.get('/source-selection', params={'document': sid, 'task': 'structure'})
        assert frozen.status_code == 200 and '/review/headings/batch-confirm' not in frozen.text
        assert not any(i.get('name') == 'object_ids' for f in Forms(frozen.text).forms for i in f['inputs'])
        assert client.post('/review/headings/batch-confirm', data=data, follow_redirects=False).status_code == 400
        assert _state(state, sid) == before
    response = client.post('/review/headings/batch-confirm', data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers['location'] == f'/source-selection?document={sid}&task=structure'
    after = _state(state, sid)
    current = ui._current_review_objects(state.workflow_document_store.list_document_objects(sid))
    selected = next(r for r in current if r['object_id'] == ids[0])
    assert selected['governance']['validation_status'] == 'approved'
    assert all(r in current for r in original_rows if r['object_id'] != ids[0])
    assert state._envelope(sid)['sha256'] == before[1]['sha256']
    refreshed = client.get(response.headers['location'])
    remaining = {i['value'] for i in _form(refreshed.text)['inputs'] if i.get('name') == 'object_ids'}
    assert remaining == all_heading_ids - {ids[0]}
    assert client.post('/review/headings/batch-confirm', data=data, follow_redirects=False).status_code == 409
    assert _state(state, sid) == after
    assert _new_process_state(tmp_path, sid, 'postgres') == json.loads(json.dumps(after))
    # No boom operation has been moved or made available via this prose view.
    envelope = state._envelope(sid)
    with monkeypatch.context() as boom:
        boom.setattr(state, '_envelope', lambda _: {**deepcopy(envelope), 'class': 'beslisboom'})
        target = client.get('/source-selection', params={'document': sid, 'task': 'structure'}, follow_redirects=False)
        assert target.status_code == 303 and target.headers['location'] == f'/review?document={sid}&task=structure'
    assert _state(state, sid) == after
