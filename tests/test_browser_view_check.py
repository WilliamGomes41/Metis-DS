"""Actual browser trigger -> PG task -> separate browser -> private evidence.
# release-control-evidence: scope/belofte toegang opslag beschikbaarheid kwaliteit slop releasebewijs
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


@pytest.mark.skipif(not os.environ.get('METIS_BROWSER_EXECUTABLE'), reason='Required browser acceptance job supplies Chromium')
def test_browser_inzicht_investigation(tmp_path, complete_postgres):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'PYTHONPATH': str(root), 'METIS_BROWSER_BASE': f'http://127.0.0.1:{port}',
           'METIS_BROWSER_OUTPUT': str(tmp_path)}
    with (tmp_path / 'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tests.browser_view_check_fixture:app',
                                   '--host', '127.0.0.1', '--port', str(port)], cwd=root, env=env, stdout=log, stderr=log)
        try:
            for _ in range(200):
                try:
                    with urllib.request.urlopen(env['METIS_BROWSER_BASE']+'/browser-manifest'):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                pytest.fail((tmp_path/'server.log').read_text())
            # Fixture ingestion precedes browser reads; upload has its own acceptance test.
            run = subprocess.run(['node', str(root/'tests/browser_view_check.cjs')], cwd=root, env=env,
                                 capture_output=True, text=True, timeout=100)
            assert run.returncode == 0, run.stderr
            result = json.loads((tmp_path/'view-check-result.json').read_text())
            assert result['state'] == 'completed' and result['evidence']['status'] == 200
            assert result['domainUnchanged'] is True
            assert result['sourceCase']['state'] == 'completed'
            assert result['sourceCase']['evidence']['status'] == 200
        finally:
            server.terminate()
            server.wait(timeout=20)
