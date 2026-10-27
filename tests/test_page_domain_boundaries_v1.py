"""#862: concrete evidence links reuse the authorized owner without GET writes.

# release-control-evidence: scope/belofte toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import pytest

from src.insight_v1 import _diagnosis_actions_html
from src.processing_diagnostics_v1 import processing_diagnostics, processing_diagnostic_rows
from src.publish_readiness_ui_v1 import _blocker_view
from src.review_ledger import read_events
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
    ('source_passage_review_incomplete', '/source-selection', 'disposition'),
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
