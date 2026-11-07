"""W1: complete HTTP repair is prepared without a write lock or SQL transaction.
# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit metrics slop releasebewijs
"""
from src.review.review_command_state_v1 import active_review_command
from src.workflows.workflow_transaction_v1 import workflow_transaction_active
from tests.test_a09_source_repair import setup_repair, repair, assert_complete


def test_complete_http_repair_prepares_before_transaction(tmp_path, monkeypatch, production_console, production_app):
    console, sid, obj, reviewer, fresh = setup_repair(tmp_path, production_console=production_console)
    units = console.source_units(snapshot_id=sid, object_id=obj['object_id'])
    observed = []
    original = console._source_repair

    def probe(**kwargs):
        state = active_review_command(console)
        observed.append((state is not None and state.preparing,
                         console._store_lock_depth, workflow_transaction_active()))
        return original(**kwargs)

    monkeypatch.setattr(console, '_source_repair', probe)
    response = repair(console, sid, obj, units[:1], production_app=production_app)
    assert response.status_code == 303, response.text
    assert observed == [(True, 0, False)]
    live = assert_complete(fresh(), sid, obj['object_id'])
    assert live['governance']['validation_status'] == 'needs_review'
    assert live['object_version'] != obj['object_version']
