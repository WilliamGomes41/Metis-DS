# release-control-evidence: scope/belofte opslag toegang slop releasebewijs
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
def test_ko4_native_review_support_na_correction_and_restart(tmp_path, complete_postgres):
    project = Path(__file__).resolve().parents[1]
    configuration = tmp_path / 'fixture.json'
    configuration.write_text(json.dumps({'root': str(tmp_path / 'console'), 'dsn': complete_postgres.dsn}))
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        port = connection.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'PYTHONPATH': str(project), 'METIS_BROWSER_BASE': base,
        'METIS_BROWSER_OUTPUT': str(tmp_path), 'METIS_KO4_BROWSER_CONFIG': str(configuration),
        'METIS_KO4_SOURCE_SHA': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip(),
        'METIS_AUDIT_HMAC_KEY': 'ko4-browser-fixture-only'}
    for phase in ['before', 'after']:
        with (tmp_path / f'server-{phase}.log').open('w') as log:
            server = subprocess.Popen([sys.executable, '-m', 'uvicorn',
                'tests.browser_ko4_transitions_fixture:app', '--host', '127.0.0.1', '--port', str(port)],
                cwd=project, env=env, stdout=log, stderr=log)
            try:
                for _ in range(300):
                    try:
                        with urllib.request.urlopen(base + '/ko4-browser-manifest') as response:
                            json.load(response)
                        break
                    except OSError:
                        if server.poll() is not None:
                            pytest.fail((tmp_path / f'server-{phase}.log').read_text())
                        time.sleep(.1)
                else:
                    pytest.fail((tmp_path / f'server-{phase}.log').read_text())
                subprocess.run([env.get('METIS_BROWSER_NODE', 'node'),
                    str(project / 'tests/browser_ko4_transitions_check.cjs')], cwd=project,
                    env={**env, 'METIS_KO4_BROWSER_PHASE': phase}, check=True, timeout=240)
            finally:
                server.terminate()
                server.wait(timeout=15)
    result = json.loads((tmp_path / 'ko4-result.json').read_text())
    assert result['restart_preserved'] is True
    assert result['linked_approval'] is True
    assert result['explicit_not_applicable'] is True
    assert result['correction_reopens'] is True
