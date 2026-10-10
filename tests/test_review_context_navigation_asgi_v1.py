"""A15: navigation through the complete installed application, with local stores.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from html.parser import HTMLParser
import os
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from src.console_asgi import build_app
from src.operations_console_app import _source_context_panel
from src.source_context_review_v1 import links_of
from tests.test_source_context_review_v1 import _system
from tests.test_source_context_review_ui_v1 import Forms, _link_form, _payload


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.hrefs = []
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == 'a' and 'href' in attrs:
            self.hrefs.append(attrs['href'])


@pytest.fixture
def installed(tmp_path, monkeypatch):
    # Isolate infrastructure config, without replacing any installer/route/backend.
    for key in list(os.environ):
        if key.startswith(('METIS_', 'CONSOLE_', 'WEBSITE_')):
            monkeypatch.delenv(key)
    _, researcher, reviewer, source, target, command = _system(tmp_path)
    monkeypatch.setenv('CONSOLE_DATA_ROOT', str(tmp_path))
    monkeypatch.setenv('CONSOLE_SOURCE_STORE', str(tmp_path / 'sources'))
    monkeypatch.setenv('CONSOLE_RUNTIME', str(tmp_path / 'runtime'))
    app = build_app()
    state = app.state.operations_kernel
    client = TestClient(app, base_url='https://testserver')
    assert client.post('/login', data={'username': 'bert', 'password': 'bert-secret'},
                       follow_redirects=False).status_code == 303
    return client, state, researcher, reviewer, source, target, command


def _context_link(page, source_id, target_id=''):
    for href in Links(page.text).hrefs:
        query = parse_qs(urlsplit(href).query)
        if (query.get('object') == [source_id]
                and query.get('context_target', ['']) == [target_id]
                and (target_id or query.get('context_mode') == ['source'])):
            return href
    raise AssertionError('Expected generated source-context link')


def test_installed_context_choice_save_redirect_reopen_and_add_target(installed):
    client, state, _, _, source, target, command = installed
    sid, tid, soid = command['snapshot_id'], target['object_id'], source['object_id']
    before = deepcopy(state.snapshot_objects(sid))
    page = client.get('/review', params={'document': sid, 'object': tid})
    assert page.status_code == 200
    choice = client.get(_context_link(page, soid, tid))
    assert choice.status_code == 200
    data = _payload(_link_form(choice))
    assert data['target_object_ids'] == [tid]
    assert data['return_object_id'] == tid
    assert state.snapshot_objects(sid) == before
    saved = client.post('/review/source-context', data=data, follow_redirects=False)
    assert saved.status_code == 303
    location = saved.headers['location']
    assert location.startswith('/review?')
    assert parse_qs(urlsplit(location).query)['object'] == [tid]
    after = client.get(location)
    assert after.status_code == 200
    assert 'Het contextbesluit is opgeslagen' in after.text
    assert 'Koppeling aanpassen of verwijderen' in after.text
    assert any(link['source_object_id'] == soid for link in links_of(
        next(row for row in state.snapshot_objects(sid) if row['object_id'] == tid)))
    persisted = deepcopy(state.snapshot_objects(sid))
    reopened = client.get('/review', params={'document': sid, 'object': tid})
    assert 'Koppeling aanpassen of verwijderen' in reopened.text
    assert 'Het contextbesluit is opgeslagen' not in reopened.text
    assert state.snapshot_objects(sid) == persisted
    other = next(row for row in persisted if 'bespreekt passende ondersteuning' in
                 row.get('content', {}).get('clean_text', ''))
    extra = client.get(_context_link(reopened, soid, tid))
    extra_form = _link_form(extra)
    extra_data = _payload(extra_form)
    assert extra_data['target_object_ids'] == [tid]
    # Select an additional checkbox actually offered by the generated form.
    additional = next(field for field in extra_form['inputs']
                      if field.get('name') == 'target_object_ids'
                      and field.get('value') == other['object_id'])
    extra_data['target_object_ids'].append(additional['value'])
    assert set(extra_data['target_object_ids']) == {tid, other['object_id']}
    assert extra_data['return_object_id'] == tid
    extra_saved = client.post('/review/source-context', data=extra_data, follow_redirects=False)
    assert extra_saved.status_code == 303
    assert client.get(extra_saved.headers['location']).status_code == 200
    for target_id in extra_data['target_object_ids']:
        row = next(row for row in state.snapshot_objects(sid) if row['object_id'] == target_id)
        assert any(link['source_object_id'] == soid for link in links_of(row))


def test_installed_source_mode_invalid_target_and_failed_posts(installed):
    client, state, _, _, source, target, command = installed
    sid, tid, soid = command['snapshot_id'], target['object_id'], source['object_id']
    before = deepcopy(state.snapshot_objects(sid))
    ordinary = client.get('/review', params={'document': sid, 'object': tid})
    assert 'data-source-context-form' not in ordinary.text  # No label heuristic.
    source_mode = client.get(_context_link(ordinary, tid))
    assert source_mode.status_code == 200
    assert _link_form(source_mode)
    invalid = client.get('/review', params={'document': sid, 'object': soid,
                                           'context_target': 'nonexistent-target'})
    assert invalid.status_code == 400
    choice = client.get(_context_link(ordinary, soid, tid))
    data = _payload(_link_form(choice), reason='Mijn gecontroleerde contextkeuze')
    bad = client.post('/review/source-context', data={**data, 'role': ''}, follow_redirects=False)
    assert bad.status_code == 400
    assert 'Je keuzes zijn niet opgeslagen' in bad.text
    retry = _payload(_link_form(bad))
    assert retry['target_object_ids'] == [tid]
    assert retry['return_object_id'] == tid
    assert data['reason'] in bad.text
    stale = client.post('/review/source-context', data={**data, 'snapshot_revision': 'stale'},
                        follow_redirects=False)
    assert stale.status_code == 409
    retry = _payload(_link_form(stale))
    assert retry['target_object_ids'] == [tid]
    assert retry['return_object_id'] == tid
    assert retry['snapshot_revision'] == state.objects_revision(sid)
    assert data['reason'] in stale.text
    assert state.snapshot_objects(sid) == before


def test_installed_navigation_access_redirect_and_workboard_contract(installed):
    client, state, researcher, _, source, target, command = installed
    sid, tid, soid = command['snapshot_id'], target['object_id'], source['object_id']
    before = deepcopy(state.snapshot_objects(sid))
    for signal in ('', 'true', 'YES', '1', 'yes'):
        response = client.get('/review', params={'document': sid, 'object': tid, 'context_saved': signal})
        assert response.status_code == 200
        assert ('Het contextbesluit is opgeslagen' in response.text) == (signal == 'yes')
        assert 'Koppeling aanpassen of verwijderen' not in response.text
    board = client.get('/review', params={'document': sid, 'q': 'Zorg', 'page': 1,
                                        'theme': '', 'context_mode': 'source'})
    assert board.status_code == 200
    assert '/review?' in board.text
    assert client.get('/review', params={'document': sid, 'work': 'invalid'}).status_code == 400
    detail = client.get('/review', params={'document': sid, 'object': tid, 'q': 'observatie', 'page': 2})
    assert '/review?document=' in detail.text and 'q=observatie&amp;page=2' in detail.text
    choice = client.get(_context_link(detail, soid, tid))
    data = _payload(_link_form(choice))
    anonymous = TestClient(client.app, base_url='https://testserver')
    assert anonymous.get('/review', params={'document': sid, 'object': soid,
        'context_target': tid, 'context_mode': 'source', 'context_saved': 'yes'},
        follow_redirects=False).status_code == 401
    outsider = TestClient(client.app, base_url='https://testserver')
    assert outsider.post('/login', data={'username': researcher['username'], 'password': 'anne-secret'},
                         follow_redirects=False).status_code == 303
    denied = outsider.get('/review', params={'document': sid, 'object': soid,
        'context_target': tid, 'context_mode': 'source', 'context_saved': 'yes'}, follow_redirects=False)
    assert denied.status_code == 403
    assert 'data-source-context-form' not in denied.text
    assert outsider.post('/review/source-context', data=data, follow_redirects=False).status_code == 403
    state.create_account(username='unassigned', password='unassigned-secret', roles=('reviewer',))
    unassigned = TestClient(client.app, base_url='https://testserver')
    assert unassigned.post('/login', data={'username': 'unassigned', 'password': 'unassigned-secret'},
                           follow_redirects=False).status_code == 303
    redirect = unassigned.get('/review', params={'document': sid, 'object': soid,
        'context_target': tid, 'context_mode': 'source', 'context_saved': 'yes'}, follow_redirects=False)
    assert redirect.status_code == 303
    destination = urlsplit(redirect.headers['location'])
    assert not destination.scheme and not destination.netloc
    assert destination.path == '/review/trajectory'
    assert parse_qs(destination.query) == {'document': [sid]}
    trajectory = unassigned.get(redirect.headers['location'])
    assert trajectory.status_code == 200
    assert 'data-source-context-form' not in trajectory.text
    refused = unassigned.post('/review/source-context', data=data, follow_redirects=False)
    assert refused.status_code == 400  # Existing non-assignment error mapping.
    assert 'Je bent niet aangewezen als beoordelaar voor dit document' in refused.text
    assert state.snapshot_objects(sid) == before
    external = client.post('/review/source-context', data={**data, 'return_object_id': 'https://example.com'},
                           follow_redirects=False)
    assert external.status_code == 303
    assert external.headers['location'].startswith('/review?')
    assert 'example.com' not in external.headers['location']


def test_context_links_keep_url_values_inside_html_attributes(installed):
    _, state, _, _, source, target, command = installed
    sid = command['snapshot_id']
    rows = deepcopy(state.snapshot_objects(sid))
    # Presentation fixture only: exercise a valid selected target containing
    # delimiters, without altering persisted identities or bypassing GET validation.
    target_id = '\"><svg onload=alert(1)>&context_mode=source'
    next(row for row in rows if row['object_id'] == target['object_id'])['object_id'] = target_id
    panel = _source_context_panel(source, rows, sid, state.objects_revision(sid),
                                  context_target=target_id, source_mode=True)
    parsed = Links(panel)
    assert not any(tag in {'svg', 'script', 'img'} or any(key.startswith('on') for key in attrs)
                   for tag, attrs in parsed.tags)
    assert '&amp;object=' in panel and '&amp;amp;' not in panel
    back = next(href for href in parsed.hrefs
                if parse_qs(urlsplit(href).query).get('object') == [target_id])
    assert urlsplit(back).path == '/review'
    assert parse_qs(urlsplit(back).query) == {'document': [sid], 'object': [target_id]}
    fields = _payload(next(form for form in Forms(panel).forms
                           if 'data-source-context-form' in form['attrs']))
    assert fields['return_object_id'] == target_id
