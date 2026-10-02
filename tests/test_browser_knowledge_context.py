"""Actual Chromium checks for full prose, exact second review and path alternatives.

# release-control-evidence: scope/belofte kwaliteit slop releasebewijs

Set METIS_BROWSER_EXECUTABLE to Chrome headless shell and
METIS_PLAYWRIGHT_MODULE to the installed Node Playwright module to run this test.
No browser runtime or dependency is introduced into the product.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

import pytest


@pytest.mark.skipif(not os.environ.get('METIS_BROWSER_EXECUTABLE'), reason='Chromium browser verification is opt-in')
def test_desktop_mobile_review_context_exact_revision_and_separate_paths(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as port:
        port.bind(('127.0.0.1', 0))
        address = port.getsockname()[1]
    base = f'http://127.0.0.1:{address}'
    env = dict(os.environ, PYTHONPATH=str(root), METIS_BROWSER_BASE=base,
               METIS_BROWSER_OUTPUT=str(tmp_path))
    import sys
    with (tmp_path/'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tests.browser_knowledge_context_fixture:app',
                                   '--host', '127.0.0.1', '--port', str(address)], cwd=root, env=env,
                                  stdout=log, stderr=log)
        try:
            for _ in range(200):
                try:
                    with urllib.request.urlopen(base+'/browser-manifest') as response:
                        json.load(response)
                    break
                except OSError:
                    time.sleep(.1)
            else:
                pytest.fail((tmp_path/'server.log').read_text())
            subprocess.run([env.get('METIS_BROWSER_NODE', 'node'), str(root/'tests/browser_knowledge_context_check.cjs')],
                           env=env, cwd=root, check=True, timeout=90)
            assert len(list(tmp_path.glob('*.png'))) == 6
        finally:
            server.terminate()
            server.wait(timeout=15)
