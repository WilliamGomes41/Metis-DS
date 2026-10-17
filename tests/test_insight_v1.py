"""Inzicht: one room for system, quality, documents and checks; existing owners reused.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.quality_metrics_app_v1 import capture
from src.quality_metrics_v1 import build_report
from src.request_diagnostics_v1 import doc_ref
from tests.test_d5_4_review_interaction_evidence import PASSWORD, _system


def _login(console, username):
    client = TestClient(create_console_app(console), base_url='https://testserver')
    assert client.post('/login', data={'username': username, 'password': PASSWORD}, follow_redirects=False).status_code == 303
    return client


def test_inzicht_requires_login_and_has_four_tabs(tmp_path):
    console, users, _sid, _oid = _system(tmp_path)
    anonymous = TestClient(create_console_app(console), base_url='https://testserver')
    for path in ('/inzicht', '/inzicht/api/quality', '/inzicht/api/documents', '/telemetry/api/summary'):
        assert anonymous.get(path).status_code == 401
    client = _login(console, users['researcher']['username'])
    page = client.get('/inzicht?tab=kwaliteit')
    assert page.status_code == 200 and 'data-initial-tab="kwaliteit"' in page.text
    for key in ('systeem', 'kwaliteit', 'documenten', 'controles'):
        assert f'href="/inzicht?tab={key}"' in page.text and f'data-panel="{key}"' in page.text
    assert 'aria-selected="true" aria-current="page">Kwaliteit &amp; werkproces' in page.text
    assert 'data-initial-tab="systeem"' in client.get('/inzicht?tab=onbekend').text


def test_quality_api_is_the_same_measurement_as_the_table_page(tmp_path):
    console, users, sid, _oid = _system(tmp_path)
    client = _login(console, users['researcher']['username'])
    data = client.get('/inzicht/api/quality').json()
    expected = build_report(capture(console, users['researcher'])['documents'], as_of=data['as_of'])
    assert data['cohort_size'] == expected['cohort_size'] == 1
    assert data['open_passages'] == expected['open_passages']
    assert data['routes'] == expected['routes']
    assert data['documents'][0]['snapshot_id'] == sid and data['documents'][0]['doc_ref'] == doc_ref(sid)
    assert data['trend'] and data['trend'][-1]['calculation_id'] == data['calculation_id']
    table = client.get('/settings/quality')
    assert 'href="/inzicht?tab=kwaliteit"' in table.text and 'aria-current="page">Kwaliteit' in table.text
    assert client.get('/inzicht/api/quality?from=invalid').status_code == 400


def test_documents_api_only_shows_authorized_documents_with_diagnostics(tmp_path):
    console, users, sid, _oid = _system(tmp_path)
    rows = _login(console, users['researcher']['username']).get('/inzicht/api/documents').json()['documents']
    assert [row['snapshot_id'] for row in rows] == [sid]
    row = rows[0]
    assert row['doc_ref'] == doc_ref(sid) and row['blocked'] is not None
    assert set(row['telemetry']) == {'requests', 'errors'}
    outsider = console.create_account(username='outsider.inzicht', password=PASSWORD, roles=('reviewer',))
    assert _login(console, outsider['username']).get('/inzicht/api/documents').json()['documents'] == []


def test_settings_hub_channels_inzicht_beheer_and_uitleg(tmp_path):
    console, users, _sid, _oid = _system(tmp_path)
    client = _login(console, users['researcher']['username'])
    settings = client.get('/settings').text
    for heading in ('<h2>Inzicht</h2>', '<h2>Beheer</h2>', '<h2>Uitleg</h2>'):
        assert heading in settings
    for key in ('systeem', 'kwaliteit', 'documenten', 'controles'):
        assert f'href="/inzicht?tab={key}"' in settings
    assert 'href="/settings/quality"' not in settings and 'href="/telemetry"' not in settings
    technical = client.get('/settings/technical').text
    assert 'href="/inzicht?tab=documenten"' in technical
