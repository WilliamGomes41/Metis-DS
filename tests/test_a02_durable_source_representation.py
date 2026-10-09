"""A02 durable representation acceptance, installed query/restart proof.
# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json
import re

import pytest
from fastapi.testclient import TestClient
from tests.test_availability_repair import accounts, bind, provider, login, installed_app
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401

ROUTES = [('/publish', {}), ('/review', {'work': 'all'}), ('/review', {}),
          ('/review', {'task': 'disposition'}), ('/review', {'task': 'individual'}),
          ('/review', {'task': 'detail'}), ('/review/bronpassage', {})]


def console_at(root, config=None):
    if config is not None:
        from tests.test_review_batch_atomic_postgres import _console
        return _console(root, config)
    from src.review_closure_v1 import ReviewClosureConsole
    return ReviewClosureConsole(root=root, source_store=root/'sources', runtime=root/'runtime')


@pytest.fixture(params=['local', 'postgres'])
def representation_backend(request):
    return request.getfixturevalue('workflow_postgres') if request.param == 'postgres' else None


def ingest(console):
    author, reviewer = accounts(console)
    def select(url, headers, payload, timeout):
        data = json.loads(payload['input'][1]['content'])
        if not data.get('selection_targets') and any('Gebruik geen zalf.' in b['text'] for b in data['source_blocks']):
            return provider(url, headers, payload, timeout)
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps({'objects': [], 'relations': [], 'abstain_reason': 'uncertain'})}]}]}
    bind(console, select)
    texts = ['Gebruik geen zalf.', *[f'Bronpassage {i} bevat informatie voor menselijke beoordeling.' for i in range(30)]]
    sid = console.ingest(actor_id=author, filename='fixture.html',
        data=('<html><body><h1>Adviezen</h1>'+''.join(f'<p>{t}</p>' for t in texts)+'</body></html>').encode(),
        content_type='text/html', ingest_kind='new', title='Fixture', version='1', date='2026-10-09',
        live_url='', class_='richtlijn', family='fixture', named_reviewers=[author, reviewer])['snapshot_id']
    return sid, author, reviewer


def query_for(console, sid, path, params):
    from src.source_accountability_v1 import is_source_record
    objects = console.snapshot_objects(sid)
    query = dict(params)
    if path != '/publish' and (params.get('task') or path == '/review/bronpassage'):
        query['document'] = sid
    if params.get('task') == 'detail':
        query.pop('task')
        query['object'] = next(o['object_id'] for o in objects if o.get('proposed_object_type') == 'recommendation')
    if path == '/review/bronpassage':
        query['object'] = next(o['object_id'] for o in objects if is_source_record(o))
    return query


def normalize(text):
    return re.sub(r'(name="(?:command_id|interaction_id)" value=")[^"]+', r'\1COMMAND', text)


@pytest.mark.parametrize('path,params', ROUTES)
def test_a02_zero_reconstruction_installed_routes_and_restart(representation_backend, tmp_path, monkeypatch, path, params):
    console = console_at(tmp_path, representation_backend)
    sid, author, reviewer = ingest(console)
    query = query_for(console, sid, path, params)
    with TestClient(installed_app(console)) as client:
        login(client)
        expected = client.get(path, params=query)
        assert expected.status_code == 200, expected.text

    import src.semantic_passage_v1 as semantic
    import src.knowledge_materialisation_v1 as materialisation
    calls = []
    original = semantic._reconstructed_blocks
    def counted(rows):
        calls.append(1)
        return original(rows)
    monkeypatch.setattr(semantic, '_reconstructed_blocks', counted)
    monkeypatch.setattr(materialisation, '_reconstructed_blocks', counted)
    for current in (console, console_at(tmp_path, representation_backend)):
        def forbidden(*args, **kwargs):
            pytest.fail('A02_QUERY_EXECUTED_SOURCE_PROCESSING')
        monkeypatch.setattr(current, '_extract', forbidden)
        monkeypatch.setattr(current, '_fragments_and_spec', forbidden)
        bind(current, forbidden)
        # Zero reconstruction must not depend on a ContextVar wrapper.
        monkeypatch.setattr(materialisation, '_source_reconstruction',
            type('DisabledScope', (), {'get': lambda self: None, 'set': lambda self, value: None,
                                       'reset': lambda self, token: None})())
        calls.clear()
        with TestClient(installed_app(current)) as client:
            login(client)
            response = client.get(path, params=query)
            assert response.status_code == 200, response.text
            assert normalize(response.text) == normalize(expected.text)
            assert not calls, ('A02_DURABLE_READ_RECONSTRUCTED', path, len(calls))
            login(client, 'reviewer')
            if path == '/publish':
                assert client.get(path, params=query).status_code == 403
        print('A02_DURABLE_READ='+json.dumps({'backend': 'postgres' if representation_backend else 'local',
              'route': path, 'reconstructions': len(calls), 'restart': current is not console}))
