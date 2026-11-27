"""A15: navigation through the actual production PostgreSQL application.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from tests.semantic_fixture_support import bind_fixture_selections
from copy import deepcopy
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from tests.test_source_context_review_v1 import _system


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
def installed(tmp_path, production_console, production_app):
    initial = production_console(root=tmp_path, processing_binder=bind_fixture_selections)
    _, researcher, reviewer, source, target, command = _system(tmp_path, console=initial)
    state = production_console(root=tmp_path, processing_binder=bind_fixture_selections)
    app = production_app(state)
    client = TestClient(app, base_url='https://testserver')
    assert client.post('/login', data={'username': 'bert', 'password': 'bert-secret'},
                       follow_redirects=False).status_code == 303
    return client, state, researcher, reviewer, source, target, command


def test_old_context_address_is_closed_for_every_actor(installed):
    client, state, researcher, reviewer, source, target, command = installed
    sid = command['snapshot_id']
    before = deepcopy(state.snapshot_objects(sid))
    for username, password in ((None, None), ('bert', 'bert-secret'), ('anne', 'anne-secret')):
        actor = TestClient(client.app, base_url='https://testserver')
        if username:
            assert actor.post('/login', data={'username': username, 'password': password}, follow_redirects=False).status_code == 303
        params = dict(document=sid, object=source['object_id'], context_target=target['object_id'])
        for route in ('/review', '/source-selection'):
            refused = actor.get(route, params=params, follow_redirects=False)
            assert refused.status_code == 404 and 'location' not in refused.headers
        assert actor.post('/review/source-context', data=command).status_code == 404
    assert state.snapshot_objects(sid) == before
