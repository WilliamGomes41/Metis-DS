"""The legacy ZIP route cannot mutate a container-hosted production app.

# release-control-evidence: scope/belofte slop releasebewijs
"""
from pathlib import Path
import os
import re
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GUARD = 'Verify legacy ZIP runtime before Azure mutations'


def production_steps():
    workflow = yaml.safe_load((ROOT / '.github/workflows/deploy-production.yml').read_text())
    trigger = workflow.get('on', workflow.get(True))
    assert set(trigger) == {'workflow_dispatch'}
    assert {'commit_sha', 'ci_run_id'} <= set(trigger['workflow_dispatch']['inputs'])
    assert workflow['jobs']['deploy']['environment'] == 'production'
    steps = workflow['jobs']['deploy']['steps']
    guards = [step for step in steps if step.get('name') == GUARD]
    assert len(guards) == 1, 'The legacy ZIP route requires a live runtime guard'
    return steps, guards[0]


@pytest.mark.parametrize('runtime,read_exit,allowed', [
    ('PYTHON|3.13', 0, True),
    ('DOCKER|registry.example/metis@sha256:abc', 0, False),
    ('sitecontainers', 0, False),
    ('PYTHON|3.12', 0, False),
    ('', 0, False),
    ('null', 0, False),
    ('PYTHON|3.13', 9, False),
])
def test_live_runtime_guard_controls_both_azure_mutations(tmp_path, runtime, read_exit, allowed):
    steps, guard = production_steps()
    login = next(i for i,s in enumerate(steps) if s.get('uses') == 'azure/login@v2')
    guard_index = steps.index(guard)
    mutations = [s for s in steps if re.search(r'az\s+webapp\s+(?:deploy|config\s+appsettings\s+set)', s.get('run', ''))]
    assert len(mutations) == 2
    assert login < guard_index < min(steps.index(s) for s in mutations)
    assert '--query linuxFxVersion' in guard['run']
    assert '${{' not in guard['run'], 'Read coordinates through quoted environment variables'

    calls = tmp_path / 'azure-calls'
    az = tmp_path / 'az'
    az.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$FIXTURE_CALLS"
if [ "$1 $2 $3" = "webapp config show" ]; then
  printf '%s\\n' "$FIXTURE_RUNTIME"
  exit "$FIXTURE_READ_EXIT"
fi
exit 0
''')
    az.chmod(0o755)
    # Execute the actual guard and both actual mutation commands with a fake az.
    script = '\n'.join([guard['run'], *[s['run'] for s in mutations]])
    script = re.sub(r'\$\{\{.*?\}\}', 'fixture', script)
    result = subprocess.run(
        ['bash', '--noprofile', '--norc', '-e', '-o', 'pipefail', '-c', script],
        cwd=tmp_path, capture_output=True, text=True, timeout=5,
        env={**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
             'FIXTURE_CALLS': str(calls), 'FIXTURE_RUNTIME': runtime,
             'FIXTURE_READ_EXIT': str(read_exit), 'RUNNER_TEMP': str(tmp_path),
             'AZURE_RESOURCE_GROUP': 'fixture', 'AZURE_PRODUCTION_WEBAPP_NAME': 'vvn-metis-console'},
    )
    commands = calls.read_text().splitlines()
    assert commands[0].startswith('webapp config show ')
    if allowed:
        assert result.returncode == 0, result.stderr
        assert 'production_zip_runtime_verified' in result.stdout
        assert commands[1].startswith('webapp config appsettings set ')
        assert commands[2].startswith('webapp deploy ')
    else:
        assert result.returncode != 0
        assert len(commands) == 1, 'Denied runtime must never reach settings or ZIP deployment'
        if read_exit == 0:
            assert 'production_zip_runtime_blocked' in result.stdout + result.stderr


def test_active_runbooks_do_not_offer_an_unguarded_manual_zip_deployment():
    for name in ('AZURE_STEP9_CUTOVER_RUNBOOK.md', 'AZURE_RELEASE_RUNBOOK.md',
                 'TEST_AND_RELEASE_RUNBOOK.md', 'agents/deployment-protocol.md'):
        text = (ROOT / 'docs' / name).read_text()
        for block in re.findall(r'```[^\n]*\n(.*?)```', text, re.S):
            assert not (re.search(r'az\s+webapp\s+deploy\b', block) and
                        re.search(r'--type(?:\s+|=)[\"\']?zip\b', block)), name
        assert 'AZURE_RELEASE_RUNBOOK.md' in text or name == 'AZURE_RELEASE_RUNBOOK.md'
