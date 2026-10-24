"""Executable workflow contracts: failed browser retries must not repeat suites.

# release-control-evidence: scope/belofte slop releasebewijs
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.safe_load((ROOT/'.github/workflows'/name).read_text())


def test_browser_is_independent_and_existing_required_checks_gate_all_shards():
    jobs = workflow('ci.yml')['jobs']
    assert 'suite' in jobs and 'browser' in jobs
    assert jobs['suite']['strategy']['matrix']['shard'] == [0, 1, 2, 3]
    assert jobs['suite']['strategy']['matrix']['python-version'] == ['3.12', '3.13']
    assert 'suite' not in jobs['browser']['needs']
    assert {'suite', 'browser', 'characterization-evidence'} <= set(jobs['test']['needs'])
    assert jobs['test']['strategy']['matrix']['python-version'] == ['3.12', '3.13']
    assert not any('pytest ' in s.get('run','') and 'browser' in s['run'] for s in jobs['test']['steps'])
    # upload-artifact v4 otherwise returns HTTP 409 when a failed job already
    # uploaded evidence. Retrying that job must replace its proof, not fail again.
    for name, job in jobs.items():
        if name == 'package':
            continue
        for step in job['steps']:
            if step.get('uses') == 'actions/upload-artifact@v4':
                assert step['with'].get('overwrite') is True, (name, step.get('name'))


def test_deployments_download_verified_package_before_azure_without_rerunning_suite():
    for name in ('deploy-test.yml', 'deploy-production.yml'):
        data = workflow(name)
        trigger = data.get('on', data.get(True))
        assert {'commit_sha', 'ci_run_id'} <= set(trigger['workflow_dispatch']['inputs'])
        steps = data['jobs']['deploy']['steps']
        commands = '\n'.join(s.get('run','') for s in steps)
        assert 'pytest -q' not in commands
        assert 'create_azure_deploy_package.sh' not in commands
        verify = next(i for i,s in enumerate(steps) if 'verified_deploy_artifact.py verify' in s.get('run',''))
        login = next(i for i,s in enumerate(steps) if s.get('uses') == 'azure/login@v2')
        assert verify < login
        download = next(s for s in steps if s.get('uses') == 'actions/download-artifact@v4')
        assert download['with']['run-id'] == '${{ inputs.ci_run_id }}'
        assert data['permissions']['actions'] == 'read'


def test_package_only_builds_on_main_after_all_existing_ci_gates():
    job = workflow('ci.yml')['jobs']['package']
    assert {'test', 'browser', 'characterization-evidence'} <= set(job['needs'])
    assert "github.event_name == 'push'" in job['if']
    assert "github.ref == 'refs/heads/main'" in job['if']
    commands = '\n'.join(s.get('run','') for s in job['steps'])
    assert 'bash scripts/create_azure_deploy_package.sh' in commands
    assert 'verified_deploy_artifact.py seal' in commands
