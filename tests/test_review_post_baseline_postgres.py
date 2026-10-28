"""Execute the retained #888 evidence harness in the normal native test suite.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import os
import runpy


def test_native_post_baseline(tmp_path, production_console, production_app, monkeypatch):
    # Keep one scenario owner: the opt-in multi-size harness also serves CI.
    harness = Path(__file__).resolve().parents[1] / 'evidence/review-integrated-888/benchmark.py'
    namespace = runpy.run_path(str(harness))
    if not os.environ.get('REVIEW_PROOF_OUTPUT'):
        monkeypatch.setenv('REVIEW_PROOF_OUTPUT', str(tmp_path / 'post-baseline.json'))
    namespace['test_native_review_post_baseline'](
        20, tmp_path, production_console, production_app, monkeypatch)
