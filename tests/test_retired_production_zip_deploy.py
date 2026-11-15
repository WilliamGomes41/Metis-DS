"""Production ZIP dispatch is inert; the existing container route remains usable.

# release-control-evidence: scope/belofte slop releasebewijs
"""
from pathlib import Path
import os
import re
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_production_zip_dispatch_rejects_without_credentials_or_azure_calls(tmp_path):
    workflow = yaml.safe_load((ROOT / '.github/workflows/deploy-production.yml').read_text())
    trigger = workflow.get('on', workflow.get(True))
    assert set(trigger) == {'workflow_dispatch'}
    assert workflow['permissions'] == {}, 'Retired route must not request an OIDC or repository token'
    assert set(workflow['jobs']) == {'retired'}, 'No executable deployment job may remain'
    job = workflow['jobs']['retired']
    assert set(job) <= {'name', 'runs-on', 'timeout-minutes', 'steps'}
    assert len(job['steps']) == 1
    step = job['steps'][0]
    assert set(step) <= {'name', 'shell', 'run'}, 'No checkout, actions, credentials or environment'
    assert '${{' not in step['run'], 'Dispatch inputs and settings cannot change the rejection'

    # A valid legacy activation/target cannot reach Azure, even with az available.
    called = tmp_path / 'azure-called'
    binary = tmp_path / 'az'
    binary.write_text('#!/bin/sh\ntouch "$AZURE_CALL_MARKER"\nexit 99\n')
    binary.chmod(0o755)
    result = subprocess.run(
        ['bash', '--noprofile', '--norc', '-e', '-c', step['run']],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
             'AZURE_CALL_MARKER': str(called), 'METIS_TEST_APP_READY': 'true',
             'METIS_DEPLOY_IDENTITY': 'metis-deploy-production',
             'AZURE_PRODUCTION_WEBAPP_NAME': 'vvn-metis-console'},
    )
    assert result.returncode == 1
    assert 'production_zip_deploy_retired' in result.stdout + result.stderr
    assert not called.exists()


def test_active_production_runbooks_have_no_zip_deploy_command():
    for name in ('AZURE_STEP9_CUTOVER_RUNBOOK.md', 'AZURE_RELEASE_RUNBOOK.md',
                 'TEST_AND_RELEASE_RUNBOOK.md', 'agents/deployment-protocol.md'):
        text = (ROOT / 'docs' / name).read_text()
        for block in re.findall(r'```[^\n]*\n(.*?)```', text, re.S):
            assert not (re.search(r'az\s+webapp\s+deploy\b', block) and
                        re.search(r'--type(?:\s+|=)[\"\']?zip\b', block)), name
        assert 'AZURE_RELEASE_RUNBOOK.md' in text or name == 'AZURE_RELEASE_RUNBOOK.md'
