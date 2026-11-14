"""#1072, besluit William 2026-11-14 (optie A): the review duty follows a v1 configuration that needs two approvals.

Black-box on native PostgreSQL, from intake to publication readiness. The publication gate already demands both
people (``configured_approval``, B10); the review duty now asks the second one, so the document can be published.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale herstart
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from src.operations_console_v1 import ConsoleError
from tests.production_support import restart_production

from src.review.review_duty_v1 import FIRST_REVIEW, SECOND_REVIEW, review_stage
from src.review.revision_workflow import current_revisions
from src.vorming import human_annotation_v1 as annotation
from src.vorming.source_bound_fields_v3 import FIELDS
from tests.ko_review_fixture_support import affirmative_assessment
from tests.test_human_annotation_postgres import anchor, command
from tests.test_human_annotation_review_postgres import approve, execute_build

REVIEW_BLOCKERS = {'review_configuration_approval_missing', 'second_named_reviewer_required', 'four_eyes_required',
                   'required_policy_review_missing', 'object_tuple_required'}


def _document(production_console, tmp_path, *, option, four_eyes):
    console = production_console(root=tmp_path)
    uploader = console.create_account(username='builder', password='human-build-secret',
                                      roles=('researcher', 'reviewer'))['account_id']
    first = console.create_account(username='reviewer', password='human-build-secret', roles=('reviewer',))['account_id']
    other = console.create_account(username='reviewer2', password='human-build-secret', roles=('reviewer',))['account_id']
    reviewers = [first, other] if option == 'two_others' else [first]
    sid = console.receive_source(actor_id=uploader, filename='v1.html', content_type='text/html',
        data=b'<html><body><p>De kwetsbare huid verklaart de pijn.</p></body></html>',
        ingest_kind='new', title='v1', version='1.0', date='2026-11-14', live_url='', class_='richtlijn',
        family='test', named_reviewers=[], review_choice={'contract': 'review-configuration-v1', 'option': option,
        'four_eyes_required': four_eyes, 'reviewers': reviewers, 'readers': []})['snapshot_id']
    view = annotation.prepare(console, actor_id=uploader, snapshot_id=sid, expected_revision=console.objects_revision(sid))
    core = anchor(view, 'De kwetsbare')
    fields = {key: {'span': None, 'missing_reason': 'not_applicable'} for key in FIELDS}
    for field, text in [('subject_span', 'De kwetsbare huid'), ('predicate_span', 'verklaart'),
                        ('supported_object', 'de pijn')]:
        start = core['quote'].index(text)
        fields[field] = {'span': {'block_id': core['block_id'], 'start': start, 'end': start + len(text)},
                         'missing_reason': None, 'quote': text}
    fields.update(type_evidence_spans={'core': True}, support_span={'core': True})
    request = command(view, ranges=[core], status='ready')
    request['selection'].update(object_type='explanation', evidence_not_applicable=True, field_evidence=fields,
                                required_links=[])
    annotation.save(console, actor_id=uploader, **request)
    execute_build(console, uploader, sid)
    oid = next(o['object_id'] for o in console.snapshot_objects(sid) if (o.get('metadata') or {}).get('human_annotation'))
    second = other if option == 'two_others' else uploader
    return console, sid, oid, first, second


def _stage(console, sid, oid):
    obj = next(o for o in current_revisions(console.snapshot_objects(sid, include_blocked=True), snapshot_id=sid)
               if o['object_id'] == oid)
    return review_stage(obj, review_path='richtlijn', bindings=console.object_review_bindings(sid),
                        fragments=console.review_source_fragments(sid))


@pytest.mark.parametrize('option,four_eyes', [('two_others', False), ('two_others', True), ('one_other', True)])
def test_a_v1_configuration_that_needs_two_approvals_asks_the_second_person(production_console, tmp_path,
                                                                             option, four_eyes):
    console, sid, oid, first, second = _document(production_console, tmp_path, option=option, four_eyes=four_eyes)
    assert _stage(console, sid, oid) == FIRST_REVIEW
    approve(console, sid, oid, first)
    # The publication gate still waits for the second person; the duty now asks them instead of closing.
    assert _stage(console, sid, oid) == SECOND_REVIEW
    assert REVIEW_BLOCKERS & set(console.publication_readiness(sid)['blockers'])
    console.approve_second_review(actor_id=second, snapshot_id=sid, object_id=oid, assessment=affirmative_assessment(),
                                  evidence_not_applicable=True)
    assert _stage(console, sid, oid) is None
    assert not REVIEW_BLOCKERS & set(console.publication_readiness(sid)['blockers'])


@pytest.mark.parametrize('option,four_eyes', [('one_other', False), ('uploader_sole', False)])
def test_a_v1_configuration_with_one_approval_is_unchanged(production_console, tmp_path, option, four_eyes):
    from src.review.review_configuration_v1 import policy_for_configuration
    configuration = {'contract': 'review-configuration-v1', 'option': option, 'four_eyes_required': four_eyes,
                     'reviewers': ['r1'] if option == 'one_other' else [], 'readers': [], 'revision': 1,
                     'locked_at': None, 'source': 'chosen'}
    assert policy_for_configuration(configuration, uploader_id='up') is None


def test_the_second_duty_survives_a_restart_and_one_approval_wins(production_console, tmp_path):
    """Opslag: the derived policy is durable (herstart), and the second approval is guarded by the exact revision
    (stale), and the same approval arriving twice counts once (concurrent)."""
    console, sid, oid, first, second = _document(production_console, tmp_path, option='two_others', four_eyes=False)
    approve(console, sid, oid, first)
    console = restart_production(console)
    assert _stage(console, sid, oid) == SECOND_REVIEW
    revision = console.objects_revision(sid)
    with pytest.raises(ConsoleError):
        console.approve_second_review(actor_id=second, snapshot_id=sid, object_id=oid, expected_revision='stale',
                                      assessment=affirmative_assessment(), evidence_not_applicable=True)
    assert _stage(console, sid, oid) == SECOND_REVIEW
    console.approve_second_review(actor_id=second, snapshot_id=sid, object_id=oid, expected_revision=revision,
                                  assessment=affirmative_assessment(), evidence_not_applicable=True)
    # The same approval arriving twice (a retry or a second tab) counts once: it changes nothing.
    before = console.snapshot_objects(sid, include_blocked=True), console.object_review_bindings(sid)
    try:
        console.approve_second_review(actor_id=second, snapshot_id=sid, object_id=oid, expected_revision=revision,
                                      assessment=affirmative_assessment(), evidence_not_applicable=True)
    except ConsoleError:
        pass
    assert (console.snapshot_objects(sid, include_blocked=True), console.object_review_bindings(sid)) == before
    assert _stage(console, sid, oid) is None


def test_an_uploader_without_review_role_is_refused_where_their_approval_is_required(production_console, tmp_path):
    """Codex P2: v1 one_other with four eyes needs the uploader's approval. An uploader without the reviewer role
    could never give it; such a document used to be accepted and stay unpublishable. Now the intake refuses it,
    as it already did for v2 uploader_and_other, and stores nothing."""
    console = production_console(root=tmp_path)
    uploader = console.create_account(username='researcher', password='human-build-secret',
                                      roles=('researcher',))['account_id']
    first = console.create_account(username='reviewer', password='human-build-secret', roles=('reviewer',))['account_id']
    with pytest.raises(ConsoleError) as refused:
        console.receive_source(actor_id=uploader, filename='v1.html', content_type='text/html',
            data=b'<html><body><p>De kwetsbare huid verklaart de pijn.</p></body></html>',
            ingest_kind='new', title='v1', version='1.0', date='2026-11-14', live_url='', class_='richtlijn',
            family='test', named_reviewers=[], review_choice={'contract': 'review-configuration-v1',
            'option': 'one_other', 'four_eyes_required': True, 'reviewers': [first], 'readers': []})
    assert refused.value.code == 'reviewer_role_required'
    assert console.list_envelopes() == []


def test_named_reviewers_given_by_username_still_match_the_derived_policy(production_console, tmp_path):
    """Codex P2: receive_source accepts usernames for named_reviewers; the derived policy is compared after they
    resolve to account IDs, as before."""
    console = production_console(root=tmp_path)
    uploader = console.create_account(username='builder', password='human-build-secret',
                                      roles=('researcher', 'reviewer'))['account_id']
    first = console.create_account(username='reviewer', password='human-build-secret', roles=('reviewer',))['account_id']
    other = console.create_account(username='reviewer2', password='human-build-secret', roles=('reviewer',))['account_id']
    sid = console.receive_source(actor_id=uploader, filename='v1.html', content_type='text/html',
        data=b'<html><body><p>De kwetsbare huid verklaart de pijn.</p></body></html>',
        ingest_kind='new', title='v1', version='1.0', date='2026-11-14', live_url='', class_='richtlijn',
        family='test', named_reviewers=['reviewer', 'reviewer2'], review_choice={'contract': 'review-configuration-v1',
        'option': 'two_others', 'four_eyes_required': False, 'reviewers': [first, other], 'readers': []})['snapshot_id']
    policy = console._envelope(sid)['review_policy']
    assert policy['primary'] == first and [a['reviewer_id'] for a in policy['assignments']] == [other]
