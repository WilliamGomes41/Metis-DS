"""#862: concrete evidence links reuse the authorized owner without GET writes.

# release-control-evidence: scope/belofte toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import pytest

from src.settings.insight_v1 import _diagnosis_actions_html
from src.vorming.processing_diagnostics_v1 import processing_diagnostics, processing_diagnostic_rows
from src.publication.publish_readiness_ui_v1 import _blocker_view
from src.review.review_ledger import read_events
from tests.production_support import restart_production
from tests.test_document_diagnosis_redesign_v1 import _system, _client
from tests.test_insight_diagnostics_navigation_v1 import Links


def test_diagnosis_opens_each_actual_passage_and_no_get_changes_native_work(tmp_path, *, production_console, production_app):
    console, sid = _system(tmp_path, production_console=production_console)
    browser = _client(console, production_app, 'reviewer.854')
    def state():
        fresh = restart_production(console)
        return deepcopy((fresh._envelope(sid), fresh.snapshot_objects(sid), fresh.objects_revision(sid),
                         fresh.object_review_bindings(sid), read_events(fresh._ledger_path)))
    before = state()
    diagnosis = browser.get('/inzicht/document', params={'document': sid})
    assert diagnosis.status_code == 200
    actions = diagnosis.text.split('<section id="acties">')[1].split('</section>')[0]
    links = set(Links(actions).hrefs)
    expected = {r['object_id']: r['candidate_text'] for r in processing_diagnostic_rows(console.snapshot_objects(sid))}
    assert len(expected) >= 2
    assert {parse_qs(urlsplit(url).query)['object'][0] for url in links} == set(expected)
    for url in links:
        query = parse_qs(urlsplit(url).query)
        assert urlsplit(url).path == '/source-selection' and query['document'] == [sid]
        owner = browser.get(url)
        assert owner.status_code == 200, owner.text
        assert '<h1>Vorming</h1>' in owner.text
        from html import escape
        assert escape(expected[query['object'][0]]) in owner.text
    assert state() == before

    # Audit the installed pages, including their response transforms, rather
    # than inferring an editable entrance from a historical POST URL.
    from html.parser import HTMLParser
    class Forms(HTMLParser):
        def __init__(self, html):
            super().__init__()
            self.actions = set()
            self.feed(html)

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'form' and attrs.get('method', 'get').lower() == 'post':
                self.actions.add(attrs.get('action'))

    uploader = _client(console, production_app, 'uploader.854')
    for path, allowed in [('/', {'/logout'}), ('/tree', {'/logout', '/tree/move', '/tree/promote', '/documents/delete'}),
                          ('/ingest', {'/logout', '/ingest'}),
                          ('/publish?document=' + sid, {'/logout', '/publish', '/publish/withdraw'}),
                          ('/inzicht/document?document=' + sid, {'/logout', '/inzicht/document/weergavecontrole'})]:
        response = uploader.get(path)
        assert response.status_code == 200, response.text
        assert Forms(response.text).actions <= allowed
    assert state() == before


def test_unknown_reason_and_missing_identity_are_evidence_not_invented_editor_ids():
    objects = [{'object_id': 'actual', 'metadata': {'admission': {'gate_result': 'blocked', 'reason_codes': []}}},
               {'metadata': {'admission': {'gate_result': 'blocked', 'reason_codes': ['unknown']}}}]
    html = _diagnosis_actions_html(processing_diagnostics(objects), 'source & snapshot', objects)
    links = Links(html).hrefs
    assert len(links) == 1
    assert parse_qs(urlsplit(links[0]).query) == {'document': ['source & snapshot'], 'object': ['actual'], 'task': ['repair']}
    assert 'blocked-1' not in html


@pytest.mark.parametrize(('code', 'path', 'task'), [
    ('source_passage_review_incomplete', '/source-selection', None),
    ('review_disposition_inconsistent', '/source-selection', 'repair'),
    ('review_repair_incomplete', '/source-selection', 'repair'),
    ('source_formation_incomplete', '/source-selection', None),
    ('pre_review_processing_incomplete', '/source-selection', None),
    ('review_work_incomplete', '/review', None),
    ('four_eyes_required', '/review', None),
    ('second_named_reviewer_required', '/review', None),
])
def test_publication_explains_blocker_and_opens_its_existing_owner(code, path, task):
    view = _blocker_view(code, 'snapshot & exact')
    url = urlsplit(view['recovery_href'])
    assert url.path == path
    assert parse_qs(url.query) == {'document': ['snapshot & exact'], **({'task': [task]} if task else {})}
    assert view['code'] == code


def test_unknown_publication_gate_does_not_invent_a_human_task():
    assert _blocker_view('unknown_integrity_gate', 'snapshot')['recovery_href'] is None


def _publication_owner(client, sid, code):
    publication = client.get('/publish', params={'document': sid})
    assert publication.status_code == 200
    blocker = publication.text.split(f'data-blocker-code="{code}">', 1)[1].split('</li>', 1)[0]
    links = Links(blocker).hrefs
    assert len(links) == 1
    return links[0]


def test_publication_source_blocker_opens_its_blocked_candidates(tmp_path, *, production_console, production_app):
    console, sid = _system(tmp_path, production_console=production_console)
    readiness = console.publication_readiness(sid)
    blocked = {row['object_id'] for row in processing_diagnostic_rows(console.snapshot_objects(sid))}
    assert blocked and blocked <= set(readiness['unresolved_source_passage_ids'])
    publisher = _client(console, production_app, 'uploader.854')
    href = _publication_owner(publisher, sid, 'source_passage_review_incomplete')
    reviewer = _client(console, production_app, 'reviewer.854')
    before = deepcopy((console.snapshot_objects(sid), console.objects_revision(sid),
                       console.object_review_bindings(sid), read_events(console._ledger_path)))
    owner = reviewer.get(href)
    assert owner.status_code == 200
    owner_links = [parse_qs(urlsplit(url).query) for url in Links(owner.text).hrefs]
    assert blocked <= {q['object'][0] for q in owner_links if q.get('document') == [sid] and q.get('object')}
    assert (console.snapshot_objects(sid), console.objects_revision(sid),
            console.object_review_bindings(sid), read_events(console._ledger_path)) == before


def test_publication_repair_blocker_opens_requested_revision(tmp_path, *, production_console, production_app):
    from fastapi.testclient import TestClient
    from tests.test_closed_review_loop_v1 import _system as setup, _review
    console, _, reviewer, sid, ids = setup(tmp_path, production_console=production_console)
    console.create_account(username='publisher.862', password='publisher-862-secret', roles=('publisher',))
    oid = ids[0]
    _review(console, reviewer, sid, oid, decision='revise', suitability='mist_context',
            eindoordeel='goedkeuren_na_correctie', comment='Context ontbreekt.')
    readiness = console.publication_readiness(sid)
    assert oid in readiness['review_repair_object_ids']
    publisher = TestClient(production_app(console), base_url='https://testserver')
    assert publisher.post('/login', data={'username': 'publisher.862', 'password': 'publisher-862-secret'},
                          follow_redirects=False).status_code == 303
    href = _publication_owner(publisher, sid, 'review_repair_incomplete')
    browser = TestClient(production_app(console), base_url='https://testserver')
    assert browser.post('/login', data={'username': 'bert', 'password': 'bert-secret'},
                        follow_redirects=False).status_code == 303
    before = deepcopy((console.snapshot_objects(sid), console.objects_revision(sid),
                       console.object_review_bindings(sid), read_events(console._ledger_path)))
    owner = browser.get(href)
    assert owner.status_code == 200
    repair_links = [url for url in Links(owner.text).hrefs if parse_qs(urlsplit(url).query).get('object') == [oid]]
    assert repair_links, 'The publication repair link must expose the requested revision'
    assert all(parse_qs(urlsplit(url).query).get('object') != [ids[1]] for url in Links(owner.text).hrefs)
    editor = browser.get(next(url for url in repair_links if urlsplit(url).path == '/source-selection'))
    assert editor.status_code == 200 and 'data-formation-repair' in editor.text
    assert oid in editor.text
    assert browser.get(href).status_code == 200
    assert publisher.get(href).status_code == 403
    assert (console.snapshot_objects(sid), console.objects_revision(sid),
            console.object_review_bindings(sid), read_events(console._ledger_path)) == before
