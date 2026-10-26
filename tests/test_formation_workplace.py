"""#859-A: one workspace, unchanged native PostgreSQL command authority.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from html.parser import HTMLParser

from fastapi.testclient import TestClient

from tests.production_support import restart_production
from tests.test_availability_repair import bind, drain, login
from tests.test_review_formation_problems import received, execute, FIRST, SECOND


class StartForm(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {} if attrs.get('action') == '/source-selection/start' else None
            if self.current is not None:
                self.forms.append(self.current)
        if tag == 'input' and self.current is not None and attrs.get('name'):
            self.current[attrs['name']] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


def durable(console, sid):
    return deepcopy((console._envelope(sid), console.snapshot_objects(sid), console.object_review_bindings(sid)))


def test_one_start_form_and_legacy_navigation_do_not_start_work(tmp_path, production_console, monkeypatch):
    console, sid, author, _, calls, _, _ = received(tmp_path, production_console, monkeypatch)
    client = TestClient(console._metis_test_application)
    login(client)
    before = durable(console, sid)
    overview = client.get('/source-selection')
    assert overview.status_code == 200 and not StartForm(overview.text).forms
    assert 'href="/source-selection" aria-current="page">Vorming</a>' in overview.text
    assert 'href="/formation-problems"' not in overview.text
    legacy = client.get('/formation-problems', params={'document': sid, 'offset': 100}, follow_redirects=False)
    assert legacy.status_code == 303
    assert legacy.headers['location'] == f'/source-selection?document={sid}&offset=100'
    assert not StartForm(legacy.text).forms
    assert durable(console, sid) == before and not calls
    reads = []
    original = console.processing_status
    def counted(*args, **kwargs):
        reads.append(args[0])
        return original(*args, **kwargs)
    monkeypatch.setattr(console, 'processing_status', counted)
    page = client.get('/source-selection', params={'document': sid})
    forms = StartForm(page.text).forms
    assert page.status_code == 200 and '<h1>Vorming</h1>' in page.text
    assert 'Nog geen verwerkingsresultaat' in page.text
    assert len(forms) == 1 and forms[0]['document'] == sid
    assert forms[0]['expected_revision'] == console.objects_revision(sid)
    assert reads == [sid], 'Combined details must not repeat the status/deep check'
    assert durable(console, sid) == before and not calls


def test_partial_resume_uses_rendered_command_after_restart(tmp_path, production_console, monkeypatch):
    console, sid, author, _, calls, mode, provider = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'initial')
    before = durable(console, sid)
    first = next(o for o in before[1] if o.get('proposed_object_type') == 'recommendation')
    assert first['content']['clean_text'] == FIRST
    console = restart_production(console)
    bind(console, provider)
    app = console._metis_test_application
    with TestClient(app, base_url='https://testserver') as client:
        login(client)
        page = client.get('/formation-problems', params={'document': sid})
        assert page.status_code == 200 and page.url.path == '/source-selection'
        assert SECOND in page.text and 'Bekijk en behandel dit bronstuk' in page.text
        assert 'Hervatten</button>' in page.text and 'Naar Review' in page.text
        forms = StartForm(page.text).forms
        assert len(forms) == 1 and durable(console, sid) == before and len(calls) == 3
        form = forms[0]
        stale = client.post('/source-selection/start', data={**form, 'expected_revision': 'stale'}, follow_redirects=False)
        assert stale.status_code == 400 and durable(console, sid) == before
        mode['broken'] = False
        posted = client.post('/source-selection/start', data=form, follow_redirects=False)
        assert posted.status_code == 303 and posted.headers['location'] == f'/source-selection?document={sid}'
        drain(client, app)
        assert len(calls) == 4 and [b['text'] for b in calls[-1]['source_blocks']] == [SECOND]
        again = client.post('/source-selection/start', data=form, follow_redirects=False)
        assert again.status_code == 303 and len(calls) == 4
        refreshed = client.get(posted.headers['location'])
        assert refreshed.status_code == 200 and 'Geen open vormingsproblemen' in refreshed.text
        assert not StartForm(refreshed.text).forms
        current = console.snapshot_objects(sid)
        assert next(o for o in current if o['object_id'] == first['object_id']) == first
        assert console.object_review_bindings(sid) == before[2]
        assert not console.publication_readiness(sid)['publish_allowed']
