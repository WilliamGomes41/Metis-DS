"""#974: execute the collector with a fake read-only Azure boundary.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import os
from pathlib import Path
import stat
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/collect_worker_abort_evidence.sh'


def environment(tmp_path):
    binary = tmp_path / 'bin'
    binary.mkdir()
    azure = binary / 'az'
    azure.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['FAKE_AZ_CALLS'], 'a') as stream:
    stream.write(json.dumps(args) + '\\n')
if args[:2] == ['account', 'show']:
    print(os.environ.get('FAKE_SUBSCRIPTION', 'approved'))
elif args[:4] == ['monitor', 'log-analytics', 'workspace', 'show']:
    print('workspace-id')
elif args[:3] == ['monitor', 'log-analytics', 'query']:
    query = args[args.index('--analytics-query') + 1]
    assert all(token not in query for token in ('{START}', '{END}', '{SITE}'))
    if os.environ.get('FAIL_ONE_QUERY') and 'LastElapsedMs' in query:
        print('table unavailable', file=sys.stderr)
        sys.exit(1)
    print('[{"row": 1}]')
else:
    raise AssertionError('Unexpected Azure operation')
''')
    azure.chmod(0o700)
    return {**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH'],
            'METIS_SUBSCRIPTION_ID': 'approved', 'METIS_RESOURCE_GROUP': 'fixture-group',
            'METIS_WEBAPP': 'fixture-site', 'METIS_LOG_WORKSPACE': 'fixture-workspace',
            'FAKE_AZ_CALLS': str(tmp_path / 'calls.jsonl')}


def collect(tmp_path, env, start='2026-11-04T13:28:00Z', end='2026-11-04T14:05:00Z', out=None):
    return subprocess.run(['bash', str(SCRIPT), start, end, str(out or tmp_path / 'evidence')],
                          env=env, capture_output=True, text=True, timeout=30)


def test_all_sections_are_collected_privately(tmp_path):
    env = environment(tmp_path)
    result = collect(tmp_path, env)
    assert result.returncode == 0, result.stderr
    out = tmp_path / 'evidence'
    assert len(list(out.glob('*.json'))) == 6
    assert all(json.loads(path.read_text()) == [{'row': 1}] for path in out.glob('*.json'))
    assert stat.S_IMODE(out.stat().st_mode) == 0o700
    assert stat.S_IMODE((out / 'manifest.txt').stat().st_mode) == 0o600
    assert len(Path(env['FAKE_AZ_CALLS']).read_text().splitlines()) == 8


@pytest.mark.parametrize('start,end', [
    ('2026-02-30T13:28:00Z', '2026-11-04T14:05:00Z'),
    ('2026-11-04T14:05:00Z', '2026-11-04T13:28:00Z'),
    ('2026-11-04T13:28:00Z', '2026-11-04T13:28:00Z'),
])
def test_invalid_calendar_or_order_is_rejected_before_azure(tmp_path, start, end):
    env = environment(tmp_path)
    result = collect(tmp_path, env, start, end)
    assert result.returncode == 2
    assert not Path(env['FAKE_AZ_CALLS']).exists()
    assert not (tmp_path / 'evidence').exists()


def test_repository_symlink_is_rejected_before_azure(tmp_path):
    env = environment(tmp_path)
    alias = tmp_path / 'repo-alias'
    alias.symlink_to(ROOT, target_is_directory=True)
    result = collect(tmp_path, env, out=alias / 'must-not-create-974')
    assert result.returncode == 2
    assert not Path(env['FAKE_AZ_CALLS']).exists()
    assert not (ROOT / 'must-not-create-974').exists()


def test_wrong_subscription_stops_before_workspace_read(tmp_path):
    env = {**environment(tmp_path), 'FAKE_SUBSCRIPTION': 'wrong'}
    result = collect(tmp_path, env)
    assert result.returncode == 1
    assert len(Path(env['FAKE_AZ_CALLS']).read_text().splitlines()) == 1
    assert not (tmp_path / 'evidence').exists()


def test_missing_table_does_not_skip_other_queries(tmp_path):
    env = {**environment(tmp_path), 'FAIL_ONE_QUERY': 'yes'}
    result = collect(tmp_path, env)
    assert result.returncode == 1
    assert len(Path(env['FAKE_AZ_CALLS']).read_text().splitlines()) == 8
    assert (tmp_path / 'evidence/aborted_review_saves.err').exists()
    assert json.loads((tmp_path / 'evidence/review_save_finished.json').read_text()) == [{'row': 1}]
