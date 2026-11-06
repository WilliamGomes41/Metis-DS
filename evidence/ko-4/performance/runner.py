"""Run the frozen KO4 method only with an explicit immutable head and quiet GO."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess

ROOT = Path('/tmp/ko4-perf')
PYTHON = '/workspace/.venvs/metis-ds/bin/python'
BASELINE = '837b115f213bcfd0e9f4a71a1010231d2040365e'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def order():
    return [{'sequence': (round_id-1)*2 + index + 1, 'round': round_id,
             'side': side, 'pair_order': 'AB' if round_id % 2 else 'BA'}
            for round_id in range(1, 6)
            for index, side in enumerate(('base', 'head') if round_id % 2 else ('head', 'base'))]


def main():
    assert os.environ.get('KO4_QUIET_GO') == '1', 'Explicit quiet GO is required'
    head = os.environ.get('KO4_HEAD_SHA', '')
    assert re.fullmatch('[0-9a-f]{40}', head), 'An immutable full KO4_HEAD_SHA is required'
    pins = {side: subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT/side, text=True).strip()
            for side in ['base', 'head']}
    assert pins == {'base': BASELINE, 'head': head}
    for side in pins:
        assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'],
                                           cwd=ROOT/side, text=True).strip(), side
    protocol = json.loads((ROOT/'protocol.json').read_text())
    assert protocol['baseline_sha'] == BASELINE
    for name, expected in protocol['source_hashes'].items():
        assert digest(ROOT/name) == expected, name
    out = Path('/workspace/ko4-perf-evidence') / ('v1-counterbalanced-' + head[:8])
    assert not out.exists(), 'Never overwrite previous evidence'
    out.mkdir(parents=True)
    for name in [*protocol['source_hashes'], 'protocol.json']:
        shutil.copyfile(ROOT/name, out/name)
    manifest = {'method_version': 1, 'baseline_sha': BASELINE, 'head_sha': head,
        'actual_pinned_heads': pins, 'planned_order': order(), 'rounds': 5,
        'pair_balance': {'AB': 3, 'BA': 2}, 'samples_per_operation_side': 20,
        'samples_per_execution_operation': 4,
        'sources': {name: digest(ROOT/name) for name in protocol['source_hashes']},
        'protocol_sha256': digest(ROOT/'protocol.json'),
        'budgets': {'approve_wall_p95_ratio': 1.1, 'correct_wall_p95_ratio': 1.1,
                    'maximum_individual_save_seconds': 30},
        'metric_scope': 'authenticated POST303 response, not receipt navigation; native preparatory GET outside timing',
        'attribution_only': 'server_ms,db_queries,db_json_bytes,physical_connections,response_bytes',
        'fixture': protocol['fixture'], 'expected_executions': 10,
        'expected_production_workers': 20, 'expected_measured_saves': 80,
        'runtime': {'python_executable': PYTHON, 'platform': platform.platform()},
        'gc': 'ordinary enabled GC; no forced collection or threshold changes',
        'observer': 'all business proofs and finalized log parsing after both timed paths',
        'p95': 'nearest rank ceil(.95*20)=19; retain all20 observations; maximum save budget applies to all'}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2))

    def event(kind, item, **extra):
        with (out/'execution-order.jsonl').open('a') as stream:
            stream.write(json.dumps({'event': kind, 'timestamp': datetime.now(timezone.utc).isoformat(),
                                     **item, **extra}) + '\n')

    for item in manifest['planned_order']:
        side = item['side']
        checkout = ROOT/side
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip() == pins[side]
        assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'],
                                           cwd=checkout, text=True).strip(), side
        for name, expected in manifest['sources'].items():
            assert digest(ROOT/name) == expected
        assert digest(ROOT/'protocol.json') == manifest['protocol_sha256']
        if item['sequence'] % 2:
            with (out/'load.txt').open('a') as stream:
                subprocess.run(['uptime'], stdout=stream, check=True)
        target = checkout/'tests/ko4_perf_probe_tmp.py'
        assert not target.exists(), 'Probe temp file must not replace an existing test'
        shutil.copyfile(ROOT/'probe.py', target)
        env = {**os.environ, 'PATH': '/workspace/.postgres/usr/lib/postgresql/17/bin:' + os.environ['PATH'],
            'METIS_TEST_POSTGRES_DSN': 'postgresql://postgres@127.0.0.1:55432/postgres',
            'KO4_OUT': str(out), 'KO4_SIDE': side, 'KO4_ROUND': str(item['round'])}
        event('started', item)
        print(f"Started round {item['round']} {side} ({item['pair_order']})", flush=True)
        try:
            with (out/f"{side}-{item['round']}.log").open('w') as stream:
                done = subprocess.run([PYTHON, '-m', 'pytest', '-q', 'tests/ko4_perf_probe_tmp.py'],
                    cwd=checkout, env=env, stdout=stream, stderr=subprocess.STDOUT)
        finally:
            target.unlink(missing_ok=True)
        event('completed' if done.returncode == 0 else 'failed', item, exit_code=done.returncode)
        if done.returncode:
            raise SystemExit(done.returncode)
        print(f"Completed round {item['round']} {side} ({item['pair_order']})", flush=True)


if __name__ == '__main__':
    main()
