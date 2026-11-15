"""Run existing tests on an owned, disposable PostgreSQL server; no Azure I/O."""
from pathlib import Path
import json
import os
import socket
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PG = Path(os.environ.get('PGBIN', '/workspace/.postgres/usr/lib/postgresql/17/bin'))
SHARE = PG.parents[3] / 'share/postgresql' / PG.parent.name
PYTHON = sys.executable

def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)

def main():
    OUT.mkdir(exist_ok=True)
    state = Path(tempfile.mkdtemp(prefix='metis-pg-design-'))
    data = state / 'data'
    started = False
    results = {}
    try:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with (OUT / 'server-setup.log').open('w') as log:
            run([PG/'initdb', '-D', data, '-L', SHARE, '-U', 'postgres',
                 '--encoding=UTF8', '--no-locale', '--auth-local=trust', '--auth-host=trust'], stdout=log, stderr=log)
            run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                 '-keyout', state/'server.key', '-out', state/'server.crt',
                 '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost',
                 '-addext', 'basicConstraints=critical,CA:TRUE'], stdout=log, stderr=log)
            (state/'server.key').chmod(0o600)
            options = f'-h 127.0.0.1 -p {port} -k {state} -c timezone=UTC -c ssl=on -c ssl_cert_file={state}/server.crt -c ssl_key_file={state}/server.key'
            run([PG/'pg_ctl', '-D', data, '-l', state/'server.log', '-o', options, '-w', 'start'], stdout=log, stderr=log)
            started = True
        dsn = f'postgresql://postgres@127.0.0.1:{port}/postgres'
        env = {**os.environ, 'METIS_TEST_POSTGRES_DSN': dsn, 'PYTHON': PYTHON,
               'PYTHONPATH': str(ROOT), 'DESIGN_PROBE_PORT': str(port),
               'DESIGN_PROBE_CERT': str(state/'server.crt')}
        with (OUT/'postgres-preflight.log').open('w') as log:
            run(['bash', 'scripts/test_postgres.sh'], cwd=ROOT, env=env, stdout=log, stderr=log)
        selected = [
            'tests/test_workflow_postgres_migration_v1.py',
            'tests/test_workflow_runtime_privileges_v1.py',
            'tests/test_workflow_transaction_v1.py',
            'tests/test_workflow_postgres_concurrency.py',
            'tests/test_migration_018_postgres_v1.py',
            'tests/test_azure_step9_cutover_v1.py',
        ]
        with (OUT/'baseline.log').open('w') as log:
            result = subprocess.run([PYTHON, '-m', 'pytest', '-q', *selected,
                '--junitxml='+str(OUT/'baseline.xml')], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            results['pytest_exit_code'] = result.returncode
        with (OUT/'probes.log').open('w') as log:
            result = subprocess.run([PYTHON, str(OUT/'probes.py')], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            results['probes_exit_code'] = result.returncode
        results['postgres_version'] = subprocess.check_output([str(PG/'postgres'), '--version'], text=True).strip()
        results['git_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    finally:
        if started:
            with (OUT/'server-setup.log').open('a') as log:
                run([PG/'pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop'], stdout=log, stderr=log)
            results['owned_server_stopped'] = True
        import shutil
        shutil.rmtree(state)
        (OUT/'summary.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results, indent=2))
    return int(bool(results.get('pytest_exit_code') or results.get('probes_exit_code')))

if __name__ == '__main__':
    sys.exit(main())
