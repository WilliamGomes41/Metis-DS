"""One repair workplace through real HTTP and native PostgreSQL.

# release-control-evidence: scope/belofte opslag concurrent stale toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
from urllib.parse import urlencode, parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from tests.test_deterministic_review_repair_v1 import _system
from tests.test_source_context_review_ui_v1 import Forms
from tests.semantic_fixture_support import bind_fixture_selections


def form_data(page, action='/review/resolve'):
    forms = [f for f in Forms(page.text).forms if f['attrs'].get('action') == action]
    assert len(forms) == 1, page.text
    return {field['name']: field.get('value', '') for field in forms[0]['inputs']
            if field.get('type') == 'hidden' or 'checked' in field}


def classification_system(tmp_path, *, production_app, production_console):
    state = production_console(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime',
        processing_binder=bind_fixture_selections)
    researcher = state.create_account(username='anne', password='anne-secret', roles=('researcher',))
    reviewer = state.create_account(username='bert', password='bert-secret', roles=('reviewer',))
    text = 'Eenzaamheid is een gevoel van gemis.'
    bind_fixture_selections(state, [(text, 'definition')])
    sid = state.ingest(actor_id=researcher['account_id'], filename='classificatie.html',
        data=('<html><body><h1>Richtlijn</h1><h2>1 Begin</h2><p>' + text + '</p><h2>2 Vervolg</h2></body></html>').encode(),
        content_type='text/html', ingest_kind='new', title='Classificatie', version='1.0', date='2026-10-26',
        live_url='', class_='richtlijn', family='classification', named_reviewers=[reviewer['account_id']])['snapshot_id']
    objects = [o for o in state.snapshot_objects(sid) if o.get('proposed_object_type') == 'definition']
    client = TestClient(production_app(state))
    client.post('/login', data=dict(username='bert', password='bert-secret'))
    return state, client, researcher, reviewer, sid, objects


@pytest.mark.parametrize('kind', ['source_units', 'merge_objects', 'support_relation', 'classification'])
def test_complete_existing_repair_runs_only_on_formation(tmp_path, monkeypatch, kind, *, production_app, production_console):
    setup = classification_system if kind == 'classification' else _system
    state, client, _, _, sid, objects = setup(tmp_path, production_app=production_app, production_console=production_console)
    obj = objects[0]
    oid = obj['object_id']
    url = '/source-selection?' + urlencode(dict(document=sid, object=oid, task='repair', repair_kind=kind))
    before = deepcopy(state.snapshot_objects(sid, include_blocked=True))
    events = deepcopy(state.workflow_review_store.read_events())
    envelope = deepcopy(state._envelope(sid))
    review = client.get('/review', params=dict(document=sid, object=oid))
    assert review.status_code == 200
    assert 'value="type_wijzigen"' not in review.text
    assert 'value="andere_kop"' not in review.text
    assert 'data-heading-chooser' not in review.text
    assert 'name="proposed_correction"' not in review.text
    assert 'action="/review/resolve"' not in review.text
    assert 'Passage herstellen in Vorming' in review.text
    if kind == 'classification':
        import src.review_passage_read_v1 as reader
        original_read = reader.read_review_passage
        reads = []
        with monkeypatch.context() as patch:
            patch.setattr(reader, 'read_review_passage', lambda *a, **kw:
                (reads.append(1) or original_read(*a, **kw)))
            patch.setattr(state, 'snapshot_objects', lambda *a, **kw: pytest.fail('unbounded classification read'))
            patch.setattr(state, 'snapshot_objects_and_revision', lambda *a, **kw: pytest.fail('unbounded classification read'))
            owner = client.get(url)
        assert reads == [1]
    else:
        owner = client.get(url)
    assert owner.status_code == 200 and 'data-formation-repair' in owner.text
    data = form_data(owner)
    assert data['repair_kind'] == kind
    assert state.snapshot_objects(sid, include_blocked=True) == before
    assert state.workflow_review_store.read_events() == events
    assert state._envelope(sid) == envelope
    old = client.get('/review', params=dict(document=sid, object=oid, task='repair'), follow_redirects=False)
    assert old.status_code == 303 and old.headers['location'].startswith('/source-selection?')
    data['comment'] = 'Controleerbare correctie op de bestaande bron.'
    if kind == 'source_units':
        refs = {r['raw_object_id'] for r in obj['provenance']['source_fragments']}
        data['source_unit_ids'] = [u['unit_id'] for u in state.source_units(snapshot_id=sid, object_id=oid) if u['fragment_id'] in refs]
    elif kind == 'merge_objects':
        data['merge_object_ids'] = [objects[1]['object_id']]
    elif kind == 'support_relation':
        data['claim_object_id'] = objects[1]['object_id']
    else:
        data.update(type_action='type_wijzigen', confirmed_object_type='explanation', documentpositie_action='andere_kop',
                    parent_choice=next(o['object_id'] for o in state.snapshot_objects(sid) if '2 Vervolg' in o['content']['clean_text']))
        assert data['snapshot_revision'].startswith('review-generation-v1:')
    invalid = client.post('/review/resolve', data={**data, 'comment': ' '})
    assert invalid.status_code == 400
    assert 'Niet opgeslagen' in invalid.text
    assert state.snapshot_objects(sid, include_blocked=True) == before
    outsider = TestClient(production_app(state))
    outsider.post('/login', data=dict(username='anne', password='anne-secret'))
    assert outsider.get(url).status_code == 400
    assert outsider.post('/review/resolve', data=data).status_code == 403
    with monkeypatch.context() as patch:
        patch.setattr(state, 'snapshot_is_published', lambda sid: True)
        assert 'action="/review/resolve"' not in client.get(url).text
        assert client.post('/review/resolve', data=data).status_code == 400
    stale = client.post('/review/resolve', data={**data, 'snapshot_revision': 'stale'})
    assert stale.status_code == 400 and 'Niet opgeslagen' in stale.text
    assert state.snapshot_objects(sid, include_blocked=True) == before
    response = client.post('/review/resolve', data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert parse_qs(urlsplit(response.headers['location']).query)['object'] == [oid]
    revised = state._current_object(sid, oid)
    assert revised['governance']['validation_status'] == 'needs_review'
    assert not any(r['governance']['validation_status'] == 'revise' for r in state.snapshot_objects(sid))
    if kind != 'support_relation':
        assert revised['object_version'] != obj['object_version']
    assert state._envelope(sid)['sha256'] == envelope['sha256']
    after = deepcopy(state.snapshot_objects(sid, include_blocked=True))
    replay = client.post('/review/resolve', data=data)
    assert replay.status_code == 400
    assert state.snapshot_objects(sid, include_blocked=True) == after
    saved = client.get(response.headers['location'])
    assert saved.status_code == 200 and 'Het nieuwe voorstel is opgeslagen' in saved.text
    assert state.snapshot_objects(sid, include_blocked=True) == after
    restarted = production_console(processing_binder=bind_fixture_selections,
        root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime')
    assert restarted._current_object(sid, oid) == revised
    if kind == 'classification':
        review = client.get('/review', params=dict(document=sid, object=oid))
        approve = form_data(review, '/review')
        assert approve['confirmed_object_type'] == 'explanation'
        assert approve['parent_choice'] == data['parent_choice']
        assert 'data-current-parent="' + data['parent_choice'] + '"' in review.text
        assert 'Actuele kop:' in review.text
        approve.update(suitability='ja', eindoordeel='goedkeuren', type_action='dit_klopt', documentpositie_action='dit_klopt')
        approved = client.post('/review', data=approve, follow_redirects=False)
        assert approved.status_code == 303, approved.text
        assert state._current_object(sid, oid)['confirmed_object_type'] == 'explanation'
        assert state._current_object(sid, oid)['parent_object_id'] == data['parent_choice']


def test_graph_editor_and_confirmation_have_distinct_owners(tmp_path, *, production_app, production_console):
    from tests.test_decision_graph_chain import _console, _accounts, ingest, complete_graph
    state = _console(tmp_path, production_console=production_console)
    accounts = _accounts(state)
    sid = ingest(state, accounts)['snapshot_id']
    client = TestClient(production_app(state))
    client.post('/login', data=dict(username='researcher.anne', password='anne-secret'))
    before = deepcopy(state._envelope(sid))
    objects = deepcopy(state.snapshot_objects(sid))
    review = client.get('/review/decision-graph', params=dict(document=sid))
    assert review.status_code == 200
    assert 'value="graph"' not in review.text and 'name="node_mode"' not in review.text
    assert 'value="confirm"' in review.text
    owner = client.get('/source-selection', params=dict(document=sid, task='graph'))
    assert owner.status_code == 200
    assert 'name="node_mode"' in owner.text and 'value="graph"' in owner.text
    assert 'value="confirm"' not in owner.text
    assert 'action="/review/decision-graph"' in owner.text
    assert state._envelope(sid) == before and state.snapshot_objects(sid) == objects
    graph = complete_graph(state, sid)
    data = form_data(owner, '/review/decision-graph')
    data.update(action='graph', reason='Verbindingen gecontroleerd tegen de bron.',
        node_id=[n['object_id'] for n in graph['nodes']], node_mode=[n['mode'] for n in graph['nodes']],
        entrypoint=graph['entrypoints'], **{'from': graph['edges'][0]['from'], 'to': graph['edges'][0]['to'],
        'kind': 'continue', 'label': '', 'evidence-0': graph['edges'][0]['evidence_ids']})
    response = client.post('/review/decision-graph', data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers['location'].startswith('/source-selection?')
    saved = deepcopy(state._envelope(sid))
    events = deepcopy(state.workflow_review_store.read_events())
    assert saved['decision_graph']['edges'][0]['from'] == graph['edges'][0]['from']
    assert saved['sha256'] == before['sha256']
    current = state.snapshot_objects(sid)
    assert [(o['object_id'], o['content'], o['provenance']['source_fragments']) for o in current] == [(o['object_id'], o['content'], o['provenance']['source_fragments']) for o in objects]
    assert all(n['object_version'] == next(o['object_version'] for o in current if o['object_id'] == n['object_id']) for n in saved['decision_graph']['nodes'])
    duplicate = client.post('/review/decision-graph', data=data, follow_redirects=False)
    assert duplicate.status_code == 400 and 'decision_review_command_conflict' in duplicate.text
    assert state._envelope(sid) == saved and state.workflow_review_store.read_events() == events
    stale = client.post('/review/decision-graph', data={**data, 'command_id': 'another-command'})
    assert stale.status_code == 400
    assert state._envelope(sid) == saved

    assert client.get(response.headers['location']).status_code == 200
    restarted = _console(tmp_path, production_console=production_console)
    assert restarted._envelope(sid)['decision_graph'] == saved['decision_graph']
    review = client.get('/review/decision-graph', params=dict(document=sid))
    confirm = form_data(review, '/review/decision-graph')
    confirm.update(action='confirm', reason='De volledige interpretatie is gecontroleerd.')
    accepted = client.post('/review/decision-graph', data=confirm, follow_redirects=False)
    assert accepted.status_code == 400 and 'decision_graph_passage_review_required' in accepted.text
    assert state._envelope(sid) == saved

def test_source_record_keeps_its_existing_source_context_owner(tmp_path, *, production_app, production_console):
    from tests.test_source_context_review_v1 import _system as context_system
    from src.source_accountability_v1 import is_source_record
    state, _, _, source, _, command = context_system(tmp_path,
        console=production_console(root=tmp_path, processing_binder=bind_fixture_selections))
    assert is_source_record(source)
    sid = command['snapshot_id']
    before = deepcopy(state.snapshot_objects(sid))
    client = TestClient(production_app(state))
    client.post('/login', data=dict(username='bert', password='bert-secret'))
    page = client.get('/source-selection', params=dict(document=sid, object=source['object_id'], task='repair'))
    assert page.status_code == 200
    assert 'action="/review/resolve"' not in page.text
    assert 'Brongebruik bepalen of bronbewijs herstellen in Vorming' in page.text
    assert state.snapshot_objects(sid) == before
