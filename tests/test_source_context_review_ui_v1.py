"""Passage-first context decisions through the real HTTP/domain boundary.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""

from copy import deepcopy
from html.parser import HTMLParser

from fastapi.testclient import TestClient

from tests.test_source_context_review_v1 import _system


class Forms(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            assert self.current is None, 'Context forms must not nest inside knowledge review'
            self.current = {'attrs': attrs, 'inputs': []}
            self.forms.append(self.current)
        if tag == 'input' and self.current is not None:
            self.current['inputs'].append(attrs)

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


def _client(state, username='bert', password='bert-secret', *, production_app):
    client = TestClient(production_app(state))
    assert client.post('/login', data={'username': username, 'password': password}, follow_redirects=False).status_code == 303
    return client


def test_historical_context_is_readable_without_an_editor(tmp_path, production_console, production_app):
    state, _, _, source, target, command = _system(tmp_path, production_console=production_console)
    state.confirm_source_context(**command)
    before = deepcopy(state.snapshot_objects(command['snapshot_id']))
    client = _client(state, production_app=production_app)
    page = client.get('/review', params={'document': command['snapshot_id'], 'object': target['object_id']})
    assert page.status_code == 200
    assert source['content']['clean_text'] in page.text and command['reason'] in page.text
    assert not any(form['attrs'].get('action') == '/review/source-context' for form in Forms(page.text).forms)
    assert state.snapshot_objects(command['snapshot_id']) == before
