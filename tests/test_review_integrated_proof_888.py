"""Report integrity, not a replacement for the opt-in native performance run.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence' / 'review-integrated-888'
spec = importlib.util.spec_from_file_location('review_integrated_report_888', EVIDENCE / 'report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


@pytest.mark.parametrize('tamper', ['source', 'runtime', 'harness', 'meaning'])
def test_report_rejects_an_unmatched_or_changed_workload(tamper):
    before = report.load(EVIDENCE / 'before.json.gz')
    after = deepcopy(report.load(EVIDENCE / 'after.json.gz'))
    row = after['continued600']
    if tamper == 'source':
        row['documents'][0]['fragments'] = 21
    elif tamper == 'runtime':
        row['configuration']['stores'] = 'in-memory replacement'
    elif tamper == 'harness':
        row['harness_sha256'] = 'different measurement program'
    else:
        for sample in row['samples']:
            if sample['route'] == 'passage' and sample['incomplete']:
                sample['formation_warning'] = False
    with pytest.raises(AssertionError):
        report.compare(before, after)


def test_initial_budget_misses_remain_red_after_control_aggregation(tmp_path):
    output = tmp_path / 'comparison.json'
    completed = subprocess.run([sys.executable, str(EVIDENCE / 'report.py'),
        '--before', str(EVIDENCE / 'before.json.gz'), '--after', str(EVIDENCE / 'after.json.gz'),
        '--before-repeat', str(EVIDENCE / 'before-controls.json.gz'),
        '--after-repeat', str(EVIDENCE / 'after-controls.json.gz'),
        '--output', str(output), '--assert-budget'], capture_output=True, text=True)
    assert completed.returncode == 1 and 'RED: 2 provisional route budgets missed' in completed.stderr
    result = json.loads(output.read_text())
    assert result['budget_misses_before_noise_adjustment'] == 2
    assert result['controls_two_rounds_budget_misses'] == 0
    assert result['p95'] is None
