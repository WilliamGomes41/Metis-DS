"""Validate matched WP5/WP8 inputs and report every engineering-budget miss."""
import argparse
import gzip
import json
from pathlib import Path
from statistics import median
import xml.etree.ElementTree as ET


def load(path, junit):
    path = Path(path)
    data = json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())
    cases = ET.parse(junit).findall('.//testcase')
    assert cases and all(not any(c.tag in {'failure', 'error', 'skipped'} for c in case) for case in cases), 'incomplete or failed native JUnit'
    assert len(cases) == len(data), 'JUnit/result inventory mismatch'
    return data


def validate(row):
    assert row['integrated_acceptance'] and not row['production_diff']
    assert row['workload']['candidates'] in {32, 128}
    assert row['workload']['history_depth'] == 2 and row['workload']['history_candidates'] == 2
    assert row['workload']['bindings'] > row['workload']['matching_bindings'] > 0
    expected = {f'{route}_{temperature}': 200
                for route in ('overview', 'individual', 'inventory', 'batch', 'passage')
                for temperature in ('first', *[f'warm_{i}' for i in range(7)])}
    expected.update(passage=200, pretransaction_refusal=400, semantic_refusal=400,
                    warm_passage_0=200, warm_semantic_refusal_0=400,
                    warm_passage_1=200, warm_semantic_refusal_1=400,
                    approve=303, redirect_after_approve=200, overview_after_approve=200,
                    old_form_retry=409, fresh_passage=200, concurrent_stale=409)
    samples = row['samples']
    assert len(samples) == len(expected), 'missing or duplicate requests'
    assert {s['action']: s['http_status'] for s in samples} == expected, 'request inventory/status changed'
    for sample in samples:
        d = sample['diagnostics']
        assert d['status'] == sample['http_status'] and d['outcome'] == 'completed'
        assert sample['wall_ms'] > 0 and sample['response_bytes'] > 0
        if sample['action'] in {'approve', 'semantic_refusal', 'warm_semantic_refusal_0', 'warm_semantic_refusal_1'}:
            for phase in ('store_lock_hold', 'store_transaction'):
                assert d['phases'][phase]['inclusive_ms'] > 0, 'missing command phase evidence'


def budgets(row):
    misses = []
    for sample in row['samples']:
        action = sample['action']
        post = sample['http_status'] in {303, 400, 409}
        limit = 3000 if post or action.startswith('overview_') else 5000
        values = [('response_ms', sample['wall_ms'], limit)]
        if post:
            for phase, bound in (('store_lock_hold', 250), ('store_transaction', 500)):
                value = sample['diagnostics'].get('phases', {}).get(phase, {}).get('inclusive_ms')
                # A pretransaction refusal has no transaction. Absence is not zero.
                if value is not None:
                    values.append((phase + '_ms', value, bound))
        misses.extend({'action': action, 'metric': metric, 'value': value, 'limit': bound}
                      for metric, value, bound in values if value > bound)
    return misses


def compare(before, after, *, cutover=False):
    key = lambda row: row['workload']['candidates']
    assert len({key(r) for r in before}) == len(before), 'duplicate before workload'
    assert len({key(r) for r in after}) == len(after), 'duplicate after workload'
    left, right = {key(r): r for r in before}, {key(r): r for r in after}
    assert left.keys() == right.keys() == {32, 128}, 'incomplete scale matrix'
    output = []
    for size, a in right.items():
        b = left[size]
        validate(b)
        validate(a)
        for field in ('workload', 'configuration', 'harness_sha256', 'integrated_driver_sha256', 'python', 'runtime'):
            assert b[field] == a[field], f'unmatched {field}'
        assert b['storage_before']['postgres_version'] == a['storage_before']['postgres_version']
        if cutover:
            assert b['commit'] == a['commit'] and b['review_card_mode'] == 'legacy' and a['review_card_mode'] == 'compact'
        else:
            assert b['commit'] != a['commit'] and b['review_card_mode'] == a['review_card_mode'] == 'legacy'
        summary = []
        for route in ('overview', 'individual', 'inventory', 'batch', 'passage'):
            old = [s['wall_ms'] for s in b['samples'] if s['action'].startswith(route + '_warm_')]
            new = [s['wall_ms'] for s in a['samples'] if s['action'].startswith(route + '_warm_')]
            assert len(old) == len(new) == 7
            summary.append({'route': route, 'before_median_ms': median(old), 'after_median_ms': median(new),
                            'after_min_ms': min(new), 'after_max_ms': max(new), 'n': 7})
        output.append({'candidates': size, 'before_commit': b['commit'], 'after_commit': a['commit'],
                       'routes': summary, 'before_budget_misses': budgets(b), 'after_budget_misses': budgets(a)})
    return {'comparison': 'reader cutover' if cutover else 'WP5 to integrated WP8', 'results': output,
            'after_budget_misses': sum(len(r['after_budget_misses']) for r in output),
            'p95': None, 'production_acceptance': False,
            'limits': ['Synthetic local native workload; no live production evidence.',
                       'Inclusive phases overlap and must not be summed.',
                       'Seven warm observations do not establish p95 or process/DB-cold latency.',
                       'Historical WP1 control-budget misses remain separate open criteria.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'before-junit', 'after-junit', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--cutover', action='store_true')
    parser.add_argument('--assert-budget', action='store_true')
    args = parser.parse_args()
    result = compare(load(args.before, args.before_junit), load(args.after, args.after_junit), cutover=args.cutover)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if args.assert_budget and result['after_budget_misses']:
        raise SystemExit('RED: integrated engineering budget missed; see retained samples')


if __name__ == '__main__':
    main()
