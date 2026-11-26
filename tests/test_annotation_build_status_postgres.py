"""Lifecycle proof for the read-only build overview on native PostgreSQL.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""

import pytest
from starlette.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_v1 as annotation
from src.vorming.source_processing_dispatch_v1 import claim
from src.vorming.worker_handover_v1 import native_attempt
from tests.production_support import restart_production
from tests.test_human_annotation_build_postgres import closing, saved_source
from tests.test_human_annotation_review_postgres import correction_request


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_status_is_document_scoped_and_follows_durable_build_history(
        tmp_path, monkeypatch, production_console, production_app, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, sid, saved = saved_source(
        production_console, tmp_path, review_option='uploader_sole', context_function='supported_by',
    )
    scope = {'actor_id': actor, 'snapshot_id': sid}

    def login(kernel, username='builder'):
        client = TestClient(production_app(kernel), base_url='https://testserver')
        response = client.post('/login', data={'username': username, 'password': 'human-build-secret'},
                               follow_redirects=False)
        assert response.status_code == 303
        return client

    def page(client, attempt=None):
        params = {'document': sid}
        if attempt:
            params['attempt'] = attempt
        response = client.get('/annotations/build', params=params)
        assert response.status_code == 200
        return response.text

    client = login(console)
    assert 'Er is nog geen bouwopdracht voor dit document.' in page(client)
    with console.workflow_document_store._connect() as con:
        assert build.latest_build(con, sid) is None
    stopped = build.finalize(console, actor_id=actor, **closing(build.overview(console, **scope)))['attempt_id']
    assert 'Wacht op verwerking' in page(client)
    claimed = claim(console, snapshot_id=sid, attempt_id=stopped, actor_id=actor)
    assert '>Bezig<' in page(client)
    console._record_processing_failure(sid, stopped, ConsoleError('processing_attempt_expired'),
                                       claim_token=claimed['dispatch']['token'])
    stopped_page = page(client, stopped)
    assert '>Gestopt<' in stopped_page and 'processing_attempt_expired' in stopped_page
    assert 'Naar Documentcontrole' in stopped_page
    assert '<dt>Kennisobjecten gebouwd</dt><dd>Onbekend</dd>' in stopped_page

    running = build.finalize(console, actor_id=actor, **closing(build.overview(console, **scope)))['attempt_id']
    restarted = restart_production(console)
    client = login(restarted)
    assert 'Wacht op verwerking' in page(client)
    restarted.execute_source_selection(**scope, attempt=native_attempt(restarted, sid, running))
    completed = page(client)
    assert '>Geslaagd<' in completed
    assert '<dt>Kennisobjecten gebouwd</dt><dd>1</dd>' in completed, completed.split('<dl>')[1].split('</dl>')[0]
    assert '<dt>Klaar voor Review</dt><dd>1</dd>' in completed
    assert 'Naar Review' in completed
    assert stopped in completed
    assert '<h2>Geselecteerde bouwopdracht</h2>' in page(client, stopped)
    assert 'Naar Documentcontrole' not in page(client, stopped)
    assert client.get('/annotations/build/api', params={'document': sid}).json()['attempt_id'] == running

    edit = correction_request(restarted, sid, saved)
    next(row for row in edit['selection']['ranges'] if row['role'] == 'evidence')['evidence_function'] = 'explains'
    annotation.save(restarted, actor_id=actor, **edit)
    stale = page(client, running)
    assert 'Deze opdracht hoort bij een eerdere bouw of annotatieversie.' in stale
    assert 'Naar Review' not in stale
    assert '<dt>Kennisobjecten gebouwd</dt><dd>1</dd>' in stale

    replacement = build.finalize(restarted, actor_id=actor, **closing(build.overview(restarted, **scope)))['attempt_id']
    restarted.execute_source_selection(**scope, attempt=native_attempt(restarted, sid, replacement))
    assert running in page(client)
    historical = page(client, running)
    assert '<h2>Geselecteerde bouwopdracht</h2>' in historical
    assert '<dt>Kennisobjecten gebouwd</dt><dd>1</dd>' in historical
    assert 'Naar Review' not in historical

    reviewer = next(row['account_id'] for row in restarted.list_accounts() if row['username'] == 'reviewer')
    other = restarted.receive_source(
        actor_id=actor, filename='other.html', content_type='text/html', class_='richtlijn',
        data=b'<p>Another source.</p>', ingest_kind='new', title='Other document', version='1.0',
        date='2026-11-26', live_url='', family='test', named_reviewers=[reviewer],
    )['snapshot_id']
    restarted.create_account(username='outsider', password='human-build-secret', roles=('reviewer',))
    outsider = login(restarted, 'outsider')
    for url in ('/annotations/build', '/annotations/build/api'):
        assert client.get(url, params={'document': other, 'attempt': running}).status_code >= 400
        assert outsider.get(url, params={'document': sid, 'attempt': running}).status_code >= 400
    with restarted.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.annotation_build_commands WHERE snapshot_id=%s',
                           (sid,)).fetchone()['n'] == 3
