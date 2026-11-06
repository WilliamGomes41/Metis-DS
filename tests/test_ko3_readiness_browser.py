"""KO-3 actual browser proof over persisted PostgreSQL and a process restart.

# release-control-evidence: scope/belofte opslag slop releasebewijs
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import pytest


@pytest.mark.skipif(not os.environ.get('METIS_BROWSER_EXECUTABLE'), reason='Chromium browser verification is opt-in')
def test_ko3_readiness_review_publish_withdraw_and_restart(tmp_path, complete_postgres):
    project = Path(__file__).resolve().parents[1]
    config = tmp_path / 'fixture.json'
    config.write_text(json.dumps({'root': str(tmp_path / 'console'), 'dsn': complete_postgres.dsn}))
    with socket.socket() as socket_:
        socket_.bind(('127.0.0.1', 0))
        port = socket_.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'PYTHONPATH': str(project), 'METIS_BROWSER_BASE': base,
           'METIS_BROWSER_OUTPUT': str(tmp_path), 'METIS_KO3_BROWSER_CONFIG': str(config),
           'METIS_KO3_SOURCE_SHA': subprocess.check_output(
               ['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip(),
           'METIS_AUDIT_HMAC_KEY': 'ko3-browser-test-only'}
    for phase in ['before', 'after']:
        with (tmp_path / f'server-{phase}.log').open('w') as log:
            server = subprocess.Popen([sys.executable, '-m', 'uvicorn',
                'tests.browser_ko3_readiness_fixture:app', '--host', '127.0.0.1', '--port', str(port)],
                cwd=project, env=env, stdout=log, stderr=log)
            try:
                for _ in range(300):
                    try:
                        with urllib.request.urlopen(base + '/browser-manifest') as response:
                            json.load(response)
                        break
                    except OSError:
                        if server.poll() is not None:
                            pytest.fail((tmp_path / f'server-{phase}.log').read_text())
                        time.sleep(.1)
                else:
                    pytest.fail((tmp_path / f'server-{phase}.log').read_text())
                subprocess.run([env.get('METIS_BROWSER_NODE', 'node'),
                    str(project / 'tests/browser_ko3_readiness_check.cjs')], cwd=project,
                    env={**env, 'METIS_KO3_BROWSER_PHASE': phase}, check=True, timeout=180)
            finally:
                server.terminate()
                server.wait(timeout=15)
    result = json.loads((tmp_path / 'result.json').read_text())
    assert result['refusal_survived_restart'] is True
    assert result['published_object_count'] == 2
    assert result['withdrawn_projection_count'] == 0
    assert len(list(tmp_path.glob('ko3-*.png'))) >= 10
