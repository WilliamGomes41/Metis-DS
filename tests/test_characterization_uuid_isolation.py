"""A golden fixture must not leave frozen command IDs in later HTTP tests.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.pure_function
ROOT = Path(__file__).resolve().parents[1]


def test_first_annotation_route_import_during_characterization_does_not_freeze_later_commands():
    # A fresh interpreter is essential: the original leak only happens when
    # build_app imports the route for the first time under the UUID freeze.
    script = """
import pytest
from tests.characterization.conftest import offline_clock

with pytest.MonkeyPatch.context() as patch:
    offline_clock.__wrapped__(patch)
    from src.vorming import human_annotation_ui_v1 as annotations

assert annotations.uuid4() != annotations.uuid4(), 'characterization UUID escaped its fixture'
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
