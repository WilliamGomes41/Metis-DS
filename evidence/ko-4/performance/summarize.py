"""Validate every frozen observation before reporting the two KO4 save gates."""
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics
import sys

root = Path(sys.argv[1])
manifest = json.loads((root/'manifest.json').read_text())
assert manifest['method_version'] == 1 and manifest['rounds'] == 5
assert manifest['baseline_sha'] == '837b115f213bcfd0e9f4a71a1010231d2040365e'
assert manifest['budgets'] == {'approve_wall_p95_ratio': 1.1, 'correct_wall_p95_ratio': 1.1,
                               'maximum_individual_save_seconds': 30}
assert manifest['samples_per_operation_side'] == 20
for name, expected in manifest['sources'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == expected
assert hashlib.sha256((root/'protocol.json').read_bytes()).hexdigest() == manifest['protocol_sha256']
protocol = json.loads((root/'protocol.json').read_text())
assert manifest['planned_order'] == protocol['planned_order']
order = [json.loads(line) for line in (root/'execution-order.jsonl').read_text().splitlines()]
assert len(order) == 20 and len(manifest['planned_order']) == 10
for expected, start, finish in zip(manifest['planned_order'], order[::2], order[1::2]):
    assert start['event'] == 'started' and finish['event'] == 'completed' and finish['exit_code'] == 0
    assert all(start[k] == value and finish[k] == value for k, value in expected.items())
assert manifest['pair_balance'] == {'AB': 3, 'BA': 2}
runs = {side: [json.loads((root/f'{side}-{n}.json').read_text()) for n in range(1, 6)]
        for side in ['base', 'head']}
for side, rows in runs.items():
    for row in rows:
        assert row['version'] == 1 and row['sha'] == manifest['actual_pinned_heads'][side]
        assert row['fixture'] == {'paragraphs': 923, 'raw_source_fragments': 924, 'candidates': 92,
            'approval_tasks_with_real_support': 4, 'correction_tasks': 4}
        assert row['proofs'] == {'approved_exact_bindings': 4, 'new_open_corrections': 4,
            'three_yes_recorded': True, 'untargeted_objects_unchanged': True,
            'source_files_unchanged': True, 'canonical_store_unchanged': True,
            'persisted_after_restart': True, 'no_persisted_revise': True}
        assert len(row['workers']) == 2
        assert len({w['pid'] for w in row['workers']}) == 2
        assert all(w['sha'] == row['sha'] and w['gc_enabled'] and w['gunicorn_default_timeout_seconds'] == 30
                   for w in row['workers'])
        for operation in ['approve', 'correct']:
            assert len(row['metrics'][operation]) == 4
            assert all(m['status'] == 303 and m['request_id'] and m['server_ms'] >= 0
                       for m in row['metrics'][operation])


def stats(values):
    assert len(values) == 20
    return {'median': statistics.median(values), 'min': min(values), 'max': max(values),
            'p95': sorted(values)[math.ceil(.95*len(values))-1], 'values': values}


summary = {'method_version': 1, 'baseline_sha': manifest['baseline_sha'], 'head_sha': manifest['head_sha'],
    'method': '5counterbalancedpairs3AB/2BA;20samples/operation/side;actualPOSTsave;startup/auth/formGEToutside;defaultGC/Gunicorn30s',
    'verdict': 'PASS', 'metrics': {}, 'attribution_only': {}, 'sources': manifest['sources'],
    'proofs': {'executions': 10, 'production_workers': 20, 'measured_saves': 80,
        'approved_exact_bindings': 40, 'new_open_corrections': 40, 'source_and_canonical_unchanged': 10,
        'untargeted_objects_unchanged': 10, 'durability_restart_verified': 10},
    'scope_limit': 'POST response only; excludes receipt navigation. Server and SQL/byte counters are attribution, not additional gates.'}
csv_rows = []
for operation in ['approve', 'correct']:
    primary = {side: stats([m['wall_ms'] for row in rows for m in row['metrics'][operation]])
               for side, rows in runs.items()}
    ratio = primary['head']['p95'] / primary['base']['p95']
    primary.update(ratio=ratio, percent_change=(ratio-1)*100, pass_budget=ratio <= 1.1,
                   individual_save_budget_seconds=30,
                   all_individual_saves_within_timeout=max(primary['base']['max'], primary['head']['max']) <= 30000)
    if not primary['pass_budget'] or not primary['all_individual_saves_within_timeout']:
        summary['verdict'] = 'FAIL'
    summary['metrics'][operation+'_wall_ms'] = primary
    summary['attribution_only'][operation] = {
        side: {key: stats([m[key] for row in rows for m in row['metrics'][operation]])
               for key in ['server_ms', 'db_queries', 'db_json_bytes', 'physical_connections', 'response_bytes']}
        for side, rows in runs.items()}
    for event in manifest['planned_order']:
        row = runs[event['side']][event['round']-1]
        for metric in row['metrics'][operation]:
            csv_rows.append({**event, 'operation': operation, 'sha': row['sha'], **metric})
assert len(csv_rows) == 80
csv_rows.sort(key=lambda r: (r['sequence'], 0 if r['operation'] == 'approve' else 1, r['sample']))
with (root/'saves.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(csv_rows)
(root/'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
