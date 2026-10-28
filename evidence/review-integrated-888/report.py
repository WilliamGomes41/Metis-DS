"""Compare matched samples without manufacturing tail-percentile confidence."""
import argparse
import json
from pathlib import Path
from statistics import median


def load(path):
    cases = json.loads(Path(path).read_text())
    assert len({r['case'] for r in cases}) == len(cases), 'duplicate cases'
    return {row['case']: row for row in cases}


def summary(rows):
    return {'n': len(rows), 'median_ms': median(r['wall_ms'] for r in rows),
        'min_ms': min(r['wall_ms'] for r in rows), 'max_ms': max(r['wall_ms'] for r in rows),
        'html_bytes': sorted({r['html_bytes'] for r in rows}),
        'db_json_bytes': sorted({r['db']['db_json_bytes'] for r in rows}),
        'db_queries': sorted({r['db']['db_queries'] for r in rows}),
        'phase_medians_ms': {name: median(r['phases'].get(name, {}).get('inclusive_ms', 0) for r in rows)
            for name in ('source_prepare', 'source_build_blocks', 'source_reconstruction',
                         'processing_status', 'db_connect', 'db_execute', 'db_fetch')},
        'unattributed_lower_bound_ms': median(r['unattributed_lower_bound_ms'] for r in rows)
            if all('unattributed_lower_bound_ms' in r for r in rows) else None,
        'truncated_phase_trees': sum(bool(r.get('phase_tree_truncated')) for r in rows)}


def compare(before, after):
    assert before.keys() == after.keys(), 'workload cases differ'
    results = []
    for case in before:
        b, a = before[case], after[case]
        for key in ('documents', 'configuration', 'harness_sha256', 'repeats', 'python', 'runtime'):
            assert b[key] == a[key], f'{case}: unmatched {key}'
        assert not b['production_diff'] and not a['production_diff'], 'uncommitted production changes'
        assert b['commit'] != a['commit'], 'identical code references'
        assert b['repeats'] >= 5, 'at least five warm samples required'
        for incomplete in (False, True):
            for route in ('overview', 'individual', 'inventory', 'batch', 'passage'):
                select = lambda r: (r['route'] == route and r['incomplete'] == incomplete
                                    and r['temperature'] == 'warm')
                left = [r for r in b['samples'] if select(r)]
                right = [r for r in a['samples'] if select(r)]
                assert len(left) == len(right) == b['repeats'], 'missing warm samples'
                assert all(r['status'] == 200 and r['outcome'] == 'completed' and not r.get('error')
                           for r in left + right), 'request failed'
                assert {(r['formation_warning'], r['batch_members']) for r in left} == {
                    (r['formation_warning'], r['batch_members']) for r in right}, 'observable meaning differs'
                bs, ass = summary(left), summary(right)
                ratio = ass['median_ms'] / bs['median_ms']
                limit = 0.70 if case == 'continued600' else 1.15 if case in ('small', 'complex', 'multiple') else None
                results.append({'case': case, 'incomplete': incomplete, 'route': route,
                    'before': bs, 'after': ass, 'ratio': ratio, 'provisional_ratio_budget': limit,
                    'within_budget_before_noise_adjustment': ratio <= limit if limit else None})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--assert-budget', action='store_true')
    args = parser.parse_args()
    before, after = load(args.before), load(args.after)
    results = compare(before, after)
    failures = [r for r in results if r['within_budget_before_noise_adjustment'] is False]
    Path(args.output).write_text(json.dumps({'results': results,
        'budget_misses_before_noise_adjustment': len(failures),
        'p95': None, 'p95_reason': 'seven warm observations cannot establish a stable tail; no p95 claim',
        'notes': ['Phase columns are inclusive and overlap; do not add them.',
                  'Remainder is a conservative lower bound, not an exact gap.',
                  'First-for-route is reported in raw samples; it is not process/DB cold.',
                  'One two-request wave per state is a concurrency smoke test, not sustained load.',
                  'Control budget misses require matched repeat/noise investigation.',
                  'No current production deployment or production latency has been observed.']}, indent=2) + '\n')
    for r in results:
        print(f"{r['case']:15} {str(r['incomplete']):5} {r['route']:10} "
              f"{r['before']['median_ms']:9.2f} -> {r['after']['median_ms']:9.2f} ms "
              f"ratio={r['ratio']:.3f} budget={r['provisional_ratio_budget']}")
    if args.assert_budget and failures:
        raise SystemExit(f'RED: {len(failures)} provisional route budgets missed; investigate noise before conclusion')


if __name__ == '__main__':
    main()
