"""Review corrections through Documentcontrole (#1169) and denial of the retired #1064 write path.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from html import unescape
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.review.review_ledger import read_events
from src.vorming import annotation_document_check_v1 as document_check
from src.vorming import annotation_section_coverage_v1 as coverage
from src.vorming import confirmed_document_structure_v1 as structure
from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_v1 as annotation
from src.vorming.worker_handover_v1 import native_attempt
from tests.production_support import application_for, restart_production
from tests.test_human_annotation_build_postgres import closing, saved_source
from tests.test_human_annotation_review_postgres import (
    approve, candidate, correction_request, execute_build, save_second_claim,
)


def prepare_reviewable_document(production_console, root):
    console, author, sid, first = saved_source(
        production_console, root, context_function='supported_by', for_build=False,
        heading='<h1>Diagnostiek</h1>', claim_tail=' De oorzaak telt mee.',
        second_heading='<h1>Doelgroep</h1>',
    )
    first_view = annotation.overview(console, actor_id=author, snapshot_id=sid)
    structure.confirm(console, actor_id=author, snapshot_id=sid, extraction_hash=first_view['extraction_hash'],
                      entries=structure.proposed(first_view['blocks']))
    second = save_second_claim(console, author, sid)
    view = annotation.overview(console, actor_id=author, snapshot_id=sid, include_coverage=True)
    document_check.transition(console, actor_id=author, snapshot_id=sid, phase='checking',
                              expected_generation=view['generation'], expected_round=0)
    scope = view[coverage.KEY]
    coverage.write(console, actor_id=author, snapshot_id=sid, basis=scope['basis'], scope='full')
    for section in scope['sections']:
        coverage.write(console, actor_id=author, snapshot_id=sid, basis=scope['basis'],
                       section=section['block_id'], fingerprint=section['fingerprint'])
    execute_build(console, author, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    objects = {obj['metadata']['human_annotation']['annotation_id']: obj['object_id']
               for obj in console.snapshot_objects(sid) if (obj.get('metadata') or {}).get('human_annotation')}
    oid, untouched = objects[first['annotation_id']], objects[second['annotation_id']]
    for item in (oid, untouched):
        approve(console, sid, item, reviewer)
    return console, reviewer, sid, first, oid, untouched


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_named_reviewer_uses_documentcontrole_and_preserves_the_other_approval(
        production_console, production_app, tmp_path, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, reviewer, sid, first, oid, other_id = prepare_reviewable_document(production_console, tmp_path)
    actor = {'actor_id': reviewer, 'snapshot_id': sid}

    def object_for(kernel, target):
        return next(obj for obj in kernel.snapshot_objects(sid) if obj['object_id'] == target)

    def other_bindings(kernel):
        return [item for item in kernel.object_review_bindings(sid) if item['object_id'] == other_id]

    untouched, judgment = object_for(console, other_id), other_bindings(console)
    before = object_for(console, oid)
    assert any(item['valid'] for item in judgment)
    console.create_account(username='outside', password='human-build-secret', roles=('reviewer',))

    with TestClient(production_app(console)) as client, TestClient(production_app(console)) as outsider:
        client.post('/login', data={'username': 'reviewer', 'password': 'human-build-secret'})
        outsider.post('/login', data={'username': 'outside', 'password': 'human-build-secret'})
        review_url = '/review?document='+sid+'&object='+oid
        page = client.get(review_url).text
        repair, = re.findall(r'<a [^>]*href="([^"]+)"[^>]*>Aanpassen in de kaart</a>', page)
        repair = unescape(repair)
        assert parse_qs(urlsplit(repair).query)['annotation'] == [first['annotation_id']]
        workspace = client.get(repair)
        assert workspace.status_code == 200
        assert workspace.text.index('Opgeslagen annotaties') < workspace.text.index('id="annotation-document-check-title"')
        for obsolete in ('Kennisobject opnieuw bouwen', 'Opbouw bekijken', 'Opgeslagen bouwopdracht bekijken'):
            assert obsolete not in workspace.text
        denied = outsider.get(repair)
        assert 400 <= denied.status_code < 500 and 'annotation-data' not in denied.text

        stale = closing(build.overview(console, **actor))
        correction = correction_request(console, sid, first)
        claim = next(item for item in correction['selection']['ranges'] if item['role'] == 'core')
        claim['quote'] = 'De kwetsbare huid verklaart de pijn.'
        claim['end'] = len(claim['quote'])
        assert outsider.post('/annotations/api', json=correction).status_code == 403
        saved = client.post('/annotations/api', json=correction)
        assert saved.status_code == 200, saved.text

        def blocked(kernel):
            with pytest.raises(ConsoleError, match='annotation_correction_pending'):
                approve(kernel, sid, oid, reviewer)
            assert object_for(kernel, other_id) == untouched
            assert other_bindings(kernel) == judgment

        blocked(console)
        assert not any(item['valid'] for item in console.object_review_bindings(sid) if item['object_id'] == oid)
        assert 'Rond Documentcontrole af' in client.get(review_url).text
        scope = annotation.overview(console, **actor, include_coverage=True)[coverage.KEY]
        assert [(row['title'], row['status']) for row in scope['sections']] == [
            ('Diagnostiek', 'stale'), ('Doelgroep', 'checked'),
        ]
        assert 'Afronden en bouwen' not in client.get(repair).text.split('id="annotation-document-check-title"')[1]
        with pytest.raises(ConsoleError, match='annotation_document_incomplete'):
            build.finalize(console, actor_id=reviewer, **stale)
        section = scope['sections'][0]
        coverage.write(console, **actor, basis=scope['basis'], section=section['block_id'],
                       fingerprint=section['fingerprint'])
        with pytest.raises(ConsoleError, match='annotation_overview_stale'):
            build.finalize(console, actor_id=reviewer, **stale)
        removed = client.post('/annotations/rebuild', json={'document': sid, 'annotation': first['annotation_id'],
                               'expected_generation': saved.json()['generation']})
        assert removed.status_code == 404

        def build_form():
            panel = client.get(repair).text
            form, = re.findall(r'<form [^>]*data-confirmed-document-build>(.*?)</form>', panel)
            return {name: unescape(value) for name, value in re.findall(r'name="([^"]+)" value="([^"]*)"', form)}

        # Keep the normal HTTP reservation and start its durable delivery after a kernel restart.
        from src.vorming.source_processing_dispatch_v1 import SourceProcessingDispatcher
        monkeypatch.setattr(SourceProcessingDispatcher, 'notify', lambda *_: None)
        form = build_form()
        stale_form = {**form, 'expected_generation': str(int(form['expected_generation']) - 1),
                      'annotation': first['annotation_id']}
        stale_post = client.post('/annotations/finalize', data=stale_form, follow_redirects=False)
        assert stale_post.status_code == 409
        assert first['annotation_id'] + '#annotation-document-check-title' in stale_post.text
        denied = outsider.post('/annotations/finalize', data=form, follow_redirects=False)
        assert 400 <= denied.status_code < 500 and 'location' not in denied.headers
        first_response = client.post('/annotations/finalize', data=form, follow_redirects=False)
        assert first_response.status_code == 303
        attempt_url = first_response.headers['location']
        assert client.post('/annotations/finalize', data=form, follow_redirects=False).headers['location'] == attempt_url
        pending = parse_qs(urlsplit(attempt_url).query)['attempt'][0]
        resumed = restart_production(console)
        assert native_attempt(resumed, sid, pending)['dispatch']['state'] == 'pending'
        assert build.correction_state(resumed, sid, oid) == 'building'
        blocked(resumed)

        with monkeypatch.context() as failed_worker:
            def stop(*args, **kwargs):
                raise ConsoleError('processing_timeout')
            failed_worker.setattr(resumed, '_verified_source_bytes', stop)
            with pytest.raises(ConsoleError, match='processing_timeout'):
                resumed.execute_source_selection(**actor, attempt=native_attempt(resumed, sid, pending))
        assert build.correction_state(resumed, sid, oid) == 'saved'
        blocked(resumed)
        status_page = client.get(attempt_url).text
        recover, = re.findall(r'<a [^>]*href="([^"]+)"[^>]*>Naar Documentcontrole</a>', status_page)
        recover = unescape(recover)
        assert urlsplit(recover).fragment == 'annotation-document-check-title'
        assert 'De bouw is gestopt' in client.get(recover).text
        retry = client.post('/annotations/finalize', data=build_form(), follow_redirects=False)
        assert retry.status_code == 303
        retry_id = parse_qs(urlsplit(retry.headers['location']).query)['attempt'][0]
        assert retry_id != pending
        resumed.execute_source_selection(**actor, attempt=native_attempt(resumed, sid, retry_id))

    latest = restart_production(console)
    corrected = object_for(latest, oid)
    assert corrected['object_version'] != before['object_version']
    assert corrected['metadata']['revision_lineage']['previous_object_version'] == before['object_version']
    assert object_for(latest, other_id) == untouched
    assert other_bindings(latest) == judgment
    assert build.correction_state(latest, sid, oid) is None
    audit = read_events(latest._ledger_path)
    saved_events = [event for event in audit if event['event_type'] == 'annotation_correction_saved']
    assert len(saved_events) == 1
    assert saved_events[0]['details']['affected_objects'] == [oid]
    assert saved_events[0]['details']['generation'] == saved.json()['generation']
    assert build.overview(latest, **actor)['document_round']['revision'] == 1
    assert latest.snapshot_is_published(sid) is False
    failed, succeeded = (native_attempt(latest, sid, key) for key in (pending, retry_id))
    assert (failed['state'], succeeded['state']) == ('failed', 'succeeded')
    assert failed['annotation_seal_id'] == succeeded['annotation_seal_id']


def review_page(console, sid, oid, username):
    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username': username, 'password': 'human-build-secret'})
        return client.get('/review', params={'document': sid, 'object': oid}).text


def corrected(production_console, tmp_path):
    console, actor, sid, original = saved_source(production_console, tmp_path, context_function='supported_by')
    execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    approve(console, sid, candidate(console, sid)['object_id'], reviewer)
    before = candidate(console, sid)  # approving with a confirmed type is itself a version
    request = correction_request(console, sid, original)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    saved = annotation.save(console, actor_id=reviewer, **request)
    return console, reviewer, sid, original, before, saved


def test_review_card_has_one_entry_and_shows_a_saved_correction_until_it_is_rebuilt(production_console, tmp_path):
    console, reviewer, sid, original, before, saved = corrected(production_console, tmp_path)
    oid = before['object_id']
    assert build.correction_state(console, sid, oid) == 'saved'
    page = review_page(console, sid, oid, 'reviewer')
    assert 'Correctie opgeslagen, nog niet opnieuw gebouwd' in page
    assert 'data-ko-rebuilding="saved"' in page
    assert page.count('Aanpassen in de kaart') == 1
    for gone in ('Bronselectie corrigeren', 'Wil je iets aanpassen?', 'Andere plek kiezen',
                 'Oorspronkelijke annotatie en bronbereiken bekijken'):
        assert gone not in page
    assert '<button class="ko-primary" type="submit" name="review_action" value="approve" disabled>' in page

    scope = {'actor_id': reviewer, 'snapshot_id': sid}
    command = closing(build.overview(console, **scope))
    assert command['expected_generation'] == saved['generation']
    result = build.finalize(console, actor_id=reviewer, **command)
    assert build.correction_state(console, sid, oid) == 'building'
    assert 'Nieuwe versie wordt opgebouwd' in review_page(console, sid, oid, 'reviewer')
    assert build.finalize(console, actor_id=reviewer, **command) == result
    console.execute_source_selection(actor_id=reviewer, snapshot_id=sid,
                                     attempt=native_attempt(console, sid, result['attempt_id']))
    after = candidate(console, sid)
    assert after['object_id'] == oid and after['object_version'] != before['object_version']
    assert after['metadata']['revision_lineage']['previous_object_version'] == before['object_version']
    assert build.correction_state(console, sid, oid) is None
    page = review_page(console, sid, oid, 'reviewer')
    assert 'opnieuw gebouwd na correctie van versie ' + before['object_version'] in page
    assert 'data-ko-rebuilding' not in page


def test_saved_correction_rejects_a_stale_document_build(production_console, tmp_path):
    console, reviewer, sid, _, before, saved = corrected(production_console, tmp_path)
    view = build.overview(console, actor_id=reviewer, snapshot_id=sid)
    outdated = {**closing(view), 'expected_generation': saved['generation'] - 1}
    with pytest.raises(ConsoleError, match='annotation_overview_stale'):
        build.finalize(console, actor_id=reviewer, **outdated)
    assert build.correction_state(console, sid, before['object_id']) == 'saved'
