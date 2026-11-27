"""Confirmed outline from the existing editor to the same built and reviewed document.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from urllib.parse import urlencode

import psycopg
import pytest
from starlette.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.review.review_cockpit_v1 import found_under_path
from src.vorming import confirmed_document_structure_v1 as structure
from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_v1 as annotations
from src.vorming.worker_handover_v1 import native_attempt
from tests.production_support import restart_production
from tests.test_human_annotation_build_postgres import closing, saved_source, open_document_check


def test_confirm_outline_then_build_and_review_same_document(tmp_path, monkeypatch, production_console, production_app):
    console, actor, sid, _ = saved_source(production_console, tmp_path, for_build=False,
                                          heading='<h1>Diagnostiek</h1><h2>Kenmerken</h2>')
    view = annotations.overview(console, actor_id=actor, snapshot_id=sid)
    before = build.overview(console, actor_id=actor, snapshot_id=sid)
    assert not before['can_finalize']
    assert any(item['code'] == 'annotation_structure_confirmation_required' for item in before['inspection']['findings'])
    entries = structure.proposed(view['blocks'])
    assert [item['title'] for item in entries] == ['Diagnostiek', 'Kenmerken']
    entries[1].update(title='Klinische kenmerken', level=1)
    client = TestClient(production_app(console), base_url='https://testserver')
    assert client.post('/login', data={'username': 'builder', 'password': 'human-build-secret'},
                       follow_redirects=False).status_code == 303
    location = '/annotations?' + urlencode({'document': sid})
    first = client.get(location)
    assert 'Klopt de inhoudsopgave?' in first.text
    assert 'annotation-simple-rows' not in first.text
    form = {'document': sid, 'basis': view['extraction_hash'],
            'anchor': [item['block_id'] for item in entries],
            'title': [item['title'] for item in entries], 'level': [item['level'] for item in entries]}
    assert client.post('/annotations/structure', data={**form, 'basis': 'stale'},
                       follow_redirects=False).status_code == 409
    assert client.post('/annotations/structure', data={**form, 'anchor': list(reversed(form['anchor']))},
                       follow_redirects=False).status_code == 409
    confirmed = client.post('/annotations/structure', data=form, follow_redirects=False)
    assert confirmed.status_code == 303 and confirmed.headers['location'] == location
    reopened = client.get(location)
    assert 'annotation-simple-rows' in reopened.text
    assert f'href="#{entries[1]["block_id"]}">Klinische kenmerken</a>' in reopened.text
    assert '>Kenmerken</span>' in reopened.text

    resumed = restart_production(console)
    open_document_check(resumed, actor, sid)
    with pytest.raises(ConsoleError, match='annotation_overview_stale'):
        build.finalize(resumed, actor_id=actor, **closing(before))
    receipt = build.finalize(resumed, actor_id=actor, **closing(build.overview(resumed, actor_id=actor, snapshot_id=sid)))
    resumed.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=native_attempt(resumed, sid, receipt['attempt_id']))
    build_page = client.get('/annotations/build', params={'document': sid, 'attempt': receipt['attempt_id']})
    assert build_page.status_code == 200 and 'Klinische kenmerken' in build_page.text
    latest = restart_production(resumed)
    before_review = latest._envelope(sid)
    reviewer = TestClient(production_app(latest), base_url='https://testserver')
    assert reviewer.post('/login', data={'username': 'reviewer', 'password': 'human-build-secret'},
                         follow_redirects=False).status_code == 303
    item = next(obj for obj in latest.snapshot_objects(sid, include_blocked=True)
                if (obj.get('metadata') or {}).get('human_annotation'))
    assert found_under_path(item) == 'Klinische kenmerken'
    assert item['content']['clean_text'] == 'De kwetsbare huid verklaart de pijn.'
    response = reviewer.get('/review', params={'document': sid, 'object': item['object_id']})
    assert response.status_code == 200 and 'Klinische kenmerken' in response.text
    assert 'task=structure' not in response.text
    assert '/review/headings/batch-confirm' not in response.text
    old_queries = [
        ('/source-selection', {'object': item['object_id']}),
        ('/source-selection', {'selected_document': sid, 'object': item['object_id']}),
        ('/source-selection', {'task': 'repair'}),
        ('/review', {'task': 'repair', 'object': item['object_id']}),
        ('/review', {'context_mode': 'source', 'object': item['object_id']}),
    ]
    for route, query in old_queries:
        old = reviewer.get(route, params={'document': sid, **query}, follow_redirects=False)
        assert old.status_code == 404, (route, query)
        assert 'location' not in old.headers
    assert 'Aanpassen in de kaart' in response.text
    assert latest._envelope(sid)['working_revision_id'] == before_review['working_revision_id']
    with latest.workflow_document_store._connect() as con:
        seal = con.execute('SELECT payload FROM workflow.annotation_seals WHERE seal_id=%s', (receipt['seal_id'],)).fetchone()
        assert seal['payload'][structure.KEY] == structure.read(con, sid)
        assert con.execute('SELECT count(*) AS n FROM workflow.processing_attempts WHERE snapshot_id=%s',
                           (sid,)).fetchone()['n'] == 1

    # A stale writer that omits the confirmation cannot seal a different build basis.
    from src.integrity_kernel import stable_hash
    from src.workflows.processing_archives_v1 import encoded
    old_payload = dict(seal['payload'])
    del old_payload[structure.KEY]
    old_payload['overview_hash'] = stable_hash({key: value for key, value in old_payload.items() if key != 'overview_hash'})
    with pytest.raises(psycopg.Error, match='annotation_structure_seal_mismatch'):
        with latest.workflow_document_store._connect() as con:
            con.execute(
                'INSERT INTO workflow.annotation_seals (seal_id,snapshot_id,extraction_hash,generation,'
                'overview_hash,payload,payload_text,created_by) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)',
                (stable_hash(old_payload), sid, old_payload['extraction_hash'], old_payload['generation'],
                 old_payload['overview_hash'], encoded(old_payload), encoded(old_payload), actor),
            )

    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from tests.postgres_support import database, install_schema

    config = latest.workflow_document_store.config
    archive = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config)).export_state()
    with database(config.dsn) as target:
        install_schema(target.dsn)
        restore = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target))
        restore.restore_state(archive)
        restored_tables = restore.export_state()['formation_recovery']['tables']
        assert restored_tables['annotation_seals'][0]['payload'][structure.KEY] == seal['payload'][structure.KEY]


def test_concurrent_confirmation_is_one_decision_and_survives_backup(tmp_path, production_console):
    from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
    from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
    from tests.postgres_support import database, install_schema

    console, actor, sid, _ = saved_source(production_console, tmp_path, for_build=False, heading='<h1>Diagnostiek</h1>')
    view = annotations.overview(console, actor_id=actor, snapshot_id=sid)
    entries = structure.proposed(view['blocks'])
    wrong = deepcopy(entries)
    wrong[0]['title'] = 'Andere kop'
    outsider = console.create_account(username='outsider', password='human-build-secret', roles=('reviewer',))['account_id']

    def submit(kernel, rows, user=actor):
        return structure.confirm(kernel, actor_id=user, snapshot_id=sid, extraction_hash=view['extraction_hash'], entries=rows)

    with pytest.raises(ConsoleError, match='reviewer_not_named_on_snapshot'):
        submit(console, entries, outsider)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda kernel: submit(kernel, entries), [console, restart_production(console)]))
    assert results[0] == results[1]
    with pytest.raises(ConsoleError, match='annotation_structure_conflict'):
        submit(restart_production(console), wrong)
    config = console.workflow_document_store.config
    archive = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config)).export_state()
    with database(config.dsn) as target:
        install_schema(target.dsn)
        restored = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target))
        restored.restore_state(archive)
        tables = restored.export_state()['formation_recovery']['tables']
        assert len(tables['annotation_structure_confirmations']) == 1
        assert tables['annotation_structure_confirmations'][0]['definition'] == results[0]
