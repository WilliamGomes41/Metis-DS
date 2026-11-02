"""Native user-path proof: retained history must leave ordinary Review bounded.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit metrics slop releasebewijs
"""
import importlib


def test_native_review_does_not_reload_retained_histories(tmp_path, production_console, monkeypatch):
    from tests.test_t9_review_knowledge_authority import _console, _approve
    console, reviewer, sid, focal = _console(tmp_path, production_console=production_console)

    def forbidden(*args, **kwargs):
        raise AssertionError('ordinary Review reread the retained history')
    monkeypatch.setattr(console.workflow_document_store, 'review_command_histories', forbidden)
    _approve(console, reviewer, sid, focal)
    current = next(o for o in console.snapshot_objects(sid) if o['object_id'] == focal['object_id'])
    assert current['governance']['validation_status'] == 'approved'
    assert console.object_review_bindings(sid)


def test_native_retained_history_partial_formation_http_budget(tmp_path, production_console, monkeypatch):
    # Reuse the existing full release probe without changing its source workload,
    # functional assertions or3s/5s budgets. No second synthetic candidate creator.
    probe = importlib.import_module('evidence.review-scoped-951.combined_probe')
    probe.test_partial_formation_history_existing_decision_and_http_command_together(
        tmp_path, production_console, monkeypatch, 'compact')
