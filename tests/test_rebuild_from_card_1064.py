"""#1064: a reviewer corrects in the card, rebuilds with one button, and finds the new version in Review.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest
from starlette.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_v1 as annotation
from tests.production_support import application_for
from tests.test_human_annotation_build_postgres import saved_source
from tests.test_human_annotation_review_postgres import approve, candidate, correction_request, execute_build


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

    # One button: the existing build starts, the review card says so, and the new version follows.
    result = build.rebuild(console, actor_id=reviewer, snapshot_id=sid, annotation_id=original['annotation_id'],
                           command_id='rebuild-1', expected_generation=saved['generation'])
    assert result['started'] and result['object_id'] == oid
    assert build.correction_state(console, sid, oid) == 'building'
    assert 'Nieuwe versie wordt opgebouwd' in review_page(console, sid, oid, 'reviewer')
    # Asking again while it builds starts nothing new.
    again = build.rebuild(console, actor_id=reviewer, snapshot_id=sid, annotation_id=original['annotation_id'],
                          command_id='rebuild-2', expected_generation=saved['generation'])
    assert again == {**result, 'started': False}
    from src.vorming.worker_handover_v1 import native_attempt
    console.execute_source_selection(actor_id=reviewer, snapshot_id=sid,
                                     attempt=native_attempt(console, sid, result['attempt_id']))
    after = candidate(console, sid)
    assert after['object_id'] == oid and after['object_version'] != before['object_version']
    assert after['metadata']['revision_lineage']['previous_object_version'] == before['object_version']
    assert build.correction_state(console, sid, oid) is None
    page = review_page(console, sid, oid, 'reviewer')
    assert 'opnieuw gebouwd na correctie van versie ' + before['object_version'] in page
    assert 'data-ko-rebuilding' not in page


def test_rebuild_refuses_a_card_that_is_behind_and_an_object_that_was_never_built(production_console, tmp_path):
    console, reviewer, sid, original, _, saved = corrected(production_console, tmp_path)
    with pytest.raises(ConsoleError) as stale:
        build.rebuild(console, actor_id=reviewer, snapshot_id=sid, annotation_id=original['annotation_id'],
                      command_id='stale', expected_generation=saved['generation'] - 1)
    assert stale.value.code == 'annotation_overview_stale'
    with pytest.raises(ConsoleError) as unknown:
        build.rebuild(console, actor_id=reviewer, snapshot_id=sid, annotation_id='00000000-0000-4000-8000-000000000000',
                      command_id='unknown', expected_generation=saved['generation'])
    assert unknown.value.code == 'annotation_command_invalid'
    assert build.correction_state(console, sid, candidate(console, sid)['object_id']) == 'saved'


def test_the_route_starts_the_build_and_returns_the_review_card(production_console, tmp_path):
    console, reviewer, sid, original, before, saved = corrected(production_console, tmp_path)
    with TestClient(application_for(console)) as client:
        client.post('/login', data={'username': 'reviewer', 'password': 'human-build-secret'})
        refused = client.post('/annotations/rebuild', json={'document': sid, 'annotation': original['annotation_id'],
            'command_id': 'route-0', 'expected_generation': saved['generation'] - 1})
        assert refused.status_code == 409 and refused.json()['error'] == 'annotation_overview_stale'
        started = client.post('/annotations/rebuild', json={'document': sid, 'annotation': original['annotation_id'],
            'command_id': 'route-1', 'expected_generation': saved['generation']})
    assert started.status_code == 200
    assert started.json()['review_url'] == f"/review?document={sid}&object={before['object_id']}"
    assert build.correction_state(console, sid, before['object_id']) in {'building', None}
