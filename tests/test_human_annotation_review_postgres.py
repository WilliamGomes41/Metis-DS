"""Human corrections use the actual workflow/revision/review authorities.

# release-control-evidence: scope/belofte opslag concurrent stale recovery toegang kwaliteit releasebewijs
"""
from copy import deepcopy
from uuid import uuid4

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_v1 as annotation
from src.vorming import human_annotation_build_v1 as build
from tests.production_support import restart_production
from tests.test_human_annotation_build_postgres import saved_source, closing


def execute_build(console, actor, sid):
    receipt = build.finalize(console, actor_id=actor,
        **closing(build.overview(console, actor_id=actor, snapshot_id=sid)))
    from src.vorming.worker_handover_v1 import native_attempt
    console.execute_source_selection(actor_id=actor, snapshot_id=sid,
        attempt=native_attempt(console, sid, receipt['attempt_id']))
    return receipt


def candidate(console, sid):
    return next(obj for obj in console.snapshot_objects(sid, include_blocked=True)
                if (obj.get('metadata') or {}).get('human_annotation'))


@pytest.mark.parametrize('storage', ['legacy', 'v1'])
def test_original_annotation_corrects_evidence_without_losing_confirmed_type(
        production_console, tmp_path, monkeypatch, storage):
    monkeypatch.setenv('METIS_DOCUMENT_INPUT_STORAGE', storage)
    if storage == 'v1':
        monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console, actor, sid, original = saved_source(production_console, tmp_path,
        context_function='supported_by')
    first = execute_build(console, actor, sid)
    reviewer = console._envelope(sid)['named_reviewers'][0]
    before = candidate(console, sid)
    console.confirm_object_type(actor_id=reviewer, snapshot_id=sid,
        object_id=before['object_id'], confirmed_object_type='explanation',
        expected_revision=console.objects_revision(sid))
    before = candidate(console, sid)
    correction = {**deepcopy(original), 'command_id': str(uuid4()),
        'expected_revision': 1, 'expected_generation': 1,
        'expected_objects_revision': console.objects_revision(sid)}
    evidence = next(a for a in correction['selection']['ranges'] if a['role'] == 'evidence')
    evidence['evidence_function'] = 'explains'
    saved = annotation.save(console, actor_id=reviewer, **correction)
    assert saved['revision'] == 2
    resumed = restart_production(console)
    assert annotation.save(resumed, actor_id=reviewer, **correction) == saved
    assert candidate(resumed, sid) == before  # input save never edits source text
    second = execute_build(resumed, reviewer, sid)
    after = candidate(restart_production(resumed), sid)
    assert second['seal_id'] != first['seal_id']
    assert after['object_id'] == before['object_id']
    assert after['object_version'] != before['object_version']
    assert after['confirmed_object_type'] == 'explanation'
    assert after['metadata']['human_annotation']['annotation_id'] == original['annotation_id']
    assert after['metadata']['human_annotation']['revision'] == 2
    assert after['metadata']['revision_lineage']['previous_object_version'] == before['object_version']
    assert after['governance']['validation_status'] == 'needs_review'
    assert not any(b['valid'] for b in resumed.object_review_bindings(sid))


def test_postactivation_save_requires_exact_object_frontier(production_console, tmp_path):
    console, actor, sid, original = saved_source(production_console, tmp_path)
    execute_build(console, actor, sid)
    correction = {**deepcopy(original), 'command_id': str(uuid4()),
        'expected_revision': 1, 'expected_generation': 1,
        'expected_objects_revision': 'stale-frontier'}
    correction['selection']['status'] = 'draft'
    with pytest.raises(ConsoleError, match='annotation_objects_stale'):
        annotation.save(console, actor_id=actor, **correction)
    assert annotation.overview(console, actor_id=actor, snapshot_id=sid)['generation'] == 1
