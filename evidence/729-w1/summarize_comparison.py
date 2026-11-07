"""Validate complete W1 runs and emit public counters (never worker configs)."""
from pathlib import Path
import json
import math
import statistics
import sys


def stats(values):
    values = sorted(values)
    return dict(n=len(values), min=min(values), median=statistics.median(values),
                p95=values[math.ceil(.95 * len(values)) - 1], max=max(values))


def main():
    out = Path(sys.argv[1])
    manifest = json.loads((out / 'manifest.json').read_text())
    order = [json.loads(line) for line in (out / 'execution-order.jsonl').read_text().splitlines()]
    assert [(row['round'], row['side']) for row in order] == [tuple(pair) for pair in manifest['order']]
    assert all(row['returncode'] == 0 for row in order)
    results = {}
    for side in ('base', 'head'):
        samples = {'approve': [], 'correct': []}
        for round_id in range(1, 6):
            run = json.loads((out / f'{side}-{round_id}.json').read_text())
            assert run['sha'] == manifest[side]
            assert run['fixture']['candidates'] == 92
            assert all(run['proofs'].values())
            assert all(worker['sha'] == manifest[side] and worker['gc_enabled']
                       and worker['gunicorn_default_timeout_seconds'] == 30 for worker in run['workers'])
            for operation, rows in run['metrics'].items():
                assert len(rows) == 4 and all(row['status'] == 303 for row in rows)
                assert all(row['wall_ms'] > 0 and row['outer_lock_ms'] > 0
                           and row['transaction_ms'] > 0 and row['db_queries'] > 0
                           for row in rows)
                if operation == 'correct':
                    assert all(row['complete_action_ms'] > row['wall_ms']
                               and row['form_get_ms'] > 0 and row['redirect_get_ms'] > 0
                               and row['reopen_get_ms'] > 0 for row in rows)
                samples[operation].extend(rows)
        results[side] = {}
        for operation, rows in samples.items():
            keys = ['wall_ms', 'db_queries', 'db_json_bytes', 'physical_connections',
                    'outer_lock_ms', 'transaction_ms']
            if operation == 'correct':
                keys += ['form_get_ms', 'redirect_get_ms', 'reopen_get_ms', 'complete_action_ms']
            results[side][operation] = {key: stats([row[key] for row in rows]) for key in keys}
            results[side][operation]['post_over_5s'] = sum(row['wall_ms'] > 5000 for row in rows)
            if operation == 'correct':
                results[side][operation]['complete_action_over_5s'] = sum(row['complete_action_ms'] > 5000 for row in rows)
    budget_keys = {'post': 'wall_ms', 'outer_lock': 'outer_lock_ms',
                   'transaction': 'transaction_ms', 'complete_action': 'complete_action_ms'}
    budgets = {name: dict(limit_ms=limit,
        p95_within=results['head']['correct'][budget_keys[name]]['p95'] <= limit,
        all_samples_within=results['head']['correct'][budget_keys[name]]['max'] <= limit)
        for name, limit in manifest['budgets_ms'].items()}
    report = dict(manifest=manifest, results=results, budgets=budgets, local_only=True,
                  p95_method='nearest rank observation 19/20; all observations retained',
                  scope='form GET + POST303 + redirect GET + reopen GET, excluding login and user think time')
    (out / 'summary.json').write_text(json.dumps(report, indent=2))
    for side in results:
        print(side, {key: round(results[side]['correct'][key]['p95'], 2)
                     for key in ('wall_ms', 'outer_lock_ms', 'transaction_ms', 'complete_action_ms')})


if __name__ == '__main__':
    main()
