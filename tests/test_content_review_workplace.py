"""#861 native route/command evidence; no parallel review authority.

# release-control-evidence: scope/belofte toegang kwaliteit slop releasebewijs opslag durable recovery stale
"""
from copy import deepcopy
from collections import Counter
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from tests.content_review_fixture_support import PASSWORD, bind, prepare, snapshot
from tests.production_support import restart_production
from tests.test_formation_repair_workplace import form_data
from tests.test_source_context_review_ui_v1 import Forms


def login(console, production_app, account):
    client = TestClient(production_app(console))
    assert client.post('/login', data={'username': account['username'], 'password': PASSWORD}, follow_redirects=False).status_code == 303
    return client


def test_one_mixed_workplace_actor_routes_exact_commands_and_restart(tmp_path, monkeypatch, production_console, production_app):
    console = production_console(root=tmp_path, processing_binder=bind)
    actors, docs = prepare(console)
    doc = docs[0]; sid = doc['snapshot_id']
    a = login(console, production_app, actors['a'])
    b = login(console, production_app, actors['b'])
    before = deepcopy(snapshot(console, docs))
    import src.review.review_passage_read_v1 as reads
    original = reads.read_review_document
    import src.operations_console_app as ui
    route_owner = ui.reviewer_route_for
    route_calls = Counter()
    def route_once(row, **kwargs):
        route_calls[row['object_id']] += 1
        return route_owner(row, **kwargs)
    count = []
    with monkeypatch.context() as patch:
        patch.setattr(ui, 'reviewer_route_for', route_once)
        patch.setattr(reads, 'read_review_document', lambda *args, **kwargs: (count.append(1) or original(*args, **kwargs)))
        for task in ('contextual', 'batch', 'second_review'):
            route_calls.clear()
            page = a.get('/review', params=dict(document=sid, task=task))
            assert page.status_code == 200
            assert route_calls and set(route_calls.values()) == {1}
            assert 'Kennisvoorstellen beoordelen' in page.text and 'data-content-review-workplace' in page.text
            assert doc['context'] in page.text
            forms = [f for f in Forms(page.text).forms if f['attrs'].get('action') == '/review/normal-risk/batch-confirm']
            assert len(forms) == 1
            members = {i['value'] for i in forms[0]['inputs'] if i.get('name') == 'object_ids'}
            assert members == set(doc['batch'])
            assert not any('checked' in i for i in forms[0]['inputs'] if i.get('name') == 'object_ids')
        assert count == [1, 1, 1]  # Same single existing document reader for every alias.
    waiting = b.get('/review', params=dict(document=sid, task='batch'))
    assert 'action="/review/normal-risk/batch-confirm"' not in waiting.text
    assert doc['context'] not in waiting.text
    other = b.get('/review', params=dict(document=doc['second_snapshot'], task='second_review'))
    assert doc['second'] in other.text
    assert 'action="/review/normal-risk/batch-confirm"' not in other.text
    assert doc['context'] not in other.text
    assert snapshot(console, docs) == before
    batch = form_data(page, '/review/normal-risk/batch-confirm')
    batch['object_ids'] = doc['batch']
    # No silently relaxed selection: contextual/high-assurance object is ineligible.
    invalid = a.post('/review/normal-risk/batch-confirm', data={**batch, 'object_ids': [doc['context']]})
    assert invalid.status_code == 400
    assert snapshot(console, docs) == before
    denied = b.post('/review/normal-risk/batch-confirm', data=batch)
    assert denied.status_code in (400, 403)
    assert snapshot(console, docs) == before
    response = a.post('/review/normal-risk/batch-confirm', data=batch, follow_redirects=False)
    assert response.status_code == 303, response.text
    bindings = [r for r in console.object_review_bindings(sid) if r['object_id'] in doc['batch'] and r['valid']]
    assert {r['object_id'] for r in bindings} == set(doc['batch'])
    for binding in bindings:
        obj = console._current_object(sid, binding['object_id'])
        assert binding['object_version'] == obj['object_version']
        assert binding['canonical_object_hash'] == obj['provenance']['canonical_object_hash']
        assert binding['confirmed_object_type'] == 'definition' and binding['decision'] == 'approve'
    after = deepcopy(snapshot(console, docs))
    assert a.post('/review/normal-risk/batch-confirm', data=batch).status_code == 409
    assert snapshot(console, docs) == after
    second_page = b.get('/review', params=dict(document=doc['second_snapshot'], object=doc['second'], task='second_review'))
    second = form_data(second_page, '/review/second-review'); second['action'] = 'approve'
    assert b.post('/review/second-review', data=second, follow_redirects=False).status_code == 303
    final = deepcopy(snapshot(console, docs))
    assert snapshot(restart_production(console), docs) == final
    a.get('/review', params=dict(document=sid, task='batch'))
    assert snapshot(console, docs) == final


def test_repair_return_preserves_origin_without_transferring_approval(tmp_path, production_console, production_app):
    console = production_console(root=tmp_path, processing_binder=bind)
    actors, docs = prepare(console); doc = docs[0]; sid = doc['snapshot_id']; oid = doc['batch'][0]
    client = login(console, production_app, actors['a'])
    review = client.get('/review', params=dict(document=sid, object=oid, task='contextual'))
    import re, html
    link = next(html.unescape(h) for h in re.findall(r'href="([^"]+)"', review.text) if 'task=repair' in h and 'review_revision=' in h)
    params = parse_qs(urlsplit(link).query)
    origin = params['review_revision'][0]
    owner = client.get(link + '&repair_kind=classification')
    data = form_data(owner); assert data['review_revision'] == origin
    old = console._current_object(sid, oid)
    data.update(comment='Controleerbaar type behouden.', type_action='type_wijzigen', confirmed_object_type='explanation')
    result = client.post('/review/resolve', data=data, follow_redirects=False)
    assert result.status_code == 303, result.text
    saved = client.get(result.headers['location'])
    back = next(html.unescape(h) for h in re.findall(r'href="([^"]+)"', saved.text) if h.startswith('/review?') and 'review_revision=' in h)
    assert parse_qs(urlsplit(back).query)['review_revision'] == [origin]
    returned = client.get(back)
    assert returned.status_code == 200 and 'data-review-return-changed' in returned.text
    current = console._current_object(sid, oid)
    assert current['object_id'] == old['object_id'] and current['object_version'] != old['object_version']
    assert current['governance']['validation_status'] == 'needs_review'
    assert not [r for r in console.object_review_bindings(sid) if r['object_id'] == oid and r['valid']]
    assert form_data(returned, '/review')['snapshot_revision'] != origin


def test_context_picker_preserves_review_origin_through_source_and_post(tmp_path, production_console, production_app):
    import html, re
    from tests.semantic_fixture_support import bind_fixture_selections
    from tests.test_source_context_review_v1 import _system
    from tests.test_source_context_review_ui_v1 import _client, _link_form, _payload
    state, _, _, source, target, command = _system(tmp_path,
        console=production_console(root=tmp_path, processing_binder=bind_fixture_selections))
    sid = command['snapshot_id']; oid = target['object_id']
    client = _client(state, production_app=production_app)
    review = client.get('/review', params=dict(document=sid, object=oid))
    link = next(html.unescape(h) for h in re.findall(r'href="([^"]+)"', review.text)
                if h.startswith('/source-selection?') and '#passage-context' in h)
    origin = parse_qs(urlsplit(link).query)['review_revision'][0]
    owner = client.get(link)
    pick = next(html.unescape(h) for h in re.findall(r'href="([^"]+)"', owner.text)
                if f'object={source["object_id"]}' in h and f'context_target={oid}' in h)
    assert parse_qs(urlsplit(pick).query)['review_revision'] == [origin]
    pair = client.get(pick)
    back = next(html.unescape(h) for h in re.findall(r'href="([^"]+)"', pair.text) if h.startswith('/review?'))
    assert parse_qs(urlsplit(back).query)['object'] == [oid]
    assert 'data-review-return-changed' not in client.get(back).text
    data = _payload(_link_form(pair))
    assert data['review_revision'] == origin and data['return_object_id'] == oid
    saved = client.post('/review/source-context', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    page = client.get(saved.headers['location'])
    back = next(html.unescape(h) for h in re.findall(r'href="([^"]+)"', page.text) if h.startswith('/review?'))
    assert parse_qs(urlsplit(back).query)['object'] == [oid]
    assert parse_qs(urlsplit(back).query)['review_revision'] == [origin]
    assert 'data-review-return-changed' in client.get(back).text
