"""Inzicht: one room for system, quality, documents and checks; existing owners reused.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: metrics teller noemer score-must-drop
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from fastapi.testclient import TestClient

from src.quality_metrics_app_v1 import capture
from src.quality_metrics_v1 import build_report
from src.request_diagnostics_v1 import doc_ref
from tests.test_d5_4_review_interaction_evidence import PASSWORD, _system


def _login(console, username, *, production_app):
    client = TestClient(production_app(console), base_url='https://testserver')
    assert client.post('/login', data={'username': username, 'password': PASSWORD}, follow_redirects=False).status_code == 303
    return client


def test_inzicht_requires_login_and_has_four_tabs(tmp_path, *, production_app, production_console):
    console, users, _sid, _oid = _system(tmp_path, production_console=production_console)
    anonymous = TestClient(production_app(console), base_url='https://testserver')
    for path in ('/inzicht', '/inzicht/api/quality', '/inzicht/api/documents', '/telemetry/api/summary'):
        assert anonymous.get(path).status_code == 401
    client = _login(console, users['researcher']['username'], production_app=production_app)
    page = client.get('/inzicht?tab=kwaliteit')
    assert page.status_code == 200 and 'data-initial-tab="kwaliteit"' in page.text
    for key in ('systeem', 'kwaliteit', 'documenten', 'controles'):
        assert f'href="/inzicht?tab={key}"' in page.text and f'data-panel="{key}"' in page.text
    assert 'aria-selected="true" aria-current="page">Kwaliteit &amp; werkproces' in page.text
    assert 'data-initial-tab="systeem"' in client.get('/inzicht?tab=onbekend').text


def test_quality_api_is_the_same_measurement_as_the_table_page(tmp_path, *, production_app, production_console):
    console, users, sid, _oid = _system(tmp_path, production_console=production_console)
    client = _login(console, users['researcher']['username'], production_app=production_app)
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


def test_documents_api_only_shows_authorized_documents_with_diagnostics(tmp_path, *, production_app, production_console):
    console, users, sid, _oid = _system(tmp_path, production_console=production_console)
    rows = _login(console, users['researcher']['username'], production_app=production_app).get('/inzicht/api/documents').json()['documents']
    assert [row['snapshot_id'] for row in rows] == [sid]
    row = rows[0]
    assert row['doc_ref'] == doc_ref(sid) and row['blocked'] is not None
    assert set(row['telemetry']) == {'requests', 'errors'}
    outsider = console.create_account(username='outsider.inzicht', password=PASSWORD, roles=('reviewer',))
    assert _login(console, outsider['username'], production_app=production_app).get('/inzicht/api/documents').json()['documents'] == []


def test_settings_hub_channels_inzicht_beheer_and_uitleg(tmp_path, *, production_app, production_console):
    console, users, _sid, _oid = _system(tmp_path, production_console=production_console)
    client = _login(console, users['researcher']['username'], production_app=production_app)
    settings = client.get('/settings').text
    for heading in ('<h2>Inzicht</h2>', '<h2>Beheer</h2>', '<h2>Uitleg</h2>'):
        assert heading in settings
    for key in ('systeem', 'kwaliteit', 'documenten', 'controles'):
        assert f'href="/inzicht?tab={key}"' in settings
    assert 'href="/settings/quality"' not in settings and 'href="/telemetry"' not in settings
    technical = client.get('/settings/technical').text
    assert 'href="/settings/llm"' in technical
    for removed in ('href="/inzicht', 'href="/settings/quality', 'href="/settings/technical/exports', 'Verwerkingsproblemen herstellen'):
        assert removed not in technical


def test_quality_projection_keeps_teller_noemer_and_shows_a_score_drop():
    """metrics: the chart projection passes the measured teller (direct) and noemer
    (first decisions) unchanged, and a later lower score MUST show as a drop."""
    from src.insight_v1 import quality_projection

    def report(as_of, direct, first):
        rate = direct / first if first else None
        return {"as_of": as_of, "definition_version": "v", "filters": {}, "cohort_size": 1, "open_passages": 3,
                "oldest_unfinished_source_days": 1.0, "publication_duration_seconds": {"samples": 0, "median": None, "p90": None},
                "burden": {"review_interactions": 1, "object_decisions": 1},
                "routes": {"semantic": {"direct": direct, "first_decisions": first, "known_comparisons": first,
                                        "direct_rate": rate, "changed_fields": {"text": 1}}},
                "documents": [], "processing_runs": {}, "definitions": {}, "limitations": [],
                "readiness_duration": {"reason": "r"}, "clinical_errors": {"reason": "c"}}
    earlier = {"calculation_id": "a", "report": report("2026-10-16T08:00:00Z", 4, 5)}
    later = {"calculation_id": "b", "report": report("2026-10-17T08:00:00Z", 4, 8)}
    data = quality_projection({"record": later, "report": later["report"], "history": [later, earlier]})
    semantic = data["routes"]["semantic"]
    assert (semantic["direct"], semantic["first_decisions"]) == (4, 8)
    rates = [point["direct_rate"]["semantic"] for point in data["trend"]]
    assert rates == [0.8, 0.5] and rates[-1] < rates[0], "score-must-drop: the drop MUST stay visible"


def test_documents_are_paged_and_searched_over_the_whole_authorized_list():
    from src.insight_v1 import documents_projection

    class State:
        def list_envelopes(self):
            return [{'snapshot_id': f'snap-{i:016x}-0000000{i}', 'title': f'Richtlijn {i}'} for i in range(5)]

        def processing_status(self, *_args, **_kwargs):
            return {'state': 'ready'}

        def snapshot_objects(self, _sid):
            return []

    account = {'account_id': 'a', 'roles': ['researcher']}
    first = documents_projection(State(), account, offset=0, limit=2)
    assert first['total'] == 5 and [d['title'] for d in first['documents']] == ['Richtlijn 0', 'Richtlijn 1']
    last = documents_projection(State(), account, offset=4, limit=2)
    assert [d['title'] for d in last['documents']] == ['Richtlijn 4']
    found = documents_projection(State(), account, query='richtlijn 4', limit=2)
    assert found['total'] == 1 and found['documents'][0]['title'] == 'Richtlijn 4'
    State.processing_status = lambda self, sid, **_kwargs: {'state': 'failed', 'retry_allowed': sid.endswith('4')}
    retry = documents_projection(State(), account, state_filter='retry', limit=2)
    assert [d['title'] for d in retry['documents']] == ['Richtlijn 4']
    assert retry['total'] is None and retry['next_offset'] is None
