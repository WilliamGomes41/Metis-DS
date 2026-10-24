"""Actual Chromium run of Raad's deploy check against the PostgreSQL console.

# release-control-evidence: scope/belofte releasebewijs

Set METIS_BROWSER_EXECUTABLE and METIS_PLAYWRIGHT_MODULE to run this test.
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
def test_deploy_check_names_each_failing_page_and_changes_nothing(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as port:
        port.bind(('127.0.0.1', 0))
        address = port.getsockname()[1]
    base = f'http://127.0.0.1:{address}'
    env = dict(os.environ, PYTHONPATH=str(root), METIS_BROWSER_BASE=base, METIS_BROWSER_OUTPUT=str(tmp_path))
    with (tmp_path / 'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tests.browser_deploy_check_fixture:app',
                                   '--host', '127.0.0.1', '--port', str(address)], cwd=root, env=env,
                                  stdout=log, stderr=log)
        try:
            for _ in range(300):
                try:
                    with urllib.request.urlopen(base + '/browser-manifest') as response:
                        json.load(response)
                    break
                except OSError:
                    time.sleep(.1)
            else:
                pytest.fail((tmp_path / 'server.log').read_text())
            subprocess.run([env.get('METIS_BROWSER_NODE', 'node'), str(root / 'tests/browser_deploy_check.cjs')],
                           env=env, cwd=root, check=True, timeout=300)
            result = json.loads((tmp_path / 'deploy-check-result.json').read_text())
            assert result['domainUnchanged'] is True
        finally:
            server.terminate()
            server.wait(timeout=15)
