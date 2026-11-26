"""The saved annotation round and coverage guard the existing build and release.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4

import psycopg

import pytest
from starlette.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.vorming import annotation_document_check_v1 as check
from src.vorming import annotation_section_coverage_v1 as coverage
from src.vorming import confirmed_document_structure_v1 as structure
from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_v1 as annotation
from src.vorming.worker_handover_v1 import native_attempt
from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
from tests.postgres_support import database, install_schema
from tests.production_support import restart_production
from tests.test_human_annotation_build_postgres import closing, saved_source
from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore, _complete_review


@pytest.mark.parametrize('scope', ['selection', 'full'])
def test_same_workspace_check_build_review_and_publication(
        tmp_path, monkeypatch, production_console, production_app, scope):
    monkeypatch.setenv('METIS_ANNOTATION_DOCUMENT_CHECK', '1')
    monkeypatch.setenv('METIS_ANNOTATION_CONFIRMED_STRUCTURE', '1')
    store = MemorySourceStore()
    console, actor, sid, saved = saved_source(production_console, tmp_path,
        review_option='uploader_sole', source_status='established', immutable_source_store=store,
        heading='<h1>Algemeen</h1><p>Overige begeleidende tekst.</p><h1>Diagnostiek</h1>')

    def state(kernel=console):
        return annotation.overview(kernel, actor_id=actor, snapshot_id=sid, include_source_work=True)

    initial = state()
    structure.confirm(console, actor_id=actor, snapshot_id=sid,
                      extraction_hash=initial['extraction_hash'], entries=structure.proposed(initial['blocks']))
    baseline = state()

    def overview(kernel=console):
        return build.overview(kernel, actor_id=actor, snapshot_id=sid)

    def assert_no_build():
        with console.workflow_document_store._connect() as con:
            assert not con.execute('SELECT 1 FROM workflow.processing_attempts WHERE snapshot_id=%s',
                                   (sid,)).fetchall()

    assert not overview()['can_finalize']
    with pytest.raises(ConsoleError, match='annotation_document_incomplete'):
        build.finalize(console, actor_id=actor, **closing(overview()))

    client = TestClient(production_app(console), base_url='https://testserver')
    assert client.post('/login', data={'username': 'builder', 'password': 'human-build-secret'},
                       follow_redirects=False).status_code == 303
    old_link = client.get('/annotations', params={'document': sid, 'overview': 'true'})
    assert 'Ik ben klaar met dit document' in old_link.text
    assert 'data-confirmed-document-build' not in old_link.text
    with console.workflow_document_store._connect() as con:
        assert check.read(con, sid) is None
    form = {'document': sid, 'phase': 'checking', 'expected_generation': baseline['generation'],
            'expected_round': 0}
    for _ in range(2):
        response = client.post('/annotations/round', data=form, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'] == '/annotations?document=' + sid
    assert_no_build()

    resumed = restart_production(console)
    assert overview(resumed)['document_round']['revision'] == 1
    monkeypatch.delenv('METIS_ANNOTATION_DOCUMENT_CHECK')
    assert overview(resumed)['document_round']['phase'] == 'checking'
    panel = client.get('/annotations', params={'document': sid, 'overview': 'true'})
    assert 'Verder annoteren' in panel.text and 'Overige begeleidende tekst' in panel.text
    assert 'data-confirmed-document-build' in panel.text
    prior = closing(overview())
    section_view = state()[coverage.KEY]
    if scope == 'full':
        coverage.write(console, actor_id=actor, snapshot_id=sid, basis=section_view['basis'], scope='full')
        assert not overview()['can_finalize']
        assert 'data-confirmed-document-build' not in client.get('/annotations', params={'document': sid}).text
        assert {row['title'] for row in overview()['inspection']['findings']
                if row['code'] == 'annotation_document_coverage_required'} == {'Algemeen', 'Diagnostiek'}
        for section in section_view['sections']:
            coverage.write(console, actor_id=actor, snapshot_id=sid, basis=section_view['basis'],
                           section=section['block_id'], fingerprint=section['fingerprint'])
    else:
        # This is a new round even when the selected evidence stays the same.
        for revision, phase in [(1, 'annotating'), (2, 'checking')]:
            check.transition(resumed, actor_id=actor, snapshot_id=sid, phase=phase,
                             expected_round=revision, expected_generation=baseline['generation'])
            assert overview(resumed)['can_finalize'] == (phase == 'checking')

    assert_no_build()
    assert overview()['can_finalize']
    with pytest.raises(ConsoleError, match='annotation_overview_stale'):
        build.finalize(resumed, actor_id=actor, **prior)
    outsider = console.create_account(username='outside', password='human-review-secret', roles=('reviewer',))
    with pytest.raises(ConsoleError, match='reviewer_not_named_on_snapshot'):
        check.transition(resumed, actor_id=outsider['account_id'], snapshot_id=sid, phase='annotating',
                         expected_round=overview()['document_round']['revision'], expected_generation=baseline['generation'])

    close = closing(overview())

    def submit(kernel):
        return build.finalize(kernel, actor_id=actor, **close)

    with ThreadPoolExecutor(2) as pool:
        first, second = pool.map(submit, (console, resumed))
    assert first == second
    with console.workflow_document_store._connect() as con:
        seal = con.execute('SELECT payload FROM workflow.annotation_seals WHERE seal_id=%s',
                           (first['seal_id'],)).fetchone()['payload']
        assert seal[check.KEY]['scope'] == scope
        assert bool(seal[check.KEY]['confirmations']) == (scope == 'full')
        assert len(con.execute('SELECT 1 FROM workflow.processing_attempts WHERE snapshot_id=%s', (sid,)).fetchall()) == 1
    with pytest.raises(psycopg.Error, match='annotation_document_check_seal_mismatch'):
        with console.workflow_document_store._connect() as con:
            con.execute("INSERT INTO workflow.annotation_seals(seal_id,snapshot_id,extraction_hash,generation,"
                        "overview_hash,payload,payload_text,created_by) SELECT repeat('0',64),snapshot_id,"
                        "extraction_hash,generation,overview_hash,payload-'document_check',payload_text,created_by "
                        "FROM workflow.annotation_seals WHERE seal_id=%s", (first['seal_id'],))
    with pytest.raises(ConsoleError, match='annotation_coverage_build_locked'):
        coverage.write(console, actor_id=actor, snapshot_id=sid, basis=section_view['basis'],
                       scope='selection' if scope == 'full' else 'full')
    console.execute_source_selection(actor_id=actor, snapshot_id=sid,
        attempt=native_attempt(console, sid, first['attempt_id']))
    assert native_attempt(console, sid, first['attempt_id'])['state'] == 'succeeded'
    assert build.finalize(resumed, actor_id=actor, **close) == first
    assert not overview()['can_finalize']
    with pytest.raises(ConsoleError, match='annotation_document_round_required'):
        build.rebuild(console, actor_id=actor, snapshot_id=sid, annotation_id=saved['annotation_id'],
                      command_id=str(uuid4()), expected_generation=overview()['generation'])
    objects = console.snapshot_objects(sid, include_blocked=True)
    assert sum(bool(o.get('metadata', {}).get('human_annotation')) for o in objects) == 1
    assert not any('Overige begeleidende tekst' in str(o['content']) for o in objects)
    assert state()['working_revision_id'] == baseline['working_revision_id']
    assert 'Overige begeleidende tekst' in client.get('/annotations', params={'document': sid}).text

    publisher = console.create_account(username='publisher', password='human-publish-secret', roles=('publisher',))
    assert console.publish(actor_id=publisher['account_id'], snapshot_id=sid)['status'] == 'BLOCKED'
    _complete_review(console, {'reviewer': {'account_id': actor}}, {'snapshot_id': sid})
    readiness = console.publication_readiness(sid)
    assert readiness['publication_ready'], readiness['blockers']

    envelope = console._envelope(sid)
    locator = envelope['immutable_storage_locator']
    honest = store.blobs[locator]
    store.blobs[locator] = b'changed immutable source representation'
    console._source_cache_path(envelope).unlink()
    assert console.publish(actor_id=publisher['account_id'], snapshot_id=sid)['status'] == 'BLOCKED'
    store.blobs[locator] = honest
    published = console.publish(actor_id=publisher['account_id'], snapshot_id=sid)
    assert published['published_items'] == 1
    assert console.snapshot_is_published(sid)
    forbidden_preparation = client.post('/annotations/source', data={
        'document': sid, 'command_id': 'no-preparation-after-publication',
        'expected_revision': console.objects_revision(sid),
    }, follow_redirects=False)
    assert forbidden_preparation.status_code == 409
    assert 'Deze versie is gepubliceerd.' in forbidden_preparation.text
    with console.workflow_document_store._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.processing_attempts WHERE snapshot_id=%s',
                           (sid,)).fetchone()['n'] == 1


def test_annotation_round_history_survives_operational_restore(tmp_path, monkeypatch, production_console):
    monkeypatch.setenv('METIS_ANNOTATION_DOCUMENT_CHECK', '1')
    console, actor, sid, _ = saved_source(production_console, tmp_path)
    for previous, phase in enumerate(('checking', 'annotating', 'checking')):
        check.transition(console, actor_id=actor, snapshot_id=sid, phase=phase,
                         expected_round=previous, expected_generation=1)
    result = build.finalize(console, actor_id=actor,
        **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    config = console.workflow_document_store.config
    archive = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(config)).export_state()
    with database(config.dsn) as target:
        install_schema(target.dsn)
        restored = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(target))
        restored.restore_state(archive)
        before = archive['formation_recovery']['tables']['annotation_round_events']
        after = restored.export_state()['formation_recovery']['tables']['annotation_round_events']
        assert before == after
        assert [row['phase'] for row in after] == ['checking', 'annotating', 'checking']
        seals = restored.export_state()['formation_recovery']['tables']['annotation_seals']
        assert seals[0]['seal_id'] == result['seal_id']
        assert seals[0]['payload'][check.KEY]['round']['revision'] == 3


def test_full_plain_source_and_annotation_change_requires_new_section_check(
        tmp_path, monkeypatch, production_console):
    monkeypatch.setenv('METIS_ANNOTATION_DOCUMENT_CHECK', '1')
    monkeypatch.setenv('METIS_ANNOTATION_CONFIRMED_STRUCTURE', '1')
    console, actor, sid, saved = saved_source(production_console, tmp_path)
    inputs = {'actor_id': actor, 'snapshot_id': sid}
    view = annotation.overview(console, **inputs)
    assert not structure.proposed(view['blocks'])
    with pytest.raises(ConsoleError, match='annotation_structure_confirmation_required'):
        check.transition(console, **inputs, phase='checking', expected_round=0, expected_generation=1)
    structure.confirm(console, **inputs, extraction_hash=view['extraction_hash'], entries=[])
    check.transition(console, **inputs, phase='checking', expected_round=0, expected_generation=1)

    def section():
        result = annotation.overview(console, **inputs, include_coverage=True)[coverage.KEY]
        row, = result['sections']
        assert row['title'] == 'Hele document'
        return result['basis'], row

    basis, first = section()
    coverage.write(console, **inputs, basis=basis, scope='full')
    coverage.write(console, **inputs, basis=basis, section=first['block_id'], fingerprint=first['fingerprint'])
    assert build.overview(console, **inputs)['can_finalize']
    edit = deepcopy(saved)
    edit.update(command_id=str(uuid4()), expected_generation=1, expected_revision=1)
    edit['selection']['status'] = 'draft'
    annotation.save(console, actor_id=actor, **edit)
    _, updated = section()
    assert updated['status'] == 'stale'
    checked = build.overview(console, **inputs)
    assert not checked['can_finalize']
    assert checked['document_round']['phase'] == 'checking'
    assert any(f['code'] == 'annotation_document_coverage_required' for f in checked['inspection']['findings'])
    with pytest.raises(ConsoleError, match='annotation_coverage_stale'):
        coverage.write(console, **inputs, basis=basis, section=first['block_id'], fingerprint=first['fingerprint'])
