"""Opt-in Chromium proof over real PostgreSQL, following existing browser fixtures.

# release-control-evidence: scope/belofte toegang kwaliteit slop releasebewijs
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


@pytest.mark.skipif(not os.environ.get("METIS_BROWSER_EXECUTABLE"), reason="Chromium must be supplied for browser verification")
def test_metis_explained_desktop_mobile_and_no_javascript(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        port = connection.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "PYTHONPATH": str(root), "METIS_BROWSER_BASE": base,
           "METIS_BROWSER_OUTPUT": str(tmp_path)}
    with (tmp_path / "server.log").open("w") as log:
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "tests.browser_metis_explained_fixture:app",
                                   "--host", "127.0.0.1", "--port", str(port)], cwd=root,
                                  env=env, stdout=log, stderr=log)
        try:
            for _ in range(200):
                try:
                    with urllib.request.urlopen(base + "/browser-manifest") as response:
                        json.load(response)
                    break
                except OSError:
                    if server.poll() is not None:
                        pytest.fail((tmp_path / "server.log").read_text())
                    time.sleep(.1)
            else:
                pytest.fail((tmp_path / "server.log").read_text())
            subprocess.run([env.get("METIS_BROWSER_NODE", "node"), str(root / "tests/browser_metis_explained_check.cjs")],
                           cwd=root, env=env, check=True, timeout=90)
            assert len(list(tmp_path.glob("*.png"))) == 8
        finally:
            server.terminate()
            server.wait(timeout=15)
