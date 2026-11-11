"""Exercise sudo env-reset at the actual CI dependency-command boundary.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def setup(tmp_path):
    # Simulate sudo's env_reset; without --preserve-env the child cannot use the
    # runner network. No root access, network request or real credentials needed.
    sudo = tmp_path/'sudo'
    sudo.write_text('#!'+sys.executable+'\n'+'''import os, sys
args=sys.argv[1:]
env={'PATH':os.environ['PATH']}
if args[0].startswith('--preserve-env='):
    for name in args.pop(0).split('=',1)[1].split(','):
        if name in os.environ: env[name]=os.environ[name]
os.execve(args[0], args, env)
''')
    sudo.chmod(0o700)
    env = {key:value for key,value in os.environ.items() if key.lower() not in ('http_proxy','https_proxy','no_proxy')}
    env.update(PATH=str(tmp_path)+os.pathsep+env['PATH'], HTTP_PROXY='http://proxy.invalid:8080',
               HTTPS_PROXY='http://secure-proxy.invalid:8080', NO_PROXY='localhost,127.0.0.1')
    command = [sys.executable, '-c', '''import os
assert os.environ.get('http_proxy') == 'http://proxy.invalid:8080', 'APT_PROXY_LOST'
assert os.environ.get('https_proxy') == 'http://secure-proxy.invalid:8080', 'APT_PROXY_LOST'
assert os.environ.get('no_proxy') == 'localhost,127.0.0.1', 'APT_PROXY_LOST'
print('apt-proxy-preserved')''']
    return env, command


def test_apt_command_survives_sudo_env_reset(tmp_path):
    env, command = setup(tmp_path)
    red = subprocess.run(['sudo', *command], env=env, capture_output=True, text=True)
    assert red.returncode != 0 and 'APT_PROXY_LOST' in red.stderr
    result = subprocess.run(['bash', str(ROOT/'scripts/ci_with_apt_proxy.sh'), *command],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'apt-proxy-preserved'


def test_dependency_failure_is_not_masked(tmp_path):
    env, _ = setup(tmp_path)
    result = subprocess.run(['bash', str(ROOT/'scripts/ci_with_apt_proxy.sh'),
                             sys.executable, '-c', 'raise SystemExit(42)'], env=env,
                            capture_output=True, text=True)
    assert result.returncode == 42


def test_both_dependency_consumers_use_the_proxy_boundary():
    import yaml
    action = yaml.safe_load((ROOT/'.github/actions/install-test-browser/action.yml').read_text())
    commands = '\n'.join(step.get('run','') for step in action['runs']['steps'])
    assert 'bash scripts/ci_with_apt_proxy.sh "$browser" install-deps chromium' in commands
    job = yaml.safe_load((ROOT/'.github/workflows/docling-acceptance.yml').read_text())['jobs']['real-pdf']
    commands = '\n'.join(step.get('run','') for step in job['steps'])
    assert 'bash scripts/ci_with_apt_proxy.sh apt-get update' in commands
    assert 'bash scripts/ci_with_apt_proxy.sh apt-get install' in commands
