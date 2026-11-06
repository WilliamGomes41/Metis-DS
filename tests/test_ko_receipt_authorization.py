"""The saved bon freshly authorizes within its bounded workflow snapshot.

# release-control-evidence: scope/belofte toegang opslag slop releasebewijs
"""
import pytest

from src.operations_console_v1 import ConsoleError
from src.review.ko_receipt_ui_v1 import read_saved_review
from src.workflows.account_retirement_v1 import retire_account
from src.workflows.workflow_transaction_v1 import workflow_transaction_active
from tests.test_ko_new_pages import compact_submission
from tests.test_ko_receipt_ui import prepared
from tests.test_review_command_bounded_http_v1 import physical_state


@pytest.mark.parametrize('change', ['role_revoked', 'retired', 'not_named', 'foreign_event'])
def test_stale_account_cannot_authorize_a_saved_bon(tmp_path, production_console, monkeypatch, change):
    console, sid, reviewer, obj, client, page, _ = prepared(tmp_path, production_console, monkeypatch)
    data = compact_submission(page)
    assert client.post('/review', data=data, follow_redirects=False).status_code == 303
    stale = console._account(reviewer)
    if change == 'role_revoked':
        console.workflow_identity_store.update_roles(reviewer, ['researcher'])
    elif change == 'retired':
        publisher = console.create_account(username='operator', password='fixture-only', roles=('publisher',))
        with console.workflow_identity_store._connect() as connection:
            retire_account(connection, account_id=reviewer, actor_id=publisher['account_id'],
                           reason='Receipt authorization regression', apply=True)
    else:
        stale = console.create_account(username='other', password='fixture-only', roles=('reviewer',))
        if change == 'foreign_event':
            publisher = console.create_account(username='operator', password='fixture-only', roles=('publisher',))
            console.manage_review_participation(actor_id=publisher['account_id'], snapshot_id=sid,
                action='add_optional', reviewer_id=stale['account_id'], reason='Receipt ownership regression',
                command_id='receipt-add', expected_revision=console.objects_revision(sid))
    before = physical_state(console, sid)
    original = console.workflow_identity_store.account_by_id
    reads = []

    def fresh_account(account_id, **kwargs):
        assert workflow_transaction_active()
        assert not kwargs.get('for_share') and not kwargs.get('for_key_share')
        reads.append(account_id)
        return original(account_id, **kwargs)

    monkeypatch.setattr(console.workflow_identity_store, 'account_by_id', fresh_account)
    if change == 'foreign_event':
        assert read_saved_review(console, stale, sid, obj['object_id'], data['interaction_id']) is None
    else:
        def no_private_event_read(*args, **kwargs):
            raise AssertionError('Authorization must precede private event access')

        monkeypatch.setattr(console.workflow_review_store, 'read_review_command_events', no_private_event_read)
        expected = {'role_revoked': 'reviewer_role_required', 'retired': 'not_authenticated',
                    'not_named': 'reviewer_not_named_on_snapshot'}[change]
        with pytest.raises(ConsoleError, match=expected):
            read_saved_review(console, stale, sid, obj['object_id'], data['interaction_id'])
    assert reads == [stale['account_id']]
    assert physical_state(console, sid) == before


def test_saved_bon_uses_three_physical_connections_and_separate_publication_authority(
        tmp_path, production_console, monkeypatch):
    import psycopg
    console, sid, _, _, client, page, _ = prepared(tmp_path, production_console, monkeypatch)
    saved = client.post('/review', data=compact_submission(page), follow_redirects=False)
    assert saved.status_code == 303
    original_status = console.document_release_serving_status
    canonical_reads = []

    def canonical_status(snapshot_id, **kwargs):
        assert not workflow_transaction_active()
        canonical_reads.append(snapshot_id)
        return original_status(snapshot_id, **kwargs)

    monkeypatch.setattr(console, 'document_release_serving_status', canonical_status)
    original_connect = psycopg.connect
    connections = []

    def connect(*args, **kwargs):
        connections.append(1)
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(psycopg, 'connect', connect)
    result = client.get(saved.headers['location'])
    assert result.status_code == 200 and result.text.count('data-answer="yes"') == 3
    assert canonical_reads == [sid]
    assert len(connections) == 3
