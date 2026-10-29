"""Ownership and nested-failure controls for the bounded command workspace.

Native transaction/delta behavior is verified separately on PostgreSQL.
# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.operations_console_v1 import ConsoleError
from src.review.review_command_state_v1 import (
    ReviewCommandInputs, active_review_command, review_bindings_view,
    review_command_scope, review_envelopes_view,
)
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore

pytestmark = pytest.mark.pure_function


def inputs():
    owner = SimpleNamespace(
        workflow_document_store=SimpleNamespace(
            revision_for_rows=PostgresConcurrentWorkflowDocumentStore._revision_token),
        _ledger_path=Path('/tmp/review-state-ledger'),
        _envelopes={'other': {'snapshot_id': 'other'}},
        _bindings={'other': [{'object_id': 'other'}]},
    )
    return ReviewCommandInputs(owner, 'snapshot', {'snapshot_id': 'snapshot'},
        [{'object_id': 'target', 'object_version': '1.0', 'content': {'clean_text': 'Exact source.'}}],
        [], None, b'source', Path('/tmp/frozen-source'), 'target')


def test_staging_is_detached_from_inputs_and_shared_maps():
    captured = inputs()
    baseline = deepcopy(captured.histories)
    shared = deepcopy((captured.owner._bindings, captured.owner._envelopes))
    with pytest.raises(ConsoleError, match='source_views_carrier_immutable'):
        captured.histories[0]['content']['clean_text'] = 'Mutate baseline.'
    with review_command_scope(captured) as state:
        assert set(review_bindings_view(captured.owner)) == {'snapshot'}
        assert set(review_envelopes_view(captured.owner)) == {'snapshot'}
        proposed = deepcopy(state.histories)
        proposed[0]['governance'] = {'validation_status': 'approved'}
        state.stage(objects=('snapshot', proposed), expected_revision=state.revision)
        proposed[0]['content']['clean_text'] = 'Changed caller copy.'
        assert state.histories[0]['content']['clean_text'] == 'Exact source.'
        assert captured.histories == baseline
        assert (captured.owner._bindings, captured.owner._envelopes) == shared
    assert active_review_command(captured.owner) is None
    assert review_bindings_view(captured.owner) is captured.owner._bindings


def test_caught_nested_failure_restores_staged_state_and_freshness():
    captured = inputs()
    with review_command_scope(captured) as state:
        initial_revision = state.revision
        with pytest.raises(RuntimeError, match='nested failure'):
            with state.savepoint():
                proposed = deepcopy(state.histories)
                proposed[0]['object_version'] = '1.1'
                state.stage(objects=('snapshot', proposed), expected_revision=initial_revision)
                raise RuntimeError('nested failure')
        assert state.revision == initial_revision
        assert state.commit_count == 0
        assert state.object_transitions == []
        # An explicit unchanged later-commit still invalidates the old form.
        state.stage(objects=('snapshot', state.histories), expected_revision=initial_revision)
        assert state.commit_count == 1


def test_scope_rejects_foreign_snapshot_and_stale_staging():
    captured = inputs()
    with review_command_scope(captured) as state:
        assert active_review_command(object()) is None
        with pytest.raises(ConsoleError, match='review_command_snapshot_mismatch'):
            active_review_command(captured.owner, 'other')
        with pytest.raises(ConsoleError, match='review_command_snapshot_mismatch'):
            state.stage(snapshot_id='snapshot', objects=('other', state.histories))
        with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
            state.stage(objects=('snapshot', state.histories), expected_revision='stale')
        assert state.commit_count == 0
