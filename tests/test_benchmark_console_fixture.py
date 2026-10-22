"""#803 P2: the fixture benchmark accepts only a clean, non-empty pytest run.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from scripts.benchmark_console_fixture import template_accepted


def _result(**overrides):
    return {'exit_code': 0, 'tests': 3, 'failures': [], 'skipped': 0, **overrides}


def test_clean_run_is_accepted():
    assert template_accepted(_result())


@pytest.mark.parametrize('overrides', [
    {'exit_code': 5, 'tests': 0},
    {'exit_code': 1},
    {'tests': 0},
    {'failures': ['tests.test_x::test_y'], 'exit_code': 1},
    {'skipped': 1},
])
def test_incomplete_or_failed_run_is_rejected(overrides):
    assert not template_accepted(_result(**overrides))
