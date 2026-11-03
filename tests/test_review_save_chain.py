"""Ordinary HTTP save and navigation use the existing prepared owners.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit metrics slop releasebewijs
"""
import re

import pytest

from tests.test_v233_review_audit_regressions import review_system


def form(client, sid, oid):
    page = client.get('/review', params={'document': sid, 'object': oid})
    assert page.status_code == 200
    revision = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text).group(1)
    return {'snapshot_id': sid, 'object_id': oid, 'snapshot_revision': revision,
            'suitability': 'ja', 'documentpositie_action': 'dit_klopt',
            'type_action': 'dit_klopt', 'confirmed_object_type': 'definition',
            'eindoordeel': 'goedkeuren', 'decision': 'approve', 'relation_review_ack': '1'}


def test_ordinary_http_kernel_runs_without_write_lock_or_workflow_io(review_system, monkeypatch):
    from src.review.review_command_state_v1 import active_review_command
    from src.workflows.workflow_transaction_v1 import workflow_transaction_active, WorkflowTransactionError
    console, client, sid, actor, ids = review_system
    data = form(client, sid, ids[0])
    original = console.review_object
    observed = []

    def probe(*args, **kwargs):
        state = active_review_command(console)
        if state is not None:
            assert not console._store_lock_depth, 'ordinary kernel still holds the outer write lock'
            assert not workflow_transaction_active(), 'ordinary kernel still holds a SQL transaction'
            assert state.preparing
            with pytest.raises(WorkflowTransactionError, match='workflow_io_during_review_preparation'):
                console.workflow_document_store._connect()
            observed.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(console, 'review_object', probe)
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    assert observed == [True]
    assert next(o for o in console.snapshot_objects(sid) if o['object_id'] == ids[0])['governance']['validation_status'] == 'approved'
    assert any(b['object_id'] == ids[0] and b['reviewer_id'] == actor for b in console.object_review_bindings(sid))


@pytest.mark.parametrize('task', ['', 'contextual'])
def test_next_passage_uses_verified_cards_then_real_passage(review_system, monkeypatch, task):
    from src.workflows.review_card_inputs_postgres_v1 import prepare_review_cards
    from tests.production_support import restart_production
    console, client, sid, _actor, ids = review_system
    prepare_review_cards(console.workflow_document_store, sid)
    data = {**form(client, sid, ids[0]), 'return_task': task}
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    store = console.workflow_document_store
    with monkeypatch.context() as patch:
        def forbidden(*args, **kwargs):
            raise AssertionError('next-passage navigation evaluated the complete document')
        patch.setattr(store, 'formation_input', forbidden)
        patch.setattr(store, 'review_document_window', forbidden)
        patch.setattr(store, 'list_document_objects', forbidden)
        page = client.get(saved.headers['location'])
    assert page.status_code == 200, page.text
    assert f'id="review-form-{ids[1]}"' in page.text
    assert f'id="review-form-{ids[0]}"' not in page.text
    reopened = client.get('/review', params={'document': sid, 'object': ids[0]})
    assert reopened.status_code == 200
    restarted = restart_production(console)
    assert next(o for o in restarted.snapshot_objects(sid) if o['object_id'] == ids[0])['governance']['validation_status'] == 'approved'
