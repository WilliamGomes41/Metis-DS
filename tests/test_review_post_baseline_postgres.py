"""Execute the retained #888 evidence harness in the normal native test suite.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import os
import runpy
import pytest


def completion_probe(tmp_path, monkeypatch, name, *args):
    harness = Path(__file__).resolve().parents[1] / 'evidence/review-integrated-888/completion_902.py'
    namespace = runpy.run_path(str(harness))
    if not os.environ.get('REVIEW_PROOF_OUTPUT'):
        monkeypatch.setenv('REVIEW_PROOF_OUTPUT', str(tmp_path / 'completion.json'))
    namespace[name](*args)


@pytest.mark.parametrize('profile', ['initial', 'history', 'history_incomplete'])
def test_native_post_baseline(tmp_path, production_console, production_app, monkeypatch, profile):
    # Keep one scenario owner: the opt-in multi-size harness also serves CI.
    harness = Path(__file__).resolve().parents[1] / 'evidence/review-integrated-888/benchmark.py'
    namespace = runpy.run_path(str(harness))
    monkeypatch.setenv('REVIEW_POST_PROFILE', profile)
    if not os.environ.get('REVIEW_PROOF_OUTPUT'):
        monkeypatch.setenv('REVIEW_PROOF_OUTPUT', str(tmp_path / 'post-baseline.json'))
    namespace['test_native_review_post_baseline'](
        20, tmp_path, production_console, production_app, monkeypatch)


@pytest.mark.parametrize('incomplete', [False, True])
def test_native_task_v1_post(tmp_path, production_console, production_app, monkeypatch, incomplete):
    harness = Path(__file__).resolve().parents[1] / 'evidence/review-integrated-888/benchmark.py'
    namespace = runpy.run_path(str(harness))
    if not os.environ.get('REVIEW_PROOF_OUTPUT'):
        monkeypatch.setenv('REVIEW_PROOF_OUTPUT', str(tmp_path / 'task-v1-post.json'))
    namespace['test_native_task_v1_review'](
        tmp_path, production_console, production_app, monkeypatch, incomplete)


@pytest.mark.parametrize('fault', ['binding', 'commit'])
def test_native_task_v1_rollback(tmp_path, production_console, production_app, monkeypatch, fault):
    harness = Path(__file__).resolve().parents[1] / 'evidence/review-integrated-888/benchmark.py'
    namespace = runpy.run_path(str(harness))
    if not os.environ.get('REVIEW_PROOF_OUTPUT'):
        monkeypatch.setenv('REVIEW_PROOF_OUTPUT', str(tmp_path / 'task-v1-rollback.json'))
    namespace['test_native_task_v1_review'](
        tmp_path, production_console, production_app, monkeypatch, False, fault=fault)


@pytest.mark.parametrize('dependency', ['role', 'context'])
def test_native_task_v1_dependencies(tmp_path, production_console, production_app, monkeypatch, dependency):
    harness = Path(__file__).resolve().parents[1] / 'evidence/review-integrated-888/benchmark.py'
    namespace = runpy.run_path(str(harness))
    if not os.environ.get('REVIEW_PROOF_OUTPUT'):
        monkeypatch.setenv('REVIEW_PROOF_OUTPUT', str(tmp_path / 'task-v1-dependencies.json'))
    namespace['test_native_task_v1_review'](
        tmp_path, production_console, production_app, monkeypatch, False, dependency=dependency)


@pytest.mark.parametrize('storage', ['legacy', 'task-v1'])
def test_native_binding_only(tmp_path, production_console, production_app, monkeypatch, storage):
    completion_probe(tmp_path, monkeypatch, 'binding_only',
        tmp_path, production_console, production_app, monkeypatch, storage)


@pytest.mark.parametrize('decision', ['reject', 'revise', 'later'])
def test_native_decision_retry(tmp_path, production_console, production_app, monkeypatch, decision):
    completion_probe(tmp_path, monkeypatch, 'decision_retry',
        tmp_path, production_console, production_app, monkeypatch, decision)


def test_native_context_retarget(tmp_path, production_console, monkeypatch):
    completion_probe(tmp_path, monkeypatch, 'context_retarget', tmp_path, production_console, monkeypatch)


def test_native_context_single_lock_cycle(tmp_path, production_console, monkeypatch):
    completion_probe(tmp_path, monkeypatch, 'context_lock_cycle', tmp_path, production_console, monkeypatch)


@pytest.mark.parametrize('size', [32, 128])
def test_native_task_v1_scale(tmp_path, production_console, production_app, monkeypatch, size):
    harness = Path(__file__).resolve().parents[1] / 'evidence/review-integrated-888/benchmark.py'
    namespace = runpy.run_path(str(harness))
    if not os.environ.get('REVIEW_PROOF_OUTPUT'):
        monkeypatch.setenv('REVIEW_PROOF_OUTPUT', str(tmp_path / 'task-v1-scale.json'))
    namespace['test_native_task_v1_review'](tmp_path, production_console, production_app,
        monkeypatch, False, size=size, history_depth=2)
