"""Reject misleading integrated acceptance reports using retained native inputs.

# release-control-evidence: scope/belofte metrics slop releasebewijs
"""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1] / 'evidence/review-integrated-888'
REPORT = runpy.run_path(str(ROOT / 'integrated_report.py'))


def inputs():
    return [json.loads(gzip.decompress((ROOT / name).read_bytes()))
            for name in ('wp5-matched.json.gz', 'wp8-legacy.json.gz')]


@pytest.mark.parametrize('damage', ['source', 'history', 'harness', 'driver', 'configuration',
                                   'request', 'status', 'phase', 'duplicate'])
def test_integrated_comparison_refuses_unmatched_or_incomplete_native_evidence(damage):
    before, after = inputs()
    after = deepcopy(after)
    row = after[0]
    if damage == 'source':
        row['workload']['source_sha256'] = 'different-source'
    elif damage == 'history':
        row['workload']['stored_versions'] += 1
    elif damage == 'harness':
        row['harness_sha256'] = 'different-harness'
    elif damage == 'driver':
        row['integrated_driver_sha256'] = 'different-driver'
    elif damage == 'configuration':
        row['configuration']['field_contract'] = 'different-contract'
    elif damage == 'request':
        row['samples'].pop()
    elif damage == 'status':
        row['samples'][0]['http_status'] = 500
    elif damage == 'phase':
        approve = next(s for s in row['samples'] if s['action'] == 'approve')
        del approve['diagnostics']['phases']['store_lock_hold']
    else:
        after.append(deepcopy(row))
    with pytest.raises(AssertionError):
        REPORT['compare'](before, after)


def test_single_slow_first_observation_stays_visible_beside_fast_warm_samples():
    _, after = inputs()
    row = deepcopy(after[0])
    next(s for s in row['samples'] if s['action'] == 'overview_first')['wall_ms'] = 3001
    assert any(m == {'action': 'overview_first', 'metric': 'response_ms', 'value': 3001, 'limit': 3000}
               for m in REPORT['budgets'](row))


@pytest.mark.parametrize('outcome', ['failure', 'error', 'skipped', 'missing'])
def test_native_junit_failure_skip_or_missing_case_cannot_become_acceptance(tmp_path, outcome):
    junit = tmp_path / 'native.xml'
    if outcome == 'missing':
        body = '<testcase name="one"/>'
    else:
        body = f'<testcase name="one"><{outcome}/></testcase><testcase name="two"/>'
    junit.write_text('<testsuites><testsuite>' + body + '</testsuite></testsuites>')
    with pytest.raises(AssertionError):
        REPORT['load'](ROOT / 'wp8-legacy.json.gz', junit)


def test_native_reports_preserve_scope_and_do_not_claim_production_acceptance():
    before, after = inputs()
    result = REPORT['compare'](before, after)
    compact = json.loads(gzip.decompress((ROOT / 'wp8-compact.json.gz').read_bytes()))
    cutover = REPORT['compare'](after, compact, cutover=True)
    assert result['p95'] is None and cutover['p95'] is None
    assert not result['production_acceptance'] and not cutover['production_acceptance']
    assert result['after_budget_misses'] == sum(len(r['after_budget_misses']) for r in result['results'])
