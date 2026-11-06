"""V5 runner: six counterbalanced pairs; frozen V4.1 HTTP probe/server unchanged."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path('/tmp/ko2-perf')
BASE = '595fe8f233fdee98dfb67609bd5c7206136ee956'
PROBE_SHA = 'fb391e729d961d9bdf54c09627f6a5b9deb346ed918c609f4421d0464f238722'
SERVER_SHA = 'c35ff047ca57ca548f20dcf0db9968e5ea0e42db0dd9061f94de8b2d4851b749'
PYTHON = '/workspace/.venvs/metis-ds/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execution_plan():
    return [dict(sequence=len_prefix + index + 1, round=round_id, fixture=fixture, side=side,
                 pair_order='AB' if round_id % 2 else 'BA')
            for round_id in range(1, 7)
            for fi, fixture in enumerate(('legacy', 'native'))
            for len_prefix in [(round_id-1)*4 + fi*2]
            for index, side in enumerate(('base', 'head') if round_id % 2 else ('head', 'base'))]


def main():
    assert len(sys.argv) == 1, 'Set explicit KO2_HEAD_SHA environment variable'
    head = os.environ.get('KO2_HEAD_SHA', '')
    assert re.fullmatch('[0-9a-f]{40}', head), 'Exact immutable KO2_HEAD_SHA required'
    out = Path('/workspace/ko2-perf-evidence') / ('v5-counterbalanced-' + head[:8])
    assert not out.exists(), 'Never overwrite an earlier run'
    assert sha(ROOT/'probe_v4_finalized.py') == PROBE_SHA
    assert sha(ROOT/'server_v4.py') == SERVER_SHA
    pinned = {side: subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT/side, text=True).strip()
              for side in ['base', 'head']}
    assert pinned == {'base': BASE, 'head': head}
    out.mkdir(parents=True)
    plan = execution_plan()
    manifest = {'method_version':5,'baseline_sha':BASE,'head_sha':head,'actual_pinned_heads':pinned,
        'probe_sha256':PROBE_SHA,'server_sha256':SERVER_SHA,'runner_sha256':sha(Path(__file__)),
        'rounds':6,'samples_per_execution':3,'samples_per_path_side_fixture':18,
        'expected_approvals':72,'expected_head_assessments':36,
        'pair_orders':{'odd':'AB','even':'BA'},'planned_execution_order':plan,
        'budget':{'server_p95_max_ratio':1.1,'postgres_json_p95_max_ratio':1.1},
        'p95':'nearest rank ceil(.95*18)=18, therefore maximum; no samples dropped',
        'change':'Counterbalanced runner order and sample count only; frozen V4.1 probe/server unchanged.'}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
    for source, target in [('probe_v4_finalized.py','probe.py'),('server_v4.py','server.py')]:
        shutil.copyfile(ROOT/source, out/target)
    shutil.copyfile(Path(__file__), out/'run.py')
    def record(event, item, **extra):
        with (out/'execution-order.jsonl').open('a') as log:
            log.write(json.dumps({'event':event,'timestamp':datetime.now(timezone.utc).isoformat(),**item,**extra})+'\n')
    for item in plan:
        if item['sequence'] % 4 == 1:
            with (out/'load.txt').open('a') as log:
                subprocess.run(['uptime'], stdout=log, check=True)
        side, fixture, round_id = item['side'], item['fixture'], item['round']
        checkout = ROOT/side
        assert subprocess.check_output(['git','rev-parse','HEAD'], cwd=checkout, text=True).strip() == (BASE if side=='base' else head)
        assert sha(ROOT/'probe_v4_finalized.py') == PROBE_SHA and sha(ROOT/'server_v4.py') == SERVER_SHA
        target = checkout/'tests/ko2_perf_probe_tmp.py'
        assert not target.exists(), 'Refuse to replace an existing temporary probe'
        record('started', item)
        shutil.copyfile(ROOT/'probe_v4_finalized.py', target)
        env = {**os.environ,'PATH':'/workspace/.postgres/usr/lib/postgresql/17/bin:'+os.environ['PATH'],
            'METIS_TEST_POSTGRES_DSN':'postgresql://postgres@127.0.0.1:55432/postgres',
            'KO2_OUT':str(out),'KO2_FIXTURE':fixture,'KO2_LABEL':side,'KO2_ROUND':str(round_id),
            'KO2_EXPECT_RECEIPT':'1' if side=='head' else '0'}
        try:
            with (out/f'{fixture}-{side}-{round_id}.log').open('w') as log:
                result = subprocess.run([PYTHON,'-m','pytest','-q','tests/ko2_perf_probe_tmp.py'],
                    cwd=checkout, env=env, stdout=log, stderr=subprocess.STDOUT)
        finally:
            target.unlink(missing_ok=True)
        record('completed' if result.returncode==0 else 'failed', item, exit_code=result.returncode)
        if result.returncode:
            raise SystemExit(result.returncode)
        print(f"{round_id} {fixture} {side} completed ({item['pair_order']})", flush=True)
        if item['sequence'] % 4 == 0:
            print(f"{round_id}/6 paired rounds across both fixtures complete", flush=True)


if __name__ == '__main__':
    main()
