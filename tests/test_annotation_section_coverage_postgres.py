"""A section confirmation belongs to the confirmed working revision.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.vorming import annotation_section_coverage_v1 as coverage
from src.vorming import confirmed_document_structure_v1 as structure
from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_v1 as annotations
from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
from tests.postgres_support import database, install_schema
from tests.production_support import restart_production
from tests.test_human_annotation_build_postgres import saved_source, open_document_check


def test_scope_and_exact_sections_survive_edits_and_recovery(tmp_path, monkeypatch, production_console, production_app):
    console, actor, sid, request = saved_source(production_console, tmp_path, for_build=False,
        heading='<p>Voorwerk.</p><h1>Diagnostiek</h1><p>Eerste sectietekst.</p><h1>Diagnostiek</h1>')
    state = annotations.overview(console, actor_id=actor, snapshot_id=sid)
    structure.confirm(console, actor_id=actor, snapshot_id=sid,
                      extraction_hash=state['extraction_hash'], entries=structure.proposed(state['blocks']))
    open_document_check(console, actor, sid)
    build_hash = build.overview(console, actor_id=actor, snapshot_id=sid)['overview_hash']

    def view(kernel=console):
        return annotations.overview(kernel, actor_id=actor, snapshot_id=sid, include_source_work=True)[coverage.KEY]

    initial = view()
    assert initial['scope'] == 'selection'
    first, second, third = initial['sections']
    assert first['title'] == 'Vóór de eerste kop'
    assert second['title'] == third['title'] == 'Diagnostiek'
    assert second['block_id'] != third['block_id']

    def write(kernel=console, user=actor, **fields):
        return coverage.write(kernel, actor_id=user, snapshot_id=sid, basis=initial['basis'], **fields)

    def mark(row, kernel=console):
        return write(kernel=kernel, section=row['block_id'], fingerprint=row['fingerprint'])

    with pytest.raises(ConsoleError, match='annotation_coverage_scope_closed'):
        mark(second)
    outsider = console.create_account(username='outsider', password='coverage-secret', roles=('reviewer',))['account_id']
    with pytest.raises(ConsoleError, match='reviewer_not_named_on_snapshot'):
        write(user=outsider, scope='full')

    client = TestClient(production_app(console), base_url='https://testserver')
    assert client.post('/login', data={'username': 'builder', 'password': 'human-build-secret'},
                       follow_redirects=False).status_code == 303
    page = client.get('/annotations', params={'document': sid})
    assert 'Dekking hele richtlijn controleren' in page.text
    assert 'data-section-status="' not in page.text
    result = client.post('/annotations/coverage', data={'document': sid, 'basis': initial['basis'], 'scope': 'full'},
                         headers={'Accept': 'application/json'})
    assert result.status_code == 200 and 'Vóór de eerste kop' in result.json()['contents']

    reopened = restart_production(console)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda pair: mark(*pair), [(second, console), (third, reopened)]))
    assert [row['status'] for row in view(reopened)['sections']] == ['open', 'checked', 'checked']
    assert build.overview(reopened, actor_id=actor, snapshot_id=sid)['overview_hash'] != build_hash

    # Exact retries leave the saved actor, time and decision intact.
    with console.workflow_document_store._connect() as con:
        before_retry = coverage.read(con, sid)
    mark(third)
    with console.workflow_document_store._connect() as con:
        assert coverage.read(con, sid) == before_retry

    edit = {**deepcopy(request), 'command_id': str(uuid4()), 'expected_generation': 1, 'expected_revision': 1}
    edit['selection']['status'] = 'draft'
    annotations.save(reopened, actor_id=actor, **edit)
    assert [row['status'] for row in view(reopened)['sections']] == ['open', 'checked', 'stale']
    with pytest.raises(ConsoleError, match='annotation_coverage_stale'):
        mark(third)
    assert client.get('/annotations', params={'document': sid}).text.count('Opnieuw nakijken') == 1
    write(scope='selection')
    assert 'data-section-status="' not in client.get('/annotations', params={'document': sid}).text

    config = console.workflow_document_store.config
    archive = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config)).export_state()
    with database(config.dsn) as target:
        install_schema(target.dsn)
        restore = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target))
        restore.restore_state(archive)
        before = archive['formation_recovery']['tables']['annotation_section_coverage']
        after = restore.export_state()['formation_recovery']['tables']['annotation_section_coverage']
        assert after == before and after[0]['scope'] == 'selection'
        assert set(after[0]['confirmations']) == {second['block_id'], third['block_id']}
