"""W1 local comparison: frozen KO4 fixture, plus real correction navigation.

Run only after other tests stop. DSN is supplied through the environment and
never included in the public manifest. Raw worker configs remain private.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys


def git(checkout, *args):
    return subprocess.check_output(['git', *args], cwd=checkout, text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    for arg in ('base', 'head', 'out', 'tools'):
        parser.add_argument('--' + arg, type=Path, required=True)
    args = parser.parse_args()
    assert os.environ.get('METIS_TEST_POSTGRES_DSN')
    assert not os.environ.get('GUNICORN_CMD_ARGS')
    pins = {side: git(getattr(args, side), 'rev-parse', 'HEAD') for side in ('base', 'head')}
    source = (args.base / 'evidence/ko-4/performance/probe.py').read_text()
    original_hash = hashlib.sha256(source.encode()).hexdigest()

    def replace(old, new):
        nonlocal source
        assert source.count(old) == 1, old
        source = source.replace(old, new)

    replace("TOOLS = Path('/tmp/ko4-perf')", "TOOLS = Path(os.environ['W1_TOOLS'])")
    replace("    for sample, task in enumerate(tasks, 1):\n", "    for sample, task in enumerate(tasks, 1):\n        action_started = time.perf_counter()\n")
    replace("        started = time.perf_counter()\n", "        form_get_ms = (time.perf_counter() - action_started) * 1000\n        started = time.perf_counter()\n")
    replace("    client.close()\n    forced = stop_child(child, log)", """        if operation == 'correct':
            next_started = time.perf_counter()
            next_page = client.get(response.headers['location'])
            assert next_page.status_code == 200
            next_ms = (time.perf_counter() - next_started) * 1000
            reopen_started = time.perf_counter()
            reopened_page = client.get('/source-selection', params={'document': config['snapshot'],
                'object': task['object_id'], 'task': 'repair', 'repair_kind': 'source_units'})
            assert reopened_page.status_code == 200
            observations[-1].update(form_get_ms=form_get_ms, redirect_get_ms=next_ms,
                reopen_get_ms=(time.perf_counter() - reopen_started) * 1000,
                complete_action_ms=(time.perf_counter() - action_started) * 1000)
    client.close()
    forced = stop_child(child, log)""")
    replace("            query = parse_qs(urlparse(metric['location']).query)", """            metric.update(outer_lock_ms=row.get('phases', {}).get('store_lock_hold', {}).get('inclusive_ms', 0),
                transaction_ms=row.get('phases', {}).get('store_transaction', {}).get('inclusive_ms', 0))
            query = parse_qs(urlparse(metric['location']).query)""")
    replace("'POST response only; real preparatory form GET outside timing; no receipt navigation timing'",
            "'POST response separately; correction also measures form GET, redirect GET and reopen GET without user think time'")
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'probe.py').write_text(source)
    order = [(round_id, side) for round_id in range(1, 6)
             for side in (('base', 'head') if round_id % 2 else ('head', 'base'))]
    manifest = dict(base=pins['base'], head=pins['head'], rounds=5,
        order=order, original_probe_sha256=original_hash,
        probe_sha256=hashlib.sha256(source.encode()).hexdigest(),
        python=sys.version, local_only=True, scope='full source-units resolution',
        budgets_ms=dict(post=3000, outer_lock=250, transaction=500, complete_action=5000))
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    shutil.copyfile(args.base / 'evidence/ko-4/performance/server.py', args.tools / 'server.py')
    for round_id, side in order:
        checkout = getattr(args, side)
        assert git(checkout, 'rev-parse', 'HEAD') == pins[side]
        assert not git(checkout, 'status', '--porcelain')
        target = checkout / 'tests/w1_perf_probe_tmp.py'
        assert not target.exists()
        target.write_text(source)
        env = {**os.environ, 'KO4_OUT': str(args.out), 'KO4_SIDE': side,
               'KO4_ROUND': str(round_id), 'W1_TOOLS': str(args.tools)}
        print(f'Start {round_id} {side}', flush=True)
        started = datetime.now(timezone.utc).isoformat()
        try:
            with (args.out / f'{side}-{round_id}.log').open('w') as output:
                result = subprocess.run([sys.executable, '-m', 'pytest', '-q',
                    str(target), '--tb=short'], cwd=checkout, env=env,
                    stdout=output, stderr=subprocess.STDOUT)
        finally:
            target.unlink()
        with (args.out / 'execution-order.jsonl').open('a') as output:
            output.write(json.dumps(dict(round=round_id, side=side, started=started,
                finished=datetime.now(timezone.utc).isoformat(), returncode=result.returncode)) + '\n')
        if result.returncode:
            raise SystemExit(result.returncode)
        print(f'Completed {round_id} {side}', flush=True)


if __name__ == '__main__':
    main()
