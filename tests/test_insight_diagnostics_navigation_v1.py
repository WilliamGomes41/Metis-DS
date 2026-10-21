"""Diagnostics have one home while existing evidence and role boundaries survive.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.review_ledger import read_events
from tests.test_d5_4_review_interaction_evidence import PASSWORD, _system
from tests.test_review_context_navigation_asgi_v1 import installed  # noqa: F401


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.hrefs = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'href' in attrs:
            self.hrefs.append(attrs['href'])


def login(app, username):
    client = TestClient(app, base_url='https://testserver')
    assert client.post('/login', data={'username': username, 'password': PASSWORD}, follow_redirects=False).status_code == 303
    return client


def test_installed_work_pages_lead_to_one_document_diagnosis_without_writes(installed):
    client, state, _, _, _, _, command = installed
    sid = command['snapshot_id']
    before = deepcopy(state.snapshot_objects(sid)), state.objects_revision(sid), read_events(state._ledger_path)
    source = client.get('/source-selection', params={'document': sid})
    assert source.status_code == 200
    links = Links(source.text).hrefs
    diagnosis = [url for url in links if urlsplit(url).path == '/inzicht/document']
    assert len(diagnosis) == 1
    assert parse_qs(urlsplit(diagnosis[0]).query)['document'] == [sid]
    assert not any(urlsplit(url).path in {'/source-selection/blockage', '/source-selection/processing-trace'} for url in links)
    assert source.text.count('Naar Review</a>') == 1
    page = client.get(diagnosis[0])
    assert page.status_code == 200, page.text
    for section in ('id="verwerking"', 'id="passages"', 'id="bewijs"', 'Reviewinteracties'):
        assert section in page.text
    assert '/inzicht/document/verwerkingsspoor?' in page.text
    assert '/inzicht/document/verwerkingsbewijs?' in page.text
    assert '/inzicht/document/publicatiebewijs?' not in page.text  # reviewer is not publisher
    for path in ('/review', '/tree'):
        work = client.get(path)
        assert work.status_code == 200
        assert '/inzicht/document?' in work.text
        assert 'class="processing-diagnostics"' not in work.text
    assert before == (state.snapshot_objects(sid), state.objects_revision(sid), read_events(state._ledger_path))


def test_diagnosis_roles_keep_processing_passages_and_publication_evidence_separate(tmp_path):
    state, users, sid, _ = _system(tmp_path)
    outsider = state.create_account(username='outsider.diagnosis', password=PASSWORD, roles=('reviewer',))
    publisher = state.create_account(username='publisher.diagnosis', password=PASSWORD, roles=('publisher',))
    app = create_console_app(state)
    assert TestClient(app).get('/inzicht/document', params={'document': sid}).status_code == 401
    other = login(app, outsider['username'])
    assert other.get('/inzicht/document', params={'document': sid}).status_code == 400
    missing = other.get('/inzicht/document')
    assert missing.status_code == 400 and 'text/html' in missing.headers['content-type']
    assert not any(parse_qs(urlsplit(url).query).get('document') == [sid]
                   for url in Links(other.get('/tree').text).hrefs
                   if urlsplit(url).path == '/inzicht/document')
    reviewer = login(app, users['reviewer_a']['username'])
    researcher = login(app, users['researcher']['username'])
    publisher_client = login(app, publisher['username'])
    for client, has_passages, has_publication in ((reviewer, True, False), (researcher, False, False), (publisher_client, False, True)):
        page = client.get('/inzicht/document', params={'document': sid})
        assert page.status_code == 200, page.text
        assert ('/inzicht/document/passages?' in page.text) is has_passages
        assert ('/inzicht/document/publicatiebewijs?' in page.text) is has_publication
    publisher_rows = publisher_client.get('/inzicht/api/documents').json()['documents']
    assert publisher_rows[0]['blocked'] is None and publisher_rows[0]['reasons'] == []
    for path in ('passages', 'diagnostiek', 'detaildiagnostiek', 'verwerkingsbewijs'):
        assert reviewer.get('/inzicht/document/' + path, params={'document': sid}).status_code == 200
        assert researcher.get('/inzicht/document/' + path, params={'document': sid}).status_code == 400
        assert publisher_client.get('/inzicht/document/' + path, params={'document': sid}).status_code == 403
        assert other.get('/inzicht/document/' + path, params={'document': sid}).status_code == 400
    assert publisher_client.get('/inzicht/document/publicatiebewijs', params={'document': sid}).status_code == 200
    assert reviewer.get('/inzicht/document/publicatiebewijs', params={'document': sid}).status_code == 403
    assert publisher_client.get('/inzicht/document/verwerkingsspoor', params={'document': sid}).status_code == 403


@pytest.mark.parametrize(('old', 'new'), [
    ('/settings/technical/processing', '/inzicht/document'),
    ('/settings/technical/exports', '/inzicht/document'),
    ('/source-selection/processing-trace', '/inzicht/document/verwerkingsspoor'),
    ('/source-selection/publication-evidence', '/inzicht/document/publicatiebewijs'),
    ('/source-selection/blockage', '/inzicht/document/blokkade'),
    ('/review/passages-export', '/inzicht/document/passages'),
    ('/review/processing-evidence-export', '/inzicht/document/verwerkingsbewijs'),
    ('/review/processing-diagnostics', '/inzicht/document/diagnostiek'),
    ('/review/processing-diagnostics-detail', '/inzicht/document/detaildiagnostiek'),
    ('/review/processing-diagnostic-replay', '/inzicht/document/poging'),
    ('/settings/quality', '/inzicht'),
    ('/settings/quality/compare', '/inzicht/routevergelijking'),
    ('/settings/quality/compare/comparison-1', '/inzicht/routevergelijking/comparison-1'),
])
def test_legacy_get_redirects_preserve_document_attempt_format_report_and_filters(tmp_path, old, new):
    state, users, sid, _ = _system(tmp_path)
    app = create_console_app(state)
    client = login(app, users['reviewer_a']['username'])
    params = {'document': sid, 'attempt': 'pa_' + 'a' * 32, 'format': 'csv', 'report': 'report1', 'from': '2026-09-01', 'q': 'Zorg & herstel', 'download': '1'}
    response = client.get(old, params=params, follow_redirects=False)
    assert response.status_code == 303
    target = urlsplit(response.headers['location'])
    assert target.path == new
    for key, value in params.items():
        assert parse_qs(target.query)[key] == [value]
    if old == '/settings/quality':
        override = client.get(old, params={**params, 'tab': 'systeem', 'view': 'other'}, follow_redirects=False)
        assert parse_qs(urlsplit(override.headers['location']).query)['tab'] == ['kwaliteit']
        assert parse_qs(urlsplit(override.headers['location']).query)['view'] == ['table']
    assert TestClient(app).get(old, params=params, follow_redirects=False).status_code == 401


def test_quality_table_history_and_graphs_stay_in_one_tab_and_same_report(tmp_path):
    state, users, _, _ = _system(tmp_path)
    client = login(create_console_app(state), users['researcher']['username'])
    data = client.get('/inzicht/api/quality', params={'kind': 'richtlijn'}).json()
    params = {'tab': 'kwaliteit', 'view': 'table', 'kind': 'richtlijn', 'report': data['calculation_id']}
    table = client.get('/inzicht', params=params)
    assert table.status_code == 200
    assert 'Rapporthistorie' in table.text and 'name="view" value="table"' in table.text
    assert 'href="/settings/quality' not in table.text
    graph = next(url for url in Links(table.text).hrefs if parse_qs(urlsplit(url).query).get('report') == [data['calculation_id']] and 'view' not in parse_qs(urlsplit(url).query))
    assert parse_qs(urlsplit(graph).query)['kind'] == ['richtlijn']
    assert client.get(graph).status_code == 200
    assert client.get('/inzicht/api/quality', params={'report': data['calculation_id']}).json()['calculation_id'] == data['calculation_id']


def test_configuration_has_no_diagnostics_and_controls_use_insight_addresses(tmp_path):
    state, users, _, _ = _system(tmp_path)
    client = login(create_console_app(state), users['researcher']['username'])
    config = client.get('/settings/technical').text
    assert '/settings/llm' in config and '/settings/api-access' in config
    assert not any(item in config for item in ('Routevergelijking', 'Semantische veiligheidstests', 'Alle exports', 'Verwerkingsproblemen herstellen', 'href="/inzicht'))
    insight = client.get('/inzicht?tab=controles').text
    assert '/inzicht/routevergelijking' in insight and '/inzicht/reviewsignalen' in insight
    assert '/settings/quality/compare' not in insight and '/settings/technical/exports' not in insight


def test_installed_review_signals_keep_researcher_access_and_old_bookmark(installed):
    client, _, researcher, _, _, _, _ = installed
    assert client.get('/inzicht/reviewsignalen').status_code == 403
    assert client.post('/login', data={'username': researcher['username'], 'password': 'anne-secret'}, follow_redirects=False).status_code == 303
    old = client.get('/audit/review-signals?q=zorg', follow_redirects=False)
    assert old.status_code == 303 and old.headers['location'] == '/inzicht/reviewsignalen?q=zorg'
    page = client.get(old.headers['location'])
    assert page.status_code == 200 and 'Signalen uit Review' in page.text
