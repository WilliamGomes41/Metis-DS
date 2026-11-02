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


def test_stage_versions_are_immutable_detached_and_getters_can_thaw():
    captured = inputs()
    with review_command_scope(captured) as state:
        rows = deepcopy(state.histories)
        rows[0]['governance'] = {'validation_status':'approved'}
        envelope = {'snapshot_id':'snapshot', 'review_passes':{'actor':{'valid':True}}}
        bindings = [{'object_id':'target', 'valid':True}]
        state.stage(objects=('snapshot', rows), envelopes={'snapshot':envelope},
                    bindings={'snapshot':bindings}, expected_revision=state.revision)
        revision = state.revision
        rows[0]['content']['clean_text'] = 'Caller mutation'
        envelope['review_passes']['actor']['valid'] = False
        bindings[0]['valid'] = False
        assert state.histories[0]['content']['clean_text'] == 'Exact source.'
        assert state.envelope['review_passes']['actor']['valid'] is True
        assert state.bindings[0]['valid'] is True
        for value in (state.histories[0], state.object_transitions[0][0], state.bindings[0]):
            with pytest.raises(ConsoleError, match='source_views_carrier_immutable'):
                value['in_place_mutation'] = True
        with pytest.raises(AttributeError):
            state.histories = []
        thawed = deepcopy(state.histories)
        thawed[0]['content']['clean_text'] = 'Disposable kernel copy'
        assert state.revision == revision
        assert state.histories[0]['content']['clean_text'] == 'Exact source.'


def test_nested_version_rollback_restores_token_and_transition_chain_before_next_stage():
    captured = inputs()
    with review_command_scope(captured) as state:
        def stage(label):
            rows = deepcopy(state.histories)
            rows[0]['governance'] = {'validation_status':label}
            state.stage(objects=('snapshot', rows), expected_revision=state.revision,
                envelopes={'snapshot':{'snapshot_id':'snapshot','review_passes':{label:True}}},
                bindings={'snapshot':[{'object_id':'target','state':label}]})
        stage('A')
        a = deepcopy((state.histories, state.envelope, state.bindings))
        token = state.revision
        with pytest.raises(RuntimeError, match='discard B'):
            with state.savepoint():
                stage('B')
                with state.savepoint():
                    stage('inner')
                raise RuntimeError('discard B')
        assert (state.histories, state.envelope, state.bindings) == tuple(a)
        assert state.revision == token and state.commit_count == 1
        assert len(state.object_transitions) == 1
        stage('C')
        assert state.revision != token and state.commit_count == 2
        assert [rows[0]['governance']['validation_status'] for rows in state.object_transitions] == ['A','C']


@pytest.mark.parametrize('klasse,public_source', [('richtlijn', True), ('beslisboom', False)])
def test_scoped_source_readers_keep_content_and_tree_contracts(klasse, public_source):
    from dataclasses import replace
    from src.operations_console_v1 import OperationsConsole
    captured = inputs()
    captured = replace(captured, envelope={'snapshot_id':'snapshot', 'class':klasse},
                       fragments=[{'fragment_id':'source-1'}])
    console = captured.owner
    console._verified_source_bytes = lambda envelope: OperationsConsole._verified_source_bytes(console, envelope)
    with review_command_scope(captured):
        # Low-level source/graph validation always receives pinned fragments.
        assert OperationsConsole._read_source_fragments(console, captured.envelope, None) is captured.fragments
        actual = OperationsConsole.review_source_fragments(console, 'snapshot')
        assert actual is (captured.fragments if public_source else None)
        if public_source:
            assert OperationsConsole.review_source_fragments(console, 'snapshot',
                envelope={**deepcopy(captured.envelope), 'sha256':'different-source'}) is None
            with pytest.raises(ConsoleError, match='source_lineage_unavailable'):
                OperationsConsole._read_source_fragments(console,
                    {**deepcopy(captured.envelope), 'sha256':'different-source'}, None)
