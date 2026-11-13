"""#1064 part 2 (Class A): the independent second reviewer may reject; that decision is final.

Black-box lifecycle scenario of docs/change-contracts/1064-second-review-reject.md on native PostgreSQL.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from src.operations_console_v1 import ConsoleError
from src.review.knowledge_object_state_v1 import AFGEWEZEN, derive_ko_state
from src.review.review_duty_v1 import SECOND_REVIEW, review_stage
from src.review.review_ledger import read_events
from src.vorming import human_annotation_build_v1 as build
from src.vorming import human_annotation_v1 as annotation
from tests.ko_review_fixture_support import affirmative_assessment
from tests.production_support import restart_production
from tests.test_human_annotation_build_postgres import saved_source
from tests.test_human_annotation_review_postgres import (approve, correction_request, execute_build,
                                                         save_second_claim)


def four_eyes(production_console, tmp_path, **options):
    console, actor, sid, original = saved_source(production_console, tmp_path, review_option='two_others',
        four_eyes=True, context_function='supported_by', **options)
    second_claim = save_second_claim(console, actor, sid)
    execute_build(console, actor, sid)
    policy = console._envelope(sid)['review_policy']
    first, second = policy['primary'], policy['assignments'][0]['reviewer_id']
    ids = {o['metadata']['human_annotation']['annotation_id']: o['object_id'] for o in console.snapshot_objects(sid)
           if (o.get('metadata') or {}).get('human_annotation')}
    return console, actor, sid, original, first, second, ids[original['annotation_id']], ids[second_claim['annotation_id']]


def current(console, sid, oid):
    from src.review.revision_workflow import current_revisions
    return next(o for o in current_revisions(console.snapshot_objects(sid, include_blocked=True), snapshot_id=sid)
                if o['object_id'] == oid)


def state(console, sid, oid):
    return derive_ko_state(current(console, sid, oid), review_path='richtlijn', bindings=console.object_review_bindings(sid),
                           fragments=console.review_source_fragments(sid))['state']


def test_second_reviewer_rejects_and_the_document_publishes_without_that_object(production_console, tmp_path):
    from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore
    # The second claim is rejected: its evidence is also the first claim's, so every source passage stays
    # accounted. (Context that belongs only to a rejected object becomes open source text, exactly as after
    # a first-review rejection; see test_context_of_a_rejected_object_is_open_source_text_as_before.)
    console, actor, sid, _, first, second, kept, rejected = four_eyes(production_console, tmp_path,
        source_status='established', immutable_source_store=MemorySourceStore())
    for oid in (rejected, kept):
        approve(console, sid, oid, first)
        assert review_stage(current(console, sid, oid), review_path='richtlijn', bindings=console.object_review_bindings(sid),
                            fragments=console.review_source_fragments(sid)) == SECOND_REVIEW
    console.approve_second_review(actor_id=second, snapshot_id=sid, object_id=kept, assessment=affirmative_assessment())
    version = current(console, sid, rejected)['object_version']
    assert not console.publication_readiness(sid)['publication_ready']  # the open second review holds it

    before = console.objects_revision(sid)
    console.reject_second_review(actor_id=second, snapshot_id=sid, object_id=rejected,
                                 comment='Dit is geen zelfstandige kennis.', expected_revision=before)
    obj = current(console, sid, rejected)
    assert obj['object_version'] == version  # governance only, no new version
    assert obj['governance']['validation_status'] == 'rejected'
    assert obj['governance']['second_review']['status'] == 'rejected'
    assert state(console, sid, rejected) == AFGEWEZEN
    first_approvals = [b for b in console.object_review_bindings(sid) if b['object_id'] == rejected]
    assert first_approvals and not any(b['valid'] for b in first_approvals)  # kept as history, no longer counts
    event = [e for e in read_events(console._ledger_path) if e.get('event_type') == 'second_review_reject'][-1]
    assert event['object_id'] == rejected and event['details']['comment'] == 'Dit is geen zelfstandige kennis.'
    assert event['details']['first_approver_ids'] == [first] and event['details']['second_reviewer_id'] == second

    readiness = console.publication_readiness(sid)
    assert readiness['publication_ready'], readiness['blockers']
    resumed = restart_production(console)
    assert state(resumed, sid, rejected) == AFGEWEZEN
    publisher = resumed.create_account(username='publisher', password='human-publish-secret', roles=('publisher',))
    result = resumed.publish(actor_id=publisher['account_id'], snapshot_id=sid)
    assert result['status'] != 'BLOCKED', result
    assert result['published_items'] == 1
    from src.product_api_v1 import create_product_app
    from tests.test_product_api_v1 import paths, registry, headers
    from starlette.testclient import TestClient
    public = TestClient(create_product_app('real', paths=paths(tmp_path), tenant_registry=registry(docs=('*',)),
        canonical_publication_store=resumed.canonical_publication_store, immutable_source_store=resumed.immutable_source_store))
    served = public.get('/v1/knowledge/' + kept, headers=headers())
    assert served.status_code == 200 and served.json()['release']['release_id'] == result['release_id']
    assert public.get('/v1/knowledge/' + rejected, headers=headers()).status_code == 404


def test_refusals_change_nothing(production_console, tmp_path):
    console, actor, sid, _, first, second, rejected, _ = four_eyes(production_console, tmp_path)
    approve(console, sid, rejected, first)
    before = console.snapshot_objects(sid, include_blocked=True), console.object_review_bindings(sid)
    revision = console.objects_revision(sid)
    for kwargs, code in [
        ({'actor_id': first, 'comment': 'Eigen werk'}, 'independent_second_reviewer_required'),
        ({'actor_id': second, 'comment': '   '}, 'review_comment_required'),
        ({'actor_id': second, 'comment': 'Verouderd', 'expected_revision': 'stale'}, None),
        ({'actor_id': actor, 'comment': 'Niet benoemd'}, None),
    ]:
        with pytest.raises(ConsoleError) as refused:
            console.reject_second_review(snapshot_id=sid, object_id=rejected, **{'expected_revision': revision, **kwargs})
        if code:
            assert refused.value.code == code
    assert (console.snapshot_objects(sid, include_blocked=True), console.object_review_bindings(sid)) == before
    assert not [e for e in read_events(console._ledger_path) if e.get('event_type') == 'second_review_reject']


def test_one_of_approve_and_reject_wins_on_the_same_revision(production_console, tmp_path):
    console, _, sid, _, first, second, rejected, _ = four_eyes(production_console, tmp_path)
    approve(console, sid, rejected, first)
    revision = console.objects_revision(sid)
    console.reject_second_review(actor_id=second, snapshot_id=sid, object_id=rejected, comment='Geen kennis.',
                                 expected_revision=revision)
    with pytest.raises(ConsoleError):
        console.approve_second_review(actor_id=second, snapshot_id=sid, object_id=rejected,
                                      expected_revision=revision, assessment=affirmative_assessment())
    assert state(console, sid, rejected) == AFGEWEZEN


def test_a_correction_after_the_rejection_starts_again_at_the_first_review(production_console, tmp_path):
    console, actor, sid, original, first, second, rejected, _ = four_eyes(production_console, tmp_path)
    approve(console, sid, rejected, first)
    console.reject_second_review(actor_id=second, snapshot_id=sid, object_id=rejected, comment='Geen kennis.')
    version = current(console, sid, rejected)['object_version']
    request = correction_request(console, sid, original)
    next(a for a in request['selection']['ranges'] if a['role'] == 'evidence')['evidence_function'] = 'explains'
    saved = annotation.save(console, actor_id=first, **request)
    result = build.rebuild(console, actor_id=first, snapshot_id=sid, annotation_id=original['annotation_id'],
                           command_id='after-reject', expected_generation=saved['generation'])
    from src.vorming.worker_handover_v1 import native_attempt
    console.execute_source_selection(actor_id=first, snapshot_id=sid, attempt=native_attempt(console, sid, result['attempt_id']))
    obj = current(console, sid, rejected)
    assert obj['object_version'] != version
    assert obj['metadata']['revision_lineage']['previous_object_version'] == version
    assert obj['governance']['validation_status'] == 'needs_review'
    assert state(console, sid, rejected) != AFGEWEZEN
    # The corrector may do the first review of the new version; the second must be someone else.
    approve(console, sid, rejected, first)
    with pytest.raises(ConsoleError, match='independent_second_reviewer_required'):
        console.reject_second_review(actor_id=first, snapshot_id=sid, object_id=rejected, comment='Toch niet.')


@pytest.mark.parametrize('stage', ['first', 'second'])
def test_context_of_a_rejected_object_is_open_source_text_as_before(production_console, tmp_path, stage):
    """Existing behaviour, unchanged: the second reviewer's rejection has the same effect as the first's."""
    console, _, sid, _, first, second, rejected, other = four_eyes(production_console, tmp_path)
    approve(console, sid, other, first)
    console.approve_second_review(actor_id=second, snapshot_id=sid, object_id=other, assessment=affirmative_assessment())
    if stage == 'second':
        approve(console, sid, rejected, first)
        console.reject_second_review(actor_id=second, snapshot_id=sid, object_id=rejected, comment='Geen kennis.')
    else:
        console.review_object(actor_id=first, snapshot_id=sid, object_id=rejected, decision='reject', comment='Geen kennis.',
                              suitability='geen_kenniseenheid', eindoordeel='afwijzen')
    assert state(console, sid, rejected) == AFGEWEZEN
    assert 'source_passage_review_incomplete' in console.publication_readiness(sid)['blockers']


def test_second_reviewer_rejects_from_the_review_card_and_the_first_reviewer_reads_why(production_console, tmp_path):
    import re
    from starlette.testclient import TestClient
    from tests.production_support import application_for
    console, _, sid, _, first, second, rejected, _ = four_eyes(production_console, tmp_path)
    approve(console, sid, rejected, first)

    def login(client, account_id):
        client.post('/login', data={'username': console._account(account_id)['username'], 'password': 'human-build-secret'})

    with TestClient(application_for(console)) as client:
        login(client, second)
        page = client.get('/review', params={'document': sid, 'object': rejected}).text
        assert 'Onafhankelijk tweede akkoord' in page and 'Afwijzen met toelichting' in page
        form = page[page.index('<form method="post" action="/review/second-review"'):]
        form = form[:form.index('</form>')]
        hidden = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form))
        without = client.post('/review/second-review', data={**hidden, 'review_action': 'reject', 'comment': ''},
                              follow_redirects=False)
        assert without.status_code == 400 and state(console, sid, rejected) != AFGEWEZEN
        done = client.post('/review/second-review', data={**hidden, 'review_action': 'reject',
                           'comment': 'Dit is een kop, geen kennis.'}, follow_redirects=False)
        assert done.status_code == 303
    assert state(console, sid, rejected) == AFGEWEZEN
    with TestClient(application_for(console)) as client:
        login(client, first)
        page = client.get('/review', params={'document': sid, 'object': rejected}).text
    assert 'data-ko-rejected' in page
    assert ('Afgewezen in de tweede review door ' + console._account(second)['username']
            + ': Dit is een kop, geen kennis.') in page
    assert 'De passage kan nu niet worden goedgekeurd' not in page
