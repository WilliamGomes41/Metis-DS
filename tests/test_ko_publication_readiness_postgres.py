"""KO-3: explain existing publication blockers without changing their authority.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.integrity_kernel import stamp_canonical_hashes
from src.publication.publication_readiness_v1 import (
    PublicationReadinessMixin,
    REVIEW_DISPOSITION_INCONSISTENT,
    REVIEW_REPAIR_INCOMPLETE,
    REVIEW_WORK_INCOMPLETE,
    SOURCE_PASSAGE_REVIEW_INCOMPLETE,
)
from src.review.knowledge_path_v1 import content_reviewable
from tests.semantic_fixture_support import install_fixture_history
from tests.test_review_command_bounded_http_v1 import physical_state
from tests.test_t12_publication_readiness_authority import _console


def _durable(console, snapshot_id):
    return deepcopy((physical_state(console, snapshot_id),
                     console.workflow_review_store.read_events_for_snapshots([snapshot_id])))


def _row(considered, object_id):
    return next(row for row in considered['object_readiness'] if row['object_id'] == object_id)


def test_missing_support_keeps_the_existing_first_review_obligation(tmp_path, *, production_console):
    console, sid = _console(tmp_path, production_console=production_console)
    candidate = next(obj for obj in console.snapshot_objects(sid) if content_reviewable(obj))
    before = _durable(console, sid)

    considered = console.publication_readiness(sid)

    row = _row(considered, candidate['object_id'])
    assert row['state'] == 'Bewijs open'
    assert row['review_stage'] == 'first_review'
    assert REVIEW_WORK_INCOMPLETE in row['blockers']
    assert SOURCE_PASSAGE_REVIEW_INCOMPLETE in row['blockers']
    assert considered['publication_ready'] is False
    assert _durable(console, sid) == before


def test_recorded_approval_without_binding_remains_open_and_does_not_write(tmp_path, *, production_console):
    console, sid = _console(tmp_path, production_console=production_console)
    objects = console.snapshot_objects(sid)
    candidate = next(obj for obj in objects if content_reviewable(obj))
    candidate['object_type'] = candidate['confirmed_object_type'] = 'definition'
    candidate['governance']['validation_status'] = 'approved'
    stamp_canonical_hashes(candidate)
    install_fixture_history(console, sid, objects)
    before = _durable(console, sid)

    considered = console.publication_readiness(sid)

    row = _row(considered, candidate['object_id'])
    assert row['state'] == 'In review'
    assert 'approved_without_current_binding' in row['invalid']
    assert REVIEW_WORK_INCOMPLETE in row['blockers']
    assert considered['publication_ready'] is False
    assert _durable(console, sid) == before


def test_legacy_revision_keeps_its_existing_content_repair_blocker(tmp_path, *, production_console):
    console, sid = _console(tmp_path, production_console=production_console)
    objects = console.snapshot_objects(sid)
    candidate = next(obj for obj in objects if content_reviewable(obj))
    candidate['governance']['validation_status'] = 'revise'
    stamp_canonical_hashes(candidate)
    install_fixture_history(console, sid, objects)
    before = _durable(console, sid)

    considered = console.publication_readiness(sid)

    row = _row(considered, candidate['object_id'])
    assert row['state'] == 'Kandidaat'
    assert REVIEW_REPAIR_INCOMPLETE in row['blockers']
    assert considered['review_repair_object_ids'] == [candidate['object_id']]
    assert _durable(console, sid) == before


@pytest.mark.parametrize('closure,action', [('waiting_on_target', 'none'), ('repair_required', 'technical_repair')])
def test_non_ko_source_obligations_do_not_become_content_repair(monkeypatch, closure, action):
    from src.publication import publication_readiness_v1 as readiness

    class Authority(PublicationReadinessMixin):
        def snapshot_objects(self, snapshot_id, **kwargs):
            return [{'object_id': 'source', 'object_type': 'source_record', 'object_version': '1'}]

        def technical_publication_readiness(self, **kwargs):
            return {'blockers': [], 'publishable_object_count': 1}

    monkeypatch.setattr(readiness, 'review_duties', lambda *a, **k: [])
    monkeypatch.setattr(readiness, 'review_repair_duties', lambda *a, **k: [])
    monkeypatch.setattr(readiness, 'source_accountability', lambda *a, **k: {
        'source': {'required': True, 'closure': closure, 'human_action': action}})
    monkeypatch.setattr(readiness, 'derive_ko_state', lambda *a, **k: {
        'state': None, 'reasons': ['not_knowledge_object'], 'invalid': []})

    considered = Authority().publication_readiness('snapshot')

    row = _row(considered, 'source')
    assert row['state'] is None
    assert row['blockers'] == [SOURCE_PASSAGE_REVIEW_INCOMPLETE]
    assert considered['curation_blockers'] == [SOURCE_PASSAGE_REVIEW_INCOMPLETE]
    assert considered['review_repair_duty_count'] == 0
    assert considered['publication_ready'] is False


def test_orphan_disposition_conflict_remains_a_global_blocker():
    class Authority(PublicationReadinessMixin):
        def snapshot_objects(self, snapshot_id, **kwargs):
            return []

        def technical_publication_readiness(self, **kwargs):
            return {'blockers': [REVIEW_DISPOSITION_INCONSISTENT],
                    'disposition_conflict_object_ids': ['removed-object'],
                    'publishable_object_count': 1}

    considered = Authority().publication_readiness('snapshot')

    assert considered['object_readiness'] == []
    assert considered['curation_blockers'] == [REVIEW_DISPOSITION_INCONSISTENT]
    assert considered['publication_ready'] is False


def test_all_rejected_objects_do_not_make_an_empty_publication_ready(tmp_path, *, production_console):
    console, sid = _console(tmp_path, production_console=production_console)
    reviewer_id = console._envelope(sid)['named_reviewers'][0]
    candidate = next(obj for obj in console.snapshot_objects(sid) if content_reviewable(obj))
    console.review_object(actor_id=reviewer_id, snapshot_id=sid, object_id=candidate['object_id'],
        decision='reject', suitability='ja', eindoordeel='afwijzen', comment='Niet opnemen.')

    considered = console.publication_readiness(sid)

    assert _row(considered, candidate['object_id'])['state'] == 'Afgewezen'
    assert considered['publishable_object_count'] == 0
    assert considered['publication_ready'] is False
    assert 'object_tuple_required' in considered['blockers']


def test_native_badge_sql_and_prepared_cards_share_final_statuses(tmp_path, *, production_console):
    from tests.test_console_list_reads_postgres_v1 import _envelope, _object

    console, original_sid = _console(tmp_path, production_console=production_console)
    account_id = console._envelope(original_sid)['uploader_account_id']
    statuses = ('approved', 'rejected', 'superseded', 'revise', 'needs_review', None, 'unknown')
    expected = {}
    inputs = {}
    for index, status in enumerate(statuses):
        sid = original_sid + '-badge-' + str(index)
        objects = [_object(sid, 0, object_type='document', validation_status='approved'),
                   _object(sid, 1, object_type='definition', validation_status=status)]
        envelope = _envelope(sid, '0' * 32, account_id)
        console.workflow_document_store.write_bundle(envelope=envelope, objects=objects)
        inputs[sid] = {'envelope': envelope, 'objects': objects}
        expected[sid] = status not in ('approved', 'rejected', 'superseded')
    sid = original_sid + '-document-only'
    objects = [_object(sid, 0, object_type='document', validation_status='needs_review')]
    envelope = _envelope(sid, '0' * 32, account_id)
    console.workflow_document_store.write_bundle(envelope=envelope, objects=objects)
    inputs[sid] = {'envelope': envelope, 'objects': objects}
    expected[sid] = False

    selected = console._workflow_list_status_rows(list(expected))
    all_rows = console._workflow_list_status_rows()
    prepared = console._workflow_list_status_rows(list(expected), card_inputs=inputs)

    for sid, opened in expected.items():
        assert selected[sid]['has_open_review'] is opened
        assert all_rows[sid]['has_open_review'] is opened
        assert prepared[sid]['has_open_review'] is opened


def test_selected_publish_page_explains_open_objects_without_changing_work(tmp_path, *, production_console, production_app):
    from fastapi.testclient import TestClient

    console, sid = _console(tmp_path, production_console=production_console)
    console.create_account(username='publisher', password='test-publisher', roles=('publisher',))
    candidate = next(obj for obj in console.snapshot_objects(sid) if content_reviewable(obj))
    before = _durable(console, sid)
    client = TestClient(production_app(console), base_url='https://testserver')
    assert client.post('/login', data={'username': 'publisher', 'password': 'test-publisher'},
                       follow_redirects=False).status_code == 303

    overview = client.get('/publish')
    selected = client.get('/publish', params={'document': sid})

    assert overview.status_code == selected.status_code == 200
    assert 'data-object-readiness' not in overview.text
    assert 'data-publish-form' not in overview.text
    assert f'data-readiness-object="{candidate["object_id"]}"' in selected.text
    assert 'data-ko-state="Bewijs open"' in selected.text
    assert 'De eerste beoordeling staat nog open.' in selected.text
    assert 'data-publish-form' not in selected.text
    assert _durable(console, sid) == before


@pytest.mark.parametrize('error_type', [KeyError, TypeError, ValueError])
def test_unavailable_object_state_returns_structured_unknown_readiness(monkeypatch, tmp_path, error_type, *, production_console):
    from src.publication import publication_readiness_v1 as readiness

    console, sid = _console(tmp_path, production_console=production_console)
    before = _durable(console, sid)

    def unavailable(*args, **kwargs):
        raise error_type('state facts unavailable')

    monkeypatch.setattr(readiness, 'derive_ko_state', unavailable)

    considered = console.publication_readiness(sid)

    assert considered['publication_ready'] is False
    assert considered['curation_complete_known'] is False
    assert considered['technical_blockers'] == ['readiness_authority_unavailable']
    assert considered['authority_error'] == error_type.__name__
    assert _durable(console, sid) == before
