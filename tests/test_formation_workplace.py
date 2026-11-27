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


def test_annotation_entry_and_legacy_navigation_do_not_start_work(tmp_path, production_console, monkeypatch):
    console, sid, author, _, calls, _, _ = received(tmp_path, production_console, monkeypatch)
    client = TestClient(console._metis_test_application)
    login(client)
    before = durable(console, sid)
    overview = client.get('/source-selection')
    assert overview.status_code == 200 and not StartForm(overview.text).forms
    assert 'href="/source-selection" aria-current="page">Vorming</a>' in overview.text
    assert 'href="/formation-problems"' not in overview.text
    legacy = client.get('/formation-problems', params={'document': sid, 'offset': 100}, follow_redirects=False)
    assert legacy.status_code == 404
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
    # #1168: the fresh source shows the manual card; Annoteren prepares the source by POST.
    assert 'Bekijk status bouwopdrachten' in page.text
    assert not forms
    assert '<form method="post" action="/annotations/source">' in page.text and '>Annoteren</button>' in page.text
    # The manual card needs no processing status; any other card reads it once.
    assert reads in ([], [sid]), 'Combined details must not repeat the status/deep check'
    assert durable(console, sid) == before and not calls


def test_historical_partial_formation_cannot_resume_through_the_card_after_restart(tmp_path, production_console, monkeypatch):
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
        page = client.get('/source-selection', params={'document': sid})
        assert page.status_code == 200 and page.url.path == '/source-selection'
        assert 'Bekijk status bouwopdrachten' in page.text
        assert not StartForm(page.text).forms
        assert 'Vormingsproblemen' not in page.text
        for revision in ('stale', console.objects_revision(sid)):
            refused = client.post('/source-selection/start', data={'document':sid, 'expected_revision':revision,
                                  'command_id':'old-retry'}, follow_redirects=False)
            assert refused.status_code == 404
        assert durable(console, sid) == before and len(calls) == 3
        assert not console.publication_readiness(sid)['publish_allowed']


def test_shared_source_inputs_keep_the_same_processing_decision(tmp_path, production_console, monkeypatch):
    from src.vorming.source_preparation_context_v1 import stored_extraction
    from src.vorming import processing_retry_v1
    console, sid, author, _, _, _, _ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'partial')
    instant = processing_retry_v1.now()
    monkeypatch.setattr(processing_retry_v1, 'now', lambda: instant)
    before = durable(console, sid)
    ordinary = console.processing_status(sid, actor_id=author)
    fragments = stored_extraction(console._envelope(sid))
    captured = console.processing_status(sid, actor_id=author, formation_fragments=fragments)
    assert captured == ordinary
    assert durable(console, sid) == before
